# -*- coding: utf-8 -*-
"""CalculatorWidget — 计算器风格 LCD 显示屏 + 按钮网格。

标准计算器布局：上方表达式行 + 下方大号结果行 + 5×6 按钮网格。
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

# ── 按钮布局 (text, row, col, style_class) ─────────────────
_BUTTONS: list[tuple[str, int, int, str]] = [
    # row 0 — 清除 / 删除 / 括号
    ("C",  0, 0, "ctrl"),
    ("⌫",  0, 1, "ctrl"),
    ("(",  0, 2, "paren"),
    (")",  0, 3, "paren"),
    ("÷",  0, 4, "op"),
    # row 1 — 数字 + 运算符
    ("7",  1, 0, "num"),
    ("8",  1, 1, "num"),
    ("9",  1, 2, "num"),
    ("×",  1, 3, "op"),
    ("x²", 1, 4, "func"),
    # row 2
    ("4",  2, 0, "num"),
    ("5",  2, 1, "num"),
    ("6",  2, 2, "num"),
    ("−",  2, 3, "op"),
    ("√",  2, 4, "func"),
    # row 3
    ("1",  3, 0, "num"),
    ("2",  3, 1, "num"),
    ("3",  3, 2, "num"),
    ("+",  3, 3, "op"),
    ("n!", 3, 4, "func"),
    # row 4
    ("0",  4, 0, "num"),
    (".",  4, 1, "num"),
    ("±",  4, 2, "func"),
    ("=",  4, 3, "eq"),
    ("1/x",4, 4, "func"),
    # row 5 — 常数 / 高级
    ("π",  5, 0, "const"),
    ("e",  5, 1, "const"),
    ("xⁿ", 5, 2, "func"),
    ("log",5, 3, "func"),
    ("ln", 5, 4, "func"),
]


class CalculatorWidget(QWidget):
    """计算器控件 — 标准计算器界面。

    用法:
        calc = CalculatorWidget()
        calc.result_available.connect(lambda val: print(val))
    """

    result_available = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expr: str = ""          # 表达式（显示在上方）
        self._current: str = "0"      # 当前输入/结果（显示在下方大号）

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── LCD 显示屏（双行计算器同款） ──
        lcd = QWidget()
        lcd.setObjectName("calc_lcd")
        lcd_layout = QVBoxLayout(lcd)
        lcd_layout.setContentsMargins(12, 8, 12, 8)
        lcd_layout.setSpacing(2)

        # 上方 — 表达式行（较小字体，灰色）
        self._expr_label = QLabel("")
        self._expr_label.setObjectName("calc_expr")
        self._expr_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self._expr_label.setFont(QFont("Segoe UI, Microsoft YaHei, sans-serif", 14))
        lcd_layout.addWidget(self._expr_label)

        # 下方 — 当前数字 / 结果行（大号字体，醒目）
        self._result_label = QLabel("0")
        self._result_label.setObjectName("calc_result")
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        font = QFont("Segoe UI, Microsoft YaHei, sans-serif", 40)
        font.setBold(True)
        self._result_label.setFont(font)
        self._result_label.setMinimumHeight(55)
        lcd_layout.addWidget(self._result_label)

        layout.addWidget(lcd)

        # ── 按钮网格 ──
        grid = QGridLayout()
        grid.setSpacing(4)

        for text, row, col, cls in _BUTTONS:
            btn = QPushButton(text)
            btn.setObjectName(f"calc_btn_{cls}")
            btn.setMinimumHeight(42)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda checked, t=text: self._on_button(t))
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

    # ── 按钮处理 ──────────────────────────────────────────

    def _on_button(self, text: str) -> None:
        """按钮点击分发。"""
        if text == "C":
            self._expr = ""
            self._current = "0"
            self._expr_label.setText("")
            self._result_label.setText("0")
            return

        if text == "⌫":
            self._backspace()
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
            self._current = ""
            self._expr_label.setText(self._expr)
            self._result_label.setText(text)
            return

        # 函数类
        func_map: dict[str, str] = {
            "√": "sqrt(", "n!": "factorial(",
            "xⁿ": "**(", "π": "pi", "e": "e",
            "log": "log10(", "ln": "log(",
        }
        if text in func_map:
            self._expr += func_map[text]
            self._current = ""
            self._expr_label.setText(self._expr)
            self._result_label.setText(text)
            return

        # 数字、小数点、括号
        self._expr += text
        self._expr_label.setText(self._expr)

        # 更新当前输入显示
        if self._current in ("0", ""):
            self._current = text
        else:
            self._current += text
        self._result_label.setText(self._current)

    def _backspace(self) -> None:
        """删除最后一个字符。"""
        if not self._expr:
            return
        # 处理多字符 tokens (factorial(, sqrt(, **2, **(-1), **(
        multi_char_tokens = ["factorial(", "**(-1)", "**2", "**(",
                             "sqrt(", "log10(", "log(",
                             "pi", "e"]
        for tok in multi_char_tokens:
            if self._expr.endswith(tok):
                self._expr = self._expr[:-len(tok)]
                self._expr_label.setText(self._expr)
                self._result_label.setText(self._current[:-1] if len(self._current) > 1 else "0")
                return
        # 单字符删除
        self._expr = self._expr[:-1]
        self._expr_label.setText(self._expr)
        if len(self._current) > 1:
            self._current = self._current[:-1]
        else:
            self._current = "0"
        self._result_label.setText(self._current)

    def _toggle_sign(self) -> None:
        """切换当前值的正负号。"""
        if not self._expr:
            return
        if self._expr.startswith("-"):
            self._expr = self._expr[1:]
        else:
            self._expr = "-" + self._expr
        self._expr_label.setText(self._expr)
        self._result_label.setText(self._expr[-8:] or "0")

    def _evaluate(self) -> None:
        """安全求值，结果显示在大号行。"""
        if not self._expr.strip():
            return
        try:
            expr = self._expr
            open_parens = expr.count("(") - expr.count(")")
            expr += ")" * open_parens

            result = eval(expr, {"__builtins__": {}}, _SAFE_NS)
            if isinstance(result, (int, float)):
                if isinstance(result, float) and result == int(result):
                    result = int(result)

            # 显示：表达式上移，结果大号显示
            self._expr_label.setText(self._expr + " =")
            self._result_label.setText(_fmt_result(result))
            self._current = str(result)
            self.result_available.emit(str(result))
        except Exception:
            self._result_label.setText("错误")
            self._current = "0"

    # ── 公开方法 ──────────────────────────────────────────

    def set_expression(self, expr: str) -> None:
        """外部设置表达式。"""
        self._expr = expr
        self._expr_label.setText(expr)

    def get_expression(self) -> str:
        """获取当前表达式。"""
        return self._expr

    def clear(self) -> None:
        """清除所有内容。"""
        self._on_button("C")


def _fmt_result(val) -> str:
    """格式化结果 — 大数用科学记数法，小数截断。"""
    if isinstance(val, float):
        if abs(val) >= 1e12 or (abs(val) < 1e-10 and val != 0):
            return f"{val:.6e}"
        # 去掉多余的尾部零
        s = f"{val:.12f}".rstrip("0").rstrip(".")
        return s
    return str(val)
