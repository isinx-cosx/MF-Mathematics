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
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget,
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


class ResizeEdge(QFrame):
    """窗口底部透明拖拽边 — 流畅调整窗口高度。

    使用 setUpdatesEnabled(False/True) 防止拖拽过程中界面闪烁卡顿。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(5)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setStyleSheet("background: transparent;")
        self._resizing = False
        self._start_y = 0
        self._start_h = 0

    def mousePressEvent(self, event) -> None:
        """记录拖拽起点，暂停界面刷新。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._resizing = True
            self._start_y = event.globalPosition().toPoint().y()
            self._start_h = self.window().height()
            self.window().setUpdatesEnabled(False)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """动态调整窗口高度。"""
        if self._resizing:
            delta_y = event.globalPosition().toPoint().y() - self._start_y
            new_h = max(self.window().minimumHeight(), self._start_h + delta_y)
            self.window().resize(self.window().width(), new_h)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """恢复界面刷新并强制重绘。"""
        if self._resizing:
            self._resizing = False
            self.window().setUpdatesEnabled(True)
            self.window().update()
        super().mouseReleaseEvent(event)


def apply_frameless(window, title: str = "Multifunctional-Mathematics") -> CustomTitleBar:
    """将 QMainWindow 转换为无边框 + 自定义标题栏。

    Returns:
        CustomTitleBar 实例，调用方可 emit 其信号。
    """
    from PySide6.QtWidgets import QVBoxLayout

    # 保存原始内容
    central = window.centralWidget()
    menu_bar = window.menuBar()

    # 收集所有工具栏（QMainWindow 子控件）
    toolbars = [tb for tb in window.findChildren(QWidget)
                if tb.parent() is window and tb is not central]

    # 创建容器
    container = QWidget()
    container.setObjectName("framelessContainer")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # 标题栏（最顶部）
    title_bar = CustomTitleBar(window, title)
    layout.addWidget(title_bar)

    # 菜单栏（标题栏下方）
    if menu_bar:
        menu_bar.setParent(container)
        layout.addWidget(menu_bar)

    # 工具栏（菜单栏下方）
    for tb in toolbars:
        tb.setParent(container)
        layout.addWidget(tb)

    # 原始内容
    if central:
        layout.addWidget(central, 1)

    # 底部拖拽边 — 流畅缩放（ResizeEdge）
    resize_edge = ResizeEdge(container)
    layout.addWidget(resize_edge, 0)

    # 外层透明容器 — 为阴影留出 8px 渲染空间
    outer = QWidget()
    outer.setObjectName("mfShadowHost")
    outer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    outer.setStyleSheet("#mfShadowHost { background: transparent; }")
    outer_layout = QVBoxLayout(outer)
    outer_layout.setContentsMargins(8, 8, 8, 8)
    outer_layout.setSpacing(0)
    outer_layout.addWidget(container)

    window.setCentralWidget(outer)
    # 将 framelessContainer 引用挂到 outer 上，方便外部访问
    outer.setProperty("framelessContainer", container)

    # 主窗口圆角
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    s = window.styleSheet()
    if "border-radius" not in s:
        window.setStyleSheet(s + "QMainWindow { border-radius: 8px; }")

    # 保存动画前状态
    _anim_geo = [None]
    _animating = [False]

    def _animate_max_restore():
        """最大化/还原动画 — 先 QPropertyAnimation 过渡几何，再同步窗口状态。"""
        if _animating[0]:
            return
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        _animating[0] = True
        if window.isMaximized():
            # ── 还原：动画从最大化几何 → 保存的普通几何 ──
            target = _anim_geo[0] if _anim_geo[0] is not None else window.normalGeometry()
            start = window.geometry()
            anim = QPropertyAnimation(window, b"geometry")
            anim.setDuration(150)
            anim.setStartValue(start)
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

            def _on_restore_finished():
                window.showNormal()
                _animating[0] = False

            anim.finished.connect(_on_restore_finished)
            anim.start()
        else:
            # ── 最大化：动画从当前几何 → 屏幕可用几何 ──
            _anim_geo[0] = window.geometry()
            target = screen.availableGeometry()
            anim = QPropertyAnimation(window, b"geometry")
            anim.setDuration(150)
            anim.setStartValue(_anim_geo[0])
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

            def _on_max_finished():
                window.showMaximized()
                _animating[0] = False

            anim.finished.connect(_on_max_finished)
            anim.start()

    def _animate_minimize():
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        _animating[0] = True
        anim = QPropertyAnimation(window, b"windowOpacity")
        anim.setDuration(150)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(window.showMinimized)
        anim.finished.connect(lambda: window.setWindowOpacity(1.0))
        anim.finished.connect(lambda: _animating.__setitem__(0, False))
        anim.start()

    title_bar.minimize_requested.connect(_animate_minimize)
    title_bar.maximize_requested.connect(_animate_max_restore)
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
