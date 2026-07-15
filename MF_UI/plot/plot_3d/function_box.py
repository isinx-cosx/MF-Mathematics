# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.function_box — 3D 模式函数框。

独立于 2D 代码，仅调用 MF_Mathematics 核心数学库。
支持四种形式: 显式 z=f(x,y) / 隐式 f(x,y,z)=0 / 参数曲面 / 参数曲线。
变量仅限 x,y,z,u,v,t，无参数滑块。
"""

from __future__ import annotations

import re
import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

# ── 预设颜色 ──────────────────────────────────────────────────
_PRESET = ["#e74c3c","#3498db","#2ecc71","#f39c12",
           "#9b59b6","#1abc9c","#e67e22","#e84393"]
_CI = 0
def _nc() -> str:
    global _CI; c = _PRESET[_CI % len(_PRESET)]; _CI += 1; return c

# ── 已知函数 ──────────────────────────────────────────────────
_KNOWN = {"sin","cos","tan","cot","sec","csc","sinh","cosh","tanh","coth",
          "asin","acos","atan","arcsin","arccos","arctan",
          "ln","log","sqrt","exp","abs","sign","pi","E","e","I","oo"}

# ── 模式定义 ──────────────────────────────────────────────────
_FORM_MODES = ["显式 z=f(x,y)", "隐式 f(x,y,z)=0",
               "参数曲面 x,y,z=f(u,v)", "参数曲线 x,y,z=f(t)"]

# 每种模式允许的变量
_MODE_VARS = {
    0: {"x", "y"},            # 显式: z=f(x,y)
    1: {"x", "y", "z"},       # 隐式: f(x,y,z)=0
    2: {"u", "v"},            # 参数曲面: f(u,v)
    3: {"t"},                 # 参数曲线: f(t)
}


def _preprocess(s: str) -> str:
    """自然书写 → sympy 兼容。"""
    s = re.sub(r"\be\^\(?", "exp(", s)
    s = s.replace("^", "**")
    s = re.sub(r"\bln\b", "log", s)
    s = re.sub(r"\barcsin\b", "asin", s)
    s = re.sub(r"\barccos\b", "acos", s)
    s = re.sub(r"\barctan\b", "atan", s)
    s = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", s)
    s = re.sub(r"\)\s*\(", ")*(", s)
    s = re.sub(r"\)([a-zA-Z])", r")*\1", s)
    s = re.sub(r"([a-zA-Z])\s+([a-zA-Z])", r"\1*\2", s)
    return s


class FunctionBox(QWidget):
    """3D 模式函数框 — 四种方程形式，仅限 x,y,z,u,v,t 变量，无参数。"""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, index: int = 1, color: str = "",
                 mode: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color or _nc()
        self._visible = True
        self._form = 0          # 0=显式 1=隐式 2=参数曲面 3=参数曲线
        self._exprs: list[str] = []  # 1 或 3 个表达式
        self._error = ""

        self._build_ui()

    # ── UI ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            FunctionBox { background:#f9fafb; border:1px solid #e2e8f0;
                          border-radius:8px; padding:8px; margin:2px 0; }
        """)
        s = QGraphicsDropShadowEffect(self); s.setBlurRadius(8); s.setOffset(0,1)
        s.setColor(QColor(0,0,0,30)); self.setGraphicsEffect(s)
        root = QVBoxLayout(self); root.setSpacing(4)
        root.setContentsMargins(8,6,8,6)

        # 第 1 行：序号 | 可见 | 模式选择 | 删除
        r1 = QHBoxLayout(); r1.setSpacing(4)

        idx = QLabel(f"{self._index}.")
        idx.setFixedWidth(22)
        idx.setStyleSheet("font-weight:600; font-size:13px; color:#1e293b;")
        r1.addWidget(idx)

        self._vis = QPushButton("")
        self._vis.setFixedSize(16,16)
        self._vis.setStyleSheet(f"QPushButton{{background:{self._color};"
                                "border:2px solid rgba(0,0,0,0.15);border-radius:8px;}}")
        self._vis.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vis.clicked.connect(self._tv)
        r1.addWidget(self._vis)

        self._combo = QComboBox()
        self._combo.addItems(_FORM_MODES)
        self._combo.setStyleSheet(
            "QComboBox{font-size:11px;padding:2px 4px;border:1px solid #d1d5db;"
            "border-radius:3px;background:#fff;}")
        self._combo.currentIndexChanged.connect(self._on_form)
        r1.addWidget(self._combo)

        r1.addStretch()

        self._del_btn = QPushButton("×"); self._del_btn.setFixedSize(25,25)
        self._del_btn.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#94a3b8;"
            "font-size:18px;font-weight:bold;padding:0 4px;}"
            "QPushButton:hover{color:#ef4444;background:#fee2e2;border-radius:4px;}")
        self._del_btn.clicked.connect(lambda: self.removed.emit(self))
        r1.addWidget(self._del_btn)
        root.addLayout(r1)

        # 输入区 — 根据模式动态创建
        self._input_area = QVBoxLayout()
        self._input_area.setSpacing(3)
        root.addLayout(self._input_area)

        # 错误
        self._err = QLabel("")
        self._err.setStyleSheet("color:#dc2626;font-size:11px;padding:0 4px;")
        self._err.setWordWrap(True); self._err.hide()
        root.addWidget(self._err)

        self._rebuild_inputs()

    # ── 输入框重建 ───────────────────────────────────────────

    def _rebuild_inputs(self) -> None:
        while self._input_area.count():
            it = self._input_area.takeAt(0)
            if it.widget(): it.widget().deleteLater()

        self._inputs: list[QLineEdit] = []

        if self._form == 0:           # 显式 z=f(x,y)
            lbl = QLabel("z = f(x, y)")
            lbl.setStyleSheet("font-size:11px; color:#64748b;")
            self._input_area.addWidget(lbl)
            self._add_input("sin(x)*cos(y)")
        elif self._form == 1:         # 隐式 f(x,y,z)=0
            lbl = QLabel("f(x, y, z) = 0")
            lbl.setStyleSheet("font-size:11px; color:#64748b;")
            self._input_area.addWidget(lbl)
            self._add_input("x^2+y^2+z^2-1")
        elif self._form == 2:         # 参数曲面
            for axis, ph in [("x(u,v)", "u*cos(v)"),
                             ("y(u,v)", "u*sin(v)"),
                             ("z(u,v)", "u")]:
                self._add_labeled_input(axis, ph)
        elif self._form == 3:         # 参数曲线
            for axis, ph in [("x(t)", "cos(t)"),
                             ("y(t)", "sin(t)"),
                             ("z(t)", "t")]:
                self._add_labeled_input(axis, ph)

    def _add_input(self, ph: str) -> None:
        inp = QLineEdit(); inp.setFixedHeight(28); inp.setPlaceholderText(ph)
        inp.setStyleSheet("QLineEdit{border:1px solid #d1d5db;border-radius:4px;"
                          "padding:3px 8px;font-size:13px;background:#fff;color:#1e293b;}"
                          "QLineEdit:focus{border-color:#3b82f6;}")
        inp.textChanged.connect(self._on_text)
        self._input_area.addWidget(inp)
        self._inputs.append(inp)

    def _add_labeled_input(self, label: str, ph: str) -> None:
        r = QHBoxLayout(); r.setSpacing(4)
        l = QLabel(label); l.setFixedWidth(44)
        l.setStyleSheet("font-size:11px;color:#64748b;")
        r.addWidget(l)
        inp = QLineEdit(); inp.setFixedHeight(26); inp.setPlaceholderText(ph)
        inp.setStyleSheet("QLineEdit{border:1px solid #d1d5db;border-radius:4px;"
                          "padding:2px 6px;font-size:12px;background:#fff;color:#1e293b;}"
                          "QLineEdit:focus{border-color:#3b82f6;}")
        inp.textChanged.connect(self._on_text)
        r.addWidget(inp, 1)
        self._input_area.addLayout(r)
        self._inputs.append(inp)

    # ── 属性 ─────────────────────────────────────────────────

    @property
    def is_visible(self) -> bool: return self._visible

    @property
    def color(self) -> str: return self._color

    @property
    def form(self) -> int: return self._form

    @property
    def exprs(self) -> list[str]: return self._exprs

    # ── 交互 ─────────────────────────────────────────────────

    def _tv(self) -> None:
        self._visible = not self._visible
        self._vis.setStyleSheet(
            f"QPushButton{{background:{self._color};"
            "border:2px solid rgba(0,0,0,0.15);border-radius:8px;}}"
            if self._visible else
            "QPushButton{background:transparent;"
            "border:2px dashed #94a3b8;border-radius:8px;}")
        self.changed.emit()

    def _on_form(self, idx: int) -> None:
        self._form = idx; self._exprs = []
        self._rebuild_inputs(); self.changed.emit()

    def _on_text(self, _: str) -> None:
        self._error = ""; self._err.hide()
        raw = [inp.text().strip() for inp in self._inputs]
        if not any(raw): self._exprs = []; self.changed.emit(); return

        allowed = _MODE_VARS[self._form]
        self._exprs = []
        for i, s in enumerate(raw):
            if not s: continue
            s = _preprocess(s)
            try:
                expr = sp.sympify(s)
            except Exception as e:
                self._error = f"表达式 {i+1} 解析错误"; self._err.setText(self._error)
                self._err.show(); self._exprs = []; return

            syms = {str(x) for x in expr.free_symbols}
            bad = syms - allowed - _KNOWN
            if bad:
                self._error = f"变量 {', '.join(sorted(bad))} 无效（仅允许 {', '.join(sorted(allowed))}）"
                self._err.setText(self._error); self._err.show()
                self._exprs = []; return

            self._exprs.append(s)

        self.changed.emit()
