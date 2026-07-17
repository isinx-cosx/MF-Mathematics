"""core_algorithms.py — 数论核心算法。

涵盖欧几里得算法、扩展欧几里得、模逆元、快速幂取模等基础算法。
"""

from __future__ import annotations

from typing import Tuple

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="number_theory", action="gcd")
def gcd(a: int, b: int) -> MathObject:
    """欧几里得算法求最大公约数。

    Args:
        a: 第一个整数。
        b: 第二个整数。

    Returns:
        MathObject: result 为 a 和 b 的最大公约数（非负整数）。
    """
    try:
        a_int, b_int = int(a), int(b)
        steps: list[str] = []
        x, y = abs(a_int), abs(b_int)
        if y > x:
            x, y = y, x
        steps.append(f"计算 gcd({a_int}, {b_int})")
        while y != 0:
            steps.append(f"  {x} ÷ {y} = {x // y} 余 {x % y}")
            x, y = y, x % y
        steps.append(f"结果: {x}")
        return MathObject(
            result=x,
            steps=steps,
            meaning=f"{a} 和 {b} 的最大公约数（Greatest Common Divisor）",
            module="number_theory",
            action="gcd",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="gcd")


@register(module="number_theory", action="extended_gcd")
def extended_gcd(a: int, b: int) -> MathObject:
    """扩展欧几里得算法，返回 (gcd, x, y) 使得 ax + by = gcd(a, b)。

    Args:
        a: 第一个整数。
        b: 第二个整数。

    Returns:
        MathObject: result 为三元组 (gcd, x, y)，满足 a*x + b*y = gcd(a,b)。
    """
    try:
        a_int, b_int = int(a), int(b)
        steps: list[str] = []
        steps.append(f"扩展欧几里得: 求 a={a_int}, b={b_int} 的贝祖系数")

        old_r, r = a_int, b_int
        old_s, s = 1, 0
        old_t, t = 0, 1

        while r != 0:
            q = old_r // r
            old_r, r = r, old_r - q * r
            old_s, s = s, old_s - q * s
            old_t, t = t, old_t - q * t

        g = old_r
        sx, ty = old_s, old_t

        if g < 0:
            g, sx, ty = -g, -sx, -ty

        steps.append(f"  gcd = {g}, x = {sx}, y = {ty}")
        steps.append(f"  验证: {a_int}*({sx}) + {b_int}*({ty}) = {a_int * sx + b_int * ty} = {g}")
        return MathObject(
            result=(g, sx, ty),
            steps=steps,
            meaning=f"贝祖等式: {a}·{sx} + {b}·{ty} = {g}",
            module="number_theory",
            action="extended_gcd",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="extended_gcd")


@register(module="number_theory", action="mod_inverse")
def mod_inverse(a: int, m: int) -> MathObject:
    """计算 a 模 m 的乘法逆元，要求 gcd(a, m) = 1。

    Args:
        a: 需要求逆元的整数。
        m: 模数（正整数）。

    Returns:
        MathObject: result 为满足 a*x ≡ 1 (mod m) 的整数 x（在 [0, m-1] 范围内）。
    """
    try:
        a_int, m_int = int(a), int(m)
        if m_int <= 0:
            raise ValueError(f"模数 m 必须为正整数，得到 {m_int}")
        steps: list[str] = []
        steps.append(f"计算 {a_int} 在模 {m_int} 下的逆元")

        g, x, y = _extended_gcd_raw(a_int, m_int)
        if g != 1:
            raise ValueError(f"gcd({a_int}, {m_int}) = {g} ≠ 1，逆元不存在（需互素）")

        inv = x % m_int
        steps.append(f"  gcd({a_int}, {m_int}) = 1, 存在唯一逆元")
        steps.append(f"  扩展欧几里得: {a_int}*({x}) + {m_int}*({y}) = 1")
        steps.append(f"  逆元: {x} mod {m_int} = {inv}")
        steps.append(f"  验证: {a_int} * {inv} = {a_int * inv} ≡ {a_int * inv % m_int} (mod {m_int})")
        return MathObject(
            result=inv,
            steps=steps,
            meaning=f"{a} 在模 {m} 下的乘法逆元，满足 {a}·{inv} ≡ 1 (mod {m})",
            module="number_theory",
            action="mod_inverse",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="mod_inverse")


def _extended_gcd_raw(a: int, b: int) -> Tuple[int, int, int]:
    """内部辅助: 扩展欧几里得，返回原始 (gcd, x, y)。"""
    old_r, r = a, b
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r != 0:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    if old_r < 0:
        return -old_r, -old_s, -old_t
    return old_r, old_s, old_t


@register(module="number_theory", action="mod_pow")
def mod_pow(base: int, exp: int, mod: int) -> MathObject:
    """快速幂取模：计算 base^exp mod mod，使用二进制指数分解。

    Args:
        base: 底数。
        exp: 指数（非负整数）。
        mod: 模数（正整数）。

    Returns:
        MathObject: result 为 base^exp mod mod。
    """
    try:
        b = int(base)
        e = int(exp)
        m = int(mod)
        if m <= 0:
            raise ValueError(f"模数 mod 必须为正整数，得到 {m}")
        if e < 0:
            raise ValueError(f"指数 exp 必须为非负整数，得到 {e}")

        steps: list[str] = []
        steps.append(f"计算 {b}^{e} mod {m}")
        steps.append(f"使用二进制快速幂（平方-乘算法）")

        result = 1
        b_mod = b % m
        exp_bin = bin(e)[2:]
        steps.append(f"  指数二进制: {e} = {exp_bin}₂")

        bit_position = 0
        while e > 0:
            if e & 1:
                result = (result * b_mod) % m
                steps.append(f"  位 {bit_position}=1: result = (result * {b_mod}) mod {m} = {result}")
            e >>= 1
            b_mod = (b_mod * b_mod) % m
            bit_position += 1

        steps.append(f"结果: {b}^{exp} mod {m} = {result}")
        return MathObject(
            result=result,
            steps=steps,
            meaning=f"{base}^{exp} ≡ {result} (mod {mod})",
            module="number_theory",
            action="mod_pow",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="mod_pow")


def self_test() -> tuple[int, int, int]:
    """自检：验证核心算法函数。返回 (passed, failed, errors)。"""
    passed, failed, errors = 0, 0, 0
    tests = [
        ("gcd(48, 18)", lambda: gcd(48, 18).result, 6),
        ("extended_gcd(48, 18)", lambda: extended_gcd(48, 18).result, None),
        ("mod_inverse(3, 7)", lambda: mod_inverse(3, 7).result, 5),
        ("mod_pow(2, 10, 1000)", lambda: mod_pow(2, 10, 1000).result, 24),
        ("gcd(0, 7)", lambda: gcd(0, 7).result, 7),
    ]
    for name, fn, expected in tests:
        try:
            result = fn()
            if name == "extended_gcd(48, 18)":
                g, x, y = result
                assert g == 6 and x == -1 and y == 3, f"期望 (6,-1,3) 得 {result}"
            else:
                assert result == expected, f"期望 {expected} 得 {result}"
            passed += 1
            print(f"  [PASS] {name} = {result}")
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:
            errors += 1
            print(f"  [ERROR] {name}: {e}")
    print(f"  core_algorithms 自测: {passed} pass, {failed} fail, {errors} error")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
