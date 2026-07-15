# -*- coding: utf-8 -*-
"""数学键盘 — 浮动、可拖拽、可缩放、6 分类符号输入。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QFont, QMouseEvent, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSizeGrip, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

# ── 符号定义 ──────────────────────────────────────────────

SYMBOLS: dict[str, list[list[str]]] = {
    "基础运算": [
        ["7", "8", "9", "/", "√"],
        ["4", "5", "6", "*", "^"],
        ["1", "2", "3", "-", "_"],
        ["0", ".", "=", "+", "|"],
        ["(", ")", "[", "]", "{", "}"],
        [",", ";", ":", "!", "?"],
    ],
    "微积分": [
        ["∫", "∮", "∬", "∭", "∂"],
        ["d/dx", "Δ", "∇", "lim", "∞"],
        ["∑", "∏", "dx", "dy", "dz"],
        ["sin", "cos", "tan", "log", "ln"],
        ["arcsin", "arccos", "arctan", "exp", "abs"],
    ],
    "线性代数": [
        ["det", "tr", "rank", "dim", "ker"],
        ["·", "×", "⊗", "⊕", "⊤"],
        ["∥v∥", "⟨v,w⟩", "⊥", "∥"],
        ["I_n", "0_{m×n}", "A⁻¹", "A^T", "A^*"],
    ],
    "希腊字母": [
        ["α", "β", "γ", "δ", "ε", "ζ"],
        ["η", "θ", "ι", "κ", "λ", "μ"],
        ["ν", "ξ", "ο", "π", "ρ", "σ"],
        ["τ", "υ", "φ", "χ", "ψ", "ω"],
        ["Γ", "Δ", "Θ", "Λ", "Ξ", "Π"],
        ["Σ", "Φ", "Ψ", "Ω", "∇", "∂"],
    ],
    "概率统计": [
        ["P(▢)", "E(▢)", "Var(▢)", "Cov(▢,▢)", "σ(▢)"],
        ["N(μ,σ²)", "Bin(n,p)", "Pois(λ)", "U(a,b)", "Exp(λ)"],
        ["~", "≈", "≤", "≥", "≠"],
        ["x̄", "ŷ", "p̂", "μ̂", "σ̂"],
        ["P(▢|▢)", "∫_{-∞}^{∞}", "Φ", "φ", "Z"],
    ],
    "常用模板": [
        ["\\frac{▢}{▢}", "\\sqrt[▢]{▢}", "∫▢^▢", "∑_{▢}^{▢}"],
        ["lim_{▢→▢}", "\\left(▢\\right)", "\\left[▢\\right]", "\\left\\{▢\\right\\}"],
        ["\\begin{pmatrix}▢\\end{pmatrix}", "\\begin{bmatrix}▢\\end{bmatrix}", "\\begin{vmatrix}▢\\end{vmatrix}"],
        ["e^{▢}", "\\ln(▢)", "▢^{▢}", "▢_{▢}"],
        ["|▢|", "∥▢∥", "⌊▢⌋", "⌈▢⌉"],
    ],
}

# ── 样式 ──────────────────────────────────────────────────

_LIGHT_QSS = """
    MathKeyboard {
        background: #f8fafc; border: 2px solid #cbd5e1; border-radius: 12px;
    }
    #kb_header {
        background: #f1f5f9; border-bottom: 1px solid #e2e8f0;
        border-top-left-radius: 10px; border-top-right-radius: 10px;
    }
    #kb_close {
        background: transparent; border: none; color: #94a3b8;
        font-size: 16px; font-weight: bold; padding: 0 4px;
    }
    #kb_close:hover { color: #ef4444; background: #fee2e2; border-radius: 4px; }
    QTabWidget::pane { border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; }
    QTabBar::tab {
        background: #f1f5f9; color: #475569; padding: 4px 10px;
        border: 1px solid #d1d5db; border-bottom: none;
        border-top-left-radius: 6px; border-top-right-radius: 6px;
        font-size: 11px; margin-right: 2px;
    }
    QTabBar::tab:selected { background: #fff; color: #0f172a; font-weight: 600; }
    QPushButton {
        background: #fff; color: #1e293b; border: 1px solid #e2e8f0;
        border-radius: 5px; font-size: 13px;
    }
    QPushButton:hover { background: #dbeafe; border-color: #3b82f6; }
    QPushButton:pressed { background: #bfdbfe; }
"""

_DARK_QSS = """
    MathKeyboard {
        background: #1e1e2e; border: 2px solid #45475a; border-radius: 12px;
    }
    #kb_header {
        background: #252540; border-bottom: 1px solid #313244;
        border-top-left-radius: 10px; border-top-right-radius: 10px;
    }
    #kb_close {
        background: transparent; border: none; color: #6c7086;
        font-size: 16px; font-weight: bold; padding: 0 4px;
    }
    #kb_close:hover { color: #ef4444; background: #3b1c1c; border-radius: 4px; }
    QTabWidget::pane { border: 1px solid #313244; background: #252540; border-radius: 6px; }
    QTabBar::tab {
        background: #313244; color: #94a3b8; padding: 4px 10px;
        border: 1px solid #45475a; border-bottom: none;
        border-top-left-radius: 6px; border-top-right-radius: 6px;
        font-size: 11px; margin-right: 2px;
    }
    QTabBar::tab:selected { background: #252540; color: #cdd6f4; font-weight: 600; }
    QPushButton {
        background: #313244; color: #cdd6f4; border: 1px solid #45475a;
        border-radius: 5px; font-size: 13px;
    }
    QPushButton:hover { background: #3b3b5c; border-color: #89b4fa; }
    QPushButton:pressed { background: #45475a; }
"""


# ═══════════════════════════════════════════════════════════════
#  MathKeyboard
# ═══════════════════════════════════════════════════════════════

class MathKeyboard(QWidget):
    """浮动数学键盘 — 非模态、可拖拽、可缩放。

    信号:
        closed — 键盘被关闭
    """

    closed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("MathKeyboard")
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("数学键盘")
        self.setMinimumSize(280, 220)

        self._dark = False
        self._drag_pos: QPoint | None = None
        self._last_focus: QWidget | None = None

        # 布局
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(4, 0, 4, 0)

        # ── 标题栏 ──
        hdr = QHBoxLayout()
        hdr.setContentsMargins(8, 6, 4, 4)
        title_lbl = QLabel("数学键盘")
        title_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #475569; background: transparent;")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        close_btn = QPushButton("×")
        close_btn.setObjectName("kb_close")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        hdr.addWidget(close_btn)

        # 标题栏容器（用于 QSS 样式）
        hdr_widget = QWidget()
        hdr_widget.setObjectName("kb_header")
        hdr_widget.setLayout(hdr)
        root.addWidget(hdr_widget)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._build_tabs()
        root.addWidget(self._tabs, 1)

        # 缩放手柄
        grip = QSizeGrip(self)
        grip.setFixedSize(14, 14)
        grip.setStyleSheet("background: transparent;")
        root.addWidget(grip, 0, Qt.AlignmentFlag.AlignRight)

        # 关闭快捷键
        QShortcut(QKeySequence("Esc"), self, self.close)

        # 恢复上次位置/大小/标签
        self.resize(getattr(MathKeyboard, '_saved_size', QSize(420, 300)))
        if hasattr(MathKeyboard, '_saved_pos'):
            self.move(MathKeyboard._saved_pos)
        if hasattr(MathKeyboard, '_saved_tab'):
            self._tabs.setCurrentIndex(MathKeyboard._saved_tab)

        self._apply_theme()
        self._track_focus()

    # ── 构建标签页 ────────────────────────────────────────

    def _build_tabs(self):
        for category, rows in SYMBOLS.items():
            page = QWidget()
            grid = QGridLayout(page)
            grid.setSpacing(3)
            grid.setContentsMargins(6, 6, 6, 6)

            for r, row in enumerate(rows):
                for c, sym in enumerate(row):
                    btn = QPushButton(sym)
                    btn.setSizePolicy(
                        btn.sizePolicy().horizontalPolicy(),
                        btn.sizePolicy().verticalPolicy())
                    btn.setMinimumHeight(28)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.clicked.connect(lambda _, s=sym: self._insert(s))
                    grid.addWidget(btn, r, c)

            # 均匀拉伸
            for c in range(max(len(r) for r in rows)):
                grid.setColumnStretch(c, 1)
            for r in range(len(rows)):
                grid.setRowStretch(r, 1)

            self._tabs.addTab(page, category)

    # ── 符号插入 ──────────────────────────────────────────

    def _insert(self, symbol: str) -> None:
        """将符号插入当前焦点输入框。"""
        widget = self._find_target()
        if widget is None:
            return

        # 模板符号（含 ▢) → 用占位符处理
        if "▢" in symbol:
            text = symbol.replace("▢", "")
            if isinstance(widget, (QLineEdit,)):
                widget.insert(text)
            elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
                cursor = widget.textCursor()
                cursor.insertText(text)
            return

        # 普通符号
        if isinstance(widget, (QLineEdit,)):
            widget.insert(symbol)
        elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
            cursor = widget.textCursor()
            cursor.insertText(symbol)

    def _find_target(self) -> QWidget | None:
        """找到当前焦点输入框。"""
        # 1. 当前焦点控件
        focus = QApplication.focusWidget()
        if self._is_input(focus):
            self._last_focus = focus
            return focus
        # 2. 上一个焦点控件（可能失焦到键盘按钮）
        if self._last_focus and self._is_input(self._last_focus):
            return self._last_focus
        # 3. 递归查找主窗口中的活动 calc block
        return self._find_active_input()

    def _find_active_input(self) -> QWidget | None:
        """在主窗口中找到当前激活的 CalcBlock 输入框。"""
        try:
            parent = self.parent()
            # 上溯到 MainWindow
            while parent and not hasattr(parent, '_stacked_widget'):
                parent = parent.parent()
            if parent is None:
                return None
            sw = getattr(parent, '_stacked_widget', None)
            if sw is None:
                return None
            w = sw.currentWidget()
            if w is None:
                return None

            def find_block(widget):
                if hasattr(widget, 'input_box') and isinstance(widget.input_box, QLineEdit):
                    return widget.input_box
                for child in getattr(widget, 'children', lambda: [])():
                    r = find_block(child)
                    if r:
                        return r
                return None
            return find_block(w)
        except Exception:
            return None

    @staticmethod
    def _is_input(w: QWidget | None) -> bool:
        if w is None:
            return False
        return isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit))

    # ── 焦点追踪 ──────────────────────────────────────────

    def _track_focus(self):
        """监听焦点变化，记住最后一个输入框。"""
        try:
            QApplication.instance().focusChanged.connect(self._on_focus_changed)
        except Exception:
            pass

    def _on_focus_changed(self, _old, new):
        if self._is_input(new):
            self._last_focus = new

    # ── 拖拽 ──────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move((event.globalPosition().toPoint() - self._drag_pos))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    # ── 关闭 ──────────────────────────────────────────────

    def closeEvent(self, event):
        # 存位置/大小/标签
        MathKeyboard._saved_pos = self.pos()
        MathKeyboard._saved_size = self.size()
        MathKeyboard._saved_tab = self._tabs.currentIndex()
        self.closed.emit()
        super().closeEvent(event)

    # ── 主题 ──────────────────────────────────────────────

    def set_dark_theme(self, dark: bool):
        self._dark = dark
        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(_DARK_QSS if self._dark else _LIGHT_QSS)
