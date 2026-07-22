# -*- coding: utf-8 -*-
"""BaseWorkspace — 计算工作区基类。

消除 algebra / linear_algebra / numerical / probability 四个子模块中
的重复 UI 代码。子类仅需实现 get_title / get_description / create_calc_block。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from MF_UI.calc.base_calc_block import BaseCalcBlock


class BaseWorkspace(QWidget):
    """计算工作区基类 — 标题 + 描述 + 卡片 + 滚动区 + 虚框按钮。"""

    # 子类可覆盖：是否允许多计算块（基础运算设为 False）
    _enable_add_block: bool = True

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._block_counter = 1
        self._blocks: list[BaseCalcBlock] = []
        self._separators: dict[BaseCalcBlock, QFrame | None] = {}

        # ── 布局 ──
        root = QVBoxLayout(self)
        root.setSpacing(2)

        self._title_label = QLabel(self.get_title())
        self._title_label.setObjectName("title_label")
        root.addWidget(self._title_label)

        self._desc_label = QLabel(self.get_description())
        self._desc_label.setObjectName("desc_label")
        root.addWidget(self._desc_label)

        # ── 卡片容器 ──
        self._card = QFrame()
        self._card.setObjectName("work_card")

        self._scroll = QScrollArea(self._card)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setObjectName("calcScroll")

        self._content = QWidget()
        self._scroll.setWidget(self._content)

        self._card_layout = QVBoxLayout(self._content)
        self._card_layout.setSpacing(8)
        self._card_layout.setContentsMargins(0, 0, 0, 0)

        card_inner = QVBoxLayout(self._card)
        card_inner.setContentsMargins(0, 0, 0, 0)
        card_inner.addWidget(self._scroll)

        # 虚框添加按钮（子类可通过 _enable_add_block=False 禁用）
        self._btn_add: QPushButton | None = None
        if self._enable_add_block:
            self._btn_add = QPushButton("＋ 添加计算")
            self._btn_add.setFlat(True)
            self._btn_add.setFixedHeight(50)
            self._btn_add.setObjectName("btn_add")
            self._btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_add.clicked.connect(self._on_add_block)
            self._card_layout.addWidget(self._btn_add)

        self._card_layout.addStretch()

        root.addWidget(self._card, 1)

        # 初始添加一个计算块
        self._on_add_block()

    # ── 子类覆盖 ──────────────────────────────────────────────

    def get_title(self) -> str:
        raise NotImplementedError("子类必须实现 get_title()")

    def get_description(self) -> str:
        raise NotImplementedError("子类必须实现 get_description()")

    def create_calc_block(self, block_id: int,
                          on_delete: callable) -> BaseCalcBlock:
        raise NotImplementedError("子类必须实现 create_calc_block()")

    # ── 计算块增删 ────────────────────────────────────────────

    def _on_add_block(self) -> None:
        """添加计算块。若 _enable_add_block=False 则仅允许首次调用（初始化）。"""
        if not self._enable_add_block and self._blocks:
            return  # 单块模式：已有一个块，不允许添加

        cb = self.create_calc_block(self._block_counter, self._on_delete_block)
        cb.setFixedHeight(120)
        self._block_counter += 1

        idx = self._card_layout.indexOf(self._btn_add) if self._btn_add else -1
        if idx < 0:
            idx = self._card_layout.count()  # 末尾

        if self._blocks:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setObjectName("calc_separator")
            self._card_layout.insertWidget(idx, sep)
            self._separators[cb] = sep
        else:
            self._separators[cb] = None

        self._card_layout.insertWidget(idx, cb)
        self._blocks.append(cb)

    def _on_delete_block(self, block: BaseCalcBlock) -> None:
        if len(self._blocks) <= 1:
            return

        sep = self._separators.pop(block, None)
        if sep is not None:
            self._card_layout.removeWidget(sep)
            sep.hide()
            sep.deleteLater()

        self._card_layout.removeWidget(block)
        if block in self._blocks:
            self._blocks.remove(block)
        block.deleteLater()
