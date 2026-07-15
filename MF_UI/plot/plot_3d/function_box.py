# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.function_box — 3D 模式函数框。

独立于 2D FunctionBox，无继承关系。
仅支持变量 x, y, z，无参数。
"""

from __future__ import annotations

import re
import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

_ALLOWED = {"x", "y", "z"}
_KNOWN = {
    "sin", "cos", "tan", "cot", "sec", "csc",
    "sinh", "cosh", "tanh", "coth",
    "asin", "acos", "atan", "acot", "asec", "acsc",
    "arcsin", "arccos", "arctan",
    "ln", "log", "log10", "sqrt", "exp", "abs",
    "e", "pi", "E", "Pi", "oo", "I", "nan",
}
_ERR_STYLE = "color: #dc2626; font-size: 11px; padding: 0 4px;"


def _preprocess(s: str) -> str:
    s = re.sub(r"\be\^\(?", "exp(", s)
    s = s.replace("^", "**")
    s = re.sub(r"\b(ln)\b", "log", s)
    s = re.sub(r"\barcsin\b", "asin", s)
    s = re.sub(r"\barccos\b", "acos", s)
    s = re.sub(r"\barctan\b", "atan", s)
    s = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", s)
    s = re.sub(r"\)\s*\(", ")*(", s)
    s = re.sub(r"\)([a-zA-Z])", r")*\1", s)
    s = re.sub(r"(\d)\s*\(", r"\1*(", s)
    s = re.sub(r"([a-zA-Z])\s+([a-zA-Z])", r"\1*\2", s)
    return s


class FunctionBox(QWidget):
    """3D 函数框 — z = f(x, y, z)，仅 x/y/z 变量，无参数。"""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, index: int = 1, color: str = "#3498db",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color
        self._valid_expr = ""

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8); shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(3); root.setContentsMargins(8, 6, 8, 6)

        row1 = QHBoxLayout(); row1.setSpacing(6)
        self._title = QLabel(f"{index}.")
        self._title.setStyleSheet("font-weight:600; font-size:13px;")
        row1.addWidget(self._title)

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setPlaceholderText("sin(x)*cos(y), x^2+y^2+z^2")
        self._input.textChanged.connect(self._on_text)
        row1.addWidget(self._input, 1)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color}; font-size:16px;")
        dot.setFixedWidth(20); dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row1.addWidget(dot)
        root.addLayout(row1)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet(_ERR_STYLE)
        self._error_label.setWordWrap(True); self._error_label.hide()
        root.addWidget(self._error_label)

        row2 = QHBoxLayout(); row2.setSpacing(4)
        self._hint = QLabel("z = f(x, y, z)")
        self._hint.setStyleSheet("font-size: 11px; color: #94a3b8;")
        row2.addWidget(self._hint)
        row2.addStretch()

        self._vis = QCheckBox("显示")
        self._vis.setChecked(True)
        self._vis.setObjectName("func_vis_cb")
        self._vis.toggled.connect(lambda _: self.changed.emit())
        row2.addWidget(self._vis)

        self._del_btn = QPushButton("×")
        self._del_btn.setFixedSize(24, 24)
        self._del_btn.setObjectName("func_del_btn")
        self._del_btn.setToolTip("删除此函数")
        self._del_btn.clicked.connect(lambda: self.removed.emit(self))
        row2.addWidget(self._del_btn)
        root.addLayout(row2)

    @property
    def expr(self) -> str:
        return self._valid_expr

    @property
    def is_visible(self) -> bool:
        return self._vis.isChecked()

    @property
    def color(self) -> str:
        return self._color

    @property
    def label(self) -> str:
        raw = self._input.text().strip()
        return f"{self._index}. {raw}" if raw else f"{self._index}."

    def _on_text(self, _txt: str) -> None:
        raw = self._input.text().strip()
        if not raw:
            self._error_label.hide(); self._valid_expr = ""
            self.changed.emit(); return

        processed = _preprocess(raw)
        try:
            expr = sp.sympify(processed)
        except Exception as e:
            self._show_error(f"解析错误: {e}"); return

        syms = {str(s) for s in expr.free_symbols}
        invalid = syms - _ALLOWED - _KNOWN
        if invalid:
            self._show_error(f"仅支持 x、y、z，无效符号: {', '.join(sorted(invalid))}")
            return
        if not (syms & _ALLOWED):
            self._show_error("至少需要 x、y 或 z 中的一个变量")
            return

        self._error_label.hide()
        self._valid_expr = processed
        self.changed.emit()

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg); self._error_label.show()
        self._valid_expr = ""
