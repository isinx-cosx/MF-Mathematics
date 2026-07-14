"""期望与方差 — 期望、方差、协方差、相关系数。

依赖: numpy, sympy
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import sympy as sp
from sympy import Symbol

from ..core.math_object import MathObject
from ..core.registry import register


def _prepare_data(
    data: Union[List[float], np.ndarray],
) -> np.ndarray:
    """转为 numpy 数组。"""
    return np.asarray(data, dtype=float)


@register(module="probability", action="expectation")
def expectation(
    data: Optional[List[float]] = None,
    expr: Optional[str] = None,
    var: str = "x",
    pmf_data: Optional[Dict] = None,
    domain: Optional[Tuple[float, float]] = None,
) -> MathObject:
    """计算期望 E[X] 或 E[g(X)]。

    三种模式：
    1. 数值样本 data → 样本均值 E[X]。
    2. 离散型 (pmf_data) → Σ xi·pi。
    3. 连续型 (domain + expr) → ∫ g(x)·f(x) dx（expr 为 x*f(x) 时即期望）。

    Args:
        data: 数值样本列表（计算样本均值）。
        expr: g(X) 表达式字符串（连续型模式）。
        var: 自变量符号名。
        pmf_data: 离散分布列 {"values": [...], "probs": [...]}。
        domain: 积分区间 (a, b)。

    Returns:
        MathObject:
            - result: 期望值。
    """
    try:
        if data is not None:
            arr = _prepare_data(data)
            return MathObject(
                result=float(np.mean(arr)),
                steps=[f"样本容量 n = {len(arr)}", f"样本均值 = {np.mean(arr):.6f}"],
                meaning="样本均值是总体期望的无偏估计。",
            )

        if pmf_data is not None:
            values = pmf_data["values"]
            probs = pmf_data["probs"]
            total = sum(np.asarray(values, dtype=float) * np.asarray(probs, dtype=float))
            return MathObject(
                result=float(total),
                steps=[f"离散型期望 E[X] = Σ xi·pi = {total:.6f}"],
                meaning="离散型随机变量的数学期望。",
            )

        if expr is not None and domain is not None:
            from sympy.parsing.sympy_parser import parse_expr

            x = Symbol(var)
            g = parse_expr(expr, local_dict={var: x})
            a, b = domain
            result = sp.integrate(g, (x, a, b))
            return MathObject(
                result=float(result.evalf()),
                steps=[f"连续型期望: ∫_{a}^{b} {expr} dx = {result}"],
                meaning="连续型随机变量的数学期望。",
            )

        return MathObject(error="请提供 data（样本）、pmf_data（离散型）或 expr+domain（连续型）。")
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="variance")
def variance(
    data: Optional[List[float]] = None,
    expr: Optional[str] = None,
    var: str = "x",
    pmf_data: Optional[Dict] = None,
    domain: Optional[Tuple[float, float]] = None,
) -> MathObject:
    """计算方差 Var(X) = E[X²] - (E[X])²。

    三种模式同 expectation。

    Args:
        data: 数值样本列表（计算样本方差 ddof=1）。
        expr: 密度相关表达式（连续型）。
        var: 自变量符号名。
        pmf_data: 离散分布列。
        domain: 积分区间。

    Returns:
        MathObject:
            - result: 方差值。
            - steps: 计算过程。
    """
    try:
        if data is not None:
            arr = _prepare_data(data)
            var_val = float(np.var(arr, ddof=1))
            return MathObject(
                result=var_val,
                steps=[
                    f"样本容量 n = {len(arr)}",
                    f"样本均值 = {np.mean(arr):.6f}",
                    f"样本方差 (s², ddof=1) = {var_val:.6f}",
                ],
                meaning="样本方差是总体方差的无偏估计。",
            )

        if pmf_data is not None:
            values = np.asarray(pmf_data["values"], dtype=float)
            probs = np.asarray(pmf_data["probs"], dtype=float)
            mean_val = np.sum(values * probs)
            var_val = np.sum((values**2) * probs) - mean_val**2
            return MathObject(
                result=float(var_val),
                steps=[
                    f"E[X] = {mean_val:.6f}",
                    f"E[X²] = {np.sum(values**2 * probs):.6f}",
                    f"Var(X) = E[X²] - (E[X])² = {var_val:.6f}",
                ],
                meaning="离散型随机变量的方差。",
            )

        if expr is not None and domain is not None:
            from sympy.parsing.sympy_parser import parse_expr

            x = Symbol(var)
            g = parse_expr(expr, local_dict={var: x})
            a, b = domain

            # E[X]
            mean_val = sp.integrate(x * g, (x, a, b))
            # E[X²]
            second_moment = sp.integrate(x**2 * g, (x, a, b))
            var_val = second_moment - mean_val**2

            return MathObject(
                result=float(var_val.evalf()),
                steps=[
                    f"E[X] = ∫_{a}^{b} x·f(x) dx = {float(mean_val.evalf()):.6f}",
                    f"E[X²] = ∫_{a}^{b} x²·f(x) dx = {float(second_moment.evalf()):.6f}",
                    f"Var(X) = {float(var_val.evalf()):.6f}",
                ],
                meaning="连续型随机变量的方差。",
            )

        return MathObject(error="请提供 data、pmf_data 或 expr+domain。")
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="covariance")
def covariance(
    X: Union[List[float], np.ndarray],
    Y: Union[List[float], np.ndarray],
    joint_dist: Optional[Dict] = None,
) -> MathObject:
    """计算协方差 Cov(X, Y) = E[XY] - E[X]E[Y]。

    Args:
        X: 变量 X 的观测值或取值列表。
        Y: 变量 Y 的观测值或取值列表。
        joint_dist: 联合分布（可选）。格式: {"values": [(x1,y1), ...], "probs": [p1, ...]}。

    Returns:
        MathObject:
            - result: 协方差值。
    """
    try:
        X_arr = _prepare_data(X)
        Y_arr = _prepare_data(Y)

        if joint_dist is not None:
            xy_pairs = joint_dist["values"]
            probs = np.asarray(joint_dist["probs"], dtype=float)
            xy_arr = np.array(xy_pairs)
            X_vals = xy_arr[:, 0].astype(float)
            Y_vals = xy_arr[:, 1].astype(float)
            e_xy = np.sum(X_vals * Y_vals * probs)
            e_x = np.sum(X_vals * probs)
            e_y = np.sum(Y_vals * probs)
            cov_val = e_xy - e_x * e_y
        else:
            # 样本协方差
            n = len(X_arr)
            cov_val = np.cov(X_arr, Y_arr, ddof=1)[0, 1]

        sign = "正相关" if cov_val > 0 else ("负相关" if cov_val < 0 else "无关")
        return MathObject(
            result=float(cov_val),
            steps=[
                f"E[X] = {np.mean(X_arr):.4f}",
                f"E[Y] = {np.mean(Y_arr):.4f}",
                f"{'E[XY] = ' + str(np.mean(X_arr * Y_arr)) if joint_dist is None else '依联合分布计算'}",
                f"Cov(X, Y) = {cov_val:.6f}",
            ],
            meaning=f"协方差为 {cov_val:.4f}，{sign}。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="correlation_coefficient")
def correlation_coefficient(
    X: Union[List[float], np.ndarray],
    Y: Union[List[float], np.ndarray],
    joint_dist: Optional[Dict] = None,
) -> MathObject:
    """计算相关系数 ρ = Cov(X,Y) / (σ_X·σ_Y)。

    Args:
        X: X 观测值。
        Y: Y 观测值。
        joint_dist: 联合分布（同 covariance）。

    Returns:
        MathObject:
            - result: 相关系数 ρ ∈ [-1, 1]。
    """
    try:
        X_arr = _prepare_data(X)
        Y_arr = _prepare_data(Y)

        cov_result = covariance(X_arr, Y_arr, joint_dist)
        if cov_result.error:
            return cov_result

        cov_val = cov_result.result

        if joint_dist is not None:
            xy_pairs = joint_dist["values"]
            probs = np.asarray(joint_dist["probs"], dtype=float)
            xy_arr = np.array(xy_pairs)
            X_vals = xy_arr[:, 0].astype(float)
            Y_vals = xy_arr[:, 1].astype(float)
            e_x = np.sum(X_vals * probs)
            e_y = np.sum(Y_vals * probs)
            var_x = np.sum((X_vals**2) * probs) - e_x**2
            var_y = np.sum((Y_vals**2) * probs) - e_y**2
        else:
            var_x = np.var(X_arr, ddof=1)
            var_y = np.var(Y_arr, ddof=1)

        denom = np.sqrt(var_x * var_y)
        if abs(denom) < 1e-15:
            return MathObject(error="标准差为零，相关系数无定义。")

        rho = cov_val / denom
        strength = (
            "强" if abs(rho) > 0.7 else ("中等" if abs(rho) > 0.3 else "弱")
        )

        return MathObject(
            result=float(rho),
            steps=[
                f"Cov(X, Y) = {cov_val:.6f}",
                f"σ_X = {np.sqrt(var_x):.6f}",
                f"σ_Y = {np.sqrt(var_y):.6f}",
                f"ρ = {rho:.6f}",
            ],
            meaning=f"{'正' if rho > 0 else ('负' if rho < 0 else '零')}"
                    f"相关，强度: {strength}。",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """模块自测。"""
    print("=== expectations 自测 ===")

    # 期望（样本）
    r1 = expectation(data=[1, 2, 3, 4, 5])
    assert r1.ok and abs(r1.result - 3.0) < 0.01, r1.error
    print(f"  expectation (样本): {r1.result}  PASSED")

    # 方差（样本）
    r2 = variance(data=[1, 2, 3, 4, 5])
    assert r2.ok, r2.error
    # s² = Σ(x - x̄)²/(n-1) = 10/4 = 2.5
    assert abs(r2.result - 2.5) < 0.01, r2.result
    print(f"  variance (样本): {r2.result}  PASSED")

    # 协方差
    r3 = covariance([1, 2, 3], [2, 4, 6])
    assert r3.ok, r3.error
    assert r3.result > 0, r3.result
    print(f"  covariance: {r3.result:.4f}  PASSED")

    # 相关系数（完全正相关）
    r4 = correlation_coefficient([1, 2, 3], [2, 4, 6])
    assert r4.ok, r4.error
    assert abs(r4.result - 1.0) < 0.01, r4.result
    print(f"  correlation_coefficient: {r4.result}  PASSED")

    # 相关系数（完全负相关）
    r5 = correlation_coefficient([1, 2, 3], [3, 2, 1])
    assert r5.ok, r5.error
    assert abs(r5.result + 1.0) < 0.01, r5.result
    print(f"  correlation_coefficient (负): {r5.result}  PASSED")

    print("expectations 自测全部通过!\n")
    return True


if __name__ == "__main__":
    self_test()
