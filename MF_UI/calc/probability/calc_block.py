# -*- coding: utf-8 -*-
"""概率统计计算块 — 通过 calc_engine.calculate_direct 统一调度。"""

from __future__ import annotations

import MF_Mathematics.probability  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate_direct


class CalcBlock(BaseCalcBlock):
    """概率统计计算块 — 守卫 + AI 加速继承自 BaseCalcBlock。"""

    def get_mode_list(self) -> list[str]:
        return [
            "条件概率", "独立性", "全概率公式", "贝叶斯公式",
            "伯努利分布", "二项分布", "泊松分布",
            "均匀分布", "指数分布", "正态分布",
            "期望", "方差", "协方差", "相关系数",
            "大数定律", "中心极限定理",
            "样本均值", "样本方差", "矩估计", "MLE",
            "置信区间", "z检验", "t检验", "卡方检验", "p值",
            "单因素ANOVA", "双因素ANOVA",
            "线性回归", "预测", "残差",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _get_module_name(self) -> str:
        return "probability"

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
            if op in ("线性回归", "预测", "残差"):
                if len(val) == 2:
                    return calculate_direct(op, x_data=val[0], y_data=val[1])
            if op in ("单因素ANOVA", "双因素ANOVA"):
                return calculate_direct(op, groups=val)
            return calculate_direct(op, data=val)
        else:
            return calculate_direct(op, val=val)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    sys.exit(app.exec())
