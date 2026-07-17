# -*- coding: utf-8 -*-
"""向量场模式工作区 — 2D/3D 向量场可视化。"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from MF_UI.plot import mpl_setup  # noqa — 中文字体 + 后端初始化
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class VectorFieldWorkspace(QWidget):
    """向量场模式工作区 — F(x,y) = (P, Q) 形式。"""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._px = ""; self._py = ""
        self._x0, self._x1 = -5.0, 5.0
        self._y0, self._y1 = -5.0, 5.0
        self._res = 30
        self._auto_density = True
        self._streamline = False  # False=quiver, True=streamplot
        self._heatmap = 0  # 0=无, 1=散度, 2=旋度

        self._build_ui()
        self._show_waiting()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self); root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        t = QLabel("向量场模式 — F(x, y) = (P, Q)")
        t.setObjectName("plot_title_label")
        root.addWidget(t)

        # 分量输入
        for lbl, attr, ph in [("P(x,y) =", "_px","-y"), ("Q(x,y) =", "_py","x")]:
            r = QHBoxLayout(); r.setSpacing(6)
            r.addWidget(QLabel(lbl))
            inp = QLineEdit(); inp.setPlaceholderText(ph)
            inp.setObjectName("vf_input")
            inp.textChanged.connect(lambda _, a=attr, i=inp: setattr(self, a, i.text().strip()))
            r.addWidget(inp, 1); root.addLayout(r)

        # 参数
        pr = QHBoxLayout(); pr.setSpacing(8)
        for lbl, mn, mx, attr in [("x:",-100,100,"_x0"),("~",-100,100,"_x1"),
                                   ("y:",-100,100,"_y0"),("~",-100,100,"_y1")]:
            if not lbl.startswith("~"): pr.addWidget(QLabel(lbl))
            s = QDoubleSpinBox(); s.setRange(mn,mx); s.setValue(-5 if "0" in attr else 5)
            s.setDecimals(1); s.valueChanged.connect(lambda v,a=attr: setattr(self,a,v))
            pr.addWidget(s)
        pr.addWidget(QLabel(" 密度:"))
        rs = QSpinBox(); rs.setRange(10,60); rs.setValue(30)
        rs.valueChanged.connect(lambda v: setattr(self,"_res",v))
        pr.addWidget(rs)
        self._density_spin = rs  # 保存引用以便自动模式禁用

        from PySide6.QtWidgets import QCheckBox
        auto_cb = QCheckBox("自动"); auto_cb.setChecked(True)
        auto_cb.toggled.connect(self._on_auto_density)
        pr.addWidget(auto_cb)

        cb = QCheckBox("流线"); cb.setChecked(False)
        cb.toggled.connect(lambda v: setattr(self,"_streamline",v))
        pr.addWidget(cb)

        from PySide6.QtWidgets import QComboBox as QCB
        heat_label = QLabel("标量场:")
        pr.addWidget(heat_label)
        hm_cb = QCB()
        hm_cb.addItems(["无", "散度 ∇·F", "旋度 ∇×F"])
        hm_cb.currentIndexChanged.connect(lambda v: setattr(self, "_heatmap", v))
        pr.addWidget(hm_cb)

        btn = QPushButton("重绘")
        btn.setObjectName("vf_redraw_btn")
        btn.clicked.connect(self._redraw); pr.addWidget(btn)
        pr.addStretch(); root.addLayout(pr)

        from MF_UI.plot.mpl_setup import get_mpl_figure_facecolor
        self._fig = Figure(facecolor=get_mpl_figure_facecolor())
        self._canvas = FigureCanvasQTAgg(self._fig); self._canvas.setMinimumHeight(400)
        root.addWidget(self._canvas, 1)

        self._waiting = QLabel("等待输入分量 P、Q")
        self._waiting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._waiting.setObjectName("vf_waiting")
        root.addWidget(self._waiting); self._canvas.hide()

    def resizeEvent(self, event) -> None:
        """窗口大小变化时 debounce 重绘（避免快速拖拽时频繁 lambdify）。"""
        super().resizeEvent(event)
        if self._auto_density and (self._px or self._py):
            if hasattr(self, '_resize_timer'):
                self._resize_timer.start(150)  # 重置定时器
            else:
                from PySide6.QtCore import QTimer
                self._resize_timer = QTimer(self)
                self._resize_timer.setSingleShot(True)
                self._resize_timer.timeout.connect(self._redraw)
                self._resize_timer.start(150)

    def _on_auto_density(self, checked: bool) -> None:
        """切换自动密度模式。"""
        self._auto_density = checked
        self._density_spin.setEnabled(not checked)
        if checked:
            self._redraw()

    def _compute_auto_resolution(self) -> int:
        """根据画布像素尺寸和视口范围自动计算最佳密度。

        目标：约每 22~30 像素一个箭头，确保视觉密度适中。
        密度范围限制在 [10, 60]，避免过稀或计算量过大。
        """
        w = self._canvas.width()
        h = self._canvas.height()
        if w <= 0 or h <= 0:
            return 30  # 画布尚未显示，使用默认值

        # 最大维度像素数决定基础分辨率
        max_px = max(w, h)
        # 每 22px 一个箭头 → 视觉密度舒适
        target_res = max_px / 22

        # 视口范围修正：范围越大需要越高分辨率
        x_range = self._x1 - self._x0
        y_range = self._y1 - self._y0
        range_factor = max(x_range, y_range) / 10.0  # 以 10 为基准
        target_res *= (1.0 + range_factor * 0.15)  # 适度放大

        return max(10, min(60, int(target_res)))

    def _show_waiting(self):
        self._fig.clear(); self._canvas.draw_idle()
        self._canvas.hide(); self._waiting.show()

    def _redraw(self) -> None:
        if not self._px and not self._py:
            self._show_waiting(); return
        rng = max(self._x1-self._x0, self._y1-self._y0)
        if rng > 100:
            r = QMessageBox.warning(self, "范围过大",
                f"范围 {rng:.0f} 过大，可能导致卡顿。继续？",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes: return

        try:
            import sympy as sp
            x,y = sp.Symbol("x"), sp.Symbol("y")
            fP = sp.lambdify((x,y), sp.sympify(self._px or "0"), "numpy")
            fQ = sp.lambdify((x,y), sp.sympify(self._py or "0"), "numpy")
        except Exception as e:
            self._show_waiting(); self.status_message.emit(f"表达式错误: {e}"); return

        res = self._compute_auto_resolution() if self._auto_density else self._res
        xs = np.linspace(self._x0, self._x1, res)
        ys = np.linspace(self._y0, self._y1, res)
        X, Y = np.meshgrid(xs, ys)
        try:
            U, V = fP(X,Y), fQ(X,Y)
        except Exception as e:
            self._show_waiting(); self.status_message.emit(f"计算错误: {e}"); return

        U = np.nan_to_num(U); V = np.nan_to_num(V)
        M = np.sqrt(U**2+V**2); M = np.where(M>0, M, 1)

        self._waiting.hide(); self._canvas.show()
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        if self._streamline:
            ax.streamplot(X, Y, U, V, color=M, cmap="viridis", density=1.5,
                          linewidth=1, arrowsize=0.8)
        else:
            ax.quiver(X, Y, U/M, V/M, M, cmap="viridis", scale=30, width=0.003)
        ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_aspect("equal")
        title_parts = [f"F = ({self._px or 0}, {self._py or 0})"]

        # ── 散度/旋度热图叠加 ──
        if self._heatmap > 0 and self._px and self._py:
            try:
                dx = xs[1] - xs[0]
                dy = ys[1] - ys[0]
                if self._heatmap == 1:  # 散度: dP/dx + dQ/dy
                    dU_dx = np.gradient(U, dx, axis=1)
                    dV_dy = np.gradient(V, dy, axis=0)
                    scalar = dU_dx + dV_dy
                    title_parts.append("散度 ∇·F")
                else:  # 旋度: dQ/dx - dP/dy
                    dV_dx = np.gradient(V, dx, axis=1)
                    dU_dy = np.gradient(U, dy, axis=0)
                    scalar = dV_dx - dU_dy
                    title_parts.append("旋度 ∇×F")
                cf = ax.contourf(X, Y, scalar, levels=20, cmap="RdBu_r",
                                 alpha=0.35, zorder=0)
                self._fig.colorbar(cf, ax=ax, shrink=0.7, label="标量值")
            except Exception:
                pass  # 计算失败时静默跳过

        ax.set_title(" | ".join(title_parts))
        self._canvas.draw_idle()
        mode = "流线" if self._streamline else "箭头"
        hm_tag = {1: "+散度", 2: "+旋度"}.get(self._heatmap, "")
        auto_tag = "[自动]" if self._auto_density else ""
        self.status_message.emit(
            f"已绘制({mode}){hm_tag}{auto_tag}: ({self._px},{self._py}) {res}×{res}")
