# -*- coding: utf-8 -*-
"""自定义标题栏 — 替换原生标题栏，支持暗色/亮色主题。

用法:
    window = QMainWindow(flags=Qt.FramelessWindowHint)
    title_bar = CustomTitleBar(window, "MF-Mathematics")
    window 需自行处理窗口移动、双击最大化等。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint, QPointF, QRect, QSize
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget,
)


# ═══════════════════════════════════════════════════════════════════
#  WindowControlButton — 矢量图标标题栏按钮
# ═══════════════════════════════════════════════════════════════════

class WindowControlButton(QPushButton):
    """Windows 11 风格标题栏控制按钮 — QPainter 矢量图标。

    支持:
      - "minimize" — 水平横线
      - "maximize" — 方框 / 双框叠加（还原）
      - "close"     — X 叉号
    自动适配亮色/暗色主题。
    """

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind  # "minimize" | "maximize" | "close"
        self._hovered = False
        self._pressed = False
        self._maximized = False  # 仅 maximize 类型使用

        self.setFixedSize(46, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("background: transparent; border: none;")

    # ── 公开 API ──────────────────────────────────────────────

    def set_maximized_state(self, maximized: bool) -> None:
        """切换最大化/还原图标。"""
        if self._kind == "maximize" and self._maximized != maximized:
            self._maximized = maximized
            self.update()

    # ── 事件 ──────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        """矢量绘制按钮图标。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self.rect()
        is_dark = self._detect_dark_theme()
        is_close = self._kind == "close"

        # ── 背景（关闭按钮右上角 8px 圆角，适配窗口圆角）──
        def _fill_bg(color):
            if is_close:
                path = QPainterPath()
                path.moveTo(r.topLeft())
                path.lineTo(QPointF(r.right() - 8, r.top()))
                path.quadTo(r.topRight(), QPointF(r.right(), r.top() + 8))
                path.lineTo(r.bottomRight())
                path.lineTo(r.bottomLeft())
                path.closeSubpath()
                p.fillPath(path, color)
            else:
                p.fillRect(r, color)

        if self._hovered:
            _fill_bg(QColor("#e81123") if is_close
                     else QColor(255, 255, 255, 20) if is_dark
                     else QColor(0, 0, 0, 12))
        elif self._pressed:
            _fill_bg(QColor("#bf0f1d") if is_close
                     else QColor(255, 255, 255, 30) if is_dark
                     else QColor(0, 0, 0, 20))

        # ── 图标颜色 ──
        if is_close and (self._hovered or self._pressed):
            icon_color = QColor("#ffffff")
        elif self._hovered:
            icon_color = QColor("#cdd6f4") if is_dark else QColor("#334155")
        else:
            icon_color = QColor("#a6adc8") if is_dark else QColor("#64748b")

        pen = QPen(icon_color, 1.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        # ── 图标路径（居中 10×10 区域）─
        icon_sz = 10
        cx, cy = r.center().x(), r.center().y()
        x, y = cx - icon_sz // 2, cy - icon_sz // 2

        if self._kind == "minimize":
            p.drawLine(QPoint(x + 1, cy), QPoint(x + icon_sz - 1, cy))

        elif self._kind == "maximize":
            if self._maximized:
                # 还原图标：两个重叠方框
                offset = 2
                # 后方框（右下）
                p.drawRect(QRect(x + offset, y, icon_sz, icon_sz))
                # 前方框填充背景（覆盖后方框交叠区域）
                bg = QColor("#181825") if is_dark else QColor("#f8fafc")
                if self._hovered:
                    bg = QColor(255, 255, 255, 20) if is_dark else QColor(0, 0, 0, 12)
                p.fillRect(QRect(x, y + offset, icon_sz, icon_sz), bg)
                p.drawRect(QRect(x, y + offset, icon_sz, icon_sz))
            else:
                # 最大化图标：单个方框
                p.drawRect(QRect(x, y, icon_sz, icon_sz))

        elif self._kind == "close":
            p.drawLine(QPoint(x + 1, y + 1),
                       QPoint(x + icon_sz - 1, y + icon_sz - 1))
            p.drawLine(QPoint(x + icon_sz - 1, y + 1),
                       QPoint(x + 1, y + icon_sz - 1))

        p.end()

    def _detect_dark_theme(self) -> bool:
        """检测主窗口当前主题。"""
        w = self.window()
        if w and hasattr(w, '_current_theme'):
            return w._current_theme == "dark"
        return True  # 默认暗色


# ═══════════════════════════════════════════════════════════════════
#  CustomTitleBar
# ═══════════════════════════════════════════════════════════════════

class CustomTitleBar(QWidget):
    """MF-Mathematics 风格自定义标题栏。

    信号:
        minimize_requested — 最小化
        maximize_requested — 最大化/还原
        close_requested     — 关闭
    """

    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None,
                 title: str = "MF-Mathematics",
                 icon_path: str = "",
                 show_minimize: bool = True,
                 show_maximize: bool = True) -> None:
        super().__init__(parent)
        self._title = title
        self._icon_path = icon_path
        self._drag_pos: QPoint | None = None
        self._drag_start_offset: QPoint = QPoint()

        self.setObjectName("customTitleBar")
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._build_ui(show_minimize, show_maximize)

    def _build_ui(self, show_min: bool, show_max: bool) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(6)

        # ── 左侧：图标（16px，适配标题栏高度）──
        if self._icon_path:
            self._icon_label = QLabel()
            self._icon_label.setObjectName("titlebar_icon")
            self._icon_label.setFixedSize(24, 24)
            self._icon_label.setScaledContents(True)
            icon = QIcon(self._icon_path)
            self._icon_label.setPixmap(icon.pixmap(24, 24))
            layout.addWidget(self._icon_label)
        else:
            self._icon_label = None

        # ── 左侧：标题 ──
        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("titlebar_title")
        layout.addWidget(self._title_label)

        layout.addStretch()

        # ── 右侧：窗口控制按钮（矢量图标）──
        if show_min:
            self._btn_min = WindowControlButton("minimize", self)
            self._btn_min.setObjectName("titlebar_btn_min")
            self._btn_min.clicked.connect(self.minimize_requested.emit)
            layout.addWidget(self._btn_min)
        else:
            self._btn_min = None

        if show_max:
            self._btn_max = WindowControlButton("maximize", self)
            self._btn_max.setObjectName("titlebar_btn_max")
            self._btn_max.clicked.connect(self.maximize_requested.emit)
            layout.addWidget(self._btn_max)
        else:
            self._btn_max = None

        self._btn_close = WindowControlButton("close", self)
        self._btn_close.setObjectName("titlebar_btn_close")
        self._btn_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(self._btn_close)

    # ── 公开 API ──────────────────────────────────────────────

    def set_title(self, title: str) -> None:
        """更新标题文本。"""
        self._title = title
        self._title_label.setText(title)

    def set_maximized(self, maximized: bool) -> None:
        """切换最大化/还原图标。"""
        if self._btn_max is not None:
            self._btn_max.set_maximized_state(maximized)

    # ── 窗口拖拽 ──────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        """记录拖拽起点和鼠标在标题栏内的偏移（用于最大化时拖拽还原定位）。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            self._drag_start_offset = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """窗口拖拽移动 — 最大化时拖拽自动还原（模拟 Windows 原生行为）。"""
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            w = self.window()
            if w is not None:
                if w.isMaximized():
                    # ── 最大化状态下拖拽：还原窗口并跟随鼠标 ──
                    if delta.manhattanLength() < 5:
                        return  # 阈值过滤，防止误触
                    # 计算鼠标在最大化标题栏上的比例位置
                    max_geo = w.geometry()
                    ratio_x = ((self._drag_pos.x() - max_geo.x()) / max_geo.width()
                               if max_geo.width() > 0 else 0.5)
                    # 获取还原几何（由 changeEvent / resizeEvent 持续保存）
                    restore_geo = getattr(w, '_normal_geometry', None)
                    if restore_geo is None or not restore_geo.isValid():
                        restore_geo = w.normalGeometry()
                    # 直接还原（跳过动画），触发 changeEvent 更新标题栏图标
                    w.showNormal()
                    if restore_geo.isValid():
                        new_x = int(event.globalPosition().toPoint().x()
                                    - ratio_x * restore_geo.width())
                        new_y = int(event.globalPosition().toPoint().y()
                                    - self._drag_start_offset.y())
                        w.setGeometry(new_x, new_y,
                                      restore_geo.width(), restore_geo.height())
                    # 重置拖拽起点（防止窗口跳动）
                    self._drag_pos = event.globalPosition().toPoint()
                    self._drag_start_offset = QPoint(
                        int(ratio_x * (restore_geo.width() if restore_geo.isValid()
                                       else w.width())),
                        self._drag_start_offset.y(),
                    )
                else:
                    # ── 正常状态：跟随鼠标移动窗口 ──
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


# ═══════════════════════════════════════════════════════════════════
#  ResizeEdge — 底部流畅缩放拖拽边
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
#  apply_frameless — 主窗口无边框包装
# ═══════════════════════════════════════════════════════════════════

def apply_frameless(window, title: str = "Multifunctional-Mathematics") -> CustomTitleBar:
    """将 QMainWindow 转换为无边框 + 自定义标题栏。

    Returns:
        CustomTitleBar 实例，调用方可 emit 其信号。
    """
    from PySide6.QtWidgets import QVBoxLayout

    # 保存原始内容
    central = window.centralWidget()
    menu_bar = window.menuBar()

    # 收集所有工具栏（QMainWindow 子控件，排除 QStatusBar）
    from PySide6.QtWidgets import QStatusBar as _QSB
    toolbars = [tb for tb in window.findChildren(QWidget)
                if tb.parent() is window
                and tb is not central
                and not isinstance(tb, _QSB)]

    # 创建容器
    container = QWidget()
    container.setObjectName("framelessContainer")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # 标题栏（最顶部）
    import os as _os
    _icon = _os.path.join(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))), "assets", "icon.ico")
    if not _os.path.exists(_icon):
        _icon = ""
    title_bar = CustomTitleBar(window, title, icon_path=_icon)
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

    # 外层透明容器 — 12px 均匀边距为圆角 + 阴影留出渲染空间
    outer = QWidget()
    outer.setObjectName("mfShadowHost")
    outer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    outer.setStyleSheet("#mfShadowHost { background: transparent; }")
    outer_layout = QVBoxLayout(outer)
    outer_layout.setContentsMargins(12, 12, 12, 12)
    outer_layout.setSpacing(0)
    outer_layout.addWidget(container, 1)

    window.setCentralWidget(outer)
    outer.setProperty("framelessContainer", container)

    # 主窗口圆角 — 依赖 WA_TranslucentBackground + QSS border-radius:12px
    # 均匀 12px 透明边距使四角自然圆润，无需 setMask（无法抗锯齿）
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def _apply_rounded_mask():
        """最大化时清除假性蒙版（实际上无蒙版，仅保持接口兼容）。"""
        # QSS border-radius + 均匀透明边距已处理圆角，无需 setMask
        pass

    _apply_rounded_mask()
    window._apply_rounded_mask = _apply_rounded_mask

    # ── 动画状态与持久引用（防止 GC 回收）──
    _anim_geo = [None]       # 保存的最大化前几何
    _animating = [False]     # 动画进行中标志
    _anim_ref = [None]       # ★ 持久持有动画对象，防止 QPropertyAnimation GC

    # 缓存 shadow effect 引用 — 动画期间临时禁用，避免阴影重绘引起卡顿
    _shadow_effect = [None]

    def _get_screen():
        """获取窗口所在屏幕（回退到主屏幕）。"""
        from PySide6.QtWidgets import QApplication
        s = window.screen()
        return s if s else QApplication.primaryScreen()

    def _toggle_shadow(enabled: bool):
        """动画期间禁用阴影效果，减少重绘开销。最大化时始终禁用（边距归零，阴影溢出）。"""
        if _shadow_effect[0] is None:
            _shadow_effect[0] = container.graphicsEffect()
        if _shadow_effect[0] is not None:
            _shadow_effect[0].setEnabled(enabled and not window.isMaximized())

    def _animate_max_restore():
        """最大化/还原动画 — 平滑几何过渡。"""
        if _animating[0]:
            return
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        from PySide6.QtWidgets import QApplication
        screen = _get_screen()
        if screen is None:
            return
        _animating[0] = True
        window._geometry_locked = True  # 动画期间禁止 resizeEvent 覆盖还原几何
        _toggle_shadow(False)  # 动画期间关闭阴影

        if window.isMaximized():
            # ── 还原：直接在最大化状态下动画几何（经测试 setGeometry 有效），
            #     动画结束后 showNormal() 同步状态（此时几何已匹配，无跳跃）──
            target = _anim_geo[0] if _anim_geo[0] is not None else window.normalGeometry()
            anim = QPropertyAnimation(window, b"geometry")
            anim.setDuration(150)
            anim.setStartValue(window.geometry())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

            def _on_restore_finished():
                window.showNormal()
                window._normal_geometry = target
                window._geometry_locked = False
                _animating[0] = False
                _toggle_shadow(True)

            anim.finished.connect(_on_restore_finished)
            _anim_ref[0] = anim
            anim.start()
        else:
            # ── 最大化：动画从当前几何 → 屏幕可用几何 ──
            _anim_geo[0] = window.geometry()
            window._normal_geometry = _anim_geo[0]  # 保存还原几何供拖拽使用
            target = screen.availableGeometry()
            anim = QPropertyAnimation(window, b"geometry")
            anim.setDuration(150)
            anim.setStartValue(_anim_geo[0])
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

            def _on_max_finished():
                window.showMaximized()
                # showMaximized() 触发 changeEvent → 手动纠正几何（消除缝隙）
                window._geometry_locked = False
                _animating[0] = False
                _toggle_shadow(True)

            anim.finished.connect(_on_max_finished)
            _anim_ref[0] = anim
            anim.start()

    def _animate_minimize():
        """最小化动画 — 淡出 150ms。"""
        if _animating[0]:
            return
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        _animating[0] = True
        _toggle_shadow(False)
        anim = QPropertyAnimation(window, b"windowOpacity")
        anim.setDuration(150)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)

        def _on_min_finished():
            window.showMinimized()
            window.setWindowOpacity(1.0)
            _animating[0] = False
            _toggle_shadow(True)

        anim.finished.connect(_on_min_finished)
        _anim_ref[0] = anim
        anim.start()

    title_bar.minimize_requested.connect(_animate_minimize)
    title_bar.maximize_requested.connect(_animate_max_restore)
    title_bar.close_requested.connect(window.close)

    # 监听最大化变化以更新按钮图标（事件过滤器 → 无 monkey-patch 链断裂风险）
    from PySide6.QtCore import QObject as _QObj, QEvent as _QE

    class _WindowStateFilter(_QObj):
        def eventFilter(self, obj, event):
            if event.type() == _QE.Type.WindowStateChange:
                title_bar.set_maximized(window.isMaximized())
            return False  # 不消费事件，继续传递
    window.installEventFilter(_WindowStateFilter(window))

    return title_bar
