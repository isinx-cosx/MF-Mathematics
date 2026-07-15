"""product_measure.py — 乘积测度与 Fubini 定理。

涵盖乘积测度构造与 Fubini 定理验证。
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import parse_func

from typing import Any, Callable, List, Optional, Tuple, Union

import numpy as np
import scipy.integrate as integrate
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
@register(module="measure_theory", action="product_measure")
def product_measure(
    mu: Any,
    nu: Any,
    A: Union[Tuple[float, float], List[float]],
    B: Union[Tuple[float, float], List[float]],
) -> MathObject:
    """计算乘积测度 (μ × ν)(A × B) = μ(A) · ν(B)。

    对于勒贝格测度 λ × λ((a,b) × (c,d)) = (b-a)(d-c)。

    若 mu 或 nu 为 "lebesgue" 字符串，使用勒贝格测度。
    若为可调用对象，直接调用。
    若为数值，当作常数因子（如计数测度）。

    Args:
        mu: 第一个测度（字符串 "lebesgue" / 可调用对象 / 数值）。
        nu: 第二个测度。
        A: 第一个坐标集合（区间 [a, b]）。
        B: 第二个坐标集合（区间 [c, d]）。

    Returns:
        MathObject: result 为乘积测度值。
    """
    try:
        def _eval_measure(m, interval):
            if m == "lebesgue" or m is None:
                return abs(float(interval[1]) - float(interval[0]))
            elif callable(m):
                return m(interval)
            elif isinstance(m, (int, float)):
                return float(m) * abs(float(interval[1]) - float(interval[0]))
            else:
                return abs(float(interval[1]) - float(interval[0]))

        mu_A = _eval_measure(mu, A)
        nu_B = _eval_measure(nu, B)

        prod = mu_A * nu_B

        steps = [
            f"μ(A) = μ({A}) = {mu_A}",
            f"ν(B) = ν({B}) = {nu_B}",
            f"(μ × ν)(A × B) = μ(A) · ν(B) = {mu_A} · {nu_B} = {prod}",
        ]

        return MathObject(
            result=prod,
            steps=steps,
            meaning=f"乘积测度 (μ × ν)({A} × {B}) = {prod}",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="fubini_theorem")
def fubini_theorem(
    f: Union[str, Callable],
    mu: Any = "lebesgue",
    nu: Any = "lebesgue",
    domain: Optional[
        Union[
            Tuple[float, float, float, float],
            List[float],
        ]
    ] = None,
) -> MathObject:
    """Fubini 定理验证：重积分次序可交换。

    若 f ∈ L¹(μ × ν)，则：
    ∫∫ f(x,y) dμ(x) dν(y) = ∫∫ f(x,y) dν(y) dμ(x)
    = ∫ f d(μ × ν)

    对于勒贝格测度在矩形区域上，等价于：
    ∫_c^d (∫_a^b f(x,y) dx) dy = ∫_a^b (∫_c^d f(x,y) dy) dx

    Args:
        f: 被积函数，字符串表达式（含 x, y）或可调用对象。
        mu: 第一个测度（默认勒贝格）。
        nu: 第二个测度（默认勒贝格）。
        domain: [a, b, c, d] 分别表示 x ∈ [a,b]，y ∈ [c,d]，默认 [0,1,0,1]。

    Returns:
        MathObject: result 含两种积分次序的值及是否一致。
    """
    try:
        if domain is None:
            a, b, c, d = 0.0, 1.0, 0.0, 1.0
        elif len(domain) == 4:
            a, b, c, d = (float(v) for v in domain)
        else:
            return MathObject(error=f"domain 需要 4 个值 [a,b,c,d]，当前 {domain}")

        x_sym, y_sym = sp.Symbol("x", real=True), sp.Symbol("y", real=True)
        expr = parse_func(f, (x_sym, y_sym))

        f_lambda = sp.lambdify((x_sym, y_sym), expr, "numpy")

        # 先 x 后 y: ∫_c^d [∫_a^b f(x,y) dx] dy
        def inner_x(y_val):
            return integrate.quad(lambda t: float(f_lambda(t, y_val)), a, b, limit=200)[0]

        xy_order, _ = integrate.quad(inner_x, c, d, limit=200)

        # 先 y 后 x: ∫_a^b [∫_c^d f(x,y) dy] dx
        def inner_y(x_val):
            return integrate.quad(lambda t: float(f_lambda(x_val, t)), c, d, limit=200)[0]

        yx_order, _ = integrate.quad(inner_y, a, b, limit=200)

        diff = abs(xy_order - yx_order)
        fubini_holds = diff < 1e-6

        # 符号验证
        sym_result = None
        try:
            inner_sym = sp.integrate(expr, (x_sym, a, b))
            outer_sym = sp.integrate(inner_sym, (y_sym, c, d))
            sym_result = float(outer_sym.evalf())
        except Exception:
            pass

        steps = [
            f"被积函数: f(x,y) = {expr}",
            f"区域: x ∈ [{a}, {b}], y ∈ [{c}, {d}]",
            f"先 x 后 y: ∫_c^d ∫_a^b f dx dy = {xy_order:.10f}",
            f"先 y 后 x: ∫_a^b ∫_c^d f dy dx = {yx_order:.10f}",
            f"差值: {diff:.2e}",
            f"Fubini 定理: {'成立 ✓' if fubini_holds else '差值显著 ✗（f 可能不可积）'}",
        ]
        if sym_result is not None:
            steps.append(f"SymPy 符号积分: {sym_result:.10f}")

        return MathObject(
            result={
                "xy_order": xy_order,
                "yx_order": yx_order,
                "difference": diff,
                "fubini_holds": fubini_holds,
                "symbolic": sym_result,
            },
            steps=steps,
            meaning="Fubini 定理验证: 重积分次序可交换",
        )

    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """product_measure 模块自测。"""
    print("=== product_measure self_test ===")
    all_ok = True

    # 测试 1: product_measure λ×λ on [0,1]×[0,1] = 1
    r = product_measure("lebesgue", "lebesgue", [0, 1], [0, 1])
    assert r.ok and abs(r.result - 1) < 1e-10, f"失败: {r}"
    print(f"  [PASS] product_measure([0,1]×[0,1]) = {r.result}")

    # 测试 2: product_measure on [0,2]×[0,3] = 6
    r = product_measure("lebesgue", "lebesgue", [0, 2], [0, 3])
    assert r.ok and abs(r.result - 6) < 1e-10, f"失败: {r}"
    print(f"  [PASS] product_measure([0,2]×[0,3]) = {r.result}")

    # 测试 3: Fubini f(x,y) = x*y on [0,1]×[0,1] → 1/4
    r = fubini_theorem("x*y", domain=[0, 1, 0, 1])
    assert r.ok and r.result["fubini_holds"], f"失败: {r}"
    assert abs(r.result["xy_order"] - 0.25) < 0.001, f"期望 0.25, 实际 {r.result}"
    print(f"  [PASS] fubini_theorem('x*y'): {r.result['xy_order']:.6f} = {r.result['yx_order']:.6f}")

    # 测试 4: Fubini f(x,y)=x**2 + y**2
    r = fubini_theorem("x**2 + y**2", domain=[0, 1, 0, 1])
    assert r.ok and r.result["fubini_holds"], f"失败: {r}"
    print(f"  [PASS] fubini_theorem('x**2+y**2'): {r.result['xy_order']:.6f}")

    print("=== product_measure: ALL PASSED ===\n")
    return all_ok


if __name__ == "__main__":
    self_test()
