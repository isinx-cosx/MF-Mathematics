# -*- coding: utf-8 -*-
"""MF-Mathematics 关于对话框 — 完整功能介绍与技术栈。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QScrollArea,
)

# ── 统一样式（黑色字体，白色背景）──
C_TITLE = "#0f172a"
C_SUBTITLE = "#1e293b"
C_SECTION = "#1e40af"
C_BODY = "#334155"
C_BULLET = "#475569"
C_SEP = "#cbd5e1"
C_BG = "#ffffff"
FONT_TITLE = "font-size:22px; font-weight:700;"
FONT_SUBTITLE = "font-size:13px;"
FONT_SECTION = "font-size:14px; font-weight:700;"
FONT_BODY = "font-size:13px;"
FONT_BULLET = "font-size:12px;"


class AboutDialog(QDialog):
    """MF-Mathematics 关于对话框 — 完整功能介绍。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("关于 MF-Mathematics")
        self.setObjectName("aboutDialog")
        self.resize(600, 600)
        self.setMinimumSize(460, 420)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 自定义标题栏 ──
        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, "关于 MF-Mathematics")

        # ── 内容区（白色背景）──
        content = QWidget()
        content.setObjectName("aboutContent")
        content.setStyleSheet(f"#aboutContent{{background:{C_BG};}}")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # 标题
        title = QLabel("MF-Mathematics")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"{FONT_TITLE} color:{C_TITLE}; padding:4px 0;")
        layout.addWidget(title)

        # 版本
        version = QLabel("v1.0.0 — 基于 PySide6 的科学计算与可视化平台")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(f"{FONT_SUBTITLE} color:{C_SUBTITLE}; padding-bottom:4px;")
        layout.addWidget(version)

        # 一句话简介
        desc = QLabel(
            "集成符号计算、数值分析、概率统计、2D/3D 函数绘图、复数域着色、"
            "向量场可视化、AI 辅助计算与交互式教程引导。"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet(f"{FONT_BODY} color:{C_BODY}; line-height:1.6;")
        layout.addWidget(desc)

        # 分隔线
        layout.addWidget(self._sep())

        # ── 滚动区域 ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea{{background:{C_BG}; border:none;}}")

        fw = QWidget()
        fw.setStyleSheet(f"background:{C_BG};")
        fl = QVBoxLayout(fw)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)

        # ═══════════════════════════════════════
        #  技术栈
        # ═══════════════════════════════════════
        fl.addWidget(self._section("技术栈"))
        fl.addWidget(self._bullet("GUI 框架：PySide6（Qt for Python 6）"))
        fl.addWidget(self._bullet("符号计算引擎：SymPy"))
        fl.addWidget(self._bullet("数值计算：NumPy / SciPy"))
        fl.addWidget(self._bullet("绘图引擎：QGraphicsView / Matplotlib（Qt5Agg 后端）"))
        fl.addWidget(self._bullet("密钥存储：keyring（操作系统凭据管理器）"))
        fl.addWidget(self._bullet("AI 接口：DeepSeek / OpenAI / Ollama 多模型支持"))

        fl.addWidget(self._sep())

        # ═══════════════════════════════════════
        #  计算模式
        # ═══════════════════════════════════════
        fl.addWidget(self._section("计算模式"))
        fl.addWidget(self._subsection("代数计算"))
        fl.addWidget(self._bullet("表达式化简 / 求导（含高阶与某点导数）/ 不定积分与定积分"))
        fl.addWidget(self._bullet("极限（含左右极限）/ 级数展开 / 因式分解 / 方程求解"))
        fl.addWidget(self._bullet("复数运算 / 有理式化简 / 部分分式分解 / 三角恒等式"))
        fl.addWidget(self._subsection("线性代数"))
        fl.addWidget(self._bullet("矩阵运算 / 行列式 / 特征值与特征向量 / 矩阵求逆"))
        fl.addWidget(self._bullet("高斯消元 / LU 分解 / QR 算法 / 施密特正交化"))
        fl.addWidget(self._bullet("向量空间 / 对角化 / 若尔当标准型 / 二次型"))
        fl.addWidget(self._subsection("概率论与数理统计"))
        fl.addWidget(self._bullet("概率分布（正态/二项/泊松/均匀/指数/伯努利）"))
        fl.addWidget(self._bullet("期望 / 方差 / 协方差 / 相关系数 / 大数定律"))
        fl.addWidget(self._bullet("假设检验（z/t/卡方/F）/ 回归分析 / ANOVA"))
        fl.addWidget(self._bullet("MLE 估计 / 贝叶斯推断 / 非参数检验"))
        fl.addWidget(self._subsection("数值分析"))
        fl.addWidget(self._bullet("插值（拉格朗日/牛顿/样条/最小二乘）/ 数值积分"))
        fl.addWidget(self._bullet("ODE 数值解（欧拉/RK4/隐式欧拉）/ 非线性方程求根"))
        fl.addWidget(self._bullet("幂法 / 雅可比迭代 / 高斯-赛德尔 / 共轭梯度"))

        fl.addWidget(self._sep())

        # ═══════════════════════════════════════
        #  数学守卫
        # ═══════════════════════════════════════
        fl.addWidget(self._section("三级数学守卫（防呆防傻安全网）"))
        fl.addWidget(self._subsection("1 级 — 慢速预警"))
        fl.addWidget(self._bullet("表达式运算符 > 500 或嵌套深度 > 10 → 弹窗提示预计耗时"))
        fl.addWidget(self._subsection("2 级 — 爆炸风险硬拦截"))
        fl.addWidget(self._bullet("超高次幂分式积分（分母 x^n, n ≥ 10）/ 大矩阵行列式（dim ≥ 6）"))
        fl.addWidget(self._bullet("大范围级数求和（N-m > 1000）→ 建议 AI 加速"))
        fl.addWidget(self._subsection("3 级 — 数学硬错误"))
        fl.addWidget(self._bullet("除零 / 未定义符号 / ∞-∞ 无意义操作 → 直接拒绝"))
        fl.addWidget(self._subsection("数域切换"))
        fl.addWidget(self._bullet("实模式下 sqrt(-1) / log(-x) → 询问切换复数模式"))
        fl.addWidget(self._subsection("极限专项防御"))
        fl.addWidget(self._bullet("高频振荡检测 sin(1/x) 模式 / 单侧探针预判 / 超时中断（5s）"))

        fl.addWidget(self._sep())

        # ═══════════════════════════════════════
        #  AI 加速
        # ═══════════════════════════════════════
        fl.addWidget(self._section("AI 辅助"))
        fl.addWidget(self._bullet("步骤推导：AI 生成分步计算过程（支持 LaTeX 数学公式渲染）"))
        fl.addWidget(self._bullet("AI 加速：本地高耗时计算自动建议转 AI 处理"))
        fl.addWidget(self._bullet("多模型支持：DeepSeek / OpenAI / Ollama 可切换"))
        fl.addWidget(self._bullet("API Key 安全存储：keyring 操作系统凭据管理器"))
        fl.addWidget(self._bullet("每日免费配额：本地 usage.json 管理"))

        fl.addWidget(self._sep())

        # ═══════════════════════════════════════
        #  绘图模式
        # ═══════════════════════════════════════
        fl.addWidget(self._section("绘图模式"))
        fl.addWidget(self._subsection("2D 函数绘图"))
        fl.addWidget(self._bullet("实函数 y=f(x) / 隐函数 f(x,y)=0 / 参数方程"))
        fl.addWidget(self._bullet("自适应智能刻度 / 滚轮缩放 / 自由拖拽平移"))
        fl.addWidget(self._bullet("渐近线断点检测（Desmos 风格飞线打断）/ 高频振荡拦截"))
        fl.addWidget(self._subsection("3D 模式"))
        fl.addWidget(self._bullet("三维曲面 z=f(x,y) / 空间参数曲线"))
        fl.addWidget(self._bullet("隐式曲面 / 等高线投影 / 视角旋转"))
        fl.addWidget(self._subsection("复数模式"))
        fl.addWidget(self._bullet("复平面 RGB 域着色 / 3D 复函数视图"))
        fl.addWidget(self._subsection("向量场模式"))
        fl.addWidget(self._bullet("2D/3D 梯度场与流线 / 自适应密度"))
        fl.addWidget(self._subsection("任意做图"))
        fl.addWidget(self._bullet("手动画圆 / 线段 / 直线 / 多边形等自由几何对象"))

        fl.addWidget(self._sep())

        # ═══════════════════════════════════════
        #  函数框系统
        # ═══════════════════════════════════════
        fl.addWidget(self._section("函数框与滑块系统"))
        fl.addWidget(self._bullet("动态添加/删除函数框卡片 / 自定义函数名与自变量"))
        fl.addWidget(self._bullet("颜色选择器 / 显示开关 / 未知参数自动识别"))
        fl.addWidget(self._bullet("滑块系统：自动生成参数滑块 / 范围自定义 / 同名参数全局同步"))

        fl.addWidget(self._sep())

        # ═══════════════════════════════════════
        #  数字估计
        # ═══════════════════════════════════════
        fl.addWidget(self._section("数字估计（无理数探索）"))
        fl.addWidget(self._bullet("常数选择（π, e, √2）/ 小数位数 1-15 位"))
        fl.addWidget(self._bullet("算法库：拉马努金级数（极速）/ 莱布尼茨级数（慢速演示）/ 蒙特卡洛"))
        fl.addWidget(self._bullet("实时显示迭代次数与当前误差 / 强制迭代上限与精度上限"))

        fl.addWidget(self._sep())

        # ═══════════════════════════════════════
        #  UI / UX
        # ═══════════════════════════════════════
        fl.addWidget(self._section("界面与用户体验"))
        fl.addWidget(self._bullet("自定义无边框窗口 + 边缘拖拽缩放 / 最大化无缝隙"))
        fl.addWidget(self._bullet("暗色 / 亮色双主题切换（QSS 独立文件）"))
        fl.addWidget(self._bullet("内置数学键盘面板（符号 / 希腊字母 / 矩阵模板 / 微积分符号）"))
        fl.addWidget(self._bullet("交互式教程引导 + 示例任务库"))
        fl.addWidget(self._bullet("计算历史撤销/重做（Ctrl+Z / Ctrl+Y）"))
        fl.addWidget(self._bullet("工作区保存/加载（JSON 格式）"))

        fl.addWidget(self._sep())

        # ═══════════════════════════════════════
        #  用户系统
        # ═══════════════════════════════════════
        fl.addWidget(self._section("用户系统与数据隔离"))
        fl.addWidget(self._bullet("本地用户注册/登录（SHA-256 + 随机盐值）"))
        fl.addWidget(self._bullet("用户独立配置目录 data/users/{username}/"))
        fl.addWidget(self._bullet("API Key 通过 keyring 按用户隔离"))

        fl.addWidget(self._sep())

        # ═══════════════════════════════════════
        #  架构红线
        # ═══════════════════════════════════════
        fl.addWidget(self._section("代码架构原则"))
        fl.addWidget(self._bullet("UI 层（PySide6）与计算层（SymPy）严格分离"))
        fl.addWidget(self._bullet("所有阈值与黑名单统一配置在 config.json 中"))
        fl.addWidget(self._bullet("所有复杂计算 / 网络请求在 QThread 子线程执行"))
        fl.addWidget(self._bullet("所有外部 API 调用包裹 try/except 并提供中文错误回退"))

        fl.addStretch()
        scroll.setWidget(fw)
        layout.addWidget(scroll, 1)

        # ── 底部：关闭按钮 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(
            "QPushButton{background:#3b82f6; color:#fff; border:none;"
            " border-radius:6px; padding:8px 28px; font-size:13px; font-weight:500}"
            "QPushButton:hover{background:#2563eb}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        root.addWidget(content, 1)

        # ── 继承父主题 + 覆盖为白色背景 ──
        if parent is not None:
            try:
                base = parent.styleSheet()
                # 覆盖 QWidget 全局背景为白色，确保黑色字体可读
                self.setStyleSheet(
                    base + f"\nQWidget{{background:{C_BG}; color:{C_BODY};}}"
                )
            except Exception:
                self.setStyleSheet(f"QWidget{{background:{C_BG}; color:{C_BODY};}}")

        from MF_UI.components.dialog_style import apply_shadow
        apply_shadow(self)

    # ── 辅助控件工厂 ────────────────────────────────────────

    @staticmethod
    def _sep() -> QLabel:
        s = QLabel()
        s.setFixedHeight(1)
        s.setStyleSheet(f"background:{C_SEP};")
        return s

    @staticmethod
    def _section(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"{FONT_SECTION} color:{C_SECTION}; padding-top:6px;")
        return lbl

    @staticmethod
    def _subsection(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size:13px; font-weight:600; color:{C_SUBTITLE}; padding-top:2px;")
        return lbl

    @staticmethod
    def _bullet(text: str) -> QLabel:
        lbl = QLabel(f"  •  {text}")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"{FONT_BULLET} color:{C_BULLET}; line-height:1.6;")
        return lbl
