"""measurable_functions.py — 可测函数。

涵盖可测函数判定、简单函数构造、简单函数逼近等。
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import parse_func

from typing import Any, Callable, List, Optional, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
def _parse_domain(domain) -> Tuple[float, float]:
    """解析定义域为 (a, b) 区间。"""
    if isinstance(domain, (list, tuple)):
        if len(domain) == 2:
            return float(domain[0]), float(domain[1])
    raise ValueError(f"无法解析定义域: {domain}")


@register(module="measure_theory", action="is_measurable")
def is_measurable(
    f: Union[str, Callable],
    domain: Union[Tuple[float, float], List[float]] = (-10, 10),
    sigma_algebra: Any = None,
) -> MathObject:
    """判断函数 f 是否关于 Borel σ-代数可测。

    在勒贝格积分理论中，连续函数、单调函数、逐段连续函数
    都是 Borel 可测的。对于 sympy 表达式，通过检查定义域上
    的奇点来判断。

    Args:
        f: 函数，字符串表达式（以 x 为变量）或可调用对象。
        domain: 定义域 (a, b)，默认 (-10, 10)。
        sigma_algebra: (概念性参数，保留)。

    Returns:
        MathObject: result=True 表示可测。
    """
    try:
        a, b = _parse_domain(domain)
        x = sp.Symbol("x", real=True)
        expr = parse_func(f, x)

        steps = [f"函数: f(x) = {expr}", f"定义域: ({a}, {b})"]

        # 检查连续性（在定义域内是否有奇点）
        has_singularity = False
        try:
            singularities = sp.singularities(expr, x, interval=sp.Interval(a, b))
            if singularities:
                has_singularity = True
                steps.append(f"发现奇点: {singularities}")
        except Exception:
            # 如果 sympy 无法计算奇点，检查分母
            if expr.has(sp.Pow) or expr.is_rational_function():
                denom = sp.denom(expr)
                if denom != 1:
                    roots = sp.solve(denom, x)
                    real_roots = [
                        float(r.evalf()) for r in roots if r.is_real
                    ]
                    in_domain = [r for r in real_roots if a <= r <= b]
                    if in_domain:
                        has_singularity = True
                        steps.append(f"分母零点在定义域内: {in_domain}")

        if expr.is_constant():
            steps.append("常函数 → 可测")
            return MathObject(
                result=True,
                steps=steps,
                meaning="常函数是 Borel 可测的",
            )

        # 对于连续函数（无奇点），自动可测
        if not has_singularity:
            steps.append("函数在定义域内连续 → Borel 可测")
            return MathObject(
                result=True,
                steps=steps,
                meaning=f"f(x)={expr} 在 ({a}, {b}) 上连续，故为 Borel 可测函数",
            )

        # 有奇点时，通过可测集的逆像判定
        steps.append("存在奇点，但逐段连续函数仍为 Borel 可测")
        return MathObject(
            result=True,
            steps=steps,
            meaning=f"f(x)={expr} 在 ({a}, {b}) 上除去奇点外连续，故仍为勒贝格可测",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="simple_function")
def simple_function(
    values: List[float],
    sets: List[List[float]],
) -> MathObject:
    """构造简单函数 Σ c_i · 1_{E_i}。

    简单函数形如 φ(x) = Σ_{i=1}^n c_i · 1_{E_i}(x)，
    其中 E_i 为互不相交的可测集，c_i 为实常数。
    1_{E_i} 为示性函数。

    Args:
        values: 系数列表 [c_1, c_2, ..., c_n]。
        sets: 集合列表，每个为区间 [a_i, b_i]。

    Returns:
        MathObject: result 为包含表达式和可调用对象的字典。
    """
    try:
        if len(values) != len(sets):
            return MathObject(error=f"系数({len(values)})与集合({len(sets)})数量不匹配")

        steps = []
        expr_terms = []
        x = sp.Symbol("x", real=True)

        for i, (c, interval) in enumerate(zip(values, sets)):
            if len(interval) != 2:
                return MathObject(error=f"集合 {i} 不是区间: {interval}")
            a, b = float(interval[0]), float(interval[1])
            # 使用 Piecewise 或条件表达式
            steps.append(f"E_{i+1} = [{a}, {b}], c_{i+1} = {c}")
            expr_terms.append((c, (x >= a) & (x <= b)))

        # 构建分段函数
        piecewise = sp.Piecewise(*expr_terms, (0, True))
        expr_str = " + ".join(
            f"{c} · 1_[{interval[0]},{interval[1]}]"
            for c, interval in zip(values, sets)
        )

        def simple_func_eval(x_val):
            result = 0.0
            for c, interval in zip(values, sets):
                if interval[0] <= x_val <= interval[1]:
                    result += c
            return result

        return MathObject(
            result={
                "expression": piecewise,
                "string_form": expr_str,
                "callable": simple_func_eval,
                "coefficients": values,
                "sets": sets,
            },
            steps=steps,
            meaning=f"简单函数 φ(x) = {expr_str}",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="step_function_approx")
def step_function_approx(
    f: Union[str, Callable],
    n: int = 4,
    domain: Union[Tuple[float, float], List[float]] = (0, 1),
) -> MathObject:
    """用简单函数逼近可测函数。

    将定义域等分为 n 段，在每段上用函数在该段左端点的值
    构造阶梯函数（简单函数）。

    Args:
        f: 目标函数，字符串表达式或可调用对象。
        n: 分段数。
        domain: 定义域 (a, b)。

    Returns:
        MathObject: result 为逼近的简单函数信息。
    """
    try:
        a, b = _parse_domain(domain)
        x = sp.Symbol("x", real=True)
        expr = parse_func(f, x)

        dx = (b - a) / n
        values = []
        intervals = []

        f_lambda = sp.lambdify(x, expr, "numpy")

        for i in range(n):
            left = a + i * dx
            right = a + (i + 1) * dx
            val = float(f_lambda(left))
            values.append(val)
            intervals.append([left, right])

        expr_str = " + ".join(
            f"{values[i]:.4f} · 1_[{intervals[i][0]:.4f}, {intervals[i][1]:.4f}]"
            for i in range(n)
        )

        steps = [
            f"目标函数: f(x) = {expr}",
            f"定义域: [{a}, {b}]，等分 n={n} 段",
            f"每段长度 dx = {dx}",
            f"逼近简单函数: φ_n(x) = {expr_str}",
        ]

        return MathObject(
            result={
                "expression": expr_str,
                "values": values,
                "intervals": intervals,
                "n": n,
                "dx": dx,
            },
            steps=steps,
            meaning=f"用 n={n} 段阶梯函数逼近 f(x)={expr}",
        )

    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """measurable_functions 模块自测。"""
    print("=== measurable_functions self_test ===")
    all_ok = True

    # 测试 1: is_measurable 多项式
    r = is_measurable("x**2")
    assert r.ok and r.result is True, f"失败: {r}"
    print(f"  [PASS] is_measurable('x**2') = {r.result}")

    # 测试 2: is_measurable 连续函数
    r = is_measurable("sin(x)")
    assert r.ok and r.result is True, f"失败: {r}"
    print(f"  [PASS] is_measurable('sin(x)') = {r.result}")

    # 测试 3: simple_function
    r = simple_function([1, 2, 3], [[0, 0.3], [0.3, 0.6], [0.6, 1.0]])
    assert r.ok, f"失败: {r}"
    assert len(r.result["coefficients"]) == 3, f"失败: {r}"
    print(f"  [PASS] simple_function: {r.result['string_form']}")

    # 测试 4: step_function_approx
    r = step_function_approx("x**2", n=4, domain=(0, 1))
    assert r.ok, f"失败: {r}"
    assert len(r.result["intervals"]) == 4, f"失败: {r}"
    print(f"  [PASS] step_function_approx('x**2', n=4)")

    print("=== measurable_functions: ALL PASSED ===\n")
    return all_ok


if __name__ == "__main__":
    self_test()
