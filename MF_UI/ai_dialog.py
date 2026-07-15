# -*- coding: utf-8 -*-
"""AI 对话对话框 — 连接 MF_AI 模块，支持流式输出。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from MF_AI import chat, stream_chat, set_api_key, get_config
from MF_AI.exceptions import AIConfigError, AIError


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
"""


# ── Worker 线程 ───────────────────────────────────────────

class _AIStreamWorker(QThread):
    """在后台线程中运行 MF_AI.stream_chat，通过信号逐块输出。"""
    chunk_ready = Signal(str)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, messages: list[dict], parent=None):
        super().__init__(parent)
        self._messages = messages

    def run(self) -> None:
        try:
            for chunk in stream_chat(self._messages):
                self.chunk_ready.emit(chunk)
            self.finished.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))


# ── 对话框 ────────────────────────────────────────────────

class AIDialog(QDialog):
    """AI 助手对话框。

    用法:
        dlg = AIDialog(self)
        dlg.exec()
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("AI 数学助手")
        self.resize(600, 500)
        self.setMinimumSize(400, 350)
        self.setStyleSheet(_DIALOG_STYLE)

        # ── 对话历史 ──
        self._messages: list[dict] = []
        self._setup_system_prompt()

        # ── UI ──
        self._build_ui()

        # ── Worker ──
        self._worker: _AIStreamWorker | None = None

    def _setup_system_prompt(self) -> None:
        """设置数学助手系统提示词。"""
        cfg = get_config()
        if not cfg.system_prompt:
            cfg.set_system_prompt(
                "你是一个专业的数学助手，名为 MF-Mathematics AI。"
                "你可以帮助用户解决数学问题、解释数学概念、推导公式、"
                "分析数据、以及提供学习建议。请用中文回答，"
                "数学公式使用 LaTeX 格式（用 $...$ 或 $$...$$ 包裹）。"
            )
        self._messages = [{"role": "system", "content": cfg.system_prompt}]

    # ── UI 构建 ────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # 标题
        hdr = QHBoxLayout()
        title = QLabel("AI 数学助手")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #0f172a; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        self._status_lbl = QLabel("就绪")
        self._status_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        hdr.addWidget(self._status_lbl)
        root.addLayout(hdr)

        # 聊天历史区域
        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        font = QFont("Microsoft YaHei", 10)
        self._chat_view.setFont(font)
        root.addWidget(self._chat_view, 1)

        # 输入区域
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入数学问题…")
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("发送")
        self._send_btn.setStyleSheet(
            "QPushButton { background: #3b82f6; color: #fff; border: none;"
            " border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { background: #2563eb; }"
            "QPushButton:disabled { background: #94a3b8; }")
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._send)
        input_row.addWidget(self._send_btn)

        root.addLayout(input_row)

        # 底部按钮
        bottom = QHBoxLayout()
        bottom.addStretch()
        clear_btn = QPushButton("清空对话")
        clear_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #94a3b8; border: none;"
            " font-size: 11px; } QPushButton:hover { color: #ef4444; }")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear)
        bottom.addWidget(clear_btn)
        root.addLayout(bottom)

    # ── 发送 ───────────────────────────────────────────────

    def _send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        if self._worker and self._worker.isRunning():
            return  # 等待上一轮完成

        # 检查 API Key
        cfg = get_config()
        try:
            cfg.validate()
        except AIConfigError:
            self._prompt_api_key()
            try:
                cfg.validate()
            except AIConfigError:
                self._append_system("请先设置 API Key 后再发送消息。")
                return

        self._input.clear()
        self._set_sending(True)

        # 显示用户消息
        self._append_user(text)
        self._messages.append({"role": "user", "content": text})

        # 启动流式请求
        self._worker = _AIStreamWorker(list(self._messages), self)
        self._worker.chunk_ready.connect(self._on_chunk)
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_chunk(self, text: str) -> None:
        """收到增量文本。"""
        cursor = self._chat_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._chat_view.setTextCursor(cursor)
        self._chat_view.ensureCursorVisible()

    def _on_finished(self) -> None:
        """流式输出完成。"""
        # 获取完整 AI 回复
        full = self._chat_view.toPlainText()
        # 找到最后一个 "AI: " 后的内容
        last_ai = full.rfind("\nAI: ")
        if last_ai >= 0:
            ai_content = full[last_ai + 5:]
        else:
            ai_content = full
        self._messages.append({"role": "assistant", "content": ai_content.strip()})
        self._set_sending(False)

    def _on_error(self, msg: str) -> None:
        self._append_system(f"错误: {msg}")
        self._set_sending(False)

    # ── UI 辅助 ────────────────────────────────────────────

    def _set_sending(self, sending: bool) -> None:
        self._input.setEnabled(not sending)
        self._send_btn.setEnabled(not sending)
        if sending:
            self._status_lbl.setText("思考中…")
            self._status_lbl.setStyleSheet("font-size: 11px; color: #3b82f6; background: transparent;")
            self._append_system("")  # 插入空行
            cursor = self._chat_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml('<span style="color:#3b82f6;">AI: </span>')
        else:
            self._status_lbl.setText("就绪")
            self._status_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
            self._chat_view.append("")

    def _append_user(self, text: str) -> None:
        self._chat_view.append(f"")
        cursor = self._chat_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(
            f'<div style="margin:4px 0;">'
            f'<b style="color:#0f172a;">你:</b> '
            f'<span style="color:#334155;">{text}</span></div>')

    def _append_system(self, text: str) -> None:
        if text:
            self._chat_view.append(f"")
            cursor = self._chat_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml(
                f'<span style="color:#94a3b8;font-style:italic;">{text}</span>')

    def _clear(self) -> None:
        self._setup_system_prompt()
        self._chat_view.clear()
        self._status_lbl.setText("对话已清空")
        self._status_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")

    def _prompt_api_key(self) -> None:
        """弹出 API Key 输入框。"""
        from PySide6.QtWidgets import QInputDialog
        key, ok = QInputDialog.getText(
            self, "API Key", "请输入 DeepSeek / OpenAI API Key:",
            QLineEdit.EchoMode.Password)
        if ok and key.strip():
            set_api_key(key.strip())
