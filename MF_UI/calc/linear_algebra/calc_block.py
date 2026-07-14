# -*- coding: utf-8 -*-
"""线性代数计算块 — 通过 calc_engine.calculate_direct 统一调度。"""

from __future__ import annotations

import MF_Mathematics.linear_algebra  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate_direct


class CalcBlock(BaseCalcBlock):
    """线性代数计算块。"""

    def get_mode_list(self) -> list[str]:
        return [
            "高斯消元", "矩阵秩", "求解方程组", "零空间",
            "特征值", "特征向量", "特征多项式", "可对角化", "对角化",
            "点积", "范数", "夹角", "正交性",
            "施密特正交化", "正交投影", "二次型", "正定性判定",
        ]

    # action_map 由 calc_engine.FUNC_MAP 统一管理，子类不再需要
    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _do_dispatch(self, mod: str, act: str, expr: str):
        """通过 calc_engine 统一调度。"""
        from ast import literal_eval
        import re as _re
        from MF_Mathematics.core.math_object import MathObject

        if "=" in expr and expr.count("=") <= 2:
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
