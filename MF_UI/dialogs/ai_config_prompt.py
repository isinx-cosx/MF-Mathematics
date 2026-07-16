# -*- coding: utf-8 -*-
"""MF 风格 AI 配置提示弹窗 — 现代化 UI，引导用户配置 API Key。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QWidget,
)

from MF_UI.components.mf_dialog import MFDialog


class AIConfigPrompt(MFDialog):
    """MF 风格 AI 配置提示弹窗。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, title="AI 服务未配置", width=420, height=240)
        self.setObjectName("aiConfigPrompt")
        self._result = False
        self._build_ui()

    def _build_ui(self) -> None:
        self.content_layout.setSpacing(14)
        self.content_layout.setContentsMargins(12, 8, 12, 8)

        # 图标 + 标题
        icon_lbl = QLabel("🤖")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 40px; background: transparent;")
        self.content_layout.addWidget(icon_lbl)

        title = QLabel("AI 服务未配置")
        title.setObjectName("ai_prompt_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(title)

        desc = QLabel("未检测到有效的 API Key 或本地模型。\n配置后可解锁 AI 加速、步骤生成、智能问答等功能。")
        desc.setObjectName("ai_prompt_desc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        self.content_layout.addWidget(desc)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        cancel_btn = QPushButton("稍后再说")
        cancel_btn.setObjectName("ai_secondary_btn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        go_btn = QPushButton("前往设置")
        go_btn.setObjectName("ai_send_btn")
        go_btn.clicked.connect(self._on_go)
        btn_row.addWidget(go_btn)

        btn_row.addStretch()
        self.content_layout.addLayout(btn_row)

    def _on_go(self) -> None:
        self._result = True
        self.accept()

    def go_to_settings(self) -> bool:
        """返回 True 表示用户点击了"前往设置"。"""
        return self._result
