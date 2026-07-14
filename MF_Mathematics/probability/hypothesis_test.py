"""假设检验 — Z 检验、t 检验、卡方检验、p 值计算。

依赖: numpy, scipy.stats
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

import numpy as np
from scipy import stats as sc_stats

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="probability", action="z_test")
def z_test(
    sample_mean: float,
    mu0: float,
    sigma: float,
    n: int,
    alpha: float = 0.05,
    alternative: str = "two-sided",
) -> MathObject:
    """单样本 Z 检验（总体方差已知）。

    H0: μ = μ0 vs H1: μ ≠ μ0 / μ > μ0 / μ < μ0。

    Args:
        sample_mean: 样本均值 X̄。
        mu0: 原假设的总体均值。
        sigma: 已知总体标准差。
        n: 样本量。
        alpha: 显著性水平，默认 0.05。
        alternative: 备择假设方向，'two-sided' / 'greater' / 'less'。

    Returns:
        MathObject:
            - result: {"Z": ..., "p_value": ..., "reject_H0": ..., "critical_value": ...}。
    """
    try:
        if sigma <= 0:
            return MathObject(error="σ 必须 > 0。")
        if n <= 0:
            return MathObject(error="n 必须 > 0。")

        import math

        se = sigma / math.sqrt(n)
        z_val = (sample_mean - mu0) / se

        # 计算 p 值
        if alternative == "two-sided":
            p_val = 2 * (1 - sc_stats.norm.cdf(abs(z_val)))
            z_crit = sc_stats.norm.ppf(1 - alpha / 2)
        elif alternative == "greater":
            p_val = 1 - sc_stats.norm.cdf(z_val)
            z_crit = sc_stats.norm.ppf(1 - alpha)
        elif alternative == "less":
            p_val = sc_stats.norm.cdf(z_val)
            z_crit = sc_stats.norm.ppf(alpha)
        else:
            return MathObject(error="alternative 必须为 'two-sided' / 'greater' / 'less'。")

        reject = p_val < alpha

        return MathObject(
            result={
                "Z": float(z_val),
                "p_value": float(p_val),
                "alpha": alpha,
                "critical_value": float(z_crit),
                "reject_H0": reject,
                "alternative": alternative,
            },
            steps=[
                f"H0: μ = {mu0}",
                f"H1: μ {'≠' if alternative == 'two-sided' else ('>' if alternative == 'greater' else '<')} {mu0}",
                f"标准误 SE = σ/√n = {sigma}/{math.sqrt(n):.2f} = {se:.4f}",
                f"Z = (X̄ - μ0) / SE = ({sample_mean} - {mu0}) / {se:.4f} = {z_val:.4f}",
                f"p-value = {p_val:.6f}",
                f"临界值 Z_crit = {z_crit:.4f}",
                (
                    f"p < α ({p_val:.4f} < {alpha})，拒绝 H0。"
                    if reject
                    else f"p ≥ α ({p_val:.4f} ≥ {alpha})，不拒绝 H0。"
                ),
            ],
            meaning=f"Z 检验结果: Z={z_val:.3f}, p={p_val:.4f}, "
                    f"{'拒绝' if reject else '不拒绝'} H0。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="t_test")
def t_test(
    data: List[float],
    mu0: float,
    alpha: float = 0.05,
    alternative: str = "two-sided",
) -> MathObject:
    """单样本 t 检验（总体方差未知）。

    H0: μ = μ0。

    Args:
        data: 样本数据列表。
        mu0: 原假设的总体均值。
        alpha: 显著性水平。
        alternative: 备择假设方向。

    Returns:
        MathObject:
            - result: t 检验结果字典。
    """
    try:
        arr = np.asarray(data, dtype=float)
        n = len(arr)
        if n < 2:
            return MathObject(error="样本量 n < 2，无法进行 t 检验。")

        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr, ddof=1))
        se = std_val / np.sqrt(n)
        t_val = (mean_val - mu0) / se

        df = n - 1

        if alternative == "two-sided":
            p_val = 2 * (1 - sc_stats.t.cdf(abs(t_val), df))
            t_crit = sc_stats.t.ppf(1 - alpha / 2, df)
        elif alternative == "greater":
            p_val = 1 - sc_stats.t.cdf(t_val, df)
            t_crit = sc_stats.t.ppf(1 - alpha, df)
        elif alternative == "less":
            p_val = sc_stats.t.cdf(t_val, df)
            t_crit = sc_stats.t.ppf(alpha, df)
        else:
            return MathObject(error="alternative 必须为 'two-sided' / 'greater' / 'less'。")

        reject = p_val < alpha

        return MathObject(
            result={
                "t": float(t_val),
                "p_value": float(p_val),
                "df": df,
                "alpha": alpha,
                "critical_value": float(t_crit),
                "reject_H0": reject,
                "alternative": alternative,
            },
            steps=[
                f"H0: μ = {mu0}",
                f"样本量 n = {n}",
                f"样本均值 X̄ = {mean_val:.4f}",
                f"样本标准差 s = {std_val:.4f}",
                f"标准误 SE = s/√n = {se:.4f}",
                f"t = ({mean_val:.4f} - {mu0}) / {se:.4f} = {t_val:.4f}",
                f"自由度 df = {df}",
                f"p-value = {p_val:.6f}",
                (
                    f"p < α，拒绝 H0。"
                    if reject
                    else f"p ≥ α，不拒绝 H0。"
                ),
            ],
            meaning=f"t 检验: t({df})={t_val:.3f}, p={p_val:.4f}, "
                    f"{'拒绝' if reject else '不拒绝'} H0。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="chi_square_test")
def chi_square_test(
    observed: List[float],
    expected: List[float],
) -> MathObject:
    """卡方拟合优度检验。

    H0: 观测频数符合期望频数。
    χ² = Σ (Oi - Ei)² / Ei。

    Args:
        observed: 观测频数列表。
        expected: 期望频数列表（长度相同）。

    Returns:
        MathObject:
            - result: {"chi2": ..., "df": ..., "p_value": ..., "reject_H0": ...}。
    """
    try:
        obs = np.asarray(observed, dtype=float)
        exp = np.asarray(expected, dtype=float)

        if len(obs) != len(exp):
            return MathObject(error="观测和期望频数列表长度必须相同。")
        if np.any(exp <= 0):
            return MathObject(error="期望频数必须全部 > 0。")

        # 计算卡方统计量
        chi2_contrib = (obs - exp) ** 2 / exp
        chi2 = float(np.sum(chi2_contrib))
        df = len(obs) - 1

        if df < 1:
            return MathObject(error="自由度 df < 1，无法检验。")

        p_val = 1 - sc_stats.chi2.cdf(chi2, df)

        return MathObject(
            result={
                "chi2": chi2,
                "df": df,
                "p_value": float(p_val),
                "contributions": [float(c) for c in chi2_contrib],
                "reject_H0": p_val < 0.05,
            },
            steps=[
                f"观测值: {list(obs)}",
                f"期望值: {list(exp)}",
                f"各分类 χ² 贡献: {[f'{c:.3f}' for c in chi2_contrib]}",
                f"χ² = {chi2:.4f}",
                f"自由度 df = {df}",
                f"p-value = {p_val:.6f}",
                (
                    f"p < 0.05，拒绝 H0（观测与期望有显著差异）。"
                    if p_val < 0.05
                    else f"p ≥ 0.05，不拒绝 H0（无显著差异）。"
                ),
            ],
            meaning=f"卡方拟合优度检验: χ²({df})={chi2:.3f}, p={p_val:.4f}。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="p_value")
def p_value(
    test_statistic: float,
    dist: str,
    df: int = 1,
    alternative: str = "two-sided",
) -> MathObject:
    """根据检验统计量计算 p 值。

    Args:
        test_statistic: 检验统计量的值（Z、t、χ² 等）。
        dist: 分布类型: 'normal' / 't' / 'chi2'。
        df: 自由度（仅 t 和 chi2 需要）。
        alternative: 'two-sided' / 'greater' / 'less'（chi2 固定为右侧）。

    Returns:
        MathObject:
            - result: p 值。
    """
    try:
        dist_lower = dist.lower()

        if dist_lower == "normal":
            if alternative == "two-sided":
                p = 2 * (1 - sc_stats.norm.cdf(abs(test_statistic)))
            elif alternative == "greater":
                p = 1 - sc_stats.norm.cdf(test_statistic)
            elif alternative == "less":
                p = sc_stats.norm.cdf(test_statistic)
            else:
                return MathObject(error="alternative 无效。")
            dist_name = f"N(0,1)"
        elif dist_lower == "t":
            if alternative == "two-sided":
                p = 2 * (1 - sc_stats.t.cdf(abs(test_statistic), df))
            elif alternative == "greater":
                p = 1 - sc_stats.t.cdf(test_statistic, df)
            elif alternative == "less":
                p = sc_stats.t.cdf(test_statistic, df)
            else:
                return MathObject(error="alternative 无效。")
            dist_name = f"t({df})"
        elif dist_lower == "chi2":
            p = 1 - sc_stats.chi2.cdf(test_statistic, df)
            dist_name = f"χ²({df})"
        else:
            return MathObject(error="dist 必须为 'normal' / 't' / 'chi2'。")

        return MathObject(
            result=float(p),
            steps=[
                f"分布: {dist_name}",
                f"检验统计量: {test_statistic:.4f}",
                f"备择假设: {alternative}",
                f"p-value = {p:.6f}",
            ],
            meaning=f"在 {dist_name} 下，{test_statistic:.4f} 对应的 "
                    f"{'双侧' if alternative == 'two-sided' else '单侧'} p 值为 {p:.4f}。",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """模块自测。"""
    print("=== hypothesis_test 自测 ===")

    # Z 检验
    r1 = z_test(sample_mean=2.5, mu0=3, sigma=1.5, n=100, alpha=0.05)
    assert r1.ok, r1.error
    print(f"  z_test: Z={r1.result['Z']:.4f}, p={r1.result['p_value']:.4f}, "
          f"reject={r1.result['reject_H0']}  PASSED")

    # t 检验
    r2 = t_test([1, 2, 3, 4, 5], mu0=3, alpha=0.05)
    assert r2.ok, r2.error
    print(f"  t_test: t={r2.result['t']:.4f}, p={r2.result['p_value']:.4f}  PASSED")

    # 卡方检验
    r3 = chi_square_test(
        observed=[50, 30, 20],
        expected=[40, 40, 20],
    )
    assert r3.ok, r3.error
    print(f"  chi_square_test: χ²={r3.result['chi2']:.4f}, p={r3.result['p_value']:.4f}  PASSED")

    # p 值计算
    r4 = p_value(1.96, "normal", alternative="two-sided")
    assert r4.ok, r4.error
    assert abs(r4.result - 0.05) < 0.01, r4.result
    print(f"  p_value (Z=1.96): {r4.result:.4f}  PASSED")

    print("hypothesis_test 自测全部通过!\n")
    return True


if __name__ == "__main__":
    self_test()
