# -*- coding: utf-8 -*-
"""CalculatorWidget — 计算器风格 LCD 显示屏 + 按钮网格。

纯 QWidget 实现，不依赖 BaseCalcBlock。使用 Python math 安全求值。
"""

from __future__ import annotations

import math as _math
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

# ── 安全计算命名空间 ────────────────────────────────────────
_SAFE_NS: dict = {
    "sqrt": _math.sqrt, "factorial": _math.factorial,
    "pi": _math.pi, "e": _math.e,
    "log10": _math.log10, "log": _math.log,
    "abs": abs, "pow": pow,
    "sin": _math.sin, "cos": _math.cos, "tan": _math.tan,
    "radians": _math.radians, "degrees": _math.degrees,
}

# ── 按钮布局定义 (text, row, col, colspan, style_class) ────
_BUTTONS: list[tuple[str, int, int, int, str]] = [
    # row 0 — 控制 / 括号
    ("C",  0, 0, 1, "ctrl"),
    ("(",  0, 1, 1, "paren"),
    (")",  0, 2, 1, "paren"),
    ("%",  0, 3, 1, "op"),
    ("÷",  0, 4, 1, "op"),
    # row 1 — 数字 + 运算符
    ("7",  1, 0, 1, "num"),
    ("8",  1, 1, 1, "num"),
    ("9",  1, 2, 1, "num"),
    ("×",  1, 3, 1, "op"),
    ("x²", 1, 4, 1, "func"),
    # row 2
    ("4",  2, 0, 1, "num"),
    ("5",  2, 1, 1, "num"),
    ("6",  2, 2, 1, "num"),
    ("−",  2, 3, 1, "op"),
    ("√",  2, 4, 1, "func"),
    # row 3
    ("1",  3, 0, 1, "num"),
    ("2",  3, 1, 1, "num"),
    ("3",  3, 2, 1, "num"),
    ("+",  3, 3, 1, "op"),
    ("n!", 3, 4, 1, "func"),
    # row 4
    ("0",  4, 0, 1, "num"),
    (".",  4, 1, 1, "num"),
    ("±",  4, 2, 1, "func"),
    ("=",  4, 3, 1, "eq"),
    ("1/x",4, 4, 1, "func"),
    # row 5 — 常数 / 高级
    ("π",  5, 0, 1, "const"),
    ("e",  5, 1, 1, "const"),
    ("xⁿ", 5, 2, 1, "func"),
    ("log",5, 3, 1, "func"),
    ("ln", 5, 4, 1, "func"),
]


class CalculatorWidget(QWidget):
    """计算器控件 — LCD 显示屏 + 5×6 按钮网格。

    用法:
        calc = CalculatorWidget()
        calc.result_available.connect(lambda val: print(val))
    """

    result_available = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expr: str = ""
        self._last_result: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── LCD 显示屏 ──
        self._display = QLabel("0")
        self._display.setObjectName("calc_lcd")
        self._display.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._display.setMinimumHeight(60)
        font = QFont("Consolas, Courier New, monospace", 24)
        font.setBold(True)
        self._display.setFont(font)
        self._display.setWordWrap(True)
        layout.addWidget(self._display)

        # ── 结果行 ──
        self._result_label = QLabel("")
        self._result_label.setObjectName("calc_result")
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._result_label.setFont(QFont("Consolas, Courier New, monospace", 12))
        layout.addWidget(self._result_label)

        # ── 按钮网格 ──
        grid = QGridLayout()
        grid.setSpacing(4)

        for text, row, col, colspan, cls in _BUTTONS:
            btn = QPushButton(text)
            btn.setObjectName(f"calc_btn_{cls}")
            btn.setMinimumHeight(40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda checked, t=text: self._on_button(t))
            grid.addWidget(btn, row, col, 1, colspan)

        layout.addLayout(grid)

    # ── 按钮处理 ──────────────────────────────────────────

    def _on_button(self, text: str) -> None:
        """按钮点击分发。"""
        if text == "C":
            self._expr = ""
            self._result_label.setText("")
            self._display.setText("0")
            return

        if text == "=":
            self._evaluate()
            return

        if text == "±":
            self._toggle_sign()
            return

        # 运算符映射
        op_map: dict[str, str] = {
            "×": "*", "÷": "/", "−": "-",
            "x²": "**2", "1/x": "**(-1)",
        }
        if text in op_map:
            self._expr += op_map[text]
            self._display.setText(self._expr)
            return

        # 函数类 — 需要在前面加 math.
        func_map: dict[str, str] = {
            "√": "sqrt(", "n!": "factorial(",
            "xⁿ": "**(", "π": "pi", "e": "e",
            "log": "log10(", "ln": "log(",
        }
        if text in func_map:
            self._expr += func_map[text]
            self._display.setText(self._expr)
            return

        # 数字、小数点、括号、百分号
        pct_map = {"%": "/100"}
        if text in pct_map:
            self._expr += pct_map[text]
        else:
            self._expr += text

        self._display.setText(self._expr)

    def _toggle_sign(self) -> None:
        """切换表达式末尾数字的正负号。"""
        if not self._expr:
            return
        if self._expr.startswith("-"):
            self._expr = self._expr[1:]
        else:
            self._expr = "-" + self._expr
        self._display.setText(self._expr)

    def _evaluate(self) -> None:
        """安全求值当前表达式。"""
        if not self._expr.strip():
            return
        try:
            # 补全未闭合括号
            expr = self._expr
            open_parens = expr.count("(") - expr.count(")")
            expr += ")" * open_parens

            result = eval(expr, {"__builtins__": {}}, _SAFE_NS)
            if isinstance(result, (int, float)):
                if isinstance(result, float) and result == int(result):
                    result = int(result)
                self._last_result = str(result)
            else:
                self._last_result = str(result)
            self._result_label.setText(f"= {self._last_result}")
            self.result_available.emit(self._last_result)
        except Exception:
            self._result_label.setText("错误")
            self._last_result = ""

    # ── 公开方法 ──────────────────────────────────────────

    def set_expression(self, expr: str) -> None:
        """外部设置表达式（如键盘输入）。"""
        self._expr = expr
        self._display.setText(expr or "0")

    def get_expression(self) -> str:
        """获取当前表达式。"""
        return self._expr

    def clear(self) -> None:
        """清除所有内容。"""
        self._on_button("C")
