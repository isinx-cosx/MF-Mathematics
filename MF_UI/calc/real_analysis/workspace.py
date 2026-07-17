# -*- coding: utf-8 -*-
"""实分析工作区。"""
from __future__ import annotations
from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.real_analysis.calc_block import CalcBlock

class Workspace(BaseWorkspace):
    def get_title(self) -> str: return "实分析"
    def get_description(self) -> str: return "包含：ε-δ极限、一致收敛、黎曼积分、介值/极值定理等"
    def create_calc_block(self, block_id: int, on_delete) -> BaseCalcBlock: return CalcBlock(block_id, on_delete, self)
