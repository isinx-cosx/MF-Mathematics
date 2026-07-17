# -*- coding: utf-8 -*-
"""代数拓扑工作区。"""
from __future__ import annotations
from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.algebraic_topology.calc_block import CalcBlock


class Workspace(BaseWorkspace):
    def get_title(self) -> str:
        return "代数拓扑"

    def get_description(self) -> str:
        return "包含：基本群、同调群、上同调、贝蒂数、欧拉示性数、映射度、不动点定理、持续同调等"

    def create_calc_block(self, block_id: int, on_delete) -> BaseCalcBlock:
        return CalcBlock(block_id, on_delete, self)
