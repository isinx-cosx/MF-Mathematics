# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.function_box — 3D 模式专用函数框。

与 2D FunctionBox 完全独立，无继承关系。
支持参数（a, b, c...），每个参数自动生成滑块。

用法:
    box = FunctionBox(index=1, color="#e74c3c", parent=self)
    box.changed.connect(...)   # 表达式/参数变化 → 触发曲面重绘
    box.removed.connect(...)   # 删除按钮 → 移除曲面
    box.get_params()           # → {"a": 1.5, "b": 2.0}
"""

from __future__ import annotations

import re

import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget,
)

# ── 自变量（不识别为参数）───────────────────────────────────
_INDEP_VARS = {"x", "y", "z"}

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

# ── 内联样式 ────────────────────────────────────────────────
_ERR_STYLE = "color: #dc2626; font-size: 11px; padding: 0 4px;"
_SLIDER_ROW_STYLE = "font-size: 11px; color: #475569;"


class FunctionBox(QWidget):
    """3D 模式函数框 — z = f(x, y, z)，支持参数滑块。

    信号:
      changed()   — 表达式 / 参数 / 可见性变化
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
        self._params: dict[str, tuple[QSlider, QLineEdit]] = {}
        self._updating = False

        self._build_ui()

    # ── UI ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8); shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(3); root.setContentsMargins(8, 6, 8, 6)

        # 第 1 行：标题 + 输入 + 色点
        row1 = QHBoxLayout(); row1.setSpacing(6)
        self._title = QLabel(f"{self._index}.")
        self._title.setStyleSheet("font-weight:600; font-size:13px;")
        row1.addWidget(self._title)

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setPlaceholderText("sin(x)*cos(y), a*x^2+b*y^2")
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
        self._error_label.setWordWrap(True); self._error_label.hide()
        root.addWidget(self._error_label)

        # 参数滑块区
        self._slider_area = QVBoxLayout()
        self._slider_area.setSpacing(2)
        root.addLayout(self._slider_area)

        # 第 2 行：提示 + 显示开关 + 删除
        row2 = QHBoxLayout(); row2.setSpacing(4)
        self._hint = QLabel("")
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

    def get_params(self) -> dict[str, float]:
        """返回当前滑块参数值。"""
        return {k: s.value() / 100.0 for k, (s, _) in self._params.items()}

    # ── 输入处理 ─────────────────────────────────────────────

    def _on_text(self, _txt: str) -> None:
        if self._updating:
            return
        raw = self._input.text().strip()

        if not raw:
            self._error_label.hide()
            self._valid_expr = ""
            self._clear_sliders()
            self._hint.setText("")
            self.changed.emit()
            return

        processed = _preprocess_3d(raw)

        try:
            expr = sp.sympify(processed)
        except Exception as e:
            self._show_error(f"解析错误: {e}")
            return

        # 提取参数（排除自变量和已知常量）
        syms = expr.free_symbols
        param_names = sorted(
            str(s) for s in syms
            if str(s) not in _INDEP_VARS and str(s) not in _KNOWN_IDS
        )

        # 通过
        self._error_label.hide()
        self._valid_expr = processed
        self._rebuild_sliders(param_names)
        self._update_hint(param_names)
        self.changed.emit()

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.show()
        self._valid_expr = ""
        self._clear_sliders()
        self._hint.setText("")

    # ── 参数滑块 ─────────────────────────────────────────────

    def _clear_sliders(self) -> None:
        for s, e in self._params.values():
            s.deleteLater(); e.deleteLater()
        self._params.clear()
        # 清除布局中的旧控件
        while self._slider_area.count():
            item = self._slider_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild_sliders(self, param_names: list[str]) -> None:
        self._clear_sliders()
        for name in param_names:
            row = QHBoxLayout(); row.setSpacing(4)

            lbl = QLabel(f"{name} =")
            lbl.setFixedWidth(24)
            lbl.setStyleSheet(_SLIDER_ROW_STYLE)
            row.addWidget(lbl)

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(-500, 500)
            slider.setValue(100)  # 默认 1.0
            row.addWidget(slider, 1)

            edit = QLineEdit("1.00")
            edit.setFixedWidth(48)
            edit.setStyleSheet(
                "QLineEdit{font-size:11px;padding:1px 3px;border:1px solid #d1d5db;border-radius:3px;}")
            row.addWidget(edit)

            slider.valueChanged.connect(
                lambda v, e=edit: self._on_slider_move(v, e))
            edit.editingFinished.connect(
                lambda s=slider, e=edit: self._on_edit_done(s, e))

            self._slider_area.addLayout(row)
            self._params[name] = (slider, edit)

    def _on_slider_move(self, value: int, edit: QLineEdit) -> None:
        if self._updating:
            return
        v = value / 100.0
        self._updating = True
        edit.setText(f"{v:.2f}")
        self._updating = False
        self.changed.emit()

    def _on_edit_done(self, slider: QSlider, edit: QLineEdit) -> None:
        if self._updating:
            return
        try:
            v = float(edit.text())
            v = max(-5.0, min(5.0, v))
            self._updating = True
            edit.setText(f"{v:.2f}")
            slider.setValue(int(round(v * 100)))
            self._updating = False
            self.changed.emit()
        except ValueError:
            edit.setText("0.00")

    def _update_hint(self, param_names: list[str]) -> None:
        parts = ["z = f(x, y, z)"]
        if param_names:
            parts.append(f"参数: {', '.join(param_names)}")
        self._hint.setText("  |  ".join(parts))


# ═══════════════════════════════════════════════════════════════════════
#  预处理
# ═══════════════════════════════════════════════════════════════════════

def _preprocess_3d(s: str) -> str:
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
