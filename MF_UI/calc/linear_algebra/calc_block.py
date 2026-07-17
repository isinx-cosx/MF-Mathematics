# -*- coding: utf-8 -*-
"""线性代数计算块 — 通过 calc_engine.calculate_direct 统一调度。"""

from __future__ import annotations

import MF_Mathematics.linear_algebra  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate_direct


class CalcBlock(BaseCalcBlock):
    """线性代数计算块 — 守卫 + AI 加速继承自 BaseCalcBlock。"""

    def get_mode_list(self) -> list[str]:
        return [
            "高斯消元", "矩阵秩", "求解方程组", "零空间",
            "特征值", "特征向量", "特征多项式", "可对角化", "对角化",
            "点积", "范数", "夹角", "正交性",
            "施密特正交化", "正交投影", "二次型", "正定性判定",
            # ── 向量空间 ──
            "向量空间判定", "线性组合", "线性无关判定", "基", "维数", "张成子空间",
            # ── 线性变换 ──
            "线性变换", "矩阵表示", "核", "像", "秩-零化度", "逆矩阵",
            # ── 二次型补充 ──
            "标准化", "负定判定", "不定判定",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _get_module_name(self) -> str:
        return "linear_algebra"

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
            # 用逗号或分号分隔
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
                    # 没有 = 的部分 → 尝试作为值或 var=value
                    all_kv = False
            if kwargs and all_kv:
                return calculate_direct(op, **kwargs)

        # 2. 尝试 literal_eval
        try:
            val = literal_eval(expr)
        except (ValueError, SyntaxError):
            # 3. 不是字面量 → 作为表达式字符串
            return calculate_direct(op, expr=expr)

        # 4. 字面量成功 → 根据操作类型路由参数
        if isinstance(val, (list, tuple)):
            if op in ("高斯消元", "矩阵秩", "求解方程组", "零空间",
                      "特征值", "特征向量", "特征多项式", "可对角化",
                      "对角化", "二次型", "正定性判定",
                      "施密特正交化", "正交投影",
                      "向量空间判定", "线性组合", "线性无关判定", "基", "维数",
                      "张成子空间", "线性变换", "矩阵表示", "核", "像", "秩-零化度",
                      "标准化", "负定判定", "不定判定", "逆矩阵"):
                return calculate_direct(op, matrix=val)
            elif op in ("范数",):
                return calculate_direct(op, vector=val)
            elif op in ("点积", "夹角", "正交性"):
                if len(val) == 2:
                    return calculate_direct(op, v1=val[0], v2=val[1])
                return calculate_direct(op, matrix=val)
            else:
                return calculate_direct(op, matrix=val)
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
