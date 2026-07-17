# -*- coding: utf-8 -*-
"""复分析计算块。"""
from __future__ import annotations
import MF_Mathematics.complex_analysis  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "复数运算", "复共轭", "复模长", "复辐角",
            "复函数值", "全纯判定", "Cauchy积分",
            "留数", "Laurent级数", "围道积分",
            "共形映射", "Riemann ζ", "Dirichlet η",
            "零点与极点",
        ]

    def _get_module_name(self) -> str:
        return "complex_analysis"
