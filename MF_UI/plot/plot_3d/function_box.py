# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d.function_box — 3D 模式函数框（纯 UI，无计算）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

_PRESET_COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#e84393",
]
_COLOR_IDX = 0


def _next_color() -> str:
    global _COLOR_IDX
    c = _PRESET_COLORS[_COLOR_IDX % len(_PRESET_COLORS)]
    _COLOR_IDX += 1
    return c


class FunctionBox(QWidget):
    """3D 函数框 — 仅 UI，无计算、无绘制。"""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, index: int = 1, color: str = "",
                 mode: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._color = color or _next_color()
        self._visible = True

        self.setStyleSheet("""
            FunctionBox {
                background: #f9fafb; border: 1px solid #e2e8f0;
                border-radius: 8px; padding: 8px; margin: 2px 0;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8); shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(4); root.setContentsMargins(8, 6, 8, 6)

        row = QHBoxLayout(); row.setSpacing(4)

        idx_lbl = QLabel(f"{index}.")
        idx_lbl.setFixedWidth(22)
        idx_lbl.setStyleSheet("font-weight:600; font-size:13px; color:#1e293b;")
        row.addWidget(idx_lbl)

        self._vis_btn = QPushButton("")
        self._vis_btn.setFixedSize(16, 16)
        self._vis_btn.setStyleSheet(
            "QPushButton {"
            f"  background: {self._color};"
            "  border: 2px solid rgba(0,0,0,0.15);"
            "  border-radius: 8px;"
            "}")
        self._vis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vis_btn.clicked.connect(self._toggle_vis)
        row.addWidget(self._vis_btn)

        inp = QLineEdit()
        inp.setFixedHeight(28)
        inp.setPlaceholderText("3D 开发中...")
        inp.setReadOnly(True)
        inp.setStyleSheet("""
            QLineEdit {
                border: 1px solid #d1d5db; border-radius: 4px;
                padding: 3px 8px; font-size: 13px; background: #fff; color: #1e293b;
            }
        """)
        row.addWidget(inp, 1)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(25, 25)
        del_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; color: #94a3b8;
                font-size: 18px; font-weight: bold; padding: 0 4px;
            }
            QPushButton:hover { color: #ef4444; background: #fee2e2; border-radius: 4px; }
        """)
        del_btn.clicked.connect(lambda: self.removed.emit(self))
        row.addWidget(del_btn)
        root.addLayout(row)

    def _toggle_vis(self) -> None:
        self._visible = not self._visible
        if self._visible:
            self._vis_btn.setStyleSheet(
                "QPushButton {"
                f"  background: {self._color};"
                "  border: 2px solid rgba(0,0,0,0.15);"
                "  border-radius: 8px;"
                "}")
        else:
            self._vis_btn.setStyleSheet(
                "QPushButton {"
                "  background: transparent;"
                "  border: 2px dashed #94a3b8;"
                "  border-radius: 8px;"
                "}")

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def color(self) -> str:
        return self._color
