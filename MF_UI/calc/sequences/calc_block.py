# -*- coding: utf-8 -*-
"""数列计算块。"""
from __future__ import annotations
import MF_Mathematics.algebra  # noqa — sequences 在 algebra 包中
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "等差数列第n项", "等比数列第n项",
            "数列求和", "数列求积",
            "无穷级数求和", "无穷乘积",
            "级数收敛判定", "级数绝对收敛",
        ]

    def _get_module_name(self) -> str:
        return "algebra"
