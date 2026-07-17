# -*- coding: utf-8 -*-
"""微积分计算块。"""
from __future__ import annotations
import MF_Mathematics.calculus  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "求导", "高阶导数", "偏导", "隐函数求导",
            "不定积分", "定积分", "广义积分", "重积分",
            "极限", "单侧极限", "无穷极限", "连续性判定",
            "泰勒展开", "级数展开", "幂级数",
            "单调性", "凹凸性", "拐点", "渐近线",
            "极值", "最值", "平均值",
            "弧长", "旋转体体积(圆盘)", "旋转体体积(壳)",
            "曲线间面积", "曲率", "曲率半径",
            "Rolle定理", "Lagrange中值定理", "Cauchy中值定理",
            "洛必达法则",
            "一阶ODE", "高阶ODE", "ODE系统", "ODE数值解",
            "一阶PDE", "二阶PDE",
            "Fourier级数", "Fourier系数", "复Fourier系数",
            "Fourier变换", "逆Fourier变换",
        ]

    def _get_module_name(self) -> str:
        return "calculus"
