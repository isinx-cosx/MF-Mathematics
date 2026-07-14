"""概率空间 — 条件概率、独立性、全概率公式、贝叶斯公式。

依赖: sympy
"""

from __future__ import annotations

from typing import Any, Dict, List, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_prob(value: Union[float, sp.Expr]) -> sp.Expr:
    """将概率值统一转为 sympy 表达式。"""
    if isinstance(value, sp.Expr):
        return value
    return sp.Rational(value).limit_denominator()


@register(module="probability", action="conditional_probability")
def conditional_probability(
    A: Union[float, str],
    B: Union[float, str],
    P: Dict[str, float],
) -> MathObject:
    """计算条件概率 P(A|B) = P(A∩B) / P(B)。

    Args:
        A: 事件 A 的标识符。
        B: 事件 B 的标识符。
        P: 事件概率字典，键为事件名，值为概率值。
           必须包含 "A∩B" 或 "A_and_B" 作为交集概率的键，以及 B 的概率。

    Returns:
        MathObject:
            - result: 条件概率 P(A|B) 的值。
            - steps: 计算步骤。
            - meaning: 条件概率的直观解释。

    Examples:
        >>> conditional_probability("rain", "cloud", {"rain_and_cloud": 0.3, "cloud": 0.5})
    """
    try:
        A_and_B = None
        for key in [f"{A}_and_{B}", f"{A}∩{B}", "A_and_B", "A∩B"]:
            if key in P:
                A_and_B = _to_prob(P[key])
                break
        if A_and_B is None:
            # 尝试直接用字符串键
            for key, val in P.items():
                if "and" in key.lower() or "∩" in key:
                    A_and_B = _to_prob(val)
                    break

        if A_and_B is None:
            return MathObject(
                error="概率字典中缺少交集概率 (A_and_B 或 A∩B)。"
            )

        P_B = _to_prob(P.get(B, P.get("B", None)))
        if P_B is None:
            return MathObject(error=f"概率字典中缺少 P({B}) 的值。")

        if abs(float(P_B)) < 1e-15:
            return MathObject(error=f"P({B}) = 0，条件概率无定义。")

        result = A_and_B / P_B
        return MathObject(
            result=float(result.evalf()),
            steps=[
                f"P(A∩B) = {float(A_and_B.evalf())}",
                f"P(B) = {float(P_B.evalf())}",
                f"P(A|B) = P(A∩B) / P(B) = {float(A_and_B.evalf())} / {float(P_B.evalf())} = {float(result.evalf())}",
            ],
            meaning=f"在事件 {B} 已发生的条件下，事件 {A} 发生的概率为 {float(result.evalf()):.4f}。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="is_independent")
def is_independent(
    A: Union[float, str],
    B: Union[float, str],
    P: Dict[str, float],
) -> MathObject:
    """判断事件 A 和 B 是否独立。P(A∩B) = P(A)·P(B)。

    Args:
        A: 事件 A 的标识符。
        B: 事件 B 的标识符。
        P: 事件概率字典，必须包含 A、B、A_and_B（或 A∩B）的概率。

    Returns:
        MathObject:
            - result: True 表示独立，False 表示不独立。
    """
    try:
        P_A = _to_prob(P.get(A, P.get("A", None)))
        P_B = _to_prob(P.get(B, P.get("B", None)))
        if P_A is None:
            return MathObject(error=f"概率字典中缺少 P({A})。")
        if P_B is None:
            return MathObject(error=f"概率字典中缺少 P({B})。")

        A_and_B = None
        for key in [f"{A}_and_{B}", f"{A}∩{B}", "A_and_B", "A∩B"]:
            if key in P:
                A_and_B = _to_prob(P[key])
                break
        if A_and_B is None:
            return MathObject(error="概率字典中缺少交集概率。")

        product = P_A * P_B
        is_indep = abs(float(A_and_B.evalf()) - float(product.evalf())) < 1e-12

        return MathObject(
            result=is_indep,
            steps=[
                f"P(A) = {float(P_A.evalf())}",
                f"P(B) = {float(P_B.evalf())}",
                f"P(A)×P(B) = {float(product.evalf())}",
                f"P(A∩B) = {float(A_and_B.evalf())}",
                (
                    "两者相等，独立。"
                    if is_indep
                    else "两者不等，不独立。"
                ),
            ],
            meaning=(
                "事件 A 与 B 独立：一个发生不影响另一个的概率。"
                if is_indep
                else "事件 A 与 B 不独立：一个发生会影响另一个的概率。"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="total_probability")
def total_probability(
    events: Dict[str, float],
    P: Dict[str, float],
    condition: str,
) -> MathObject:
    """全概率公式：P(A) = Σ P(A|Bi)·P(Bi)，其中 {Bi} 为完备事件组。

    Args:
        events: 完备事件组及其概率，如 {"B1": 0.6, "B2": 0.4}。
        P: 条件概率字典，键如 "A|B1"、 "A_given_B1"，值为条件概率。
        condition: 被全概率分解的事件名（通常是 "A"）。

    Returns:
        MathObject:
            - result: 全概率 P(A)。
    """
    try:
        total = sp.Rational(0)
        steps = []

        for evt_name, p_evt in events.items():
            p_evt_sym = _to_prob(p_evt)
            cond_key_candidates = [
                f"{condition}|{evt_name}",
                f"{condition}_given_{evt_name}",
            ]
            p_cond = None
            for ck in cond_key_candidates:
                if ck in P:
                    p_cond = _to_prob(P[ck])
                    break
            if p_cond is None:
                return MathObject(
                    error=f"缺少条件概率 P({condition}|{evt_name})。"
                )

            term = p_cond * p_evt_sym
            total += term
            steps.append(
                f"P({condition}|{evt_name})·P({evt_name}) = "
                f"{float(p_cond.evalf())} × {float(p_evt_sym.evalf())} = {float(term.evalf())}"
            )

        return MathObject(
            result=float(total.evalf()),
            steps=steps + [f"P({condition}) = {float(total.evalf())}"],
            meaning=f"利用完备事件组分解，{condition} 的全概率为 {float(total.evalf()):.4f}。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="bayes_theorem")
def bayes_theorem(
    events: Dict[str, float],
    P: Dict[str, float],
    evidence: str,
) -> MathObject:
    """贝叶斯公式：P(Bi|A) = P(A|Bi)·P(Bi) / Σ P(A|Bj)·P(Bj)。

    Args:
        events: 完备事件组及其先验概率，如 {"B1": 0.6, "B2": 0.4}。
        P: 条件概率字典，键如 "A|B1"。
        evidence: 观测到的事件名（证据，通常是 "A"）。

    Returns:
        MathObject:
            - result: 每个事件的后验概率字典。
            - steps: 推导步骤。
    """
    try:
        # 先算总概率（分母）
        total = sp.Rational(0)
        terms: Dict[str, sp.Expr] = {}
        steps = ["一、计算全概率（分母）"]

        for evt_name, p_evt in events.items():
            p_evt_sym = _to_prob(p_evt)
            cond_key_candidates = [
                f"{evidence}|{evt_name}",
                f"{evidence}_given_{evt_name}",
            ]
            p_cond = None
            for ck in cond_key_candidates:
                if ck in P:
                    p_cond = _to_prob(P[ck])
                    break
            if p_cond is None:
                return MathObject(
                    error=f"缺少条件概率 P({evidence}|{evt_name})。"
                )
            term = p_cond * p_evt_sym
            terms[evt_name] = term
            total += term
            steps.append(
                f"  P({evidence}|{evt_name})·P({evt_name}) = "
                f"{float(p_cond.evalf())} × {float(p_evt_sym.evalf())} = {float(term.evalf())}"
            )
        steps.append(f"  全概率 P({evidence}) = {float(total.evalf())}")

        # 再算每个后验概率
        steps.append("\n二、计算后验概率（贝叶斯公式）")
        posterior: Dict[str, float] = {}
        for evt_name, term in terms.items():
            post = term / total
            posterior[evt_name] = float(post.evalf())
            steps.append(
                f"  P({evt_name}|{evidence}) = {float(term.evalf())} / "
                f"{float(total.evalf())} = {float(post.evalf())}"
            )

        return MathObject(
            result=posterior,
            steps=steps,
            meaning=f"基于证据 '{evidence}'，更新了各事件的后验概率。",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """模块自测。"""
    print("=== probability_space 自测 ===")

    # 条件概率
    r1 = conditional_probability(
        "rain", "cloud",
        {"rain_and_cloud": 0.3, "cloud": 0.5},
    )
    assert r1.ok and abs(r1.result - 0.6) < 0.01, r1.error
    print(f"  conditional_probability: {r1.result}  PASSED")

    # 独立性
    r2 = is_independent("A", "B", {"A": 0.5, "B": 0.4, "A_and_B": 0.2})
    assert r2.ok and r2.result is True, r2.error
    print(f"  is_independent (独立): {r2.result}  PASSED")

    r3 = is_independent("A", "B", {"A": 0.5, "B": 0.4, "A_and_B": 0.1})
    assert r3.ok and r3.result is False, r3.error
    print(f"  is_independent (不独立): {r3.result}  PASSED")

    # 全概率
    r4 = total_probability(
        {"B1": 0.6, "B2": 0.4},
        {"A|B1": 0.8, "A|B2": 0.3},
        "A",
    )
    assert r4.ok, r4.error
    # P(A) = 0.6*0.8 + 0.4*0.3 = 0.48 + 0.12 = 0.60
    assert abs(r4.result - 0.60) < 0.01, r4.result
    print(f"  total_probability: {r4.result}  PASSED")

    # 贝叶斯
    r5 = bayes_theorem(
        {"B1": 0.6, "B2": 0.4},
        {"A|B1": 0.8, "A|B2": 0.3},
        "A",
    )
    assert r5.ok, r5.error
    assert abs(r5.result["B1"] - 0.8) < 0.01, r5.result
    print(f"  bayes_theorem: {r5.result}  PASSED")

    print("probability_space 自测全部通过!\n")
    return True


if __name__ == "__main__":
    self_test()
