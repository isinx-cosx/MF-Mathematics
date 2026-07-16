# -*- coding: utf-8 -*-
"""MFDialog — 带自定义标题栏的对话框基类。

所有子界面对话框继承此类即可获得:
  - MF-Mathematics 风格自定义标题栏
  - 暗色/亮色双主题自动适配
  - 窗口拖拽移动
  - 关闭按钮

用法:
    class MyDialog(MFDialog):
        def __init__(self, parent=None):
            super().__init__(parent, title="我的窗口", width=500, height=400)
            self._build_content_ui()  # 在 content_layout 中构建内容

        def _build_content_ui(self):
            lbl = QLabel("内容")
            self.content_layout.addWidget(lbl)
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)


class MFDialog(QDialog):
    """MF-Mathematics 风格对话框基类 — 无边框 + 自定义标题栏。"""

    def __init__(self, parent: QWidget | None = None,
                 title: str = "MF-Mathematics",
                 width: int = 500, height: int = 400,
                 show_minimize: bool = False,
                 show_maximize: bool = False) -> None:
        super().__init__(parent)
        self._drag_pos: QPoint | None = None

        # 无边框 + 透明背景（圆角需要）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("QDialog { border-radius: 10px; }")

        # 投影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

        self._title = title
        self.resize(width, height)

        # 主布局
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # 自定义标题栏
        self._build_title_bar(show_minimize, show_maximize)

        # 内容区域（子类通过 self.content_layout 添加控件）
        self._content_widget = QWidget()
        self._content_widget.setObjectName("mfDialogContent")
        self.content_layout = QVBoxLayout(self._content_widget)
        self.content_layout.setContentsMargins(16, 12, 16, 16)
        self.content_layout.setSpacing(10)
        self._root_layout.addWidget(self._content_widget, 1)

    def _build_title_bar(self, show_min: bool, show_max: bool) -> None:
        bar = QWidget()
        bar.setObjectName("mfDialogTitleBar")
        bar.setFixedHeight(34)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(0)

        # 图标
        icon = QLabel("📐")
        icon.setObjectName("titlebar_icon")
        icon.setFixedWidth(24)
        layout.addWidget(icon)

        # 标题
        lbl = QLabel(self._title)
        lbl.setObjectName("titlebar_title")
        layout.addWidget(lbl)

        layout.addStretch()

        # 关闭按钮
        btn = QPushButton("✕")
        btn.setObjectName("titlebar_btn_close")
        btn.setFixedSize(32, 26)
        btn.clicked.connect(self.reject)
        layout.addWidget(btn)

        self._root_layout.addWidget(bar)

    # ── 窗口拖拽 ──────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


def apply_dialog_title_bar(dialog: QDialog, title: str = "") -> QWidget:
    """为现有 QDialog 添加自定义标题栏 + 圆角 + 阴影。

    自动处理:
      - 无边框窗口标志
      - 34px 自定义标题栏（📐 图标 + 标题 + ✕ 关闭）
      - QGraphicsDropShadowEffect 投影
      - 拖拽移动
      - 对话框高度 +34px 以适应标题栏

    用法:
        dlg = QDialog(parent)
        dlg.setObjectName("...")
        # ... 构建 dlg 的原有 layout（必须使用 QVBoxLayout）...
        apply_dialog_title_bar(dlg, "我的标题")
    """
    dialog.setWindowFlags(
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.Dialog
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    layout = dialog.layout()
    if layout is None:
        return None

    # 圆角 + 阴影
    dialog.setStyleSheet(
        dialog.styleSheet() +
        "QDialog { border-radius: 10px; }"
    )

    # 投影效果
    shadow = QGraphicsDropShadowEffect(dialog)
    shadow.setBlurRadius(24)
    shadow.setOffset(0, 4)
    shadow.setColor(QColor(0, 0, 0, 60))
    dialog.setGraphicsEffect(shadow)

    # 构建标题栏
    bar = QWidget()
    bar.setObjectName("mfDialogTitleBar")
    bar.setFixedHeight(34)
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(12, 0, 4, 0)
    bar_layout.setSpacing(0)

    icon = QLabel("📐")
    icon.setObjectName("titlebar_icon")
    icon.setFixedWidth(24)
    bar_layout.addWidget(icon)

    lbl = QLabel(title or dialog.windowTitle())
    lbl.setObjectName("titlebar_title")
    bar_layout.addWidget(lbl)
    bar_layout.addStretch()

    btn = QPushButton("✕")
    btn.setObjectName("titlebar_btn_close")
    btn.setFixedSize(32, 26)
    btn.clicked.connect(dialog.reject)
    bar_layout.addWidget(btn)

    # 插入到布局最顶部（索引 0 = 最上方）
    layout.insertWidget(0, bar)

    # 调整窗口高度以容纳标题栏（考虑固定尺寸的情况）
    min_h = dialog.minimumHeight()
    max_h = dialog.maximumHeight()
    cur_h = dialog.height()
    cur_w = dialog.width()
    new_h = cur_h + 34
    if min_h == max_h and min_h > 0:
        # setFixedSize 情况 → 重新设置固定尺寸
        dialog.setFixedSize(cur_w, new_h)
    else:
        dialog.resize(cur_w, new_h)
        if min_h > 0:
            dialog.setMinimumHeight(min_h + 34)
        if max_h < 16777215:  # QWIDGETSIZE_MAX
            dialog.setMaximumHeight(max_h + 34)

    # 拖拽功能
    _drag_pos = [None]
    def _press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            _drag_pos[0] = event.globalPosition().toPoint()
        QDialog.mousePressEvent(dialog, event)
    def _move(event):
        if _drag_pos[0] is not None and event.buttons() == Qt.MouseButton.LeftButton:
            d = event.globalPosition().toPoint() - _drag_pos[0]
            dialog.move(dialog.pos() + d)
            _drag_pos[0] = event.globalPosition().toPoint()
        QDialog.mouseMoveEvent(dialog, event)
    def _release(event):
        _drag_pos[0] = None
        QDialog.mouseReleaseEvent(dialog, event)
    dialog.mousePressEvent = _press
    dialog.mouseMoveEvent = _move
    dialog.mouseReleaseEvent = _release

    return bar
