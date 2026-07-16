# -*- coding: utf-8 -*-
"""StepViewer — AI 驱动的步骤查看器，LaTeX 渲染，像人类教师书写。"""

from __future__ import annotations

import hashlib
from functools import lru_cache

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from MF_UI.dialogs.ai_dialog import _render_response

# ── 教科书风格系统提示词 ──────────────────────────────────

_STEP_SYSTEM_PROMPT = (
    "你是一位经验丰富的数学教师，擅长用清晰、自然的语言向学生讲解数学推导。\n"
    "用户会提供一个「表达式」和一个「操作类型」。请你从头开始完成这个操作，"
    "生成完整的、逐步的推导过程——注意：你需要自己完成计算，而不是解释已有的结果。\n\n"
    "要求：\n"
    "1. 先重述问题（如「我们需要对 f(x)=sin(x) 求导」）。\n"
    "2. 每步标注【步骤 N】，先描述做了什么（如「使用链式法则」），再给出 LaTeX 推导。\n"
    "3. 行内公式用 $...$，关键公式独立成行用 $$...$$。\n"
    "4. 最终答案用 \\boxed{...} 标注。\n"
    "5. 语气自然友好，像在给学生当面讲解。\n"
    "6. 步骤数量：3~8 步，每步逻辑独立不跳跃。\n"
    "7. 必须自己计算到最终结果，不要假设用户已经知道答案。"
)

# ── 样式 ──────────────────────────────────────────────────

_STYLE = """
    QDialog { background: #fafbfc; }
    QTextEdit {
        border: 1px solid #e2e8f0; border-radius: 8px;
        background: #fff; font-size: 14px; padding: 12px;
        line-height: 1.6;
    }
"""


# ── AI Worker ─────────────────────────────────────────────

class _StepWorker(QThread):
    """后台线程：调用 AI 生成步骤。"""
    finished = Signal(str)      # 完整步骤文本
    error = Signal(str)

    def __init__(self, expr: str, mode: str, parent=None):
        super().__init__(parent)
        self._expr = expr
        self._mode = mode

    def run(self):
        try:
            from MF_AI import chat
            prompt = f"表达式：{self._expr}\n操作：{self._mode}"
            result = chat([
                {"role": "system", "content": _STEP_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            if result:
                self.finished.emit(result)
            else:
                self.error.emit("AI 返回为空")
        except Exception as e:
            self.error.emit(str(e))


# ── 缓存 ─────────────────────────────────────────────────

@lru_cache(maxsize=64)
def _cached_steps(expr_hash: str) -> str | None:
    """缓存占位 — 实际实现在 StepViewer 中管理。"""
    return None


# ═══════════════════════════════════════════════════════════════
#  StepViewer
# ═══════════════════════════════════════════════════════════════

class StepViewer(QDialog):
    """AI 步骤查看器 — 像老师手写一样的推导过程。"""

    # 全局缓存：key = md5(expr + mode), value = rendered HTML
    _cache: dict[str, str] = {}

    def __init__(self, parent: QWidget | None = None,
                 expr: str = "", mode: str = ""):
        super().__init__(parent)
        self.setWindowTitle("步骤查看器")
        self.resize(600, 520)
        self.setMinimumSize(440, 360)
        self.setStyleSheet(_STYLE)

        self._expr = expr
        self._mode = mode
        self._cache_key = self._make_key(expr, mode)
        self._raw_text = ""
        self._worker: _StepWorker | None = None

        self._build_ui()
        self._start()

    @staticmethod
    def _make_key(expr: str, mode: str) -> str:
        return hashlib.md5(f"{mode}|{expr}".encode()).hexdigest()

    # ── UI ────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 14, 16, 14)

        # 标题
        title = QLabel(f"步骤推导 — {self._mode}")
        title.setStyleSheet(
            "font-size: 16px; font-weight: 600; color: #0f172a; background: transparent;")
        root.addWidget(title)

        # 表达式
        if self._expr:
            expr_label = QLabel(f"表达式: {self._expr}")
            expr_label.setStyleSheet(
                "font-size: 12px; color: #6366f1; background: #eef2ff;"
                " padding: 6px 10px; border-radius: 5px;"
                " font-family: 'Latin Modern Math', 'STIX', 'Cambria Math', serif;")
            expr_label.setWordWrap(True)
            root.addWidget(expr_label)

        # 主体
        self._view = QTextEdit()
        self._view.setReadOnly(True)
        self._view.setFont(QFont("Latin Modern Math, STIX, Cambria Math, serif", 13))
        root.addWidget(self._view, 1)

        # 底部按钮
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        self._status = QLabel("AI 正在生成步骤…")
        self._status.setStyleSheet("font-size: 11px; color: #3b82f6;")
        btn_row.addWidget(self._status, 1)

        copy_btn = QPushButton("复制（纯文本）")
        copy_btn.setStyleSheet(
            "QPushButton{background:#f1f5f9;border:1px solid #d1d5db;border-radius:6px;"
            "padding:6px 14px;font-size:12px;color:#475569;}"
            "QPushButton:hover{background:#e2e8f0;}")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(
            "QPushButton{background:#3b82f6;color:#fff;border:none;"
            "border-radius:6px;padding:6px 20px;font-size:12px;font-weight:500;}"
            "QPushButton:hover{background:#2563eb;}")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── 启动 ──────────────────────────────────────────────

    def _start(self):
        # 1. 检查缓存
        cached = StepViewer._cache.get(self._cache_key)
        if cached:
            self._view.setHtml(cached)
            self._status.setText("（缓存）就绪")
            self._status.setStyleSheet("font-size: 11px; color: #10b981;")
            return

        # 2. 检查是否有本地步骤（从 MathObject.steps 传入）
        # 由调用方在 set_local_steps 中设置
        if hasattr(self, '_local_steps_text') and self._local_steps_text:
            self._show_steps(self._local_steps_text)
            return

        # 3. 调用 AI
        if not self._expr:
            self._view.setPlainText("请输入表达式。")
            self._status.setText("表达式为空")
            self._status.setStyleSheet("font-size: 11px; color: #ef4444;")
            return

        self._worker = _StepWorker(self._expr, self._mode, self)
        self._worker.finished.connect(self._on_ai_steps)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def set_local_steps(self, steps: list[str]):
        """设置本地步骤（来自 MathObject.steps），跳过 AI 调用。"""
        # 编号
        text = "\n\n".join(
            f"【步骤 {i+1}】{s.strip()}" for i, s in enumerate(steps) if s.strip()
        )
        self._local_steps_text = text

    def _show_steps(self, text: str):
        """渲染步骤为 HTML 并显示。"""
        self._raw_text = text
        html = _render_response(text)
        # 轻微样式增强
        html = (
            "<div style='font-family: Latin Modern Math, STIX, Cambria Math, serif;"
            " font-size: 15px; line-height: 1.8; color: #1e293b;'>"
            + html + "</div>"
        )
        self._view.setHtml(html)
        # 缓存
        StepViewer._cache[self._cache_key] = html
        self._status.setText("就绪")
        self._status.setStyleSheet("font-size: 11px; color: #10b981;")

    def _on_ai_steps(self, text: str):
        self._show_steps(text)

    def _on_error(self, msg: str):
        self._view.setHtml(
            f"<div style='color:#dc2626;padding:16px;'>"
            f"<b>AI 服务暂时不可用</b><br><br>{msg}<br><br>请稍后重试。</div>")
        self._status.setText("生成失败")
        self._status.setStyleSheet("font-size: 11px; color: #ef4444;")

    # ── 复制 ──────────────────────────────────────────────

    def _copy(self):
        if self._raw_text:
            QApplication.clipboard().setText(self._raw_text)
            self._status.setText("已复制到剪贴板")
            self._status.setStyleSheet("font-size: 11px; color: #10b981;")
