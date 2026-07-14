"""极限定理 — 大数定律与中心极限定理。

依赖: numpy, scipy
"""

from __future__ import annotations

from typing import Any, List, Tuple, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="probability", action="law_of_large_numbers")
def law_of_large_numbers(
    sample_mean: float,
    true_mean: float,
    n: int,
) -> MathObject:
    """大数定律演示：样本均值随 n 增大收敛到总体均值。

    验证 |X̄_n - μ| 随 n 增大而趋于 0（依概率收敛）。

    Args:
        sample_mean: 样本均值 X̄_n。
        true_mean: 总体均值 μ。
        n: 样本量。

    Returns:
        MathObject:
            - result: {"deviation": |X̄ - μ|, "converged": bool}。
    """
    try:
        deviation = abs(sample_mean - true_mean)
        # 经验阈值：偏差小于 3σ/√n 量级认为收敛
        threshold = 3.0 / np.sqrt(n)
        converged = deviation < threshold if n > 0 else False

        return MathObject(
            result={
                "sample_mean": sample_mean,
                "true_mean": true_mean,
                "deviation": deviation,
                "n": n,
                "threshold": threshold,
                "converged": converged,
            },
            steps=[
                f"样本容量 n = {n}",
                f"样本均值 X̄_n = {sample_mean:.6f}",
                f"总体均值 μ = {true_mean}",
                f"偏差 |X̄_n - μ| = {deviation:.6f}",
                f"阈值 (3/√n) = {threshold:.6f}",
                (
                    f"偏差 < 阈值，大数定律收敛趋势验证。"
                    if converged
                    else f"样本量可能不足，建议增大 n。"
                ),
            ],
            meaning=f"大数定律：当 n → ∞ 时，X̄_n → μ。当前偏差={deviation:.6f}。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="central_limit_theorem")
def central_limit_theorem(
    sample: List[float],
    mu: float,
    sigma: float,
    n: int,
) -> MathObject:
    """中心极限定理：标准化样本均值近似 N(0,1)。

    Z = (X̄ - μ) / (σ/√n) → N(0, 1)，n 充分大。

    Args:
        sample: 原始样本列表。
        mu: 总体均值。
        sigma: 总体标准差。
        n: 样本量。

    Returns:
        MathObject:
            - result: 含 Z 值、p 值、是否近似正态等信息。
    """
    try:
        import math

        sample_arr = np.asarray(sample, dtype=float)
        sample_mean_val = float(np.mean(sample_arr))

        if abs(sigma) < 1e-15:
            return MathObject(error="σ 不能为 0。")

        se = sigma / math.sqrt(n)
        z_val = (sample_mean_val - mu) / se

        # 近似 p 值（双侧）
        from math import erf

        p_val = 2 * (1 - 0.5 * (1 + erf(abs(z_val) / math.sqrt(2))))

        return MathObject(
            result={
                "sample_mean": sample_mean_val,
                "Z": z_val,
                "p_value": p_val,
                "n": n,
                "standard_error": se,
                "approx_normal": n >= 30,
            },
            steps=[
                f"样本量 n = {n}",
                f"总体均值 μ = {mu}, 总体标准差 σ = {sigma}",
                f"标准误 SE = σ/√n = {se:.6f}",
                f"样本均值 X̄ = {sample_mean_val:.6f}",
                f"Z = (X̄ - μ) / SE = {z_val:.4f}",
                f"双侧 p-value ≈ {p_val:.6f}",
                (
                    f"n ≥ 30，中心极限定理适用。"
                    if n >= 30
                    else f"n < 30，中心极限定理近似可能不精确。"
                ),
            ],
            meaning=(
                f"中心极限定理：当 n ≥ 30 时，X̄ 近似服从 N(μ, σ²/n)。"
                f"Z = {z_val:.4f}, p = {p_val:.4f}。"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """模块自测。"""
    print("=== limit_theorems 自测 ===")

    # 大数定律
    r1 = law_of_large_numbers(sample_mean=50.2, true_mean=50.0, n=100)
    assert r1.ok, r1.error
    print(f"  LLN: deviation={r1.result['deviation']:.4f}  PASSED")

    r2 = law_of_large_numbers(sample_mean=49.98, true_mean=50.0, n=1000)
    assert r2.ok, r2.error
    print(f"  LLN (large n): deviation={r2.result['deviation']:.4f}  PASSED")

    # 中心极限定理
    rng = np.random.default_rng(42)
    sample = rng.normal(50, 10, 100).tolist()
    r3 = central_limit_theorem(sample, mu=50, sigma=10, n=100)
    assert r3.ok, r3.error
    print(f"  CLT: Z={r3.result['Z']:.4f}, p={r3.result['p_value']:.4f}  PASSED")

    print("limit_theorems 自测全部通过!\n")
    return True


if __name__ == "__main__":
    self_test()
