# -*- coding: utf-8 -*-
"""泛函分析计算块。"""
from __future__ import annotations
import MF_Mathematics.functional_analysis  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "Lp范数", "Banach空间", "Hilbert空间",
            "线性算子", "算子范数", "谱半径",
            "Hahn-Banach定理", "一致有界原理",
            "开映射定理", "闭图像定理",
            "内积空间", "正交性", "正交投影",
            "弱收敛", "弱*收敛", "紧算子",
            "特征值问题", "Fredholm二择一",
            "Riesz表示定理", "共轭算子",
            "自伴算子判定",
        ]

    def _get_module_name(self) -> str:
        return "functional_analysis"
