# -*- coding: utf-8 -*-
"""自定义标题栏 — 替换原生标题栏，支持暗色/亮色主题。

用法:
    window = QMainWindow(flags=Qt.FramelessWindowHint)
    title_bar = CustomTitleBar(window, "MF-Mathematics")
    window 需自行处理窗口移动、双击最大化等。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint, QSize
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget,
)


class CustomTitleBar(QWidget):
    """MF-Mathematics 风格自定义标题栏。

    信号:
        minimize_requested — 最小化
        maximize_requested — 最大化/还原
        close_requested — 关闭
    """

    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None,
                 title: str = "MF-Mathematics",
                 show_minimize: bool = True,
                 show_maximize: bool = True) -> None:
        super().__init__(parent)
        self._title = title
        self._drag_pos: QPoint | None = None
        self._is_maximized = False

        self.setObjectName("customTitleBar")
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._build_ui(show_minimize, show_maximize)

    def _build_ui(self, show_min: bool, show_max: bool) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 4, 0)
        layout.setSpacing(0)

        # ── 左侧：标题 ──
        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("titlebar_title")
        layout.addWidget(self._title_label)

        layout.addStretch()

        # ── 右侧：窗口控制按钮 ──
        btn_size = QSize(36, 28)

        if show_min:
            btn_min = QPushButton("─")
            btn_min.setObjectName("titlebar_btn_min")
            btn_min.setFixedSize(btn_size)
            btn_min.clicked.connect(self.minimize_requested.emit)
            layout.addWidget(btn_min)

        if show_max:
            self._btn_max = QPushButton("□")
            self._btn_max.setObjectName("titlebar_btn_max")
            self._btn_max.setFixedSize(btn_size)
            self._btn_max.clicked.connect(self.maximize_requested.emit)
            layout.addWidget(self._btn_max)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("titlebar_btn_close")
        btn_close.setFixedSize(btn_size)
        btn_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(btn_close)

    # ── 公开 API ──────────────────────────────────────────────

    def set_title(self, title: str) -> None:
        """更新标题文本。"""
        self._title = title
        self._title_label.setText(title)

    def set_maximized(self, maximized: bool) -> None:
        """切换最大化/还原图标。"""
        self._is_maximized = maximized
        if hasattr(self, '_btn_max'):
            self._btn_max.setText("❐" if maximized else "□")

    def mousePressEvent(self, event) -> None:
        """记录拖拽起点。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """窗口拖拽移动。"""
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            w = self.window()
            if w and not w.isMaximized():
                w.move(w.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """双击标题栏 → 最大化/还原。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_requested.emit()
        super().mouseDoubleClickEvent(event)


def apply_frameless(window, title: str = "Multifunctional-Mathematics") -> CustomTitleBar:
    """将 QMainWindow 转换为无边框 + 自定义标题栏。

    Returns:
        CustomTitleBar 实例，调用方可 emit 其信号。
    """
    from PySide6.QtWidgets import QVBoxLayout

    # 保存原始内容
    central = window.centralWidget()

    # 创建容器
    container = QWidget()
    container.setObjectName("framelessContainer")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # 标题栏
    title_bar = CustomTitleBar(window, title)
    layout.addWidget(title_bar)

    # 原始内容
    if central:
        layout.addWidget(central, 1)

    window.setCentralWidget(container)

    # 连接窗口控制
    title_bar.minimize_requested.connect(window.showMinimized)
    title_bar.maximize_requested.connect(
        lambda: window.showNormal() if window.isMaximized() else window.showMaximized()
    )
    title_bar.close_requested.connect(window.close)

    # 监听最大化变化以更新按钮图标（通过猴子补丁 changeEvent）
    _orig_change = window.changeEvent
    def _patched_change(self, event):
        from PySide6.QtCore import QEvent
        _orig_change(event)
        if event.type() == QEvent.Type.WindowStateChange:
            title_bar.set_maximized(window.isMaximized())
    import types
    window.changeEvent = types.MethodType(_patched_change, window)

    return title_bar
