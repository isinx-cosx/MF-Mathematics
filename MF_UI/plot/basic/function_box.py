# -*- coding: utf-8 -*-
"""FunctionBox — 函数输入卡片（精简 UI）。

信号:
  - changed()               表达式 / 可见性变化
  - removed(box)            删除按钮
  - param_added(str)        请求为参数创建滑块
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)
from MF_UI.utils.translator import MathTranslator

# ── 预设颜色 ──────────────────────────────────────────────────
_PRESET_COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#e84393",
]
_COLOR_IDX = 0


def next_color() -> str:
    global _COLOR_IDX
    c = _PRESET_COLORS[_COLOR_IDX % len(_PRESET_COLORS)]
    _COLOR_IDX += 1
    return c


# ── 常量 ────────────────────────────────────────────────────
_KNOWN_IDS = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'sinh', 'cosh', 'tanh', 'coth',
    'arcsin', 'arccos', 'arctan', 'asin', 'acos', 'atan',
    'ln', 'log', 'log10', 'sqrt', 'exp', 'abs', 'ceiling', 'floor',
    'limit', 'diff', 'integrate', 'Sum', 'sum', 'solve',
    'e', 'pi', 'E', 'Pi', 'oo', 'nan', 'I',
}
_CONSTANTS = {sp.E, sp.pi, sp.Symbol("e")}

# ── 样式 ────────────────────────────────────────────────────
# 注意：FunctionBox、QLineEdit、#func_del_btn 的样式
# 已由 light.qss / dark.qss 统一管理，此处仅保留功能性/动态样式
_WARN_STYLE = "QPushButton { background: transparent; border: none; font-size: 13px; padding: 0 2px; color: #d97706; }"


@dataclass
class _Parsed:
    name: str; var: str; raw_expr: str; is_explicit: bool


def parse_input(text: str, default_var: str) -> _Parsed:
    text = text.strip()
    m = re.match(r"^([a-zA-Z]\w*)\s*\(\s*([a-zA-Z])\s*\)\s*=\s*(.+)$", text)
    if m:
        return _Parsed(name=m.group(1), var=m.group(2),
                       raw_expr=m.group(3).strip(), is_explicit=True)
    return _Parsed(name="", var=default_var, raw_expr=text, is_explicit=False)


class FunctionBox(QWidget):
    """函数输入卡片 — 精简 UI，参数由独立滑块框管理。

    信号:
      changed()        — 表达式/可见性变化 → 重绘
      removed(box)     — 删除
      param_added(str) — 请求创建参数滑块
    """

    changed = Signal()
    removed = Signal(object)
    param_added = Signal(str)

    def __init__(self, index: int = 1, color: str = "",
                 mode: str = "normal", parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color or next_color()
        self._mode = mode
        if mode == "complex":
            self._default_var = "z"
        elif mode == "polar":
            self._default_var = "θ"
        else:
            self._default_var = "x"
        if mode == "3d":
            self._independent_vars = {"x", "y"}
        elif mode == "polar":
            self._independent_vars = {"θ"}
        else:
            self._independent_vars = {"x"}

        self._func_name = ""
        self._independent_var = self._default_var
        self._expr_type = "explicit"
        self._valid_expr = ""
        self._error = ""
        self._visible = True
        self._added_params: set[str] = set()       # 本框已请求的滑块
        self._existing_global: set[str] = set()   # 全局已存在的滑块

        self._build_ui()

    # ── UI ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # 卡片样式由 QSS FunctionBox 选择器管理
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8); shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(4); root.setContentsMargins(8, 6, 8, 6)

        # 主行：序号 | 显示 | 输入 | 删除
        row = QHBoxLayout(); row.setSpacing(4)

        self._index_lbl = QLabel(f"{self._index}.")
        self._index_lbl.setFixedWidth(22)
        self._index_lbl.setObjectName("func_index_lbl")
        row.addWidget(self._index_lbl)

        self._vis_btn = QPushButton("")
        self._vis_btn.setFixedSize(16, 16)
        self._vis_btn.setStyleSheet(
            "QPushButton {"
            f"  background: {self._color};"
            "  border: 2px solid rgba(0,0,0,0.15);"
            "  border-radius: 8px;"
            "}")
        self._vis_btn.setToolTip("隐藏")
        self._vis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vis_btn.clicked.connect(self._toggle_visibility)
        row.addWidget(self._vis_btn)

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        if self._mode == "polar":
            self._input.setPlaceholderText("r(θ)=")
        else:
            self._input.setPlaceholderText("f(x)=")
        # 输入框样式由 QSS FunctionBox QLineEdit 选择器管理
        self._input.textChanged.connect(self._on_text)
        row.addWidget(self._input, 1)

        self._del_btn = QPushButton("×")
        self._del_btn.setFixedSize(25, 25)
        self._del_btn.setObjectName("func_del_btn")
        self._del_btn.setToolTip("删除")
        self._del_btn.clicked.connect(lambda: self.removed.emit(self))
        row.addWidget(self._del_btn)
        root.addLayout(row)

        # 添加滑块按钮区
        self._param_btns = QHBoxLayout()
        self._param_btns.setSpacing(4)
        root.addLayout(self._param_btns)

    # ── 属性 ─────────────────────────────────────────────────

    @property
    def expr(self) -> str:
        return self._valid_expr

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def color(self) -> str:
        return self._color

    @property
    def independent_var(self) -> str:
        return self._independent_var

    @property
    def expr_type(self) -> str:
        return self._expr_type

    @property
    def is_derivative(self) -> bool:
        if self._expr_type == "implicit": return False
        d, _, _ = _parse_derivative(self._input.text().strip(), self._independent_var)
        return d is not None

    @property
    def referenced_function(self) -> str:
        if self._expr_type == "implicit": return ""
        _, _, ref = _parse_derivative(self._input.text().strip(), self._independent_var)
        return ref

    @property
    def label(self) -> str:
        return f"{self._index}."

    @property
    def detected_params(self) -> set[str]:
        if not self._valid_expr: return set()
        try:
            from MF_Mathematics.core.helpers import safe_sympify
            syms = safe_sympify(self._valid_expr).free_symbols
        except Exception:
            return set()
        excluded = {sp.Symbol(v) for v in self._independent_vars}
        excluded.add(sp.Symbol(self._independent_var))
        if self._expr_type == "implicit": excluded.add(sp.Symbol("y"))
        return {str(s) for s in syms - excluded - _CONSTANTS}

    def resolve_derivative(self, definitions: dict[str, str]) -> str:
        if not self.is_derivative: return self.expr
        ref = self.referenced_function
        if not ref or ref not in definitions: return self.expr
        try:
            d = sp.Derivative(sp.sympify(definitions[ref]), sp.Symbol(self._independent_var))
            return str(d.doit())
        except Exception:
            return self.expr

    # ── 可见性 ───────────────────────────────────────────────

    def _update_vis_button(self) -> None:
        if self._error:
            self._vis_btn.setText("⚠")
            self._vis_btn.setFixedSize(20, 20)
            self._vis_btn.setStyleSheet(_WARN_STYLE)
            self._vis_btn.setToolTip(self._error)
        elif self._visible:
            self._vis_btn.setText("")
            self._vis_btn.setFixedSize(16, 16)
            self._vis_btn.setStyleSheet(
                "QPushButton {"
                f"  background: {self._color};"
                "  border: 2px solid rgba(0,0,0,0.15);"
                "  border-radius: 8px;"
                "}")
            self._vis_btn.setToolTip("隐藏")
        else:
            self._vis_btn.setText("")
            self._vis_btn.setFixedSize(16, 16)
            self._vis_btn.setStyleSheet(
                "QPushButton {"
                "  background: transparent;"
                "  border: 2px dashed #94a3b8;"
                "  border-radius: 8px;"
                "}")
            self._vis_btn.setToolTip("显示")

    def _toggle_visibility(self) -> None:
        if self._error: return
        self._visible = not self._visible
        self._update_vis_button()
        self.changed.emit()

    # ── 输入处理 ─────────────────────────────────────────────

    def _on_text(self, _: str) -> None:
        raw = self._input.text().strip()
        if not raw:
            self._valid_expr = ""; self._error = ""
            self._update_vis_button(); self._update_param_buttons()
            self.changed.emit(); return

        classification = self._classify(raw)
        self._expr_type = classification["type"]
        if self._expr_type == "error":
            self._error = classification.get("message", "无法识别")
            self._valid_expr = ""
            self._update_vis_button(); self._update_param_buttons(); return

        # ── 预处理：隐式乘法 → sympy 兼容 ──
        def _fix_adjacent_letters(s: str) -> str:
            """在相邻字母变量间插入 *（bx→b*x, a(x)→a*(x)）。"""
            _KNOWN_F = {"sin","cos","tan","cot","sec","csc","sinh","cosh","tanh","coth",
                        "arcsin","arccos","arctan","asin","acos","atan",
                        "ln","log","sqrt","exp","abs","pi","E","Pi"}
            # 1. 非函数名后跟 ( → 插入 *
            s = re.sub(r"([a-zA-Z]+)\(",
                       lambda m: m.group(0) if m.group(1) in _KNOWN_F else m.group(1) + "*(", s)
            # 2. 已知函数名 → \x00N 标记保护（不含字母，不会被 split）
            _markers: dict[str, str] = {}
            for i, fn in enumerate(sorted(_KNOWN_F, key=len, reverse=True)):
                marker = f"\x00{i}\x00"
                _markers[marker] = fn
                s = s.replace(fn, marker)
            # 3. 剩余相邻字母间插入 *
            s = re.sub(r"([a-zA-Z])([a-zA-Z])", r"\1*\2", s)
            # 4. 恢复函数名
            for marker, fn in _markers.items():
                s = s.replace(marker, fn)
            return s

        if self._expr_type == "implicit":
            s = _normalize_implicit(raw)
            s = MathTranslator.human_to_computer(s) if s else ""
            self._valid_expr = _fix_adjacent_letters(s) if s else ""
            self._func_name = ""; self._independent_var = "x"
        else:
            d_expr, d_var, _ = _parse_derivative(raw, self._independent_var)
            if d_expr is not None:
                try:
                    d = sp.sympify(d_expr)
                    r = sp.diff(d.args[0], d.args[1]) if hasattr(d, 'func') and d.func == sp.Derivative else d.doit()
                    self._valid_expr = str(r)
                except Exception:
                    s = MathTranslator.human_to_computer(d_expr) if d_expr else ""
                    self._valid_expr = _fix_adjacent_letters(s) if s else ""
                self._func_name = ""; self._independent_var = d_var
            else:
                parsed = parse_input(raw, self._independent_var)
                self._func_name = parsed.name; self._independent_var = parsed.var
                s = parsed.raw_expr
                if self._mode == "complex":
                    s = re.sub(r'\bx\b', 'z', s); s = re.sub(r'\by\b', 'z', s)
                s = MathTranslator.human_to_computer(s) if s else ""
                self._valid_expr = _fix_adjacent_letters(s) if s else ""

        try:
            sp.sympify(self._valid_expr)
            self._error = ""
        except Exception as exc:
            self._error = f"解析错误: {str(exc)[:20]}"
            self._valid_expr = ""
            self._update_vis_button(); self._update_param_buttons(); return

        self._update_vis_button()
        self._update_param_buttons()
        self.changed.emit()

    # ── 分类 ─────────────────────────────────────────────────

    def _classify(self, raw: str) -> dict:
        raw = raw.strip()
        if not raw: return {"type": "explicit"}
        if re.match(r"^([a-zA-Z]\w*)\s*\(\s*([a-zA-Z])\s*\)\s*=\s*(.+)$", raw):
            return {"type": "explicit"}
        if "=" not in raw: return {"type": "explicit"}
        all_ids = set(re.findall(r'[a-zA-Z]\w*', raw))
        vars_found = all_ids - _KNOWN_IDS
        has_xy = ('x' in vars_found or 'X' in vars_found) and ('y' in vars_found or 'Y' in vars_found)
        if len(vars_found) > 2:
            return {"type": "error", "message": "隐式方程仅支持 x 和 y"}
        elif has_xy: return {"type": "implicit"}
        elif len(vars_found) == 1 and ('x' in vars_found or 'y' in vars_found):
            return {"type": "implicit"}
        return {"type": "explicit"}

    # ── 添加滑块按钮 ─────────────────────────────────────────

    def _update_param_buttons(self) -> None:
        while self._param_btns.count():
            item = self._param_btns.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if self._error or not self._valid_expr: return
        params = self.detected_params - self._added_params - self._existing_global
        if not params: return

        lbl = QLabel("添加滑块:")
        lbl.setObjectName("param_add_lbl")
        self._param_btns.addWidget(lbl)
        for name in sorted(params):
            btn = QPushButton(name)
            btn.setObjectName("param_add_btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, n=name: self._on_add_param(n))
            self._param_btns.addWidget(btn)
        self._param_btns.addStretch()

    def set_existing_sliders(self, names: set[str]) -> None:
        """更新全局已有滑块列表，刷新添加按钮。"""
        self._existing_global = names
        self._update_param_buttons()

    def _on_add_param(self, name: str) -> None:
        self._added_params.add(name)
        self._update_param_buttons()
        self.param_added.emit(name)

    def mark_param_removed(self, name: str) -> None:
        """外部通知：参数滑块已删除，允许重新添加。"""
        self._added_params.discard(name)
        self._update_param_buttons()


# ═══════════════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════════════

def _parse_derivative(raw: str, default_var: str = "x") -> tuple[str | None, str, str]:
    raw = raw.strip()
    if "'" not in raw: return None, "", ""
    m = re.match(r"^([a-zA-Z]\w*)\s*'\s*\(\s*([a-zA-Z])\s*\)$", raw)
    if m:
        fn, var = m.group(1), m.group(2)
        ref = "" if fn in _KNOWN_IDS else fn
        return f"Derivative({fn}({var}), {var})", var, ref
    m = re.match(r"^\((.+)\)\s*'$", raw)
    if m: return f"Derivative({m.group(1).strip()}, {default_var})", default_var, ""
    return None, "", ""


def _normalize_implicit(s: str) -> str:
    s = s.strip()
    if "=" in s:
        left, right = s.split("=", 1)
        left = left.strip(); right = right.strip()
        if right == "0": return left
        return f"({left}) - ({right})"
    return s
