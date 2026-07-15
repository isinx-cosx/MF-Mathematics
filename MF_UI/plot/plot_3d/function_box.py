# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.function_box — 3D 模式函数框（仅占位 UI，无功能）。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)


class FunctionBox(QWidget):
    """3D 模式函数框 — 纯占位，无任何实际功能。"""

    def __init__(self, index: int = 1, color: str = "#3498db",
                 parent: QWidget | None = None):
        super().__init__(parent)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(3)
        root.setContentsMargins(8, 6, 8, 6)

        row1 = QHBoxLayout()
        row1.setSpacing(6)

        title = QLabel(f"{index}.")
        title.setStyleSheet("font-weight:600; font-size:13px;")
        row1.addWidget(title)

        inp = QLineEdit()
        inp.setFixedHeight(28)
        inp.setPlaceholderText("3D 功能开发中...")
        inp.setReadOnly(True)
        row1.addWidget(inp, 1)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color}; font-size:16px;")
        dot.setFixedWidth(20)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row1.addWidget(dot)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(4)
        row2.addStretch()

        cb = QCheckBox("显示")
        cb.setChecked(True)
        cb.setEnabled(False)
        row2.addWidget(cb)

        btn = QPushButton("×")
        btn.setFixedSize(24, 24)
        btn.setEnabled(False)
        btn.setToolTip("3D 模式开发中")
        row2.addWidget(btn)
        root.addLayout(row2)
