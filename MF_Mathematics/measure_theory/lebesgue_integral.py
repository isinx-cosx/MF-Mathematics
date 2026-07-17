"""lebesgue_integral.py — 勒贝格积分。

涵盖简单函数积分、非负可测函数积分、一般可测函数积分
以及零测集无关性验证。
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import parse_func

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import scipy.integrate as integrate
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
def _parse_domain(domain) -> Tuple[float, float]:
    """解析定义域。"""
    if isinstance(domain, (list, tuple)):
        if len(domain) == 2:
            return float(domain[0]), float(domain[1])
    raise ValueError(f"无法解析: {domain}")


@register(module="measure_theory", action="integral_simple")
def integral_simple(
    simple_func: Union[Dict, Any],
    measure: Any = None,
) -> MathObject:
    """计算简单函数的勒贝格积分。

    简单函数 φ(x) = Σ c_i · 1_{E_i}，
    则 ∫ φ dμ = Σ c_i · μ(E_i)。

    若 measure 为 None，默认用勒贝格测度 μ(E) = length(E)。

    Args:
        simple_func: 简单函数，格式为 {'coefficients': [...], 'sets': [...]}
                     或从 simple_function() 返回的结果。
        measure: 测度函数（可选），默认勒贝格测度。

    Returns:
        MathObject: result 为积分值。
    """
    try:
        # 提取系数和集合
        if isinstance(simple_func, dict):
            coefs = simple_func.get("coefficients", [])
            sets = simple_func.get("sets", [])
        elif isinstance(simple_func, MathObject):
            data = simple_func.result
            if isinstance(data, dict):
                coefs = data.get("coefficients", [])
                sets = data.get("sets", [])
            else:
                return MathObject(error="simple_func 格式不正确")
        else:
            return MathObject(error="simple_func 必须是字典或 MathObject")

        if len(coefs) != len(sets):
            return MathObject(error=f"系数({len(coefs)})与集合({len(sets)})数量不匹配")

        total = 0.0
        terms = []

        for i, (c, interval) in enumerate(zip(coefs, sets)):
            if len(interval) != 2:
                return MathObject(error=f"集合 {i} 不是区间")
            a, b = float(interval[0]), float(interval[1])
            length = abs(b - a)

            if measure is None:
                mu_E = length
            elif callable(measure):
                mu_E = measure(interval)
            else:
                mu_E = length

            term = c * mu_E
            total += term
            terms.append(f"c_{i+1} · μ(E_{i+1}) = {c} · {mu_E} = {term}")

        steps = ["简单函数积分: ∫ φ dμ = Σ c_i · μ(E_i)"]
        steps.extend(terms)
        steps.append(f"总计: {total}")

        return MathObject(
            result=total,
            steps=steps,
            meaning="简单函数的勒贝格积分",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="integral_nonnegative")
def integral_nonnegative(
    f: Union[str, Callable],
    domain: Union[Tuple[float, float], List[float]] = (0, 1),
    n_steps: int = 1000,
) -> MathObject:
    """计算非负可测函数的勒贝格积分。

    使用简单函数逼近方法：将值域等分为 n 层，
    对每一层用示性函数构造逼近，取上确界。
    对于连续函数，勒贝格积分与黎曼积分一致，故可使用
    Riemann 积分数值近似。

    ∫ f dλ = lim_{n→∞} Σ_{k=0}^{n-1} (kΔy) · λ({x: kΔy ≤ f(x) < (k+1)Δy})

    Args:
        f: 非负函数，字符串表达式或可调用对象。
        domain: 定义域 (a, b)。
        n_steps: 逼近步数。

    Returns:
        MathObject: result 为积分值。
    """
    try:
        a, b = _parse_domain(domain)
        x = sp.Symbol("x", real=True)
        expr = parse_func(f, x)

        # 检查非负性
        f_lambda = sp.lambdify(x, expr, "numpy")
        test_points = np.linspace(a, b, 100)
        test_vals = f_lambda(test_points)

        if np.any(test_vals < -1e-10):
            return MathObject(
                error=f"函数在 [{a}, {b}] 上并非处处非负，负值出现在 f(...) = {np.min(test_vals)}。请使用 integral_general。"
            )

        # 使用 SciPy 做数值积分（连续函数勒贝格积分 = 黎曼积分）
        integral_val, _ = integrate.quad(
            lambda t: float(f_lambda(t)), a, b, limit=200
        )

        # 同时用简单函数逼近方法验证
        f_max = float(np.max(test_vals))
        dy = f_max / n_steps

        # 对每个层级 kΔy ≤ f(x) < (k+1)Δy 对应的 x 集合测度做近似
        mid_sum = 0.0
        for k in range(n_steps):
            y_low = k * dy
            y_mid = (k + 0.5) * dy
            # 用采样近似测度
            samples = np.linspace(a, b, 500)
            vals = f_lambda(samples)
            in_level = np.sum((vals >= y_low) & (vals < (k + 1) * dy))
            level_measure = (b - a) * (in_level / len(samples))
            mid_sum += y_mid * level_measure

        # 解析理论值
        sym_result = None
        try:
            sym_result = float(sp.integrate(expr, (x, a, b)).evalf())
        except Exception:
            pass

        steps = [
            f"函数: f(x) = {expr}, 定义域: [{a}, {b}]",
            f"SciPy 数值积分 (连续=勒贝格): {integral_val:.10f}",
            f"简单函数逼近 (n={n_steps}层): {mid_sum:.10f}",
        ]
        if sym_result is not None:
            steps.append(f"SymPy 解析积分: {sym_result:.10f}")

        return MathObject(
            result=integral_val,
            steps=steps,
            meaning=f"非负可测函数 f(x)={expr} 在 [{a}, {b}] 上的勒贝格积分",
            data={"n_steps": n_steps, "approximation": mid_sum},
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="integral_general")
def integral_general(
    f: Union[str, Callable],
    domain: Union[Tuple[float, float], List[float]] = (-1, 1),
    n_steps: int = 1000,
) -> MathObject:
    """计算一般可测函数的勒贝格积分（正部减负部）。

    f = f⁺ - f⁻，其中 f⁺ = max(f, 0)，f⁻ = max(-f, 0)。
    ∫ f dλ = ∫ f⁺ dλ - ∫ f⁻ dλ。

    要求 ∫ f⁺ dλ 和 ∫ f⁻ dλ 不同时为 ∞（即可积）。

    Args:
        f: 函数，字符串表达式或可调用对象。
        domain: 定义域 (a, b)。
        n_steps: 逼近步数。

    Returns:
        MathObject: result 为积分值。
    """
    try:
        a, b = _parse_domain(domain)
        x = sp.Symbol("x", real=True)
        expr = parse_func(f, x)

        f_lambda = sp.lambdify(x, expr, "numpy")

        def f_pos(t):
            return max(float(f_lambda(t)), 0.0)

        def f_neg(t):
            return max(-float(f_lambda(t)), 0.0)

        # 正部积分
        pos_integral, _ = integrate.quad(f_pos, a, b, limit=200)
        # 负部积分
        neg_integral, _ = integrate.quad(f_neg, a, b, limit=200)

        integral_val = pos_integral - neg_integral

        # 解析验证
        sym_result = None
        try:
            sym_result = float(sp.integrate(expr, (x, a, b)).evalf())
        except Exception:
            pass

        steps = [
            f"函数: f(x) = {expr}, 定义域: [{a}, {b}]",
            f"正部积分 ∫ f⁺ dλ = {pos_integral:.10f}",
            f"负部积分 ∫ f⁻ dλ = {neg_integral:.10f}",
            f"勒贝格积分 ∫ f dλ = {integral_val:.10f}",
        ]
        if sym_result is not None:
            steps.append(f"SymPy 解析积分: {sym_result:.10f}")

        return MathObject(
            result=integral_val,
            steps=steps,
            meaning=f"一般可测函数 f(x)={expr} 在 [{a}, {b}] 上的勒贝格积分 = 正部积分 - 负部积分",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="integral_zero_set_independent")
def integral_zero_set_independent(
    f: Union[str, Callable],
    g: Union[str, Callable],
    zero_set: Optional[List[float]] = None,
    domain: Union[Tuple[float, float], List[float]] = (0, 1),
) -> MathObject:
    """验证勒贝格积分的零测集无关性。

    若 f = g λ-a.e.（即除零测集外处处相等），
    则 ∫ f dλ = ∫ g dλ。
    即改变函数在零测集上的值不影响积分值。

    Args:
        f: 第一个函数。
        g: 第二个函数（应与 f λ-a.e. 相等）。
        zero_set: 差异所在的零测集点列表（可选）。
        domain: 积分区间。

    Returns:
        MathObject: result 为两个积分值是否一致。
    """
    try:
        a, b = _parse_domain(domain)
        x = sp.Symbol("x", real=True)
        expr_f = parse_func(f, x)
        expr_g = parse_func(g, x)

        f_lambda = sp.lambdify(x, expr_f, "numpy")
        g_lambda = sp.lambdify(x, expr_g, "numpy")

        int_f, _ = integrate.quad(lambda t: float(f_lambda(t)), a, b, limit=200)
        int_g, _ = integrate.quad(lambda t: float(g_lambda(t)), a, b, limit=200)

        are_equal = abs(int_f - int_g) < 1e-8

        # 找到差异点
        diff_expr = sp.simplify(expr_f - expr_g)
        diff_points = []
        if zero_set:
            diff_points = zero_set
        else:
            try:
                roots = sp.solve(diff_expr, x)
                diff_points = [
                    float(r.evalf())
                    for r in roots
                    if r.is_real and a <= float(r.evalf()) <= b
                ]
            except Exception:
                pass

        steps = [
            f"f(x) = {expr_f}",
            f"g(x) = {expr_g}",
            f"∫ f dλ = {int_f:.10f}",
            f"∫ g dλ = {int_g:.10f}",
            f"差异点: {diff_points}（测度为 0 或可数）",
            f"结论: {'一致' if are_equal else '不一致'}（期望一致，因为零测集不影响积分）",
        ]

        return MathObject(
            result=are_equal,
            steps=steps,
            meaning="若两个函数几乎处处相等，则其勒贝格积分相等",
        )

    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> tuple[int, int, int]:
    """lebesgue_integral 模块自测。返回 (passed, failed, errors)。"""
    print("=== lebesgue_integral self_test ===")
    passed, failed, errors = 0, 0, 0

    tests: list[tuple[str, callable, callable]] = [
        ("integral_nonnegative x^2 on (0,1)",
         lambda: integral_nonnegative("x**2", domain=(0, 1)),
         lambda r: r.ok and abs(r.result - 1/3) < 0.001),
        ("integral_general x on (-1,1)",
         lambda: integral_general("x", domain=(-1, 1)),
         lambda r: r.ok and abs(r.result) < 0.001),
        ("integral_simple",
         lambda: integral_simple({"coefficients": [1, 2], "sets": [[0, 0.5], [0.5, 1]]}),
         lambda r: r.ok and abs(r.result - 1.5) < 0.001),
        ("integral_zero_set_independent",
         lambda: integral_zero_set_independent("x**2", "x**2"),
         lambda r: r.ok and r.result is True),
    ]
    for name, fn, check in tests:
        try:
            r = fn()
            assert check(r), f"未通过: {r}"
            passed += 1
            print(f"  [PASS] {name} = {r.result if hasattr(r, 'result') else r}")
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:
            errors += 1
            print(f"  [ERROR] {name}: {e}")
    print(f"  lebesgue_integral 自测: {passed} pass, {failed} fail, {errors} error")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
