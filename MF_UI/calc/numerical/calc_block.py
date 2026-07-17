# -*- coding: utf-8 -*-
"""数值分析计算块 — 通过 calc_engine.calculate_direct 统一调度。"""

from __future__ import annotations

import MF_Mathematics.numerical  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate_direct


class CalcBlock(BaseCalcBlock):
    """数值分析计算块 — 守卫 + AI 加速继承自 BaseCalcBlock。"""

    def get_mode_list(self) -> list[str]:
        return [
            "条件数", "截断误差", "舍入误差", "稳定性判断",
            "拉格朗日插值", "牛顿插值", "三次样条", "最小二乘拟合",
            "梯形法则", "辛普森法则", "高斯求积", "数值求导", "最优步长",
            "LU分解", "雅可比迭代", "高斯-赛德尔", "共轭梯度", "幂法", "QR算法",
            "欧拉方法", "RK4", "隐式欧拉", "刚性检测",
            "梯度下降", "相图",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _get_module_name(self) -> str:
        return "numerical"

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr:
            return
        op = self.calc_mode_combo.currentText()
        self._guarded_calculate(expr, op)

    def _do_dispatch(self, mod: str, act: str, expr: str):
        """通过 calc_engine 统一调度（智能参数解析）。"""
        from ast import literal_eval
        import re as _re

        op = self.calc_mode_combo.currentText()

        # 1. 尝试 key=value 格式解析
        if "=" in expr and not expr.strip().startswith(("[", "(")):
            parts = _re.split(r'[,;]\s*', expr)
            kwargs = {}
            all_kv = True
            for p in parts:
                p = p.strip()
                if "=" in p:
                    k, v = p.split("=", 1)
                    k = k.strip(); v = v.strip()
                    try: kwargs[k] = literal_eval(v)
                    except (ValueError, SyntaxError): kwargs[k] = v
                elif p:
                    all_kv = False
            if kwargs and all_kv:
                return calculate_direct(op, **kwargs)

        # 2. 尝试 literal_eval
        try:
            val = literal_eval(expr)
        except (ValueError, SyntaxError):
            # 3. 不是字面量 → 作为表达式字符串
            return calculate_direct(op, expr=expr)

        # 4. 字面量成功 → 根据类型路由
        if isinstance(val, (list, tuple)):
            # 插值类：点列表 [(x1,y1),...]
            if op in ("拉格朗日插值", "牛顿插值", "三次样条", "最小二乘拟合"):
                if val and isinstance(val[0], (list, tuple)):
                    return calculate_direct(op, points=val)
                return calculate_direct(op, x_points=val)
            return calculate_direct(op, matrix=val)
        else:
            return calculate_direct(op, val=val)

        # 梯度下降/相图 — 通过 calculate() 字符串路径
        if op in ("梯度下降", "相图"):
            from calc_engine import calculate
            return calculate(op, [expr])


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    sys.exit(app.exec())
