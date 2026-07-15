"""Desmos 风格数学输入框控件 — 实时预览、括号匹配、自动补全。"""

from PySide6.QtCore import Qt, Signal, QRect, QEvent
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QLabel,
    QListWidget, QListWidgetItem,
)

import sympy as sp

# 自动补全候选函数/常量
AUTOCOMPLETE_CANDIDATES = [
    "sin", "cos", "tan",
    "asin", "acos", "atan",
    "sinh", "cosh", "tanh",
    "log", "ln", "sqrt", "exp",
    "limit", "diff", "integrate", "solve",
    "pi", "E",
    "abs", "floor", "ceil",
]


class MathInput(QWidget):
    """数学表达式输入控件 — 输入区 + 实时预览 + 自动补全。"""

    expressionChanged = Signal(str)   # 文本变化
    executeRequested = Signal()       # Ctrl+Enter 请求执行

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("math_input_widget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # ---- 输入区 ----
        self._input = QPlainTextEdit()
        self._input.setObjectName("math_input_text")
        self._input.setPlaceholderText("输入表达式，如 x^2 + 2*x + 1")
        self._input.textChanged.connect(self._on_text_changed)
        self._input.installEventFilter(self)

        font = QFont("Consolas", 13)
        self._input.setFont(font)

        layout.addWidget(self._input, stretch=1)

        # ---- 预览区 ----
        self._preview = QLabel("")
        self._preview.setObjectName("math_input_preview")
        self._preview.setMinimumHeight(24)
        self._preview.setWordWrap(True)
        layout.addWidget(self._preview)

        # ---- 自动补全弹窗 ----
        self._popup = QListWidget()
        self._popup.setObjectName("math_autocomplete")
        self._popup.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self._popup.setMaximumHeight(180)
        self._popup.setFocusPolicy(Qt.NoFocus)
        self._popup.hide()
        self._popup.itemClicked.connect(self._on_autocomplete_select)

        self._popup_timer_id = None  # placeholder

    # ================================================================
    #  事件过滤 — 处理快捷键、括号匹配、自动补全导航
    # ================================================================
    def eventFilter(self, obj, event):
        if obj is not self._input:
            return False

        # Ctrl+Enter
        if (event.type() == QEvent.ShortcutOverride and
                event.key() == Qt.Key_Return and
                event.modifiers() == Qt.ControlModifier):
            self.executeRequested.emit()
            return True

        if event.type() == QEvent.KeyPress:
            return self._handle_keypress(event)

        return False

    def _handle_keypress(self, event) -> bool:
        """返回 True 表示事件已被消费。"""
        key = event.key()

        # ----- 自动补全弹窗导航 -----
        if self._popup.isVisible():
            if key in (Qt.Key_Tab, Qt.Key_Enter, Qt.Key_Return):
                row = self._popup.currentRow()
                if row >= 0:
                    self._on_autocomplete_select(self._popup.item(row))
                return True
            if key == Qt.Key_Escape:
                self._popup.hide()
                return True
            if key == Qt.Key_Down:
                row = self._popup.currentRow()
                if row < self._popup.count() - 1:
                    self._popup.setCurrentRow(row + 1)
                return True
            if key == Qt.Key_Up:
                row = self._popup.currentRow()
                if row > 0:
                    self._popup.setCurrentRow(row - 1)
                return True

        # ----- 括号自动配对 -----
        if event.text() == "(":
            cursor = self._input.textCursor()
            cursor.insertText("()")
            cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1)
            self._input.setTextCursor(cursor)
            return True

        # ----- 跳过已有右括号 -----
        if event.text() == ")":
            cursor = self._input.textCursor()
            text = self._input.toPlainText()
            pos = cursor.position()
            if pos < len(text) and text[pos] == ")":
                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, 1)
                self._input.setTextCursor(cursor)
                return True

        return False

    # ================================================================
    #  文本变化 → 预览 + 自动补全
    # ================================================================
    def _on_text_changed(self):
        text = self._input.toPlainText()
        self.expressionChanged.emit(text)
        self._update_preview(text)
        self._update_autocomplete()

    def _update_preview(self, text: str):
        if not text.strip():
            self._preview.setText("")
            return
        try:
            expr = sp.sympify(text)
            latex = sp.latex(expr)
            self._preview.setText(f"$${latex}$$")
        except Exception:
            self._preview.setText("正在输入...")

    def _update_autocomplete(self):
        cursor = self._input.textCursor()
        pos = cursor.position()
        text = self._input.toPlainText()

        # 从光标位置向左扫描字母/数字，找到当前单词起点
        i = pos - 1
        while i >= 0 and (text[i].isalpha() or text[i].isdigit()):
            i -= 1
        i += 1
        word = text[i:pos] if i < pos else ""

        if len(word) < 1:
            self._popup.hide()
            return

        candidates = [c for c in AUTOCOMPLETE_CANDIDATES
                      if c.startswith(word.lower()) or c.startswith(word)]
        if not candidates:
            self._popup.hide()
            return

        self._popup.clear()
        for c in candidates:
            item = QListWidgetItem(c)
            item.setData(Qt.UserRole, (i, word))
            self._popup.addItem(item)
        self._popup.setCurrentRow(0)

        # 定位到光标下方
        rect = self._input.cursorRect()
        global_pos = self._input.mapToGlobal(rect.bottomLeft())
        self._popup.move(global_pos)
        self._popup.setFixedWidth(160)
        self._popup.show()

    def _on_autocomplete_select(self, item):
        data = item.data(Qt.UserRole)
        if data is None:
            return
        start_idx, word = data
        full = item.text()

        cursor = self._input.textCursor()
        # 选中从 start_idx 到当前位置的单词
        cursor.setPosition(start_idx)
        cursor.setPosition(cursor.position() + len(word), QTextCursor.KeepAnchor)
        cursor.insertText(full)
        self._popup.hide()
        self._input.setFocus()

    # ================================================================
    #  公开接口
    # ================================================================
    def set_expression(self, expr: str):
        """以编程方式设置表达式文本。"""
        self._input.setPlainText(expr)

    def get_expression(self) -> str:
        """返回当前输入文本。"""
        return self._input.toPlainText()

    def clear(self):
        """清空输入和预览。"""
        self._input.clear()
        self._preview.setText("")

    def set_placeholder(self, text: str):
        """设置占位文本。"""
        self._input.setPlaceholderText(text)

    def setFocus(self):
        """将焦点交给输入框。"""
        self._input.setFocus()
