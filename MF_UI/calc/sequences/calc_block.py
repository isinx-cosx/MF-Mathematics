# -*- coding: utf-8 -*-
"""数列计算块。"""

from __future__ import annotations

import MF_Mathematics.algebra  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate


class CalcBlock(BaseCalcBlock):
    """数列计算块。"""

    def get_mode_list(self) -> list[str]:
        return [
            "数列通项", "等差数列", "等差数列求和", "等差数列证明",
            "等比数列", "等比数列求和", "等比数列证明",
            "递推数列",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _get_module_name(self) -> str:
        return "algebra"

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr: return
        self._current_op = self.calc_mode_combo.currentText()
        self._guarded_calculate(expr, self._current_op)

    def _do_dispatch(self, mod: str, act: str, expr: str):
        return calculate(self._current_op, [expr])
