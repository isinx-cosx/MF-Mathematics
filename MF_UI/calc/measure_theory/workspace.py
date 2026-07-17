# -*- coding: utf-8 -*-
"""测度论工作区。"""
from __future__ import annotations
from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.measure_theory.calc_block import CalcBlock


class Workspace(BaseWorkspace):
    def get_title(self) -> str:
        return "测度论"

    def get_description(self) -> str:
        return "包含：σ-代数、勒贝格测度、可测函数、勒贝格积分、收敛定理、乘积测度、Fubini定理、概率测度等"

    def create_calc_block(self, block_id: int, on_delete) -> BaseCalcBlock:
        return CalcBlock(block_id, on_delete, self)
