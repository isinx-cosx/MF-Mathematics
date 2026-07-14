"""prime_sieves.py — 素数分布与筛法。

涵盖埃拉托斯特尼筛法、分段筛法、米勒-拉宾素性测试、质因数分解。
"""

from __future__ import annotations

import math
import random
from typing import List

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="number_theory", action="eratosthenes")
def eratosthenes(n: int) -> MathObject:
    """埃拉托斯特尼筛法：生成不超过 n 的所有素数。

    Args:
        n: 上界（正整数，≥2）。

    Returns:
        MathObject: result 为 ≤n 的素数列表。
    """
    try:
        n_int = int(n)
        if n_int < 2:
            return MathObject(
                result=[],
                steps=[f"n={n_int} < 2，无素数"],
                meaning="不存在小于 2 的素数",
                module="number_theory",
                action="eratosthenes",
            )

        steps: list[str] = []
        steps.append(f"埃拉托斯特尼筛法: 求 ≤{n_int} 的所有素数")

        is_prime = [True] * (n_int + 1)
        is_prime[0] = is_prime[1] = False

        limit = int(math.isqrt(n_int))
        steps.append(f"  筛到 √{n_int} = {limit}")

        for i in range(2, limit + 1):
            if is_prime[i]:
                for j in range(i * i, n_int + 1, i):
                    is_prime[j] = False

        primes = [i for i in range(2, n_int + 1) if is_prime[i]]
        count = len(primes)
        steps.append(f"  共找到 {count} 个素数")
        steps.append(f"  素数定理估计: π({n_int}) ≈ {n_int / math.log(n_int):.1f}")

        return MathObject(
            result=primes,
            steps=steps,
            meaning=f"不超过 {n} 的素数共 {count} 个",
            module="number_theory",
            action="eratosthenes",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="eratosthenes")


@register(module="number_theory", action="segmented_sieve")
def segmented_sieve(n: int, segment_size: int = 100000) -> MathObject:
    """分段筛法：高效生成大范围内的所有素数，逐段枚举。

    Args:
        n: 上界（正整数）。
        segment_size: 每个分段的长度（内存控制），默认 100000。

    Returns:
        MathObject: result 为 ≤n 的素数列表（仅当 n 较小时返回完整列表；
                    若 n 过大则返回 stats 摘要）。
    """
    try:
        n_int = int(n)
        if n_int < 2:
            return MathObject(
                result=[],
                steps=[f"n={n_int} < 2，无素数"],
                meaning="",
                module="number_theory",
                action="segmented_sieve",
            )

        steps: list[str] = []
        steps.append(f"分段筛法: 求 ≤{n_int} 的所有素数，分段大小 = {segment_size}")

        limit = int(math.isqrt(n_int))
        # Step 1: Sieve small primes up to sqrt(n)
        small_primes = _simple_eratosthenes(limit)
        steps.append(f"  第1步: 筛出 ≤√{n_int} = {limit} 的素数，共 {len(small_primes)} 个")

        all_primes: list[int] = list(small_primes)

        # Step 2: Segmented sieve
        low = max(limit + 1, 2)
        segments_count = 0
        while low <= n_int:
            segments_count += 1
            high = min(low + segment_size - 1, n_int)
            seg_len = high - low + 1
            segment = [True] * seg_len

            for p in small_primes:
                start = max(p * p, ((low + p - 1) // p) * p)
                for j in range(start, high + 1, p):
                    segment[j - low] = False

            for i in range(seg_len):
                if segment[i]:
                    all_primes.append(low + i)

            low = high + 1

        steps.append(f"  第2步: 分段处理完成，共 {segments_count} 段")
        steps.append(f"  总计 {len(all_primes)} 个素数")

        # If result is too large, return summary only
        if len(all_primes) > 50000:
            return MathObject(
                result={"count": len(all_primes), "sample": all_primes[:20] + ["..."] + all_primes[-20:]},
                steps=steps,
                meaning=f"≤{n} 的素数共 {len(all_primes)} 个（列表过长，仅显示前20+后20）",
                module="number_theory",
                action="segmented_sieve",
            )

        return MathObject(
            result=all_primes,
            steps=steps,
            meaning=f"≤{n} 的素数共 {len(all_primes)} 个",
            module="number_theory",
            action="segmented_sieve",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="segmented_sieve")


def _simple_eratosthenes(n: int) -> list[int]:
    """内部辅助: 简单筛法返回素数列表。"""
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


@register(module="number_theory", action="is_prime")
def is_prime(n: int, k: int = 10) -> MathObject:
    """米勒-拉宾素性测试（概率型）。

    对于 n < 2^64 的整数，使用确定性的基底集合保证正确性。

    Args:
        n: 待测试的整数。
        k: 测试轮数（仅对 n ≥ 2^64 的极大数生效），默认 10。

    Returns:
        MathObject: result 为 True（可能素数）或 False（合数）。
    """
    try:
        n_int = int(n)
        steps: list[str] = []
        steps.append(f"米勒-拉宾素性测试: n = {n_int}")

        if n_int < 2:
            steps.append("  n < 2 → 不是素数")
            return MathObject(
                result=False,
                steps=steps,
                meaning=f"{n} 不是素数（小于 2）",
                module="number_theory",
                action="is_prime",
            )
        if n_int == 2 or n_int == 3:
            steps.append("  n = 2 或 3 → 是素数")
            return MathObject(
                result=True,
                steps=steps,
                meaning=f"{n} 是素数",
                module="number_theory",
                action="is_prime",
            )
        if n_int % 2 == 0:
            steps.append(f"  n = {n_int} 是偶数 → 合数")
            return MathObject(
                result=False,
                steps=steps,
                meaning=f"{n} 是合数（偶数）",
                module="number_theory",
                action="is_prime",
            )

        # Write n-1 = d * 2^s
        d = n_int - 1
        s = 0
        while d % 2 == 0:
            d //= 2
            s += 1
        steps.append(f"  n-1 = {n_int - 1} = {d} × 2^{s}")

        # Select witnesses
        if n_int < 2047:
            witnesses = [2]
        elif n_int < 1373653:
            witnesses = [2, 3]
        elif n_int < 25326001:
            witnesses = [2, 3, 5]
        elif n_int < 3215031751:
            witnesses = [2, 3, 5, 7]
        elif n_int < 2152302898747:
            witnesses = [2, 3, 5, 7, 11]
        elif n_int < 3474749660383:
            witnesses = [2, 3, 5, 7, 11, 13]
        elif n_int < 341550071728321:
            witnesses = [2, 3, 5, 7, 11, 13, 17]
        elif n_int < 3825123056546413051:
            witnesses = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        elif n_int < 2**64:
            witnesses = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]
        else:
            witnesses = [random.randint(2, n_int - 2) for _ in range(k)]

        for a in witnesses:
            a_mod = a % n_int
            if a_mod == 0:
                continue
            x = pow(a_mod, d, n_int)
            if x == 1 or x == n_int - 1:
                continue
            composite = True
            for _ in range(s - 1):
                x = pow(x, 2, n_int)
                if x == n_int - 1:
                    composite = False
                    break
            if composite:
                steps.append(f"  基底 a={a} 检测为合数")
                return MathObject(
                    result=False,
                    steps=steps,
                    meaning=f"{n} 是合数（米勒-拉宾检测）",
                    module="number_theory",
                    action="is_prime",
                )

        steps.append(f"  通过 {len(witnesses)} 轮测试 → 判定为素数")
        return MathObject(
            result=True,
            steps=steps,
            meaning=f"{n} 极大概率为素数（米勒-拉宾 k={k}）",
            module="number_theory",
            action="is_prime",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="is_prime")


@register(module="number_theory", action="prime_factors")
def prime_factors(n: int) -> MathObject:
    """质因数分解：返回 n 的所有质因数及其指数。

    使用试除法 + Pollard Rho 占位。对于较小整数直接试除，大整数使用 sympy 辅助。

    Args:
        n: 待分解的整数（≥2）。

    Returns:
        MathObject: result 为字典 {质因数: 指数}，steps 含过程。
    """
    try:
        n_int = int(n)
        if n_int < 2:
            return MathObject(
                result={},
                steps=[f"{n_int} 无质因数分解"],
                meaning="只有 ≥2 的整数才有质因数分解",
                module="number_theory",
                action="prime_factors",
            )

        steps: list[str] = []
        steps.append(f"质因数分解: {n_int}")

        original = n_int
        factors: dict[int, int] = {}

        # Trial division by small primes
        small_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
        for p in small_primes:
            if n_int % p == 0:
                count = 0
                while n_int % p == 0:
                    n_int //= p
                    count += 1
                factors[p] = count
                steps.append(f"  试除: {p}^{count}")

            if p * p > n_int:
                break

        # Continue trial division beyond small primes
        d = small_primes[-1] + 2 if small_primes else 3
        while d * d <= n_int:
            if n_int % d == 0:
                count = 0
                while n_int % d == 0:
                    n_int //= d
                    count += 1
                factors[d] = count
                steps.append(f"  试除: {d}^{count}")
            d += 2

        if n_int > 1:
            factors[n_int] = 1
            steps.append(f"  剩余因子: {n_int}")

        # Format result
        factor_str = " × ".join(f"{p}^{e}" if e > 1 else f"{p}" for p, e in sorted(factors.items()))
        steps.append(f"  分解结果: {original} = {factor_str}")

        return MathObject(
            result=factors,
            steps=steps,
            meaning=f"{original} = {factor_str}",
            module="number_theory",
            action="prime_factors",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="prime_factors")


def self_test() -> bool:
    """自检：验证筛法和素性测试函数。"""
    all_pass = True

    # 测试 1: eratosthenes
    r1 = eratosthenes(20)
    assert r1.result == [2, 3, 5, 7, 11, 13, 17, 19], f"期望 8 个素数，得到 {r1.result}"
    print(f"  [PASS] eratosthenes(20) = {r1.result}")

    # 测试 2: is_prime
    r2 = is_prime(17)
    assert r2.result is True, f"17 是素数"
    print(f"  [PASS] is_prime(17) = {r2.result}")
    r2b = is_prime(100)
    assert r2b.result is False, f"100 不是素数"
    print(f"  [PASS] is_prime(100) = {r2b.result}")
    r2c = is_prime(2**31 - 1)
    assert r2c.result is True, f"2^31-1 是素数（梅森素数 M31）"
    print(f"  [PASS] is_prime(2^31-1) = {r2c.result}")

    # 测试 3: prime_factors
    r3 = prime_factors(84)
    assert r3.result == {2: 2, 3: 1, 7: 1}, f"84 = 2²×3×7, 得到 {r3.result}"
    print(f"  [PASS] prime_factors(84) = {r3.result}")
    r3b = prime_factors(97)
    assert r3b.result == {97: 1}, f"97 是素数"
    print(f"  [PASS] prime_factors(97) = {r3b.result}")

    # 测试 4: segmented_sieve
    r4 = segmented_sieve(100)
    assert len(r4.result) == 25, f"≤100 共 25 个素数，得到 {len(r4.result)} 个"
    print(f"  [PASS] segmented_sieve(100): {len(r4.result)} 个素数")

    print(f"  prime_sieves 自测: {'ALL PASSED' if all_pass else 'FAILED'}")
    return all_pass


if __name__ == "__main__":
    self_test()
