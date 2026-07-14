"""modular_arithmetic.py — 模算术与同余。

涵盖中国剩余定理（CRT）、原根、离散对数（大步小步法）。
"""

from __future__ import annotations

import math
from typing import List

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="number_theory", action="crt")
def crt(residues: List[int], moduli: List[int]) -> MathObject:
    """中国剩余定理（CRT）：解同余方程组 x ≡ r_i (mod m_i)，其中模数两两互素。

    Args:
        residues: 余数列表 [r_1, r_2, ..., r_k]。
        moduli: 模数列表 [m_1, m_2, ..., m_k]，需两两互素。

    Returns:
        MathObject: result 为满足方程组的最小非负解 x。
    """
    try:
        r_list = [int(r) for r in residues]
        m_list = [int(m) for m in moduli]

        if len(r_list) != len(m_list):
            raise ValueError(f"余数个数 ({len(r_list)}) 与模数个数 ({len(m_list)}) 不一致")
        if len(r_list) == 0:
            raise ValueError("至少需要一个同余方程")

        steps: list[str] = []
        steps.append("中国剩余定理 (CRT) 求解")

        for i, (r, m) in enumerate(zip(r_list, m_list)):
            steps.append(f"  方程 {i+1}: x ≡ {r} (mod {m})")

        # Verify pairwise coprime
        for i in range(len(m_list)):
            for j in range(i + 1, len(m_list)):
                g = math.gcd(m_list[i], m_list[j])
                if g != 1:
                    raise ValueError(f"模数 m_{i+1}={m_list[i]} 和 m_{j+1}={m_list[j]} 不互素 (gcd={g})")

        M = 1
        for m in m_list:
            M *= m
        steps.append(f"  M = ∏ m_i = {M}")

        x = 0
        for i in range(len(r_list)):
            Mi = M // m_list[i]
            # Find inverse of Mi modulo m_i
            inv = pow(Mi, -1, m_list[i]) if hasattr(pow(Mi, -1, m_list[i]), '__int__') else _mod_inv(Mi, m_list[i])
            term = r_list[i] * Mi * inv
            x += term
            steps.append(f"  M_{i+1} = {Mi}, inv(M_{i+1} mod {m_list[i]}) = {inv}")
            steps.append(f"    项 {i+1}: {r_list[i]} × {Mi} × {inv} = {term}")

        x %= M
        steps.append(f"  解: x = Σ(...) mod {M} = {x}")

        # Verification
        verify_lines = []
        for i, (r, m) in enumerate(zip(r_list, m_list)):
            verify_lines.append(f"  x mod {m} = {x % m} ≡ {r} (mod {m})")
        steps.extend(verify_lines)

        return MathObject(
            result=x,
            steps=steps,
            meaning=f"满足所有同余方程的最小非负解 x = {x}，周期为 {M}",
            module="number_theory",
            action="crt",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="crt")


def _mod_inv(a: int, m: int) -> int:
    """内部辅助：模逆元（使用 pow 的内置算法或扩展欧几里得）。"""
    # Python 3.8+ pow supports modular inverse
    try:
        return pow(a, -1, m)
    except (ValueError, TypeError):
        # Fallback: extended gcd
        old_r, r = a, m
        old_s, s = 1, 0
        while r != 0:
            q = old_r // r
            old_r, r = r, old_r - q * r
            old_s, s = s, old_s - q * s
        return old_s % m


@register(module="number_theory", action="primitive_root")
def primitive_root(p: int) -> MathObject:
    """求模 p 的一个原根（当 p 为奇素数或 p=2,4,p^k,2p^k 时存在原根）。

    Args:
        p: 正整数模数。

    Returns:
        MathObject: result 为最小原根 g，或 None（若不存在原根）。
    """
    try:
        p_int = int(p)
        if p_int < 2:
            raise ValueError(f"模数必须 ≥2，得到 {p_int}")

        steps: list[str] = []
        steps.append(f"求模 {p_int} 的原根")

        # Check if primitive root exists
        # Primitive roots exist for: 1, 2, 4, p^k, 2p^k (p odd prime)
        if p_int == 2:
            steps.append("  模 2 的原根为 1")
            return MathObject(
                result=1,
                steps=steps,
                meaning="模 2 的原根为 1（1¹ ≡ 1 mod 2）",
                module="number_theory",
                action="primitive_root",
            )
        if p_int == 4:
            steps.append("  模 4 的原根为 3")
            return MathObject(
                result=3,
                steps=steps,
                meaning="模 4 的原根为 3",
                module="number_theory",
                action="primitive_root",
            )

        # Check existence
        temp = p_int
        odd_prime = None
        if temp % 2 == 0:
            temp //= 2
            if temp % 2 == 0:
                raise ValueError(f"模 {p_int} 不存在原根（含因子 2²，不是 2,4,p^k,2p^k）")

        phi = p_int
        # Factor phi
        temp_phi = phi
        phi_factors: list[int] = []
        temp = temp_phi
        d = 2
        while d * d <= temp:
            if temp % d == 0:
                while temp % d == 0:
                    temp //= d
                phi_factors.append(d)
            d += 1 if d == 2 else 2
        if temp > 1:
            phi_factors.append(temp)

        # Actually need φ(p_int)
        phi_val = _euler_phi_val(p_int)
        # Get prime factors of phi
        phi_prime_factors = _get_prime_factors_list(phi_val)

        steps.append(f"  φ({p_int}) = {phi_val}")
        steps.append(f"  φ({p_int}) 的质因数: {phi_prime_factors}")

        # Search for primitive root
        for g in range(2, p_int):
            if math.gcd(g, p_int) != 1:
                continue
            is_primitive = True
            for q in phi_prime_factors:
                if pow(g, phi_val // q, p_int) == 1:
                    is_primitive = False
                    break
            if is_primitive:
                steps.append(f"  原根: g = {g}")
                steps.append(f"  验证: g 的阶为 φ({p_int}) = {phi_val}")
                return MathObject(
                    result=g,
                    steps=steps,
                    meaning=f"模 {p} 的最小原根为 {g}，生成乘法群 (Z/{p}Z)×",
                    module="number_theory",
                    action="primitive_root",
                )

        raise ValueError(f"模 {p_int} 不存在原根或搜索失败")
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="primitive_root")


def _euler_phi_val(n: int) -> int:
    """计算 φ(n) 的值。"""
    result = n
    temp = n
    p = 2
    while p * p <= temp:
        if temp % p == 0:
            while temp % p == 0:
                temp //= p
            result -= result // p
        p += 1 if p == 2 else 2
    if temp > 1:
        result -= result // temp
    return result


def _get_prime_factors_list(n: int) -> list[int]:
    """获取 n 的所有质因数（去重）列表。"""
    factors: list[int] = []
    d = 2
    temp = n
    while d * d <= temp:
        if temp % d == 0:
            factors.append(d)
            while temp % d == 0:
                temp //= d
        d += 1 if d == 2 else 2
    if temp > 1:
        factors.append(temp)
    return factors


@register(module="number_theory", action="discrete_log")
def discrete_log(g: int, h: int, p: int) -> MathObject:
    """离散对数：求解满足 g^x ≡ h (mod p) 的 x（大步小步法 / Baby-step Giant-step）。

    要求 p 为素数，g 为模 p 的原根或生成元。

    Args:
        g: 底数（生成元）。
        h: 目标值。
        p: 素数模数。

    Returns:
        MathObject: result 为最小非负解 x，或 None（无解）。
    """
    try:
        g_int = int(g)
        h_int = int(h)
        p_int = int(p)

        steps: list[str] = []
        steps.append(f"离散对数: 求 x 使得 {g_int}^x ≡ {h_int} (mod {p_int})")
        steps.append("使用大步小步法 (Baby-step Giant-step)")

        g_mod = g_int % p_int
        h_mod = h_int % p_int

        if h_mod == 1:
            steps.append("  h ≡ 1 → x = 0")
            return MathObject(
                result=0,
                steps=steps,
                meaning=f"{g}^0 ≡ 1 (mod {p})",
                module="number_theory",
                action="discrete_log",
            )

        # m = ceil(sqrt(p))
        m = int(math.isqrt(p_int)) + 1
        steps.append(f"  m = ⌈√{p_int}⌉ = {m}")

        # Baby steps: compute g^j mod p for j = 0..m-1
        baby_steps: dict[int, int] = {}
        current = 1
        for j in range(m):
            if current not in baby_steps:
                baby_steps[current] = j
            current = (current * g_mod) % p_int

        # Compute g^{-m} mod p
        g_inv_m = pow(pow(g_mod, -1, p_int), m, p_int) if hasattr(pow(g_mod, -1, p_int),
                                                                   '__int__') else pow(g_mod, p_int - 2, p_int)
        inv_m = pow(g_mod, -1, p_int)
        g_inv_m = pow(inv_m, m, p_int)

        steps.append(f"  g⁻¹ mod {p_int} = {pow(g_mod, -1, p_int)}")
        steps.append(f"  g⁻ᵐ mod {p_int} = {g_inv_m}")

        # Giant steps
        gamma = h_mod
        for i in range(m):
            if gamma in baby_steps:
                x = i * m + baby_steps[gamma]
                steps.append(f"  碰撞: i={i}, j={baby_steps[gamma]} → x = {i}×{m} + {baby_steps[gamma]} = {x}")
                # Verify
                verify = pow(g_mod, x, p_int)
                steps.append(f"  验证: {g_int}^{x} mod {p_int} = {verify} ≡ {h_int} (mod {p_int})")
                return MathObject(
                    result=x,
                    steps=steps,
                    meaning=f"log_{{{g}}}({h}) ≡ {x} (mod {p-1})，即 {g}^{x} ≡ {h} (mod {p})",
                    module="number_theory",
                    action="discrete_log",
                )
            gamma = (gamma * g_inv_m) % p_int

        return MathObject(
            result=None,
            steps=steps,
            error=f"在模 {p_int} 下未找到 x 使 {g_int}^x ≡ {h_int} (mod {p_int})",
            module="number_theory",
            action="discrete_log",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="discrete_log")


def self_test() -> bool:
    """自检：验证模算术函数。"""
    all_pass = True

    # 测试 1: CRT
    r1 = crt([2, 3, 2], [3, 5, 7])
    assert r1.result == 23, f"期望 23, 得到 {r1.result}"
    print(f"  [PASS] crt([2,3,2], [3,5,7]) = {r1.result}")

    # 测试 2: primitive_root
    r2 = primitive_root(7)
    assert r2.result == 3, f"模 7 原根期望 3, 得到 {r2.result}"
    print(f"  [PASS] primitive_root(7) = {r2.result}")

    # 测试 3: discrete_log
    r3 = discrete_log(3, 2, 7)
    assert r3.result is not None and pow(3, r3.result, 7) == 2, f"3^x≡2 mod 7，得到 x={r3.result}"
    print(f"  [PASS] discrete_log(3, 2, 7) = {r3.result} (验证: 3^{r3.result} mod 7 = 2)")

    # 测试 4: CRT 另一用例
    r4 = crt([0, 0, 0], [2, 3, 5])
    assert r4.result == 0, f"期望 0, 得到 {r4.result}"
    print(f"  [PASS] crt([0,0,0], [2,3,5]) = {r4.result}")

    print(f"  modular_arithmetic 自测: {'ALL PASSED' if all_pass else 'FAILED'}")
    return all_pass


if __name__ == "__main__":
    self_test()
