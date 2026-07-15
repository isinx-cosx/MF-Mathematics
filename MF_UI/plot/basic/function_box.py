# -*- coding: utf-8 -*-
"""FunctionBox — 函数输入卡片（精简 UI）。

信号:
  - changed()               表达式 / 可见性 / 参数变化
  - removed(box)            删除按钮点击
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget,
)

# ── 预设颜色 ──────────────────────────────────────────────────
_PRESET_COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#e84393",
]
_COLOR_INDEX = 0


def next_color() -> str:
    global _COLOR_INDEX
    c = _PRESET_COLORS[_COLOR_INDEX % len(_PRESET_COLORS)]
    _COLOR_INDEX += 1
    return c


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

# ── 样式 ────────────────────────────────────────────────────
_CARD_STYLE = """
    FunctionBox {
        background: #f9fafb; border: 1px solid #e2e8f0;
        border-radius: 8px; padding: 8px; margin: 2px 0;
    }
"""
_INPUT_STYLE = """
    QLineEdit {
        border: 1px solid #d1d5db; border-radius: 4px;
        padding: 3px 8px; font-size: 13px; background: #fff; color: #1e293b;
    }
    QLineEdit:focus { border-color: #3b82f6; }
"""
_DEL_STYLE = """
    QPushButton {
        background: transparent; border: none; color: #94a3b8;
        font-size: 18px; font-weight: bold; padding: 0 4px;
    }
    QPushButton:hover { color: #ef4444; background: #fee2e2; border-radius: 4px; }
"""
_VIS_STYLE = """
    QPushButton { background: transparent; border: none; font-size: 14px; padding: 0 2px; }
"""
_ERR_STYLE = "color: #dc2626; font-size: 11px; padding: 0 4px;"


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
    """函数输入卡片。

    信号:
      changed()  — 表达式 / 可见性 / 参数变化
      removed(box) — 删除按钮
    """

    changed = Signal()
    removed = Signal(object)

    def __init__(self, index: int = 1, color: str = "",
                 mode: str = "normal", parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color or next_color()
        self._mode = mode
        self._default_var = "z" if mode == "complex" else "x"
        self._independent_vars = {"x", "y"} if mode == "3d" else {"x"}

        self._func_name = ""
        self._independent_var = self._default_var
        self._expr_type = "explicit"
        self._valid_expr = ""
        self._updating = False
        self._params: dict[str, tuple[QSlider, QLineEdit]] = {}

        self._build_ui()

    # ── UI ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setStyleSheet(_CARD_STYLE)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8); shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(3); root.setContentsMargins(6, 4, 6, 4)

        # ── 主行：序号 | 显示 | 输入 | 删除 ──
        row = QHBoxLayout(); row.setSpacing(4)

        self._index_lbl = QLabel(f"{self._index}.")
        self._index_lbl.setFixedWidth(22)
        self._index_lbl.setStyleSheet("font-weight:600; font-size:13px; color:#1e293b;")
        row.addWidget(self._index_lbl)

        self._vis_btn = QPushButton("●")
        self._vis_btn.setFixedSize(20, 20)
        self._vis_btn.setStyleSheet(_VIS_STYLE + f"color:{self._color};")
        self._vis_btn.setToolTip("切换显示/隐藏")
        self._vis_btn.clicked.connect(self._toggle_visibility)
        row.addWidget(self._vis_btn)

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setPlaceholderText("表达式")
        self._input.setStyleSheet(_INPUT_STYLE)
        self._input.textChanged.connect(self._on_text)
        row.addWidget(self._input, 1)

        self._del_btn = QPushButton("×")
        self._del_btn.setFixedSize(25, 25)
        self._del_btn.setStyleSheet(_DEL_STYLE)
        self._del_btn.setToolTip("删除")
        self._del_btn.clicked.connect(lambda: self.removed.emit(self))
        row.addWidget(self._del_btn)

        root.addLayout(row)

        # ── 错误提示 ──
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(_ERR_STYLE)
        self._error_label.setWordWrap(True); self._error_label.hide()
        root.addWidget(self._error_label)

        # ── 参数滑块区 ──
        self._slider_area = QVBoxLayout()
        self._slider_area.setSpacing(2)
        root.addLayout(self._slider_area)

    # ── 属性 ─────────────────────────────────────────────────

    @property
    def expr(self) -> str:
        return self._valid_expr

    @property
    def is_visible(self) -> bool:
        return self._vis_btn.text() == "●"

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
        if self._expr_type == "implicit":
            return False
        raw = self._input.text().strip()
        d, _, _ = _parse_derivative(raw, self._independent_var)
        return d is not None

    @property
    def referenced_function(self) -> str:
        if self._expr_type == "implicit":
            return ""
        _, _, ref = _parse_derivative(self._input.text().strip(), self._independent_var)
        return ref

    @property
    def label(self) -> str:
        return f"{self._index}."

    @property
    def detected_params(self) -> set[str]:
        if not self._valid_expr:
            return set()
        try:
            syms = sp.sympify(self._valid_expr).free_symbols
        except Exception:
            return set()
        excluded = {sp.Symbol(v) for v in self._independent_vars}
        excluded.add(sp.Symbol(self._independent_var))
        if self._expr_type == "implicit":
            excluded.add(sp.Symbol("y"))
        return {str(s) for s in syms - excluded - _CONSTANTS}

    def get_params(self) -> dict[str, float]:
        return {k: s.value() / 100.0 for k, (s, _) in self._params.items()}

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

    # ── 可见性切换 ───────────────────────────────────────────

    def _toggle_visibility(self) -> None:
        if self._vis_btn.text() == "●":
            self._vis_btn.setText("○")
            self._vis_btn.setStyleSheet(_VIS_STYLE + "color:#94a3b8;")
        else:
            self._vis_btn.setText("●")
            self._vis_btn.setStyleSheet(_VIS_STYLE + f"color:{self._color};")
        self.changed.emit()

    # ── 输入处理 ─────────────────────────────────────────────

    def _on_text(self, _: str) -> None:
        if self._updating:
            return
        raw = self._input.text().strip()

        if not raw:
            self._error_label.hide(); self._valid_expr = ""
            self._clear_sliders(); self.changed.emit(); return

        # 分类
        classification = self._classify(raw)
        self._expr_type = classification["type"]
        if self._expr_type == "error":
            self._error_label.setText(classification.get("message", "无法识别"))
            self._error_label.show()
            self._valid_expr = ""; self._clear_sliders(); return

        # 获取表达式
        if self._expr_type == "implicit":
            s = _normalize_implicit(raw)
            self._valid_expr = _preprocess(s) if s else ""
            self._func_name = ""
            self._independent_var = "x"
        else:
            d_expr, d_var, _ = _parse_derivative(raw, self._independent_var)
            if d_expr is not None:
                try:
                    d = sp.sympify(d_expr)
                    result = sp.diff(d.args[0], d.args[1]) if hasattr(d, 'func') and d.func == sp.Derivative else d.doit()
                    self._valid_expr = str(result)
                except Exception:
                    self._valid_expr = _preprocess(d_expr) if d_expr else ""
                self._func_name = ""
                self._independent_var = d_var
            else:
                parsed = parse_input(raw, self._independent_var)
                self._func_name = parsed.name
                self._independent_var = parsed.var
                s = parsed.raw_expr
                if self._mode == "complex":
                    s = re.sub(r'\bx\b', 'z', s); s = re.sub(r'\by\b', 'z', s)
                self._valid_expr = _preprocess(s) if s else ""

        # 验证
        try:
            sp.sympify(self._valid_expr)
            self._error_label.hide()
        except Exception as exc:
            self._error_label.setText(f"解析错误: {exc}")
            self._error_label.show()
            self._valid_expr = ""; self._clear_sliders(); return

        # 参数滑块
        self._rebuild_sliders()
        self.changed.emit()

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
            return {"type": "error", "message": f"隐式方程仅支持 x 和 y，检测到 {len(vars_found)} 个变量。"}
        elif has_xy:
            return {"type": "implicit"}
        elif len(vars_found) == 1 and ('x' in vars_found or 'y' in vars_found):
            return {"type": "implicit"}
        return {"type": "explicit"}

    # ── 参数滑块 ─────────────────────────────────────────────

    def _clear_sliders(self) -> None:
        for s, e in self._params.values():
            s.deleteLater(); e.deleteLater()
        self._params.clear()
        while self._slider_area.count():
            item = self._slider_area.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _rebuild_sliders(self) -> None:
        self._clear_sliders()
        names = sorted(self.detected_params)
        for name in names:
            r = QHBoxLayout(); r.setSpacing(4)
            lbl = QLabel(f"{name} ="); lbl.setFixedWidth(26)
            lbl.setStyleSheet("font-size:11px; color:#475569;")
            r.addWidget(lbl)

            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(-500, 500); s.setValue(100)
            r.addWidget(s, 1)

            e = QLineEdit("1.00"); e.setFixedWidth(48)
            e.setStyleSheet("font-size:11px; padding:1px 3px; border:1px solid #d1d5db; border-radius:3px;")
            r.addWidget(e)

            s.valueChanged.connect(lambda v, ed=e: self._on_slider_move(v, ed))
            e.editingFinished.connect(lambda sl=s, ed=e: self._on_edit_done(sl, ed))

            self._slider_area.addLayout(r)
            self._params[name] = (s, e)

    def _on_slider_move(self, value: int, edit: QLineEdit) -> None:
        if self._updating: return
        v = value / 100.0
        self._updating = True; edit.setText(f"{v:.2f}"); self._updating = False
        self.changed.emit()

    def _on_edit_done(self, slider: QSlider, edit: QLineEdit) -> None:
        if self._updating: return
        try:
            v = float(edit.text()); v = max(-5.0, min(5.0, v))
            self._updating = True; edit.setText(f"{v:.2f}")
            slider.setValue(int(round(v * 100))); self._updating = False
            self.changed.emit()
        except ValueError:
            edit.setText("0.00")


# ═══════════════════════════════════════════════════════════════════════
#  模块级辅助函数
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
        if right == "0": return left
        return f"({left}) - ({right})"
    return s
