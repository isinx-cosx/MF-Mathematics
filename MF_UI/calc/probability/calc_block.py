# -*- coding: utf-8 -*-
"""概率统计计算块 — 继承 BaseCalcBlock，仅定义模式列表和分派映射。"""

from __future__ import annotations

import MF_Mathematics.probability  # noqa: 注册后端函数
from MF_UI.calc.base_calc_block import BaseCalcBlock


class CalcBlock(BaseCalcBlock):
    """概率统计计算块。"""

    def get_mode_list(self) -> list[str]:
        return [
            "条件概率", "独立性", "全概率公式", "贝叶斯公式",
            "伯努利分布", "二项分布", "泊松分布",
            "均匀分布", "指数分布", "正态分布",
            "期望", "方差", "协方差", "相关系数",
            "大数定律", "中心极限定理",
            "样本均值", "样本方差", "矩估计", "MLE",
            "置信区间", "z检验", "t检验", "卡方检验", "p值",
            "线性回归", "预测", "残差",
        ]

    def get_action_map(self) -> dict[str, tuple[str, str]]:
        return {
            "条件概率":        ("probability", "conditional_probability"),
            "独立性":          ("probability", "is_independent"),
            "全概率公式":       ("probability", "total_probability"),
            "贝叶斯公式":       ("probability", "bayes_theorem"),
            "伯努利分布":       ("probability", "bernoulli"),
            "二项分布":         ("probability", "binomial"),
            "泊松分布":         ("probability", "poisson"),
            "均匀分布":         ("probability", "uniform"),
            "指数分布":         ("probability", "exponential"),
            "正态分布":         ("probability", "normal"),
            "期望":             ("probability", "expectation"),
            "方差":             ("probability", "variance"),
            "协方差":           ("probability", "covariance"),
            "相关系数":         ("probability", "correlation_coefficient"),
            "大数定律":         ("probability", "law_of_large_numbers"),
            "中心极限定理":     ("probability", "central_limit_theorem"),
            "样本均值":         ("probability", "sample_mean"),
            "样本方差":         ("probability", "sample_variance"),
            "矩估计":           ("probability", "moment_estimate"),
            "MLE":              ("probability", "mle"),
            "置信区间":         ("probability", "confidence_interval"),
            "z检验":            ("probability", "z_test"),
            "t检验":            ("probability", "t_test"),
            "卡方检验":         ("probability", "chi_square_test"),
            "p值":              ("probability", "p_value"),
            "线性回归":         ("probability", "linear_regression"),
            "预测":             ("probability", "predict"),
            "残差":             ("probability", "residuals"),
        }


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    def dummy_delete(block):
        print(f"删除 block {block.block_id}")
    block = CalcBlock(0, dummy_delete)
    block.show()
    sys.exit(app.exec())
