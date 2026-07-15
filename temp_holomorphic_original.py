"""全纯函数 — C-R方程、调和函数。

依赖: sympy
"""

from __future__ import annotations

from typing import Any, Tuple, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


# ── 工具 ───────────────────────────────────────────────────────────────

def _parse_func(func: Any, var: Any = None):
    """解析函数表达式，返回 sympy 表达式和变量。"""
    if isinstance(func, str):
        expr = sp.sympify(func)
    else:
        expr = func
    if var is None:
        # 尝试自动检测变量
        if hasattr(expr, 'free_symbols'):
            syms = list(expr.free_symbols)
            if len(syms) == 1:
                var = syms[0]
            else:
                var = sp.Symbol('z')
    elif isinstance(var, str):
        var = sp.Symbol(var)
    return expr, var


# ── 公开函数 ──────────────────────────────────────────────────────────


@register(module="complex_analysis", action="is_holomorphic")
def is_holomorphic(
    func: Any,
    z: Any,
) -> MathObject:
    """在一点检查是否全纯（C-R方程 + 实可微）。

    若 f(z) = u(x,y) + i v(x,y)，在点 z₀ 满足 C-R 方程：
    u_x = v_y, u_y = -v_x，且 u, v 实可微，则全纯。

    对 sympy 符号表达式：用 sp.diff 计算偏导并验证 C-R 方程。

    Args:
        func: 复函数，sympy 表达式或字符串（如 "sin(z)"）。
        z: 复变量名或 sympy Symbol。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        expr, z_var = _parse_func(func, z)

        # 引入实部和虚部符号
        x = sp.Symbol('x', real=True)
        y = sp.Symbol('y', real=True)

        if z_var != sp.Symbol('z'):
            # 若用户传入的变量不是 z，尝试用 z 替代
            if str(z_var) != 'z':
                z_var = sp.Symbol('z')

        # 用 z 替换为 x + iy
        expr_xy = expr.subs(z_var, x + sp.I * y)
        # 分离实部和虚部
        u_expr = sp.simplify(sp.re(expr_xy))
        v_expr = sp.simplify(sp.im(expr_xy))

        # 计算偏导数
        u_x = sp.simplify(sp.diff(u_expr, x))
        u_y = sp.simplify(sp.diff(u_expr, y))
        v_x = sp.simplify(sp.diff(v_expr, x))
        v_y = sp.simplify(sp.diff(v_expr, y))

        # C-R 方程
        cr1 = sp.simplify(u_x - v_y)
        cr2 = sp.simplify(u_y + v_x)

        holomorphic = cr1 == 0 and cr2 == 0

        steps = [
            f"f(z) = {expr}",
            f"令 z = x + iy: f = {u_expr} + ({v_expr}) i",
            f"u(x,y) = {u_expr}",
            f"v(x,y) = {v_expr}",
            f"∂u/∂x = {u_x}, ∂v/∂y = {v_y}",
            f"∂u/∂y = {u_y}, ∂v/∂x = {v_x}",
            f"u_x - v_y = {cr1} {'✓' if cr1 == 0 else '✗'}",
            f"u_y + v_x = {cr2} {'✓' if cr2 == 0 else '✗'}",
            f"C-R 方程{'成立' if holomorphic else '不成立'} → {'全纯' if holomorphic else '非全纯'}",
        ]

        return MathObject(
            result=holomorphic,
            steps=steps,
            meaning="f 在区域上全纯 ⇔ 实部与虚部满足 C-R 方程且实可微。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="cauchy_riemann")
def cauchy_riemann(
    u: Any,
    v: Any,
    x: Any = None,
    y: Any = None,
) -> MathObject:
    """显式验证 C-R 方程组。

    给定 u(x,y), v(x,y)，验证 ∂u/∂x = ∂v/∂y 和 ∂u/∂y = -∂v/∂x。

    Args:
        u: 实部表达式。
        v: 虚部表达式。
        x: 实变量符号（默认 Symbol('x')）。
        y: 虚变量符号（默认 Symbol('y')）。

    Returns:
        MathObject，result 为 dict {cr1: bool, cr2: bool, both: bool}。
    """
    try:
        if x is None:
            x = sp.Symbol('x', real=True)
        elif isinstance(x, str):
            x = sp.Symbol(x, real=True)
        if y is None:
            y = sp.Symbol('y', real=True)
        elif isinstance(y, str):
            y = sp.Symbol(y, real=True)

        u_expr_raw = sp.sympify(u) if isinstance(u, str) else u
        v_expr_raw = sp.sympify(v) if isinstance(v, str) else v
        # 替换默认符号
        x_default = sp.Symbol('x')
        y_default = sp.Symbol('y')
        u_expr = u_expr_raw.subs({x_default: x, y_default: y})
        v_expr = v_expr_raw.subs({x_default: x, y_default: y})

        u_x = sp.simplify(sp.diff(u_expr, x))
        u_y = sp.simplify(sp.diff(u_expr, y))
        v_x = sp.simplify(sp.diff(v_expr, x))
        v_y = sp.simplify(sp.diff(v_expr, y))

        cr1 = sp.simplify(u_x - v_y) == 0
        cr2 = sp.simplify(u_y + v_x) == 0
        both = cr1 and cr2

        result = {
            "u_x": str(u_x),
            "v_y": str(v_y),
            "cr1 (u_x = v_y)": cr1,
            "u_y": str(u_y),
            "v_x": str(v_x),
            "cr2 (u_y = -v_x)": cr2,
            "both_hold": both,
        }

        steps = [
            f"u(x,y) = {u_expr}",
            f"v(x,y) = {v_expr}",
            f"∂u/∂x = {u_x},  ∂v/∂y = {v_y}  → cr1: {cr1}",
            f"∂u/∂y = {u_y},  ∂v/∂x = {v_x}  → cr2: {cr2}",
            f"全部满足: {both}",
        ]

        return MathObject(
            result=result,
            steps=steps,
            meaning="C-R 方程是全纯的必要条件。若 u,v ∈ C¹ 且 C-R 成立，则 f = u+iv 全纯。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="is_harmonic")
def is_harmonic(
    func: Any,
    x: Any = None,
    y: Any = None,
) -> MathObject:
    """判断是否为调和函数（Δu = 0）。

    对函数 u(x,y) 计算拉普拉斯算子 Δu = ∂²u/∂x² + ∂²u/∂y²，
    若恒为零则为调和函数。全纯函数的实部和虚部都是调和函数。

    Args:
        func: 实函数表达式。
        x, y: 变量符号。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        if x is None:
            x = sp.Symbol('x', real=True)
        elif isinstance(x, str):
            x = sp.Symbol(x, real=True)
        if y is None:
            y = sp.Symbol('y', real=True)
        elif isinstance(y, str):
            y = sp.Symbol(y, real=True)

        expr_raw = sp.sympify(func) if isinstance(func, str) else func
        # 替换 sympify 产生的默认符号为带 real=True 的符号
        x_default = sp.Symbol('x')
        y_default = sp.Symbol('y')
        expr = expr_raw.subs({x_default: x, y_default: y})

        u_xx = sp.simplify(sp.diff(expr, x, 2))
        u_yy = sp.simplify(sp.diff(expr, y, 2))
        laplacian = sp.simplify(u_xx + u_yy)

        harmonic = laplacian == 0

        steps = [
            f"u(x,y) = {expr}",
            f"∂²u/∂x² = {u_xx}",
            f"∂²u/∂y² = {u_yy}",
            f"Δu = ∂²u/∂x² + ∂²u/∂y² = {laplacian}",
            f"{'是' if harmonic else '不是'}调和函数 (Δu = 0: {harmonic})",
        ]

        return MathObject(
            result=harmonic,
            steps=steps,
            meaning="调和函数满足拉普拉斯方程 Δu = 0。全纯函数的实部与虚部互为共轭调和函数。",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ── self_test ──────────────────────────────────────────────────────────

def self_test() -> None:
    """自测：全纯函数。"""
    print("=== holomorphic self_test ===")

    # 1. is_holomorphic: f(z) = sin(z) 应全纯
    r = is_holomorphic("sin(z)", "z")
    assert r.ok, r.error
    assert r.result is True, f"sin(z) 应全纯: {r.result}"
    print(f"  is_holomorphic(sin(z)): {r.result}")

    # 2. is_holomorphic: f(z) = conj(z) 应非全纯
    r = is_holomorphic("conjugate(z)", "z")
    assert r.ok, r.error
    # 复共轭不满足 C-R 方程
    assert r.result is False, f"conj(z) 应非全纯: {r.result}"
    print(f"  is_holomorphic(conjugate(z)): {r.result}")

    # 3. cauchy_riemann: u=x^2-y^2, v=2xy (即 f(z)=z^2)
    x = sp.Symbol('x', real=True)
    y = sp.Symbol('y', real=True)
    r = cauchy_riemann(x**2 - y**2, 2*x*y, x, y)
    assert r.ok, r.error
    assert r.result["both_hold"] is True
    print(f"  cauchy_riemann(u=x²-y², v=2xy): {r.result['both_hold']}")

    # 4. is_harmonic: u = x^2 - y^2 是调和函数
    r = is_harmonic(x**2 - y**2, x, y)
    assert r.ok, r.error
    assert r.result is True, f"x²-y² 应是调和函数: {r.result}"
    print(f"  is_harmonic(x²-y²): {r.result}")

    # 5. is_harmonic: u = x^2 + y^2 不是调和函数（Δu=4）
    r = is_harmonic(x**2 + y**2, x, y)
    assert r.ok, r.error
    assert r.result is False
    print(f"  is_harmonic(x²+y²): {r.result}")

    # 6. is_harmonic: u = log(x^2+y^2) 是调和函数（基本解）
    r = is_harmonic(sp.log(x**2 + y**2), x, y)
    assert r.ok, r.error
    print(f"  is_harmonic(log(x²+y²)): {r.result}")

    print("=== holomorphic self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
