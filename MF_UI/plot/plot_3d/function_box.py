# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.function_box — 3D 模式函数框。

独立于 2D 代码，仅调用 MF_Mathematics 核心数学库。
自动识别: 显式 z=f(x,y) / 隐式 f(x,y,z)=0 / 参数形式。
变量仅限 x,y,z,u,v,t，无参数。
"""

from __future__ import annotations

import re
import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

_PRESET = ["#e74c3c","#3498db","#2ecc71","#f39c12",
           "#9b59b6","#1abc9c","#e67e22","#e84393"]
_CI = 0
def _nc() -> str:
    global _CI; c = _PRESET[_CI % len(_PRESET)]; _CI += 1; return c

_KNOWN = {"sin","cos","tan","cot","sec","csc","sinh","cosh","tanh","coth",
          "asin","acos","atan","arcsin","arccos","arctan",
          "ln","log","sqrt","exp","abs","sign","pi","E","e","I","oo"}

# 三种模式允许的变量
_ALLOWED = {"x","y","z","u","v","t"}


def _preprocess(s: str) -> str:
    s = re.sub(r"\be\^\(?", "exp(", s)
    s = s.replace("^", "**")
    s = re.sub(r"\bln\b", "log", s)
    s = re.sub(r"\barcsin\b", "asin", s)
    s = re.sub(r"\barccos\b", "acos", s)
    s = re.sub(r"\barctan\b", "atan", s)
    _KF = {"sin","cos","tan","cot","sec","csc","sinh","cosh","tanh","coth",
           "asin","acos","atan","arcsin","arccos","arctan",
           "ln","log","sqrt","exp","abs","pi","E","Pi"}
    _mk = {}
    for i, fn in enumerate(sorted(_KF, key=len, reverse=True)):
        m = f"\x00{i}\x00"; _mk[m] = fn; s = s.replace(fn, m)
    s = re.sub(r"(\d)\s*\(", r"\1*(", s)
    s = re.sub(r"\)\s*\(", ")*(", s)
    s = re.sub(r"\)([a-zA-Z])", r")*\1", s)
    s = re.sub(r"([a-zA-Z])\s*\(", r"\1*(", s)
    s = re.sub(r"([a-zA-Z])\s+([a-zA-Z])", r"\1*\2", s)
    s = re.sub(r"([a-zA-Z])([a-zA-Z])", r"\1*\2", s)
    for m, fn in _mk.items(): s = s.replace(m, fn)
    s = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", s)
    F = "sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|coth|arcsin|arccos|arctan|asin|acos|atan|ln|log|sqrt|exp|abs"
    s = re.sub(rf"\b({F})([a-zA-Z])", r"\1(\2)", s)
    return s


class FunctionBox(QWidget):
    """3D 函数框 — 自动识别方程形式，与 2D 风格一致。"""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, index: int = 1, color: str = "",
                 mode: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color or _nc()
        self._visible = True
        self._valid: list[str] = []
        self._error = ""

        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            FunctionBox { background:#f9fafb; border:1px solid #e2e8f0;
                          border-radius:8px; padding:8px; margin:2px 0; }
        """)
        s = QGraphicsDropShadowEffect(self); s.setBlurRadius(8); s.setOffset(0,1)
        s.setColor(QColor(0,0,0,30)); self.setGraphicsEffect(s)
        root = QVBoxLayout(self); root.setSpacing(4)
        root.setContentsMargins(8,6,8,6)

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

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setPlaceholderText("sin(x)*cos(y), x^2+y^2+z^2=1, x=u*cos(v);y=u*sin(v);z=u")
        self._input.setStyleSheet(
            "QLineEdit{border:1px solid #d1d5db;border-radius:4px;"
            "padding:3px 8px;font-size:13px;background:#fff;color:#1e293b;}"
            "QLineEdit:focus{border-color:#3b82f6;}")
        self._input.textChanged.connect(self._on_text)
        r1.addWidget(self._input, 1)

        self._del_btn = QPushButton("×"); self._del_btn.setFixedSize(25,25)
        self._del_btn.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#94a3b8;"
            "font-size:18px;font-weight:bold;padding:0 4px;}"
            "QPushButton:hover{color:#ef4444;background:#fee2e2;border-radius:4px;}")
        self._del_btn.clicked.connect(lambda: self.removed.emit(self))
        r1.addWidget(self._del_btn)
        root.addLayout(r1)

        self._hint = QLabel("")
        self._hint.setStyleSheet("font-size:11px; color:#64748b;")
        root.addWidget(self._hint)

        self._err = QLabel("")
        self._err.setStyleSheet("color:#dc2626;font-size:11px;padding:0 4px;")
        self._err.setWordWrap(True); self._err.hide()
        root.addWidget(self._err)

    @property
    def is_visible(self) -> bool: return self._visible
    @property
    def color(self) -> str: return self._color
    @property
    def exprs(self) -> list[str]: return self._valid

    def _tv(self) -> None:
        self._visible = not self._visible
        self._vis.setStyleSheet(
            f"QPushButton{{background:{self._color};"
            "border:2px solid rgba(0,0,0,0.15);border-radius:8px;}}"
            if self._visible else
            "QPushButton{background:transparent;"
            "border:2px dashed #94a3b8;border-radius:8px;}")
        self.changed.emit()

    def _on_text(self, _: str) -> None:
        raw = self._input.text().strip()
        self._error = ""; self._err.hide(); self._valid = []

        if not raw:
            self._hint.setText(""); self.changed.emit(); return

        # ── 检测分号分隔（参数形式: x=f(u,v); y=g(u,v); z=h(u,v)）──
        if ";" in raw:
            self._valid = self._parse_multi(raw)
            if self._valid:
                n = len(self._valid)
                self._hint.setText(f"参数{'曲面' if n==3 else '曲线'}（{n} 个表达式）")
            self.changed.emit(); return

        # ── 含 = → 隐式或显式 ──
        if "=" in raw and ";" not in raw:
            left, _, right = raw.partition("=")
            left = left.strip(); right = right.strip()
            # z = f(x,y) → 显式
            if left in ("z", "Z") and right:
                s = _preprocess(right)
                if self._check_vars(s, {"x","y"}):
                    self._valid = [s]; self._hint.setText("显式 z = f(x, y)")
                self.changed.emit(); return
            # f(x,y,z) = value → 移项: left - right = 0
            s = _preprocess(f"({left}) - ({right})")
            if self._check_vars(s, {"x","y","z"}):
                self._valid = [s]; self._hint.setText("隐式 f(x, y, z) = 0")
            self.changed.emit(); return

        # ── 无 = → 默认显式 z=f(x,y) ──
        s = _preprocess(raw)
        if self._check_vars(s, {"x","y"}):
            self._valid = [s]; self._hint.setText("显式 z = f(x, y)")
        self.changed.emit()

    def _parse_multi(self, raw: str) -> list[str]:
        """解析分号分隔的参数方程，自动检测变量类型。"""
        parts = [p.strip() for p in raw.split(";")]
        result = []
        all_vars: set[str] = set()
        for p in parts:
            if "=" in p:
                left, _, right = p.partition("=")
                left = left.strip(); right = right.strip()
                if re.match(r"^[xyzXYZ]$", left) and right:
                    s = _preprocess(right)
                    try:
                        expr = sp.sympify(s)
                    except Exception:
                        self._err.setText("解析错误"); self._err.show(); return []
                    all_vars |= {str(x) for x in expr.free_symbols}
                    result.append(s)
                    continue
            self._err.setText("参数格式: x=f(...); y=g(...); z=h(...)")
            self._err.show(); return []
        # 检查变量合法性
        bad = all_vars - _ALLOWED - _KNOWN
        if bad:
            self._err.setText(f"变量 {', '.join(sorted(bad))} 无效")
            self._err.show(); return []
        if not all_vars.issubset({"u","v","t"}):
            self._err.setText("参数仅允许 u,v,t 变量"); self._err.show(); return []
        if result:
            self._hint.setText(f"参数{'曲面' if len(result)>=3 else '曲线'}（{len(result)} 表达式）")
        return result

    def _check_vars(self, s: str, allowed: set[str], silent: bool = False) -> bool:
        try:
            expr = sp.sympify(s)
        except Exception as e:
            if not silent:
                self._err.setText(f"解析错误: {e}"); self._err.show()
            return False
        syms = {str(x) for x in expr.free_symbols}
        bad = syms - allowed - _KNOWN
        if bad:
            if not silent:
                self._err.setText(f"变量 {', '.join(sorted(bad))} 无效（仅允许 {', '.join(sorted(allowed))}）")
                self._err.show()
            return False
        return True
