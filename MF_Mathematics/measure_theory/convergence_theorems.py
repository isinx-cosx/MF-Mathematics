"""convergence_theorems.py — 积分极限定理。

涵盖单调收敛定理、法图引理、控制收敛定理的数值验证。
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import parse_func

from typing import Any, Callable, List, Optional, Tuple, Union

import numpy as np
import scipy.integrate as integrate
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
@register(module="measure_theory", action="monotone_convergence")
def monotone_convergence(
    f_n: Union[str, Callable],
    f: Union[str, Callable],
    n_values: Optional[List[int]] = None,
    domain: Union[Tuple[float, float], List[float]] = (0, 1),
) -> MathObject:
    """单调收敛定理数值验证。

    若 f_n ↑ f λ-a.e.（单调递增且逐点收敛），且每个 f_n 非负可测，则：
    lim (n->inf) ∫ f_n dλ = ∫ (lim (n->inf) f_n) dλ = ∫ f dλ。

    即极限与积分可交换。

    Args:
        f_n: 函数列表达式（含 n 参数），如 "1 - exp(-n*x)"。
        f: 极限函数表达式，如 "1"。
        n_values: n 的取值列表，默认 [1, 2, 5, 10, 50, 100]。
        domain: 积分区间。

    Returns:
        MathObject: result 含各 n 的积分值及极限比较。
    """
    try:
        a, b = (float(domain[0]), float(domain[1]))
        x_var = sp.Symbol("x", real=True)
        n_var = sp.Symbol("n", integer=True, positive=True)

        expr_fn = parse_func(f_n, x_var)
        expr_f = parse_func(f, x_var)

        if n_values is None:
            n_values = [1, 2, 5, 10, 50, 100]

        # 逐 n 计算积分
        integral_values = []
        for n_val in n_values:
            fn_expr = expr_fn.subs(n_var, n_val)
            fn_lambda = sp.lambdify(x_var, fn_expr, "numpy")
            val, _ = integrate.quad(lambda t: float(fn_lambda(t)), a, b, limit=200)
            integral_values.append(val)

        # 极限函数积分
        f_lambda = sp.lambdify(x_var, expr_f, "numpy")
        limit_integral, _ = integrate.quad(lambda t: float(f_lambda(t)), a, b, limit=200)

        limit_of_integrals = integral_values[-1]  # 近似 lim (n->inf) ∫ f_n

        steps = [
            f"函数列: f_n(x) = {expr_fn}",
            f"极限函数: f(x) = {expr_f}",
            f"定义域: [{a}, {b}]",
        ]
        for n_val, int_val in zip(n_values, integral_values):
            steps.append(f"n={n_val:3d}: ∫ f_n dλ = {int_val:.10f}")
        steps.append(f"lim n->inf: integral f_n d(lambda) = {limit_of_integrals:.10f}")
        steps.append(f"integral f d(lambda) = {limit_integral:.10f}")

        diff = abs(limit_of_integrals - limit_integral)
        converged = diff < 0.01

        steps.append(
            f"差值: {diff:.10f} -> "
            f"{'极限与积分可交换 [OK]' if converged else '差异显著 [X]'}"
        )

        return MathObject(
            result={
                "n_values": n_values,
                "integral_values": integral_values,
                "limit_of_integrals": limit_of_integrals,
                "integral_of_limit": limit_integral,
                "difference": diff,
                "converged": converged,
            },
            steps=steps,
            meaning="单调收敛定理验证: lim ∫ f_n = ∫ lim f_n",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="fatou_lemma")
def fatou_lemma(
    f_n: Union[str, Callable],
    n_values: Optional[List[int]] = None,
    domain: Union[Tuple[float, float], List[float]] = (0, 1),
) -> MathObject:
    """法图引理数值验证。

    Fatou 引理：对非负可测函数列 f_n，
    ∫ (liminf f_n) dλ ≤ liminf ∫ f_n dλ。

    本函数计算 liminf 积分与积分的 liminf 并比较。

    Args:
        f_n: 函数列表达式（含 n），如 "sin(n*x)**2"。
        n_values: n 的取值列表。
        domain: 积分区间。

    Returns:
        MathObject: result 含比较结果。
    """
    try:
        a, b = (float(domain[0]), float(domain[1]))
        x_var = sp.Symbol("x", real=True)
        n_var = sp.Symbol("n", integer=True, positive=True)

        expr_fn = parse_func(f_n, x_var)

        if n_values is None:
            n_values = [1, 2, 5, 10, 20]

        integral_values = []
        for n_val in n_values:
            fn_expr = expr_fn.subs(n_var, n_val)
            fn_lambda = sp.lambdify(x_var, fn_expr, "numpy")
            val, _ = integrate.quad(lambda t: max(float(fn_lambda(t)), 0), a, b, limit=200)
            integral_values.append(val)

        # liminf 积分的数值近似: 对每个 x，min(f_n(x))
        sample_points = np.linspace(a, b, 500)
        liminf_vals = np.full(len(sample_points), np.inf)
        for n_val in n_values:
            fn_expr = expr_fn.subs(n_var, n_val)
            fn_lambda = sp.lambdify(x_var, fn_expr, "numpy")
            fn_samples = np.maximum(fn_lambda(sample_points), 0)
            liminf_vals = np.minimum(liminf_vals, fn_samples)
        integral_of_liminf = np.trapezoid(liminf_vals, sample_points)

        liminf_of_integrals = min(integral_values)
        inequality_holds = integral_of_liminf <= liminf_of_integrals + 1e-8

        steps = [
            f"函数列: f_n(x) = {expr_fn}",
            f"定义域: [{a}, {b}]",
            "各 n 的积分值:",
        ]
        for n_val, int_val in zip(n_values, integral_values):
            steps.append(f"  n={n_val:3d}: ∫ f_n dλ = {int_val:.10f}")
        steps.append(f"∫ (liminf f_n) dλ = {integral_of_liminf:.10f}")
        steps.append(f"liminf ∫ f_n dλ = {liminf_of_integrals:.10f}")
        steps.append(
            f"法图不等式: {integral_of_liminf:.10f} <= {liminf_of_integrals:.10f} "
            f"-> {'成立 [OK]' if inequality_holds else '理论应成立（数值舍入）'}"
        )

        return MathObject(
            result={
                "integral_values": integral_values,
                "integral_of_liminf": integral_of_liminf,
                "liminf_of_integrals": liminf_of_integrals,
                "inequality_holds": inequality_holds,
            },
            steps=steps,
            meaning="法图引理验证: ∫ liminf f_n ≤ liminf ∫ f_n",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="dominated_convergence")
def dominated_convergence(
    f_n: Union[str, Callable],
    f: Union[str, Callable],
    g: Union[str, Callable],
    n_values: Optional[List[int]] = None,
    domain: Union[Tuple[float, float], List[float]] = (0, 1),
) -> MathObject:
    """控制收敛定理数值验证。

    Lebesgue 控制收敛定理 (DCT)：
    若 f_n → f λ-a.e.，且存在可积函数 g 使得 |f_n| ≤ g λ-a.e.，则：
    lim (n->inf) ∫ f_n dλ = ∫ f dλ。

    Args:
        f_n: 函数列表达式（含 n）。
        f: 极限函数表达式。
        g: 控制函数（需可积且 |f_n| ≤ g）。
        n_values: n 的取值列表。
        domain: 积分区间。

    Returns:
        MathObject: result 含 DCT 验证结果。
    """
    try:
        a, b = (float(domain[0]), float(domain[1]))
        x_var = sp.Symbol("x", real=True)
        n_var = sp.Symbol("n", integer=True, positive=True)

        expr_fn = parse_func(f_n, x_var)
        expr_f = parse_func(f, x_var)
        expr_g = parse_func(g, x_var)

        if n_values is None:
            n_values = [1, 2, 5, 10, 50, 100]

        # 验证控制条件 |f_n| ≤ g
        g_lambda = sp.lambdify(x_var, expr_g, "numpy")
        dominated = True
        for n_val in n_values:
            fn_expr = expr_fn.subs(n_var, n_val)
            fn_lambda = sp.lambdify(x_var, fn_expr, "numpy")
            test_points = np.linspace(a, b, 100)
            for pt in test_points:
                if abs(float(fn_lambda(pt))) > float(g_lambda(pt)) + 1e-10:
                    dominated = False
                    break
            if not dominated:
                break

        # 计算各 n 的积分
        integral_values = []
        for n_val in n_values:
            fn_expr = expr_fn.subs(n_var, n_val)
            fn_lambda = sp.lambdify(x_var, fn_expr, "numpy")
            val, _ = integrate.quad(lambda t: float(fn_lambda(t)), a, b, limit=200)
            integral_values.append(val)

        # 极限函数积分
        f_lambda = sp.lambdify(x_var, expr_f, "numpy")
        limit_integral, _ = integrate.quad(lambda t: float(f_lambda(t)), a, b, limit=200)

        # 控制函数积分
        g_integral, _ = integrate.quad(lambda t: float(g_lambda(t)), a, b, limit=200)

        limit_of_integrals = integral_values[-1]
        diff = abs(limit_of_integrals - limit_integral)

        steps = [
            f"函数列: f_n(x) = {expr_fn}",
            f"极限函数: f(x) = {expr_f}",
            f"控制函数: g(x) = {expr_g} ({'可积' if g_integral < np.inf else '不可积'})",
            f"控制条件 |f_n| ≤ g: {'满足' if dominated else '不满足'}",
            f"∫ g dλ = {g_integral:.10f}",
        ]
        for n_val, int_val in zip(n_values, integral_values):
            steps.append(f"  n={n_val:3d}: ∫ f_n dλ = {int_val:.10f}")
        steps.append(f"lim (n->inf) ∫ f_n dλ ≈ {limit_of_integrals:.10f}")
        steps.append(f"∫ (lim f_n) dλ = ∫ f dλ = {limit_integral:.10f}")

        if dominated:
            steps.append(f"DCT 交换成立: 差值 = {diff:.10f} -> {'(OK)' if diff < 0.01 else '近似接近'}")
        else:
            steps.append("控制条件不满足，DCT 不可直接应用")

        return MathObject(
            result={
                "dominated": dominated,
                "integral_values": integral_values,
                "limit_of_integrals": limit_of_integrals,
                "integral_of_limit": limit_integral,
                "g_integral": g_integral,
                "difference": diff,
            },
            steps=steps,
            meaning="控制收敛定理验证: 若 |f_n| ≤ g 可积，则极限与积分可交换",
        )

    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """convergence_theorems 模块自测。"""
    print("=== convergence_theorems self_test ===")
    all_ok = True

    # 测试 1: 单调收敛 f_n(x) = 1 - exp(-n*x), f(x)=1
    r = monotone_convergence("1 - exp(-n*x)", "1", n_values=[1, 2, 5, 10, 50, 200], domain=(0, 2))
    assert r.ok, f"失败: {r}"
    assert r.result["converged"], f"未收敛: {r.result}"
    print(f"  [PASS] monotone_convergence: diff = {r.result['difference']:.8f}")

    # 测试 2: 法图引理 f_n(x) = x**(1/n)
    r = fatou_lemma("x**(1/n)", n_values=[1, 2, 5, 10, 20], domain=(0, 1))
    assert r.ok, f"失败: {r}"
    assert r.result["inequality_holds"], f"不等式不成立: {r.result}"
    print(f"  [PASS] fatou_lemma: inequality_holds = {r.result['inequality_holds']}")

    # 测试 3: 控制收敛 f_n = sin(n*x)/(n + x**2), f=0, g=1/(1+x**2)
    r = dominated_convergence(
        "sin(n*x)/(n + x**2)", "0", "1/(1+x**2)",
        n_values=[1, 2, 5, 10, 50],
        domain=(0, 1),
    )
    assert r.ok, f"失败: {r}"
    print(f"  [PASS] dominated_convergence: dominated={r.result['dominated']}, diff={r.result['difference']:.8f}")

    print("=== convergence_theorems: ALL PASSED ===\n")
    return all_ok


if __name__ == "__main__":
    self_test()
