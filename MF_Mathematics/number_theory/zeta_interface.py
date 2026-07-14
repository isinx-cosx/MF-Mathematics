"""zeta_interface.py — 复分析与 ζ 函数接口。

涵盖欧拉乘积公式、Dirichlet 级数部分和、Dirichlet L 函数、
伯努利数、ζ 负整数值（ζ(-n) = -B_{n+1}/(n+1)）。
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Callable, List, Optional, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="number_theory", action="euler_product")
def euler_product(s: float, prime_limit: int = 100) -> MathObject:
    """欧拉乘积公式部分逼近：∏_{p ≤ P} (1 - p^{-s})^{-1} → ζ(s)（当 Re(s) > 1）。

    Args:
        s: 复变量的实部（float，>1 时严格收敛）。
        prime_limit: 使用的最大素数上限。

    Returns:
        MathObject: result 为欧拉乘积的逼近值。
    """
    try:
        s_val = float(s)
        p_lim = int(prime_limit)

        if p_lim < 2:
            raise ValueError(f"素数上限必须 ≥2，得到 {p_lim}")

        steps: list[str] = []
        steps.append(f"欧拉乘积: ∏_{{p≤{p_lim}}} (1 - p^{{-{s_val}}})⁻¹")

        # Generate primes up to prime_limit
        primes = _simple_sieve(p_lim)
        if not primes:
            return MathObject(
                result=1.0,
                steps=steps + [f"  无素数 ≤ {p_lim}，返回 1"],
                meaning="空乘积为 1",
                module="number_theory",
                action="euler_product",
            )

        product = 1.0
        for p in primes:
            factor = 1.0 / (1.0 - p ** (-s_val))
            product *= factor

        steps.append(f"  使用素数: {primes[:min(10, len(primes))]}{'...' if len(primes) > 10 else ''}，共 {len(primes)} 个")
        steps.append(f"  欧拉乘积 ≈ {product:.10f}")

        # Known values for comparison
        comparison = ""
        if abs(s_val - 2.0) < 1e-3:
            exact = math.pi ** 2 / 6.0
            comparison = f"（ζ(2) = π²/6 = {exact:.10f}）"
            steps.append(f"  ζ(2) 精确值 = π²/6 = {exact:.10f}")
            steps.append(f"  误差: {abs(product - exact):.2e}")
        elif abs(s_val - 4.0) < 1e-3:
            exact = math.pi ** 4 / 90.0
            comparison = f"（ζ(4) = π⁴/90 = {exact:.10f}）"
            steps.append(f"  ζ(4) 精确值 = π⁴/90 = {exact:.10f}")
            steps.append(f"  误差: {abs(product - exact):.2e}")

        return MathObject(
            result=product,
            steps=steps,
            meaning=f"欧拉乘积（≤{p_lim} 素数）逼近 ζ({s}) {comparison}",
            module="number_theory",
            action="euler_product",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="euler_product")


def _simple_sieve(n: int) -> list[int]:
    """筛出 ≤ n 的所有素数。"""
    if n < 2:
        return []
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    limit = int(math.isqrt(n))
    for i in range(2, limit + 1):
        if is_prime[i]:
            for j in range(i * i, n + 1, i):
                is_prime[j] = False
    return [i for i in range(2, n + 1) if is_prime[i]]


@register(module="number_theory", action="zeta_dirichlet_series")
def zeta_dirichlet_series(s: float, n_terms: int = 10000) -> MathObject:
    """ζ(s) 的 Dirichlet 级数部分和：Σ_{n=1}^{N} n^{-s}。

    Args:
        s: 复变量的实部（float，>1 时绝对收敛）。
        n_terms: 求和项数。

    Returns:
        MathObject: result 为部分和逼近值。
    """
    try:
        s_val = float(s)
        N = int(n_terms)
        if N < 1:
            raise ValueError(f"项数必须 ≥1，得到 {N}")

        steps: list[str] = []
        steps.append(f"Dirichlet 级数: Σ_{{n=1}}^{{{N}}} n^{{-{s_val}}}")

        if N > 100000:
            # Use numpy for large N
            arr = np.arange(1, N + 1, dtype=np.float64)
            partial_sum = float(np.sum(arr ** (-s_val)))
        else:
            partial_sum = sum(n ** (-s_val) for n in range(1, N + 1))

        steps.append(f"  ζ({s_val}) ≈ {partial_sum:.10f} (N={N})")

        # Known comparisons
        if abs(s_val - 2.0) < 1e-3:
            exact = math.pi ** 2 / 6.0
            steps.append(f"  精确值 ζ(2) = π²/6 = {exact:.10f}")
            steps.append(f"  误差: {abs(partial_sum - exact):.2e}")
        elif abs(s_val - 1.0) < 1e-3:
            euler_mascheroni = 0.5772156649015329
            harmonic = partial_sum  # When s=1, it's harmonic sum
            steps.append(f"  调和级数 H_{N} = {harmonic:.6f}")
            steps.append(f"  H_{N} - ln({N}) ≈ {harmonic - math.log(N):.6f} ≈ γ = {euler_mascheroni}")

        return MathObject(
            result=partial_sum,
            steps=steps,
            meaning=f"ζ({s}) 的 Dirichlet 级数部分和（N={n_terms}）",
            module="number_theory",
            action="zeta_dirichlet_series",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="zeta_dirichlet_series")


@register(module="number_theory", action="dirichlet_l_function")
def dirichlet_l_function(
    s: float,
    chi: Optional[List[int]] = None,
    n_terms: int = 1000,
    conductor: int = 4,
) -> MathObject:
    """Dirichlet L 函数 L(s, χ) 的部分和：Σ_{n=1}^{N} χ(n) n^{-s}。

    默认使用模 4 的非平凡 Dirichlet 特征：
        χ(n) = 0 (n 偶)，χ(n) = 1 (n≡1 mod 4)，χ(n) = -1 (n≡3 mod 4)。

    Args:
        s: 复变量的实部。
        chi: 自定义 Dirichlet 特征列表 chi[0..conductor-1]，或 None 使用默认。
        n_terms: 求和项数。
        conductor: Dirichlet 特征的模数（导子），默认 4。

    Returns:
        MathObject: result 为 L(s, χ) 的部分和。
    """
    try:
        s_val = float(s)
        N = int(n_terms)
        cond = int(conductor)

        steps: list[str] = []
        steps.append(f"Dirichlet L 函数: L({s_val}, χ) 模 {cond}，N={N}")

        if chi is None:
            # Default: nontrivial mod 4
            def chi_default(n: int) -> int:
                if n % 2 == 0:
                    return 0
                return 1 if n % 4 == 1 else -1

            chi_func = chi_default
            steps.append("  特征: χ(n)=0(偶), 1(n≡1 mod4), -1(n≡3 mod4)")
        elif len(chi) == cond:
            chi_vals = chi[:]

            def chi_func(n: int) -> int:
                return chi_vals[n % cond]

            steps.append(f"  自定义特征: {chi_vals}")
        else:
            raise ValueError(f"chi 长度 ({len(chi) if chi else 0}) 与 conductor ({cond}) 不匹配")

        partial_sum = 0.0
        for n in range(1, N + 1):
            cn = chi_func(n)
            if cn != 0:
                partial_sum += cn * (n ** (-s_val))

        steps.append(f"  L({s_val}, χ) ≈ {partial_sum:.10f} (N={N})")

        # Known: L(1, χ₋₄) = π/4
        if abs(s_val - 1.0) < 1e-3 and chi is None and cond == 4:
            exact = math.pi / 4.0
            steps.append(f"  L(1, χ₋₄) 精确值 = π/4 = {exact:.10f}")
            steps.append(f"  误差: {abs(partial_sum - exact):.2e}")

        return MathObject(
            result=partial_sum,
            steps=steps,
            meaning=f"L({s}, χ) 的 Dirichlet 级数部分和（模 {cond}，N={n_terms}）",
            module="number_theory",
            action="dirichlet_l_function",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="dirichlet_l_function")


def _bernoulli_recursive(n: int) -> Fraction:
    """递归计算伯努利数 B_n（分数形式）。"""
    # B_0 = 1, B_1 = -1/2
    # For n ≥ 2: sum_{k=0}^{n} C(n+1, k) B_k = 0 (when n is even, B_n computed)
    # Odd B_n = 0 for n ≥ 3
    if n == 0:
        return Fraction(1, 1)
    if n == 1:
        return Fraction(-1, 2)
    if n % 2 == 1 and n >= 3:
        return Fraction(0, 1)

    # Compute using recurrence
    B = [Fraction(0, 1)] * (n + 1)
    B[0] = Fraction(1, 1)

    for m in range(1, n + 1):
        if m == 1:
            B[1] = Fraction(-1, 2)
            continue
        if m % 2 == 1:
            B[m] = Fraction(0, 1)
            continue

        s = Fraction(0, 1)
        for k in range(m):
            s += _binom(m + 1, k) * B[k]
        B[m] = -s / (m + 1)

    return B[n]


def _binom(n: int, k: int) -> Fraction:
    """二项式系数 C(n, k) 分数形式。"""
    if k < 0 or k > n:
        return Fraction(0, 1)
    if k == 0 or k == n:
        return Fraction(1, 1)
    num = 1
    den = 1
    for i in range(1, k + 1):
        num *= (n - i + 1)
        den *= i
    return Fraction(num, den)


@register(module="number_theory", action="bernoulli_number")
def bernoulli_number(n: int) -> MathObject:
    """计算第 n 个伯努利数 B_n。

    伯努利数定义：
        x/(eˣ - 1) = Σ_{n=0}^{∞} B_n xⁿ/n!
        B_0 = 1, B_1 = -1/2, B_2 = 1/6, B_4 = -1/30, B_6 = 1/42, ...
        对奇数 n ≥ 3, B_n = 0。

    Args:
        n: 伯努利数索引（非负整数）。

    Returns:
        MathObject: result 为 B_n 的值（Fraction 或 float）。
    """
    try:
        n_int = int(n)
        if n_int < 0:
            raise ValueError(f"n 必须为非负整数，得到 {n_int}")

        steps: list[str] = []
        steps.append(f"计算伯努利数 B_{{{n_int}}}")

        if n_int < 20:
            bn = _bernoulli_recursive(n_int)
            steps.append(f"  递归计算: B_{{{n_int}}} = {bn}")
            steps.append(f"  数值: {float(bn):.10f}")
            result = bn
        else:
            # Use known formula for large n (not fully accurate but gives magnitude)
            bn_float = _bernoulli_approx(n_int)
            steps.append(f"  大 n 近似: B_{{{n_int}}} ≈ {bn_float:.6e}")
            result = bn_float

        return MathObject(
            result=result,
            steps=steps,
            meaning=f"B_{{{n}}} = {result}" + ("（精确分数）" if isinstance(result, Fraction) else "（近似值）"),
            module="number_theory",
            action="bernoulli_number",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="bernoulli_number")


def _bernoulli_approx(n: int) -> float:
    """伯努利数的大 n 渐近公式（仅偶数 n）。"""
    if n % 2 == 1 and n >= 3:
        return 0.0
    if n == 0:
        return 1.0
    if n == 1:
        return -0.5
    # |B_{2n}| ~ 4 √(π n) (n / (π e))^{2n}
    m = n // 2
    approx = 4.0 * math.sqrt(math.pi * m) * (m / (math.pi * math.e)) ** (2 * m)
    sign = -1 if m % 2 == 1 else 1
    return sign * approx


@register(module="number_theory", action="zeta_negative")
def zeta_negative(n: int) -> MathObject:
    """ζ 函数在负整数点的值：ζ(-n) = -B_{n+1} / (n+1)。

    对于正整数 n，ζ(-n) 由伯努利数给出。

    Args:
        n: 正整数。

    Returns:
        MathObject: result 为 ζ(-n) 的值。
    """
    try:
        n_int = int(n)
        if n_int < 0:
            raise ValueError(f"n 必须为非负整数，得到 {n_int}")

        steps: list[str] = []
        steps.append(f"计算 ζ(-{n_int})")
        steps.append(f"公式: ζ(-n) = -B_{{n+1}} / (n+1)")

        if n_int == 0:
            result = Fraction(-1, 2)
            steps.append("  ζ(0) = -1/2")
        else:
            bn1 = _bernoulli_recursive(n_int + 1)
            result = Fraction(-1, 1) * bn1 / (n_int + 1)
            steps.append(f"  B_{{{n_int + 1}}} = {bn1}")
            steps.append(f"  ζ(-{n_int}) = -B_{{{n_int + 1}}} / {n_int + 1} = {result}")

        steps.append(f"  数值: {float(result):.10f}")

        # Known values
        known_values = {
            1: "ζ(-1) = -1/12",
            2: "ζ(-2) = 0",
            3: "ζ(-3) = 1/120",
            4: "ζ(-4) = 0",
            5: "ζ(-5) = -1/252",
            7: "ζ(-7) = 1/240",
        }
        if n_int in known_values:
            steps.append(f"  已知: {known_values[n_int]}")

        return MathObject(
            result=result,
            steps=steps,
            meaning=f"ζ(-{n}) = {result} = {float(result):.10f}",
            module="number_theory",
            action="zeta_negative",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="zeta_negative")


def self_test() -> bool:
    """自检：验证 ζ 函数接口函数。"""
    all_pass = True

    # 测试 1: euler_product
    r1 = euler_product(2, 100)
    expected = math.pi ** 2 / 6.0
    assert abs(r1.result - expected) < 0.05, f"期望 ≈{expected}, 得到 {r1.result}"
    print(f"  [PASS] euler_product(2, 100) = {r1.result:.6f} (期望 π²/6 = {expected:.6f})")

    # 测试 2: zeta_dirichlet_series
    r2 = zeta_dirichlet_series(2, 10000)
    assert abs(r2.result - expected) < 0.01, f"期望 ≈{expected}, 得到 {r2.result}"
    print(f"  [PASS] zeta_dirichlet_series(2, 10000) = {r2.result:.6f}")

    # 测试 3: dirichlet_l_function
    r3 = dirichlet_l_function(1, n_terms=10000)
    expected_l = math.pi / 4.0
    assert abs(r3.result - expected_l) < 0.01, f"期望 ≈{expected_l}, 得到 {r3.result}"
    print(f"  [PASS] dirichlet_l_function(1, 10000) = {r3.result:.6f} (期望 π/4 = {expected_l:.6f})")

    # 测试 4: bernoulli_number
    r4 = bernoulli_number(2)
    assert abs(float(r4.result) - 1.0 / 6.0) < 1e-10, f"B₂ 期望 1/6, 得到 {float(r4.result)}"
    print(f"  [PASS] bernoulli_number(2) = {r4.result}")
    r4b = bernoulli_number(4)
    assert abs(float(r4b.result) - (-1.0 / 30.0)) < 1e-10, f"B₄ 期望 -1/30, 得到 {float(r4b.result)}"
    print(f"  [PASS] bernoulli_number(4) = {r4b.result}")

    # 测试 5: zeta_negative
    r5 = zeta_negative(1)
    assert abs(float(r5.result) - (-1.0 / 12.0)) < 1e-10, f"ζ(-1) 期望 -1/12, 得到 {float(r5.result)}"
    print(f"  [PASS] zeta_negative(1) = {r5.result}")
    r5b = zeta_negative(3)
    assert abs(float(r5b.result) - 1.0 / 120.0) < 1e-10, f"ζ(-3) 期望 1/120, 得到 {float(r5b.result)}"
    print(f"  [PASS] zeta_negative(3) = {r5b.result}")

    print(f"  zeta_interface 自测: {'ALL PASSED' if all_pass else 'FAILED'}")
    return all_pass


if __name__ == "__main__":
    self_test()
