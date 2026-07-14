# -*- coding: utf-8 -*-
"""MF_UI.plot — 绘图子系统。

子包:
  - basic        — 普通 2D 模式（核心画布、函数框、工作区）
  - plot_3d      — 三维曲面绘图（预留）
  - complex      — 复平面域着色绘图（预留）
  - vector_field — 向量场绘图（预留）
  - arbitrary    — 任意做图（预留）
"""

# 向后兼容：从 basic 子包重新导出核心类
from .basic import PlotCanvas, FunctionBox, PlotWorkspace

__all__ = ["PlotCanvas", "FunctionBox", "PlotWorkspace"]
