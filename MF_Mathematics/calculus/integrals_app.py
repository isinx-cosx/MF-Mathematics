"""积分应用 — 面积、旋转体体积（圆盘法/壳法）、弧长。

依赖: sympy
"""

from __future__ import annotations

from typing import Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_sympy(expr: Union[str, sp.Expr]) -> sp.Expr:
    """将字符串或 sympy 表达式统一转为 sympy 表达式。"""
    if isinstance(expr, sp.Expr):
        return expr
    return sp.sympify(str(expr))


@register(module="calculus", action="area_between")
def area_between(
    expr1: Union[str, sp.Expr],
    expr2: Union[str, sp.Expr],
    var: str = "x",
    a: Union[str, float, int] = 0,
    b: Union[str, float, int] = 1,
) -> MathObject:
    """计算两曲线之间的面积：∫ |f(x) - g(x)| dx。

    Args:
        expr1: 曲线1（上方或下方）。
        expr2: 曲线2。
        var: 自变量名。
        a: 积分下限。
        b: 积分上限。

    Returns:
        MathObject，result 为面积值。
    """
    try:
        x = sp.Symbol(var)
        f = _to_sympy(expr1)
        g = _to_sympy(expr2)

        # 计算定积分
        diff = f - g
        area = sp.integrate(sp.Abs(diff), (x, a, b))

        # 尝试数值
        try:
            numeric_val = float(sp.N(area))
            # 精确值简化
            exact = sp.nsimplify(numeric_val, [sp.sqrt(2), sp.sqrt(3), sp.pi])
            result_str = str(exact)
            if abs(float(exact) - numeric_val) > 1e-10:
                result_str = f"{result_str} ≈ {numeric_val}"
        except Exception:
            result_str = str(area)

        return MathObject(
            result=result_str,
            steps=[
                f"曲线1: y = {f}",
                f"曲线2: y = {g}",
                f"差函数: |f-g| = |{diff}|",
                f"面积 = ∫_{{{a}}}^{{{b}}} |{diff}| d{var}",
                f"结果: {area}",
            ],
            meaning=f"y={f} 与 y={g} 在 [{a},{b}] 之间的面积 = {area}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="volume_disk")
def volume_disk(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: Union[str, float, int] = 0,
    b: Union[str, float, int] = 1,
    axis: str = "x",
) -> MathObject:
    """旋转体体积（圆盘法）：V = π ∫ [f(x)]² dx。

    Args:
        expr: 绕轴旋转的函数表达式。
        var: 自变量名。
        a: 积分下限。
        b: 积分上限。
        axis: 旋转轴，默认 "x"（绕 x 轴）。

    Returns:
        MathObject，result 为体积值。
    """
    try:
        x = sp.Symbol(var)
        f = _to_sympy(expr)

        if axis == "x":
            integrand = sp.pi * f**2
        elif axis == "y":
            # 绕 y 轴旋转: x = g(y), V = pi ∫ g(y)^2 dy
            integrand = sp.pi * f**2
        else:
            return MathObject(error=f"不支持的旋转轴 '{axis}'，仅支持 'x' 或 'y'")

        volume = sp.integrate(integrand, (x, a, b))

        try:
            numeric_val = float(sp.N(volume))
            exact = sp.nsimplify(numeric_val, [sp.sqrt(2), sp.sqrt(3), sp.pi])
            result_str = str(exact)
            if abs(float(exact) - numeric_val) > 1e-10:
                result_str = f"{result_str} ≈ {numeric_val}"
        except Exception:
            result_str = str(volume)

        return MathObject(
            result=result_str,
            steps=[
                f"曲线: y = {f}，绕 {axis} 轴旋转",
                f"截面半径: r({var}) = {f}",
                f"体积元: dV = π · [{f}]² d{var}",
                f"V = π · ∫_{{{a}}}^{{{b}}} [{f}]² d{var}",
                f"结果: {volume}",
            ],
            meaning=f"y={f} 绕 {axis} 轴旋转，[{a},{b}] 上的体积 = {volume}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="volume_shell")
def volume_shell(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: Union[str, float, int] = 0,
    b: Union[str, float, int] = 1,
) -> MathObject:
    """旋转体体积（壳法/柱壳法）：V = 2π ∫ x·f(x) dx（绕 y 轴）。

    Args:
        expr: 被旋转的函数表达式。
        var: 自变量名。
        a: 积分下限。
        b: 积分上限。

    Returns:
        MathObject，result 为体积值。
    """
    try:
        x = sp.Symbol(var)
        f = _to_sympy(expr)

        integrand = 2 * sp.pi * x * f
        volume = sp.integrate(integrand, (x, a, b))

        try:
            numeric_val = float(sp.N(volume))
            exact = sp.nsimplify(numeric_val, [sp.sqrt(2), sp.sqrt(3), sp.pi])
            result_str = str(exact)
            if abs(float(exact) - numeric_val) > 1e-10:
                result_str = f"{result_str} ≈ {numeric_val}"
        except Exception:
            result_str = str(volume)

        return MathObject(
            result=result_str,
            steps=[
                f"曲线: y = {f}，绕 y 轴旋转（壳法）",
                f"壳半径: r = {var}",
                f"壳高: h = {f}",
                f"体积元: dV = 2π · {var} · {f} d{var}",
                f"V = 2π · ∫_{{{a}}}^{{{b}}} {var}·{f} d{var}",
                f"结果: {volume}",
            ],
            meaning=f"y={f} 绕 y 轴旋转，[{a},{b}] 上的体积 = {volume}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="arc_length")
def arc_length(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: Union[str, float, int] = 0,
    b: Union[str, float, int] = 1,
) -> MathObject:
    """计算曲线弧长：L = ∫ √(1 + [f'(x)]²) dx。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        a: 区间起点。
        b: 区间终点。

    Returns:
        MathObject，result 为弧长值。
    """
    try:
        x = sp.Symbol(var)
        f = _to_sympy(expr)
        deriv = sp.diff(f, x)
        integrand = sp.sqrt(1 + deriv**2)

        # 先尝试符号积分
        try:
            length = sp.integrate(integrand, (x, a, b))
            if length.has(sp.Integral):
                # 符号积分未成功，回退数值
                length = sp.N(sp.integrate(integrand, (x, a, b)))
        except Exception:
            length = sp.N(sp.integrate(integrand, (x, a, b)))

        try:
            numeric_val = float(sp.N(length))
            exact = sp.nsimplify(numeric_val, [sp.sqrt(2), sp.sqrt(3), sp.pi])
            result_str = str(exact)
            if abs(float(exact) - numeric_val) > 1e-10:
                result_str = f"{result_str} ≈ {numeric_val}"
        except Exception:
            result_str = str(length)

        return MathObject(
            result=result_str,
            steps=[
                f"曲线: y = {f}",
                f"导数: dy/d{var} = {deriv}",
                f"弧长微元: ds = √(1 + [{deriv}]²) d{var}",
                f"弧长 = ∫_{{{a}}}^{{{b}}} √(1+[{deriv}]²) d{var}",
                f"结果: {length}",
            ],
            meaning=f"y={f} 在 [{a},{b}] 上的弧长 = {length}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 integrals_app 模块。"""
    print("=== integrals_app self_test ===")

    # 1. area_between: sin(x) vs cos(x), [0, pi/4]
    r = area_between("sin(x)", "cos(x)", "x", 0, "pi/4")
    assert r.ok, r.error
    print(f"  area_between(sin,cos,[0,pi/4]): {r.result}")
    print("  area_between: pass")

    # 2. volume_disk: x from 0 to 1 → π/3
    r = volume_disk("x", "x", 0, 1)
    assert r.ok
    print(f"  volume_disk(x, 0, 1): {r.result}")

    # 3. volume_shell: x from 0 to 1 → 2π/3
    r = volume_shell("x", "x", 0, 1)
    assert r.ok
    print(f"  volume_shell(x, 0, 1): {r.result}")

    # 4. arc_length: x from 0 to 1 → √2
    r = arc_length("x", "x", 0, 1)
    assert r.ok
    print(f"  arc_length(x, 0, 1): {r.result}")

    print("=== integrals_app self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
