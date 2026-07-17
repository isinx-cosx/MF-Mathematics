# -*- coding: utf-8 -*-
"""代数拓扑计算块。"""
from __future__ import annotations
import MF_Mathematics.algebraic_topology  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate


class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "基本群", "单连通判定", "路径同伦",
            "单纯复形", "边界算子", "同调群",
            "贝蒂数", "欧拉示性数", "上同调群",
            "杯积", "庞加莱对偶",
            "映射度", "Brouwer不动点定理", "毛球定理",
            "过滤复形", "持续同调图", "条形码",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _get_module_name(self) -> str:
        return "algebraic_topology"

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr:
            return
        self._current_op = self.calc_mode_combo.currentText()
        self._guarded_calculate(expr, self._current_op)

    def _do_dispatch(self, mod: str, act: str, expr: str):
        return calculate(self._current_op, [expr])
