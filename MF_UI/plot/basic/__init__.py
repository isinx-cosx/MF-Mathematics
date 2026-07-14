# -*- coding: utf-8 -*-
"""MF_UI.plot.basic — 普通模式 2D 函数绘图。

包含:
  - PlotCanvas   — 交互式 2D 画布（drawForeground 全量渲染）
  - FunctionBox  — 表达式输入卡片（自动分类显式/隐式）
  - PlotWorkspace — 绘图工作区（滑块 + 函数框 + 画布）
"""

from .plot_canvas import PlotCanvas
from .function_box import FunctionBox
from .workspace import PlotWorkspace

__all__ = ["PlotCanvas", "FunctionBox", "PlotWorkspace"]
