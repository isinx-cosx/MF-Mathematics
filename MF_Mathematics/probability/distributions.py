"""经典分布族 — 离散型（伯努利、二项、泊松）和连续型（均匀、指数、正态）。

依赖: numpy, sympy
"""

from __future__ import annotations

from typing import Any, Dict, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="probability", action="bernoulli")
def bernoulli(p: float) -> MathObject:
    """两点分布（伯努利分布）B(1, p)。

    X ~ Bernoulli(p): P(X=1)=p, P(X=0)=1-p。

    Args:
        p: 成功概率，0 ≤ p ≤ 1。

    Returns:
        MathObject:
            - result: 分布参数字典 {"pmf": {0: 1-p, 1: p}, "mean": p, "variance": p(1-p)}。
    """
    try:
        if not 0 <= p <= 1:
            return MathObject(error="概率 p 必须在 [0, 1] 之间。")

        q = 1 - p
        return MathObject(
            result={
                "name": f"Bernoulli({p})",
                "pmf": {0: q, 1: p},
                "mean": p,
                "variance": p * q,
            },
            steps=[
                f"成功概率 p = {p}",
                f"P(X=1) = {p},  P(X=0) = {q}",
                f"E[X] = p = {p}",
                f"Var(X) = p(1-p) = {p * q}",
            ],
            meaning="两点分布描述单次伯努利试验的结果（成功/失败）。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="binomial")
def binomial(n: int, p: float) -> MathObject:
    """二项分布 B(n, p)。

    X ~ Binomial(n, p): P(X=k) = C(n,k)·p^k·(1-p)^{n-k}。

    Args:
        n: 试验次数，正整数。
        p: 单次成功概率。

    Returns:
        MathObject:
            - result: 分布参数字典。
    """
    try:
        if n <= 0 or not isinstance(n, int):
            return MathObject(error="n 必须为正整数。")
        if not 0 <= p <= 1:
            return MathObject(error="概率 p 必须在 [0, 1] 之间。")

        from math import comb

        q = 1 - p
        mean = n * p
        variance = n * p * q

        # 计算 PMF 前几项
        pmf_sample: Dict[int, float] = {}
        for k in range(min(n + 1, 8)):
            prob = comb(n, k) * (p**k) * (q ** (n - k))
            pmf_sample[k] = round(prob, 6)

        return MathObject(
            result={
                "name": f"Binomial({n}, {p})",
                "pmf_sample": pmf_sample,
                "mean": mean,
                "variance": variance,
                "params": {"n": n, "p": p},
            },
            steps=[
                f"试验次数 n = {n}, 成功概率 p = {p}",
                f"E[X] = np = {mean}",
                f"Var(X) = np(1-p) = {variance}",
            ],
            meaning=f"n={n} 次独立重复伯努利试验中成功次数的分布。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="poisson")
def poisson(lam: float) -> MathObject:
    """泊松分布 Poisson(λ)。

    X ~ Poisson(λ): P(X=k) = λ^k·e^{-λ} / k!。

    Args:
        lam: 速率参数 λ > 0。

    Returns:
        MathObject:
            - result: 分布参数字典。
    """
    try:
        if lam <= 0:
            return MathObject(error="λ 必须 > 0。")

        from math import exp, factorial

        mean = lam
        variance = lam

        # 计算 PMF 前几项
        pmf_sample: Dict[int, float] = {}
        for k in range(8):
            prob = (lam**k) * exp(-lam) / factorial(k)
            pmf_sample[k] = round(prob, 6)

        return MathObject(
            result={
                "name": f"Poisson({lam})",
                "pmf_sample": pmf_sample,
                "mean": mean,
                "variance": variance,
                "params": {"lambda": lam},
            },
            steps=[
                f"速率 λ = {lam}",
                f"E[X] = λ = {mean}",
                f"Var(X) = λ = {variance}",
            ],
            meaning=f"泊松分布描述单位时间内随机事件发生次数的分布。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="uniform")
def uniform(a: float, b: float) -> MathObject:
    """连续型均匀分布 U(a, b)。

    f(x) = 1/(b-a),  a ≤ x ≤ b。

    Args:
        a: 下界。
        b: 上界（b > a）。

    Returns:
        MathObject:
            - result: 分布参数字典。
    """
    try:
        if b <= a:
            return MathObject(error="必须 b > a。")

        pdf_expr = f"1/({b} - {a})"
        mean = (a + b) / 2
        var_val = (b - a) ** 2 / 12

        return MathObject(
            result={
                "name": f"Uniform({a}, {b})",
                "pdf": pdf_expr,
                "mean": mean,
                "variance": var_val,
                "params": {"a": a, "b": b},
            },
            steps=[
                f"下界 a = {a}, 上界 b = {b}",
                f"密度: f(x) = 1/({b-a})  on [{a}, {b}]",
                f"E[X] = (a+b)/2 = {mean}",
                f"Var(X) = (b-a)²/12 = {var_val}",
            ],
            meaning=f"在 [{a}, {b}] 上每一点等可能的连续均匀分布。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="exponential")
def exponential(lam: float) -> MathObject:
    """指数分布 Exp(λ)。

    f(x) = λ·e^{-λx},  x ≥ 0。

    Args:
        lam: 速率参数 λ > 0。

    Returns:
        MathObject:
            - result: 分布参数字典。
    """
    try:
        if lam <= 0:
            return MathObject(error="λ 必须 > 0。")

        mean = 1 / lam
        var_val = 1 / (lam**2)

        return MathObject(
            result={
                "name": f"Exponential({lam})",
                "pdf": f"{lam} * exp(-{lam} * x)",
                "mean": mean,
                "variance": var_val,
                "params": {"lambda": lam},
            },
            steps=[
                f"速率 λ = {lam}",
                f"密度: f(x) = {lam}·e^(-{lam}x),  x ≥ 0",
                f"E[X] = 1/λ = {mean}",
                f"Var(X) = 1/λ² = {var_val}",
            ],
            meaning="指数分布常用于描述等待时间、寿命等。无记忆性。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="normal")
def normal(mu: float, sigma: float) -> MathObject:
    """正态分布 N(μ, σ²)。

    f(x) = (1/√(2πσ²))·exp(-(x-μ)²/(2σ²))。

    Args:
        mu: 均值 μ。
        sigma: 标准差 σ > 0。

    Returns:
        MathObject:
            - result: 分布参数字典。
    """
    try:
        if sigma <= 0:
            return MathObject(error="σ 必须 > 0。")

        import math

        pdf_str = f"(1/(√(2π)·{sigma}))·exp(-(x-{mu})²/(2·{sigma}²))"
        variance = sigma**2

        return MathObject(
            result={
                "name": f"Normal({mu}, {sigma}²)",
                "pdf": pdf_str,
                "mean": mu,
                "variance": variance,
                "std": sigma,
                "params": {"mu": mu, "sigma": sigma},
            },
            steps=[
                f"均值 μ = {mu}, 标准差 σ = {sigma}",
                f"密度: f(x) = (1/√(2πσ²))·exp(-(x-μ)²/(2σ²))",
                f"E[X] = μ = {mu}",
                f"Var(X) = σ² = {variance}",
            ],
            meaning=f"正态分布（高斯分布），68-95-99.7 规则："
                    f"[μ±σ]={mu-sigma:.1f}~{mu+sigma:.1f} (68%)。",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """模块自测。"""
    print("=== distributions 自测 ===")

    # Bernoulli
    r1 = bernoulli(0.3)
    assert r1.ok, r1.error
    assert abs(r1.result["mean"] - 0.3) < 0.01
    print(f"  bernoulli: {r1.result['name']}  PASSED")

    # Binomial
    r2 = binomial(10, 0.5)
    assert r2.ok, r2.error
    assert abs(r2.result["mean"] - 5.0) < 0.01, r2.result
    print(f"  binomial: {r2.result['name']}, E={r2.result['mean']}  PASSED")

    # Poisson
    r3 = poisson(3.0)
    assert r3.ok, r3.error
    assert abs(r3.result["mean"] - 3.0) < 0.01
    print(f"  poisson: {r3.result['name']}  PASSED")

    # Uniform
    r4 = uniform(0, 10)
    assert r4.ok, r4.error
    assert abs(r4.result["mean"] - 5.0) < 0.01
    print(f"  uniform: {r4.result['name']}  PASSED")

    # Exponential
    r5 = exponential(2.0)
    assert r5.ok, r5.error
    assert abs(r5.result["mean"] - 0.5) < 0.01
    print(f"  exponential: {r5.result['name']}  PASSED")

    # Normal
    r6 = normal(0, 1)
    assert r6.ok, r6.error
    assert r6.result["mean"] == 0.0
    assert r6.result["variance"] == 1.0
    print(f"  normal: {r6.result['name']}  PASSED")

    print("distributions 自测全部通过!\n")
    return True


if __name__ == "__main__":
    self_test()
