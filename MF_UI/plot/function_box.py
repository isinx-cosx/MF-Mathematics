# -*- coding: utf-8 -*-
"""FunctionBox — 函数输入卡片（编号 + 自定义命名 + 隐式/显式模式）。

信号:
  - changed()               表达式 / 可见性变化
  - removed(box)            删除按钮点击

输入格式:
  - 显式表达式:    sin(x), x^2, a*x+b
  - 命名表达式:    f(x)=sin(x), g(t)=cos(t), h(z)=z^2
  - 自然书写:      sinx, e^x, 2x+1, (x+1)(x-1)
  - 隐式方程:      x^2 + y^2 = 25, sin(x) + cos(y) = 0
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

# ── 模式 → 默认自变量 ──────────────────────────────────────
_MODE_VARS: dict[str, set[str]] = {
    "normal":  {"x", "y"},
    "2d":      {"x", "y"},
    "3d":      {"x", "y", "z"},
    "complex": {"z"},
    "vector":  {"x", "y"},
}
_CONSTANTS = {sp.E, sp.pi, sp.Symbol("e")}

# ── 已知函数名 ──────────────────────────────────────────────
_FUNCS = (
    "sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|coth|"
    "arcsin|arccos|arctan|asin|acos|atan|"
    "ln|log|log10|sqrt|exp|abs|ceiling|floor|"
    "limit|diff|integrate|Sum|sum|solve"
)

# ── 样式 ──────────────────────────────────────────────────
_CARD_STYLE = """
    FunctionBox { background: #f9fafb; border: 1px solid #e2e8f0;
                  border-radius: 8px; padding: 8px; margin: 2px 0; }
"""
_INPUT_STYLE = """
    QLineEdit { border: 1px solid #d1d5db; border-radius: 4px;
                padding: 3px 8px; font-size: 13px; background: #fff; color: #1e293b; }
    QLineEdit:focus { border-color: #3b82f6; }
"""
_DEL_BTN_STYLE = """
    QPushButton { background: transparent; border: none; color: #94a3b8;
                  font-size: 18px; font-weight: bold; padding: 0 4px; }
    QPushButton:hover { color: #ef4444; background: #fee2e2; border-radius: 4px; }
"""
_VIS_STYLE = "QCheckBox { font-size: 12px; color: #64748b; spacing: 4px; }"
_ERR_STYLE = "color: #dc2626; font-size: 11px; padding: 0 4px;"
_MODE_COMBO_STYLE = """
    QComboBox { border: 1px solid #d1d5db; border-radius: 3px;
                padding: 1px 4px; font-size: 11px; background: #fff; color: #475569; }
    QComboBox:hover { border-color: #94a3b8; }
    QComboBox::drop-down { width: 16px; border: none; }
"""


@dataclass
class _Parsed:
    name: str; var: str; raw_expr: str; is_explicit: bool


def parse_input(text: str, default_var: str) -> _Parsed:
    """解析 name(var)=expr 或纯 expr。"""
    text = text.strip()
    m = re.match(r"^([a-zA-Z]\w*)\s*\(\s*([a-zA-Z])\s*\)\s*=\s*(.+)$", text)
    if m:
        return _Parsed(name=m.group(1), var=m.group(2),
                       raw_expr=m.group(3).strip(), is_explicit=True)
    return _Parsed(name="", var=default_var,
                   raw_expr=text, is_explicit=False)


class FunctionBox(QWidget):
    """单个函数卡片 — 编号 + 表达式 + 显式/隐式模式。"""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, index: int = 1, color: str = "#3498db",
                 mode: str = "normal", parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color
        self._mode = mode
        self._default_vars = _MODE_VARS.get(mode, {"x", "y"})
        self._default_var = "z" if mode == "complex" else "x"

        self._func_name = ""       # 用户自定义函数名（空=未指定）
        self._independent_var = self._default_var
        self._is_implicit = False  # 隐式方程模式
        self._updating = False

        # ── 卡片外观 ──
        self.setStyleSheet(_CARD_STYLE)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8); shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(3); root.setContentsMargins(8, 6, 8, 6)

        # ── 第 1 行：编号.函数名(var) = 输入 + 模式选择 + 色点 ──
        row1 = QHBoxLayout(); row1.setSpacing(6)
        self._title = QLabel(f"{index}.")
        self._title.setStyleSheet("font-weight:600; font-size:13px; color:#1e293b;")
        row1.addWidget(self._title)

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setPlaceholderText("sinx, e^x, g(t)=sin(t), a*x+b")
        self._input.setStyleSheet(_INPUT_STYLE)
        self._input.textChanged.connect(self._on_text)
        row1.addWidget(self._input, 1)

        # 显式/隐式模式选择
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["显式", "隐式"])
        self._mode_combo.setFixedWidth(52)
        self._mode_combo.setStyleSheet(_MODE_COMBO_STYLE)
        self._mode_combo.setToolTip("显式: y=f(x) / 隐式: f(x,y)=0")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        row1.addWidget(self._mode_combo)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color}; font-size:16px;")
        dot.setFixedWidth(20); dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row1.addWidget(dot)
        root.addLayout(row1)

        # ── 错误提示 ──
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(_ERR_STYLE)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root.addWidget(self._error_label)

        # ── 第 2 行：控制行（可见性 + 删除）──
        row2 = QHBoxLayout(); row2.setSpacing(4)

        # 参数提示（纯文本）
        self._param_hint = QLabel("")
        self._param_hint.setStyleSheet("font-size: 11px; color: #94a3b8;")
        row2.addWidget(self._param_hint)

        row2.addStretch()

        self._vis = QCheckBox("显示")
        self._vis.setChecked(True); self._vis.setStyleSheet(_VIS_STYLE)
        self._vis.toggled.connect(lambda _: self.changed.emit())
        row2.addWidget(self._vis)

        self._del_btn = QPushButton("×")
        self._del_btn.setFixedSize(24, 24); self._del_btn.setStyleSheet(_DEL_BTN_STYLE)
        self._del_btn.setToolTip("删除此函数")
        self._del_btn.clicked.connect(lambda: self.removed.emit(self))
        row2.addWidget(self._del_btn)
        root.addLayout(row2)

    # ── 属性 ───────────────────────────────────────────────

    @property
    def expr(self) -> str:
        raw = self._input.text().strip()
        if not raw:
            return ""
        if self._is_implicit:
            s = _normalize_implicit(raw)
            return _preprocess(s) if s else ""
        parsed = parse_input(raw, self._independent_var)
        s = parsed.raw_expr
        if self._mode == "complex":
            s = re.sub(r'\bx\b', 'z', s)
            s = re.sub(r'\by\b', 'z', s)
        return _preprocess(s) if s else ""

    @property
    def independent_var(self) -> str:
        return self._independent_var

    @property
    def is_visible(self) -> bool:
        return self._vis.isChecked()

    @property
    def color(self) -> str:
        return self._color

    @property
    def is_implicit(self) -> bool:
        return self._is_implicit

    @property
    def label(self) -> str:
        if self._func_name:
            return f"{self._index}. {self._func_name}({self._independent_var})"
        return f"{self._index}."

    @property
    def detected_params(self) -> set[str]:
        """检测到的表达式中的未知参数（不含自变量和常数）。"""
        e = self.expr
        if not e:
            return set()
        try:
            syms = sp.sympify(e).free_symbols
        except Exception:
            return set()
        excluded = {sp.Symbol(v) for v in self._default_vars}
        excluded.add(sp.Symbol(self._independent_var))
        # 隐式模式的 y 也是自变量
        if self._is_implicit:
            excluded.add(sp.Symbol("y"))
        return {str(s) for s in syms - excluded - _CONSTANTS}

    # ── 模式切换 ───────────────────────────────────────────

    def _on_mode_changed(self, idx: int) -> None:
        self._is_implicit = (idx == 1)
        if self._is_implicit:
            self._input.setPlaceholderText("x^2 + y^2 = 25, sin(x) + cos(y) = 0")
            self._param_hint.setText("隐式方程")
        else:
            self._input.setPlaceholderText("sinx, e^x, g(t)=sin(t), a*x+b")
            self._param_hint.setText("")
        self._validate()
        self.changed.emit()

    # ── 输入处理 ───────────────────────────────────────────

    def _on_text(self, _txt: str) -> None:
        if self._updating:
            return
        raw = self._input.text().strip()
        if not raw:
            self._error_label.hide()
            self._update_param_hint_text()
            self.changed.emit()
            return

        if not self._is_implicit:
            parsed = parse_input(raw, self._independent_var)
            self._func_name = parsed.name
            self._independent_var = parsed.var
            if parsed.is_explicit:
                self._title.setText(f"{self._index}. {parsed.name}({parsed.var}) =")
            else:
                self._title.setText(f"{self._index}.")
        else:
            self._title.setText(f"{self._index}.")

        self._validate()
        self._update_param_hint_text()
        self.changed.emit()

    def _validate(self) -> None:
        e = self.expr
        if not e:
            self._error_label.hide()
            return
        try:
            sp.sympify(e)
            self._error_label.hide()
        except Exception as exc:
            self._error_label.setText(f"解析错误: {exc}")
            self._error_label.show()

    # ── 参数提示 ───────────────────────────────────────────

    def refresh_param_hint(self, existing_global_params: set[str]) -> None:
        """外部调用：更新参数提示（排除已有全局滑块的参数）。"""
        self._update_param_hint_text(existing_global_params)

    def _update_param_hint_text(self, existing: set[str] | None = None) -> None:
        """更新参数提示文本。"""
        if self._is_implicit:
            self._param_hint.setText("隐式方程" if not self.expr else "")
            return

        detected = self.detected_params
        if existing is not None:
            detected -= existing

        if detected:
            self._param_hint.setText(f"参数: {', '.join(sorted(detected))}")
        else:
            self._param_hint.setText("")


# ═══════════════════════════════════════════════════════════════════════
#  自然书写预处理
# ═══════════════════════════════════════════════════════════════════════

def _preprocess(s: str) -> str:
    """将自然书写表达式转为 sympy 兼容格式。"""
    s = re.sub(r'\be\^\(', 'exp(', s)
    s = re.sub(r'\be\^(\w+)', r'exp(\1)', s)
    s = s.replace('^', '**')
    s = re.sub(rf'\b({_FUNCS})(\d+)([a-zA-Z])', r'\1(\2*\3)', s)
    s = re.sub(rf'\b({_FUNCS})([a-zA-Z])', r'\1(\2)', s)
    s = re.sub(rf'\b({_FUNCS})(\d+)', r'\1(\2)', s)
    s = re.sub(r'\bln\b', 'log', s)
    s = re.sub(r'\blg\b', 'log10', s)
    s = re.sub(r'\barcsin\b', 'asin', s)
    s = re.sub(r'\barccos\b', 'acos', s)
    s = re.sub(r'\barctan\b', 'atan', s)
    s = re.sub(r'\bceil\b', 'ceiling', s)
    s = re.sub(r"(\d)([a-zA-Zα-ω])", r"\1*\2", s)
    s = re.sub(r"\)\s*\(", ")*(", s)
    s = re.sub(r"\)(\d)", r")*\1", s)
    s = re.sub(r"\)([a-zA-Z])", r")*\1", s)
    s = re.sub(r"(\d)\s*\(", r"\1*(", s)
    s = re.sub(r"(?<![a-zA-Z])([a-zA-Z])\s*\(", r"\1*(", s)
    s = re.sub(r"([a-zA-Z])\s+([a-zA-Z])", r"\1*\2", s)
    return s


def _normalize_implicit(s: str) -> str:
    """将隐式方程标准化为 f(x,y) = 0 形式。

    "x^2 + y^2 = 25" → "x^2 + y^2 - 25"
    "sin(x) + cos(y) = 0" → "sin(x) + cos(y)"
    """
    s = s.strip()
    if "=" in s:
        left, right = s.split("=", 1)
        left = left.strip(); right = right.strip()
        if right == "0":
            return left
        return f"({left}) - ({right})"
    return s
