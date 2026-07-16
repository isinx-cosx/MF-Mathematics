# -*- coding: utf-8 -*-
"""KeyboardPanel — 内置虚拟键盘面板，嵌入主窗口底部左下角。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QGridLayout, QLineEdit, QPushButton,
    QSizePolicy, QTabWidget, QVBoxLayout, QWidget,
)

# ── 6 分类符号定义 ────────────────────────────────────────────

SYMBOLS: dict[str, list[list[str]]] = {
    "基础运算": [
        ["7", "8", "9", "/", "√"],
        ["4", "5", "6", "*", "^"],
        ["1", "2", "3", "-", "_"],
        ["0", ".", "=", "+", "|x|"],
        ["(", ")", "[", "]", "{", "}"],
    ],
    "微积分": [
        ["∫", "∬", "∂", "∇", "lim"],
        ["d/dx", "∞", "Δ", "∑", "∏"],
        ["sin", "cos", "tan", "log", "ln"],
        ["arcsin", "arccos", "arctan", "exp", "abs"],
    ],
    "线性代数": [
        ["det", "tr", "rank", "·", "×"],
        ["∥v∥", "⟨u,v⟩", "⊥", "A⁻¹", "Aᵀ"],
        ["I_n", "0_{m×n}", "⊕", "⊗", "⊤"],
    ],
    "希腊字母": [
        ["α", "β", "γ", "δ", "ε", "ζ"],
        ["η", "θ", "ι", "κ", "λ", "μ"],
        ["ν", "ξ", "ο", "π", "ρ", "σ"],
        ["τ", "υ", "φ", "χ", "ψ", "ω"],
        ["Γ", "Δ", "Θ", "Λ", "Ξ", "Π"],
        ["Σ", "Φ", "Ψ", "Ω"],
    ],
    "概率统计": [
        ["P(A)", "E(X)", "Var(X)", "σ(X)", "Cov"],
        ["N(μ,σ²)", "Bin(n,p)", "Pois(λ)", "Exp(λ)", "U(a,b)"],
        ["≤", "≥", "≠", "≈", "±"],
        ["x̄", "ŷ", "p̂", "μ̂", "σ̂"],
    ],
    "常用模板": [
        ["\\frac{▢}{▢}", "\\sqrt[▢]{▢}", "e^{▢}", "▢^{▢}", "▢_{▢}"],
        ["∫_{▢}^{▢}", "∑_{▢}^{▢}", "lim_{▢→▢}"],
        ["\\begin{pmatrix}", "\\begin{bmatrix}", "\\begin{vmatrix}"],
    ],
}

# 键盘样式已迁移到 light.qss / dark.qss（KeyboardPanel, #kb_btn 选择器）


# ═══════════════════════════════════════════════════════════════
#  KeyboardPanel
# ═══════════════════════════════════════════════════════════════

class KeyboardPanel(QWidget):
    """底部虚拟键盘面板 — 6 分类标签页，左下角对齐。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("KeyboardPanel")
        self.setVisible(False)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 2, 4, 2)
        root.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._build_tabs()
        root.addWidget(self._tabs)

    def _build_tabs(self) -> None:
        for category, rows in SYMBOLS.items():
            page = QWidget()
            grid = QGridLayout(page)
            grid.setSpacing(3)
            grid.setContentsMargins(4, 4, 4, 4)

            for r, row in enumerate(rows):
                for c, sym in enumerate(row):
                    btn = QPushButton(sym)
                    btn.setObjectName("kb_btn")
                    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    btn.setMinimumHeight(24)
                    btn.setSizePolicy(
                        QSizePolicy.Policy.Expanding,
                        QSizePolicy.Policy.Expanding)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.clicked.connect(lambda _, s=sym: self._on_key_clicked(s))
                    grid.addWidget(btn, r, c)

            for c in range(max(len(r) for r in rows)):
                grid.setColumnStretch(c, 1)
            for r in range(len(rows)):
                grid.setRowStretch(r, 1)

            self._tabs.addTab(page, category)

    @staticmethod
    def _on_key_clicked(char: str) -> None:
        """仅当焦点在 QLineEdit 时插入字符，否则静默忽略。"""
        focused = QApplication.focusWidget()
        if focused is not None and isinstance(focused, QLineEdit):
            text = char.replace("▢", "")
            focused.insert(text)
