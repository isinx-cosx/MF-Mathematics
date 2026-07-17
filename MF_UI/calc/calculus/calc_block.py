# -*- coding: utf-8 -*-
"""微积分计算块。"""

from __future__ import annotations

import MF_Mathematics.calculus  # noqa
from MF_UI.calc.base_calc_block import BaseCalcBlock
from calc_engine import calculate


class CalcBlock(BaseCalcBlock):
    """微积分计算块。"""

    def get_mode_list(self) -> list[str]:
        return [
            "求导", "某点导数", "隐函数求导", "参数方程求导",
            "定积分", "不定积分", "数值积分", "反常积分",
            "极限", "连续性判断", "间断点分类", "洛必达法则",
            "单调性", "局部极值", "全局最值",
            "泰勒展开", "幂级数展开", "级数求和", "级数敛散性",
            "微分", "罗尔定理", "拉格朗日中值定理",
            "曲线间面积", "旋转体体积(圆盘法)", "旋转体体积(柱壳法)", "弧长",
            "幂级数收敛半径",
            "莱布尼茨判别法", "极限比较判别法", "积分判别法",
            "直接比较判别法", "p-级数判别法", "综合判别与分类",
            # ── 傅里叶分析 ──
            "傅里叶系数", "傅里叶级数", "复傅里叶系数", "正交性验证",
            "傅里叶变换", "逆傅里叶变换", "普兰舍利定理",
            "高斯函数傅里叶变换",
            "卷积", "卷积定理", "高斯模糊", "低通滤波器",
            "δ 分布", "δ 的傅里叶变换", "常数的傅里叶变换", "缓增分布",
            "不确定性原理", "短时傅里叶变换", "小波变换",
            "泊松求和", "Theta 函数", "函数方程演示",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def _get_module_name(self) -> str:
        return "calculus"

    def on_calc_clicked(self) -> None:
        expr = self.input_box.text().strip()
        if not expr:
            return
        self._current_op = self.calc_mode_combo.currentText()
        self._guarded_calculate(expr, self._current_op)

    def _do_dispatch(self, mod: str, act: str, expr: str):
        return calculate(self._current_op, [expr])
