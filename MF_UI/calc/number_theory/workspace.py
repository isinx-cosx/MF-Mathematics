# -*- coding: utf-8 -*-
"""数论工作区。"""
from __future__ import annotations
from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.number_theory.calc_block import CalcBlock

class Workspace(BaseWorkspace):
    def get_title(self) -> str: return "数论"
    def get_description(self) -> str: return "包含：素数、模运算、欧拉函数、连分数、中国剩余定理等"
    def create_calc_block(self, block_id: int, on_delete) -> BaseCalcBlock: return CalcBlock(block_id, on_delete, self)
