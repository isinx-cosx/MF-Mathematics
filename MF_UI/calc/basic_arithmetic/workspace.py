# -*- coding: utf-8 -*-
"""基础运算工作区 — 计算器风格界面。"""

from MF_UI.calc.base_workspace import BaseWorkspace
from MF_UI.calc.basic_arithmetic.calculator import CalculatorWidget


class Workspace(BaseWorkspace):
    """基础运算工作区 — 单块计算器模式，不支持多块管理。"""

    _enable_add_block = False

    def get_title(self) -> str:
        return "基础运算"

    def get_description(self) -> str:
        return "计算器风格的基础数学运算 — 四则运算 · 乘方 · 开方 · 阶乘 · 三角函数 · 对数"

    def create_calc_block(self, block_id: int,
                          on_delete: callable) -> CalculatorWidget:
        return CalculatorWidget(self)

    def _on_add_block(self) -> None:
        """重写 — 计算器需要更大高度（~420px vs 默认 120px）。"""
        super()._on_add_block()
        if self._blocks:
            self._blocks[-1].setFixedHeight(420)
