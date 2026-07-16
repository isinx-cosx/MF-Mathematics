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

from PySide6.QtCore import Qt, QEvent, QObject, QPoint
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
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

        # 无边框
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

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
    """为现有 QDialog 添加自定义标题栏（插入到布局顶部）。

    用法:
        dlg = QDialog(parent)
        dlg.setObjectName("...")
        # ... 构建 dlg 的原有 layout（必须使用 QVBoxLayout）...
        apply_dialog_title_bar(dlg, "我的标题")

    Returns:
        标题栏 QWidget。
    """
    dialog.setWindowFlags(
        dialog.windowFlags() |
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.Dialog
    )

    layout = dialog.layout()
    if layout is None:
        return None

    # 构建标题栏
    bar = QWidget()
    bar.setObjectName("mfDialogTitleBar")
    bar.setFixedHeight(34)
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(12, 0, 4, 0)
    bar_layout.setSpacing(0)

    lbl = QLabel(title or dialog.windowTitle())
    lbl.setObjectName("titlebar_title")
    bar_layout.addWidget(lbl)
    bar_layout.addStretch()

    btn = QPushButton("✕")
    btn.setObjectName("titlebar_btn_close")
    btn.setFixedSize(32, 26)
    btn.clicked.connect(dialog.reject)
    bar_layout.addWidget(btn)

    # 插入到布局最顶部
    layout.insertWidget(0, bar)

    # 拖拽功能
    # 事件过滤器 — 拖拽对话框移动（替代 monkey-patch，可叠加安装）
    _drag_pos = [None]

    class _DialogDragFilter(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    _drag_pos[0] = event.globalPosition().toPoint()
            elif event.type() == QEvent.Type.MouseMove:
                if _drag_pos[0] is not None and event.buttons() == Qt.MouseButton.LeftButton:
                    d = event.globalPosition().toPoint() - _drag_pos[0]
                    dialog.move(dialog.pos() + d)
                    _drag_pos[0] = event.globalPosition().toPoint()
            elif event.type() == QEvent.Type.MouseButtonRelease:
                _drag_pos[0] = None
            return False  # 不消费事件
    dialog.installEventFilter(_DialogDragFilter(dialog))

    # 圆角 + 阴影
    from MF_UI.components.dialog_style import apply_shadow
    apply_shadow(dialog)

    return bar
