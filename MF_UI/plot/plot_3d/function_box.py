# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.function_box — 3D 模式专用函数框。

完全独立于 2D FunctionBox，无继承关系，无参数滑块。
仅允许变量 x, y, z，表达式 z = f(x, y)。
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

# ── 允许的变量 ──────────────────────────────────────────────
_ALLOWED = {"x", "y", "z"}

# ── 已知数学函数（sympy 内置，不作为变量检测）─────────────
_KNOWN = {
    "sin", "cos", "tan", "cot", "sec", "csc",
    "sinh", "cosh", "tanh", "coth",
    "asin", "acos", "atan", "acot", "asec", "acsc",
    "arcsin", "arccos", "arctan",
    "ln", "log", "log10", "sqrt", "exp", "abs", "sign",
    "ceiling", "floor", "round",
    "e", "pi", "E", "Pi", "oo", "I", "nan",
}

# ── 样式（与 2D FunctionBox 完全一致）─────────────────────
_ERR_STYLE = "color: #dc2626; font-size: 11px; padding: 0 4px;"


def _preprocess(s: str) -> str:
    """自然书写 → sympy 兼容格式。"""
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
    """3D 模式函数框 — z = f(x, y, z)，无参数。

    信号:
      changed()   — 表达式 / 可见性变化 → Plot3D 重绘曲面
      removed(box) — 删除按钮 → 移除曲面
    """

    changed = Signal()
    removed = Signal(object)

    def __init__(self, index: int = 1, color: str = "#3498db",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color
        self._valid_expr = ""

        self._build_ui()

    # ── UI 构建 ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(3)
        root.setContentsMargins(8, 6, 8, 6)

        # ── 第 1 行：标题 + 输入 + 色点 ──
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self._title = QLabel(f"{self._index}.")
        self._title.setStyleSheet("font-weight:600; font-size:13px;")
        row1.addWidget(self._title)

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setPlaceholderText("sin(x)*cos(y), x^2+y^2, sin(x)")
        self._input.textChanged.connect(self._on_text)
        row1.addWidget(self._input, 1)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{self._color}; font-size:16px;")
        dot.setFixedWidth(20)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row1.addWidget(dot)
        root.addLayout(row1)

        # ── 错误提示 ──
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(_ERR_STYLE)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root.addWidget(self._error_label)

        # ── 第 2 行：提示 + 显示开关 + 删除 ──
        row2 = QHBoxLayout()
        row2.setSpacing(4)

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

    # ── 属性 ─────────────────────────────────────────────────

    @property
    def expr(self) -> str:
        """验证通过的表达式（sympy 兼容格式）。"""
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

    # ── 验证 ─────────────────────────────────────────────────

    def _on_text(self, _txt: str) -> None:
        raw = self._input.text().strip()

        if not raw:
            self._error_label.hide()
            self._valid_expr = ""
            self._hint.setText("z = f(x, y, z)")
            self.changed.emit()
            return

        # 预处理
        processed = _preprocess(raw)

        # sympy 解析
        try:
            expr = sp.sympify(processed)
        except Exception as e:
            self._show_error(f"解析错误: {e}")
            return

        # 变量检查
        syms = {str(s) for s in expr.free_symbols}
        invalid = syms - _ALLOWED - _KNOWN
        if invalid:
            self._show_error(
                "3D 模式仅支持变量 x、y、z，请检查表达式。\n"
                f"无效符号: {', '.join(sorted(invalid))}")
            return

        # 至少包含一个自变量
        if not (syms & _ALLOWED):
            self._show_error("表达式必须至少包含 x、y 或 z 中的一个变量。")
            return

        # 通过
        self._error_label.hide()
        self._valid_expr = processed
        self._hint.setText("z = f(x, y, z)")
        self.changed.emit()

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.show()
        self._valid_expr = ""
