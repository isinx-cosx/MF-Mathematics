"""随机变量 — 经验分布函数、离散/连续型分布列与密度函数、期望。

依赖: numpy, sympy
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import sympy as sp
from sympy import Symbol, oo

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="probability", action="distribution_function")
def distribution_function(
    data: List[float],
    x: Optional[float] = None,
) -> MathObject:
    """计算经验分布函数 F_n(x) = #{xi ≤ x} / n。

    Args:
        data: 样本数据列表。
        x: 计算经验分布函数的值点。若不传，返回 (sorted_data, F_values) 对。

    Returns:
        MathObject:
            - result: 若传入 x，返回 F_n(x) 值；否则返回 (sorted_x, F_vals) 元组。
    """
    try:
        n = len(data)
        if n == 0:
            return MathObject(error="样本数据为空。")

        sorted_data = sorted(data)

        if x is not None:
            count = sum(1 for d in data if d <= x)
            return MathObject(
                result=count / n,
                steps=[
                    f"样本量 n = {n}",
                    f"≤ {x} 的观测数 = {count}",
                    f"F_n({x}) = {count}/{n} = {count / n:.4f}",
                ],
                meaning=f"经验分布函数在 x={x} 处的值，近似 P(X ≤ {x})。",
            )

        # 返回完整分布
        x_vals = sorted_data
        f_vals = [(i + 1) / n for i in range(n)]

        return MathObject(
            result=(x_vals, f_vals),
            steps=[f"样本量 n = {n}", "计算各点的累计比例"],
            meaning="经验分布函数，是真实分布的估计。",
            data={"x": x_vals, "F": f_vals},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="pmf")
def pmf(
    values: List[Union[float, str]],
    probs: List[float],
) -> MathObject:
    """定义离散型随机变量的分布列（概率质量函数）。

    Args:
        values: 随机变量的取值列表。
        probs: 对应的概率列表（必须非负且和为 1）。

    Returns:
        MathObject:
            - result: 分布列字典 {value: probability}。
    """
    try:
        if len(values) != len(probs):
            return MathObject(error="取值列表和概率列表长度必须相同。")

        probs_arr = np.array(probs, dtype=float)
        if np.any(probs_arr < 0):
            return MathObject(error="概率必须非负。")

        total = probs_arr.sum()
        if abs(total - 1.0) > 0.01:
            probs_arr = probs_arr / total
            steps = [f"概率和 = {total:.4f}，已归一化。"]
        else:
            steps = [f"概率和 = 1，合法分布列。"]

        dist = dict(zip(values, probs_arr.tolist()))
        return MathObject(
            result=dist,
            steps=steps,
            meaning="离散型随机变量的概率质量函数（PMF）。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="pdf")
def pdf(
    expr: str,
    var: str = "x",
) -> MathObject:
    """定义连续型随机变量的概率密度函数（符号形式）。

    用法: pdf("exp(-x)", "x")，domain 参数控制自变量范围。

    Args:
        expr: 密度函数表达式字符串（sympy 语法）。
        var: 自变量符号名。

    Returns:
        MathObject:
            - result: sympy 表达式。
            - data: 包含 var 和 domain 信息。
    """
    try:
        from sympy.parsing.sympy_parser import parse_expr

        x = Symbol(var)
        density = parse_expr(expr, local_dict={var: x})

        return MathObject(
            result=density,
            steps=[
                f"自变量: {var}",
                f"密度函数: f({var}) = {sp.pretty(density)}",
            ],
            meaning="连续型随机变量的概率密度函数（PDF），积分归一化后合法。",
            data={"var": var, "expr": str(density)},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="expectation_rv")
def expectation(
    expr: Union[str, sp.Expr],
    var: str = "x",
    domain: Optional[Tuple[float, float]] = None,
    pmf_data: Optional[Dict] = None,
) -> MathObject:
    """计算随机变量的期望 E[g(X)]。

    离散型（提供 pmf_data）: E[g(X)] = Σ g(xi)·pi。
    连续型（提供 domain）: E[g(X)] = ∫ g(x)·f(x) dx。

    Args:
        expr: g(X) 的表达式字符串或 sympy 表达式。
        var: 自变量符号名。
        domain: 连续型变量的积分区间 (a, b)。None 表示离散型。
        pmf_data: 离散型分布列 dict，如 {"values": [...], "probs": [...]}。

    Returns:
        MathObject:
            - result: 期望值。
    """
    try:
        from sympy.parsing.sympy_parser import parse_expr

        x = Symbol(var)
        g = parse_expr(str(expr), local_dict={var: x}) if isinstance(expr, str) else expr

        if pmf_data is not None:
            # 离散型
            values = pmf_data["values"]
            probs = pmf_data["probs"]
            total = sp.Rational(0)
            steps_detail = []
            for vi, pi in zip(values, probs):
                term = g.subs(x, vi) * sp.Rational(pi)
                total += term
                steps_detail.append(f"g({vi})·{pi} = {float(term.evalf()):.4f}")
            return MathObject(
                result=float(total.evalf()),
                steps=["离散型期望: E[g(X)] = Σ g(xi)·pi"] + steps_detail,
                meaning=f"随机变量 g(X) 的数学期望（离散型）。",
            )

        elif domain is not None:
            # 连续型 — 需要密度函数在 g 里隐含，或 g 就是 x*f(x)
            a, b = domain
            total = sp.integrate(g, (x, a, b))
            return MathObject(
                result=float(total.evalf()),
                steps=[
                    f"连续型期望: E[g(X)] = ∫_{a}^{b} g(x) dx",
                    f"积分结果: {total}",
                ],
                meaning=f"随机变量 g(X) 的数学期望（连续型，积分区间 [{a}, {b}]）。",
            )
        else:
            return MathObject(error="请提供 pmf_data（离散型）或 domain（连续型）。")
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """模块自测。"""
    print("=== random_variable 自测 ===")

    # 经验分布函数
    data = [1, 3, 5, 7, 9]
    r1 = distribution_function(data, x=5)
    assert r1.ok, r1.error
    # 小于等于5的有1,3,5共3个，n=5 → 0.6
    assert abs(r1.result - 0.6) < 0.01, r1.result
    print(f"  distribution_function: F(5) = {r1.result}  PASSED")

    # PMF
    r2 = pmf(["H", "T"], [0.5, 0.5])
    assert r2.ok, r2.error
    assert r2.result["H"] == 0.5
    print(f"  pmf: {r2.result}  PASSED")

    # PDF
    r3 = pdf("exp(-x)", "x")
    assert r3.ok, r3.error
    print(f"  pdf: {r3.result}  PASSED")

    # 期望（离散型）
    r4 = expectation(
        "x",
        var="x",
        pmf_data={"values": [0, 1], "probs": [0.5, 0.5]},
    )
    assert r4.ok, r4.error
    assert abs(r4.result - 0.5) < 0.01, r4.result
    print(f"  expectation (离散): {r4.result}  PASSED")

    # 期望（连续型）: E[X] for uniform [0,1] → ∫ x dx = 0.5
    r5 = expectation("x", var="x", domain=(0, 1))
    assert r5.ok, r5.error
    assert abs(r5.result - 0.5) < 0.01, r5.result
    print(f"  expectation (连续): {r5.result}  PASSED")

    print("random_variable 自测全部通过!\n")
    return True


if __name__ == "__main__":
    self_test()
