# -*- coding: utf-8 -*-
"""解析几何计算块。"""

from __future__ import annotations

import MF_Mathematics.algebra  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate


class CalcBlock(BaseCalcBlock):
    """解析几何计算块。"""

    def get_mode_list(self) -> list[str]:
        return [
            "两点距离", "中点",
            "两点式直线", "斜截式直线", "点斜式直线",
            "截距式直线", "直线一般式",
            "圆标准方程", "圆一般方程",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _get_module_name(self) -> str:
        return "algebra"

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr:
            return
        op = self.calc_mode_combo.currentText()
        self._current_op = op
        self._guarded_calculate(expr, op)

    def _do_dispatch(self, mod: str, act: str, expr: str):
        return calculate(self._current_op, [expr])
