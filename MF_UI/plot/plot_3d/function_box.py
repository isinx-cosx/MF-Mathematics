# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.function_box — 3D 模式函数框（仅 UI）。

完全独立，无计算逻辑，无参数滑块。
信号 changed / removed 供外部连接。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)


class FunctionBox(QWidget):
    """3D 模式函数框 — 仅 UI，无计算。

    信号:
      changed()   — 输入 / 可见性变化
      removed(box) — 删除按钮
    """

    changed = Signal()
    removed = Signal(object)

    def __init__(self, index: int = 1, color: str = "#3498db",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color

        self._build_ui()

    def _build_ui(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8)
        shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(3)
        root.setContentsMargins(8, 6, 8, 6)

        # 第 1 行：标题 + 输入 + 色点
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self._title = QLabel(f"{self._index}.")
        self._title.setStyleSheet("font-weight:600; font-size:13px;")
        row1.addWidget(self._title)

        self._input = QLineEdit()
        self._input.setFixedHeight(28)
        self._input.setPlaceholderText("sin(x)*cos(y), x^2+y^2")
        self._input.textChanged.connect(lambda: self.changed.emit())
        row1.addWidget(self._input, 1)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{self._color}; font-size:16px;")
        dot.setFixedWidth(20)
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row1.addWidget(dot)
        root.addLayout(row1)

        # 第 2 行：显示开关 + 删除
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        row2.addStretch()

        self._vis = QCheckBox("显示")
        self._vis.setChecked(True)
        self._vis.setObjectName("func_vis_cb")
        self._vis.toggled.connect(lambda: self.changed.emit())
        row2.addWidget(self._vis)

        self._del_btn = QPushButton("×")
        self._del_btn.setFixedSize(24, 24)
        self._del_btn.setObjectName("func_del_btn")
        self._del_btn.setToolTip("删除此函数")
        self._del_btn.clicked.connect(lambda: self.removed.emit(self))
        row2.addWidget(self._del_btn)
        root.addLayout(row2)

    # ── 属性（纯数据透传，无计算）───────────────────────────

    @property
    def expr(self) -> str:
        return self._input.text().strip()

    @property
    def is_visible(self) -> bool:
        return self._vis.isChecked()

    @property
    def color(self) -> str:
        return self._color

    @property
    def label(self) -> str:
        raw = self._input.text().strip()
        return f"{self._index}. {raw}" if raw else f"{self._index}."
