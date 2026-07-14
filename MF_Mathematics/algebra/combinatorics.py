"""计数与二项式 — 加法/乘法原理、排列组合、二项式定理。

依赖: math
"""

from __future__ import annotations

import math
from typing import Any, List, Union

from ..core.math_object import MathObject
from ..core.registry import register


# ===================================================================
# 加法/乘法原理
# ===================================================================


@register(module="algebra", action="addition_principle")
def addition_principle(ways_list: List[int]) -> MathObject:
    """分类计数（加法原理）：各类方法数之和。

    Args:
        ways_list: 每类完成方法数列表，如 [3, 5, 2]。

    Returns:
        MathObject，result 为总方法数。
    """
    try:
        total = sum(ways_list)
        return MathObject(
            result=total,
            steps=[
                f"分类计数: {len(ways_list)} 类方法",
                *[f"  第 {i+1} 类: {w} 种" for i, w in enumerate(ways_list)],
                f"加法原理: 总方法数 = {' + '.join(str(w) for w in ways_list)} = {total}",
            ],
            meaning=f"分类完成一件事，共有 {total} 种方法（加法原理）",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="multiplication_principle")
def multiplication_principle(steps_list: List[int]) -> MathObject:
    """分步计数（乘法原理）：各步骤方法数之积。

    Args:
        steps_list: 每步选择数列表，如 [3, 4, 2]。

    Returns:
        MathObject，result 为总方法数。
    """
    try:
        total = 1
        for s in steps_list:
            total *= s
        return MathObject(
            result=total,
            steps=[
                f"分步计数: {len(steps_list)} 步",
                *[f"  第 {i+1} 步: {w} 种选择" for i, w in enumerate(steps_list)],
                f"乘法原理: 总方法数 = {' × '.join(str(w) for w in steps_list)} = {total}",
            ],
            meaning=f"分步完成一件事，共有 {total} 种方法（乘法原理）",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 排列组合
# ===================================================================


@register(module="algebra", action="permutation")
def permutation(n: int, m: int) -> MathObject:
    """排列数 A(n, m) = n! / (n-m)!。

    Args:
        n: 总元素数。
        m: 选取元素数。

    Returns:
        MathObject，result 为排列数。
    """
    try:
        if n < 0 or m < 0:
            return MathObject(error="n 和 m 必须为非负整数")
        if m > n:
            return MathObject(error="m 不能大于 n")
        result = math.perm(n, m)
        formula = f"A({n},{m}) = {n}! / ({n}-{m})!"
        calc = f"= {math.factorial(n)} / {math.factorial(n-m)} = {result}" if n <= 20 else f"= {result}"
        return MathObject(
            result=result,
            steps=[
                f"排列: 从 {n} 个元素中选 {m} 个排列",
                formula,
                calc,
            ],
            meaning=f"A({n}, {m}) = {result}，表示从 {n} 个元素中取 {m} 个的有序排列数",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="combination")
def combination(n: int, m: int) -> MathObject:
    """组合数 C(n, m) = n! / (m! × (n-m)!)。

    Args:
        n: 总元素数。
        m: 选取元素数。

    Returns:
        MathObject，result 为组合数。
    """
    try:
        if n < 0 or m < 0:
            return MathObject(error="n 和 m 必须为非负整数")
        if m > n:
            return MathObject(error="m 不能大于 n")
        result = math.comb(n, m)
        formula = f"C({n},{m}) = {n}! / ({m}! × ({n}-{m})!)"
        return MathObject(
            result=result,
            steps=[
                f"组合: 从 {n} 个元素中选 {m} 个组合",
                formula,
                f"= {result}",
            ],
            meaning=f"C({n}, {m}) = {result}，表示从 {n} 个元素中取 {m} 个的无序组合数",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="comb_identities")
def comb_identities() -> MathObject:
    """展示常用组合恒等式。

    Returns:
        MathObject，result 为恒等式列表。
    """
    identities = [
        "C(n, 0) = C(n, n) = 1",
        "C(n, 1) = C(n, n-1) = n",
        "对称性: C(n, m) = C(n, n-m)",
        "递推公式: C(n, m) = C(n-1, m-1) + C(n-1, m)（帕斯卡恒等式）",
        "求和公式: Σ_{k=0}^n C(n, k) = 2^n",
        "交错和: Σ_{k=0}^n (-1)^k C(n, k) = 0 (n ≥ 1)",
        "范德蒙恒等式: Σ_{k=0}^r C(m, k)·C(n, r-k) = C(m+n, r)",
        "朱世杰恒等式: Σ_{k=m}^n C(k, m) = C(n+1, m+1)",
    ]
    return MathObject(
        result=identities,
        steps=["【组合恒等式】", *identities],
        meaning="组合数的基本性质与恒等式",
    )


# ===================================================================
# 二项式定理
# ===================================================================


@register(module="algebra", action="binomial_expand")
def binomial_expand(
    a: Union[int, float, str], b: Union[int, float, str], n: int
) -> MathObject:
    """展开 (a + b)^n。

    Args:
        a: 第一项。
        b: 第二项。
        n: 指数（非负整数）。

    Returns:
        MathObject，result 为展开式字符串。
    """
    try:
        if n < 0:
            return MathObject(error="n 必须为非负整数")
        terms = []
        steps = [f"二项式展开: ({a} + {b})^{n}"]
        steps.append("使用二项式定理: (a+b)^n = Σ C(n,k)·a^(n-k)·b^k")

        for k in range(n + 1):
            coeff = math.comb(n, k)
            if coeff == 1 and n - k == 0 and k == 0:
                term = "1"
            elif coeff == 1:
                if n - k == 0:
                    term = f"{b}^{k}" if k > 1 else str(b)
                elif k == 0:
                    term = f"{a}^{n - k}" if n - k > 1 else str(a)
                else:
                    a_part = f"{a}^{n - k}" if n - k > 1 else str(a)
                    b_part = f"{b}^{k}" if k > 1 else str(b)
                    term = f"{a_part}·{b_part}"
            else:
                if n - k == 0 and k == 0:
                    term = str(coeff)
                elif n - k == 0:
                    b_part = f"{b}^{k}" if k > 1 else str(b)
                    term = f"{coeff}·{b_part}"
                elif k == 0:
                    a_part = f"{a}^{n - k}" if n - k > 1 else str(a)
                    term = f"{coeff}·{a_part}"
                else:
                    a_part = f"{a}^{n - k}" if n - k > 1 else str(a)
                    b_part = f"{b}^{k}" if k > 1 else str(b)
                    term = f"{coeff}·{a_part}·{b_part}"
            terms.append(term)

        expansion = " + ".join(terms)
        steps.append(f"展开式: {expansion}")

        return MathObject(
            result=expansion,
            steps=steps,
            meaning=f"({a} + {b})^{n} = {expansion}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="binomial_term")
def binomial_term(
    a: Union[int, float, str],
    b: Union[int, float, str],
    n: int,
    k: int,
) -> MathObject:
    """二项式展开的通项公式 T_{k+1} = C(n, k) × a^(n-k) × b^k。

    Args:
        a: 第一项。
        b: 第二项。
        n: 指数。
        k: 项索引（0-based，即第 k+1 项）。

    Returns:
        MathObject，result 为通项表达式和系数。
    """
    try:
        if n < 0:
            return MathObject(error="n 必须为非负整数")
        if k < 0 or k > n:
            return MathObject(error=f"k 必须在 [0, {n}] 范围内")
        coeff = math.comb(n, k)

        # 构建通项表达式
        a_part = ""
        b_part = ""
        if n - k == 1:
            a_part = str(a)
        elif n - k > 1:
            a_part = f"{a}^{n - k}"
        if k == 1:
            b_part = str(b)
        elif k > 1:
            b_part = f"{b}^{k}"

        if n - k == 0 and k == 0:
            term_str = str(coeff)
        elif n - k == 0:
            term_str = f"{coeff}·{b_part}" if coeff > 1 else b_part
        elif k == 0:
            term_str = f"{coeff}·{a_part}" if coeff > 1 else a_part
        else:
            parts = [str(coeff), a_part, b_part] if coeff > 1 else [a_part, b_part]
            term_str = "·".join(p for p in parts if p)

        return MathObject(
            result={"term": term_str, "coefficient": coeff, "k": k, "term_number": k + 1},
            steps=[
                f"({a} + {b})^{n} 的第 k+1 = {k+1} 项",
                f"通项公式: T_{{{k+1}}} = C({n}, {k}) × {a}^({n}-{k}) × {b}^{k}",
                f"          = C({n},{k}) × {a}^{n-k} × {b}^{k}",
                f"          = {coeff} × {a}^{n-k} × {b}^{k}",
                f"          = {term_str}",
            ],
            meaning=f"第 {k+1} 项: {term_str}，系数 C({n},{k}) = {coeff}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 combinatorics 模块。"""
    print("=== combinatorics self_test ===")

    # 1. addition_principle
    r = addition_principle([3, 5, 2])
    assert r.ok and r.result == 10
    print(f"  addition_principle: {r.result}")

    # 2. multiplication_principle
    r = multiplication_principle([3, 4, 2])
    assert r.ok and r.result == 24
    print(f"  multiplication_principle: {r.result}")

    # 3. permutation
    r = permutation(5, 3)
    assert r.ok and r.result == 60
    print(f"  permutation(5,3): {r.result}")

    # 4. combination
    r = combination(5, 2)
    assert r.ok and r.result == 10
    print(f"  combination(5,2): {r.result}")

    # 5. binomial_expand
    r = binomial_expand("x", "y", 3)
    assert r.ok
    print(f"  binomial_expand((x+y)^3): {r.result}")

    # 6. binomial_term
    r = binomial_term("x", "y", 5, 2)
    assert r.ok and r.result["coefficient"] == 10
    print(f"  binomial_term(x+y, 5, k=2): {r.result}")

    print("=== combinatorics self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
