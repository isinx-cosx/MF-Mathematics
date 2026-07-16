# -*- coding: utf-8 -*-
"""AI 对话框 — 数学助手对话，流式输出。"""

from __future__ import annotations

from PySide6.QtCore import Signal, QThread
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

import base64
import re
from io import BytesIO

from MF_AI import stream_chat, get_config

# ── LaTeX 渲染 ─────────────────────────────────────────────

def _strip_boxed(s: str) -> str:
    """移除 \\boxed{...} 包装（mathtext 不支持）。"""
    prefix = '\\boxed{'
    if not s.startswith(prefix) or not s.endswith('}'):
        return s
    # 手动配对括号
    depth = 0
    for i, ch in enumerate(s[len(prefix):], len(prefix)):
        if ch == '{':
            depth += 1
        elif ch == '}':
            if depth == 0:
                return s[len(prefix):i]
            depth -= 1
    return s  # 括号不匹配，保持原样


def _fix_latex(latex: str) -> str:
    """将不兼容 mathtext 的 LaTeX 命令转换为兼容形式。"""
    s = latex.strip()
    # \boxed{content} → content
    s = _strip_boxed(s)
    # matrix 环境 → 纯文本 + 括号（mathtext 不支持 \begin{array}）
    s = re.sub(r'\\begin\{pmatrix\}', '(', s)
    s = re.sub(r'\\end\{pmatrix\}', ')', s)
    s = re.sub(r'\\begin\{bmatrix\}', '[', s)
    s = re.sub(r'\\end\{bmatrix\}', ']', s)
    s = re.sub(r'\\begin\{vmatrix\}', '|', s)
    s = re.sub(r'\\end\{vmatrix\}', '|', s)
    # cases → 条件表达式用逗号分隔
    s = re.sub(r'\\begin\{cases\}', '', s)
    s = re.sub(r'\\end\{cases\}', '', s)
    return s


def _latex_to_html(latex: str, dark: bool = False) -> str:
    """将 LaTeX 渲染为 base64 图片并返回 <img> 标签。"""
    try:
        import matplotlib as _mpl
        _mpl.use("agg")
        _mpl.rcParams["mathtext.fontset"] = "cm"
        import matplotlib.pyplot as _plt

        face = "#1e293b" if dark else "#fafbfc"
        text_color = "#e2e8f0" if dark else "#0f172a"
        safe = _fix_latex(latex)
        # 使用原始字符串构造 mathtext
        math_text = "$" + safe + "$"

        # 估算宽度（缩小尺寸，适合聊天界面）
        w = max(len(safe) * 0.09 + 0.5, 1.2)
        fig = _plt.figure(figsize=(w, 0.45), dpi=120, facecolor=face)
        fig.text(0.5, 0.5, math_text,
                 fontsize=13, va="center", ha="center", color=text_color)
        fig.canvas.draw()

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                    pad_inches=0.08, transparent=False, facecolor=face)
        _plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" style="vertical-align:middle;">'
    except Exception:
        return f"<i>{latex}</i>"


def _render_response(text: str) -> str:
    """将文本中的 LaTeX 渲染为 HTML。

    $$...$$ → 块级公式（居中）
    $...$   → 行内公式
    其他     → 原样，换行转 <br>
    """
    # 1. 转义 HTML
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 2. 处理 $$...$$ 块级公式
    def _replace_block(m):
        formula = m.group(1).strip()
        img = _latex_to_html(formula)
        return f'<div align="center">{img}</div>'
    text = re.sub(r'\$\$(.+?)\$\$', _replace_block, text, flags=re.DOTALL)

    # 3. 处理 $...$ 行内公式
    def _replace_inline(m):
        formula = m.group(1).strip()
        return _latex_to_html(formula)
    text = re.sub(r'\$(.+?)\$', _replace_inline, text)

    # 4. 换行
    text = text.replace("\n", "<br>")

    return text


_SYSTEM_PROMPT = (
    "你是 MF-Mathematics 的 AI 数学助手。"
    "请用中文回答数学问题，适当使用 LaTeX（$...$ 行内，$$...$$ 独立行）。"
    "对于推导类问题，请分步骤解释。"
)

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

_BTN_PRIMARY = """
    QPushButton { background: #3b82f6; color: #fff; border: none;
    border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500; }
    QPushButton:hover { background: #2563eb; }
    QPushButton:disabled { background: #94a3b8; }
"""


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
                if self.isInterruptionRequested():
                    return
                self.chunk_ready.emit(chunk)
            self.finished.emit()
        except Exception as e:
            if not self.isInterruptionRequested():
                self.error_occurred.emit(str(e))


class AIDialog(QDialog):
    """AI 数学助手对话框 — 流式对话，上下文感知。"""

    def __init__(self, parent: QWidget | None = None,
                 context_expr: str = "", context_mode: str = ""):
        super().__init__(parent)
        self.setWindowTitle("AI 数学助手")
        self.resize(600, 500)
        self.setMinimumSize(450, 350)
        self.setStyleSheet(_DIALOG_STYLE)

        self._context_expr = context_expr
        self._context_mode = context_mode

        # 系统提示（含上下文）
        sys_prompt = _SYSTEM_PROMPT
        if context_expr:
            sys_prompt += f"\n用户当前正在处理表达式: {context_expr}"
            if context_mode:
                sys_prompt += f"（模式: {context_mode}）"
        self._messages: list[dict] = [{"role": "system", "content": sys_prompt}]

        self._worker: _AIStreamWorker | None = None
        self._last_full_response = ""
        self._ai_text_start: int = 0

        # 当前选中模型
        from MF_AI.config import Config
        self._model = Config().get_default_model() or "deepseek-v4-pro"

        self._build_ui()

    def _build_ui(self):
        from PySide6.QtWidgets import QComboBox

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # 标题 + 模型选择
        hdr = QHBoxLayout()
        title = QLabel("AI 数学助手")
        title.setStyleSheet(
            "font-size: 16px; font-weight: 600; color: #0f172a; background: transparent;")
        hdr.addWidget(title)

        self._model_combo = QComboBox()
        self._model_combo.setFixedWidth(150)
        self._model_combo.addItems(["deepseek-v4-pro", "deepseek-chat",
                                     "deepseek-reasoner", "gpt-4o", "gpt-4o-mini"])
        self._model_combo.setCurrentText(self._model)
        self._model_combo.currentTextChanged.connect(self._on_model_changed)
        hdr.addWidget(self._model_combo)

        hdr.addStretch()
        self._status_lbl = QLabel("就绪")
        self._status_lbl.setStyleSheet(
            "font-size: 11px; color: #94a3b8; background: transparent;")
        hdr.addWidget(self._status_lbl)
        root.addLayout(hdr)

        # 上下文提示
        if self._context_expr:
            ctx_text = f"当前: {self._context_expr}"
            if self._context_mode:
                ctx_text += f"  [{self._context_mode}]"
            ctx = QLabel(ctx_text)
            ctx.setStyleSheet(
                "font-size: 11px; color: #6366f1; background: #eef2ff;"
                " padding: 4px 8px; border-radius: 4px;")
            root.addWidget(ctx)

        # 输出
        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        self._chat_view.setFont(QFont("Microsoft YaHei", 10))
        root.addWidget(self._chat_view, 1)

        # 输入
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

        # 底部按钮
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        copy_btn = QPushButton("复制最后回复")
        copy_btn.setStyleSheet(
            "QPushButton { background: #f1f5f9; color: #475569; border: 1px solid #d1d5db;"
            " border-radius: 6px; padding: 6px 14px; font-size: 12px; }"
            "QPushButton:hover { background: #e2e8f0; }")
        copy_btn.clicked.connect(self._copy_result)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        clear_btn = QPushButton("清空对话")
        clear_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #94a3b8; border: none;"
            " font-size: 11px; } QPushButton:hover { color: #ef4444; }")
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(clear_btn)
        root.addLayout(btn_row)

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        if self._worker and self._worker.isRunning():
            return

        cfg = get_config()
        if not cfg.is_available():
            self._append_system("AI 服务未配置。请在 设置 → AI 配置 中设置 API Key。")
            return

        self._messages.append({"role": "user", "content": text})
        self._input.clear()
        self._set_sending(True)
        self._append_user(text)
        self._last_full_response = ""

        # 使用选中模型
        from MF_AI.config import Config
        Config().set_model(self._model)

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
        if self._last_full_response:
            self._messages.append(
                {"role": "assistant", "content": self._last_full_response})
            # 替换 AI 纯文本为 LaTeX 渲染后的 HTML
            html = _render_response(self._last_full_response)
            cursor = self._chat_view.textCursor()
            cursor.setPosition(self._ai_text_start)
            cursor.movePosition(QTextCursor.MoveOperation.End,
                                QTextCursor.MoveMode.KeepAnchor)
            cursor.insertHtml(html)
        self._chat_view.append("")
        self._set_sending(False)

    def _on_error(self, msg: str):
        self._append_system(f"错误: {msg}")
        self._set_sending(False)

    def _on_model_changed(self, model: str):
        self._model = model
        self._status_lbl.setText(f"模型: {model}")

    def _copy_result(self):
        if self._last_full_response:
            QApplication.clipboard().setText(self._last_full_response)
            self._status_lbl.setText("已复制到剪贴板")

    def _set_sending(self, sending: bool):
        self._input.setEnabled(not sending)
        if sending:
            self._send_btn.setText("停止")
            self._send_btn.setStyleSheet(
                "QPushButton { background: #ef4444; color: #fff; border: none;"
                " border-radius: 4px; padding: 6px 16px; font-size: 13px; font-weight: 500; }"
                "QPushButton:hover { background: #dc2626; }")
            self._send_btn.clicked.disconnect()
            self._send_btn.clicked.connect(self._stop)
        else:
            self._send_btn.setText("发送")
            self._send_btn.setStyleSheet(_BTN_PRIMARY)
            self._send_btn.clicked.disconnect()
            self._send_btn.clicked.connect(self._send)

    def _stop(self):
        """中止当前 AI 流式请求。"""
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(3000)
        self._append_system("（已中止）")
        self._set_sending(False)
        self._send_btn.setEnabled(not sending)
        if sending:
            self._status_lbl.setText("思考中…")
            self._status_lbl.setStyleSheet(
                "font-size: 11px; color: #3b82f6; background: transparent;")
            cursor = self._chat_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertHtml('<span style="color:#3b82f6;">AI: </span>')
            # 记录 AI 回复起始位置
            self._ai_text_start = cursor.position()
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
        self._messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        self._chat_view.clear()
        self._last_full_response = ""
        self._status_lbl.setText("对话已清空")
