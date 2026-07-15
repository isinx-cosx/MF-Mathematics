# -*- coding: utf-8 -*-
"""AI 对话框 — 三种模式（补全/解释/诊断），上下文感知，结果插入。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from MF_AI import stream_chat, chat, get_config
from MF_AI.exceptions import AIError, AIConfigError

# ── 系统提示词 ────────────────────────────────────────────

SYSTEM_PROMPTS = {
    "补全": (
        "你是数学表达式自动补全助手。用户会给出一个不完整的数学表达式，"
        "请根据常见的数学函数和表达式模式，将其补全为合法、完整的表达式。"
        "只返回补全后的表达式，不要任何额外解释。"
        "如果输入是'求x'或'计算x'这类，补全为常见的表达式如 sin(x)、x^2+1 等。"
    ),
    "解释": (
        "你是数学计算步骤解释助手。用户会给出一个数学表达式或计算任务，"
        "请用中文分步解释计算过程。每一步标注【步骤 N】。"
        "适当使用 LaTeX 公式（$...$ 行内，$$...$$ 独立行）。"
        "最后给出最终答案。"
    ),
    "诊断": (
        "你是数学表达式错误诊断助手。分析用户提供的表达式或报错信息，"
        "指出错误原因并给出修复建议。返回格式：\n"
        "错误原因：...\n修复建议：...\n修正后表达式：..."
    ),
}

MODE_LABELS = ["补全", "解释", "诊断"]

# ── 样式 ──────────────────────────────────────────────────

_DIALOG_STYLE = """
    QDialog { background: #f8fafc; }
    QTextEdit {
        border: 1px solid #e2e8f0; border-radius: 8px;
        background: #fff; font-size: 13px; padding: 8px;
    }
    QLineEdit {
        border: 1px solid #d1d5db; border-radius: 6px;
        padding: 8px 12px; font-size: 13px; background: #fff;
    }
    QLineEdit:focus { border-color: #3b82f6; }
    QComboBox {
        border: 1px solid #d1d5db; border-radius: 4px;
        padding: 4px 8px; font-size: 12px; background: #fff;
    }
"""

_BTN_PRIMARY = """
    QPushButton { background: #3b82f6; color: #fff; border: none;
    border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }
    QPushButton:hover { background: #2563eb; }
    QPushButton:disabled { background: #94a3b8; }
"""
_BTN_SUCCESS = """
    QPushButton { background: #10b981; color: #fff; border: none;
    border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: 500; }
    QPushButton:hover { background: #059669; }
"""


# ── Worker ────────────────────────────────────────────────

class _AIStreamWorker(QThread):
    chunk_ready = Signal(str)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, messages: list[dict], parent=None):
        super().__init__(parent)
        self._messages = messages

    def run(self):
        try:
            for chunk in stream_chat(self._messages):
                self.chunk_ready.emit(chunk)
            self.finished.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))


# ═══════════════════════════════════════════════════════════════
#  AIDialog
# ═══════════════════════════════════════════════════════════════

class AIDialog(QDialog):
    """AI 助手对话框 — 三种模式，上下文感知，流式输出。"""

    def __init__(self, parent: QWidget | None = None,
                 context_expr: str = "", context_mode: str = ""):
        super().__init__(parent)
        self.setWindowTitle("AI 数学助手")
        self.resize(620, 520)
        self.setMinimumSize(450, 380)
        self.setStyleSheet(_DIALOG_STYLE)

        self._context_expr = context_expr
        self._context_mode = context_mode
        self._messages: list[dict] = []
        self._worker: _AIStreamWorker | None = None
        self._last_full_response = ""

        self._build_ui()
        self._update_input_placeholder()

    # ── UI ────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # 标题行
        hdr = QHBoxLayout()
        title = QLabel("AI 数学助手")
        title.setStyleSheet(
            "font-size: 16px; font-weight: 600; color: #0f172a; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(MODE_LABELS)
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        hdr.addWidget(QLabel("模式:"))
        hdr.addWidget(self._mode_combo)

        self._status_lbl = QLabel("就绪")
        self._status_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        hdr.addWidget(self._status_lbl)
        root.addLayout(hdr)

        # 上下文提示
        if self._context_expr:
            ctx = QLabel(f"当前表达式: {self._context_expr}")
            ctx.setStyleSheet("font-size: 11px; color: #6366f1; background: #eef2ff;"
                              " padding: 4px 8px; border-radius: 4px;")
            root.addWidget(ctx)

        # 输出区域
        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        self._chat_view.setFont(QFont("Microsoft YaHei", 10))
        root.addWidget(self._chat_view, 1)

        # 输入区域
        input_row = QHBoxLayout(); input_row.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入数学问题…")
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("发送")
        self._send_btn.setStyleSheet(_BTN_PRIMARY)
        self._send_btn.clicked.connect(self._send)
        input_row.addWidget(self._send_btn)
        root.addLayout(input_row)

        # 操作按钮行
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        self._insert_btn = QPushButton("插入结果")
        self._insert_btn.setStyleSheet(_BTN_SUCCESS)
        self._insert_btn.clicked.connect(self._insert_result)
        btn_row.addWidget(self._insert_btn)

        self._copy_btn = QPushButton("复制")
        self._copy_btn.setStyleSheet(
            "QPushButton { background: #f1f5f9; color: #475569; border: 1px solid #d1d5db;"
            " border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
            "QPushButton:hover { background: #e2e8f0; }")
        self._copy_btn.clicked.connect(self._copy_result)
        btn_row.addWidget(self._copy_btn)

        btn_row.addStretch()

        self._clear_btn = QPushButton("清空对话")
        self._clear_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #94a3b8; border: none;"
            " font-size: 11px; } QPushButton:hover { color: #ef4444; }")
        self._clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(self._clear_btn)
        root.addLayout(btn_row)

    # ── 输入预设 ──────────────────────────────────────────

    def _update_input_placeholder(self):
        mode = self._mode_combo.currentText()
        if self._context_expr:
            if mode == "补全":
                self._input.setText(self._context_expr)
                self._input.setPlaceholderText("补全表达式…")
            elif mode == "解释":
                self._input.setPlaceholderText(f"解释计算步骤: {self._context_expr}")
            elif mode == "诊断":
                self._input.setPlaceholderText(f"诊断错误: {self._context_expr}")

    def _on_mode_changed(self, _mode: str):
        self._update_input_placeholder()

    # ── 发送 ──────────────────────────────────────────────

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        if self._worker and self._worker.isRunning():
            return

        # 检查配置
        cfg = get_config()
        if not cfg.is_available():
            self._append_system("AI 服务未配置。请在 设置 → AI 配置 中设置 API Key。")
            return

        mode = self._mode_combo.currentText()
        system_prompt = SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["解释"])

        # 构建消息
        self._messages = [{"role": "system", "content": system_prompt}]
        if self._context_expr and self._context_mode:
            self._messages.append({
                "role": "user",
                "content": f"表达式: {self._context_expr}\n操作: {self._context_mode}\n\n{text}"
            })
        else:
            self._messages.append({"role": "user", "content": text})

        self._input.clear()
        self._set_sending(True)

        # 显示用户消息
        self._append_user(text)
        self._last_full_response = ""

        # 流式请求
        self._worker = _AIStreamWorker(list(self._messages), self)
        self._worker.chunk_ready.connect(self._on_chunk)
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_chunk(self, text: str):
        self._last_full_response += text
        cursor = self._chat_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._chat_view.setTextCursor(cursor)
        self._chat_view.ensureCursorVisible()

    def _on_finished(self):
        self._messages.append({"role": "assistant", "content": self._last_full_response})
        self._chat_view.append("")
        self._set_sending(False)

    def _on_error(self, msg: str):
        self._append_system(f"错误: {msg}")
        self._set_sending(False)

    # ── 结果操作 ──────────────────────────────────────────

    def _insert_result(self):
        """将结果插入到当前计算块的输入框。"""
        if not self._last_full_response:
            return
        # 尝试找到父窗口中的当前计算块
        result = self._last_full_response.strip()
        if self._mode_combo.currentText() == "补全":
            # 提取第一行作为表达式
            lines = result.split("\n")
            result = lines[0].strip()

        parent = self.parent()
        if parent:
            self._try_insert_to_parent(parent, result)
        self.status_lbl_text("结果已插入")

    def _try_insert_to_parent(self, parent, result: str):
        """递归查找 MainWindow → 当前 calc block → input box。"""
        try:
            main_win = parent
            # 上溯到 MainWindow
            while main_win and not hasattr(main_win, '_stacked_widget'):
                main_win = main_win.parent()
            if main_win and hasattr(main_win, '_stacked_widget'):
                sw = main_win._stacked_widget
                w = sw.currentWidget()
                if w:
                    self._insert_to_workspace(w, result)
        except Exception:
            pass

    def _insert_to_workspace(self, workspace, result: str):
        """向 workspace 中的当前 calc block 插入文本。"""
        try:
            # 查找 CalcBlock
            def find_block(widget):
                if hasattr(widget, 'input_box'):
                    return widget
                if hasattr(widget, 'children'):
                    for child in widget.children():
                        r = find_block(child)
                        if r:
                            return r
                return None
            block = find_block(workspace)
            if block and hasattr(block, 'input_box'):
                block.input_box.setText(result)
        except Exception:
            pass

    def _copy_result(self):
        if self._last_full_response:
            QApplication.clipboard().setText(self._last_full_response)
            self.status_lbl_text("已复制到剪贴板")

    # ── UI 辅助 ────────────────────────────────────────────

    def _set_sending(self, sending: bool):
        self._input.setEnabled(not sending)
        self._send_btn.setEnabled(not sending)
        if sending:
            self._status_lbl.setText("思考中…")
            self._status_lbl.setStyleSheet(
                "font-size: 11px; color: #3b82f6; background: transparent;")
            self._append_system("")
            cursor = self._chat_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml('<span style="color:#3b82f6;">AI: </span>')
        else:
            self._status_lbl.setText("就绪")
            self._status_lbl.setStyleSheet(
                "font-size: 11px; color: #94a3b8; background: transparent;")

    def _append_user(self, text: str):
        cursor = self._chat_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(
            f'<div style="margin:4px 0;">'
            f'<b style="color:#0f172a;">你:</b> '
            f'<span style="color:#334155;">{text}</span></div>')

    def _append_system(self, text: str):
        if text:
            cursor = self._chat_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml(
                f'<span style="color:#94a3b8;font-style:italic;">{text}</span>')

    def _clear(self):
        self._messages.clear()
        self._chat_view.clear()
        self._last_full_response = ""
        self._update_input_placeholder()
        self.status_lbl_text("对话已清空")

    def status_lbl_text(self, text: str):
        self._status_lbl.setText(text)
