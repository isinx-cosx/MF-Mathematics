# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.workspace — 3D 模式独立工作区。

完全不依赖 basic/ 中的任何代码。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from MF_UI.plot.plot_3d.canvas import Plot3D
from MF_UI.plot.plot_3d.function_box import FunctionBox

_COLORS = ["#e74c3c","#3498db","#2ecc71","#f39c12",
           "#9b59b6","#1abc9c","#e67e22","#e84393"]


class Plot3DWorkspace(QWidget):
    """3D 模式独立工作区 — 函数框列表 + 3D 画布。"""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._color_idx = 0
        self._next_index = 1
        self._boxes: list[FunctionBox] = []
        self._separators: list[QFrame] = []

        root = QHBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # ── 左侧面板 ──
        left = QWidget(); left.setFixedWidth(340)
        left.setObjectName("plot_left_panel")
        ll = QVBoxLayout(left); ll.setSpacing(4)
        ll.setContentsMargins(12, 12, 12, 12)

        t = QLabel("3D 模式 — 三维曲面绘图")
        t.setObjectName("plot_title_label"); ll.addWidget(t)
        d = QLabel("支持：显式 z=f(x,y)、隐式 f(x,y,z)=0、参数方程")
        d.setObjectName("plot_desc_label"); ll.addWidget(d)

        self._status = QLabel("就绪")
        self._status.setStyleSheet("font-size:11px;")
        self._status.setWordWrap(True); ll.addWidget(self._status)

        # 卡片容器
        card = QFrame(); card.setObjectName("plot_work_card")
        scroll = QScrollArea(card)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setObjectName("plotScroll")

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(0)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_container)

        self._btn_add = QPushButton("＋ 添加函数")
        self._btn_add.setFlat(True); self._btn_add.setFixedHeight(50)
        self._btn_add.setObjectName("plot_btn_add")
        self._btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add.clicked.connect(self._add_function_box)
        self._list_layout.addWidget(self._btn_add)

        card_inner = QVBoxLayout(card)
        card_inner.setContentsMargins(0, 0, 0, 0); card_inner.addWidget(scroll)
        ll.addWidget(card, 1); root.addWidget(left)

        # ── 3D 画布 ──
        self._canvas = Plot3D()
        self._canvas.status_message.connect(self._status.setText)
        root.addWidget(self._canvas, 1)

        self._add_function_box()

    @property
    def canvas(self):
        return self._canvas

    def _add_function_box(self) -> None:
        color = _COLORS[self._color_idx % len(_COLORS)]
        self._color_idx += 1
        box = FunctionBox(index=self._next_index, color=color, parent=self)
        self._next_index += 1

        box.changed.connect(self._rebuild_curves)
        box.removed.connect(self._on_box_removed)

        idx = self._list_layout.indexOf(self._btn_add)
        if self._boxes:
            sep = QFrame(); sep.setFixedHeight(1)
            sep.setStyleSheet("background:#e2e8f0;border:none;")
            self._list_layout.insertWidget(idx, sep)
            self._separators.append(sep); idx += 1

        self._list_layout.insertWidget(idx, box)
        self._boxes.append(box)
        self._update_delete_buttons()
        self._rebuild_curves()

    def _on_box_removed(self, box: FunctionBox) -> None:
        if len(self._boxes) <= 1: return
        if box not in self._boxes: return
        self._boxes.remove(box)
        layout_idx = self._list_layout.indexOf(box)
        if layout_idx > 0:
            above = self._list_layout.itemAt(layout_idx - 1)
            if above and above.widget() and isinstance(above.widget(), QFrame):
                w = above.widget()
                if w in self._separators:
                    self._separators.remove(w)
                    self._list_layout.removeWidget(w); w.deleteLater()
        self._list_layout.removeWidget(box); box.deleteLater()
        self._update_delete_buttons()
        self._rebuild_curves()

    def _update_delete_buttons(self) -> None:
        v = len(self._boxes) > 1
        for b in self._boxes:
            b._del_btn.setVisible(v)

    def _rebuild_curves(self) -> None:
        self._canvas.clear_surfaces()
        for b in self._boxes:
            if not b.is_visible or not b.exprs: continue
            for s in b.exprs:
                self._canvas.add_surface(s, color=b.color)
