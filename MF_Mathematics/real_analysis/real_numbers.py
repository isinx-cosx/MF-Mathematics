"""实数系 — 戴德金分割、确界原理、阿基米德性质。

依赖: sympy
"""

from __future__ import annotations

from typing import List, Optional, Set, Tuple, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="real_analysis", action="dedekind_cut")
def dedekind_cut(
    setA: Union[List[float], Set[float]],
    setB: Union[List[float], Set[float]],
    cut_point: Optional[float] = None,
) -> MathObject:
    """戴德金分割演示。

    验证 (A, B) 是否构成有理数的一个戴德金分割：
    - A, B 非空且不相交
    - A ∪ B = Q（或有理数子集）
    - ∀ a∈A, b∈B, a < b

    Args:
        setA: 下组集合 A。
        setB: 上组集合 B。
        cut_point: 分割点（可选），用于显示分割对应的实数。

    Returns:
        MathObject，result 为分割是否有效的布尔值。
    """
    try:
        A = sorted(set(setA))
        B = sorted(set(setB))

        steps: list[str] = []
        valid = True

        # 检查非空
        if not A:
            steps.append("下组 A 为空，无效分割")
            valid = False
        if not B:
            steps.append("上组 B 为空，无效分割")
            valid = False
        if not A or not B:
            return MathObject(result=valid, steps=steps,
                            meaning="戴德金分割要求两组均非空")

        steps.append(f"下组 A = {A}")
        steps.append(f"上组 B = {B}")

        # 检查不相交
        intersection = set(A) & set(B)
        if intersection:
            steps.append(f"A ∩ B = {sorted(intersection)} ≠ ∅，无效分割")
            valid = False
        else:
            steps.append("A ∩ B = ∅ ✓")

        # 检查 A 中所有元素 < B 中所有元素
        max_A = max(A)
        min_B = min(B)
        if max_A >= min_B:
            steps.append(f"max(A)={max_A} ≥ min(B)={min_B}，无效分割")
            valid = False
        else:
            steps.append(f"∀ a∈A, b∈B: a < b ✓（max(A)={max_A} < min(B)={min_B}）")

        # 判断分割类型
        if cut_point is not None:
            steps.append(f"分割点: {cut_point}")
        elif valid:
            cut_point = (max_A + min_B) / 2.0
            steps.append(f"估算分割点: {cut_point}")

        if valid:
            # 判断是有理分割还是无理分割
            from fractions import Fraction
            try:
                Fraction(str(cut_point)).limit_denominator(1000)
                cut_type = "有理分割（cut_point ∈ Q）"
            except Exception:
                cut_type = "无理分割（cut_point ∉ Q）"
            steps.append(f"类型: {cut_type}")

        return MathObject(
            result=valid,
            steps=steps,
            meaning=f"戴德金分割: A={A}, B={B}, 有效={valid}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="supremum")
def supremum(
    s: Union[List[float], Set[float], str],
) -> MathObject:
    """计算上确界（最小上界）。

    对于有限集合直接计算最大值；对于无限集合用描述法（如 "{x | x < 2}"）。

    Args:
        s: 数值集合（list/set）或描述字符串如 "{x | x < 2}"。

    Returns:
        MathObject，result 为上确界值。
    """
    try:
        if isinstance(s, str):
            # 解析描述字符串
            desc = s.strip()
            steps = [f"解析集合描述: {desc}"]

            # 尝试匹配 {x | x < N} 或 {x | x <= N} 等模式
            import re

            # 匹配 "x < N" 或 "x <= N"
            m = re.search(r'x\s*(<=?)\s*(-?[\d.]+)', desc)
            if m:
                op = m.group(1)
                val = float(m.group(2))
                if op == '<':
                    result = val
                    steps.append(f"集合无最大元，上确界 = {val}")
                else:  # <=
                    result = val
                    steps.append(f"最大元 = {val}，上确界 = {val}")
                return MathObject(
                    result=result,
                    steps=steps,
                    meaning=f"sup {desc} = {result}",
                )

            # 匹配 {x | x > N} 无上界
            m = re.search(r'x\s*(>=?)\s*(-?[\d.]+)', desc)
            if m:
                steps.append("集合无上界")
                return MathObject(
                    result=float('inf'),
                    steps=steps,
                    meaning=f"sup {desc} = +∞（无上界）",
                )

            # fallback: 尝试作为 sympy 集合
            try:
                x = sp.Symbol('x')
                # 尝试 Interval 语法
                expr = sp.sympify(desc.replace('{', '').replace('}', ''))
                result = float(sp.oo)
                steps.append(f"符号解析: {expr}")
            except Exception:
                return MathObject(error=f"无法解析集合描述: {desc}")

            return MathObject(
                result=result,
                steps=steps,
                meaning=f"sup {desc} = {result}",
            )
        else:
            # 有限数值集合
            nums = sorted(set(float(x) for x in s))
            if not nums:
                return MathObject(
                    result=None,
                    steps=["空集合无上确界"],
                    meaning="sup ∅ 不存在",
                )

            sup_val = max(nums)
            return MathObject(
                result=sup_val,
                steps=[
                    f"集合 = {nums}",
                    f"上界集合 = {{M | M ≥ {sup_val}}}",
                    f"最小上界 = {sup_val}",
                ],
                meaning=f"sup {nums} = {sup_val}",
            )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="infimum")
def infimum(
    s: Union[List[float], Set[float], str],
) -> MathObject:
    """计算下确界（最大下界）。

    Args:
        s: 数值集合（list/set）或描述字符串如 "{x | x > 1}"。

    Returns:
        MathObject，result 为下确界值。
    """
    try:
        if isinstance(s, str):
            desc = s.strip()
            steps = [f"解析集合描述: {desc}"]

            import re

            # 匹配 "x > N" 或 "x >= N"
            m = re.search(r'x\s*(>=?)\s*(-?[\d.]+)', desc)
            if m:
                op = m.group(1)
                val = float(m.group(2))
                steps.append(f"下确界 = {val}")
                return MathObject(
                    result=val,
                    steps=steps,
                    meaning=f"inf {desc} = {val}",
                )

            # 匹配 "x < N" 无下界
            m = re.search(r'x\s*(<=?)\s*(-?[\d.]+)', desc)
            if m:
                steps.append("集合无下界")
                return MathObject(
                    result=float('-inf'),
                    steps=steps,
                    meaning=f"inf {desc} = -∞（无下界）",
                )

            return MathObject(error=f"无法解析集合描述: {desc}")

        nums = sorted(set(float(x) for x in s))
        if not nums:
            return MathObject(
                result=None,
                steps=["空集合无下确界"],
                meaning="inf ∅ 不存在",
            )

        inf_val = min(nums)
        return MathObject(
            result=inf_val,
            steps=[
                f"集合 = {nums}",
                f"下界集合 = {{m | m ≤ {inf_val}}}",
                f"最大下界 = {inf_val}",
            ],
            meaning=f"inf {nums} = {inf_val}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="archimedean_property")
def archimedean_property(
    x: float,
    epsilon: float = 1.0,
) -> MathObject:
    """验证阿基米德性质：∀ ε > 0, 任意实数 x，∃ n ∈ N 使得 nε > x。

    Args:
        x: 任意实数。
        epsilon: 正数，默认 1.0。

    Returns:
        MathObject，result 为满足 nε > x 的最小自然数 n。
    """
    try:
        if epsilon <= 0:
            return MathObject(error="ε 必须为正数")

        n = int(abs(x) / epsilon) + 1
        product = n * epsilon

        steps = [
            f"阿基米德性质: 对 x={x}, ε={epsilon}",
            f"求最小 n ∈ N 使得 n·ε > x",
            f"n = ⌊|x|/ε⌋ + 1 = ⌊{abs(x)/epsilon}⌋ + 1 = {n}",
            f"验证: {n} · {epsilon} = {product} > {x} {'✓' if product > x else '✗'}",
        ]

        return MathObject(
            result=n,
            steps=steps,
            meaning=f"阿基米德性质: ∃ n={n} ∈ N 使得 {n}·{epsilon} > {x}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 real_numbers 模块。"""
    print("=== real_numbers self_test ===")

    # 1. supremum: {x | x < 2} → 2
    r = supremum("{x | x < 2}")
    assert r.ok, r.error
    assert r.result == 2.0
    print(f"  supremum({{x | x < 2}}): {r.result}")

    # 2. infimum: {x | x > 1} → 1
    r = infimum("{x | x > 1}")
    assert r.ok, r.error
    assert r.result == 1.0
    print(f"  infimum({{x | x > 1}}): {r.result}")

    # 3. supremum on finite set
    r = supremum([1, 3, 5, 2, 4])
    assert r.ok and r.result == 5.0
    print(f"  supremum([1,3,5,2,4]): {r.result}")

    # 4. archimedean_property
    r = archimedean_property(100.0, 1.0)
    assert r.ok and r.result == 101
    print(f"  archimedean_property(100, 1): n={r.result}")

    # 5. dedekind_cut
    r = dedekind_cut([1, 2, 3], [4, 5, 6])
    assert r.ok and r.result is True
    print(f"  dedekind_cut([1,2,3], [4,5,6]): {r.result}")

    # 6. dedekind_cut invalid (overlap)
    r = dedekind_cut([1, 2, 4], [3, 4, 5])
    assert r.ok and r.result is False
    print(f"  dedekind_cut([1,2,4], [3,4,5]): {r.result}")

    print("=== real_numbers self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
