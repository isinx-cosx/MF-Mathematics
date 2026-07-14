# -*- coding: utf-8 -*-
"""数值分析计算工作区 — 继承 BaseWorkspace。"""

from __future__ import annotations

from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.numerical.calc_block import CalcBlock


class Workspace(BaseWorkspace):
    """数值分析计算工作区（插值、积分、ODE 等）。"""

    def get_title(self) -> str:
        return "数值分析"

    def get_description(self) -> str:
        return "包含：插值、数值积分、ODE 数值解、非线性方程求根等"

    def create_calc_block(self, block_id: int,
                          on_delete: callable) -> BaseCalcBlock:
        return CalcBlock(block_id, on_delete, self)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    w = Workspace()
    w.resize(400, 200)
    w.setWindowTitle("数值分析测试")
    w.show()
    sys.exit(app.exec())
