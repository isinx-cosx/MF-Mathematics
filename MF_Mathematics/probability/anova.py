# -*- coding: utf-8 -*-
"""方差分析 (ANOVA) — 单因素、双因素。

依赖: numpy, scipy
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
from scipy import stats

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="probability", action="one_way_anova")
def one_way_anova(
    groups: List[List[float]],
    alpha: float = 0.05,
) -> MathObject:
    """单因素方差分析。

    Args:
        groups: 各组数据列表，如 [[1,2,3], [4,5,6], [7,8,9]]。
        alpha: 显著性水平（默认 0.05）。

    Returns:
        MathObject，result 包含 F 统计量、p 值、结论等。
    """
    try:
        if len(groups) < 2:
            return MathObject(error="至少需要 2 组数据")
        for i, g in enumerate(groups):
            if len(g) < 2:
                return MathObject(error=f"第 {i+1} 组至少需要 2 个数据点")

        f_stat, p_value = stats.f_oneway(*groups)

        significant = p_value < alpha
        group_means = [np.mean(g) for g in groups]
        group_stds = [np.std(g, ddof=1) for g in groups]
        grand_mean = np.mean([x for g in groups for x in g])

        ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in groups)
        ss_within = sum(sum((x - np.mean(g)) ** 2 for x in g) for g in groups)
        df_between = len(groups) - 1
        df_within = sum(len(g) for g in groups) - len(groups)
        ms_between = ss_between / df_between if df_between > 0 else 0
        ms_within = ss_within / df_within if df_within > 0 else 0

        return MathObject(
            result={
                "F_statistic": float(f_stat),
                "p_value": float(p_value),
                "significant": bool(significant),
                "alpha": alpha,
                "group_means": [float(m) for m in group_means],
                "group_stds": [float(s) for s in group_stds],
                "grand_mean": float(grand_mean),
                "ss_between": float(ss_between),
                "ss_within": float(ss_within),
                "ms_between": float(ms_between),
                "ms_within": float(ms_within),
                "df_between": int(df_between),
                "df_within": int(df_within),
            },
            steps=[
                f"零假设 H0: 各组均值相等",
                f"备择假设 H1: 至少一组均值不同",
                f"组数 k = {len(groups)}, 总样本量 N = {df_within + df_between + 1}",
                f"F = MSB/MSW = {ms_between:.4f}/{ms_within:.4f} = {f_stat:.4f}",
                f"p = {p_value:.6f}",
                f"结论: {'拒绝 H0，组间差异显著' if significant else '不能拒绝 H0'} (α={alpha})",
            ],
            meaning=f"单因素 ANOVA: F({df_between},{df_within})={f_stat:.4f}, p={p_value:.6f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="two_way_anova")
def two_way_anova(
    data: List[List[float]],
    alpha: float = 0.05,
) -> MathObject:
    """双因素方差分析（无重复）。

    Args:
        data: 二维数据矩阵，行为因素 A 水平，列为因素 B 水平。
        alpha: 显著性水平。

    Returns:
        MathObject，包含行/列因素的 F 和 p 值。
    """
    try:
        arr = np.array(data, dtype=float)
        if arr.ndim != 2:
            return MathObject(error="数据必须为二维矩阵")
        rows, cols = arr.shape
        if rows < 2 or cols < 2:
            return MathObject(error="每个因素至少需要 2 个水平")

        grand_mean = arr.mean()
        ss_total = ((arr - grand_mean) ** 2).sum()

        row_means = arr.mean(axis=1)
        ss_row = cols * ((row_means - grand_mean) ** 2).sum()
        col_means = arr.mean(axis=0)
        ss_col = rows * ((col_means - grand_mean) ** 2).sum()
        ss_error = ss_total - ss_row - ss_col

        df_row = rows - 1
        df_col = cols - 1
        df_error = (rows - 1) * (cols - 1)

        ms_row = ss_row / df_row if df_row > 0 else 0
        ms_col = ss_col / df_col if df_col > 0 else 0
        ms_error = ss_error / df_error if df_error > 0 else 1e-9

        f_row = ms_row / ms_error
        f_col = ms_col / ms_error
        p_row = 1 - stats.f.cdf(f_row, df_row, df_error)
        p_col = 1 - stats.f.cdf(f_col, df_col, df_error)

        return MathObject(
            result={
                "factor_A": {"F": float(f_row), "p": float(p_row),
                             "significant": bool(p_row < alpha)},
                "factor_B": {"F": float(f_col), "p": float(p_col),
                             "significant": bool(p_col < alpha)},
                "ss": {"row": float(ss_row), "col": float(ss_col),
                       "error": float(ss_error), "total": float(ss_total)},
            },
            steps=[
                f"双因素 ANOVA ({rows}×{cols}):",
                f"因素 A: F({df_row},{df_error})={f_row:.4f}, p={p_row:.6f}"
                f" → {'显著' if p_row < alpha else '不显著'}",
                f"因素 B: F({df_col},{df_error})={f_col:.4f}, p={p_col:.6f}"
                f" → {'显著' if p_col < alpha else '不显著'}",
            ],
            meaning=f"双因素 ANOVA: A: F={f_row:.2f}, B: F={f_col:.2f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    print("=== ANOVA self_test ===")
    r = one_way_anova([[2,3,4,5], [6,7,8,9], [1,2,2,3]])
    assert r.ok, f"失败: {r.error}"
    assert "F_statistic" in r.result, r.result
    print(f"  PASS one_way: F={r.result['F_statistic']:.4f}, p={r.result['p_value']:.6f}")

    r2 = two_way_anova([[10,12,13], [14,15,16], [18,20,22]])
    assert r2.ok, f"失败: {r2.error}"
    print(f"  PASS two_way: A: p={r2.result['factor_A']['p']:.4f}, B: p={r2.result['factor_B']['p']:.4f}")
    print("=== ANOVA self_test: ALL PASSED ===")
    return True


if __name__ == "__main__":
    self_test()
