"""数列 — 数列定义、等差数列、等比数列、递推数列。

依赖: sympy, math
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


# ===================================================================
# 数列定义
# ===================================================================


@register(module="algebra", action="sequence_term")
def sequence_term(
    formula: str, n: int
) -> MathObject:
    """根据通项公式计算第 n 项。

    Args:
        formula: 通项公式（用 n 表示项号），如 "n^2"、"2*n+1"。
        n: 项号。

    Returns:
        MathObject，result 为第 n 项的值。
    """
    try:
        sym_n = sp.Symbol("n")
        expr = sp.sympify(formula)
        val = float(expr.subs(sym_n, n).evalf())
        # 如果是整数则去小数
        if val == int(val):
            val = int(val)
        return MathObject(
            result=val,
            steps=[
                f"通项公式: a_n = {formula}",
                f"代入 n = {n}: a_{n} = {val}",
            ],
            meaning=f"数列 a_n = {formula} 的第 {n} 项为 {val}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 等差数列
# ===================================================================


@register(module="algebra", action="arithmetic_sequence")
def arithmetic_sequence(
    a1: Union[int, float], d: Union[int, float], n: int
) -> MathObject:
    """生成等差数列前 n 项。

    Args:
        a1: 首项。
        d: 公差。
        n: 项数。

    Returns:
        MathObject，result 为前 n 项的列表。
    """
    try:
        if n <= 0:
            return MathObject(error="项数 n 必须为正整数")
        terms = [a1 + i * d for i in range(n)]
        an = terms[-1]
        return MathObject(
            result=terms,
            steps=[
                f"等差数列: a₁ = {a1}，公差 d = {d}",
                f"通项公式: a_n = a₁ + (n-1)d = {a1} + (n-1)×{d}",
                f"前 {n} 项: {terms}",
                f"末项 a_{n} = {an}",
            ],
            meaning=f"首项 {a1}，公差 {d} 的等差数列前 {n} 项",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="arithmetic_sum")
def arithmetic_sum(
    a1: Union[int, float], d: Union[int, float], n: int
) -> MathObject:
    """计算等差数列前 n 项和。

    S_n = n/2 * (a₁ + a_n) = n/2 * [2a₁ + (n-1)d]

    Args:
        a1: 首项。
        d: 公差。
        n: 项数。

    Returns:
        MathObject，result 为前 n 项和。
    """
    try:
        if n <= 0:
            return MathObject(error="项数 n 必须为正整数")
        an = a1 + (n - 1) * d
        sn = n / 2 * (a1 + an)
        # 整数化
        if sn == int(sn):
            sn = int(sn)
        else:
            sn = round(sn, 10)
        return MathObject(
            result=sn,
            steps=[
                f"等差数列: a₁ = {a1}，d = {d}",
                f"a_{n} = a₁ + (n-1)d = {a1} + {n-1}×{d} = {an}",
                f"S_{n} = n/2 × (a₁ + a_{n})",
                f"     = {n}/2 × ({a1} + {an})",
                f"     = {sn}",
            ],
            meaning=f"等差数列前 {n} 项和为 {sn}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="arithmetic_proof")
def arithmetic_proof() -> MathObject:
    """倒序相加法证明等差数列求和公式。

    Returns:
        MathObject，result 为证明步骤。
    """
    steps = [
        "【倒序相加法证明 S_n = n(a₁ + a_n) / 2】",
        "",
        "设等差数列: a₁, a₂, ..., a_n，公差 d",
        "a_k = a₁ + (k-1)d",
        "",
        "正序: S_n = a₁ + a₂ + ... + a_n         (1)",
        "倒序: S_n = a_n + a_{n-1} + ... + a₁   (2)",
        "",
        "(1) + (2):",
        "2S_n = (a₁ + a_n) + (a₂ + a_{n-1}) + ... + (a_n + a₁)",
        "     = (a₁ + a_n) + (a₁ + a_n) + ... + (a₁ + a_n)  共 n 项",
        "     = n(a₁ + a_n)",
        "",
        "∴ S_n = n(a₁ + a_n) / 2  ∎",
    ]
    return MathObject(
        result="S_n = n(a₁ + a_n) / 2",
        steps=steps,
        meaning="倒序相加法是等差数列求和的核心证明方法",
    )


# ===================================================================
# 等比数列
# ===================================================================


@register(module="algebra", action="geometric_sequence")
def geometric_sequence(
    a1: Union[int, float], q: Union[int, float], n: int
) -> MathObject:
    """生成等比数列前 n 项。

    Args:
        a1: 首项。
        q: 公比。
        n: 项数。

    Returns:
        MathObject，result 为前 n 项的列表。
    """
    try:
        if n <= 0:
            return MathObject(error="项数 n 必须为正整数")
        terms = [a1 * (q ** i) for i in range(n)]
        an = terms[-1]
        return MathObject(
            result=terms,
            steps=[
                f"等比数列: a₁ = {a1}，公比 q = {q}",
                f"通项公式: a_n = a₁ × q^(n-1) = {a1} × {q}^(n-1)",
                f"前 {n} 项: {terms}",
                f"末项 a_{n} = {an}",
            ],
            meaning=f"首项 {a1}，公比 {q} 的等比数列前 {n} 项",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="geometric_sum")
def geometric_sum(
    a1: Union[int, float], q: Union[int, float], n: int
) -> MathObject:
    """计算等比数列前 n 项和。

    q ≠ 1: S_n = a₁(1 - q^n) / (1 - q)
    q = 1: S_n = n × a₁

    Args:
        a1: 首项。
        q: 公比。
        n: 项数。

    Returns:
        MathObject，result 为前 n 项和。
    """
    try:
        if n <= 0:
            return MathObject(error="项数 n 必须为正整数")
        if q == 1:
            sn = n * a1
            formula_used = "S_n = n × a₁（q = 1）"
        else:
            sn = a1 * (1 - q ** n) / (1 - q)
            formula_used = f"S_n = a₁(1 - q^n) / (1 - q)"
        
        if isinstance(sn, float) and sn == int(sn):
            sn = int(sn)
        elif isinstance(sn, float):
            sn = round(sn, 10)

        return MathObject(
            result=sn,
            steps=[
                f"等比数列: a₁ = {a1}，q = {q}",
                formula_used,
                f"S_{n} = {a1} × (1 - {q}^{n}) / (1 - {q})" if q != 1 else f"S_{n} = {n} × {a1}",
                f"     = {sn}",
            ],
            meaning=f"等比数列前 {n} 项和为 {sn}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="geometric_proof")
def geometric_proof() -> MathObject:
    """错位相减法证明等比数列求和公式。

    Returns:
        MathObject，result 为证明步骤。
    """
    steps = [
        "【错位相减法证明 S_n = a₁(1 - q^n) / (1 - q) （q ≠ 1）】",
        "",
        "设等比数列: a₁, a₁q, a₁q², ..., a₁q^(n-1)",
        "",
        "正序: S_n = a₁ + a₁q + a₁q² + ... + a₁q^(n-1)              (1)",
        "× q: q·S_n =      a₁q + a₁q² + ... + a₁q^(n-1) + a₁q^n    (2)",
        "",
        "(1) - (2):",
        "S_n - q·S_n = a₁ - a₁q^n",
        "(1 - q)·S_n = a₁(1 - q^n)",
        "",
        "∴ S_n = a₁(1 - q^n) / (1 - q)  ∎",
        "",
        "当 q = 1 时，S_n = n·a₁（各项均为 a₁）",
    ]
    return MathObject(
        result="S_n = a₁(1 - q^n) / (1 - q)",
        steps=steps,
        meaning="错位相减法是等比数列求和的核心证明方法",
    )


# ===================================================================
# 递推数列
# ===================================================================


@register(module="algebra", action="recurrence_sequence")
def recurrence_sequence(
    init: List[Union[int, float]],
    relation: str,
    n: int,
) -> MathObject:
    """根据递推关系生成数列。

    Args:
        init: 初始值列表，如 [1, 1]（斐波那契数列前两项）。
        relation: 递推关系表达式。使用 a[k-1], a[k-2] 等表示前面的项。
                  例如斐波那契: "a[-1] + a[-2]"。
        n: 生成的项数。

    Returns:
        MathObject，result 为生成数列。
    """
    try:
        if n <= 0:
            return MathObject(error="项数 n 必须为正整数")
        if not init:
            return MathObject(error="初始值不能为空")

        seq = list(init)
        k = len(init)

        while len(seq) < n:
            # 构建局部变量
            local_vars = {}
            for i in range(1, min(k, len(seq)) + 1):
                local_vars[f"a_{i}"] = seq[-i]
                local_vars[f"a{i}"] = seq[-i]
            # 使用 a[-i] 形式
            local_vars["a"] = seq

            try:
                # 替换 a[-1], a[-2] 等
                rel = relation
                import re
                def _replace(match: re.Match) -> str:
                    idx = int(match.group(1))
                    if 1 <= idx <= len(seq):
                        return str(seq[-idx])
                    return match.group(0)
                rel_evaluated = re.sub(r'a\[-(\d+)\]', _replace, rel)
                next_val = float(sp.sympify(rel_evaluated))
            except Exception:
                return MathObject(error=f"无法解析递推关系式 '{relation}'，请使用 a[-1] 表示前一项")

            seq.append(int(next_val) if next_val == int(next_val) else next_val)

        return MathObject(
            result=seq[:n],
            steps=[
                f"递推数列: 初始值 = {init}",
                f"递推关系: a_k = {relation}（k > {len(init)}）",
                f"生成 {n} 项: {seq[:n]}",
            ],
            meaning=f"递推数列前 {n} 项",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 sequences 模块。"""
    print("=== sequences self_test ===")

    # 1. sequence_term
    r = sequence_term("n^2", 5)
    assert r.ok and r.result == 25
    print(f"  sequence_term(n^2, 5): {r.result}")

    # 2. arithmetic_sequence
    r = arithmetic_sequence(1, 2, 5)
    assert r.ok and r.result == [1, 3, 5, 7, 9]
    print(f"  arithmetic_sequence(1,2,5): {r.result}")

    # 3. arithmetic_sum
    r = arithmetic_sum(1, 2, 5)
    assert r.ok and r.result == 25
    print(f"  arithmetic_sum(1,2,5): {r.result}")

    # 4. geometric_sequence
    r = geometric_sequence(2, 3, 4)
    assert r.ok and r.result == [2, 6, 18, 54]
    print(f"  geometric_sequence(2,3,4): {r.result}")

    # 5. geometric_sum
    r = geometric_sum(2, 3, 4)
    assert r.ok
    print(f"  geometric_sum(2,3,4): {r.result}")

    # 6. arithmetic_proof
    r = arithmetic_proof()
    assert r.ok
    print("  arithmetic_proof: pass")

    # 7. recurrence_sequence (Fibonacci)
    r = recurrence_sequence([1, 1], "a[-1] + a[-2]", 10)
    assert r.ok and r.result[:6] == [1, 1, 2, 3, 5, 8]
    print(f"  recurrence_sequence(Fibonacci 10): {r.result}")

    print("=== sequences self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
