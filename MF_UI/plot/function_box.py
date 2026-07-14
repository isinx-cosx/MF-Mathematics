# -*- coding: utf-8 -*-
"""FunctionBox — 函数卡片（表达式输入 + 显示控制 + 删除 + 参数滑块）。"""

from __future__ import annotations

import json, os
import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget,
)

def _load_colors() -> list[str]:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = os.path.join(root, "config.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f).get("plot", {}).get("colors",
                ["#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6","#1abc9c","#e67e22","#e84393"])
    return ["#e74c3c","#3498db","#2ecc71"]

_COLORS = _load_colors()
_color_idx = [0]

def _next_color() -> str:
    c = _COLORS[_color_idx[0] % len(_COLORS)]; _color_idx[0] += 1; return c


class FunctionBox(QWidget):
    """单个函数卡片。信号: changed(), removed(box), param_changed(name, value)"""
    changed = Signal()
    removed = Signal(object)
    param_changed = Signal(str, float)

    def __init__(self, label: str = "", color: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        if not color: color = _next_color()
        if not label:
            boxes = [w for w in (parent.findChildren(FunctionBox) if parent else []) if w is not self]
            label = str(len(boxes) + 1)
        self._label = label; self._color = color
        self._sliders: dict[str, tuple[QSlider, QLineEdit]] = {}

        self.setStyleSheet(f"""
            FunctionBox{{background:#fff; border:1px solid #e2e8f0; border-left:4px solid {color};
                         border-radius:8px; padding:8px; margin:4px 0}}
        """)
        root = QVBoxLayout(self); root.setSpacing(4); root.setContentsMargins(6,6,6,6)

        # title
        tr = QHBoxLayout()
        self._title = QLabel(label); self._title.setStyleSheet("font-weight:600; color:#0f172a")
        tr.addWidget(self._title); tr.addStretch()
        cl = QLabel("●"); cl.setStyleSheet(f"color:{color}; font-size:16px"); tr.addWidget(cl)
        root.addLayout(tr)

        # input
        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setStyleSheet("QLineEdit{border:1px solid #d1d5db; border-radius:4px; padding:2px 8px; font-size:13px} QLineEdit:focus{border-color:#3b82f6}")
        self._input.textChanged.connect(self._on_expr); root.addWidget(self._input)
        self._err = QLabel(""); self._err.setStyleSheet("color:#dc2626; font-size:11px"); self._err.setVisible(False)
        root.addWidget(self._err)

        # controls
        cr = QHBoxLayout()
        self._vis = QCheckBox("show"); self._vis.setChecked(True); self._vis.toggled.connect(lambda: self.changed.emit())
        cr.addWidget(self._vis); cr.addStretch()
        self._del_btn = QPushButton("×"); self._del_btn.setFixedSize(28,28)
        self._del_btn.setStyleSheet("QPushButton{background:transparent; border:none; color:#94a3b8; font-size:18px; font-weight:bold} QPushButton:hover{color:#ef4444}")
        self._del_btn.clicked.connect(lambda: self.removed.emit(self)); cr.addWidget(self._del_btn)
        root.addLayout(cr)

        self._sa = QVBoxLayout(); self._sa.setSpacing(4); root.addLayout(self._sa)

    @property
    def expr(self) -> str: return self._input.text().strip()
    @property
    def is_visible(self) -> bool: return self._vis.isChecked()
    @property
    def color(self) -> str: return self._color
    @property
    def label(self) -> str: return self._label
    @property
    def params(self) -> dict[str, float]:
        return {k: v[0].value() / 100.0 for k, v in self._sliders.items()}

    def get_param_names(self) -> set[str]: return set(self._sliders.keys())

    def set_param(self, name: str, value: float) -> None:
        if name in self._sliders:
            s, le = self._sliders[name]; s.blockSignals(True); le.blockSignals(True)
            s.setValue(int(value*100)); le.setText(f"{value:.2f}")
            s.blockSignals(False); le.blockSignals(False)

    def _on_expr(self, txt: str) -> None:
        self._update_params(); self._validate(); self.changed.emit()

    def _validate(self) -> None:
        if not self.expr: self._err.setVisible(False); return
        try: sp.sympify(self.expr); self._err.setVisible(False)
        except Exception as e: self._err.setText(str(e)); self._err.setVisible(True)

    def _update_params(self) -> None:
        if not self.expr: return
        try:
            syms = sp.sympify(self.expr).free_symbols
            unknown = syms - {sp.Symbol(s) for s in ("x","y","z","t")}
        except: unknown = set()
        cur = set(self._sliders.keys()); tgt = {str(s) for s in unknown}
        for n in cur - tgt:
            s, le = self._sliders.pop(n); s.deleteLater(); le.deleteLater()
        for n in tgt - cur:
            row = QHBoxLayout(); row.addWidget(QLabel(f"{n} ="))
            sl = QSlider(Qt.Orientation.Horizontal); sl.setRange(-1000,1000); sl.setValue(0); row.addWidget(sl, 1)
            le = QLineEdit("0.00"); le.setFixedWidth(60); row.addWidget(le)
            sl.valueChanged.connect(lambda v, n=n, le=le: self._on_slider(n, v, le))
            le.editingFinished.connect(lambda sl=sl, le=le: self._on_input(sl, le))
            self._sa.addLayout(row); self._sliders[n] = (sl, le)

    def _on_slider(self, name, value, le):
        v = value / 100.0; le.setText(f"{v:.2f}")
        self.param_changed.emit(name, v); self.changed.emit()

    def _on_input(self, sl, le):
        try:
            v = max(-10.0, min(10.0, float(le.text()))); sl.setValue(int(v*100))
        except ValueError: pass
