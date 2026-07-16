# -*- coding: utf-8 -*-
"""MF 风格 AI 配置提示弹窗 — 现代化 UI，引导用户配置 API Key。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
)


class AIConfigPrompt(QDialog):
    """MF 风格 AI 配置提示弹窗。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 服务未配置")
        self.setFixedSize(420, 240)
        self.setObjectName("aiConfigPrompt")

        self._build_ui()
        self._result = False

        # 自定义标题栏
        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, "配置 API")

        # 继承主窗口的当前主题样式表
        if self.parent() is not None:
            self.setStyleSheet(self.parent().styleSheet())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(28, 24, 28, 20)

        # 图标 + 标题
        icon_lbl = QLabel("🤖")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 40px; background: transparent;")
        root.addWidget(icon_lbl)

        title = QLabel("AI 服务未配置")
        title.setObjectName("ai_prompt_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        desc = QLabel("未检测到有效的 API Key 或本地模型。\n配置后可解锁 AI 加速、步骤生成、智能问答等功能。")
        desc.setObjectName("ai_prompt_desc")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        root.addWidget(desc)

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
        root.addLayout(btn_row)

    def _on_go(self) -> None:
        self._result = True
        self.accept()

    def go_to_settings(self) -> bool:
        """返回 True 表示用户点击了"前往设置"。"""
        return self._result
