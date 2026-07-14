# -*- coding: utf-8 -*-
"""FunctionBox — 函数输入卡片（BaseFunctionBox → 2D / 3D 子类）。

架构:
  BaseFunctionBox   — 全部 UI + 表达式解析 + 参数检测 + 信号
  ├── FunctionBox2D — 默认自变量 {x}（普通 2D 模式）
  └── FunctionBox3D — 默认自变量 {x, y}（3D 曲面模式）

信号:
  - changed()               表达式 / 可见性变化
  - removed(box)            删除按钮点击
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

# ── 已知函数名 ──────────────────────────────────────────────
_FUNCS_PATTERN = (
    "sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|coth|"
    "arcsin|arccos|arctan|asin|acos|atan|"
    "ln|log|log10|sqrt|exp|abs|ceiling|floor|"
    "limit|diff|integrate|Sum|sum|solve"
)

_KNOWN_IDS = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'sinh', 'cosh', 'tanh', 'coth',
    'arcsin', 'arccos', 'arctan', 'asin', 'acos', 'atan',
    'ln', 'log', 'log10', 'sqrt', 'exp', 'abs', 'ceiling', 'floor',
    'limit', 'diff', 'integrate', 'Sum', 'sum', 'solve',
    'e', 'pi', 'E', 'Pi', 'oo', 'nan', 'I',
}

_CONSTANTS = {sp.E, sp.pi, sp.Symbol("e")}

# ── 功能性内联样式（不随主题变化）─────────────────────────
_ERR_STYLE = "color: #dc2626; font-size: 11px; padding: 0 4px;"
_TYPE_TAG_STYLE = (
    "font-size: 10px; font-weight: 600; border-radius: 3px; padding: 1px 6px;"
)


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


# ═══════════════════════════════════════════════════════════════════════
#  BaseFunctionBox — 全部 UI + 共享逻辑
# ═══════════════════════════════════════════════════════════════════════

class BaseFunctionBox(QWidget):
    """函数卡片基类 — UI 完全一致，子类仅需定义自变量集合。"""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, index: int = 1, color: str = "#3498db",
                 mode: str = "normal", parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color
        self._mode = mode

        self._func_name = ""
        self._independent_var = self._get_default_var()
        self._expr_type = "explicit"
        self._updating = False

        self._build_ui()

    # ── 子类覆盖 ─────────────────────────────────────────────

    def _get_default_var(self) -> str:
        """主自变量名（用于导数解析等）。2D→"x", 3D→"x"。"""
        return "x"

    def get_independent_vars(self) -> set[str]:
        """返回所有自变量名（用于参数排除）。2D→{"x"}, 3D→{"x","y"}。"""
        return {"x"}

    def _get_placeholder(self) -> str:
        return "sinx, e^x, g(t)=sin(t), x^2+y^2=25"

    # ── UI 构建（所有子类完全一致）─────────────────────────

    def _build_ui(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8); shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(3); root.setContentsMargins(8, 6, 8, 6)

        # 第 1 行
        row1 = QHBoxLayout(); row1.setSpacing(6)
        self._title = QLabel(f"{self._index}.")
        self._title.setStyleSheet("font-weight:600; font-size:13px;")
        row1.addWidget(self._title)

        self._type_tag = QLabel("")
        self._type_tag.setStyleSheet(_TYPE_TAG_STYLE)
        self._type_tag.hide()
        row1.addWidget(self._type_tag)

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setPlaceholderText(self._get_placeholder())
        self._input.textChanged.connect(self._on_text)
        row1.addWidget(self._input, 1)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{self._color}; font-size:16px;")
        dot.setFixedWidth(20); dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row1.addWidget(dot)
        root.addLayout(row1)

        # 错误提示
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(_ERR_STYLE)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root.addWidget(self._error_label)

        # 第 2 行
        row2 = QHBoxLayout(); row2.setSpacing(4)
        self._param_hint = QLabel("")
        self._param_hint.setStyleSheet("font-size: 11px;")
        row2.addWidget(self._param_hint)
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
        raw = self._input.text().strip()
        if not raw:
            return ""
        if self._expr_type == "implicit":
            s = _normalize_implicit(raw)
            return _preprocess(s) if s else ""

        deriv_expr, deriv_var, _ref = _parse_derivative(raw, self._independent_var)
        if deriv_expr is not None:
            try:
                d = sp.sympify(deriv_expr)
                result = sp.diff(d.args[0], d.args[1]) if hasattr(d, 'func') and d.func == sp.Derivative else d.doit()
                return str(result)
            except Exception:
                return _preprocess(deriv_expr) if deriv_expr else ""

        parsed = parse_input(raw, self._independent_var)
        s = parsed.raw_expr
        if self._mode == "complex":
            s = re.sub(r'\bx\b', 'z', s); s = re.sub(r'\by\b', 'z', s)
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
        return self._expr_type

    @property
    def is_derivative(self) -> bool:
        if self._expr_type == "implicit":
            return False
        raw = self._input.text().strip()
        d, _, _ = _parse_derivative(raw, self._independent_var)
        return d is not None

    @property
    def referenced_function(self) -> str:
        if self._expr_type == "implicit":
            return ""
        raw = self._input.text().strip()
        _, _, ref = _parse_derivative(raw, self._independent_var)
        return ref

    def resolve_derivative(self, definitions: dict[str, str]) -> str:
        if not self.is_derivative:
            return self.expr
        ref = self.referenced_function
        if not ref or ref not in definitions:
            return self.expr
        try:
            d = sp.Derivative(sp.sympify(definitions[ref]),
                              sp.Symbol(self._independent_var))
            return str(d.doit())
        except Exception:
            return self.expr

    @property
    def label(self) -> str:
        if self._expr_type == "implicit":
            return f"{self._index}. 隐式"
        if self.is_derivative:
            raw = self._input.text().strip()
            return f"{self._index}. 导数: {raw}"
        if self._func_name:
            return f"{self._index}. {self._func_name}({self._independent_var})"
        return f"{self._index}."

    @property
    def detected_params(self) -> set[str]:
        """检测到的未知参数（排除自变量 + 常数）。"""
        e = self.expr
        if not e:
            return set()
        try:
            syms = sp.sympify(e).free_symbols
        except Exception:
            return set()
        excluded = {sp.Symbol(v) for v in self.get_independent_vars()}
        if self._expr_type == "implicit":
            excluded.add(sp.Symbol("y"))
        return {str(s) for s in syms - excluded - _CONSTANTS}

    # ── 分类 ─────────────────────────────────────────────────

    def _classify(self, raw: str) -> dict:
        raw = raw.strip()
        if not raw:
            return {"type": "explicit"}
        if re.match(r"^([a-zA-Z]\w*)\s*\(\s*([a-zA-Z])\s*\)\s*=\s*(.+)$", raw):
            return {"type": "explicit"}
        if "=" not in raw:
            return {"type": "explicit"}

        all_ids = set(re.findall(r'[a-zA-Z]\w*', raw))
        vars_found = all_ids - _KNOWN_IDS
        has_xy = ('x' in vars_found or 'X' in vars_found) and \
                 ('y' in vars_found or 'Y' in vars_found)

        if len(vars_found) > 2:
            return {"type": "error",
                    "message": f"隐式方程仅支持 x 和 y，检测到 {len(vars_found)} 个变量: "
                               f"{', '.join(sorted(vars_found))}。\n请简化为二元方程。"}
        elif has_xy:
            return {"type": "implicit"}
        elif len(vars_found) == 1 and ('x' in vars_found or 'y' in vars_found):
            return {"type": "implicit"}
        else:
            return {"type": "explicit"}

    # ── 输入处理 ─────────────────────────────────────────────

    def _on_text(self, _txt: str) -> None:
        if self._updating:
            return
        raw = self._input.text().strip()
        if not raw:
            self._error_label.hide(); self._type_tag.hide()
            self._expr_type = "explicit"
            self._update_param_hint_text()
            self.changed.emit()
            return

        classification = self._classify(raw)
        self._expr_type = classification["type"]

        if self._expr_type == "error":
            self._error_label.setText(classification.get("message", "无法识别"))
            self._error_label.show()
            self._type_tag.hide(); self._param_hint.setText("")
            return

        if self._expr_type == "implicit":
            self._type_tag.setText("隐式")
            self._type_tag.setStyleSheet(
                _TYPE_TAG_STYLE + "color: #7c3aed; background: #f3e8ff;")
            self._type_tag.show()
            self._title.setText(f"{self._index}.")
            self._func_name = ""
            self._independent_var = "x"
        else:
            d_expr, d_var, _d_ref = _parse_derivative(raw, self._independent_var)
            if d_expr is not None:
                self._type_tag.setText("导数")
                self._type_tag.setStyleSheet(
                    _TYPE_TAG_STYLE + "color: #dc2626; background: #fee2e2;")
                self._type_tag.show()
                self._title.setText(f"{self._index}. 导数:")
                self._func_name = ""
                self._independent_var = d_var
            else:
                self._type_tag.setText("显式")
                self._type_tag.setStyleSheet(
                    _TYPE_TAG_STYLE + "color: #2563eb; background: #dbeafe;")
                self._type_tag.show()
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
            self._error_label.hide(); return
        try:
            sp.sympify(e)
            self._error_label.hide()
        except Exception as exc:
            self._error_label.setText(f"解析错误: {exc}")
            self._error_label.show()

    # ── 参数提示 ─────────────────────────────────────────────

    def refresh_param_hint(self, existing_global_params: set[str]) -> None:
        self._update_param_hint_text(existing_global_params)

    def _update_param_hint_text(self, existing: set[str] | None = None) -> None:
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
#  FunctionBox2D — 2D 模式（默认自变量 x）
# ═══════════════════════════════════════════════════════════════════════

class FunctionBox2D(BaseFunctionBox):
    """2D 函数框 — 自变量 {x}（与旧 FunctionBox 行为完全一致）。"""

    def _get_default_var(self) -> str:
        return "x"

    def get_independent_vars(self) -> set[str]:
        return {"x"}


# ═══════════════════════════════════════════════════════════════════════
#  FunctionBox3D — 3D 模式（自变量 x, y）
# ═══════════════════════════════════════════════════════════════════════

class FunctionBox3D(BaseFunctionBox):
    """3D 函数框 — 自变量 {x, y}，z = f(x, y)。"""

    def _get_default_var(self) -> str:
        return "x"

    def get_independent_vars(self) -> set[str]:
        return {"x", "y"}

    def _get_placeholder(self) -> str:
        return "sin(x)*cos(y), x^2+y^2, a*x^2+b*y^2"


# ═══════════════════════════════════════════════════════════════════════
#  向后兼容别名
# ═══════════════════════════════════════════════════════════════════════

FunctionBox = FunctionBox2D


# ═══════════════════════════════════════════════════════════════════════
#  模块级辅助函数
# ═══════════════════════════════════════════════════════════════════════

def _parse_derivative(raw: str, default_var: str = "x") -> tuple[str | None, str, str]:
    raw = raw.strip()
    if "'" not in raw:
        return None, "", ""
    m = re.match(r"^([a-zA-Z]\w*)\s*'\s*\(\s*([a-zA-Z])\s*\)$", raw)
    if m:
        func_name = m.group(1); var = m.group(2)
        ref = "" if func_name in _KNOWN_IDS else func_name
        return f"Derivative({func_name}({var}), {var})", var, ref
    m = re.match(r"^\((.+)\)\s*'$", raw)
    if m:
        inner = m.group(1).strip()
        return f"Derivative({inner}, {default_var})", default_var, ""
    return None, "", ""


def _preprocess(s: str) -> str:
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
    s = s.strip()
    if "=" in s:
        left, right = s.split("=", 1)
        left = left.strip(); right = right.strip()
        if right == "0":
            return left
        return f"({left}) - ({right})"
    return s
