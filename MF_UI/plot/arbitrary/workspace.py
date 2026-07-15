# -*- coding: utf-8 -*-
"""任意做图模式工作区 — 自由几何对象绘制（功能预留）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class ArbitraryWorkspace(QWidget):
    """任意做图模式 — 手动画圆、线段等自由几何对象（功能预留）。"""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        f = QFrame(); f.setObjectName("placeholder_frame"); f.setMinimumHeight(400)
        inner = QVBoxLayout(f); inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.setSpacing(12)

        t = QLabel("任意做图")
        t.setObjectName("page_title"); t.setStyleSheet("font-size:20px;font-weight:600;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter); inner.addWidget(t)

        d = QLabel("手动画圆、线段、直线等自由几何对象（功能预留）")
        d.setObjectName("page_desc"); d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(d)

        root.addWidget(f)
        self.status_message.emit("任意做图 — 功能预留")
