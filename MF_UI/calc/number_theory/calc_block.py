# -*- coding: utf-8 -*-
"""数论计算块。"""
from __future__ import annotations
import MF_Mathematics.number_theory  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    def get_mode_list(self) -> list[str]:
        return [
            "最大公约数", "扩展欧几里得", "模逆元", "模幂",
            "欧拉函数", "约数个数", "约数和", "莫比乌斯函数",
            "中国剩余定理", "原根", "离散对数",
            "埃氏筛", "分段筛", "素数判定", "素因数分解",
            "连分数", "连分数逼近", "最佳有理逼近",
            "欧拉乘积", "Dirichlet L 函数", "伯努利数",
        ]

    def _get_module_name(self) -> str:
        return "number_theory"
