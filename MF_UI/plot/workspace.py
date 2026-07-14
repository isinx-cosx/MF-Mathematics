# -*- coding: utf-8 -*-
"""PlotWorkspace — 绘图工作区（画布 + 函数框 + 虚框）。"""

from __future__ import annotations
import json, os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)
from MF_UI.plot.plot_canvas import PlotCanvas
from MF_UI.plot.function_box import FunctionBox


def _load_colors() -> list[str]:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = os.path.join(root, "config.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f).get("plot", {}).get("colors",
                ["#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6","#1abc9c","#e67e22","#e84393"])
    return ["#e74c3c","#3498db","#2ecc71"]

_COLORS = _load_colors()


class PlotWorkspace(QWidget):
    """绘图模式工作区。"""

    def __init__(self, title: str = "2D Plot", parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title; self._ci = 0; self._boxes: list[FunctionBox] = []

        root = QHBoxLayout(self); root.setSpacing(0); root.setContentsMargins(0,0,0,0)

        left = QWidget(); left.setFixedWidth(340)
        left.setStyleSheet("background:#f8fafc; border-right:1px solid #e2e8f0")
        ll = QVBoxLayout(left); ll.setSpacing(8); ll.setContentsMargins(12,12,12,12)
        ll.addWidget(QLabel(f"<b>{title}</b>"))
        self._status = QLabel("📐 x,y ∈ [-10000, 10000]")
        self._status.setStyleSheet("font-size:11px; color:#64748b"); self._status.setWordWrap(True)
        ll.addWidget(self._status)

        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QScrollArea.Shape.NoFrame)
        sc.setStyleSheet("QScrollArea{background:transparent; border:none}")
        self._bc = QWidget()
        self._bl = QVBoxLayout(self._bc); self._bl.setSpacing(6); self._bl.setContentsMargins(0,0,0,0)
        sc.setWidget(self._bc); ll.addWidget(sc, 1)

        # virtual box
        self._vb = QFrame()
        self._vb.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain); self._vb.setLineWidth(2)
        self._vb.setStyleSheet("QFrame{border:2px dashed #cbd5e1; border-radius:8px; background:transparent; min-height:60px} QFrame:hover{background:#e2e8f0; border-color:#94a3b8}")
        self._vb.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vb.mousePressEvent = lambda e: self._add()
        ll.addWidget(self._vb)
        root.addWidget(left)

        self._canvas = PlotCanvas()
        self._canvas.status_message.connect(self._status.setText)
        root.addWidget(self._canvas, 1)
        self._add()

    @property
    def canvas(self) -> PlotCanvas: return self._canvas

    def clear_all(self) -> None:
        for b in self._boxes[:]: self._rm(b)
        self._canvas.clear_functions()

    def _add(self) -> None:
        c = _COLORS[self._ci % len(_COLORS)]; self._ci += 1
        b = FunctionBox(label=str(len(self._boxes)+1), color=c, parent=self)
        b.changed.connect(lambda bb=b: self._re())
        b.removed.connect(self._rm)
        b.param_changed.connect(self._op)
        self._boxes.append(b); self._bl.addWidget(b); self._ub(); self._re()

    def _rm(self, b: FunctionBox) -> None:
        if len(self._boxes) <= 1: return
        if b in self._boxes: self._boxes.remove(b)
        self._bl.removeWidget(b); b.deleteLater(); self._ub(); self._re()

    def _op(self, name: str, value: float) -> None:
        for b in self._boxes:
            if name in b.get_param_names(): b.set_param(name, value)
        self._re()

    def _re(self) -> None:
        self._canvas.clear_functions()
        for b in self._boxes:
            if b.is_visible and b.expr:
                idx = self._canvas.add_function(b.expr, color=b.color, label=b.label)
                if b.params: self._canvas.set_params(idx, b.params)

    def _ub(self) -> None:
        for b in self._boxes: b._del_btn.setVisible(len(self._boxes) > 1)
