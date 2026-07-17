# -*- coding: utf-8 -*-
"""复分析工作区。"""
from __future__ import annotations
from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.complex_analysis.calc_block import CalcBlock

class Workspace(BaseWorkspace):
    def get_title(self) -> str: return "复分析"
    def get_description(self) -> str: return "包含：复数运算、回路积分、柯西定理、留数、洛朗级数、Zeta函数等"
    def create_calc_block(self, block_id: int, on_delete) -> BaseCalcBlock: return CalcBlock(block_id, on_delete, self)
