# -*- coding: utf-8 -*-
"""复数模式工作区 — 复变函数可视化（侧边栏 + 画布）。

支持: 相位图 / 3D 模长曲面 / 向量场式
特殊函数: zeta(z), gamma(z), erf(z)...
数学输入: e^z, sinz, |z|...
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from MF_UI.plot import mpl_setup  # noqa — 中文字体 + 后端初始化
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.colors as mcolors


def _preprocess_complex(s: str) -> str:
    """自然数学输入 → sympy 兼容格式。"""
    import re
    # e^ → exp(（e^z → exp(z), e^(...) → exp(...)）
    s = re.sub(r"\be\^\((.+)\)", r"exp(\1)", s)
    s = re.sub(r"\be\^(\w+)", r"exp(\1)", s)
    s = s.replace("^", "**")
    # 函数别名
    for a, c in [("ln","log"),("arcsin","asin"),("arccos","acos"),
                 ("arctan","atan"),("sen","sin"),("tg","tan")]:
        s = re.sub(rf"\b{a}\b", c, s)
    # 已知函数名保护
    KF = {"sin","cos","tan","cot","sec","csc","sinh","cosh","tanh","coth",
          "asin","acos","atan","arcsin","arccos","arctan",
          "ln","log","sqrt","exp","abs","gamma","zeta","erf","erfc",
          "pi","E","I","oo","z"}
    mk = {}
    for i, fn in enumerate(sorted(KF, key=len, reverse=True)):
        m = f"\x00{i}\x00"; mk[m] = fn; s = s.replace(fn, m)
    # 隐式乘法
    s = re.sub(r"(\d)\s*\(", r"\1*(", s)
    s = re.sub(r"\)\s*\(", ")*(", s)
    s = re.sub(r"\)([a-zA-Z])", r")*\1", s)
    s = re.sub(r"([a-zA-Z])\s*\(", r"\1*(", s)
    s = re.sub(r"([a-zA-Z])\s+([a-zA-Z])", r"\1*\2", s)
    s = re.sub(r"([a-zA-Z])([a-zA-Z])", r"\1*\2", s)
    for m, fn in mk.items(): s = s.replace(m, fn)
    s = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", s)
    # func+letter → func(letter)（sinz → sin(z)）
    F = "sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|coth|arcsin|arccos|arctan|asin|acos|atan|ln|log|sqrt|exp|abs|gamma|zeta|erf"
    s = re.sub(rf"\b({F})([a-zA-Z])", r"\1(\2)", s)
    return s


class ComplexWorkspace(QWidget):
    """复数模式工作区 — 左侧控制面板 + 右侧画布。"""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._func_expr = ""
        self._mode = 0
        self._x_min, self._x_max = -5.0, 5.0
        self._y_min, self._y_max = -5.0, 5.0
        self._resolution = 200

        self._build_ui()
        self._show_waiting()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # ── 左侧面板 (280px) ──
        left = QWidget(); left.setFixedWidth(280)
        left.setObjectName("plot_left_panel")
        ll = QVBoxLayout(left); ll.setSpacing(8)
        ll.setContentsMargins(12, 12, 12, 12)

        t = QLabel("复数模式")
        t.setObjectName("plot_title_label")
        ll.addWidget(t)

        # 函数输入
        ll.addWidget(QLabel("f(z) ="))
        self._input = QLineEdit()
        self._input.setObjectName("complex_input")
        self._input.setPlaceholderText("e^z, sin(z), zeta(z), gamma(z)...")
        self._input.returnPressed.connect(self._apply)
        ll.addWidget(self._input)

        btn_apply = QPushButton("应用")
        btn_apply.setObjectName("complex_apply_btn")
        btn_apply.clicked.connect(self._apply)
        ll.addWidget(btn_apply)

        # 分隔
        ll.addWidget(_sep())

        # 模式选择
        ll.addWidget(QLabel("绘制模式"))
        self._btn_phase = QPushButton("相位图")
        self._btn_3d = QPushButton("3D 模长曲面")
        self._btn_vec = QPushButton("向量场式")
        self._btn_hsv = QPushButton("HSV 域着色")
        self._btn_conf = QPushButton("共形映射网格")
        btns = [(self._btn_phase,0),(self._btn_3d,1),(self._btn_vec,2),
                (self._btn_hsv,3),(self._btn_conf,4)]
        for b, i in btns:
            b.setCheckable(True); b.setChecked(i==0)
            b.setObjectName("complex_mode_btn")
            b.setProperty("active", i==0)
            b.clicked.connect(lambda _, idx=i: self._set_mode(idx))
            ll.addWidget(b)

        ll.addWidget(_sep())

        # 范围
        ll.addWidget(QLabel("绘图范围"))
        for lbl, attr0, attr1 in [("x","_x_min","_x_max"),("y","_y_min","_y_max")]:
            r = QHBoxLayout(); r.setSpacing(4)
            r.addWidget(QLabel(f"{lbl}:"))
            s0 = QDoubleSpinBox(); s0.setRange(-1000,1000); s0.setValue(-5)
            s0.setDecimals(1); s0.valueChanged.connect(lambda v,a=attr0: setattr(self,a,v))
            r.addWidget(s0)
            r.addWidget(QLabel("~"))
            s1 = QDoubleSpinBox(); s1.setRange(-1000,1000); s1.setValue(5)
            s1.setDecimals(1); s1.valueChanged.connect(lambda v,a=attr1: setattr(self,a,v))
            r.addWidget(s1); ll.addLayout(r)

        # 分辨率
        rr = QHBoxLayout(); rr.setSpacing(4)
        rr.addWidget(QLabel("分辨率:"))
        self._res = QSpinBox(); self._res.setRange(50,1000)
        self._res.setValue(200); self._res.setSuffix("px"); rr.addWidget(self._res)
        rr.addStretch(); ll.addLayout(rr)

        # 重绘
        self._btn_redraw = QPushButton("重绘")
        self._btn_redraw.setObjectName("complex_redraw_btn")
        self._btn_redraw.clicked.connect(self._redraw)
        ll.addWidget(self._btn_redraw)

        ll.addStretch()
        root.addWidget(left)

        # ── 右侧画布 ──
        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(0,0,0,0)
        from MF_UI.plot.mpl_setup import get_mpl_figure_facecolor
        self._fig = Figure(facecolor=get_mpl_figure_facecolor())
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(400)
        rl.addWidget(self._canvas)

        self._waiting_label = QLabel("等待输入函数")
        self._waiting_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._waiting_label.setObjectName("complex_waiting")
        rl.addWidget(self._waiting_label)
        self._canvas.hide()
        root.addWidget(right, 1)

    def _set_mode(self, idx: int) -> None:
        self._mode = idx
        for b, i in [(self._btn_phase,0),(self._btn_3d,1),(self._btn_vec,2),
                      (self._btn_hsv,3),(self._btn_conf,4)]:
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)

    def _apply(self) -> None:
        raw = self._input.text().strip()
        if not raw:
            self._func_expr = ""; self._show_waiting()
            self.status_message.emit("就绪"); return
        try:
            import sympy as sp
            s = _preprocess_complex(raw)
            sp.sympify(s)
        except Exception:
            self._func_expr = ""; self._show_waiting()
            self.status_message.emit("表达式无效"); return
        self._func_expr = raw
        self._hide_waiting(); self._redraw()

    def _redraw(self) -> None:
        if not self._func_expr: self._show_waiting(); return
        x0, x1 = self._x_min, self._x_max
        y0, y1 = self._y_min, self._y_max
        res = self._res.value()
        rng = max(x1-x0, y1-y0)
        if rng > 100:
            r = QMessageBox.warning(self, "范围过大",
                f"绘图范围 {rng:.0f} 过大，可能导致卡顿。继续？",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes: return
        if res > 600:
            r = QMessageBox.warning(self, "分辨率过高",
                f"分辨率 {res} 可能导致卡顿。继续？",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes: return
        self._hide_waiting()
        self._compute_and_draw(x0, x1, y0, y1, res)

    def _show_waiting(self):
        self._fig.clear(); self._canvas.draw_idle()
        self._canvas.hide(); self._waiting_label.show()

    def _hide_waiting(self):
        self._waiting_label.hide(); self._canvas.show()

    def _compute_and_draw(self, x0, x1, y0, y1, res):
        try:
            import sympy as sp
            z_sym = sp.Symbol("z")
            s = _preprocess_complex(self._func_expr)
            expr = sp.sympify(s)

            # 检测特殊函数 — numpy 不支持复参数 zeta/gamma/erf/erfc
            _SPECIAL = {'zeta', 'gamma', 'erf', 'erfc', 'li', 'Ei', 'Si', 'Ci',
                        'hyper', 'meijerg', 'besselj', 'bessely', 'besseli', 'besselk'}
            _expr_str = str(expr)
            _has_special = any(fn in _expr_str for fn in _SPECIAL)

            if _has_special:
                f = sp.lambdify(z_sym, expr, "mpmath")
                _f_vec = np.vectorize(lambda val: complex(f(val)))
            else:
                f = sp.lambdify(z_sym, expr, ["numpy", "sympy"])
                _f_vec = None
        except Exception as e:
            self._show_waiting()
            self.status_message.emit(f"表达式错误: {e}"); return

        xs = np.linspace(x0, x1, res)
        ys = np.linspace(y0, y1, res)
        X, Y = np.meshgrid(xs, ys)
        Z = X + 1j * Y

        try:
            if _f_vec is not None:
                W = _f_vec(Z)
            else:
                W = np.asarray(f(Z), dtype=complex)
        except Exception as e:
            self._show_waiting()
            self.status_message.emit(f"计算错误: {e}"); return

        W = np.nan_to_num(W, nan=0.0, posinf=0.0, neginf=0.0)
        mag = np.abs(W); arg = np.angle(W)

        self._fig.clear()
        if self._mode == 0: self._draw_phase(X, Y, arg, mag)
        elif self._mode == 1: self._draw_3d_surface(X, Y, mag)
        elif self._mode == 2: self._draw_vector(X, Y, mag, arg)
        elif self._mode == 3: self._draw_hsv(X, Y, arg, mag)
        elif self._mode == 4: self._draw_conformal_grid(X, Y, Z)
        self._canvas.draw_idle()
        names = ['相位图', '3D模长', '向量场', 'HSV域着色']
        self.status_message.emit(
            f"已绘制: {self._func_expr} | {names[self._mode]}")

    def _draw_phase(self, X, Y, arg, mag):
        ax = self._fig.add_subplot(111)
        H = (arg + np.pi) / (2 * np.pi)
        S = np.ones_like(H)
        V = np.clip(mag / (mag.max() + 1e-10), 0.3, 1.0)
        HSV = np.stack([H, S, V], axis=-1)
        RGB = mcolors.hsv_to_rgb(HSV)
        ax.imshow(RGB, extent=[X.min(), X.max(), Y.min(), Y.max()], origin="lower")
        ax.set_xlabel("Re(z)"); ax.set_ylabel("Im(z)")
        ax.set_title(f"相位图: {self._func_expr}")

    def _draw_3d_surface(self, X, Y, mag):
        ax = self._fig.add_subplot(111, projection="3d")
        mag_clipped = np.clip(mag, 0, np.percentile(mag, 99))
        ax.plot_surface(X, Y, mag_clipped, cmap="viridis", linewidth=0,
                        antialiased=True, alpha=0.9)
        ax.set_xlabel("Re(z)"); ax.set_ylabel("Im(z)"); ax.set_zlabel("|f(z)|")
        ax.set_title(f"模长曲面: {self._func_expr}")
        ax.view_init(elev=30, azim=-60)

    def _draw_vector(self, X, Y, mag, arg):
        ax = self._fig.add_subplot(111)
        skip = max(1, len(X) // 40)
        Xs = X[::skip, ::skip]; Ys = Y[::skip, ::skip]
        mag_s = mag[::skip, ::skip]; arg_s = arg[::skip, ::skip]
        U = mag_s * np.cos(arg_s); V = mag_s * np.sin(arg_s)
        colors = (arg_s + np.pi) / (2 * np.pi)
        ax.quiver(Xs, Ys, U, V, colors, cmap="hsv", alpha=0.8,
                  scale=mag_s.max() * 2 if mag_s.max() > 0 else 1,
                  width=0.002)
        ax.set_xlabel("Re(z)"); ax.set_ylabel("Im(z)")
        ax.set_aspect("equal")
        ax.set_title(f"向量场: {self._func_expr}")

    def _draw_hsv(self, X, Y, arg, mag):
        """HSV 域着色: Hue=辐角, Saturation=1, Value=模(对数缩放)。"""
        import matplotlib.colors as mcolors
        ax = self._fig.add_subplot(111)
        H = (arg + np.pi) / (2 * np.pi)  # [0, 1]
        S = np.ones_like(H)
        V = np.log1p(mag) / (np.log1p(mag.max()) + 1e-9)
        V = np.clip(V, 0, 1)
        rgb = mcolors.hsv_to_rgb(np.stack([H, S, V], axis=-1))
        ax.imshow(rgb, extent=[X.min(), X.max(), Y.min(), Y.max()], origin="lower")
        ax.set_xlabel("Re(z)"); ax.set_ylabel("Im(z)")
        ax.set_aspect("equal")
        ax.set_title(f"HSV 域着色: {self._func_expr}")

    def _draw_conformal_grid(self, X, Y, Z):
        """共形映射网格变形可视化：显示 z→f(z) 下的网格变形。"""
        ax = self._fig.add_subplot(111)

        # 构建输入网格线（z-平面上的水平和垂直线）
        x0, x1 = X.min(), X.max()
        y0, y1 = Y.min(), Y.max()

        # 在 z-平面采样网格线
        n_lines = 21
        h_lines_x = np.linspace(x0, x1, 400)
        v_lines_y = np.linspace(y0, y1, 400)

        # 绘制变形后的网格：水平线 y=const → f(x + i*const)
        for y_val in np.linspace(y0, y1, n_lines):
            z_line = h_lines_x + 1j * y_val
            w = self._eval_func(z_line)
            if w is not None:
                ax.plot(w.real, w.imag, color="#3b82f6", alpha=0.4, linewidth=0.6)

        # 垂直线 x=const → f(const + i*y)
        for x_val in np.linspace(x0, x1, n_lines):
            z_line = x_val + 1j * v_lines_y
            w = self._eval_func(z_line)
            if w is not None:
                ax.plot(w.real, w.imag, color="#ef4444", alpha=0.4, linewidth=0.6)

        ax.set_xlabel("Re(w)"); ax.set_ylabel("Im(w)")
        ax.set_aspect("equal")
        ax.set_title(f"共形映射网格: w = {self._func_expr}")
        ax.grid(True, alpha=0.2)

    def _eval_func(self, z_arr):
        """对复数数组求值 f(z)，返回 w 数组。"""
        try:
            import sympy as sp
            z_sym = sp.Symbol("z")
            s = _preprocess_complex(self._func_expr)
            expr = sp.sympify(s)
            fn = sp.lambdify(z_sym, expr, "numpy")
            result = fn(z_arr)
            if isinstance(result, np.ndarray):
                result = np.where(np.isfinite(result), result, np.nan)
            return result
        except Exception:
            return None


def _sep() -> QFrame:
    s = QFrame(); s.setFixedHeight(1)
    s.setObjectName("plot_sep")
    return s
