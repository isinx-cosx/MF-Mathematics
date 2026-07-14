# -*- coding: utf-8 -*-
"""线性代数计算工作区 — 继承 BaseWorkspace。"""

from __future__ import annotations

from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.linear_algebra.calc_block import CalcBlock


class Workspace(BaseWorkspace):
    """线性代数计算工作区（矩阵、向量、特征值等）。"""

    def get_title(self) -> str:
        return "线性代数"

    def get_description(self) -> str:
        return "包含：高斯消元、特征值、对角化、施密特正交化、二次型等"

    def create_calc_block(self, block_id: int,
                          on_delete: callable) -> BaseCalcBlock:
        return CalcBlock(block_id, on_delete, self)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    w = Workspace()
    w.resize(400, 200)
    w.setWindowTitle("线性代数测试")
    w.show()
    sys.exit(app.exec())
