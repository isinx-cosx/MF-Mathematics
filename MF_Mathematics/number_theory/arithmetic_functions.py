"""arithmetic_functions.py — 数论函数。

涵盖欧拉函数 φ(n)、除数函数 τ(n) 和 σ(n)、莫比乌斯函数 μ(n)、
莫比乌斯前缀和（Mertens 函数）。
"""

from __future__ import annotations

import math
from typing import Dict, List

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="number_theory", action="euler_phi")
def euler_phi(n: int) -> MathObject:
    """欧拉函数 φ(n)：计算不超过 n 且与 n 互素的正整数个数。

    使用公式 φ(n) = n * ∏_{p|n} (1 - 1/p)，其中 p 跑遍 n 的质因数。

    Args:
        n: 正整数。

    Returns:
        MathObject: result 为 φ(n) 的值。
    """
    try:
        n_int = int(n)
        if n_int <= 0:
            raise ValueError(f"n 必须为正整数，得到 {n_int}")

        steps: list[str] = []
        steps.append(f"计算 φ({n_int})")
        steps.append("公式: φ(n) = n × ∏_{p|n} (1 - 1/p)")

        result = n_int
        temp = n_int
        p = 2
        prime_factors: list[int] = []
        while p * p <= temp:
            if temp % p == 0:
                prime_factors.append(p)
                while temp % p == 0:
                    temp //= p
                result -= result // p
                steps.append(f"  质因数 p={p}: φ ← {result + result // p} × (1 - 1/{p}) = {result}")
            p += 1 if p == 2 else 2  # 2,3,5,7,...

        if temp > 1:
            prime_factors.append(temp)
            result -= result // temp
            steps.append(f"  剩余质因数 p={temp}: φ ← {result + result // temp} × (1 - 1/{temp}) = {result}")

        steps.append(f"结果: φ({n_int}) = {result}")
        meaning = f"不超过 {n} 且与 {n} 互素的正整数有 {result} 个"
        if n_int == 1:
            meaning += "（约定 φ(1)=1）"

        return MathObject(
            result=result,
            steps=steps,
            meaning=meaning,
            module="number_theory",
            action="euler_phi",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="euler_phi")


def _prime_factorization(n: int) -> Dict[int, int]:
    """内部辅助：质因数分解返回 {p: exp}。"""
    factors: dict[int, int] = {}
    temp = n
    d = 2
    while d * d <= temp:
        while temp % d == 0:
            factors[d] = factors.get(d, 0) + 1
            temp //= d
        d += 1 if d == 2 else 2
    if temp > 1:
        factors[temp] = factors.get(temp, 0) + 1
    return factors


@register(module="number_theory", action="divisor_count")
def divisor_count(n: int) -> MathObject:
    """除数函数 τ(n)：返回 n 的正约数个数。

    使用公式：若 n = ∏ p_i^{a_i}，则 τ(n) = ∏ (a_i + 1)。

    Args:
        n: 正整数。

    Returns:
        MathObject: result 为 τ(n) 的值。
    """
    try:
        n_int = int(n)
        if n_int <= 0:
            raise ValueError(f"n 必须为正整数，得到 {n_int}")

        steps: list[str] = []
        steps.append(f"计算 τ({n_int})（正约数个数）")

        if n_int == 1:
            steps.append("  τ(1) = 1")
            return MathObject(
                result=1,
                steps=steps,
                meaning="1 只有一个正约数（即其自身）",
                module="number_theory",
                action="divisor_count",
            )

        factors = _prime_factorization(n_int)
        steps.append(f"  质因数分解: {n_int} = " + " × ".join(
            f"{p}^{e}" if e > 1 else f"{p}" for p, e in sorted(factors.items())
        ))

        result = 1
        for p, e in sorted(factors.items()):
            result *= (e + 1)
            steps.append(f"  因子 {p}^{e} → (e+1) = {e + 1}，累积 τ = {result}")

        steps.append(f"结果: τ({n_int}) = {result}")
        # List divisors for small n
        if n_int <= 10000:
            divisors = sorted(_get_divisors_from_factors(factors))
            if len(divisors) <= 100:
                steps.append(f"  正约数: {divisors}")

        return MathObject(
            result=result,
            steps=steps,
            meaning=f"{n} 的正约数共有 {result} 个",
            module="number_theory",
            action="divisor_count",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="divisor_count")


def _get_divisors_from_factors(factors: Dict[int, int]) -> List[int]:
    """从质因数分解生成所有正约数。"""
    divisors = [1]
    for p, e in factors.items():
        new_divisors = []
        power = 1
        for _ in range(e + 1):
            for d in divisors:
                new_divisors.append(d * power)
            power *= p
        divisors = new_divisors
    return divisors


@register(module="number_theory", action="divisor_sum")
def divisor_sum(n: int) -> MathObject:
    """除数和函数 σ(n)：返回 n 的所有正约数之和。

    使用公式：若 n = ∏ p_i^{a_i}，则 σ(n) = ∏ (p_i^{a_i+1} - 1) / (p_i - 1)。

    Args:
        n: 正整数。

    Returns:
        MathObject: result 为 σ(n) 的值。
    """
    try:
        n_int = int(n)
        if n_int <= 0:
            raise ValueError(f"n 必须为正整数，得到 {n_int}")

        steps: list[str] = []
        steps.append(f"计算 σ({n_int})（正约数之和）")

        if n_int == 1:
            steps.append("  σ(1) = 1")
            return MathObject(
                result=1,
                steps=steps,
                meaning="1 的唯一正约数之和为 1",
                module="number_theory",
                action="divisor_sum",
            )

        factors = _prime_factorization(n_int)
        factor_str = " × ".join(f"{p}^{e}" if e > 1 else f"{p}" for p, e in sorted(factors.items()))
        steps.append(f"  质因数分解: {n_int} = {factor_str}")

        result = 1
        for p, e in sorted(factors.items()):
            term = (p ** (e + 1) - 1) // (p - 1)
            result *= term
            steps.append(f"  因子 {p}^{e}: (p^{e+1}-1)/(p-1) = {term}，累积 σ = {result}")

        steps.append(f"结果: σ({n_int}) = {result}")

        return MathObject(
            result=result,
            steps=steps,
            meaning=f"{n} 的所有正约数之和为 {result}",
            module="number_theory",
            action="divisor_sum",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="divisor_sum")


@register(module="number_theory", action="mobius")
def mobius(n: int) -> MathObject:
    """莫比乌斯函数 μ(n)。

    定义:
    - μ(1) = 1
    - μ(n) = (-1)^k，若 n 是 k 个互异质因数之积（无平方因子）
    - μ(n) = 0，若 n 含有平方因子

    Args:
        n: 正整数。

    Returns:
        MathObject: result 为 μ(n) ∈ {-1, 0, 1}。
    """
    try:
        n_int = int(n)
        if n_int <= 0:
            raise ValueError(f"n 必须为正整数，得到 {n_int}")

        steps: list[str] = []
        steps.append(f"计算 μ({n_int})")

        if n_int == 1:
            steps.append("  μ(1) = 1（约定）")
            return MathObject(
                result=1,
                steps=steps,
                meaning="μ(1) = 1 为约定",
                module="number_theory",
                action="mobius",
            )

        temp = n_int
        prime_count = 0
        d = 2

        while d * d <= temp:
            if temp % d == 0:
                temp //= d
                if temp % d == 0:
                    steps.append(f"  发现平方因子 d={d} → μ({n_int}) = 0")
                    return MathObject(
                        result=0,
                        steps=steps,
                        meaning=f"{n} 含有平方因子 {d}²，μ(n) = 0",
                        module="number_theory",
                        action="mobius",
                    )
                prime_count += 1
                steps.append(f"  互异质因数 d={d}，计数 {prime_count}")
            d += 1 if d == 2 else 2

        if temp > 1:
            prime_count += 1
            steps.append(f"  剩余质因数 {temp}，计数 {prime_count}")

        result = (-1) ** prime_count
        steps.append(f"  共 {prime_count} 个互异质因数 → μ({n_int}) = (-1)^{prime_count} = {result}")
        return MathObject(
            result=result,
            steps=steps,
            meaning=f"μ({n}) = {result}" + ("（无平方因子）" if result != 0 else "（含平方因子）"),
            module="number_theory",
            action="mobius",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="mobius")


@register(module="number_theory", action="mobius_prefix")
def mobius_prefix(n: int) -> MathObject:
    """莫比乌斯前缀和（Mertens 函数）M(n) = Σ_{k=1}^{n} μ(k)。

    使用公式逐项累加计算。

    Args:
        n: 正整数。

    Returns:
        MathObject: result 为 M(n) 的值。
    """
    try:
        n_int = int(n)
        if n_int <= 0:
            raise ValueError(f"n 必须为正整数，得到 {n_int}")

        if n_int > 10_000_000:
            return MathObject(
                result=None,
                error=f"n={n_int} 过大，Mertens 函数仅支持 n ≤ 10,000,000",
                module="number_theory",
                action="mobius_prefix",
            )

        steps: list[str] = []
        steps.append(f"计算 Mertens 函数 M({n_int}) = Σ μ(k)")

        # Use sieve-like approach to compute μ for all k ≤ n
        mu = [1] * (n_int + 1)
        mu[0] = 0

        # Mark squareful
        is_squarefree = [True] * (n_int + 1)
        for i in range(2, int(math.isqrt(n_int)) + 1):
            sq = i * i
            for j in range(sq, n_int + 1, sq):
                is_squarefree[j] = False

        # Sieve prime counts
        for i in range(2, n_int + 1):
            if is_squarefree[i]:
                # Count distinct prime factors
                cnt = 0
                temp = i
                d = 2
                while d * d <= temp:
                    if temp % d == 0:
                        cnt += 1
                        while temp % d == 0:
                            temp //= d
                    d += 1 if d == 2 else 2
                if temp > 1:
                    cnt += 1
                mu[i] = (-1) ** cnt
            else:
                mu[i] = 0

        mertens = sum(mu)
        steps.append(f"结果: M({n_int}) = {mertens}")

        return MathObject(
            result=mertens,
            steps=steps,
            meaning=f"Mertens 函数 M({n}) = {mertens}。素数定理等价于 M(n)=o(n)。",
            module="number_theory",
            action="mobius_prefix",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="mobius_prefix")


def self_test() -> bool:
    """自检：验证数论函数。"""
    all_pass = True

    # 测试 1: euler_phi
    r1 = euler_phi(10)
    assert r1.result == 4, f"期望 4, 得到 {r1.result}"
    print(f"  [PASS] euler_phi(10) = {r1.result}")
    r1b = euler_phi(1)
    assert r1b.result == 1, f"期望 1, 得到 {r1b.result}"
    print(f"  [PASS] euler_phi(1) = {r1b.result}")

    # 测试 2: divisor_count
    r2 = divisor_count(12)
    assert r2.result == 6, f"期望 6, 得到 {r2.result}"
    print(f"  [PASS] divisor_count(12) = {r2.result}")

    # 测试 3: divisor_sum
    r3 = divisor_sum(12)
    assert r3.result == 28, f"期望 28, 得到 {r3.result}"
    print(f"  [PASS] divisor_sum(12) = {r3.result}")

    # 测试 4: mobius
    r4 = mobius(6)
    assert r4.result == 1, f"μ(6) 期望 1, 得到 {r4.result}"
    print(f"  [PASS] mobius(6) = {r4.result}")
    r4b = mobius(12)
    assert r4b.result == 0, f"μ(12) 期望 0, 得到 {r4b.result}"
    print(f"  [PASS] mobius(12) = {r4b.result}")
    r4c = mobius(30)
    assert r4c.result == -1, f"μ(30) 期望 -1, 得到 {r4c.result}"
    print(f"  [PASS] mobius(30) = {r4c.result}")

    # 测试 5: mobius_prefix
    r5 = mobius_prefix(10)
    # M(10) = μ(1)+...+μ(10) = 1 + (-1) + (-1) + 0 + (-1) + 1 + (-1) + 0 + 0 + 1 = -1
    assert r5.result == -1, f"期望 -1, 得到 {r5.result}"
    print(f"  [PASS] mobius_prefix(10) = {r5.result}")

    print(f"  arithmetic_functions 自测: {'ALL PASSED' if all_pass else 'FAILED'}")
    return all_pass


if __name__ == "__main__":
    self_test()
