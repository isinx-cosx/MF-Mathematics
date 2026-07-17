# -*- coding: utf-8 -*-
"""实分析计算块。"""
from __future__ import annotations
import MF_Mathematics.real_analysis  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "数列极限(ε-N)", "数列收敛判定", "柯西收敛准则",
            "ε-δ 极限定义", "导数定义", "一致连续",
            "介值定理", "极值定理", "上确界", "下确界",
            "黎曼可积判定", "达布和", "微积分基本定理",
            "一致收敛", "逐点收敛", "Weierstrass M-判别",
            "逐项微分", "逐项积分",
        ]

    def _get_module_name(self) -> str:
        return "real_analysis"
