# -*- coding: utf-8 -*-
"""泛函分析计算块。"""
from __future__ import annotations
import MF_Mathematics.functional_analysis  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate

class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "Lp 范数", "Banach 空间判定", "空间完备性",
            "算子范数", "有界性判定", "线性泛函求值", "核的维数",
            "Hahn-Banach 延拓", "一致有界原理", "开映射定理", "闭图像定理",
            "对偶空间基", "弱收敛", "自反性判定",
            "内积(泛函)", "正交性(泛函)", "Gram-Schmidt(泛函)", "Hilbert 空间判定",
            "谱逼近", "谱分类", "谱定理",
        ]
    def get_action_map(self) -> dict[str, tuple[str, str]]: return {}
    def _get_module_name(self) -> str: return "functional_analysis"
    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr: return
        self._current_op = self.calc_mode_combo.currentText()
        self._guarded_calculate(expr, self._current_op)
    def _do_dispatch(self, mod: str, act: str, expr: str):
        return calculate(self._current_op, [expr])
