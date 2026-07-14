"""MF-Mathematics 主窗口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar,
    QSplitter, QListWidget, QListWidgetItem,
    QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QApplication, QFrame,QComboBox
)
from calc.algebra import Workspace as AlgebraWorkspace
from calc.linear_algebra import Workspace as LinearAlgebraWorkspace
from calc.numerical import Workspace as NumericalWorkspace
from calc.probability import Workspace as ProbabilityWorkspace
from plot.basic.workspace import PlotWorkspace

# 运行时自动设置项目根路径
import sys as _sys
import os as _os
_this_dir = _os.path.dirname(_os.path.abspath(__file__))
_root_dir = _os.path.dirname(_this_dir)
if _root_dir not in _sys.path:
    _sys.path.insert(0, _root_dir)

# ---- 数据定义 ----
CALC_NAV_ITEMS = [
    ("代数计算",
     "代数计算",
     "包含：表达式化简、求导、积分、极限、级数展开、复数运算等"),
    ("线性代数",
     "线性代数",
     "包含：矩阵运算、行列式、特征值、向量计算、线性方程组求解等"),
    ("概率论与数理统计",
     "概率论与数理统计",
     "包含：概率分布、期望、方差、假设检验；统计图绘制功能等"),
    ("数值分析",
     "数值分析",
     "包含：插值、数值积分、ODE 数值解、非线性方程求根等"),
]

PLOT_NAV_ITEMS = [
    ("普通模式",
     "普通绘图模式",
     "支持：实函数 y=f(x)、隐函数 f(x,y)=0 的绘制"),
    ("3D模式",
     "3D 绘图模式",
     "支持：三维曲面 z=f(x,y)、三维参数方程 (x(t),y(t),z(t))"),
    ("复数模式",
     "复数绘图模式",
     "支持：复平面 RGB 域着色，可切换至 3D 复函数视图（功能预留）"),
    ("向量场",
     "向量场模式",
     "支持：2D/3D 向量场绘制"),
    ("任意做图",
     "任意做图模式",
     "支持：手动画圆、线段、直线等自由几何对象（功能预留）"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multifunctional-Mathematics")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        self._center_on_screen()

        self._current_theme = "light"
        self._current_mode = 0
        self._nav_populating = False

        self._calc_modes = ["代数计算", "线性代数", "概率论与数理统计", "数值分析"]
        self._plot_modes = ["普通模式", "3D模式", "复数模式", "向量场", "任意做图"]
        self.last_calc_index = 0
        self.last_plot_index = 0

        self._build_menu_bar()
        self._build_toolbar()
        self._build_central_area()
        self._build_status_bar()

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._light_qss_path = os.path.join(base_dir, "styles", "light.qss")
        self._dark_qss_path = os.path.join(base_dir, "styles", "dark.qss")
        self._apply_theme(self._light_qss_path)


    # ---------- 窗口居中 ----------
    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            center = screen.availableGeometry().center()
            frame = self.frameGeometry()
            frame.moveCenter(center)
            self.move(frame.topLeft())

    # ---------- 菜单栏 ----------
    def _build_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("文件")
        act_new = QAction("新建工作区", self)
        act_new.triggered.connect(lambda: self._status_msg("新建工作区"))
        file_menu.addAction(act_new)
        act_open = QAction("打开...", self)
        act_open.triggered.connect(lambda: self._status_msg("打开文件"))
        file_menu.addAction(act_open)
        file_menu.addSeparator()
        act_exit = QAction("退出", self)
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        edit_menu = menu_bar.addMenu("编辑")
        act_undo = QAction("撤销", self)
        act_undo.triggered.connect(lambda: self._status_msg("撤销"))
        edit_menu.addAction(act_undo)
        act_redo = QAction("重做", self)
        act_redo.triggered.connect(lambda: self._status_msg("重做"))
        edit_menu.addAction(act_redo)
        edit_menu.addSeparator()
        act_clear = QAction("清空所有", self)
        act_clear.triggered.connect(lambda: self._status_msg("清空所有"))
        edit_menu.addAction(act_clear)

        view_menu = menu_bar.addMenu("视图")
        act_light = QAction("亮色主题", self)
        act_light.triggered.connect(self._switch_to_light)
        view_menu.addAction(act_light)
        act_dark = QAction("暗色主题", self)
        act_dark.triggered.connect(self._switch_to_dark)
        view_menu.addAction(act_dark)

        help_menu = menu_bar.addMenu("帮助")
        act_about = QAction("关于", self)
        act_about.triggered.connect(lambda: self._status_msg("关于 MF-Mathematics"))
        help_menu.addAction(act_about)

    # ---------- 工具栏 ----------
    def _build_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        self._btn_calc = toolbar.addAction("计算")
        self._btn_calc.setCheckable(True)
        self._btn_calc.setChecked(True)
        self._btn_calc.triggered.connect(lambda: self._switch_mode(0))

        self._btn_plot = toolbar.addAction("绘图")
        self._btn_plot.setCheckable(True)
        self._btn_plot.triggered.connect(lambda: self._switch_mode(1))

        toolbar.actionTriggered.connect(self._on_toolbar_action)

        toolbar.addSeparator()
        
        self._sub_combo = QComboBox()
        self._sub_combo.setFixedWidth(140)
        self._sub_combo.addItems(self._calc_modes)
        toolbar.addWidget(self._sub_combo)
        self._sub_combo.currentIndexChanged.connect(self._on_sub_mode_changed)

        
        toolbar.addSeparator()

        act_search = toolbar.addAction("搜索")
        act_search.triggered.connect(lambda: self._status_msg("搜索"))
        act_history = toolbar.addAction("历史")
        act_history.triggered.connect(lambda: self._status_msg("历史记录"))
        act_AI = toolbar.addAction("AI")
        act_AI.triggered.connect(lambda: self._status_msg("AI"))
        act_settings = toolbar.addAction("设置")
        act_settings.triggered.connect(lambda: self._status_msg("设置"))

    def _on_toolbar_action(self, action):
        if action is self._btn_calc:
            self._btn_plot.setChecked(False)
            self._btn_calc.setChecked(True)
        elif action is self._btn_plot:
            self._btn_calc.setChecked(False)
            self._btn_plot.setChecked(True)

    def _switch_mode(self, mode: int):
        if self._current_mode == mode:
            return

        self._current_mode = mode

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

        self._on_sub_mode_changed(restore_index)

        if restore_index < self._sub_combo.count():
            self._sub_combo.setCurrentIndex(restore_index)

        self._sub_combo.blockSignals(False)

    def _on_sub_mode_changed(self, index: int):
        if self._current_mode == 0:  # 计算模式
            self.last_calc_index = index
            self._stacked_widget.setCurrentIndex(index)  # 索引 0~3
        else:  # 绘图模式
            self.last_plot_index = index
            self._stacked_widget.setCurrentIndex(4 + index)  # 索引 4~8
    

    # ---------- 中央区域 ----------
    def _build_central_area(self):
        # 直接让右侧工作区成为中央部件，不再使用分割器
        right_panel = self._build_right_panel()
        self.setCentralWidget(right_panel)

    # ================================================================
    #  右侧堆叠区域
    # ================================================================
    def _build_right_panel(self):
        self._stacked_widget = QStackedWidget()
        # ── 计算模式 (index 0-3) ──
        self._stacked_widget.addWidget(AlgebraWorkspace())
        self._stacked_widget.addWidget(LinearAlgebraWorkspace())
        self._stacked_widget.addWidget(ProbabilityWorkspace())
        self._stacked_widget.addWidget(NumericalWorkspace())
        # ── 绘图模式 (index 4-7): 实际 PlotWorkspace ──
        self._stacked_widget.addWidget(PlotWorkspace("普通模式 — 2D 函数绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("3D 模式 — 三维曲面绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("复数模式 — 复平面域着色绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("向量场模式 — 向量场绘图"))
        # ── index 8: 任意做图（占位）──
        self._stacked_widget.addWidget(self._make_placeholder_page("任意做图", "手动画圆、线段、直线等自由几何对象（功能预留）"))
        return self._stacked_widget

    def _make_placeholder_page(self, title: str, desc: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        placeholder_frame = QFrame()
        placeholder_frame.setObjectName("placeholder_frame")
        placeholder_frame.setFrameStyle(QFrame.NoFrame)
        placeholder_frame.setMinimumHeight(400)
        frame_layout = QVBoxLayout(placeholder_frame)
        frame_layout.setAlignment(Qt.AlignCenter)
        dev_label = QLabel("功能开发中")
        dev_label.setObjectName("dev_label")
        dev_label.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(dev_label)
        layout.addWidget(placeholder_frame, stretch=1)
        return page

        return page

    # ---------- 状态栏 ----------
    def _build_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_msg("就绪")
        brand_label = QLabel("MF-Vis-Science \u00b7 开放工作室")
        brand_label.setObjectName("brand_label")
        self._status_bar.addPermanentWidget(brand_label)

    def _status_msg(self, msg: str):
        self._status_bar.showMessage(msg, 5000)

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
