"""导数 — 求导（含高阶）、某点导数值、隐函数求导、参数方程求导、微分。

依赖: sympy
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import to_sympy

from typing import Optional, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
@register(module="calculus", action="diff")
def diff(
    expr: Union[str, sp.Expr],
    var: str = "x",
    order: int = 1,
) -> MathObject:
    """求导（支持高阶导数）。

    Args:
        expr: 函数表达式，如 "x**3"。
        var: 自变量名，默认 "x"。
        order: 求导阶数，默认 1。

    Returns:
        MathObject，result 为导数表达式。
    """
    try:
        x = sp.Symbol(var)
        ex = to_sympy(expr)
        result = sp.diff(ex, x, order)
        order_str = f"({order}阶)" if order > 1 else ""
        return MathObject(
            result=str(result),
            steps=[
                f"原函数: f({var}) = {ex}",
                f"求{order_str}导数: f{chr(39)*min(order,3)}{'('+str(order)+')' if order > 2 else ''}({var}) = {result}",
            ],
            meaning=f"d{order_str.replace('(','').replace(')','')}{ex}/d{var}{'^'+str(order) if order > 1 else ''} = {result}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="diff_at")
def diff_at(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
    order: int = 1,
) -> MathObject:
    """在某点求导数值。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 求导点。
        order: 阶数，默认 1。

    Returns:
        MathObject，result 为导数值。
    """
    try:
        x = sp.Symbol(var)
        ex = to_sympy(expr)
        deriv = sp.diff(ex, x, order)
        value = sp.N(deriv.subs(x, point))
        order_str = f"({order}阶)" if order > 1 else ""
        return MathObject(
            result=float(value),
            steps=[
                f"原函数: f({var}) = {ex}",
                f"求{order_str}导数: f'{chr(39)*min(order,3)}({var}) = {deriv}",
                f"代入 {var} = {point}: f'{chr(39)*min(order,3)}({point}) = {value}",
            ],
            meaning=f"函数在 {var}={point} 处的{order_str}导数值为 {value}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="implicit_diff")
def implicit_diff(
    eq: Union[str, sp.Expr],
    var: str = "x",
    dep_var: str = "y",
) -> MathObject:
    """隐函数求导 dy/dx。

    对形如 F(x, y) = 0 的方程，求 dy/dx = -F_x / F_y。

    Args:
        eq: 隐函数方程，如 "x**2 + y**2 - 1"（表示 x²+y²=1）。
        var: 自变量名，默认 "x"。
        dep_var: 因变量名，默认 "y"。

    Returns:
        MathObject，result 为 dy/dx 表达式。
    """
    try:
        x = sp.Symbol(var)
        y = sp.Function(dep_var)(x)
        ex = to_sympy(eq)
        # 用符号 y_sym 替换 y，然后求偏导
        y_sym = sp.Symbol(dep_var)
        ex_sym = ex
        if isinstance(ex, sp.Expr):
            ex_sym = ex.subs(y, y_sym)

        F_x = sp.diff(ex_sym, x)
        F_y = sp.diff(ex_sym, y_sym)

        if F_y == 0:
            return MathObject(
                result="无法求解",
                steps=[f"F(x,{dep_var}) = {ex_sym}", f"∂F/∂{var} = {F_x}", f"∂F/∂{dep_var} = {F_y} = 0，无法求解"],
                meaning="隐函数定理不适用（F_y=0）",
            )

        dydx = -F_x / F_y
        dydx_simplified = sp.simplify(dydx)

        return MathObject(
            result=str(dydx_simplified),
            steps=[
                f"隐函数方程: F({var},{dep_var}) = {ex_sym} = 0",
                f"∂F/∂{var} = {F_x}",
                f"∂F/∂{dep_var} = {F_y}",
                f"d{dep_var}/d{var} = -(∂F/∂{var})/(∂F/∂{dep_var}) = {dydx_simplified}",
            ],
            meaning=f"隐函数求导: d{dep_var}/d{var} = {dydx_simplified}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="parametric_diff")
def parametric_diff(
    x_expr: Union[str, sp.Expr],
    y_expr: Union[str, sp.Expr],
    t: str = "t",
) -> MathObject:
    """参数方程求导 dy/dx。

    给定 x = x(t), y = y(t)，求 dy/dx = (dy/dt) / (dx/dt)。

    Args:
        x_expr: x 关于 t 的表达式。
        y_expr: y 关于 t 的表达式。
        t: 参数名，默认 "t"。

    Returns:
        MathObject，result 为 dy/dx 表达式。
    """
    try:
        t_sym = sp.Symbol(t)
        x_ex = to_sympy(x_expr)
        y_ex = to_sympy(y_expr)

        dx_dt = sp.diff(x_ex, t_sym)
        dy_dt = sp.diff(y_ex, t_sym)

        if dx_dt == 0:
            return MathObject(
                result="无穷大（切线垂直）",
                steps=[
                    f"x({t}) = {x_ex}, y({t}) = {y_ex}",
                    f"dx/d{t} = {dx_dt} = 0",
                    f"切线垂直于 x 轴",
                ],
                meaning="dx/dt=0，导数不存在",
            )

        dydx = sp.simplify(dy_dt / dx_dt)

        return MathObject(
            result=str(dydx),
            steps=[
                f"参数方程: x({t}) = {x_ex}, y({t}) = {y_ex}",
                f"dx/d{t} = {dx_dt}",
                f"dy/d{t} = {dy_dt}",
                f"dy/dx = (dy/d{t})/(dx/d{t}) = {dydx}",
            ],
            meaning=f"参数方程求导: dy/dx = {dydx}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="differential")
def differential(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
    dx: float = 0.01,
) -> MathObject:
    """计算微分 dy = f'(x) dx。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 计算点。
        dx: 自变量增量，默认 0.01。

    Returns:
        MathObject，result 为 dy 数值。
    """
    try:
        x = sp.Symbol(var)
        ex = to_sympy(expr)
        deriv = sp.diff(ex, x)
        deriv_at = float(sp.N(deriv.subs(x, point)))
        dy = deriv_at * dx

        return MathObject(
            result=dy,
            steps=[
                f"原函数: f({var}) = {ex}",
                f"导数: f'({var}) = {deriv}",
                f"在 {var}={point} 处: f'({point}) = {deriv_at}",
                f"dy = f'({point}) · dx = {deriv_at} × {dx} = {dy}",
            ],
            meaning=f"当 {var} 从 {point} 变化 {dx} 时，函数的近似变化量 dy = {dy}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 derivatives 模块。"""
    print("=== derivatives self_test ===")

    # 1. diff: x^3 → 3*x^2
    r = diff("x**3", "x")
    assert r.ok, r.error
    assert "3" in r.result and "x" in r.result
    print(f"  diff(x^3): {r.result}")
    print("  diff: pass")

    # 2. diff second order: x^3 → 6*x
    r = diff("x**3", "x", order=2)
    assert r.ok and "6" in r.result
    print(f"  diff(x^3, order=2): {r.result}")

    # 3. diff_at: x^3 at x=2
    r = diff_at("x**3", "x", 2)
    assert r.ok and abs(float(r.result) - 12.0) < 1e-9
    print(f"  diff_at(x^3, 2): {r.result}")

    # 4. implicit_diff: x^2 + y^2 = 1 → -x/y
    r = implicit_diff("x**2 + y**2 - 1", "x", "y")
    assert r.ok
    print(f"  implicit_diff(x^2+y^2=1): {r.result}")

    # 5. parametric_diff: x=t^2, y=t^3 → (3t)/(2t) = 3t/2
    r = parametric_diff("t**2", "t**3", "t")
    assert r.ok
    print(f"  parametric_diff: {r.result}")

    # 6. differential
    r = differential("x**2", "x", 3, 0.1)
    assert r.ok
    print(f"  differential(x^2, x=3, dx=0.1): {r.result}")

    print("=== derivatives self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
