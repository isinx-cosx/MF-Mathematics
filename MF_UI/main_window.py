"""MF-Mathematics 主窗口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QStatusBar,
    QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QApplication, QComboBox, QDialog, QMessageBox,
    QPushButton, QLineEdit,
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
     "支持：复平面 RGB 域着色，可切换至 3D 复函数视图"),
    ("向量场",
     "向量场模式",
     "支持：2D/3D 向量场绘制"),
    ("任意做图",
     "任意做图模式",
     "支持：手动画圆、线段、直线等自由几何对象"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(flags=Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Multifunctional-Mathematics")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        self._center_on_screen()

        self._current_theme = "light"
        self._current_mode = 0
        self._nav_populating = False

        # 计算历史栈（撤销/重做）
        self._calc_history: list[dict] = []
        self._history_pos = -1
        self._max_history = 50

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

        # 自定义标题栏（替换原生标题栏）
        from components.custom_title_bar import apply_frameless
        self._title_bar = apply_frameless(self, "Multifunctional-Mathematics")

        # 窗口阴影 — 柔光边缘效果
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from PySide6.QtGui import QColor
        _outer = self.centralWidget()
        if _outer is not None:
            _container = _outer.property("framelessContainer")
            if _container is not None:
                _shadow = QGraphicsDropShadowEffect(_container)
                _shadow.setBlurRadius(15)
                _shadow.setOffset(0, 0)
                _shadow.setColor(QColor(0, 0, 0, 40))
                _container.setGraphicsEffect(_shadow)

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
        act_search.triggered.connect(self._open_search_panel)

        self._search_panel: object | None = None
        act_history = toolbar.addAction("历史")
        act_history.triggered.connect(lambda: self._status_msg("历史记录"))
        act_AI = toolbar.addAction("AI")
        act_AI.triggered.connect(self._open_ai_dialog)
        act_settings = toolbar.addAction("设置")
        act_settings.triggered.connect(self._open_settings)

        toolbar.addSeparator()
        self._user_action = toolbar.addAction("登录")
        self._user_action.triggered.connect(self._on_user_clicked)

        toolbar.addSeparator()
        act_help = toolbar.addAction("帮助")
        act_help.triggered.connect(self._open_help_browser)

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
        self._stacked_widget = QStackedWidget()
        # ── 计算模式 (index 0-3) ──
        self._stacked_widget.addWidget(AlgebraWorkspace())
        self._stacked_widget.addWidget(LinearAlgebraWorkspace())
        self._stacked_widget.addWidget(ProbabilityWorkspace())
        self._stacked_widget.addWidget(NumericalWorkspace())
        # ── 绘图模式 (index 4-8) ──
        self._stacked_widget.addWidget(PlotWorkspace("普通模式 — 2D 函数绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("3D 模式 — 三维曲面绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("复数模式 — 复平面域着色绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("向量场模式 — 向量场绘图"))
        self._stacked_widget.addWidget(PlotWorkspace("任意做图 — 自由几何对象绘制"))

        # 内置键盘面板
        self._build_keyboard_panel()

        # 切换按钮 — 左下角
        self._kb_toggle_btn = QPushButton("⌨️ 键盘")
        self._kb_toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._kb_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kb_toggle_btn.setObjectName("kb_toggle_btn")
        self._kb_toggle_btn.clicked.connect(self._toggle_keyboard_panel)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(8, 2, 0, 2)
        btn_row.addWidget(self._kb_toggle_btn)
        btn_row.addStretch()

        # 容器：stacked_widget (stretch=1) + btn_row + keyboard_panel (stretch=0)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._stacked_widget, 1)
        layout.addLayout(btn_row)
        layout.addWidget(self.keyboard_panel, 0)
        self.setCentralWidget(container)

    # ================================================================
    #  内置键盘面板
    # ================================================================
    def _build_keyboard_panel(self):
        from MF_UI.math_keyboard import KeyboardPanel
        self.keyboard_panel = KeyboardPanel(self)

    # ---------- 状态栏 ----------
    def _build_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_msg("就绪")

        # 用户状态标签
        self._user_status_label = QLabel("未登录")
        self._user_status_label.setStyleSheet(
            "font-size: 11px; color: #94a3b8; padding: 0 8px;")
        self._status_bar.addPermanentWidget(self._user_status_label)
        self._refresh_user_status()
        brand_label = QLabel("MF-Vis-Science \u00b7 开放工作室")
        brand_label.setObjectName("brand_label")
        self._status_bar.addPermanentWidget(brand_label)

        from PySide6.QtWidgets import QSizeGrip
        self._status_bar.addPermanentWidget(QSizeGrip(self))

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
        except Exception:
            pass

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
            self._kb_toggle_btn.setText("⌨️ 键盘")
        else:
            h = max(self.height() // 5, 80)
            self.keyboard_panel.setFixedHeight(h)
            self.keyboard_panel.setVisible(True)
            self._kb_toggle_btn.setText("▼ 收起")

    def resizeEvent(self, event) -> None:
        """窗口大小变化时更新键盘面板高度。"""
        super().resizeEvent(event)
        if hasattr(self, 'keyboard_panel') and self.keyboard_panel.isVisible():
            h = max(self.height() // 5, 60)
            self.keyboard_panel.setFixedHeight(h)

    def _get_calc_context(self) -> tuple[str, str]:
        """获取当前激活的计算块上下文（表达式 + 模式）。"""
        try:
            sw = self._stacked_widget
            w = sw.currentWidget()
            if w:
                def find_block(widget):
                    if hasattr(widget, 'input_box') and hasattr(widget, 'calc_mode_combo'):
                        return widget
                    for child in widget.children() if hasattr(widget, 'children') else []:
                        r = find_block(child)
                        if r: return r
                    return None
                block = find_block(w)
                if block:
                    expr = block.input_box.text().strip()
                    mode = block.calc_mode_combo.currentText()
                    return (expr, mode)
        except Exception:
            pass
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

    def _toggle_theme(self):
        """工具栏主题切换按钮。"""
        if self._current_theme == "light":
            self._switch_to_dark()
        else:
            self._switch_to_light()

    def _apply_theme(self, qss_path: str):
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            self._status_msg(f"样式文件未找到: {qss_path}")

    # ═══════════════════════════════════════════════════════════
    #  教程系统集成
    # ═══════════════════════════════════════════════════════════

    def _register_tutorial_elements(self) -> None:
        """注册 UI 元素供教程引导使用。"""
        self._tutorial_elements = {
            "main_window.toolbar": self.findChild(QToolBar) or self,
            "main_window.mode_selector": self._sub_combo,
            "main_window.theme_toggle": self,
            "main_window.help_button": self,
            "toolbar.calc_button": self,
            "toolbar.plot_button": self,
            "toolbar.ai_button": self,
            "toolbar.search_button": self,
            "toolbar.settings_button": self,
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
            print(f"[MainWindow] 欢迎对话框加载失败: {e}")

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
            def find_calc_block(widget):
                if hasattr(widget, 'input_box') and hasattr(widget, 'calc_mode_combo'):
                    return widget
                for child in widget.children() if hasattr(widget, 'children') else []:
                    r = find_calc_block(child)
                    if r:
                        return r
                return None

            block = find_calc_block(workspace)
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
                    self._user_status_label.setStyleSheet(
                        "font-size: 11px; color: #10b981; padding: 0 8px;")
            else:
                self._user_action.setText("登录")
                if self._user_status_label:
                    self._user_status_label.setText("未登录")
                    self._user_status_label.setStyleSheet(
                        "font-size: 11px; color: #94a3b8; padding: 0 8px;")
        except Exception:
            pass  # MF_User 模块不可用时静默失败
