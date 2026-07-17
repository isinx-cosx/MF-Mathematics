# -*- coding: utf-8 -*-
"""微积分工作区。"""
from __future__ import annotations
from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.calculus.calc_block import CalcBlock

class Workspace(BaseWorkspace):
    def get_title(self) -> str: return "微积分"
    def get_description(self) -> str: return "包含：求导/积分/极限/级数/微分应用/积分应用/收敛判别等"
    def create_calc_block(self, block_id: int, on_delete) -> BaseCalcBlock: return CalcBlock(block_id, on_delete, self)
