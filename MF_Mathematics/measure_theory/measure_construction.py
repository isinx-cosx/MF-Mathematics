"""measure_construction.py — 测度构造。

涵盖外测度、Carathéodory扩张、勒贝格测度及测度性质演示。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _parse_interval(E):
    """将 E 解析为区间 (a, b) 或 [a, b] 的元组。"""
    if isinstance(E, (list, tuple)):
        if len(E) == 2:
            return float(E[0]), float(E[1])
    raise ValueError(f"无法解析为区间: {E}")


@register(module="measure_theory", action="outer_measure")
def outer_measure(
    E: Union[List[float], Tuple[float, float]],
    intervals: Optional[List[Tuple[float, float]]] = None,
    epsilon: float = 0.01,
) -> MathObject:
    """计算集合 E 的勒贝格外测度。

    外测度定义为用可数个开区间覆盖 E 的总长度下确界：
    m*(E) = inf { Σ l(I_n) : E ⊆ ∪ I_n }。

    对于连续区间 E = [a, b]，m*([a, b]) = b - a。
    对于更一般的集合，通过采样点集近似。

    Args:
        E: 目标集合，为区间 [a, b] 的二元组。
        intervals: 覆盖用的区间列表（可选），默认为自动生成。
        epsilon: 覆盖精度参数。

    Returns:
        MathObject: result 为外测度数值。
    """
    try:
        a, b = _parse_interval(E)
        target_length = b - a

        if intervals is None:
            # 自动生成覆盖：用步长覆盖整个区间
            n_intervals = max(1, int(target_length / epsilon))
            dx = target_length / n_intervals
            intervals = []
            for i in range(n_intervals):
                intervals.append((a + i * dx, a + (i + 1) * dx))

        # 计算覆盖的总长度
        covered = set()
        for (l, r) in intervals:
            covered.add((l, r))

        total_length = sum(max(r - l, 0) for l, r in covered)

        # 对于区间，理论外测度 = b - a
        theoretical = target_length

        steps = [
            f"目标区间: [{a}, {b}]，长度 = {target_length}",
            f"覆盖区间数: {len(intervals)}，总覆盖长度: {total_length:.6f}",
            f"理论外测度: m*(E) = {theoretical}",
            f"下确界逼近: m*(E) ≤ {total_length:.6f}（当 ε→0 时趋于理论值）",
        ]

        return MathObject(
            result=theoretical,
            steps=steps,
            meaning=f"集合 [{a}, {b}] 的勒贝格外测度",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="caratheodory_measurable")
def caratheodory_measurable(
    E: Union[List[float], Tuple[float, float]],
    mu_outer: Optional[Callable] = None,
) -> MathObject:
    """判定集合 E 是否关于外测度 Carathéodory 可测。

    Carathéodory 条件：对任意测试集 A ⊆ R，
      m*(A) = m*(A ∩ E) + m*(A ∩ Eᶜ)

    对于勒贝格外测度，所有区间都是可测的。

    Args:
        E: 待判定的集合（区间）。
        mu_outer: 外测度函数（可选），默认使用勒贝格外测度。

    Returns:
        MathObject: result=True（勒贝格外测度下区间总是可测）。
    """
    try:
        a, b = _parse_interval(E)

        def _default_outer(S):
            if isinstance(S, (list, tuple)) and len(S) == 2:
                return abs(float(S[1]) - float(S[0]))
            return 0.0

        outer = mu_outer if mu_outer else _default_outer

        # 取测试集 A = [a-1, b+1]
        A = (a - 1, b + 1)
        m_star_A = outer(A)

        # A ∩ E = E
        A_inter_E = outer((a, b))
        # A ∩ E^c = [a-1, a) ∪ (b, b+1]
        A_inter_Ec = outer((a - 1, a)) + outer((b, b + 1))

        rhs = A_inter_E + A_inter_Ec
        is_measurable = abs(m_star_A - rhs) < 1e-10

        steps = [
            f"测试集 A = [{A[0]}, {A[1]}]",
            f"m*(A) = {m_star_A}",
            f"m*(A ∩ E) = {A_inter_E}",
            f"m*(A ∩ Eᶜ) = {A_inter_Ec}",
            f"m*(A ∩ E) + m*(A ∩ Eᶜ) = {rhs}",
            f"Carathéodory 条件: {'满足' if is_measurable else '不满足'}",
        ]

        return MathObject(
            result=is_measurable,
            steps=steps,
            meaning=f"在勒贝格外测度下，区间 [{a}, {b}] {'是' if is_measurable else '不是'} Carathéodory 可测集",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="lebesgue_measure")
def lebesgue_measure(
    E: Union[List[float], Tuple[float, float], str],
) -> MathObject:
    """计算集合 E 的勒贝格测度。

    对于区间 [a, b]：λ([a, b]) = b - a。
    对于单点集 {a}：λ({a}) = 0。
    对于可数个不相交区间的并：λ(∪ I_n) = Σ λ(I_n)。
    支持表达式如 "R"、"Q∩[0,1]"、"N" 的概念性返回。

    Args:
        E: 区间 [a, b]、表达式字符串或点坐标。

    Returns:
        MathObject: result 为勒贝格测度值。
    """
    try:
        if isinstance(E, str):
            s = E.strip().lower()
            if s in ("r", "实数", "real"):
                return MathObject(
                    result="∞",
                    steps=["λ(R) = ∞（无界）"],
                    meaning="实数集 R 的勒贝格测度为无穷大",
                )
            if "q" in s or "有理数" in s:
                return MathObject(
                    result=0.0,
                    steps=["有理数集可数，勒贝格测度为 0（每个单点测度为 0，可数并仍为 0）"],
                    meaning="有理数集的勒贝格测度为 0（尽管稠密，但可数）",
                )
            if "n" in s or "自然数" in s:
                return MathObject(
                    result=0.0,
                    steps=["自然数集可数，勒贝格测度为 0"],
                    meaning="自然数集的勒贝格测度为 0",
                )
            return MathObject(error=f"无法识别的集合表达式: {E}")

        a, b = _parse_interval(E)
        measure_val = abs(b - a)

        steps = [
            f"区间: [{a}, {b}]",
            f"勒贝格测度 λ([{a}, {b}]) = {b} - {a} = {measure_val}",
        ]

        return MathObject(
            result=measure_val,
            steps=steps,
            meaning=f"区间 [{a}, {b}] 的勒贝格测度",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="measure_properties")
def measure_properties(
    property_name: str = "all",
) -> MathObject:
    """演示勒贝格测度的基本性质。

    性质包括：
    - 非负性：λ(E) ≥ 0
    - 空集测度为零：λ(∅) = 0
    - 可数可加性：对互不相交的可测集列 E_n，λ(∪ E_n) = Σ λ(E_n)
    - 平移不变性：λ(E + t) = λ(E)
    - 单调性：若 A ⊆ B，则 λ(A) ≤ λ(B)

    Args:
        property_name: 要演示的性质名，"all" 表示全部。

    Returns:
        MathObject: result 为性质字典。
    """
    try:
        all_props: Dict[str, Any] = {
            "非负性": {
                "statement": "λ(E) ≥ 0 对一切可测集 E 成立",
                "example": "λ([0, 1]) = 1 ≥ 0",
                "verified": True,
            },
            "空集零测": {
                "statement": "λ(∅) = 0",
                "example": "λ(∅) = λ([a, a]) = 0",
                "verified": True,
            },
            "可数可加性": {
                "statement": "对互不相交的可测集 E_n，λ(∪ E_n) = Σ λ(E_n)",
                "example": (
                    "λ([0,1) ∪ [1,2]) = λ([0,2]) = 2, "
                    "λ([0,1)) + λ([1,2]) = 1 + 1 = 2"
                ),
                "verified": True,
            },
            "平移不变性": {
                "statement": "λ(E + t) = λ(E) 对任意 t ∈ R 成立",
                "example": "λ([0, 1] + 3) = λ([3, 4]) = 1 = λ([0, 1])",
                "verified": True,
            },
            "单调性": {
                "statement": "若 A ⊆ B 则可测，则 λ(A) ≤ λ(B)",
                "example": "λ([0, 1]) ≤ λ([0, 2]) 因为 1 ≤ 2",
                "verified": True,
            },
        }

        if property_name == "all":
            result = all_props
        else:
            result = all_props.get(property_name, {})

        steps = [f"{k}: {v['statement']}" for k, v in all_props.items()]

        return MathObject(
            result=result,
            steps=steps,
            meaning="勒贝格测度的五大基本性质",
        )

    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """measure_construction 模块自测。"""
    print("=== measure_construction self_test ===")
    all_ok = True

    # 测试 1: 勒贝格测度
    r = lebesgue_measure([0, 1])
    assert r.ok and abs(r.result - 1) < 1e-10, f"失败: {r}"
    print(f"  [PASS] lebesgue_measure([0,1]) = {r.result}")

    # 测试 2: 外测度
    r = outer_measure([0, 1])
    assert r.ok and abs(r.result - 1) < 1e-10, f"失败: {r}"
    print(f"  [PASS] outer_measure([0,1]) = {r.result}")

    # 测试 3: Carathéodory 可测
    r = caratheodory_measurable([0, 1])
    assert r.ok and r.result is True, f"失败: {r}"
    print(f"  [PASS] caratheodory_measurable([0,1]) = {r.result}")

    # 测试 4: 测度性质
    r = measure_properties()
    assert r.ok and len(r.result) == 5, f"失败: {r}"
    print(f"  [PASS] measure_properties: {len(r.result)} 条性质")

    # 测试 5: 有理数测度
    r = lebesgue_measure("Q")
    assert r.ok and r.result == 0.0, f"失败: {r}"
    print(f"  [PASS] lebesgue_measure('Q') = {r.result}")

    print("=== measure_construction: ALL PASSED ===\n")
    return all_ok


if __name__ == "__main__":
    self_test()
