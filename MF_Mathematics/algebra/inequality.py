"""不等式 — 基本性质、一元一次不等式、不等式组、一元二次不等式、基本不等式。

依赖: sympy
"""

from __future__ import annotations

from typing import Any, List, Optional, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_sympy(expr: Union[str, sp.Expr]) -> sp.Expr:
    """字符串转 sympy 表达式。"""
    if isinstance(expr, sp.Expr):
        return expr
    return sp.sympify(str(expr))


# ===================================================================
# 不等式基本性质
# ===================================================================


@register(module="algebra", action="inequality_properties")
def inequality_properties(
    a: Union[int, float], b: Union[int, float], c: Union[int, float]
) -> MathObject:
    """演示不等式基本性质：乘除负数时不等号方向改变。

    Args:
        a: 左值。
        b: 右值，假设 a < b。
        c: 乘数（可正可负）。

    Returns:
        MathObject，result 为各种操作后的不等关系列表。
    """
    try:
        if a >= b:
            return MathObject(error="请确保 a < b，不等式 a < b 才是前提")

        results = []
        steps = [f"前提: {a} < {b}"]

        # 加 c
        results.append(f"加 {c}: {a}+{c} < {b}+{c}  (方向不变)")
        steps.append(f"a + c = {a+c}  <  b + c = {b+c}")

        # 减 c
        results.append(f"减 {c}: {a}-{c} < {b}-{c}  (方向不变)")
        steps.append(f"a - c = {a-c}  <  b - c = {b-c}")

        # 乘 c
        if c > 0:
            results.append(f"乘 {c}(正): {a}×{c} < {b}×{c}  (方向不变)")
        elif c < 0:
            results.append(f"乘 {c}(负): {a}×{c} > {b}×{c}  (方向反转!)")
        else:
            results.append(f"乘 0: {a}×0 = {b}×0 = 0  (变为等式)")
        steps.append(f"a × c = {a*c}  {'<' if c>0 else '>' if c<0 else '='}  b × c = {b*c}")

        # 除以 c
        if c > 0:
            results.append(f"除以 {c}(正): {a}/{c} < {b}/{c}  (方向不变)")
        elif c < 0:
            results.append(f"除以 {c}(负): {a}/{c} > {b}/{c}  (方向反转!)")
        else:
            results.append("除以 0: 无意义")

        return MathObject(
            result=results,
            steps=steps,
            meaning="不等式基本性质：加减同一数方向不变；乘除正数方向不变；乘除负数方向反转",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 一元一次不等式
# ===================================================================


@register(module="algebra", action="solve_linear_inequality")
def solve_linear_inequality(expr: Union[str, sp.Expr], var: str = "x") -> MathObject:
    """求解一元一次不等式。

    Args:
        expr: 不等式表达式，如 "2*x - 3 > 0" 或 "2*x - 3 < 5"。
        var: 变量名。

    Returns:
        MathObject，result 为解集（区间表示）。
    """
    try:
        ex = _to_sympy(expr)
        x = sp.Symbol(var)

        if isinstance(ex, sp.StrictGreaterThan):
            rel = ">"
        elif isinstance(ex, sp.GreaterThan):
            rel = "≥"
        elif isinstance(ex, sp.StrictLessThan):
            rel = "<"
        elif isinstance(ex, sp.LessThan):
            rel = "≤"
        else:
            return MathObject(error="表达式不是有效的不等式，请使用 >, <, >=, <= 运算符")

        lhs = ex.lhs
        rhs = ex.rhs
        solution = sp.solve_univariate_inequality(ex, x, relational=False)

        # 格式化解集
        if isinstance(solution, sp.Interval):
            left_bracket = "[" if solution.left_open else "["
            right_bracket = "]" if solution.right_open else "]"
            interval_str = f"{left_bracket}{solution.start}, {solution.end}{right_bracket}"
        else:
            interval_str = str(solution)

        return MathObject(
            result=interval_str,
            steps=[
                f"不等式: {lhs} {rel} {rhs}",
                f"移项求解: {lhs - rhs} {rel} 0",
                f"解集: {interval_str}",
            ],
            meaning=f"不等式 {ex} 的解集为 {interval_str}，在数轴上对应的区间",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 一元一次不等式组
# ===================================================================


@register(module="algebra", action="solve_inequality_system")
def solve_inequality_system(
    exprs: List[Union[str, sp.Expr]], var: str = "x"
) -> MathObject:
    """求解一元一次不等式组（取交集）。

    Args:
        exprs: 不等式列表，如 ["x > 1", "x < 5"]。
        var: 变量名。

    Returns:
        MathObject，result 为交集区间。
    """
    try:
        x = sp.Symbol(var)
        inequalities = []
        for e in exprs:
            iex = _to_sympy(e)
            if isinstance(iex, (sp.StrictGreaterThan, sp.GreaterThan, sp.StrictLessThan, sp.LessThan)):
                inequalities.append(iex)
            else:
                return MathObject(error=f"'{e}' 不是有效的不等式")

        # 求解每个不等式的解集，然后取交集
        solution = sp.solve_univariate_inequality(inequalities[0], x, relational=False)
        for iex in inequalities[1:]:
            sol_i = sp.solve_univariate_inequality(iex, x, relational=False)
            solution = sp.Intersection(solution, sol_i)

        solution_str = str(solution)

        steps = [f"不等式组:"]
        for iex in inequalities:
            steps.append(f"  {iex}")
        steps.append(f"解集(交集): {solution_str}")

        return MathObject(
            result=solution_str,
            steps=steps,
            meaning=f"不等式组的解集为 {solution_str}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 一元二次不等式
# ===================================================================


@register(module="algebra", action="solve_quadratic_inequality")
def solve_quadratic_inequality(
    expr: Union[str, sp.Expr], var: str = "x"
) -> MathObject:
    """求解一元二次不等式，利用二次函数图像确定解区间。

    Args:
        expr: 二次不等式，如 "x^2 - 4 > 0"。
        var: 变量名。

    Returns:
        MathObject，result 为解集区间。
    """
    try:
        ex = _to_sympy(expr)
        x = sp.Symbol(var)

        if not isinstance(ex, (sp.StrictGreaterThan, sp.GreaterThan, sp.StrictLessThan, sp.LessThan)):
            return MathObject(error="表达式不是有效的不等式")

        # 获取二次多项式
        poly = sp.expand(ex.lhs - ex.rhs)
        roots = sp.solve(poly, x)
        coeffs = sp.Poly(poly, x).all_coeffs()
        a = float(coeffs[0]) if len(coeffs) == 3 else 0

        solution = sp.solve_univariate_inequality(ex, x, relational=False)
        solution_str = str(solution)

        steps = [
            f"不等式: {ex}",
            f"标准形式: {poly} {'>' if isinstance(ex,sp.StrictGreaterThan) else '≥' if isinstance(ex,sp.GreaterThan) else '<' if isinstance(ex,sp.StrictLessThan) else '≤'} 0",
        ]
        if len(roots) > 0:
            steps.append(f"对应方程根: {[str(r) for r in roots]}")
        if a != 0:
            steps.append(f"二次项系数 a = {a}，抛物线开口{'向上' if a>0 else '向下'}")
        steps.append(f"解集: {solution_str}")

        return MathObject(
            result=solution_str,
            steps=steps,
            meaning=f"利用二次函数图像，{'大于0取x轴上方' if a>0 else '需结合开口方向分析'}，解集为 {solution_str}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 基本不等式
# ===================================================================


@register(module="algebra", action="am_gm_inequality")
def am_gm_inequality(a: Union[int, float], b: Union[int, float]) -> MathObject:
    """算术-几何平均不等式：a + b ≥ 2√(ab)，当且仅当 a=b 时取等。

    Args:
        a: 第一个正数。
        b: 第二个正数。

    Returns:
        MathObject，result 为 (AM, GM, 是否取等)。
    """
    try:
        if a < 0 or b < 0:
            return MathObject(error="AM-GM 不等式要求 a, b ≥ 0")
        am = (a + b) / 2
        gm = (max(a * b, 0)) ** 0.5
        is_equal = abs(am - gm) < 1e-12
        return MathObject(
            result={"AM": am, "GM": gm, "is_equal": is_equal},
            steps=[
                f"已知正数: a={a}, b={b}",
                f"算术平均 AM = (a+b)/2 = ({a}+{b})/2 = {am}",
                f"几何平均 GM = √(ab) = √({a}×{b}) = {gm}",
                f"AM ≥ GM: {am} ≥ {gm} {'✓ 取等' if is_equal else '✓ 严格大于'}",
            ],
            meaning=f"AM-GM: (a+b)/2 ≥ √(ab)，即 {am} ≥ {gm}，{'取等号' if is_equal else '严格大于'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="max_min_initial")
def max_min_initial(a: Union[int, float], b: Union[int, float]) -> MathObject:
    """最值初步：给定两正数，利用基本不等式求最值。

    Args:
        a: 第一个正数。
        b: 第二个正数。

    Returns:
        MathObject，result 包含和的最小值与积的最大值分析。
    """
    try:
        if a < 0 or b < 0:
            return MathObject(error="当前版本仅支持非负数的分析")

        sum_val = a + b
        product_val = a * b
        # 和定→积最大：当 a=b 时积最大 = (sum/2)²
        max_product_with_fixed_sum = (sum_val / 2) ** 2
        # 积定→和最小：当 a=b 时和最小 = 2√(product)
        min_sum_with_fixed_product = 2 * (product_val ** 0.5)

        return MathObject(
            result={
                "a": a,
                "b": b,
                "sum": sum_val,
                "product": product_val,
                "max_product_when_ab_equal": max_product_with_fixed_sum,
                "min_sum_when_ab_equal": min_sum_with_fixed_product,
            },
            steps=[
                f"给定 a={a}, b={b}",
                f"和 = {sum_val}，积 = {product_val}",
                f"若 a = b = {sum_val/2}，积最大 = ({sum_val}/2)² = {max_product_with_fixed_sum}",
                f"若 a = b = √({product_val}) = {product_val**0.5:.2f}，和最小 = 2√({product_val}) = {min_sum_with_fixed_product:.2f}",
            ],
            meaning="利用基本不等式(a+b≥2√ab)：和定积最大，积定和最小",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 inequality 模块。"""
    print("=== inequality self_test ===")

    # 1. inequality_properties
    r = inequality_properties(2, 5, -3)
    assert r.ok, r.error
    print("  inequality_properties: pass")

    # 2. solve_linear_inequality
    r = solve_linear_inequality("2*x - 3 > 0", "x")
    assert r.ok
    print(f"  solve_linear_inequality: {r.result}")

    # 3. solve_inequality_system
    r = solve_inequality_system(["x > 1", "x < 5"], "x")
    assert r.ok
    print(f"  solve_inequality_system: {r.result}")

    # 4. solve_quadratic_inequality
    r = solve_quadratic_inequality("x^2 - 4 > 0", "x")
    assert r.ok
    print(f"  solve_quadratic_inequality: {r.result}")

    # 5. am_gm_inequality
    r = am_gm_inequality(4, 9)
    assert r.ok
    assert r.result["AM"] == 6.5 and abs(r.result["GM"] - 6.0) < 0.01
    print(f"  am_gm_inequality: AM={r.result['AM']}, GM={r.result['GM']}")

    # 6. max_min_initial
    r = max_min_initial(4, 9)
    assert r.ok
    print(f"  max_min_initial: pass")

    print("=== inequality self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
