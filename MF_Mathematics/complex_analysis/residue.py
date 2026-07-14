"""留数理论 — 留数定义、留数定理、实积分计算、辐角原理、鲁歇定理。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple, Union

import sympy as sp
import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


# ── 工具 ───────────────────────────────────────────────────────────────

def _parse_expr_var(func: Any, var: Any = None):
    """解析函数表达式和变量。"""
    if isinstance(func, str):
        expr = sp.sympify(func)
    else:
        expr = func
    if var is None:
        syms = list(expr.free_symbols)
        var = syms[0] if syms else sp.Symbol('z')
    elif isinstance(var, str):
        var = sp.Symbol(var)
    return expr, var


def _eval_complex(expr: Any, z_sym: sp.Symbol, z_val: complex) -> complex:
    """在复点求值。"""
    return complex(sp.N(expr.subs(z_sym, z_val)))


# ── 公开函数 ──────────────────────────────────────────────────────────


@register(module="complex_analysis", action="residue")
def residue(
    func: Any,
    z0: Any,
    var: Any = None,
) -> MathObject:
    """计算留数（洛朗展开的 -1 次项系数 a_{-1}）。

    方法：
    - 若 m 阶极点：Res(f, z₀) = 1/(m-1)! · lim_{z→z₀} d^{m-1}/dz^{m-1} [(z-z₀)^m f(z)]
    - 一般情形用 sympy residue 函数。

    Args:
        func: 函数表达式。
        z0: 奇点位置。
        var: 复变量符号。

    Returns:
        MathObject，result 为留数值。
    """
    try:
        expr, var_sym = _parse_expr_var(func, var)
        z0_sym = sp.sympify(z0)

        # 使用 sympy 内置函数
        res = sp.residue(expr, var_sym, z0_sym)
        res_numeric = complex(sp.N(res))

        steps = [
            f"f(z) = {expr}",
            f"奇点: z₀ = {z0_sym}",
            f"Res(f, {z0_sym}) = {res}",
        ]
        if res != res_numeric:
            steps.append(f"数值: {res_numeric.real:.10g} + {res_numeric.imag:.10g}i")

        return MathObject(
            result={"symbolic": str(res), "numeric": res_numeric},
            steps=steps,
            meaning="留数 = 洛朗级数中 (z-z₀)^{-1} 的系数 a_{-1}。",
        )
    except Exception as e:
        # 手动计算：尝试极点公式
        try:
            expr, var_sym = _parse_expr_var(func, var)
            z0_sym = sp.sympify(z0)

            # 假设是 m 阶极点，从 m=1 开始尝试
            for m in range(1, 11):
                powered = sp.simplify(expr * (var_sym - z0_sym) ** m)
                lim_val = sp.limit(powered, var_sym, z0_sym)
                if lim_val.is_finite and lim_val != 0:
                    # 使用极点留数公式
                    deriv = sp.diff(powered, var_sym, m - 1)
                    lim_deriv = sp.limit(deriv, var_sym, z0_sym)
                    res_val = lim_deriv / sp.factorial(m - 1)
                    res_numeric = complex(sp.N(res_val))
                    steps = [
                        f"f(z) = {expr}",
                        f"z₀ = {z0_sym}（{m} 阶极点）",
                        f"Res = 1/({m-1})! lim d^{{{m-1}}}/dz^{{{m-1}}} [(z-z₀)^{{{m}}}f(z)]",
                        f"Res = {res_val}",
                    ]
                    return MathObject(
                        result={"symbolic": str(res_val), "numeric": res_numeric},
                        steps=steps,
                        meaning="m 阶极点的留数公式。",
                    )
            return MathObject(error=str(e))
        except Exception as e2:
            return MathObject(error=f"{e}; {e2}")


@register(module="complex_analysis", action="residue_theorem")
def residue_theorem(
    func: Any,
    contour: str,
    singularities: List[Any],
    var: Any = None,
) -> MathObject:
    """留数定理。

    ∮_γ f(z) dz = 2πi Σ Res(f, z_k)，其中 z_k 为 γ 内部的所有奇点。

    Args:
        func: 被积函数。
        contour: 闭合曲线规格 "circle(center, r)"。
        singularities: 奇点列表（需先确认在 contour 内部）。
        var: 复变量符号。

    Returns:
        MathObject，result 为积分值。
    """
    try:
        expr, var_sym = _parse_expr_var(func, var)

        total_res = sp.Integer(0)
        residues_detail = []

        for zk in singularities:
            zk_sym = sp.sympify(zk)
            res = sp.residue(expr, var_sym, zk_sym)
            total_res += res
            residues_detail.append({
                "singularity": str(zk_sym),
                "residue": str(res),
                "numeric": complex(sp.N(res)),
            })

        integral = 2 * sp.pi * sp.I * total_res
        integral_numeric = complex(sp.N(integral))

        steps = [
            f"f(z) = {expr}",
            f"闭合曲线: {contour}",
            f"内部奇点: {singularities}",
        ]
        for d in residues_detail:
            steps.append(f"  Res(f, {d['singularity']}) = {d['residue']}")
        steps.append(f"Σ Res = {total_res}")
        steps.append(f"∮ f dz = 2πi · Σ Res = {integral_numeric.real:.10g} + {integral_numeric.imag:.10g}i")

        return MathObject(
            result={"integral": integral_numeric, "symbolic": str(integral)},
            steps=steps,
            meaning="留数定理: ∮_γ f dz = 2πi Σ_{内部奇点} Res(f, z_k)。",
            data={"residues": residues_detail},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="real_integral")
def real_integral(
    func: Any,
    a: float = float('-inf'),
    b: float = float('inf'),
    var: Any = None,
) -> MathObject:
    """用留数定理计算实积分。

    典型示例：∫_{-∞}^{∞} dx/(1+x²) = π。

    目前支持 ∫_{-∞}^{∞} 型有理函数积分。

    Args:
        func: 被积函数（如 "1/(1+x**2)"）。
        a: 积分下限。
        b: 积分上限。
        var: 变量符号。

    Returns:
        MathObject，result 为实积分值和计算过程。
    """
    try:
        expr, var_sym = _parse_expr_var(func, var)
        is_full_real_line = (a == float('-inf') and b == float('inf'))

        if is_full_real_line:
            # 将实变量替换为复变量 z
            z_sym = sp.Symbol('z')
            expr_z = expr.subs(var_sym, z_sym)

            # 在上半平面寻找极点
            # 通过求解分母零点
            if hasattr(expr_z, 'as_numer_denom'):
                num, den = expr_z.as_numer_denom()
            else:
                den = sp.denom(expr_z)
                num = sp.numer(expr_z)

            # 求分母零点
            denom_roots = sp.solve(den, z_sym)

            # 筛选上半平面极点
            upper_poles = []
            for root in denom_roots:
                root_c = complex(sp.N(root))
                if root_c.imag > 0:
                    upper_poles.append(root)

            # 计算留数和
            total_res = sp.Integer(0)
            residue_list = []
            for pole in upper_poles:
                res = sp.residue(expr_z, z_sym, pole)
                total_res += res
                residue_list.append({
                    "pole": str(pole),
                    "residue": str(res),
                    "numeric": complex(sp.N(res)),
                })

            result_val = 2 * sp.pi * sp.I * total_res
            result_numeric = complex(sp.N(result_val))

            steps = [
                f"I = ∫_{{{a}}}^{{{b}}} {expr} d{var_sym}",
                "使用围道积分（上半平面大圆弧 + 实轴）",
                f"上半平面极点: {[str(p) for p in upper_poles]}",
            ]
            for rd in residue_list:
                steps.append(f"  Res({rd['pole']}) = {rd['residue']}")
            steps.append(f"I = 2πi Σ Res = {result_numeric.real:.10g}")

            if abs(result_numeric.imag) < 1e-14:
                steps.append(f"虚部 ≈ 0，纯实结果: {result_numeric.real:.10g}")

            return MathObject(
                result={"integral": result_numeric.real if abs(result_numeric.imag) < 1e-14 else result_numeric,
                        "symbolic": str(result_val)},
                steps=steps,
                meaning="用留数定理 + 上半平面围道积分计算实积分。",
                data={"upper_half_plane_poles": residue_list},
            )

        # 有限区间数值积分
        import numpy as np
        from scipy import integrate

        f_lambda = sp.lambdify(var_sym, expr, 'numpy')
        result_val, error = integrate.quad(f_lambda, a, b)

        steps = [
            f"∫_{{{a}}}^{{{b}}} {expr} d{var_sym}",
            f"数值积分结果: {result_val:.10g}",
            f"估计误差: {error:.2e}",
        ]

        return MathObject(
            result=result_val,
            steps=steps,
            meaning="定积分数值计算。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="argument_principle")
def argument_principle(
    func: Any,
    contour: str,
    var: Any = None,
) -> MathObject:
    """辐角原理。

    1/(2πi) ∮_γ f'(z)/f(z) dz = Z - P，
    其中 Z 为零点数，P 为极点数（计重数）。

    Args:
        func: 复函数表达式。
        contour: 闭合曲线规格。
        var: 复变量符号。

    Returns:
        MathObject，result 为 dict {zeros_minus_poles, ...}。
    """
    try:
        import re

        expr, var_sym = _parse_expr_var(func, var)

        match = re.match(r'circle\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', contour)
        if not match:
            return MathObject(error=f"无法解析 contour: {contour}")

        center_str = match.group(1).strip()
        r0 = float(match.group(2).strip())
        if 'i' in center_str or 'j' in center_str:
            center = complex(center_str.replace('i', 'j').replace('I', 'j'))
        else:
            center = complex(float(center_str), 0)

        # 数值计算辐角原理积分
        n_points = 2000
        t_vals = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
        dt = 2 * np.pi / n_points
        total = complex(0, 0)

        deriv = sp.diff(expr, var_sym)

        for t in t_vals:
            z_t = center + r0 * complex(np.cos(t), np.sin(t))
            dz = r0 * complex(-np.sin(t), np.cos(t)) * dt
            fz = _eval_complex(expr, var_sym, z_t)
            fprime_z = _eval_complex(deriv, var_sym, z_t)
            if abs(fz) > 1e-15:
                total += (fprime_z / fz) * dz

        zp = total / (2 * np.pi * 1j)
        zp_real = round(zp.real)  # 应为整数

        steps = [
            f"f(z) = {expr}",
            f"γ: {contour}",
            f"1/(2πi) ∮ f'/f dz = {zp.real:.10g} + {zp.imag:.10g}i",
            f"Z - P = {zp_real}",
        ]

        return MathObject(
            result={"zeros_minus_poles": zp_real, "numeric": zp},
            steps=steps,
            meaning="辐角原理: 1/(2πi) ∮ f'/f dz = Z - P。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="rouche_theorem")
def rouche_theorem(
    f: Any,
    g: Any,
    contour: str,
    var: Any = None,
) -> MathObject:
    """鲁歇定理判定根数。

    若在 γ 上 |f(z) - g(z)| < |f(z)| + |g(z)|（通常简化为 |f - g| < |f|），
    则 f 和 g 在 γ 内部有相同数量的零点（计重数）。

    常用形式：若在 γ 上 |g(z)| < |f(z)|，则 f 和 f+g 有相同零点数。

    Args:
        f: 主导函数。
        g: 扰动函数。
        contour: 闭合曲线规格。
        var: 复变量符号。

    Returns:
        MathObject，result 包含判定结果和零点数。
    """
    try:
        import re

        f_expr, var_sym = _parse_expr_var(f, var)
        g_expr, var_sym = _parse_expr_var(g, var)

        match = re.match(r'circle\(\s*([^,]+)\s*,\s*([^)]+)\s*\)', contour)
        if not match:
            return MathObject(error=f"无法解析 contour: {contour}")

        center_str = match.group(1).strip()
        r0 = float(match.group(2).strip())
        if 'i' in center_str or 'j' in center_str:
            center = complex(center_str.replace('i', 'j').replace('I', 'j'))
        else:
            center = complex(float(center_str), 0)

        # 在 contour 上采样，检查 |g| < |f|
        n_samples = 200
        theta_vals = np.linspace(0, 2 * np.pi, n_samples, endpoint=False)
        condition_holds = True
        max_ratio = 0.0

        for theta in theta_vals:
            z_pt = center + r0 * complex(np.cos(theta), np.sin(theta))
            f_val = abs(_eval_complex(f_expr, var_sym, z_pt))
            g_val = abs(_eval_complex(g_expr, var_sym, z_pt))
            ratio = g_val / f_val if f_val > 1e-15 else float('inf')
            max_ratio = max(max_ratio, ratio)
            if g_val >= f_val:
                condition_holds = False

        # 计算 f 在上半平面/内部零点数（数值近似）
        # 使用辐角原理
        f_deriv = sp.diff(f_expr, var_sym)
        n_points_int = 2000
        t_int = np.linspace(0, 2 * np.pi, n_points_int, endpoint=False)
        dt_int = 2 * np.pi / n_points_int
        total_f = complex(0, 0)

        for t in t_int:
            z_t = center + r0 * complex(np.cos(t), np.sin(t))
            dz = r0 * complex(-np.sin(t), np.cos(t)) * dt_int
            fz = _eval_complex(f_expr, var_sym, z_t)
            fpz = _eval_complex(f_deriv, var_sym, z_t)
            if abs(fz) > 1e-15:
                total_f += (fpz / fz) * dz

        zeros_f = round((total_f / (2 * np.pi * 1j)).real)

        # 计算 f+g 的零点数
        fg_expr = f_expr + g_expr
        fg_deriv = sp.diff(fg_expr, var_sym)
        total_fg = complex(0, 0)

        t_int2 = np.linspace(0, 2 * np.pi, n_points_int, endpoint=False)
        for t in t_int2:
            z_t = center + r0 * complex(np.cos(t), np.sin(t))
            dz = r0 * complex(-np.sin(t), np.cos(t)) * dt_int
            fgz = _eval_complex(fg_expr, var_sym, z_t)
            fgpz = _eval_complex(fg_deriv, var_sym, z_t)
            if abs(fgz) > 1e-15:
                total_fg += (fgpz / fgz) * dz

        zeros_fg = round((total_fg / (2 * np.pi * 1j)).real)

        steps = [
            f"主导函数 f(z) = {f_expr}",
            f"扰动 g(z) = {g_expr}",
            f"γ: {contour}",
            f"max |g/f| on γ = {max_ratio:.6g}",
            f"条件 |g| < |f| 在 γ 上{'成立' if condition_holds else '不成立'}",
        ]
        if condition_holds:
            steps.append("由鲁歇定理，f 与 f+g 在 γ 内有相同零点数")
            steps.append(f"f 的零点数: {zeros_f}")
            steps.append(f"f+g 的零点数: {zeros_fg}")
        else:
            steps.append("条件不满足，鲁歇定理不直接适用")
            steps.append(f"但仍计算: f 零点数={zeros_f}, f+g 零点数={zeros_fg}")

        return MathObject(
            result={
                "condition_holds": condition_holds,
                "max_ratio": max_ratio,
                "zeros_f": zeros_f,
                "zeros_fg": zeros_fg,
            },
            steps=steps,
            meaning="鲁歇定理: 若 |g| < |f| 在 γ 上成立，则 f 与 f+g 在 γ 内部有相同零点数。",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ── self_test ──────────────────────────────────────────────────────────

def self_test() -> None:
    """自测：留数理论。"""
    print("=== residue self_test ===")

    # 1. residue: 1/(z^2+1) at z=i → 1/(2i)
    r = residue("1/(z**2+1)", sp.I)
    assert r.ok, r.error
    print(f"  residue(1/(z²+1), i): {r.result}")

    # 2. residue_theorem: 1/(z^2+1) 在 |z|=2
    r = residue_theorem("1/(z**2+1)", "circle(0, 2)", [sp.I, -sp.I])
    assert r.ok, r.error
    assert abs(r.result["integral"]) < 1e-8
    print(f"  residue_theorem(1/(z²+1), |z|=2): {r.result['integral']:.6g}")

    # 3. real_integral: ∫_{-∞}^{∞} dx/(1+x²)
    r = real_integral("1/(1+x**2)", a=float('-inf'), b=float('inf'))
    assert r.ok, r.error
    integral_val = r.result["integral"] if isinstance(r.result, dict) else r.result
    assert abs(float(integral_val) - np.pi) < 0.1
    print(f"  real_integral(1/(1+x²), -∞, ∞): {integral_val}")

    # 4. argument_principle: f(z)=z^2 在 |z|=1 → Z-P=2
    r = argument_principle("z**2", "circle(0, 1)")
    assert r.ok, r.error
    assert r.result["zeros_minus_poles"] == 2
    print(f"  argument_principle(z², |z|=1): Z-P={r.result['zeros_minus_poles']}")

    # 5. rouche_theorem: f=z^5, g=z, |z|=1.5
    r = rouche_theorem("z**5", "z", "circle(0, 1.5)")
    assert r.ok, r.error
    print(f"  rouche_theorem(z⁵, z, |z|=1.5): condition={r.result['condition_holds']}, "
          f"zeros_f={r.result['zeros_f']}, zeros_fg={r.result['zeros_fg']}")

    # 6. residue: 1/(z-1) at z=1 → 1
    r = residue("1/(z-1)", 1)
    assert r.ok, r.error
    print(f"  residue(1/(z-1), 1): {r.result}")

    print("=== residue self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
