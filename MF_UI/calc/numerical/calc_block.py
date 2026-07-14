# -*- coding: utf-8 -*-
"""数值分析计算块 — 通过 calc_engine.calculate_direct 统一调度。"""

from __future__ import annotations

import MF_Mathematics.numerical  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate_direct


class CalcBlock(BaseCalcBlock):
    """数值分析计算块。"""

    def get_mode_list(self) -> list[str]:
        return [
            "条件数", "截断误差", "舍入误差", "稳定性判断",
            "拉格朗日插值", "牛顿插值", "三次样条", "最小二乘拟合",
            "梯形法则", "辛普森法则", "高斯求积", "数值求导", "最优步长",
            "LU分解", "雅可比迭代", "高斯-赛德尔", "共轭梯度", "幂法", "QR算法",
            "欧拉方法", "RK4", "隐式欧拉", "刚性检测",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _do_dispatch(self, mod: str, act: str, expr: str):
        """通过 calc_engine 统一调度。"""
        from ast import literal_eval
        import re as _re

        if "=" in expr and expr.count("=") <= 3:
            parts = _re.split(r'[,;]\s*(?=[a-zA-Z_])', expr)
            kwargs = {}
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    kwargs[k.strip()] = literal_eval(v.strip())
            return calculate_direct(self.calc_mode_combo.currentText(), **kwargs)
        else:
            args = literal_eval(expr)
            if isinstance(args, (list, tuple)):
                return calculate_direct(self.calc_mode_combo.currentText(), *args)
            else:
                return calculate_direct(self.calc_mode_combo.currentText(), args)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    sys.exit(app.exec())
