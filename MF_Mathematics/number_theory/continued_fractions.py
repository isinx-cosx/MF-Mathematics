"""continued_fractions.py — 连分数。

涵盖实数连分数展开、渐近分数序列、最佳有理逼近。
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import List, Tuple, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="number_theory", action="continued_fraction")
def continued_fraction(x: float, n_terms: int = 20) -> MathObject:
    """计算实数 x 的连分数展开，返回连分数系数列表 [a_0; a_1, a_2, ...]。

    Args:
        x: 实数（float 或整数）。
        n_terms: 最大项数，默认 20。

    Returns:
        MathObject: result 为连分数系数列表 [a0, a1, a2, ...]，
                    notation 字段含格式化表示 "[a0; a1, a2, ...]"。
    """
    try:
        x_val = float(x)
        max_terms = int(n_terms)

        steps: list[str] = []
        steps.append(f"连分数展开: x = {x_val}，最多 {max_terms} 项")

        if x_val == float('inf') or x_val == float('-inf') or math.isnan(x_val):
            raise ValueError(f"无法对 {x_val} 做连分数展开")

        # Check if x is a rational number (via Fraction)
        coeffs: list[int] = []
        remaining = x_val
        prev_remaining = None
        used_terms = 0

        for i in range(max_terms):
            if remaining < 0 and i > 0:
                # Adjust for negative remainder in non-first step
                a_i = int(math.floor(remaining))
            else:
                a_i = int(math.floor(remaining))

            coeffs.append(a_i)
            used_terms += 1

            frac_part = remaining - a_i
            if abs(frac_part) < 1e-15:
                break
            remaining = 1.0 / frac_part

            # Overflow / termination check
            if abs(remaining) > 1e15:
                break
            if prev_remaining is not None and abs(remaining - prev_remaining) < 1e-15:
                break
            prev_remaining = remaining

        # Format notation
        if len(coeffs) == 1:
            notation = f"[{coeffs[0]}]"
        else:
            notation = f"[{coeffs[0]}; {', '.join(str(c) for c in coeffs[1:])}]"

        steps.append(f"  展开: {notation}")
        if used_terms >= max_terms:
            steps.append(f"  达到最大项数 {max_terms}，展开可能被截断")

        return MathObject(
            result=coeffs,
            steps=steps,
            meaning=f"{x} 的连分数展开为 {notation}",
            data={"notation": notation, "terms": used_terms},
            module="number_theory",
            action="continued_fraction",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="continued_fraction")


@register(module="number_theory", action="convergents")
def convergents(frac: List[int]) -> MathObject:
    """从连分数系数列表计算渐近分数序列。

    递推公式:
        p_{-1}=1, p_0=a_0,  p_n = a_n * p_{n-1} + p_{n-2}
        q_{-1}=0, q_0=1,    q_n = a_n * q_{n-1} + q_{n-2}

    Args:
        frac: 连分数系数列表 [a0, a1, a2, ...]。

    Returns:
        MathObject: result 为渐近分数列表，每项为 (分子, 分母, 浮点近似值) 的三元组。
    """
    try:
        if not frac:
            raise ValueError("连分数系数列表不能为空")

        steps: list[str] = []
        steps.append(f"计算渐近分数，连分数: {frac}")

        conv_list: list[Tuple[int, int, float]] = []

        # Initial values
        p_minus_1, p_minus_2 = 1, frac[0]
        q_minus_1, q_minus_2 = 0, 1

        # First convergent
        first_p, first_q = frac[0], 1
        conv_list.append((first_p, first_q, first_p / first_q if first_q != 0 else float('inf')))
        steps.append(f"  C₀ = {first_p}/{first_q} ≈ {first_p / first_q:.10f}")

        for n in range(1, len(frac)):
            a_n = frac[n]
            if n == 1:
                p_n = a_n * p_minus_2 + p_minus_1
                q_n = a_n * q_minus_2 + q_minus_1
            else:
                p_n = a_n * conv_list[-1][0] + conv_list[-2][0]
                q_n = a_n * conv_list[-1][1] + conv_list[-2][1]

            approx = p_n / q_n if q_n != 0 else float('inf')
            conv_list.append((p_n, q_n, approx))
            steps.append(f"  C_{n} = {p_n}/{q_n} ≈ {approx:.10f}")

        return MathObject(
            result=conv_list,
            steps=steps,
            meaning=f"共 {len(conv_list)} 个渐近分数，逐步逼近原始值",
            module="number_theory",
            action="convergents",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="convergents")


@register(module="number_theory", action="best_rational_approximation")
def best_rational_approximation(x: float, max_denom: int = 1000000) -> MathObject:
    """最佳有理逼近：在分母不超过 max_denom 的条件下，找到最接近 x 的有理数。

    使用连分数展开 + 渐近分数法，高效找到最佳逼近。

    Args:
        x: 实数（float）。
        max_denom: 分母上限，默认 1000000。

    Returns:
        MathObject: result 为 (分子, 分母, 浮点近似值) 三元组。
    """
    try:
        x_val = float(x)
        max_d = int(max_denom)
        if max_d < 1:
            raise ValueError(f"分母上限必须 ≥1，得到 {max_d}")

        steps: list[str] = []
        steps.append(f"最佳有理逼近: x = {x_val}, 分母 ≤ {max_d}")

        if x_val == 0.0:
            return MathObject(
                result=(0, 1, 0.0),
                steps=steps + ["  x = 0 → 最佳逼近 = 0/1"],
                meaning="0 的最佳有理逼近为 0/1",
                module="number_theory",
                action="best_rational_approximation",
            )

        sign = 1 if x_val >= 0 else -1
        x_abs = abs(x_val)

        # Use continued fraction convergents
        p_minus_2, p_minus_1 = 0, 1
        q_minus_2, q_minus_1 = 1, 0

        remaining = x_abs
        best_p, best_q = 0, 1
        best_error = float('inf')

        for _ in range(100):  # safety limit
            a = int(math.floor(remaining))
            p = a * p_minus_1 + p_minus_2
            q = a * q_minus_1 + q_minus_2

            if q > max_d:
                # Use semiconvergents
                t = (max_d - q_minus_2) // q_minus_1
                if t > 0:
                    sp = t * p_minus_1 + p_minus_2
                    sq = t * q_minus_1 + q_minus_2
                    if sq <= max_d:
                        err = abs(x_abs - sp / sq)
                        if err < best_error:
                            best_p, best_q = sp, sq
                            best_error = err
                break

            err = abs(x_abs - p / q)
            if err < best_error:
                best_p, best_q = p, q
                best_error = err

            p_minus_2, p_minus_1 = p_minus_1, p
            q_minus_2, q_minus_1 = q_minus_1, q

            frac_part = remaining - a
            if abs(frac_part) < 1e-15:
                break
            remaining = 1.0 / frac_part

        best_p *= sign
        approx = best_p / best_q if best_q != 0 else float('inf')

        steps.append(f"  最佳逼近: {best_p}/{best_q} ≈ {approx}")
        steps.append(f"  误差: |x - p/q| = {best_error:.2e}")

        return MathObject(
            result=(best_p, best_q, approx),
            steps=steps,
            meaning=f"分母 ≤ {max_d} 时，{x} 的最佳有理逼近为 {best_p}/{best_q} ≈ {approx}",
            module="number_theory",
            action="best_rational_approximation",
        )
    except Exception as e:
        return MathObject(error=str(e), module="number_theory", action="best_rational_approximation")


def self_test() -> bool:
    """自检：验证连分数函数。"""
    all_pass = True

    # 测试 1: continued_fraction of pi
    import math as _math
    r1 = continued_fraction(_math.pi, 6)
    # pi ≈ [3; 7, 15, 1, 292, 1, ...]
    coeffs = r1.result
    assert coeffs[:5] == [3, 7, 15, 1, 292], f"期望 [3,7,15,1,292], 得到 {coeffs[:5]}"
    print(f"  [PASS] continued_fraction(π, 6) ≈ {r1.result[:6]}")

    # 测试 2: convergents
    r2 = convergents([3, 7, 15, 1])
    # Convergents: 3/1, 22/7, 333/106, 355/113
    conv = r2.result
    assert conv[0][0] == 3 and conv[0][1] == 1, f"C0 = 3/1"
    assert conv[1][0] == 22 and conv[1][1] == 7, f"C1 = 22/7"
    assert conv[3][0] == 355 and conv[3][1] == 113, f"C3 = 355/113"
    print(f"  [PASS] convergents([3,7,15,1]) = {[(p, q) for p, q, _ in conv]}")

    # 测试 3: best_rational_approximation
    r3 = best_rational_approximation(_math.pi, 1000)
    p3, q3, _ = r3.result
    assert p3 == 355 and q3 == 113, f"期望 355/113, 得到 {p3}/{q3}"
    print(f"  [PASS] best_rational_approximation(π, 1000) = {p3}/{q3}")

    # 测试 4: continued_fraction of sqrt(2)
    r4 = continued_fraction(_math.sqrt(2), 8)
    # sqrt(2) = [1; 2, 2, 2, ...] (periodic)
    assert r4.result[:4] == [1, 2, 2, 2], f"sqrt(2) 期望 [1,2,2,2,...], 得到 {r4.result[:4]}"
    print(f"  [PASS] continued_fraction(√2, 8) = {r4.result[:8]}")

    print(f"  continued_fractions 自测: {'ALL PASSED' if all_pass else 'FAILED'}")
    return all_pass


if __name__ == "__main__":
    self_test()
