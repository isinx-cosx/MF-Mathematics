# -*- coding: utf-8 -*-
"""复分析计算块。"""

from __future__ import annotations

import MF_Mathematics.complex_analysis  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate


class CalcBlock(BaseCalcBlock):
    """复分析计算块。"""

    def get_mode_list(self) -> list[str]:
        return [
            "复数运算",
            "回路积分", "柯西定理", "柯西积分公式",
            "洛朗级数", "奇点分类", "留数", "留数定理",
            "辐角原理", "Rouche 定理",
            "Zeta 级数", "Zeta 解析延拓", "Zeta 函数方程", "Zeta 非平凡零点",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _get_module_name(self) -> str:
        return "complex_analysis"

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr: return
        self._current_op = self.calc_mode_combo.currentText()
        self._guarded_calculate(expr, self._current_op)

    def _do_dispatch(self, mod: str, act: str, expr: str):
        return calculate(self._current_op, [expr])
