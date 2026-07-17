# -*- coding: utf-8 -*-
"""测度论计算块。"""
from __future__ import annotations
import MF_Mathematics.measure_theory  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate


class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "σ-代数判定", "生成σ-代数", "Borel σ-代数",
            "外测度", "Caratheodory可测", "勒贝格测度", "测度性质",
            "可测函数判定", "简单函数", "阶梯函数逼近",
            "简单函数积分", "非负函数积分", "一般勒贝格积分", "零测集无关性",
            "单调收敛定理", "Fatou引理", "控制收敛定理",
            "乘积测度", "Fubini定理",
            "概率空间", "随机变量(测度论)", "期望(测度论)", "条件期望", "独立性判定",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _get_module_name(self) -> str:
        return "measure_theory"

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr:
            return
        self._current_op = self.calc_mode_combo.currentText()
        self._guarded_calculate(expr, self._current_op)

    def _do_dispatch(self, mod: str, act: str, expr: str):
        return calculate(self._current_op, [expr])
