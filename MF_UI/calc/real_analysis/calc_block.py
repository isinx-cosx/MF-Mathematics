# -*- coding: utf-8 -*-
"""实分析计算块。"""
from __future__ import annotations
import MF_Mathematics.real_analysis  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate

class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "数列极限(ε-N)", "数列收敛判定", "柯西收敛准则",
            "ε-δ 极限定义", "导数定义", "一致连续",
            "介值定理", "极值定理", "上确界", "下确界",
            "黎曼可积判定", "达布和", "微积分基本定理",
            "一致收敛", "逐点收敛", "Weierstrass M-判别",
            "逐项微分", "逐项积分",
        ]
    def get_action_map(self) -> dict[str, tuple[str, str]]: return {}
    def _get_module_name(self) -> str: return "real_analysis"
    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr: return
        self._current_op = self.calc_mode_combo.currentText()
        self._guarded_calculate(expr, self._current_op)
    def _do_dispatch(self, mod: str, act: str, expr: str):
        return calculate(self._current_op, [expr])
