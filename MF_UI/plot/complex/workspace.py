# -*- coding: utf-8 -*-
"""复数模式工作区 — 复变函数可视化。

支持三种绘制模式: 相位图 / 3D 模长曲面 / 向量场式。
非实时重绘: 修改参数后需点击"重绘"按钮。
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.colors as mcolors


class ComplexWorkspace(QWidget):
    """复数模式工作区。"""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._func_expr = ""
        self._mode = 0           # 0=相位图 1=3D模长 2=向量场
        self._x_min, self._x_max = -5.0, 5.0
        self._y_min, self._y_max = -5.0, 5.0
        self._resolution = 200

        self._build_ui()
        self._show_waiting()

    # ── UI ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8); root.setContentsMargins(12, 12, 12, 12)

        # ── 标题 ──
        title = QLabel("复数模式 — 复变函数可视化")
        title.setStyleSheet("font-size:16px;font-weight:600;color:#0f172a;")
        root.addWidget(title)

        # ── 函数输入行 ──
        fr = QHBoxLayout(); fr.setSpacing(6)
        fr.addWidget(QLabel("f(z) ="))
        self._input = QLineEdit()
        self._input.setPlaceholderText("z**2, sin(z), exp(z)...")
        self._input.setStyleSheet(
            "QLineEdit{border:1px solid #d1d5db;border-radius:4px;"
            "padding:6px 10px;font-size:14px;background:#fff;}"
            "QLineEdit:focus{border-color:#3b82f6;}")
        self._input.returnPressed.connect(self._apply)
        fr.addWidget(self._input, 1)

        btn_apply = QPushButton("应用")
        btn_apply.setStyleSheet(
            "QPushButton{background:#3b82f6;color:#fff;border:none;"
            "border-radius:4px;padding:6px 16px;font-size:13px;font-weight:500;}"
            "QPushButton:hover{background:#2563eb;}")
        btn_apply.clicked.connect(self._apply)
        fr.addWidget(btn_apply)
        root.addLayout(fr)

        # ── 模式选择 ──
        mr = QHBoxLayout(); mr.setSpacing(4)
        mr.addWidget(QLabel("模式:"))
        self._btn_phase = QPushButton("相位图")
        self._btn_3d = QPushButton("3D 模长")
        self._btn_vec = QPushButton("向量场")
        for b, i in [(self._btn_phase,0),(self._btn_3d,1),(self._btn_vec,2)]:
            b.setCheckable(True); b.setChecked(i==0)
            b.setStyleSheet(self._mode_btn_style(i==0))
            b.clicked.connect(lambda _, idx=i: self._set_mode(idx))
            mr.addWidget(b)
        mr.addStretch()
        root.addLayout(mr)

        # ── 范围 + 分辨率 + 重绘 ──
        pr = QHBoxLayout(); pr.setSpacing(8)

        pr.addWidget(QLabel("x:"))
        self._xmin = QDoubleSpinBox(); self._xmin.setRange(-1000,1000)
        self._xmin.setValue(-5); self._xmin.setDecimals(1)
        self._xmin.setStyleSheet("QDoubleSpinBox{width:60px;}")
        pr.addWidget(self._xmin)
        pr.addWidget(QLabel("~"))
        self._xmax = QDoubleSpinBox(); self._xmax.setRange(-1000,1000)
        self._xmax.setValue(5); self._xmax.setDecimals(1)
        pr.addWidget(self._xmax)

        pr.addWidget(QLabel("  y:"))
        self._ymin = QDoubleSpinBox(); self._ymin.setRange(-1000,1000)
        self._ymin.setValue(-5); self._ymin.setDecimals(1)
        pr.addWidget(self._ymin)
        pr.addWidget(QLabel("~"))
        self._ymax = QDoubleSpinBox(); self._ymax.setRange(-1000,1000)
        self._ymax.setValue(5); self._ymax.setDecimals(1)
        pr.addWidget(self._ymax)

        pr.addWidget(QLabel("  分辨率:"))
        self._res = QSpinBox(); self._res.setRange(50,1000)
        self._res.setValue(200); self._res.setSuffix("px")
        pr.addWidget(self._res)

        self._btn_redraw = QPushButton("重绘")
        self._btn_redraw.setStyleSheet(
            "QPushButton{background:#10b981;color:#fff;border:none;"
            "border-radius:4px;padding:6px 20px;font-size:13px;font-weight:500;}"
            "QPushButton:hover{background:#059669;}")
        self._btn_redraw.clicked.connect(self._redraw)
        pr.addWidget(self._btn_redraw)
        pr.addStretch()
        root.addLayout(pr)

        # ── 画布区 ──
        self._fig = Figure(facecolor="#f8fafc")
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(400)
        root.addWidget(self._canvas, 1)

        # 默认隐藏 canvas，显示等待提示
        self._waiting_label = QLabel("等待输入函数")
        self._waiting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._waiting_label.setStyleSheet(
            "font-size:18px;color:#94a3b8;background:transparent;")
        root.addWidget(self._waiting_label)
        self._canvas.hide()

    def _mode_btn_style(self, active: bool) -> str:
        if active:
            return ("QPushButton{background:#3b82f6;color:#fff;border:none;"
                    "border-radius:4px;padding:4px 12px;font-size:12px;font-weight:500;}")
        return ("QPushButton{background:#f1f5f9;color:#475569;border:1px solid #d1d5db;"
                "border-radius:4px;padding:4px 12px;font-size:12px;}")

    def _set_mode(self, idx: int) -> None:
        self._mode = idx
        for b, i in [(self._btn_phase,0),(self._btn_3d,1),(self._btn_vec,2)]:
            b.setStyleSheet(self._mode_btn_style(i==idx))

    # ── 应用 / 重绘 ──────────────────────────────────────────

    def _apply(self) -> None:
        raw = self._input.text().strip()
        if not raw:
            self._func_expr = ""
            self._show_waiting()
            self.status_message.emit("就绪")
            return

        # 测试表达式是否有效
        try:
            import sympy as sp
            z_sym = sp.Symbol("z")
            sp.sympify(raw.replace("I","1j").replace("i","1j"))
        except Exception:
            self._func_expr = ""
            self._show_waiting()
            self.status_message.emit("表达式无效")
            return

        self._func_expr = raw
        self._hide_waiting()
        self._redraw()

    def _redraw(self) -> None:
        if not self._func_expr:
            self._show_waiting(); return

        x_min = self._xmin.value(); x_max = self._xmax.value()
        y_min = self._ymin.value(); y_max = self._ymax.value()
        res = self._res.value()

        # 范围过大警告
        rng = max(x_max - x_min, y_max - y_min)
        if rng > 100:
            r = QMessageBox.warning(self, "范围过大",
                f"绘图范围 {rng:.0f}×{rng:.0f} 过大，可能导致卡顿。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes: return

        # 分辨率过高警告
        if res > 600:
            r = QMessageBox.warning(self, "分辨率过高",
                f"分辨率 {res}×{res} 可能导致卡顿。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes: return

        self._hide_waiting()
        self._compute_and_draw(x_min, x_max, y_min, y_max, res)

    # ── 状态切换 ─────────────────────────────────────────────

    def _show_waiting(self) -> None:
        self._fig.clear()
        self._canvas.draw_idle()
        self._canvas.hide()
        self._waiting_label.show()

    def _hide_waiting(self) -> None:
        self._waiting_label.hide()
        self._canvas.show()

    # ── 计算与绘制 ───────────────────────────────────────────

    def _compute_and_draw(self, x0, x1, y0, y1, res):
        try:
            import sympy as sp
            z_sym = sp.Symbol("z")
            raw = self._func_expr.replace("I","1j").replace("i","1j")
            expr = sp.sympify(raw)
            f = sp.lambdify(z_sym, expr, "numpy")
        except Exception as e:
            self._show_waiting()
            self.status_message.emit(f"表达式错误: {e}")
            return

        xs = np.linspace(x0, x1, res)
        ys = np.linspace(y0, y1, res)
        X, Y = np.meshgrid(xs, ys)
        Z = X + 1j * Y

        try:
            W = f(Z)
        except Exception as e:
            self._show_waiting()
            self.status_message.emit(f"计算错误: {e}")
            return

        W = np.nan_to_num(W, nan=0.0, posinf=0.0, neginf=0.0)
        mag = np.abs(W)
        arg = np.angle(W)

        self._fig.clear()

        if self._mode == 0:
            self._draw_phase(X, Y, arg, mag)
        elif self._mode == 1:
            self._draw_3d_surface(X, Y, mag)
        elif self._mode == 2:
            self._draw_vector(X, Y, mag, arg)

        self._canvas.draw_idle()
        self.status_message.emit(
            f"已绘制: {self._func_expr} | {['相位图','3D模长','向量场'][self._mode]} "
            f"| 范围[{x0:.0f},{x1:.0f}]×[{y0:.0f},{y1:.0f}] | {res}×{res}")

    # ── 相位图 ───────────────────────────────────────────────

    def _draw_phase(self, X, Y, arg, mag):
        ax = self._fig.add_subplot(111)
        H = (arg + np.pi) / (2 * np.pi)  # 0~1
        # HSV: H=辐角, S=1, V=亮度随模长变化
        S = np.ones_like(H)
        V = np.clip(mag / (mag.max() + 1e-10), 0.3, 1.0)
        HSV = np.stack([H, S, V], axis=-1)
        RGB = mcolors.hsv_to_rgb(HSV)
        ax.imshow(RGB, extent=[X.min(), X.max(), Y.min(), Y.max()], origin="lower")
        ax.set_xlabel("Re(z)"); ax.set_ylabel("Im(z)")
        ax.set_title(f"相位图: {self._func_expr}")

    # ── 3D 模长曲面 ──────────────────────────────────────────

    def _draw_3d_surface(self, X, Y, mag):
        ax = self._fig.add_subplot(111, projection="3d")
        ax.plot_surface(X, Y, mag, cmap="viridis", linewidth=0,
                        antialiased=True, alpha=0.9)
        ax.set_xlabel("Re(z)"); ax.set_ylabel("Im(z)"); ax.set_zlabel("|f(z)|")
        ax.set_title(f"模长曲面: {self._func_expr}")
        ax.view_init(elev=30, azim=-60)

    # ── 向量场式 ─────────────────────────────────────────────

    def _draw_vector(self, X, Y, mag, arg):
        ax = self._fig.add_subplot(111)
        # 降采样以避免箭头过密
        skip = max(1, len(X) // 40)
        Xs = X[::skip, ::skip]; Ys = Y[::skip, ::skip]
        mag_s = mag[::skip, ::skip]; arg_s = arg[::skip, ::skip]

        U = mag_s * np.cos(arg_s)
        V = mag_s * np.sin(arg_s)
        colors = (arg_s + np.pi) / (2 * np.pi)

        ax.quiver(Xs, Ys, U, V, colors, cmap="hsv", alpha=0.8,
                  scale=mag_s.max() * 2 if mag_s.max() > 0 else 1,
                  width=0.002)
        ax.set_xlabel("Re(z)"); ax.set_ylabel("Im(z)")
        ax.set_aspect("equal")
        ax.set_title(f"向量场: {self._func_expr}")
