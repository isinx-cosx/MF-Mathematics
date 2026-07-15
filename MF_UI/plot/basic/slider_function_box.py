# -*- coding: utf-8 -*-
"""SliderFunctionBox — 参数滑块控件（独立于函数框）。

信号:
  - valueChanged(str, float)  参数值变化
  - removed(box)              删除按钮
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QVBoxLayout, QWidget,
)

_CARD_STYLE = """
    SliderFunctionBox {
        background: #f9fafb; border: 1px solid #e2e8f0;
        border-radius: 8px; padding: 8px; margin: 2px 0;
    }
"""
_DEL_STYLE = """
    QPushButton {
        background: transparent; border: none; color: #94a3b8;
        font-size: 18px; font-weight: bold; padding: 0 4px;
    }
    QPushButton:hover { color: #ef4444; background: #fee2e2; border-radius: 4px; }
"""
_VIS_STYLE = "QPushButton { background: transparent; border: none; font-size: 14px; padding: 0 2px; }"


class SliderFunctionBox(QWidget):
    """参数滑块控件 — 每个参数一个独立滑块框。

    信号:
      valueChanged(name, value) — 值变化
      removed(box) — 删除
    """

    valueChanged = Signal(str, float)
    removed = Signal(object)

    def __init__(self, index: int, param_name: str, color: str = "#3498db",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._index = index
        self._param_name = param_name
        self._color = color
        self._visible = True
        self._updating = False

        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(_CARD_STYLE)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(8); shadow.setOffset(0, 1)
        shadow.setColor(QColor(0, 0, 0, 30))
        self.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(6, 4, 6, 4)

        row = QHBoxLayout(); row.setSpacing(4)

        # 序号
        idx_lbl = QLabel(f"{self._index}.")
        idx_lbl.setFixedWidth(22)
        idx_lbl.setStyleSheet("font-weight:600; font-size:13px; color:#1e293b;")
        row.addWidget(idx_lbl)

        # 显示按钮
        self._vis_btn = QPushButton("●")
        self._vis_btn.setFixedSize(20, 20)
        self._vis_btn.setStyleSheet(_VIS_STYLE + f"color:{self._color};")
        self._vis_btn.setToolTip("隐藏")
        self._vis_btn.clicked.connect(self._toggle_vis)
        row.addWidget(self._vis_btn)

        # 参数名 + 值
        self._val_btn = QPushButton(f"{self._param_name} = 1.0")
        self._val_btn.setFixedWidth(72)
        self._val_btn.setStyleSheet(
            "QPushButton { font-size: 11px; color: #475569; background: #f1f5f9;"
            " border: 1px solid #d1d5db; border-radius: 3px; padding: 1px 4px; }"
            "QPushButton:hover { background: #e2e8f0; }")
        self._val_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._val_btn.clicked.connect(self._start_edit)
        row.addWidget(self._val_btn)

        # 行内编辑器（默认隐藏）
        self._edit = QLineEdit("1.0")
        self._edit.setFixedWidth(72)
        self._edit.setStyleSheet(
            "QLineEdit { font-size: 11px; padding: 1px 4px;"
            " border: 1px solid #3b82f6; border-radius: 3px; }")
        self._edit.hide()
        self._edit.editingFinished.connect(self._finish_edit)
        row.addWidget(self._edit)

        # 滑块（步长 0.1, 范围 -5~5）
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(-50, 50)
        self._slider.setValue(10)  # default 1.0
        self._slider.valueChanged.connect(self._on_slider)
        row.addWidget(self._slider, 1)

        # 删除
        del_btn = QPushButton("×")
        del_btn.setFixedSize(25, 25)
        del_btn.setStyleSheet(_DEL_STYLE)
        del_btn.setToolTip("删除滑块")
        del_btn.clicked.connect(lambda: self.removed.emit(self))
        row.addWidget(del_btn)

        root.addLayout(row)

    # ── 属性 ─────────────────────────────────────────────────

    @property
    def param_name(self) -> str:
        return self._param_name

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def value(self) -> float:
        return self._slider.value() / 10.0

    @property
    def color(self) -> str:
        return self._color

    # ── 交互 ─────────────────────────────────────────────────

    def _toggle_vis(self) -> None:
        self._visible = not self._visible
        if self._visible:
            self._vis_btn.setText("●")
            self._vis_btn.setStyleSheet(_VIS_STYLE + f"color:{self._color};")
        else:
            self._vis_btn.setText("○")
            self._vis_btn.setStyleSheet(_VIS_STYLE + "color:#94a3b8;")
        self.valueChanged.emit(self._param_name, self.value)

    def _on_slider(self, val: int) -> None:
        if self._updating: return
        v = val / 10.0
        self._val_btn.setText(f"{self._param_name} = {v:.1f}")
        self.valueChanged.emit(self._param_name, v)

    def _start_edit(self) -> None:
        self._val_btn.hide()
        self._edit.setText(f"{self.value:.1f}")
        self._edit.show()
        self._edit.setFocus()
        self._edit.selectAll()

    def _finish_edit(self) -> None:
        self._edit.hide()
        try:
            v = float(self._edit.text())
            v = max(-5.0, min(5.0, v))
        except ValueError:
            v = self.value
        self._updating = True
        self._slider.setValue(int(round(v * 10)))
        self._updating = False
        self._val_btn.setText(f"{self._param_name} = {v:.1f}")
        self._val_btn.show()
        self.valueChanged.emit(self._param_name, v)
