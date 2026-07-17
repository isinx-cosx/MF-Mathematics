# -*- coding: utf-8 -*-
"""解析几何计算块。"""
from __future__ import annotations
import MF_Mathematics.algebra  # noqa — analytic_geometry 在 algebra 包中
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "两点距离", "中点坐标", "斜率",
            "直线方程", "圆标准方程", "圆一般方程",
            "椭圆方程", "双曲线方程", "抛物线方程",
        ]

    def _get_module_name(self) -> str:
        return "algebra"
