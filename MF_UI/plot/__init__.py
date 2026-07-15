# -*- coding: utf-8 -*-
"""MF_UI.plot — 绘图子系统。

子包:
  - basic         — 普通 2D 模式（核心画布、函数框、工作区、滑块框）
  - plot_3d       — 三维曲面绘图（坐标系 + 函数框）
  - complex       — 复平面域着色绘图（相位图 / 3D模长 / 向量场）
  - vector_field  — 向量场绘图（F=(P,Q) 形式）
  - arbitrary     — 任意做图（自由几何对象，功能预留）
"""

from .basic import PlotCanvas, FunctionBox, PlotWorkspace
from .basic.slider_function_box import SliderFunctionBox
from .plot_3d import Plot3D, Plot3DCanvas
from .complex import ComplexWorkspace
from .vector_field import VectorFieldWorkspace
from .arbitrary import ArbitraryWorkspace

__all__ = [
    "PlotCanvas", "FunctionBox", "PlotWorkspace",
    "SliderFunctionBox", "Plot3D", "Plot3DCanvas",
    "ComplexWorkspace", "VectorFieldWorkspace",
    "ArbitraryWorkspace",
]
