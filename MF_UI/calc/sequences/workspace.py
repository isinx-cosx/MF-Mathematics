# -*- coding: utf-8 -*-
"""数列工作区。"""
from __future__ import annotations
from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.sequences.calc_block import CalcBlock

class Workspace(BaseWorkspace):
    def get_title(self) -> str: return "数列"
    def get_description(self) -> str: return "包含：等差/等比数列、递推数列等"
    def create_calc_block(self, block_id: int, on_delete) -> BaseCalcBlock: return CalcBlock(block_id, on_delete, self)
