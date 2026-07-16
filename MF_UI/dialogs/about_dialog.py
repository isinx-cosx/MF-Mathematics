# -*- coding: utf-8 -*-
"""MF-Mathematics 关于对话框 — 软件介绍与技术栈。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QScrollArea, QSizePolicy,
)


class AboutDialog(QDialog):
    """MF-Mathematics 关于对话框。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("关于 MF-Mathematics")
        self.setObjectName("aboutDialog")
        self.resize(560, 520)
        self.setMinimumSize(420, 360)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 自定义标题栏 ──
        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, "关于 MF-Mathematics")

        # ── 内容区 ──
        content = QWidget()
        content.setObjectName("aboutContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 标题
        title = QLabel("MF-Mathematics")
        title.setObjectName("aboutTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "font-size:22px; font-weight:700; color:#cdd6f4; padding:4px 0;"
        )
        layout.addWidget(title)

        # 版本
        version = QLabel("v1.0.0 — 科学计算与可视化平台")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("font-size:13px; color:#a6adc8; padding-bottom:8px;")
        layout.addWidget(version)

        # 简介
        desc = QLabel(
            "基于 PySide6 构建的多功能数学软件，"
            "集成符号计算、数值分析、概率统计、\n"
            "2D/3D 函数绘图、复数域着色、向量场可视化等功能，"
            "支持 AI 辅助计算与交互式教程引导。"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("font-size:13px; color:#a6adc8; line-height:1.6;")
        layout.addWidget(desc)

        # 分隔线
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#313244;")
        layout.addWidget(sep)

        # 滚动区域：功能特性
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent; border:none;}")

        feature_widget = QWidget()
        feature_layout = QVBoxLayout(feature_widget)
        feature_layout.setContentsMargins(0, 0, 0, 0)
        feature_layout.setSpacing(12)

        # ── 技术栈 ──
        feature_layout.addWidget(self._section_label("技术栈"))
        feature_layout.addWidget(self._bullet("GUI 框架: PySide6 (Qt for Python)"))
        feature_layout.addWidget(self._bullet("符号计算引擎: SymPy"))
        feature_layout.addWidget(self._bullet("数值计算: NumPy / SciPy"))
        feature_layout.addWidget(self._bullet("绘图引擎: QGraphicsView / Matplotlib"))

        # ── 计算模式 ──
        feature_layout.addWidget(self._section_label("计算模式"))
        feature_layout.addWidget(self._bullet("代数计算: 求导/积分/极限/级数展开/化简/因式分解"))
        feature_layout.addWidget(self._bullet("线性代数: 矩阵运算/行列式/特征值/高斯消元"))
        feature_layout.addWidget(self._bullet("概率统计: 分布/假设检验/回归/方差分析"))
        feature_layout.addWidget(self._bullet("数值分析: 插值/ODE数值解/非线性方程"))
        feature_layout.addWidget(self._bullet("三级数学守卫: 慢速预警→爆炸拦截→硬错误拒绝"))
        feature_layout.addWidget(self._bullet("AI 加速: 多模型支持 + 步骤推导"))

        # ── 绘图模式 ──
        feature_layout.addWidget(self._section_label("绘图模式"))
        feature_layout.addWidget(self._bullet("2D 函数绘图: 实函数/隐函数/参数方程"))
        feature_layout.addWidget(self._bullet("3D 曲面绘图: 三维曲面/空间曲线"))
        feature_layout.addWidget(self._bullet("复数域着色: RGB 域着色 + 3D 视图"))
        feature_layout.addWidget(self._bullet("向量场: 2D/3D 梯度场与流线"))
        feature_layout.addWidget(self._bullet("任意做图: 自由几何对象 (圆/线/多边形)"))

        # ── 其他特性 ──
        feature_layout.addWidget(self._section_label("其他特性"))
        feature_layout.addWidget(self._bullet("自定义无边框窗口 + 暗色/亮色双主题"))
        feature_layout.addWidget(self._bullet("内置数学键盘面板 (符号/希腊字母/矩阵)"))
        feature_layout.addWidget(self._bullet("交互式教程引导 + 示例任务库"))
        feature_layout.addWidget(self._bullet("用户系统 + 数据隔离"))

        feature_layout.addStretch()
        scroll.setWidget(feature_widget)
        layout.addWidget(scroll, 1)

        # ── 底部: 关闭按钮 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(
            "QPushButton{background:#3b82f6; color:#fff; border:none;"
            " border-radius:6px; padding:8px 24px; font-size:13px; font-weight:500}"
            "QPushButton:hover{background:#2563eb}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        root.addWidget(content, 1)

        # ── 继承父主题 ──
        if parent is not None:
            try:
                self.setStyleSheet(parent.styleSheet())
            except Exception:
                pass

        from MF_UI.components.dialog_style import apply_shadow
        apply_shadow(self)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size:14px; font-weight:700; color:#cdd6f4; padding-top:4px;"
        )
        return lbl

    @staticmethod
    def _bullet(text: str) -> QLabel:
        lbl = QLabel(f"  •  {text}")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size:12px; color:#a6adc8; line-height:1.5;")
        return lbl
