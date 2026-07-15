# -*- coding: utf-8 -*-
"""MF_UI.plot.plot_3d — 三维坐标系与曲面绘制。

Plot3D: 完整三维坐标系控件（轴/网格/刻度/箭头）
Plot3DCanvas: Plot3D 的别名（向后兼容）
Plot3DWorkspace: 3D 模式独立工作区
"""

from .canvas import Plot3D, Plot3DCanvas
from .workspace import Plot3DWorkspace

__all__ = ["Plot3D", "Plot3DCanvas", "Plot3DWorkspace"]
