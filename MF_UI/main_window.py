"""MF-Mathematics 主窗口"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PySide6.QtCore import Qt, QEvent, QObject, QPoint, QRect, QSize
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar,
    QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QApplication, QComboBox, QDialog,
    QPushButton, QLineEdit, QToolButton,
)
from calc.algebra import Workspace as AlgebraWorkspace
from calc.calculus import Workspace as CalculusWorkspace
from calc.analytic_geometry import Workspace as AnalyticGeometryWorkspace
from calc.linear_algebra import Workspace as LinearAlgebraWorkspace
from calc.numerical import Workspace as NumericalWorkspace
from calc.number_theory import Workspace as NumberTheoryWorkspace
from calc.probability import Workspace as ProbabilityWorkspace
from calc.real_analysis import Workspace as RealAnalysisWorkspace
from calc.sequences import Workspace as SequencesWorkspace
from calc.complex_analysis import Workspace as ComplexAnalysisWorkspace
from calc.functional_analysis import Workspace as FunctionalAnalysisWorkspace
from calc.algebraic_topology import Workspace as AlgebraicTopologyWorkspace
from calc.measure_theory import Workspace as MeasureTheoryWorkspace
from plot.basic.workspace import PlotWorkspace
from plot.fractal.workspace import FractalWorkspace

# 运行时自动设置项目根路径
_this_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_this_dir)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

# ═══════════════════════════════════════════════════════════════
#  EdgeResizeFilter — 无边框窗口边缘缩放（全局事件拦截）
# ═══════════════════════════════════════════════════════════════

class EdgeResizeFilter(QObject):
    """全局事件过滤器 — 拦截主窗口边缘鼠标事件，委托系统原生缩放。

    检测鼠标是否处于窗口边缘 8px，设置对应光标；
    鼠标按下时调用 QWindow.startSystemResize() 委托 Windows 原生缩放
    （模态缩放循环，GPU 垂直同步，完美平滑）。
    """

    _BORDER = 8

    # 边缘 → 光标 & Qt.Edge 映射
    _EDGE_MAP: dict[str, tuple] = {
        "top":         (Qt.CursorShape.SizeVerCursor,  Qt.Edge.TopEdge),
        "bottom":      (Qt.CursorShape.SizeVerCursor,  Qt.Edge.BottomEdge),
        "left":        (Qt.CursorShape.SizeHorCursor,  Qt.Edge.LeftEdge),
        "right":       (Qt.CursorShape.SizeHorCursor,  Qt.Edge.RightEdge),
        "topleft":     (Qt.CursorShape.SizeFDiagCursor, Qt.Edge.TopEdge | Qt.Edge.LeftEdge),
        "bottomright": (Qt.CursorShape.SizeFDiagCursor, Qt.Edge.BottomEdge | Qt.Edge.RightEdge),
        "topright":    (Qt.CursorShape.SizeBDiagCursor, Qt.Edge.TopEdge | Qt.Edge.RightEdge),
        "bottomleft":  (Qt.CursorShape.SizeBDiagCursor, Qt.Edge.BottomEdge | Qt.Edge.LeftEdge),
    }

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(parent=window)
        self._win = window
        QApplication.instance().installEventFilter(self)

    # ── 边缘检测 ──────────────────────────────────────────────

    def _hit_edge(self, pos: QPoint) -> str | None:
        """判断窗口局部坐标是否命中边缘/角。"""
        r = self._win.rect()
        b = self._BORDER
        on_l = pos.x() < b
        on_r = pos.x() > r.width() - b
        on_t = pos.y() < b
        on_b = pos.y() > r.height() - b

        if on_t and on_l:
            return "topleft"
        if on_t and on_r:
            return "topright"
        if on_b and on_l:
            return "bottomleft"
        if on_b and on_r:
            return "bottomright"
        if on_t:
            return "top"
        if on_b:
            return "bottom"
        if on_l:
            return "left"
        if on_r:
            return "right"
        return None

    # ── 事件过滤 ──────────────────────────────────────────────

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """拦截边缘鼠标事件：移动更新光标，按下启动原生缩放。"""
        # 只处理属于主窗口（或其子孙）的事件
        try:
            if (obj is not self._win and
                    (not hasattr(obj, "window") or obj.window() is not self._win)):
                return False
        except Exception:
            return False

        t = event.type()

        # ── 鼠标移动：更新光标 ──
        if t == QEvent.Type.MouseMove:
            local = self._win.mapFromGlobal(event.globalPosition().toPoint())
            hit = self._hit_edge(local)
            if hit and not self._win.isMaximized():
                self._win.setCursor(self._EDGE_MAP[hit][0])
            else:
                self._win.unsetCursor()

        # ── 鼠标按下边缘 → 委托 Windows 原生缩放（模态循环，完美平滑）──
        elif (t == QEvent.Type.MouseButtonPress and
              event.button() == Qt.MouseButton.LeftButton and
              not self._win.isMaximized()):
            local = self._win.mapFromGlobal(event.globalPosition().toPoint())
            hit = self._hit_edge(local)
            if hit:
                handle = self._win.windowHandle()
                if handle is not None:
                    handle.startSystemResize(self._EDGE_MAP[hit][1])
                return True  # 消费事件

        return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(flags=Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle("Multifunctional-Mathematics")

        # 窗口图标（任务栏 + Alt+Tab）— 适配开发/打包两种环境
        if getattr(sys, 'frozen', False):
            _ico = os.path.join(sys._MEIPASS, "assets", "icon.ico")
        else:
            _ico = os.path.join(_root_dir, "assets", "icon.ico")
        if os.path.exists(_ico):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(_ico))

        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        self._center_on_screen()

        self._current_theme = "light"
        self._current_mode = 0
        # 计算历史栈（撤销/重做）
        self._calc_history: list[str] = []
        self._history_pos = -1
        self._max_history = 50

        self._calc_modes = [
            "代数计算", "微积分", "解析几何", "数列",
            "线性代数", "概率论与数理统计", "数值分析",
            "数论", "实分析", "泛函分析", "复分析",
            "代数拓扑", "测度论",
        ]
        self._plot_modes = ["普通模式", "极坐标", "3D模式", "复数模式", "向量场", "任意做图", "分形探索"]
        self.last_calc_index = 0
        self.last_plot_index = 0

        # 最大化/还原状态管理
        self._normal_geometry: QRect | None = None  # 最大化前窗口几何
        self._geometry_locked: bool = False           # 动画期间锁定几何保存

        self._build_menu_bar()
        self._build_toolbar()
        self._build_central_area()

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._light_qss_path = os.path.join(base_dir, "styles", "light.qss")
        self._dark_qss_path = os.path.join(base_dir, "styles", "dark.qss")
        self._apply_theme(self._light_qss_path)

        # 自定义标题栏（替换原生标题栏）
        from components.custom_title_bar import apply_frameless
        self._title_bar = apply_frameless(self, "Multifunctional-Mathematics")

        # 窗口阴影 — 柔光边缘效果（最大化时禁用，防止边缘溢出造成视觉缝隙）
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor
        self._window_shadow: QGraphicsDropShadowEffect | None = None
        _outer = self.centralWidget()
        if _outer is not None:
            _container = _outer.property("framelessContainer")
            if _container is not None:
                self._window_shadow = QGraphicsDropShadowEffect(_container)
                self._window_shadow.setBlurRadius(15)
                self._window_shadow.setOffset(0, 0)
                self._window_shadow.setColor(QColor(0, 0, 0, 40))
                _container.setGraphicsEffect(self._window_shadow)

        # 安装全局边缘缩放过滤器（8px 边角，setUpdatesEnabled 防闪烁）
        self._edge_filter = EdgeResizeFilter(self)

        # 重新居中（frameless 切换可能改变窗口位置）
        self._center_on_screen()

        # 注册教程系统 UI 元素
        self._register_tutorial_elements()

        # 首次启动：显示欢迎对话框
        QApplication.instance().processEvents()
        self._check_first_launch()

    # ---------- 窗口居中 ----------
    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

    # ---------- 窗口状态变化 ----------
    def showEvent(self, event) -> None:
        """窗口显示时 — 最大化状态使用 availableGeometry（不遮挡任务栏）。"""
        super().showEvent(event)
        if self.isMaximized():
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                self.setGeometry(screen.availableGeometry())

    def changeEvent(self, event: QEvent) -> None:
        """窗口状态变化 — 最大化使用 availableGeometry（不遮挡任务栏），还原恢复保存几何。

        无边框窗口（FramelessWindowHint）在 Windows 上最大化时：
        1. 外容器 8px 边距（用于阴影）需归零
        2. QGraphicsDropShadowEffect 需禁用（阴影在边缘外绘制造成视觉缝隙）
        3. 使用 availableGeometry — 停在任务栏上方，不遮挡
        还原时恢复到 _normal_geometry 保存的位置和大小。
        """
        if event.type() == QEvent.Type.WindowStateChange:
            outer = self.centralWidget()
            if self.isMaximized():
                # 消除外容器边距 + 禁用阴影
                if outer is not None:
                    outer.layout().setContentsMargins(0, 0, 0, 0)
                if self._window_shadow is not None:
                    self._window_shadow.setEnabled(False)
                # availableGeometry — 停在任务栏上方，不遮挡
                screen = self.screen() or QApplication.primaryScreen()
                if screen is not None:
                    self.setGeometry(screen.availableGeometry())
            elif self._normal_geometry is not None:
                # 还原外容器边距 + 启用阴影 + 恢复到保存的正常几何
                if outer is not None:
                    outer.layout().setContentsMargins(12, 12, 12, 12)
                if self._window_shadow is not None:
                    self._window_shadow.setEnabled(True)
                self.setGeometry(self._normal_geometry)
            # 更新标题栏最大化图标
            if hasattr(self, '_title_bar') and self._title_bar is not None:
                self._title_bar.set_maximized(self.isMaximized())
        super().changeEvent(event)

    def moveEvent(self, event) -> None:
        """窗口移动时保存正常状态几何（用于最大化后还原）。"""
        super().moveEvent(event)
        if not self.isMaximized() and not self._geometry_locked:
            self._normal_geometry = self.geometry()

    # ---------- 菜单栏 ----------
    def _build_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("文件")
        act_save = QAction("保存工作区", self)
        act_save.triggered.connect(self._save_workspace)
        file_menu.addAction(act_save)
        act_load = QAction("加载工作区", self)
        act_load.triggered.connect(self._load_workspace)
        file_menu.addAction(act_load)
        file_menu.addSeparator()
        act_exit = QAction("退出", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        edit_menu = menu_bar.addMenu("编辑")
        act_undo = QAction("撤销\tCtrl+Z", self)
        act_undo.triggered.connect(self._undo)
        edit_menu.addAction(act_undo)
        act_redo = QAction("重做\tCtrl+Y", self)
        act_redo.triggered.connect(self._redo)
        edit_menu.addAction(act_redo)
        edit_menu.addSeparator()
        act_clear = QAction("清空历史", self)
        act_clear.triggered.connect(self._clear_history)
        edit_menu.addAction(act_clear)

        view_menu = menu_bar.addMenu("视图")
        act_light = QAction("亮色主题", self)
        act_light.triggered.connect(self._switch_to_light)
        view_menu.addAction(act_light)
        act_dark = QAction("暗色主题", self)
        act_dark.triggered.connect(self._switch_to_dark)
        view_menu.addAction(act_dark)

        help_menu = menu_bar.addMenu("帮助")
        act_help_browser = QAction("帮助文档\tF1", self)
        act_help_browser.triggered.connect(self._open_help_browser)
        help_menu.addAction(act_help_browser)
        act_walkthrough = QAction("交互式引导", self)
        act_walkthrough.triggered.connect(self._open_guided_walkthrough)
        help_menu.addAction(act_walkthrough)
        act_examples = QAction("示例任务库", self)
        act_examples.triggered.connect(self._open_example_library)
        help_menu.addAction(act_examples)
        help_menu.addSeparator()
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._open_about_dialog)
        help_menu.addAction(act_about)

    # ---------- 工具栏 ----------
    def _build_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        # ── QActionGroup 互斥：先入组，再设初始选中 ──
        # 关键：QActionGroup.triggered 发送 QAction*（非 bool），
        # 而 QAction.triggered 发送 bool(checked)。前者才能正确识别按钮。
        self._btn_group = QActionGroup(self)
        self._btn_group.setExclusive(True)

        self._btn_calc = toolbar.addAction("计算")
        self._btn_calc.setCheckable(True)
        self._btn_group.addAction(self._btn_calc)

        self._btn_plot = toolbar.addAction("绘图")
        self._btn_plot.setCheckable(True)
        self._btn_group.addAction(self._btn_plot)

        # 全部入组后再设初始选中（QActionGroup 内部状态一致）
        self._btn_calc.setChecked(True)

        # 给 QToolButton widget 设置 objectName — QSS ID 选择器直接定位
        calc_widget = toolbar.widgetForAction(self._btn_calc)
        if calc_widget is not None:
            calc_widget.setObjectName("tb_calc_btn")
        plot_widget = toolbar.widgetForAction(self._btn_plot)
        if plot_widget is not None:
            plot_widget.setObjectName("tb_plot_btn")

        self._btn_group.triggered.connect(self._on_toolbar_action)

        toolbar.addSeparator()
        
        self._sub_combo = QComboBox()
        self._sub_combo.setFixedWidth(140)
        self._sub_combo.addItems(self._calc_modes)
        toolbar.addWidget(self._sub_combo)
        self._sub_combo.currentIndexChanged.connect(self._on_sub_mode_changed)

        
        toolbar.addSeparator()

        self._act_search = toolbar.addAction("搜索")
        self._act_search.triggered.connect(self._open_search_panel)

        self._search_panel: object | None = None
        self._act_history = toolbar.addAction("历史")
        self._act_history.triggered.connect(self._open_history)
        self._act_ai = toolbar.addAction("AI")
        self._act_ai.triggered.connect(self._open_ai_dialog)
        self._act_settings = toolbar.addAction("设置")
        self._act_settings.triggered.connect(self._open_settings)

        toolbar.addSeparator()
        self._user_action = toolbar.addAction("登录")
        self._user_action.triggered.connect(self._on_user_clicked)

        toolbar.addSeparator()
        self._act_help = toolbar.addAction("帮助")
        self._act_help.triggered.connect(self._open_help_browser)

        # F1 快捷键
        self._shortcut_f1 = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        self._shortcut_f1.activated.connect(self._open_help_browser)

        # ── 教程系统 ──
        self._tutorial_elements: dict[str, QWidget] = {}
        self._walkthrough: object | None = None
        self._help_browser: object | None = None
        self._example_library: object | None = None

        # ── 用户系统 ──
        self._user_status_label: QLabel | None = None

    def _on_toolbar_action(self, action):
        """工具栏按钮互斥 + 模式切换 — QActionGroup 自动互斥，isChecked 防二次触发。

        QActionGroup.triggered 发送 QAction*（非 bool），
        QActionGroup.setExclusive(True) 自动管理 checked 互斥。
        当 _switch_mode 程序化调用 setChecked 时，
        QActionGroup 会再次 emit triggered，isChecked 守卫确保只处理被选中的按钮。
        """
        self._push_history()
        if action is self._btn_calc and self._btn_calc.isChecked():
            self._switch_mode(0)
        elif action is self._btn_plot and self._btn_plot.isChecked():
            self._switch_mode(1)

    def _switch_mode(self, mode: int):
        """切换计算/绘图模式 — 同步 combo box、stacked widget 和工具栏按钮。

        所有模式切换路径（用户点击、教程加载、程序化调用）最终汇聚于此，
        _current_mode 守卫防止递归（QActionGroup 在 setChecked 后二次 emit triggered）。
        """
        if self._current_mode == mode:
            return

        self._current_mode = mode

        # ── 1. 同步工具栏按钮（四层：QAction + QToolButton + 动态属性 + repolish）──
        self._sync_toolbar_buttons()

        # ── 2. 更新子模式下拉框 ──
        self._sub_combo.blockSignals(True)
        self._sub_combo.clear()

        if mode == 0:
            self._sub_combo.addItems(self._calc_modes)
            restore_index = self.last_calc_index
            self._status_msg("切换到计算模式")
        else:
            self._sub_combo.addItems(self._plot_modes)
            restore_index = self.last_plot_index
            self._status_msg("切换到绘图模式")

        if restore_index < self._sub_combo.count():
            self._sub_combo.setCurrentIndex(restore_index)

        self._sub_combo.blockSignals(False)

        # ── 3. 切换 stacked widget ──
        if restore_index < self._sub_combo.count():
            self._on_sub_mode_changed(restore_index)

    def _sync_toolbar_buttons(self) -> None:
        """强制工具栏按钮 checked 状态 + 动态属性 + re-polish。

        Qt 样式表引擎在 QAction.checked 变化时不会自动 re-polish 关联的
        QToolButton widget → :checked 伪状态可能滞后。此方法绕过伪状态：
        1. setChecked 同步 QAction + QToolButton 双层
        2. setProperty("checked", bool) → QSS [checked="true"] 动态属性选择器
        3. unpolish/polish/update 强制样式重新计算
        """
        toolbar: QToolBar | None = self.findChild(QToolBar)
        if toolbar is None:
            return
        for btn in toolbar.findChildren(QToolButton):
            action = btn.defaultAction()
            if action is self._btn_calc:
                target = self._current_mode == 0
            elif action is self._btn_plot:
                target = self._current_mode == 1
            else:
                continue
            # 1. QAction 层
            if action.isChecked() != target:
                action.setChecked(target)
            # 2. QToolButton widget 层
            if btn.isChecked() != target:
                btn.setChecked(target)
            # 3. 动态属性 — QSS QToolButton#id[checked="true"] 匹配
            btn.setProperty("checked", target)
            # 4. 强制样式重新计算（核心修复）
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def _on_sub_mode_changed(self, index: int):
        if self._current_mode == 0:  # 计算模式
            self.last_calc_index = index
            self._stacked_widget.setCurrentIndex(index)  # 索引 0~12
        else:  # 绘图模式
            self.last_plot_index = index
            self._stacked_widget.setCurrentIndex(13 + index)  # 索引 13~19


    # ---------- 中央区域 ----------
    def _build_central_area(self):
        self._stacked_widget = QStackedWidget()
        # ── 计算模式 (index 0-12) ──
        self._stacked_widget.addWidget(AlgebraWorkspace())
        self._stacked_widget.addWidget(CalculusWorkspace())
        self._stacked_widget.addWidget(AnalyticGeometryWorkspace())
        self._stacked_widget.addWidget(SequencesWorkspace())
        self._stacked_widget.addWidget(LinearAlgebraWorkspace())
        self._stacked_widget.addWidget(ProbabilityWorkspace())
        self._stacked_widget.addWidget(NumericalWorkspace())
        self._stacked_widget.addWidget(NumberTheoryWorkspace())
        self._stacked_widget.addWidget(RealAnalysisWorkspace())
        self._stacked_widget.addWidget(FunctionalAnalysisWorkspace())
        self._stacked_widget.addWidget(ComplexAnalysisWorkspace())
        self._stacked_widget.addWidget(AlgebraicTopologyWorkspace())
        self._stacked_widget.addWidget(MeasureTheoryWorkspace())
        # ── 绘图模式 (index 13-19) ──
        self._stacked_widget.addWidget(PlotWorkspace("普通模式 — 2D 函数绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("极坐标 — r = f(θ) 绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("3D 模式 — 三维曲面绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("复数模式 — 复平面域着色绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("向量场模式 — 向量场绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("任意做图 — 自由几何对象绘制"))
        self._stacked_widget.addWidget(FractalWorkspace("分形探索 — Julia/Mandelbrot 集"))

        # 内置键盘面板
        self._build_keyboard_panel()

    # 切换按钮 — 左下角
        self._kb_toggle_btn = QPushButton("键盘")
        self._kb_toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._kb_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kb_toggle_btn.setObjectName("kb_toggle_btn")
        self._kb_toggle_btn.clicked.connect(self._toggle_keyboard_panel)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(8, 2, 0, 2)
        btn_row.addWidget(self._kb_toggle_btn)
        btn_row.addStretch()

    # ── 容器：一个 container，一个 layout ──
        container = QWidget()
        container.setObjectName("framelessContainer")
        container.setAttribute(Qt.WA_TranslucentBackground, True)
        container.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._stacked_widget, 1)      # 中央区域
        layout.addLayout(btn_row)                      # 键盘切换按钮
        layout.addWidget(self.keyboard_panel, 0)       # 键盘面板

    # ── 状态栏 ──
        self._status_bar = QStatusBar(container)
        self._status_bar.setFixedHeight(30)
        self._status_bar.setSizeGripEnabled(False)  # 禁用内置size grip，否则矩形手柄冲破右下角圆角
        self._status_bar.showMessage("就绪")
        self._user_status_label = QLabel("未登录")
        self._user_status_label.setObjectName("user_status_label")
        self._status_bar.addPermanentWidget(self._user_status_label)
        self._refresh_user_status()
        brand_label = QLabel("MF-Vis-Science · 开放工作室")
        brand_label.setObjectName("brand_label")
        self._status_bar.addPermanentWidget(brand_label)

        layout.addWidget(self._status_bar, 0)

        self.setCentralWidget(container)

    # ================================================================
    #  内置键盘面板
    # ================================================================
    def _build_keyboard_panel(self):
        from MF_UI.math_keyboard import KeyboardPanel
        self.keyboard_panel = KeyboardPanel(self)

    # ---------- 状态栏（已在 _build_central_area 中创建并加入布局）----------
    def _status_msg(self, msg: str):
        self._status_bar.showMessage(msg, 5000)

    def _open_ai_dialog(self):
        """打开 AI 助手对话框 — 先检查配置，传递当前计算上下文。"""
        from MF_UI.dialogs.ai_dialog import AIDialog
        from MF_AI.config import Config

        cfg = Config()
        if not cfg.is_available():
            from MF_UI.dialogs.ai_config_prompt import AIConfigPrompt
            dlg = AIConfigPrompt(self)
            dlg.exec()
            if dlg.go_to_settings():
                self._open_settings(open_ai_tab=True)
            return

        expr, mode = self._get_calc_context()
        dlg = AIDialog(self, context_expr=expr, context_mode=mode)
        dlg.exec()

    def _open_settings(self, open_ai_tab: bool = False):
        """打开设置对话框。"""
        from MF_UI.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self, open_ai_tab=open_ai_tab)
        dlg.exec()

    # ── 撤销/重做 ──────────────────────────────────────────

    def _push_history(self) -> None:
        """保存当前表达式到历史栈。"""
        expr = self._get_calc_context()[0]
        if expr:
            self._calc_history = self._calc_history[:self._history_pos + 1]
            self._calc_history.append(expr)
            if len(self._calc_history) > self._max_history:
                self._calc_history.pop(0)
            self._history_pos = len(self._calc_history) - 1

    def _undo(self) -> None:
        if self._history_pos > 0:
            self._history_pos -= 1
            self._restore_expression(self._calc_history[self._history_pos])
            self._status_msg("已撤销")

    def _redo(self) -> None:
        if self._history_pos < len(self._calc_history) - 1:
            self._history_pos += 1
            self._restore_expression(self._calc_history[self._history_pos])
            self._status_msg("已重做")

    def _clear_history(self) -> None:
        self._calc_history.clear()
        self._history_pos = -1
        self._status_msg("历史已清空")

    def _restore_expression(self, expr: str) -> None:
        """将表达式恢复到当前计算块的输入框。"""
        try:
            w = self._stacked_widget.currentWidget()
            if w:
                for child in w.findChildren(QLineEdit):
                    if hasattr(child, 'isVisible') and child.isVisible():
                        child.setText(expr)
                        return
        except Exception as _e:
            import logging
            logging.getLogger("MF-Mathematics").debug("恢复表达式失败: %s", _e)

    # ── 保存/加载工作区 ─────────────────────────────────────

    def _save_workspace(self) -> None:
        """保存当前工作区到 JSON 文件。"""
        import json as _json
        expr, mode = self._get_calc_context()
        data = {
            "expression": expr,
            "mode": mode,
            "calc_mode": self._calc_modes[self.last_calc_index] if self._current_mode == 0 else "",
        }
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace_save.json")
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(data, f, ensure_ascii=False, indent=2)
            self._status_msg("工作区已保存")
        except OSError as e:
            self._status_msg(f"保存失败: {e}")

    def _load_workspace(self) -> None:
        """从 JSON 文件加载工作区。"""
        import json as _json
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace_save.json")
            if not os.path.exists(path):
                self._status_msg("未找到保存文件")
                return
            with open(path, "r", encoding="utf-8") as f:
                data = _json.load(f)
            self._restore_expression(data.get("expression", ""))
            self._status_msg("工作区已加载")
        except (OSError, json.JSONDecodeError) as e:
            self._status_msg(f"加载失败: {e}")

    def _open_search_panel(self):
        """打开联网搜索面板。"""
        from MF_UI.dialogs.search_panel import SearchPanel
        if self._search_panel is None:
            self._search_panel = SearchPanel(self)
        self._search_panel.show()
        self._search_panel.raise_()
        self._search_panel.activateWindow()

    def _toggle_keyboard_panel(self) -> None:
        """切换内置键盘面板显隐。"""
        if self.keyboard_panel.isVisible():
            self.keyboard_panel.setVisible(False)
            self._kb_toggle_btn.setText("键盘")
        else:
            h = max(self.height() // 5, 80)
            self.keyboard_panel.setFixedHeight(h)
            self.keyboard_panel.setVisible(True)
            self._kb_toggle_btn.setText("▼ 收起")

    def resizeEvent(self, event) -> None:
        """窗口大小变化时更新键盘面板高度和还原几何。"""
        super().resizeEvent(event)
        # 圆角由 QSS border-radius + 透明边距处理，无需蒙版
        # 非最大化 + 非动画期间：持续保存几何用于还原
        if not self.isMaximized() and not self._geometry_locked:
            self._normal_geometry = self.geometry()
        # 键盘面板自适应
        if hasattr(self, 'keyboard_panel') and self.keyboard_panel.isVisible():
            h = max(self.height() // 5, 60)
            self.keyboard_panel.setFixedHeight(h)

    @staticmethod
    def _find_calc_block(widget: QWidget) -> QWidget | None:
        """递归查找包含 input_box 和 calc_mode_combo 的 CalcBlock。"""
        if hasattr(widget, 'input_box') and hasattr(widget, 'calc_mode_combo'):
            return widget
        for child in widget.children() if hasattr(widget, 'children') else []:
            result = MainWindow._find_calc_block(child)
            if result is not None:
                return result
        return None

    def _get_calc_context(self) -> tuple[str, str]:
        """获取当前激活的计算块上下文（表达式 + 模式）。"""
        try:
            w = self._stacked_widget.currentWidget()
            if w is not None:
                block = self._find_calc_block(w)
                if block:
                    expr = block.input_box.text().strip()
                    mode = block.calc_mode_combo.currentText()
                    return (expr, mode)
        except Exception as _e:
            import logging
            logging.getLogger("MF-Mathematics").debug("查找计算块失败: %s", _e)
        return ("", "")

    # ---------- 主题切换 ----------
    def _switch_to_light(self):
        if self._current_theme == "light":
            return
        self._current_theme = "light"
        self._apply_theme(self._light_qss_path)
        self._status_msg("已切换到亮色主题")

    def _switch_to_dark(self):
        if self._current_theme == "dark":
            return
        self._current_theme = "dark"
        self._apply_theme(self._dark_qss_path)
        self._status_msg("已切换到暗色主题")

    def _apply_theme(self, qss_path: str):
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            self._status_msg(f"样式文件未找到: {qss_path}")
        # setStyleSheet 触发全局 re-polish → QToolButton 可能被重建 → checked 状态需恢复
        if hasattr(self, '_btn_calc') and hasattr(self, '_btn_plot'):
            self._sync_toolbar_buttons()

    # ═══════════════════════════════════════════════════════════
    #  教程系统集成
    # ═══════════════════════════════════════════════════════════

    def _register_tutorial_elements(self) -> None:
        """注册 UI 元素供教程引导系统高亮定位。

        工具栏按钮通过 QToolBar.widgetForAction() 获取实际的 QToolButton widget，
        确保教程覆盖层能精确定位到按钮而非整个主窗口。
        """
        toolbar: QToolBar | None = self.findChild(QToolBar)
        calc_widget = toolbar.widgetForAction(self._btn_calc) if toolbar else None
        plot_widget = toolbar.widgetForAction(self._btn_plot) if toolbar else None
        ai_widget = toolbar.widgetForAction(self._act_ai) if toolbar else None
        search_widget = toolbar.widgetForAction(self._act_search) if toolbar else None
        settings_widget = toolbar.widgetForAction(self._act_settings) if toolbar else None
        help_widget = toolbar.widgetForAction(self._act_help) if toolbar else None

        self._tutorial_elements = {
            "main_window.toolbar": toolbar or self,
            "main_window.mode_selector": self._sub_combo,
            "main_window.theme_toggle": self,
            "main_window.help_button": help_widget or self,
            "toolbar.calc_button": calc_widget or self._btn_calc,
            "toolbar.plot_button": plot_widget or self._btn_plot,
            "toolbar.ai_button": ai_widget or self,
            "toolbar.search_button": search_widget or self,
            "toolbar.settings_button": settings_widget or self,
        }

    def _check_first_launch(self) -> None:
        """首次启动时显示欢迎对话框。"""
        try:
            from MF_Tutorial.engine import TutorialEngine
            engine = TutorialEngine()
            engine.load_all()
            if engine.is_first_launch():
                self._show_welcome_dialog()
            engine.mark_launched()
        except Exception as e:
            import logging; logging.debug(f"欢迎对话框加载失败: {e}")

    def _show_welcome_dialog(self) -> None:
        """显示欢迎对话框并在用户接受后启动引导。"""
        try:
            from MF_Tutorial.welcome_dialog import WelcomeDialog
            dlg = WelcomeDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                # 用户选择开始引导
                self._open_guided_walkthrough()
        except Exception as e:
            print(f"[MainWindow] 欢迎对话框出错: {e}")

    def _open_history(self) -> None:
        """打开计算历史记录查看器。"""
        from MF_UI.dialogs.history_dialog import HistoryDialog

        def on_select(expr: str) -> None:
            self._restore_expression(expr)
            self._status_msg(f"已回退到: {expr[:40]}{'...' if len(expr) > 40 else ''}")

        dlg = HistoryDialog(
            history=self._calc_history,
            history_pos=self._history_pos,
            on_select=on_select,
            parent=self,
        )
        dlg.exec()

    def _open_help_browser(self) -> None:
        """打开帮助文档浏览器。"""
        try:
            from MF_Tutorial.help_browser import HelpBrowser
            if self._help_browser is None:
                self._help_browser = HelpBrowser(self)
            self._help_browser.show()
            self._help_browser.raise_()
            self._help_browser.activateWindow()
        except Exception as e:
            self._status_msg(f"帮助文档加载失败: {e}")

    def _open_guided_walkthrough(self) -> None:
        """启动交互式引导向导。"""
        try:
            from MF_Tutorial.walkthrough import GuidedWalkthrough
            from MF_Tutorial.engine import TutorialEngine

            # 确保引擎已加载
            engine = TutorialEngine()
            if not engine.get_all():
                engine.load_all()

            # 确保 UI 元素已注册
            if not self._tutorial_elements:
                self._register_tutorial_elements()

            self._walkthrough = GuidedWalkthrough(self)
            self._walkthrough.register_elements(self._tutorial_elements)
            self._walkthrough.set_on_finished(
                lambda: self._status_msg("引导完成！按 F1 随时查看帮助文档。")
            )
            self._walkthrough.start("quick-start")
        except Exception as e:
            self._status_msg(f"引导加载失败: {e}")

    def _open_example_library(self) -> None:
        """打开示例任务库。"""
        try:
            from MF_Tutorial.example_library import ExampleLibrary
            if self._example_library is None:
                self._example_library = ExampleLibrary(self)
                self._example_library.example_selected.connect(
                    self._on_example_selected
                )
            self._example_library.show()
            self._example_library.raise_()
            self._example_library.activateWindow()
        except Exception as e:
            self._status_msg(f"示例库加载失败: {e}")

    def _open_about_dialog(self) -> None:
        """打开关于对话框。"""
        from MF_UI.dialogs.about_dialog import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    def _on_example_selected(self, example: object) -> None:
        """用户选择了示例任务 → 加载到计算工作区。"""
        self.load_tutorial_example(example)

    def load_tutorial_example(self, example: object) -> None:
        """加载教程示例到当前工作区。

        Args:
            example: Example 数据类实例。
        """
        try:
            # 切换到计算模式
            if self._current_mode != 0:
                self._switch_mode(0)

            # 根据 example.mode 切换到对应子模式
            mode_lower = example.mode.lower() if hasattr(example, 'mode') else ""
            calc_modes_map = {
                "代数": 0, "线性代数": 1, "概率统计": 2, "概率论与数理统计": 2,
                "数值分析": 3, "数值": 3,
            }
            for key, idx in calc_modes_map.items():
                if key in mode_lower or mode_lower in key:
                    self._sub_combo.setCurrentIndex(idx)
                    break

            # 获取当前工作区
            workspace = self._stacked_widget.currentWidget()
            if workspace is None:
                return

            # 查找 CalcBlock 并填入表达式和模式
            block = self._find_calc_block(workspace)
            if block:
                if example.expr:
                    block.input_box.setText(example.expr)
                if example.action and hasattr(block, 'calc_mode_combo'):
                    combo = block.calc_mode_combo
                    for i in range(combo.count()):
                        if example.action in combo.itemText(i):
                            combo.setCurrentIndex(i)
                            break

            self._status_msg(f"已加载示例: {example.label}")
        except Exception as e:
            self._status_msg(f"示例加载失败: {e}")

    # ═══════════════════════════════════════════════════════════
    #  用户系统
    # ═══════════════════════════════════════════════════════════

    def _on_user_clicked(self) -> None:
        """处理登录/用户按钮点击。"""
        try:
            from MF_User.manager import UserManager
            mgr = UserManager()
            if mgr.is_logged_in:
                # 已登录 → 登出
                mgr.logout()
                self._refresh_user_status()
                self._status_msg("已登出")
            else:
                self._open_login_dialog()
        except Exception as e:
            self._status_msg(f"用户系统错误: {e}")

    def _open_login_dialog(self) -> None:
        """打开登录对话框。"""
        try:
            from MF_User.login_dialog import LoginDialog
            dlg = LoginDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                from MF_User.manager import UserManager
                mgr = UserManager()
                if mgr.current_user:
                    self._status_msg(f"欢迎，{mgr.current_user.username}！")
            self._refresh_user_status()
        except Exception as e:
            self._status_msg(f"登录失败: {e}")

    def _refresh_user_status(self) -> None:
        """刷新工具栏登录按钮和状态栏用户标签。"""
        try:
            from MF_User.manager import UserManager
            mgr = UserManager()
            if mgr.is_logged_in and mgr.current_user:
                self._user_action.setText(mgr.current_user.username)
                if self._user_status_label:
                    self._user_status_label.setText(
                        f"当前用户: {mgr.current_user.username}")
                    self._user_status_label.setStyleSheet("color: #10b981;")
            else:
                self._user_action.setText("登录")
                if self._user_status_label:
                    self._user_status_label.setText("未登录")
                    self._user_status_label.setStyleSheet("color: #94a3b8;")
        except Exception as _e:
            import logging
            logging.getLogger("MF-Mathematics").debug("用户状态刷新失败: %s", _e)
