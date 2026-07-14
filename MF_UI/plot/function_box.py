# -*- coding: utf-8 -*-
"""FunctionBox — 函数输入卡片（自动识别显式/隐式，编号 + 自定义命名）。

信号:
  - changed()               表达式 / 可见性变化
  - removed(box)            删除按钮点击

输入格式:
  - 显式表达式:    sin(x), x^2, a*x+b
  - 命名表达式:    f(x)=sin(x), g(t)=cos(t), h(z)=z^2
  - 自然书写:      sinx, e^x, 2x+1, (x+1)(x-1)
  - 隐式方程:      x^2 + y^2 = 25, sin(x) + cos(y) = 0

自动分类:
  - 含 name(var)=expr 形式 → 显式函数（自定义变量）
  - 含 = 且同时包含 x 和 y → 隐式方程（f(x,y)=0）
  - 不含 = → 显式函数（默认自变量 x）
  - 含 = 但变量 ≠ x,y 或多于 2 个变量 → 错误提示
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
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

# ── 已知函数名（用于变量识别时排除）───────────────────────
_FUNCS_PATTERN = (
    "sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|coth|"
    "arcsin|arccos|arctan|asin|acos|atan|"
    "ln|log|log10|sqrt|exp|abs|ceiling|floor|"
    "limit|diff|integrate|Sum|sum|solve"
)

# ── 隐式方程变量检测 → 已知标识符（非变量）─────────────────
_KNOWN_IDS = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'sinh', 'cosh', 'tanh', 'coth',
    'arcsin', 'arccos', 'arctan', 'asin', 'acos', 'atan',
    'ln', 'log', 'log10', 'sqrt', 'exp', 'abs', 'ceiling', 'floor',
    'limit', 'diff', 'integrate', 'Sum', 'sum', 'solve',
    'e', 'pi', 'E', 'Pi', 'oo', 'nan', 'I',
}

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
_TYPE_TAG_STYLE = """
    font-size: 10px; font-weight: 600; border-radius: 3px; padding: 1px 6px;
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
    """单个函数卡片 — 自动识别显式/隐式，无需手动切换。"""

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

        self._func_name = ""        # 用户自定义函数名（空=未指定）
        self._independent_var = self._default_var
        self._expr_type = "explicit"  # "explicit" | "implicit" | "error"
        self._updating = False

        # ── 卡片外观 ──
        self.setStyleSheet(_CARD_STYLE)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8); shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(3); root.setContentsMargins(8, 6, 8, 6)

        # ── 第 1 行：编号 + 类型标签 + 输入 + 色点 ──
        row1 = QHBoxLayout(); row1.setSpacing(6)
        self._title = QLabel(f"{index}.")
        self._title.setStyleSheet("font-weight:600; font-size:13px; color:#1e293b;")
        row1.addWidget(self._title)

        # 类型标签（自动显示 "显式" / "隐式"）
        self._type_tag = QLabel("")
        self._type_tag.setStyleSheet(_TYPE_TAG_STYLE)
        self._type_tag.hide()
        row1.addWidget(self._type_tag)

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setPlaceholderText("sinx, e^x, g(t)=sin(t), x^2+y^2=25")
        self._input.setStyleSheet(_INPUT_STYLE)
        self._input.textChanged.connect(self._on_text)
        row1.addWidget(self._input, 1)

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

        # ── 第 2 行：参数提示 + 可见性 + 删除 ──
        row2 = QHBoxLayout(); row2.setSpacing(4)

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
        if self._expr_type == "implicit":
            s = _normalize_implicit(raw)
            return _preprocess(s) if s else ""
        # explicit
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
    def expr_type(self) -> str:
        """表达式类型: "explicit" | "implicit" | "error"。"""
        return self._expr_type

    @property
    def label(self) -> str:
        if self._expr_type == "implicit":
            return f"{self._index}. 隐式"
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
        # 隐式方程：x 和 y 均为自变量，不作参数
        if self._expr_type == "implicit":
            excluded.add(sp.Symbol("y"))
        return {str(s) for s in syms - excluded - _CONSTANTS}

    # ── 表达式自动分类 ─────────────────────────────────────

    def _classify(self, raw: str) -> dict:
        """自动识别表达式类型。

        Returns:
            {"type": "explicit"|"implicit"|"error", "message"?: str}
        """
        raw = raw.strip()
        if not raw:
            return {"type": "explicit"}

        # 1) name(var)=expr 形式 → 显式（自定义变量）
        if re.match(r"^([a-zA-Z]\w*)\s*\(\s*([a-zA-Z])\s*\)\s*=\s*(.+)$", raw):
            return {"type": "explicit"}

        # 2) 不含 = → 显式
        if "=" not in raw:
            return {"type": "explicit"}

        # 3) 含 = → 提取变量，判断是否为隐式方程
        all_ids = set(re.findall(r'[a-zA-Z]\w*', raw))
        vars_found = all_ids - _KNOWN_IDS

        # 隐式方程仅支持 x 和 y
        has_xy = ('x' in vars_found or 'X' in vars_found) and \
                 ('y' in vars_found or 'Y' in vars_found)

        if len(vars_found) > 2:
            return {
                "type": "error",
                "message": (
                    f"隐式方程仅支持 x 和 y，检测到 {len(vars_found)} 个变量: "
                    f"{', '.join(sorted(vars_found))}。\n请简化为二元方程，如 x^2 + y^2 = 25。"
                ),
            }
        elif has_xy:
            return {"type": "implicit"}
        else:
            # 形如 y = x^2（含 = 且含 y/x 但不被识别为 name(var)=expr）
            # 将其视为显式函数（只有一个有效变量时）
            return {"type": "explicit"}

    # ── 输入处理 ───────────────────────────────────────────

    def _on_text(self, _txt: str) -> None:
        if self._updating:
            return
        raw = self._input.text().strip()
        if not raw:
            self._error_label.hide()
            self._type_tag.hide()
            self._expr_type = "explicit"
            self._update_param_hint_text()
            self.changed.emit()
            return

        # ── 自动分类 ──
        classification = self._classify(raw)
        self._expr_type = classification["type"]

        if self._expr_type == "error":
            self._error_label.setText(classification.get("message", "无法识别，请检查表达式"))
            self._error_label.show()
            self._type_tag.hide()
            self._param_hint.setText("")
            return

        # ── 更新标题与类型标签 ──
        if self._expr_type == "implicit":
            self._type_tag.setText("隐式")
            self._type_tag.setStyleSheet(
                _TYPE_TAG_STYLE + "color: #7c3aed; background: #f3e8ff;")
            self._type_tag.show()
            self._title.setText(f"{self._index}.")
            self._func_name = ""
            self._independent_var = "x"
        else:
            self._type_tag.setText("显式")
            self._type_tag.setStyleSheet(
                _TYPE_TAG_STYLE + "color: #2563eb; background: #dbeafe;")
            self._type_tag.show()
            # 解析 name(var)=expr
            parsed = parse_input(raw, self._independent_var)
            self._func_name = parsed.name
            self._independent_var = parsed.var
            if parsed.is_explicit:
                self._title.setText(f"{self._index}. {parsed.name}({parsed.var}) =")
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
        if self._expr_type == "implicit":
            self._param_hint.setText("f(x, y) = 0")
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
    s = re.sub(rf'\b({_FUNCS_PATTERN})(\d+)([a-zA-Z])', r'\1(\2*\3)', s)
    s = re.sub(rf'\b({_FUNCS_PATTERN})([a-zA-Z])', r'\1(\2)', s)
    s = re.sub(rf'\b({_FUNCS_PATTERN})(\d+)', r'\1(\2)', s)
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
    "x = y^2" → "(x) - (y^2)"
    """
    s = s.strip()
    if "=" in s:
        left, right = s.split("=", 1)
        left = left.strip(); right = right.strip()
        if right == "0":
            return left
        return f"({left}) - ({right})"
    return s
