# -*- coding: utf-8 -*-
"""概率统计计算工作区 — 继承 BaseWorkspace。"""

from __future__ import annotations

from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.base_calc_block import BaseCalcBlock
from MF_UI.calc.probability.calc_block import CalcBlock


class Workspace(BaseWorkspace):
    """概率统计计算工作区（分布、检验、回归等）。"""

    def get_title(self) -> str:
        return "概率论与数理统计"

    def get_description(self) -> str:
        return "包含：概率空间、随机变量、分布族、统计推断、回归分析等"

    def create_calc_block(self, block_id: int,
                          on_delete: callable) -> BaseCalcBlock:
        return CalcBlock(block_id, on_delete, self)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    w = Workspace()
    w.resize(400, 200)
    w.setWindowTitle("概率统计测试")
    w.show()
    sys.exit(app.exec())
