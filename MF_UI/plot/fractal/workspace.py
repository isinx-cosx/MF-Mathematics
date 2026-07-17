# -*- coding: utf-8 -*-
"""FractalWorkspace — Julia/Mandelbrot/Newton/Burning Ship 分形浏览器。"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QComboBox, QStatusBar, QFileDialog,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


_FRACTAL_TYPES = {
    "Julia 集": "julia",
    "Mandelbrot 集": "mandelbrot",
    "Burning Ship": "burning_ship",
    "Tricorn": "tricorn",
    "Newton 分形": "newton",
}
_CMAPS = ["inferno", "viridis", "plasma", "magma", "twilight", "hsv"]


def _compute_fractal(mode: str, cx: float, cy: float,
                     x_range: tuple, y_range: tuple,
                     resolution: int, max_iter: int):
    x0, x1 = x_range; y0, y1 = y_range
    w = resolution
    h = max(1, int(resolution * (y1 - y0) / (x1 - x0)))
    X = np.linspace(x0, x1, w)
    Y = np.linspace(y0, y1, h)
    C_grid = X[:, None] + 1j * Y[None, :]

    if mode == "newton":
        # f(z) = z^3 - 1, roots at 1, exp(2πi/3), exp(-2πi/3)
        roots = np.array([1, np.exp(2j * np.pi / 3), np.exp(-2j * np.pi / 3)])
        Z = C_grid.copy()
        M = np.full(C_grid.shape, max_iter, dtype=int)
        for i in range(max_iter):
            mask = np.abs(Z) < 1e10
            if not mask.any():
                break
            Z_m = Z[mask]
            f = Z_m ** 3 - 1
            fp = 3 * Z_m ** 2 + 1e-12
            Z[mask] = Z_m - f / fp
            # 收敛判定
            for k, r in enumerate(roots):
                converged = (mask & (np.abs(Z - r) < 1e-6))
                M[converged & (M == max_iter)] = i * 3 + k
        return M.T, (x0, x1, y0, y1)

    # Julia / Mandelbrot / Burning Ship / Tricorn
    if mode == "julia":
        c = complex(cx, cy)
        Z = C_grid
    else:
        Z = np.zeros_like(C_grid) if mode == "mandelbrot" else C_grid.copy()
        c = complex(cx, cy) if mode != "mandelbrot" else C_grid

    M = np.full(C_grid.shape, max_iter, dtype=int)
    for i in range(max_iter):
        mask = np.abs(Z) <= 2
        if not mask.any():
            break

        if mode == "burning_ship":
            Z_m = np.abs(Z[mask].real) + 1j * np.abs(Z[mask].imag)
        elif mode == "tricorn":
            Z_m = np.conj(Z[mask])
        else:
            Z_m = Z[mask]

        c_m = c[mask] if isinstance(c, np.ndarray) else c
        Z[mask] = Z_m ** 2 + c_m
        M[mask & (np.abs(Z) > 2)] = i

    return M.T, (x0, x1, y0, y1)


class FractalWorkspace(QWidget):
    """Julia/Mandelbrot/Newton/Burning Ship/Tricorn 分形浏览器。"""

    def __init__(self, title: str = "分形探索", parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title
        self._cx, self._cy = -0.7, 0.27
        self._mode = "julia"
        self._max_iter = 256
        self._resolution = 400
        self._x_range = (-2.0, 2.0)
        self._y_range = (-1.5, 1.5)
        self._cmap = "inferno"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ── 控制面板 ──
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(8, 4, 8, 4)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(list(_FRACTAL_TYPES.keys()))
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        ctrl.addWidget(QLabel("类型:"))
        ctrl.addWidget(self._mode_combo)

        ctrl.addWidget(QLabel(" cx:"))
        self._cx_spin = QDoubleSpinBox()
        self._cx_spin.setRange(-2, 2); self._cx_spin.setValue(-0.7)
        self._cx_spin.setSingleStep(0.01); self._cx_spin.setDecimals(4)
        self._cx_spin.valueChanged.connect(self._redraw)
        ctrl.addWidget(self._cx_spin)

        ctrl.addWidget(QLabel(" cy:"))
        self._cy_spin = QDoubleSpinBox()
        self._cy_spin.setRange(-2, 2); self._cy_spin.setValue(0.27)
        self._cy_spin.setSingleStep(0.01); self._cy_spin.setDecimals(4)
        self._cy_spin.valueChanged.connect(self._redraw)
        ctrl.addWidget(self._cy_spin)

        ctrl.addWidget(QLabel(" 迭代:"))
        self._iter_combo = QComboBox()
        self._iter_combo.addItems(["64", "128", "256", "512", "1024"])
        self._iter_combo.setCurrentText("256")
        self._iter_combo.currentTextChanged.connect(
            lambda v: setattr(self, '_max_iter', int(v)) or self._redraw())
        ctrl.addWidget(self._iter_combo)

        ctrl.addWidget(QLabel(" 配色:"))
        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(_CMAPS)
        self._cmap_combo.currentTextChanged.connect(
            lambda v: setattr(self, '_cmap', v) or self._redraw())
        ctrl.addWidget(self._cmap_combo)

        ctrl.addStretch()
        export_btn = QPushButton("导出 PNG")
        export_btn.clicked.connect(self._export_png)
        ctrl.addWidget(export_btn)
        root.addLayout(ctrl)

        # ── Matplotlib 画布 ──
        from MF_UI.plot.mpl_setup import get_mpl_figure_facecolor, get_mpl_axes_facecolor
        self._fig = Figure(figsize=(6, 5), dpi=100, facecolor=get_mpl_figure_facecolor())
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor(get_mpl_axes_facecolor())
        self._canvas = FigureCanvas(self._fig)
        self._canvas.mpl_connect("button_press_event", self._on_click)
        self._canvas.mpl_connect("scroll_event", self._on_scroll)
        self._canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        root.addWidget(self._canvas, 1)

        # ── 状态栏 ──
        self._status = QStatusBar()
        self._status.setFixedHeight(24)
        self._status.showMessage("点击缩放 | 滚轮缩放 | 双击重置 | 拖动平移")
        root.addWidget(self._status)

        self._redraw()

    def _on_mode_changed(self, idx: int) -> None:
        self._mode = list(_FRACTAL_TYPES.values())[idx]
        is_julia = self._mode in ("julia", "burning_ship", "tricorn")
        self._cx_spin.setEnabled(is_julia)
        self._cy_spin.setEnabled(is_julia)
        if self._mode == "newton":
            self._x_range = (-2.0, 2.0)
            self._y_range = (-2.0, 2.0)
        else:
            self._x_range = (-2.0, 2.0)
            self._y_range = (-1.5, 1.5)
        self._redraw()

    def _redraw(self, *args) -> None:
        M, extent = _compute_fractal(
            self._mode, self._cx, self._cy,
            self._x_range, self._y_range,
            self._resolution, self._max_iter,
        )
        self._ax.clear()
        self._ax.imshow(M, extent=extent, origin="lower", cmap=self._cmap,
                        interpolation="bilinear", aspect="equal")
        names = {v: k for k, v in _FRACTAL_TYPES.items()}
        self._ax.set_title(
            f"{names.get(self._mode, self._mode)} "
            f"({self._resolution}px, {self._max_iter} iter)"
        )
        self._canvas.draw()
        self._status.showMessage(
            f"x∈[{extent[0]:.4f},{extent[1]:.4f}]  "
            f"y∈[{extent[2]:.4f},{extent[3]:.4f}]  |  "
            f"点击/滚轮缩放 | 双击重置"
        )

    def _on_click(self, event) -> None:
        if event.xdata is None or event.ydata is None:
            return
        if event.dblclick:
            if self._mode == "newton":
                self._x_range = (-2.0, 2.0)
                self._y_range = (-2.0, 2.0)
            else:
                self._x_range = (-2.0, 2.0)
                self._y_range = (-1.5, 1.5)
        elif event.button == 1:  # 左键缩放
            w = (self._x_range[1] - self._x_range[0]) / 3
            h = (self._y_range[1] - self._y_range[0]) / 3
            self._x_range = (event.xdata - w, event.xdata + w)
            self._y_range = (event.ydata - h, event.ydata + h)
        elif event.button == 3:  # 右键缩小
            w = (self._x_range[1] - self._x_range[0]) * 0.5
            h = (self._y_range[1] - self._y_range[0]) * 0.5
            self._x_range = (event.xdata - w, event.xdata + w)
            self._y_range = (event.ydata - h, event.ydata + h)
        self._redraw()

    def _on_scroll(self, event) -> None:
        if event.xdata is None or event.ydata is None:
            return
        factor = 0.7 if event.button == "up" else 1.4
        w = (self._x_range[1] - self._x_range[0]) * factor / 2
        h = (self._y_range[1] - self._y_range[0]) * factor / 2
        self._x_range = (event.xdata - w, event.xdata + w)
        self._y_range = (event.ydata - h, event.ydata + h)
        self._redraw()

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出 PNG", "fractal.png", "PNG (*.png)")
        if path:
            self._fig.savefig(path, dpi=200, bbox_inches="tight")
            self._status.showMessage(f"已导出: {path}")
