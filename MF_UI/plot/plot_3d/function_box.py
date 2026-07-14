# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.function_box — 3D 模式专用函数框。

与 2D FunctionBox 完全独立，无继承关系。
仅支持 x, y, z 三个自变量，不支持参数。

用法:
    box = FunctionBox(index=1, color="#e74c3c", parent=self)
    box.changed.connect(...)   # 表达式变化 → 触发曲面重绘
    box.removed.connect(...)   # 删除按钮 → 移除曲面
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

# ── 3D 模式允许的自变量 ──────────────────────────────────────
_ALLOWED_VARS = {"x", "y", "z"}

# ── 已知函数名 ──────────────────────────────────────────────
_KNOWN_IDS = {
    "sin", "cos", "tan", "cot", "sec", "csc",
    "sinh", "cosh", "tanh", "coth",
    "arcsin", "arccos", "arctan", "asin", "acos", "atan",
    "ln", "log", "log10", "sqrt", "exp", "abs",
    "e", "pi", "E", "Pi",
}

_FUNCS_PATTERN = (
    "sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|coth|"
    "arcsin|arccos|arctan|asin|acos|atan|"
    "ln|log|log10|sqrt|exp|abs"
)

# ── 内联样式（与 2D 模式完全一致）─────────────────────────
_ERR_STYLE = "color: #dc2626; font-size: 11px; padding: 0 4px;"


class FunctionBox(QWidget):
    """3D 模式函数框 — z = f(x, y, z)。

    信号:
      changed()  — 表达式 / 可见性变化
      removed(box) — 删除按钮点击
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

    # ── UI（与 2D FunctionBox 完全一致）─────────────────────

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
        self._input.setPlaceholderText("sin(x)*cos(y), x^2+y^2+z^2")
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
        """返回验证通过的表达式字符串。"""
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

    # ── 输入验证 ─────────────────────────────────────────────

    def _on_text(self, _txt: str) -> None:
        raw = self._input.text().strip()

        if not raw:
            self._error_label.hide()
            self._valid_expr = ""
            self.changed.emit()
            return

        # ── 预处理 ──
        processed = _preprocess_3d(raw)

        # ── sympy 解析 ──
        try:
            expr = sp.sympify(processed)
        except Exception as e:
            self._show_error(f"解析错误: {e}")
            return

        # ── 变量检查：只允许 x, y, z ──
        syms = expr.free_symbols
        invalid = {str(s) for s in syms} - _ALLOWED_VARS - _KNOWN_IDS
        if invalid:
            self._show_error(
                f"3D 模式不支持参数，请仅使用 x、y、z 作为变量。\n"
                f"检测到无效符号: {', '.join(sorted(invalid))}")
            return

        # ── 通过 ──
        self._error_label.hide()
        self._valid_expr = processed
        self._hint.setText("z = f(x, y, z)")
        self.changed.emit()

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.show()
        self._valid_expr = ""


# ═══════════════════════════════════════════════════════════════════════
#  预处理
# ═══════════════════════════════════════════════════════════════════════

def _preprocess_3d(s: str) -> str:
    """自然书写 → sympy 兼容格式。"""
    s = re.sub(r"\be\^\(?", "exp(", s)
    s = s.replace("^", "**")
    s = re.sub(rf"\b({_FUNCS_PATTERN})(\d+)([a-zA-Z])", r"\1(\2*\3)", s)
    s = re.sub(rf"\b({_FUNCS_PATTERN})([a-zA-Z])", r"\1(\2)", s)
    s = re.sub(r"\bln\b", "log", s)
    s = re.sub(r"\barcsin\b", "asin", s)
    s = re.sub(r"\barccos\b", "acos", s)
    s = re.sub(r"\barctan\b", "atan", s)
    s = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", s)
    s = re.sub(r"\)\s*\(", ")*(", s)
    s = re.sub(r"\)([a-zA-Z])", r")*\1", s)
    s = re.sub(r"(\d)\s*\(", r"\1*(", s)
    s = re.sub(r"([a-zA-Z])\s+([a-zA-Z])", r"\1*\2", s)
    return s
