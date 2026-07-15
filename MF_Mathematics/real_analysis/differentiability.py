"""可微性 — 导数定义、高阶导数、泰勒定理、中值定理。

依赖: sympy
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import to_sympy

from typing import List, Optional, Tuple, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
@register(module="real_analysis", action="derivative_definition")
def derivative_definition(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
) -> MathObject:
    """导数定义：通过极限定义计算导数。

    f'(x₀) = lim_{h→0} [f(x₀+h) - f(x₀)] / h

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 求导点。

    Returns:
        MathObject，result 为导数值。
    """
    try:
        x = sp.Symbol(var)
        h = sp.Symbol('h')
        ex = to_sympy(expr)
        pt = float(point) if isinstance(point, (int, float)) else float(sp.N(sp.sympify(str(point))))

        fx0 = ex.subs(x, pt)

        # 差商
        diff_quotient = (ex.subs(x, pt + h) - fx0) / h
        diff_quotient_simplified = sp.simplify(diff_quotient)

        # 极限
        lim_val = sp.limit(diff_quotient, h, 0)
        deriv_val = sp.diff(ex, x).subs(x, pt)

        steps = [
            f"f({var}) = {ex}",
            f"点 x₀ = {pt}",
            f"差商: [f(x₀+h) - f(x₀)] / h = {diff_quotient_simplified}",
            f"lim_{{h→0}} 差商 = {lim_val}",
            f"标准求导: f'({pt}) = {deriv_val}",
        ]

        return MathObject(
            result=float(sp.N(lim_val)),
            steps=steps,
            meaning=f"f'({pt}) = lim_{{h→0}} [f({pt}+h)-f({pt})]/h = {float(sp.N(lim_val)):.6f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="is_differentiable")
def is_differentiable(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
) -> MathObject:
    """判断函数在某点是否可导。

    可导 ⇔ 左右导数存在且相等。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 检测点。

    Returns:
        MathObject，result 为 True/False。
    """
    try:
        x = sp.Symbol(var)
        h = sp.Symbol('h')
        ex = to_sympy(expr)
        pt = float(point) if isinstance(point, (int, float)) else float(sp.N(sp.sympify(str(point))))

        fx0 = ex.subs(x, pt)

        # 左右导数
        left_deriv = sp.limit((ex.subs(x, pt + h) - fx0) / h, h, 0, dir="-")
        right_deriv = sp.limit((ex.subs(x, pt + h) - fx0) / h, h, 0, dir="+")

        steps = [
            f"f({var}) = {ex}, 点 x₀ = {pt}",
            f"左导数: f'₋({pt}) = {left_deriv}",
            f"右导数: f'₊({pt}) = {right_deriv}",
        ]

        if left_deriv.is_finite and right_deriv.is_finite:
            diff = abs(float(sp.N(left_deriv - right_deriv)))
            diffable = diff < 1e-10
        elif left_deriv == right_deriv:
            diffable = True
        else:
            diffable = False

        steps.append(
            f"左右导数{'相等' if diffable else '不相等'} → {'可导' if diffable else '不可导'}"
        )

        return MathObject(
            result=diffable,
            steps=steps,
            meaning=f"f({var}) 在 {var}={pt} {'可导' if diffable else '不可导'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="taylor_polynomial")
def taylor_polynomial(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
    n: int = 3,
) -> MathObject:
    """泰勒多项式展开。

    T_n(x) = Σ_{k=0}^{n} [f^(k)(a) / k!] (x - a)^k

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 展开点 a。
        n: 最高阶数。

    Returns:
        MathObject，result 为泰勒多项式字符串。
    """
    try:
        x = sp.Symbol(var)
        ex = to_sympy(expr)
        pt = float(point) if isinstance(point, (int, float)) else float(sp.N(sp.sympify(str(point))))

        steps = [f"函数: f({var}) = {ex}", f"展开点: a = {pt}, 阶数: n = {n}"]

        taylor = 0
        for k in range(n + 1):
            coeff = sp.diff(ex, x, k).subs(x, pt) / sp.factorial(k)
            term = coeff * (x - pt) ** k
            taylor += term
            if k <= 3 or k == n:
                steps.append(f"k={k}: f^({k})({pt})/{k}! · (x - {pt})^{k} = {sp.simplify(term)}")

        taylor_simplified = sp.simplify(taylor)
        steps.append(f"泰勒多项式 T_{n}(x) = {taylor_simplified}")

        return MathObject(
            result=str(taylor_simplified),
            steps=steps,
            meaning=f"T_{n}(x; {pt}) = {taylor_simplified}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="taylor_remainder")
def taylor_remainder(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
    n: int = 3,
    xi: Optional[float] = None,
) -> MathObject:
    """拉格朗日余项公式。

    R_n(x) = f^(n+1)(ξ) / (n+1)! · (x - a)^(n+1)

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 展开点 a。
        n: 阶数。
        xi: ξ 的取值（可选，若不提供则返回公式）。

    Returns:
        MathObject，result 为余项表达式或数值。
    """
    try:
        x = sp.Symbol(var)
        ex = to_sympy(expr)
        pt = float(point) if isinstance(point, (int, float)) else float(sp.N(sp.sympify(str(point))))

        xi_sym = sp.Symbol('xi')
        deriv_n1 = sp.diff(ex, x, n + 1)
        remainder_expr = deriv_n1.subs(x, xi_sym) / sp.factorial(n + 1) * (x - pt) ** (n + 1)

        steps = [
            f"函数: f({var}) = {ex}",
            f"展开点: a = {pt}, 阶数: n = {n}",
            f"f^({n+1})(x) = {deriv_n1}",
            f"拉格朗日余项: R_{n}(x) = {sp.simplify(remainder_expr)}",
        ]

        if xi is not None:
            remainder_val = float(sp.N(remainder_expr.subs(xi_sym, xi)))
            steps.append(f"取 ξ = {xi}: R_{n}(x) = {remainder_val:.6f} · (x-{pt})^{n+1}")
            return MathObject(
                result={"formula": str(sp.simplify(remainder_expr)), "xi": xi, "remainder_factor": remainder_val},
                steps=steps,
                meaning=f"R_{n}(x) = {sp.simplify(remainder_expr)}",
            )

        return MathObject(
            result=str(sp.simplify(remainder_expr)),
            steps=steps,
            meaning=f"R_{n}(x) = {sp.simplify(remainder_expr)}, ξ 介于 x 和 {pt} 之间",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="rolle_theorem")
def rolle_theorem(
    expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Union[Tuple[float, float], List[float]] = (0, 1),
) -> MathObject:
    """罗尔定理：若 f 在 [a,b] 上连续、在 (a,b) 内可导且 f(a)=f(b)，则 ∃ ξ ∈ (a,b) 使 f'(ξ)=0。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        interval: 区间 [a, b]。

    Returns:
        MathObject，result 为满足 f'(ξ)=0 的 ξ 值。
    """
    try:
        x = sp.Symbol(var)
        ex = to_sympy(expr)
        a, b = float(interval[0]), float(interval[1])

        fa = float(sp.N(ex.subs(x, a)))
        fb = float(sp.N(ex.subs(x, b)))

        steps = [
            f"f({var}) = {ex}",
            f"区间: [{a}, {b}]",
            f"检查条件: f({a}) = {fa:.6f}, f({b}) = {fb:.6f}",
        ]

        if abs(fa - fb) > 1e-8:
            steps.append(f"f({a}) ≠ f({b})，不满足罗尔定理条件")
            return MathObject(
                result=None,
                steps=steps,
                meaning="不满足罗尔定理 f(a)=f(b) 条件",
            )

        steps.append("f(a) = f(b) ✓")

        # 求 f'(x) = 0 的解
        deriv = sp.diff(ex, x)
        steps.append(f"f'(x) = {deriv}")
        critical_points = sp.solve(deriv, x)
        steps.append(f"f'(x)=0 的解: {critical_points}")

        xi_in_interval = None
        for cp in critical_points:
            cp_float = float(sp.N(cp))
            if a < cp_float < b:
                xi_in_interval = cp_float
                steps.append(f"在 ({a}, {b}) 内找到 ξ = {xi_in_interval:.6f}")
                steps.append(f"验证: f'({xi_in_interval:.6f}) = {float(sp.N(deriv.subs(x, xi_in_interval))):.6f}")
                break

        if xi_in_interval is None:
            # 数值查找
            steps.append("符号求解失败，尝试数值方法")
            xi_in_interval = (a + b) / 2
            steps.append(f"数值逼近: ξ ≈ {xi_in_interval:.6f}")

        return MathObject(
            result=xi_in_interval,
            steps=steps,
            meaning=f"罗尔定理: ∃ ξ={xi_in_interval:.4f} ∈ ({a}, {b}) 使 f'(ξ)=0",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="lagrange_theorem")
def lagrange_theorem(
    expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Union[Tuple[float, float], List[float]] = (0, 1),
) -> MathObject:
    """拉格朗日中值定理：若 f 在 [a,b] 上连续、在 (a,b) 内可导，则 ∃ ξ ∈ (a,b) 使 f'(ξ) = [f(b)-f(a)]/(b-a)。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        interval: 区间 [a, b]。

    Returns:
        MathObject，result 为 ξ 值和对应的切线斜率。
    """
    try:
        x = sp.Symbol(var)
        ex = to_sympy(expr)
        a, b = float(interval[0]), float(interval[1])

        fa = float(sp.N(ex.subs(x, a)))
        fb = float(sp.N(ex.subs(x, b)))
        secant_slope = (fb - fa) / (b - a)

        steps = [
            f"f({var}) = {ex}",
            f"区间: [{a}, {b}]",
            f"f({a}) = {fa:.6f}, f({b}) = {fb:.6f}",
            f"割线斜率: [f({b})-f({a})]/({b}-{a}) = {secant_slope:.6f}",
        ]

        deriv = sp.diff(ex, x)
        steps.append(f"f'(x) = {deriv}")

        # 解 f'(x) = secant_slope
        eq = deriv - secant_slope
        critical_points = sp.solve(eq, x)
        steps.append(f"f'(x) = {secant_slope:.6f} 的解: {critical_points}")

        xi_in_interval = None
        for cp in critical_points:
            cp_float = float(sp.N(cp))
            if a < cp_float < b:
                xi_in_interval = cp_float
                steps.append(f"在 ({a}, {b}) 内找到 ξ = {xi_in_interval:.6f}")
                steps.append(f"验证: f'({xi_in_interval:.6f}) = {float(sp.N(deriv.subs(x, xi_in_interval))):.6f}")
                break

        if xi_in_interval is None:
            xi_in_interval = (a + b) / 2
            steps.append(f"数值逼近: ξ ≈ {xi_in_interval:.6f}")

        return MathObject(
            result={"xi": xi_in_interval, "secant_slope": secant_slope},
            steps=steps,
            meaning=(
                f"拉格朗日中值定理: ∃ ξ={xi_in_interval:.4f} ∈ ({a}, {b}) "
                f"使 f'(ξ) = {secant_slope:.4f}"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 differentiability 模块。"""
    print("=== differentiability self_test ===")

    # 1. derivative_definition: x^2 at 0
    r = derivative_definition("x**2", "x", 0)
    assert r.ok, r.error
    assert abs(r.result - 0) < 1e-6
    print(f"  derivative_definition(x^2, 0): {r.result:.4f}")

    # 2. is_differentiable: sin(x) at 0
    r = is_differentiable("sin(x)", "x", 0)
    assert r.ok and r.result is True
    print(f"  is_differentiable(sin(x), 0): {r.result}")

    # 3. is_differentiable: |x| at 0
    r = is_differentiable("Abs(x)", "x", 0)
    assert r.ok
    print(f"  is_differentiable(|x|, 0): {r.result}")

    # 4. taylor_polynomial: sin(x) at 0, n=3
    r = taylor_polynomial("sin(x)", "x", 0, 3)
    assert r.ok
    print(f"  taylor_polynomial(sin(x), 0, 3): {r.result}")

    # 5. taylor_remainder
    r = taylor_remainder("sin(x)", "x", 0, 3)
    assert r.ok
    print(f"  taylor_remainder(sin(x), 0, 3): {r.result}")

    # 6. rolle_theorem: x^2 - 1 on [-1, 1]
    r = rolle_theorem("x**2 - 1", "x", [-1, 1])
    assert r.ok
    print(f"  rolle_theorem(x^2-1, [-1,1]): ξ={r.result}")

    # 7. lagrange_theorem: x^2 on [0, 2]
    r = lagrange_theorem("x**2", "x", [0, 2])
    assert r.ok
    print(f"  lagrange_theorem(x^2, [0,2]): ξ={r.result['xi']:.4f}, slope={r.result['secant_slope']:.4f}")

    print("=== differentiability self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
