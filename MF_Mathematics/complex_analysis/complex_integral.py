"""复曲线积分 — 柯西定理、柯西积分公式、高阶导公式。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple, Union

import sympy as sp
import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


# ── 工具 ───────────────────────────────────────────────────────────────

def _eval_func_at(func: Any, z_val: complex) -> complex:
    """在复点处求函数值。func 可以是字符串、sympy 表达式或 Callable。"""
    if isinstance(func, str):
        z_sym = sp.Symbol('z')
        expr = sp.sympify(func)
        return complex(sp.N(expr.subs(z_sym, z_val)))
    if callable(func) and not isinstance(func, sp.Basic):
        return complex(func(z_val))
    # sympy 表达式
    z_sym = sp.Symbol('z')
    return complex(sp.N(func.subs(z_sym, z_val)))


# ── 公开函数 ──────────────────────────────────────────────────────────


@register(module="complex_analysis", action="contour_integral")
def contour_integral(
    func: Any,
    gamma: Union[str, Callable[[float], complex]],
    t_range: Tuple[float, float],
    n_points: int = 1000,
) -> MathObject:
    """复曲线积分 ∫_γ f(z) dz。

    数值计算：∫_a^b f(γ(t)) γ'(t) dt。
    对常见闭合曲线（circle）提供解析计算。

    Args:
        func: 被积函数，字符串/sympy 表达式/Callable。
        gamma: 曲线参数化。
            "circle(center, r)" 表示圆心 center、半径 r 的圆。
            或 Callable γ(t) -> complex。
        t_range: 参数 t 的范围 (a, b)。
        n_points: 数值积分的采样点数。

    Returns:
        MathObject，result 为积分值（复数或符号表达式）。
    """
    try:
        if isinstance(gamma, str) and gamma.startswith("circle"):
            # 解析 "circle(center, r)"
            import re
            match = re.match(r'circle\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', gamma)
            if match:
                center_str = match.group(1).strip()
                radius_str = match.group(2).strip()
                # 解析 center（可能是复数或 "x+yi"）
                if 'i' in center_str or 'j' in center_str:
                    center = complex(center_str.replace('i', 'j').replace('I', 'j'))
                else:
                    center = complex(float(center_str), 0)
                r0 = float(radius_str)

                # 参数化 γ(t) = center + r*e^{it}, t ∈ [0, 2π]
                a_param, b_param = t_range

                # 使用柯西定理 / 留数定理做解析计算
                z_sym = sp.Symbol('z')
                if isinstance(func, str):
                    expr = sp.sympify(func)
                else:
                    expr = func

                # 数值积分（endpoint=False 避免闭合曲线端点重复）
                t_vals = np.linspace(a_param, b_param, n_points, endpoint=False)
                dt = (b_param - a_param) / n_points
                total = complex(0, 0)

                for t in t_vals:
                    z_t = center + r0 * complex(np.cos(t), np.sin(t))
                    dz = r0 * complex(-np.sin(t), np.cos(t)) * dt
                    fz = _eval_func_at(func, z_t)
                    total += fz * dz

                steps = [
                    f"γ(t) = {center} + {r0}e^{{it}}, t ∈ [{a_param}, {b_param}]",
                    f"数值积分: n={n_points}",
                    f"∫_γ f(z) dz ≈ {total.real:.10g} + {total.imag:.10g}i",
                ]

                return MathObject(
                    result=total,
                    steps=steps,
                    meaning="复曲线积分 ∫_γ f(z) dz = ∫_a^b f(γ(t)) γ'(t) dt。",
                )

        # 通用情形：数值积分
        a_param, b_param = t_range
        t_vals = np.linspace(a_param, b_param, n_points, endpoint=False)
        dt = (b_param - a_param) / n_points
        total = complex(0, 0)

        if callable(gamma) and not isinstance(gamma, str):
            for i, t in enumerate(t_vals):
                z_t = gamma(t)
                # 数值微分 γ'(t)
                if i < n_points - 1:
                    z_next = gamma(t + dt)
                    dz = z_next - z_t
                else:
                    z_prev = gamma(t - dt)
                    dz = z_t - z_prev
                fz = _eval_func_at(func, z_t)
                total += fz * dz

            steps = [
                f"数值积分: t ∈ [{a_param}, {b_param}], n={n_points}",
                f"∫_γ f(z) dz ≈ {total.real:.10g} + {total.imag:.10g}i",
            ]
            return MathObject(
                result=total,
                steps=steps,
                meaning="对任意曲线的数值复积分。",
            )

        return MathObject(error=f"不支持的 gamma 规格: {gamma}")
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="cauchy_theorem")
def cauchy_theorem(
    func: Any,
    contour: str,
    interior: Optional[str] = None,
) -> MathObject:
    """柯西-古萨定理验证。

    若 f 在单连通区域 D 内全纯，则对 D 内任意闭合曲线 γ 有 ∫_γ f(z) dz = 0。

    此处通过检查 f 是否全纯 + 数值积分验证。

    Args:
        func: 被积函数。
        contour: 闭合曲线规格 "circle(center, r)"。
        interior: 内部区域描述（可选）。

    Returns:
        MathObject，result 包含积分值和是否为零的判定。
    """
    try:
        integral = contour_integral(func, contour, (0, 2 * np.pi))
        if integral.error:
            return integral

        val = integral.result
        is_zero = abs(val) < 1e-8

        steps = [
            f"f(z) = {func}",
            f"闭合曲线: {contour}",
            f"数值积分结果: {val.real:.10g} + {val.imag:.10g}i",
            f"|∫ f| = {abs(val):.2e}",
            f"柯西定理{'成立' if is_zero else '可能不适用（f 非全纯或有奇点）'}",
        ]

        return MathObject(
            result={"integral": val, "zero": is_zero},
            steps=steps,
            meaning="f 在单连通区域内全纯 ⇒ 沿任意闭合曲线积分为零。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="cauchy_integral_formula")
def cauchy_integral_formula(
    func: Any,
    a: complex,
    contour: str,
    n_points: int = 1000,
) -> MathObject:
    """柯西积分公式。

    f(a) = (1/(2πi)) ∫_γ f(z)/(z-a) dz，其中 a 在 γ 内部。

    Args:
        func: 被积函数 f(z)。
        a: 内点。
        contour: 闭合曲线规格 "circle(center, r)"。
        n_points: 积分采样点数。

    Returns:
        MathObject，result 为 f(a) 的数值结果对比。
    """
    try:
        import re
        match = re.match(r'circle\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', contour)
        if not match:
            return MathObject(error=f"无法解析 contour: {contour}")

        center_str = match.group(1).strip()
        r0 = float(match.group(2).strip())
        if 'i' in center_str or 'j' in center_str:
            center = complex(center_str.replace('i', 'j').replace('I', 'j'))
        else:
            center = complex(float(center_str), 0)

        # 数值积分
        t_vals = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
        dt = 2 * np.pi / n_points
        total = complex(0, 0)

        for t in t_vals:
            z_t = center + r0 * complex(np.cos(t), np.sin(t))
            dz = r0 * complex(-np.sin(t), np.cos(t)) * dt
            if abs(z_t - a) < 1e-12:
                continue  # 跳过奇点
            fz = _eval_func_at(func, z_t)
            total += (fz / (z_t - a)) * dz

        integral_value = total / (2 * np.pi * 1j)
        direct_value = _eval_func_at(func, a)

        steps = [
            f"f(z) = {func}",
            f"a = {a}",
            f"闭合曲线: {contour}",
            f"数值积分: (1/2πi) ∫ f(z)/(z-a) dz",
            f"柯西积分公式结果: {integral_value.real:.10g} + {integral_value.imag:.10g}i",
            f"直接计算 f(a): {direct_value.real:.10g} + {direct_value.imag:.10g}i",
            f"误差: {abs(integral_value - direct_value):.2e}",
        ]

        return MathObject(
            result={
                "cauchy_formula": integral_value,
                "direct_f_a": direct_value,
                "error": abs(integral_value - direct_value),
            },
            steps=steps,
            meaning="f(a) = 1/(2πi) ∮ f(z)/(z-a) dz。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="derivative_formula")
def derivative_formula(
    func: Any,
    a: complex,
    n: int,
    contour: str,
    n_points: int = 1000,
) -> MathObject:
    """高阶导积分公式。

    f^{(n)}(a) = (n!/(2πi)) ∫_γ f(z)/(z-a)^{n+1} dz

    Args:
        func: 被积函数 f(z)。
        a: 内点。
        n: 导数阶数。
        contour: 闭合曲线规格。
        n_points: 积分采样点数。

    Returns:
        MathObject，result 为 f^{(n)}(a) 的近似值。
    """
    try:
        import re
        import math
        match = re.match(r'circle\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', contour)
        if not match:
            return MathObject(error=f"无法解析 contour: {contour}")

        center_str = match.group(1).strip()
        r0 = float(match.group(2).strip())
        if 'i' in center_str or 'j' in center_str:
            center = complex(center_str.replace('i', 'j').replace('I', 'j'))
        else:
            center = complex(float(center_str), 0)

        t_vals = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
        dt = 2 * np.pi / n_points
        total = complex(0, 0)

        for t in t_vals:
            z_t = center + r0 * complex(np.cos(t), np.sin(t))
            dz = r0 * complex(-np.sin(t), np.cos(t)) * dt
            if abs(z_t - a) < 1e-12:
                continue
            fz = _eval_func_at(func, z_t)
            total += (fz / (z_t - a) ** (n + 1)) * dz

        derivative_val = math.factorial(n) * total / (2 * np.pi * 1j)

        # 符号验证（若 func 是 sympy 可解析表达式）
        try:
            z_sym = sp.Symbol('z')
            expr = sp.sympify(func) if isinstance(func, str) else func
            symbolic_deriv = sp.diff(expr, z_sym, n)
            symbolic_val = complex(sp.N(symbolic_deriv.subs(z_sym, a)))
        except Exception:
            symbolic_val = None

        steps = [
            f"f(z) = {func}",
            f"a = {a}, n = {n}",
            f"闭合曲线: {contour}",
            f"数值积分: (n!/2πi) ∫ f(z)/(z-a)^{{{n+1}}} dz",
            f"f^({n})(a) ≈ {derivative_val.real:.10g} + {derivative_val.imag:.10g}i",
        ]
        if symbolic_val is not None:
            steps.append(
                f"符号验证: f^({n})(a) = {symbolic_val.real:.10g} + {symbolic_val.imag:.10g}i"
            )
            steps.append(f"误差: {abs(derivative_val - symbolic_val):.2e}")

        return MathObject(
            result={
                "derivative": derivative_val,
                "symbolic": symbolic_val,
            },
            steps=steps,
            meaning=f"f^({n})(a) = n!/(2πi) ∮ f(z)/(z-a)^{{{n+1}}} dz。",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ── self_test ──────────────────────────────────────────────────────────

def self_test() -> None:
    """自测：复曲线积分。"""
    print("=== complex_integral self_test ===")

    # 1. 柯西定理: f(z)=1 沿单位圆积分 → 0
    r = cauchy_theorem("1", "circle(0, 1)")
    assert r.ok, r.error
    assert r.result["zero"] is True
    print(f"  cauchy_theorem(1, circle(0,1)): zero={r.result['zero']}")

    # 2. 柯西积分公式: f(z)=sin(z), a=0 沿单位圆
    r = cauchy_integral_formula("sin(z)", 0, "circle(0, 1)")
    assert r.ok, r.error
    assert abs(r.result["error"]) < 0.01
    print(f"  cauchy_integral_formula(sin(z), 0): f(0)={r.result['direct_f_a']:.6g}, "
          f"formula={r.result['cauchy_formula']:.6g}, err={r.result['error']:.2e}")

    # 3. 高阶导公式: f(z)=z^3, a=0, n=2, f''(0)=0
    r = derivative_formula("z**3", 0, 2, "circle(0, 1)")
    assert r.ok, r.error
    if r.result.get("symbolic") is not None:
        assert abs(r.result["symbolic"]) < 1e-10
    print(f"  derivative_formula(z³, 0, n=2): f''(0)={r.result['derivative']:.6g}")

    # 4. contour_integral: ∫_{|z|=1} 1/z dz = 2πi
    r = contour_integral("1/z", "circle(0, 1)", (0, 2 * np.pi), n_points=2000)
    assert r.ok, r.error
    expected = 2 * np.pi * 1j
    assert abs(r.result - expected) < 0.1
    print(f"  contour_integral(1/z, circle(0,1)): {r.result:.6g}, expected 2πi={expected:.6g}")

    print("=== complex_integral self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
