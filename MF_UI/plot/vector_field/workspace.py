# -*- coding: utf-8 -*-
"""向量场模式工作区 — 2D/3D 向量场可视化。"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

import matplotlib
matplotlib.use("Qt5Agg")
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

        self._build_ui()
        self._show_waiting()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self); root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        t = QLabel("向量场模式 — F(x, y) = (P, Q)")
        t.setStyleSheet("font-size:16px;font-weight:600;color:#0f172a;")
        root.addWidget(t)

        # 分量输入
        for lbl, attr, ph in [("P(x,y) =", "_px","-y"), ("Q(x,y) =", "_py","x")]:
            r = QHBoxLayout(); r.setSpacing(6)
            r.addWidget(QLabel(lbl))
            inp = QLineEdit(); inp.setPlaceholderText(ph)
            inp.setStyleSheet("QLineEdit{border:1px solid #d1d5db;border-radius:4px;"
                "padding:6px 10px;font-size:14px;background:#fff;}"
                "QLineEdit:focus{border-color:#3b82f6;}")
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

        btn = QPushButton("重绘")
        btn.setStyleSheet("QPushButton{background:#10b981;color:#fff;border:none;"
            "border-radius:4px;padding:6px 20px;font-weight:500;}"
            "QPushButton:hover{background:#059669;}")
        btn.clicked.connect(self._redraw); pr.addWidget(btn)
        pr.addStretch(); root.addLayout(pr)

        self._fig = Figure(facecolor="#f8fafc")
        self._canvas = FigureCanvasQTAgg(self._fig); self._canvas.setMinimumHeight(400)
        root.addWidget(self._canvas, 1)

        self._waiting = QLabel("等待输入分量 P、Q")
        self._waiting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._waiting.setStyleSheet("font-size:18px;color:#94a3b8;")
        root.addWidget(self._waiting); self._canvas.hide()

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

        xs = np.linspace(self._x0, self._x1, self._res)
        ys = np.linspace(self._y0, self._y1, self._res)
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
        ax.quiver(X, Y, U/M, V/M, M, cmap="viridis", scale=30, width=0.003)
        ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_aspect("equal")
        ax.set_title(f"F = ({self._px or 0}, {self._py or 0})")
        self._canvas.draw_idle()
        self.status_message.emit(f"已绘制: ({self._px},{self._py}) {self._res}×{self._res}")
