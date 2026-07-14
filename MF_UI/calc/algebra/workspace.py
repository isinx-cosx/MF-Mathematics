# -*- coding: utf-8 -*-
"""代数计算工作区 — 继承 BaseWorkspace。"""

from __future__ import annotations

from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.algebra.calc_block import CalcBlock


class Workspace(BaseWorkspace):
    """代数计算工作区（求导、积分、极限、方程等）。"""

    def get_title(self) -> str:
        return "代数计算"

    def get_description(self) -> str:
        return "包含：表达式化简、求导、积分、极限、级数展开、复数运算等"

    def create_calc_block(self, block_id: int,
                          on_delete: callable) -> BaseCalcBlock:
        return CalcBlock(block_id, on_delete, self)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    w = Workspace()
    w.resize(400, 200)
    w.setWindowTitle("代数计算测试")
    w.show()
    sys.exit(app.exec())
