# -*- coding: utf-8 -*-
"""FractalWorkspace — Julia 集 / Mandelbrot 集分形浏览器。"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QComboBox, QStatusBar,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class FractalWorkspace(QWidget):
    """Julia/Mandelbrot 集分形浏览工作区。"""

    def __init__(self, title: str = "分形探索", parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title
        self._cx, self._cy = -0.7, 0.27  # Julia 集参数
        self._mode = "julia"
        self._max_iter = 256
        self._resolution = 400
        self._x_range = (-2.0, 2.0)
        self._y_range = (-1.5, 1.5)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ── 控制面板 ──
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(8, 4, 8, 4)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Julia 集", "Mandelbrot 集"])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        ctrl.addWidget(QLabel("类型:"))
        ctrl.addWidget(self._mode_combo)

        ctrl.addWidget(QLabel("  cx:"))
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

        ctrl.addStretch()
        export_btn = QPushButton("导出 PNG")
        export_btn.clicked.connect(self._export_png)
        ctrl.addWidget(export_btn)
        root.addLayout(ctrl)

        # ── Matplotlib 画布 ──
        self._fig = Figure(figsize=(6, 5), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.mpl_connect("button_press_event", self._on_click)
        self._canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        root.addWidget(self._canvas, 1)

        # ── 状态栏 ──
        self._status = QStatusBar()
        self._status.setFixedHeight(24)
        self._status.showMessage("点击画布缩放 / 滚轮调整范围")
        root.addWidget(self._status)

        self._redraw()

    def _on_mode_changed(self, idx: int) -> None:
        self._mode = "julia" if idx == 0 else "mandelbrot"
        self._cx_spin.setEnabled(self._mode == "julia")
        self._cy_spin.setEnabled(self._mode == "julia")
        self._redraw()

    def _compute(self):
        x0, x1 = self._x_range; y0, y1 = self._y_range
        w, h = self._resolution, int(self._resolution * (y1 - y0) / (x1 - x0))
        X = np.linspace(x0, x1, w)
        Y = np.linspace(y0, y1, h)
        C = X[:, None] + 1j * Y[None, :]
        max_iter = self._max_iter

        if self._mode == "julia":
            c = complex(self._cx, self._cy)
            Z = C
        else:
            Z = np.zeros_like(C)
            c = C

        M = np.full(C.shape, max_iter, dtype=int)
        for i in range(max_iter):
            mask = np.abs(Z) <= 2
            if not mask.any():
                break
            Z[mask] = Z[mask] ** 2 + c
            M[mask & (np.abs(Z) > 2)] = i

        return M.T, (x0, x1, y0, y1)

    def _redraw(self, *args) -> None:
        M, extent = self._compute()
        self._ax.clear()
        self._ax.imshow(M, extent=extent, origin="lower", cmap="inferno",
                        interpolation="bilinear", aspect="equal")
        self._ax.set_title(
            f"{'Julia 集' if self._mode == 'julia' else 'Mandelbrot 集'} "
            f"({self._resolution}px, {self._max_iter} iter)"
        )
        self._canvas.draw()
        self._status.showMessage(
            f"x∈[{extent[0]:.2f},{extent[1]:.2f}]  "
            f"y∈[{extent[2]:.2f},{extent[3]:.2f}]  |  "
            f"点击缩放 | 双击重置"
        )

    def _on_click(self, event) -> None:
        if event.xdata is None or event.ydata is None:
            return
        if event.dblclick:
            self._x_range = (-2.0, 2.0)
            self._y_range = (-1.5, 1.5)
        else:
            w = (self._x_range[1] - self._x_range[0]) / 3
            h = (self._y_range[1] - self._y_range[0]) / 3
            self._x_range = (event.xdata - w, event.xdata + w)
            self._y_range = (event.ydata - h, event.ydata + h)
        self._redraw()

    def _export_png(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "导出 PNG", "fractal.png", "PNG (*.png)")
        if path:
            self._fig.savefig(path, dpi=200, bbox_inches="tight")
            self._status.showMessage(f"已导出: {path}")
