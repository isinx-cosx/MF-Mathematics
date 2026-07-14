"""导数应用 — 罗尔定理、拉格朗日中值定理、洛必达法则、
单调性、极值与最值、泰勒展开。

依赖: sympy
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_sympy(expr: Union[str, sp.Expr]) -> sp.Expr:
    """将字符串或 sympy 表达式统一转为 sympy 表达式。"""
    if isinstance(expr, sp.Expr):
        return expr
    return sp.sympify(str(expr))


@register(module="calculus", action="rolle_theorem")
def rolle_theorem(
    expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Tuple[float, float] = (0, 1),
) -> MathObject:
    """罗尔定理验证：若 f 在 [a,b] 连续、(a,b) 可导、f(a)=f(b)，则存在 ξ∈(a,b) 使 f'(ξ)=0。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        interval: 闭区间 (a, b)。

    Returns:
        MathObject，result 为满足 f'(ξ)=0 的 ξ 列表。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        a, b = interval

        f_a = float(sp.N(ex.subs(x, a)))
        f_b = float(sp.N(ex.subs(x, b)))
        deriv = sp.diff(ex, x)

        steps = [
            f"f({var}) = {ex}",
            f"区间: [{a}, {b}]",
            f"f({a}) = {f_a}, f({b}) = {f_b}",
        ]

        if abs(f_a - f_b) > 1e-10:
            return MathObject(
                result=[],
                steps=steps + [f"f({a}) ≠ f({b})，罗尔定理条件不满足"],
                meaning="罗尔定理要求 f(a)=f(b)",
            )

        # 求导数零点
        critical = sp.solve(deriv, x)
        valid = []
        for c in critical:
            c_val = float(sp.N(c)) if c.is_real else None
            if c_val is not None and a < c_val < b:
                valid.append(c_val)

        steps.append(f"f'({var}) = {deriv} = 0 的解: {[float(sp.N(c)) for c in critical]}")
        steps.append(f"在 ({a},{b}) 内的解: {valid}")

        return MathObject(
            result=valid,
            steps=steps,
            meaning=f"罗尔定理: 在 ({a},{b}) 内存在 ξ={valid} 使得 f'(ξ)=0" if valid else "罗尔定理条件不满足",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="lagrange_theorem")
def lagrange_theorem(
    expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Tuple[float, float] = (0, 1),
) -> MathObject:
    """拉格朗日中值定理验证：存在 ξ∈(a,b) 使 f'(ξ)=[f(b)-f(a)]/(b-a)。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        interval: 闭区间 (a, b)。

    Returns:
        MathObject，result 为 ξ 值。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        a, b = interval

        f_a = float(sp.N(ex.subs(x, a)))
        f_b = float(sp.N(ex.subs(x, b)))
        secant_slope = (f_b - f_a) / (b - a)
        deriv = sp.diff(ex, x)

        # 解 f'(ξ) = secant_slope
        eq = sp.Eq(deriv, secant_slope)
        solutions = sp.solve(eq, x)
        valid = []
        for s in solutions:
            s_val = float(sp.N(s)) if s.is_real else None
            if s_val is not None and a < s_val < b:
                valid.append(s_val)

        steps = [
            f"f({var}) = {ex}",
            f"区间: [{a}, {b}]",
            f"f({a}) = {f_a}, f({b}) = {f_b}",
            f"割线斜率 = {secant_slope}",
            f"f'({var}) = {deriv}",
            f"解 f'(ξ) = {secant_slope} → ξ = {valid}",
        ]

        return MathObject(
            result=valid[0] if valid else None,
            steps=steps,
            meaning=f"拉格朗日中值定理: 存在 ξ={valid[0]} 使得 f'(ξ)={secant_slope}" if valid else "未找到满足条件的 ξ",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="lhopital")
def lhopital(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
) -> MathObject:
    """洛必达法则求 0/0 或 ∞/∞ 型极限。

    Args:
        expr: 分式表达式，如 "sin(x)/x"。
        var: 自变量名。
        point: 趋近点。

    Returns:
        MathObject，result 为极限值。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)

        # 提取分子分母
        if isinstance(ex, sp.Mul):
            num, den = ex.as_numer_denom()
        else:
            num, den = ex.as_numer_denom()

        # 检查是否为 0/0 或 ∞/∞
        num_limit = sp.limit(num, x, point)
        den_limit = sp.limit(den, x, point)

        steps = [
            f"原式: {ex}",
            f"分子极限: lim num = {num_limit}",
            f"分母极限: lim den = {den_limit}",
        ]

        is_indeterminate = (
            (num_limit == 0 and den_limit == 0)
            or (num_limit in (sp.oo, -sp.oo) and den_limit in (sp.oo, -sp.oo))
        )

        if is_indeterminate:
            steps.append(f"为 {'0/0' if num_limit == 0 else '∞/∞'} 型，应用洛必达法则")
            # 对分子分母分别求导
            num_deriv = sp.diff(num, x)
            den_deriv = sp.diff(den, x)
            steps.append(f"分子求导: {num_deriv}")
            steps.append(f"分母求导: {den_deriv}")
            lhopital_result = sp.limit(num_deriv / den_deriv, x, point)
        else:
            lhopital_result = sp.limit(ex, x, point)
            steps.append("非不定式，直接求极限")

        steps.append(f"结果: {lhopital_result}")

        return MathObject(
            result=str(lhopital_result),
            steps=steps,
            meaning=f"lim_{{{var}→{point}}} {ex} = {lhopital_result}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="monotonicity")
def monotonicity(
    expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Optional[Tuple[float, float]] = None,
) -> MathObject:
    """判断函数单调性。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        interval: 考虑的区间，None 为全体实数。

    Returns:
        MathObject，result 为各区间单调性描述。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        deriv = sp.diff(ex, x)
        simplified_deriv = sp.simplify(deriv)

        # 求导数零点
        critical = sp.solve(simplified_deriv, x)
        real_critical = sorted(
            [float(sp.N(c)) for c in critical if c.is_real],
        )

        # 构建测试区间
        test_points = []
        if real_critical:
            test_points.append(real_critical[0] - 1)
            for i in range(len(real_critical) - 1):
                mid = (real_critical[i] + real_critical[i + 1]) / 2
                test_points.append(mid)
            test_points.append(real_critical[-1] + 1)
        else:
            test_points = [0]

        # 在每个测试点判断导数符号
        intervals_desc = []
        all_intervals = [float("-inf")] + real_critical + [float("inf")]
        for i in range(len(all_intervals) - 1):
            left = all_intervals[i]
            right = all_intervals[i + 1]
            test_pt = (left + right) / 2 if left != float("-inf") and right != float("inf") else (
                right - 1 if right != float("inf") else left + 1
            )
            # 确保测试点在区间内
            if left == float("-inf") and right != float("inf"):
                test_pt_val = right - 1
            elif right == float("inf") and left != float("-inf"):
                test_pt_val = left + 1
            elif left == float("-inf") and right == float("inf"):
                test_pt_val = 0
            else:
                test_pt_val = test_pt

            deriv_val = float(sp.N(simplified_deriv.subs(x, test_pt_val)))
            if deriv_val > 0:
                direction = "单调递增"
            elif deriv_val < 0:
                direction = "单调递减"
            else:
                direction = "常值"

            left_str = f"(-∞" if left == float("-inf") else f"[{left}"
            right_str = "+∞)" if right == float("inf") else f"{right})"
            interval_str = f"{left_str}, {right_str}"
            intervals_desc.append(f"{interval_str}: {direction}")

        steps = [
            f"f({var}) = {ex}",
            f"f'({var}) = {simplified_deriv}",
            f"导数零点: {real_critical}",
        ] + intervals_desc

        return MathObject(
            result=intervals_desc,
            steps=steps,
            meaning=f"函数在各区间的单调性已列出",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="local_extrema")
def local_extrema(
    expr: Union[str, sp.Expr],
    var: str = "x",
) -> MathObject:
    """求函数的局部极值点。

    Args:
        expr: 函数表达式。
        var: 自变量名。

    Returns:
        MathObject，result 为极值点列表。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)

        first_deriv = sp.diff(ex, x)
        second_deriv = sp.diff(first_deriv, x)

        critical = sp.solve(first_deriv, x)
        real_critical = [c for c in critical if c.is_real]

        maxima = []
        minima = []
        inflection = []

        for c in real_critical:
            second_val = float(sp.N(second_deriv.subs(x, c)))
            f_val = float(sp.N(ex.subs(x, c)))
            if second_val < 0:
                maxima.append((float(sp.N(c)), f_val))
            elif second_val > 0:
                minima.append((float(sp.N(c)), f_val))
            else:
                inflection.append((float(sp.N(c)), f_val))

        result_data = {
            "local_maxima": [{"x": round(m[0], 6), "f(x)": round(m[1], 6)} for m in maxima],
            "local_minima": [{"x": round(m[0], 6), "f(x)": round(m[1], 6)} for m in minima],
            "saddle_or_inflection": [{"x": round(m[0], 6), "f(x)": round(m[1], 6)} for m in inflection],
        }

        return MathObject(
            result=result_data,
            steps=[
                f"f({var}) = {ex}",
                f"f'({var}) = {first_deriv}",
                f"f''({var}) = {second_deriv}",
                f"f'({var})=0 的解: {[float(sp.N(c)) for c in real_critical]}",
                f"极大值点: {maxima}",
                f"极小值点: {minima}",
            ],
            meaning=f"局部极值分析完成：{len(maxima)} 个极大值，{len(minima)} 个极小值",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="global_extrema")
def global_extrema(
    expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Tuple[float, float] = (0, 1),
) -> MathObject:
    """求函数在闭区间上的全局最值。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        interval: 闭区间 (a, b)。

    Returns:
        MathObject，result 为 {max, min} 字典。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        a, b = interval

        first_deriv = sp.diff(ex, x)
        critical = sp.solve(first_deriv, x)
        candidates = [a, b]
        for c in critical:
            c_val = float(sp.N(c)) if c.is_real else None
            if c_val is not None and a <= c_val <= b:
                candidates.append(c_val)

        values = []
        for pt in candidates:
            val = float(sp.N(ex.subs(x, pt)))
            values.append((pt, val))

        max_pt, max_val = max(values, key=lambda v: v[1])
        min_pt, min_val = min(values, key=lambda v: v[1])

        return MathObject(
            result={"max": {"x": round(max_pt, 6), "value": round(max_val, 6)},
                     "min": {"x": round(min_pt, 6), "value": round(min_val, 6)}},
            steps=[
                f"f({var}) = {ex}，区间 [{a}, {b}]",
                f"候选点: {candidates}",
                f"函数值: {[(round(p, 4), round(v, 6)) for p, v in values]}",
                f"最大值: f({round(max_pt, 4)}) = {round(max_val, 6)}",
                f"最小值: f({round(min_pt, 4)}) = {round(min_val, 6)}",
            ],
            meaning=f"在 [{a},{b}] 上，最大值 {round(max_val, 6)} 在 x={round(max_pt, 4)}，最小值 {round(min_val, 6)} 在 x={round(min_pt, 4)}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="taylor")
def taylor(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
    order: int = 3,
) -> MathObject:
    """泰勒展开（麦克劳林展开当 point=0）。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 展开点。
        order: 展开阶数。

    Returns:
        MathObject，result 为泰勒多项式。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        series = sp.series(ex, x, point, order + 1).removeO()
        poly = sp.expand(series)

        return MathObject(
            result=str(poly),
            steps=[
                f"f({var}) = {ex}",
                f"在 {var}={point} 处展开至 {order} 阶",
                f"泰勒多项式: {poly}",
            ],
            meaning=f"{ex} 在 {var}={point} 处的 {order} 阶泰勒展开为 {poly}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 derivatives_app 模块。"""
    print("=== derivatives_app self_test ===")

    # 1. rolle_theorem: x(x-1) on [0,1]
    r = rolle_theorem("x*(x-1)", "x", (0, 1))
    assert r.ok, r.error
    print(f"  rolle_theorem(x(x-1)): {r.result}")

    # 2. lagrange_theorem: x^2 on [0,1]
    r = lagrange_theorem("x**2", "x", (0, 1))
    assert r.ok
    print(f"  lagrange_theorem(x^2, [0,1]): {r.result}")

    # 3. lhopital: sin(x)/x → 1
    r = lhopital("sin(x)/x", "x", 0)
    assert r.ok and "1" in r.result
    print(f"  lhopital(sin(x)/x): {r.result}")

    # 4. monotonicity
    r = monotonicity("x**2", "x")
    assert r.ok
    print(f"  monotonicity(x^2): {r.result}")

    # 5. local_extrema: x^2
    r = local_extrema("x**3 - 3*x", "x")
    assert r.ok
    print(f"  local_extrema(x^3-3x): {r.result}")

    # 6. global_extrema: x^2 on [-1,2]
    r = global_extrema("x**2", "x", (-1, 2))
    assert r.ok
    print(f"  global_extrema(x^2, [-1,2]): {r.result}")

    # 7. taylor: sin(x) → x - x^3/6
    r = taylor("sin(x)", "x", 0, 3)
    assert r.ok
    assert "x" in r.result
    print(f"  taylor(sin(x), 3): {r.result}")

    print("=== derivatives_app self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
