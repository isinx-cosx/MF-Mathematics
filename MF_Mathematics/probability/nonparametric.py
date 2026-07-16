# -*- coding: utf-8 -*-
"""非参数统计检验 — Mann-Whitney U、Kruskal-Wallis H、Wilcoxon 符号秩。

不依赖总体分布假设，适用于小样本或非正态数据。

依赖: numpy, scipy
"""

from __future__ import annotations

from typing import List, Optional, Union

import numpy as np
from scipy import stats

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="probability", action="mann_whitney_u")
def mann_whitney_u(
    group1: List[float],
    group2: List[float],
    alternative: str = "two-sided",
    alpha: float = 0.05,
) -> MathObject:
    """Mann-Whitney U 检验（Wilcoxon 秩和检验）。

    用于比较两个独立样本的分布是否相同，是两独立样本 t 检验的非参数替代。

    Args:
        group1: 第一组样本数据。
        group2: 第二组样本数据。
        alternative: 备择假设方向 — "two-sided"、"less"、"greater"。
        alpha: 显著性水平（默认 0.05）。

    Returns:
        MathObject，result 包含 U 统计量、p 值、结论等。
    """
    try:
        if len(group1) < 2 or len(group2) < 2:
            return MathObject(error="每组至少需要 2 个数据点")

        arr1 = np.array(group1, dtype=float)
        arr2 = np.array(group2, dtype=float)

        # scipy 的 mannwhitneyu 计算 U 统计量
        result = stats.mannwhitneyu(arr1, arr2, alternative=alternative)
        u_stat = float(result.statistic)
        p_value = float(result.pvalue)

        n1, n2 = len(arr1), len(arr2)
        # 另一个 U 值: U1 + U2 = n1 * n2
        u2 = n1 * n2 - u_stat

        med1 = float(np.median(arr1))
        med2 = float(np.median(arr2))

        significant = p_value < alpha

        alt_text = {
            "two-sided": f"分布不同 (≠)",
            "less": f"group1 < group2",
            "greater": f"group1 > group2",
        }.get(alternative, alternative)

        return MathObject(
            result={
                "U_statistic": u_stat,
                "U2": u2,
                "p_value": p_value,
                "significant": significant,
                "alpha": alpha,
                "n1": n1,
                "n2": n2,
                "median1": med1,
                "median2": med2,
                "alternative": alternative,
            },
            steps=[
                f"Mann-Whitney U 检验 (α={alpha})",
                f"备择假设: {alt_text}",
                f"样本量: n₁={n1}, n₂={n2}",
                f"中位数: M₁={med1:.4f}, M₂={med2:.4f}",
                f"U = {u_stat:.4f} (U' = {u2:.4f})",
                f"p = {p_value:.6f}",
                f"结论: {'拒绝 H₀，两组分布差异显著' if significant else '不能拒绝 H₀'}",
            ],
            meaning=f"Mann-Whitney U = {u_stat:.2f}, p = {p_value:.6f}"
                    f" → {'显著' if significant else '不显著'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="kruskal_wallis")
def kruskal_wallis(
    groups: List[List[float]],
    alpha: float = 0.05,
) -> MathObject:
    """Kruskal-Wallis H 检验。

    用于比较三个或以上独立样本的分布是否相同，
    是单因素 ANOVA 的非参数替代。

    Args:
        groups: 各组数据列表，如 [[1,2,3], [4,5,6], [7,8,9]]。
        alpha: 显著性水平（默认 0.05）。

    Returns:
        MathObject，result 包含 H 统计量、p 值、结论等。
    """
    try:
        if len(groups) < 3:
            return MathObject(error="Kruskal-Wallis 检验至少需要 3 组数据")

        for i, g in enumerate(groups):
            if len(g) < 2:
                return MathObject(error=f"第 {i+1} 组至少需要 2 个数据点")

        h_stat, p_value = stats.kruskal(*groups)

        significant = p_value < alpha
        group_medians = [float(np.median(g)) for g in groups]
        group_sizes = [len(g) for g in groups]

        # 计算平均秩（用于解释）
        all_data = np.concatenate([np.array(g, dtype=float) for g in groups])
        from scipy.stats import rankdata
        ranks = rankdata(all_data)
        idx = 0
        mean_ranks = []
        for size in group_sizes:
            mean_ranks.append(float(np.mean(ranks[idx:idx + size])))
            idx += size

        return MathObject(
            result={
                "H_statistic": float(h_stat),
                "p_value": float(p_value),
                "significant": bool(significant),
                "alpha": alpha,
                "group_medians": group_medians,
                "group_sizes": group_sizes,
                "mean_ranks": mean_ranks,
                "n_groups": len(groups),
            },
            steps=[
                f"Kruskal-Wallis H 检验 (α={alpha})",
                f"组数 k = {len(groups)}, 总样本量 N = {sum(group_sizes)}",
                f"各组中位数: {[f'{m:.4f}' for m in group_medians]}",
                f"各组平均秩: {[f'{r:.2f}' for r in mean_ranks]}",
                f"H = {h_stat:.4f}, df = {len(groups) - 1}",
                f"p = {p_value:.6f}",
                f"结论: {'拒绝 H₀，至少一组分布不同' if significant else '不能拒绝 H₀'}",
            ],
            meaning=f"Kruskal-Wallis H = {h_stat:.2f}, p = {p_value:.6f}"
                    f" → {'显著' if significant else '不显著'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="wilcoxon_signed_rank")
def wilcoxon_signed_rank(
    group1: List[float],
    group2: Optional[List[float]] = None,
    mu: float = 0.0,
    alternative: str = "two-sided",
    alpha: float = 0.05,
) -> MathObject:
    """Wilcoxon 符号秩检验。

    用于比较配对样本或单样本中位数的非参数检验，
    是配对 t 检验的非参数替代。

    Args:
        group1: 第一组样本或单样本数据。
        group2: 第二组样本（配对数据时提供）；为 None 时做单样本检验。
        mu: 单样本检验时的零假设中位数（仅 group2=None 时使用）。
        alternative: 备择假设方向 — "two-sided"、"less"、"greater"。
        alpha: 显著性水平（默认 0.05）。

    Returns:
        MathObject，result 包含 W 统计量、p 值、结论等。
    """
    try:
        arr1 = np.array(group1, dtype=float)

        if group2 is not None:
            # 配对检验
            arr2 = np.array(group2, dtype=float)
            if len(arr1) != len(arr2):
                return MathObject(error=f"配对样本长度不一致: {len(arr1)} ≠ {len(arr2)}")
            if len(arr1) < 3:
                return MathObject(error="配对样本至少需要 3 对数据")
            diff = arr1 - arr2
            test_type = "配对"
            desc = f"d = group1 - group2"
        else:
            # 单样本检验 (H₀: 中位数 = mu)
            diff = arr1 - mu
            if len(arr1) < 3:
                return MathObject(error="样本至少需要 3 个数据点")
            test_type = "单样本"
            desc = f"H₀: 中位数 = {mu}"

        # 去除差值为零的对
        nonzero = diff[diff != 0]
        n_zero = len(diff) - len(nonzero)

        if len(nonzero) < 3:
            return MathObject(error=f"非零差值数量({len(nonzero)})不足，无法检验")

        result = stats.wilcoxon(nonzero, alternative=alternative)
        # scipy ≥ 1.11 返回 WilcoxonResult 带 statistic/pvalue
        w_stat = float(getattr(result, 'statistic', result[0]))
        p_value = float(getattr(result, 'pvalue', result[1]))

        significant = p_value < alpha

        alt_text = {
            "two-sided": f"中位数{'差' if group2 else ''} ≠ 0",
            "less": f"中位数{'差' if group2 else ''} < 0",
            "greater": f"中位数{'差' if group2 else ''} > 0",
        }.get(alternative, alternative)

        return MathObject(
            result={
                "W_statistic": w_stat,
                "p_value": p_value,
                "significant": significant,
                "alpha": alpha,
                "n": len(arr1),
                "n_nonzero": len(nonzero),
                "n_zero": int(n_zero),
                "alternative": alternative,
                "test_type": test_type,
                "median_diff": float(np.median(diff)),
            },
            steps=[
                f"Wilcoxon 符号秩检验 ({test_type}, α={alpha})",
                desc,
                f"样本量: n = {len(arr1)}, 非零差: {len(nonzero)}, 零差: {n_zero}",
                f"差值中位数: {np.median(diff):.4f}",
                f"W = {w_stat:.4f}",
                f"p = {p_value:.6f}",
                f"备择假设: {alt_text}",
                f"结论: {'拒绝 H₀，差异显著' if significant else '不能拒绝 H₀'}",
            ],
            meaning=f"Wilcoxon W = {w_stat:.2f}, p = {p_value:.6f}"
                    f" → {'显著' if significant else '不显著'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 nonparametric 模块。"""
    import sys
    print("=== nonparametric self_test ===")

    try:
        # Mann-Whitney U
        g1 = [2.0, 3.0, 4.0, 5.0, 6.0]
        g2 = [7.0, 8.0, 9.0, 10.0, 11.0]
        r = mann_whitney_u(g1, g2)
        assert r.ok, f"失败: {r.error}"
        assert r.result["U_statistic"] == 0  # 完全不重叠
        assert r.result["significant"]
        print(f"  PASS Mann-Whitney U: U={r.result['U_statistic']}, p={r.result['p_value']:.6f}")

        # Kruskal-Wallis
        r2 = kruskal_wallis([[2,3,4], [5,6,7], [8,9,10]])
        assert r2.ok, f"失败: {r2.error}"
        assert "H_statistic" in r2.result
        print(f"  PASS Kruskal-Wallis: H={r2.result['H_statistic']:.4f}, p={r2.result['p_value']:.6f}")

        # Wilcoxon signed-rank (paired)
        r3 = wilcoxon_signed_rank([10,12,14,15,18], [8,9,11,13,15])
        assert r3.ok, f"失败: {r3.error}"
        assert r3.result["test_type"] == "配对"
        print(f"  PASS Wilcoxon (paired): W={r3.result['W_statistic']:.4f}, p={r3.result['p_value']:.6f}")

        # Wilcoxon signed-rank (one-sample)
        r4 = wilcoxon_signed_rank([1.5, 2.0, 2.5, 3.0, 3.5], mu=2.0)
        assert r4.ok, f"失败: {r4.error}"
        assert r4.result["test_type"] == "单样本"
        print(f"  PASS Wilcoxon (one-sample): W={r4.result['W_statistic']:.4f}, p={r4.result['p_value']:.6f}")

        print("=== nonparametric self_test: ALL PASSED ===")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    exit(0 if self_test() else 1)
