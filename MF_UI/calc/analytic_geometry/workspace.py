# -*- coding: utf-8 -*-
"""解析几何工作区。"""

from __future__ import annotations

from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.analytic_geometry.calc_block import CalcBlock


class Workspace(BaseWorkspace):
    def get_title(self) -> str:
        return "解析几何"

    def get_description(self) -> str:
        return "包含：两点距离、中点、直线方程、圆方程等"

    def create_calc_block(self, block_id: int, on_delete) -> BaseCalcBlock:
        return CalcBlock(block_id, on_delete, self)
