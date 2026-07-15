"""numerical_integration.py — 数值积分与微分。

包括牛顿-柯特斯公式（梯形法则、辛普森法则）、高斯求积、数值微分。
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import parse_func

from typing import Callable, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register
@register(module="numerical", action="trapezoidal_rule")
def trapezoidal_rule(
    f: Union[str, Callable[[float], float]],
    a: float,
    b: float,
    n: int = 100,
    var: str = "x",
) -> MathObject:
    """梯形法则（复合）数值积分。

    ∫_a^b f(x) dx ≈ h * [f(x₀)/2 + f(x₁) + ... + f(x_{n-1}) + f(xₙ)/2]

    Args:
        f: 被积函数，字符串（如 "sin(x)"）或可调用对象。
        a: 积分下限。
        b: 积分上限。
        n: 子区间数。

    Returns:
        MathObject: result 为积分近似值（float）。
    """
    try:
        f_fn = parse_func(f, var)
        x = np.linspace(a, b, n + 1)
        y = np.array([f_fn(xi) for xi in x])
        h = (b - a) / n
        integral = h * (0.5 * y[0] + np.sum(y[1:-1]) + 0.5 * y[-1])

        return MathObject(
            result=float(integral),
            steps=[
                f"积分区间: [{a}, {b}]",
                f"子区间数: {n}, 步长 h = {h:.6f}",
                f"梯形近似值 = {integral:.10f}",
            ],
            meaning=f"梯形法则 (n={n}) 积分近似值 = {integral:.8f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="simpson_rule")
def simpson_rule(
    f: Union[str, Callable[[float], float]],
    a: float,
    b: float,
    n: int = 100,
    var: str = "x",
) -> MathObject:
    """辛普森法则（复合）数值积分。

    n 必须为偶数。每个子区间用二次多项式近似。

    Args:
        f: 被积函数。
        a: 积分下限。
        b: 积分上限。
        n: 子区间数（必须为偶数，否则自动调整为偶数）。

    Returns:
        MathObject: result 为积分近似值（float）。
    """
    try:
        if n % 2 != 0:
            n += 1
        f_fn = parse_func(f, var)
        x = np.linspace(a, b, n + 1)
        y = np.array([f_fn(xi) for xi in x])
        h = (b - a) / n
        integral = h / 3 * (y[0] + y[-1] + 4 * np.sum(y[1:-1:2]) + 2 * np.sum(y[2:-2:2]))

        return MathObject(
            result=float(integral),
            steps=[
                f"积分区间: [{a}, {b}]",
                f"子区间数: {n}, 步长 h = {h:.6f}",
                f"辛普森近似值 = {integral:.10f}",
            ],
            meaning=f"辛普森法则 (n={n}) 积分近似值 = {integral:.8f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="gauss_quadrature")
def gauss_quadrature(
    f: Union[str, Callable[[float], float]],
    a: float,
    b: float,
    n: int = 3,
) -> MathObject:
    """高斯-勒让德求积。

    支持 n=2,3,4 个节点。

    Args:
        f: 被积函数。
        a: 积分下限。
        b: 积分上限。
        n: 节点数（2、3 或 4）。

    Returns:
        MathObject: result 为积分近似值（float）。
    """
    try:
        if n not in (2, 3, 4):
            return MathObject(error="高斯求积目前仅支持 n=2,3,4")

        # 高斯-勒让德节点和权重（区间 [-1,1]）
        gauss_data = {
            2: {
                "nodes": np.array([-0.5773502691896257, 0.5773502691896257]),
                "weights": np.array([1.0, 1.0]),
            },
            3: {
                "nodes": np.array([-0.7745966692414834, 0.0, 0.7745966692414834]),
                "weights": np.array([0.5555555555555556, 0.8888888888888888, 0.5555555555555556]),
            },
            4: {
                "nodes": np.array([-0.8611363115940526, -0.3399810435848563, 0.3399810435848563, 0.8611363115940526]),
                "weights": np.array([0.3478548451374538, 0.6521451548625461, 0.6521451548625461, 0.3478548451374538]),
            },
        }

        data = gauss_data[n]
        nodes = data["nodes"]
        weights = data["weights"]

        f_fn = parse_func(f, var)
        # 变换到 [a,b]
        mid = (b + a) / 2
        half = (b - a) / 2
        x_transformed = mid + half * nodes
        values = np.array([f_fn(xi) for xi in x_transformed])
        integral = half * np.sum(weights * values)

        return MathObject(
            result=float(integral),
            steps=[
                f"积分区间: [{a}, {b}] → 变换到 [-1, 1]",
                f"高斯节点数: {n}",
                f"高斯求积值 = {integral:.10f}",
            ],
            meaning=f"{n} 点高斯-勒让德求积 = {integral:.8f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="numerical_derivative")
def numerical_derivative(
    f: Union[str, Callable[[float], float]],
    x: float,
    h: float = 1e-6,
    method: str = "central",
) -> MathObject:
    """数值微分。

    支持前向差分、后向差分和中心差分。

    Args:
        f: 目标函数。
        x: 求导点。
        h: 步长。
        method: 差分方法 — 'forward'（O(h)）、'backward'（O(h)）、'central'（O(h²)）。

    Returns:
        MathObject: result 为导数值（float）。
    """
    try:
        f_fn = parse_func(f, var)
        if method == "forward":
            deriv = (f_fn(x + h) - f_fn(x)) / h
            order = "O(h)"
        elif method == "backward":
            deriv = (f_fn(x) - f_fn(x - h)) / h
            order = "O(h)"
        elif method == "central":
            deriv = (f_fn(x + h) - f_fn(x - h)) / (2 * h)
            order = "O(h²)"
        else:
            return MathObject(error=f"未知方法: {method}，可选 forward/backward/central")

        return MathObject(
            result=float(deriv),
            steps=[
                f"求导点 x = {x}",
                f"步长 h = {h}",
                f"方法: {method} ({order})",
                f"f'({x}) ≈ {deriv:.10f}",
            ],
            meaning=f"{method} 差分 (h={h}) 导数 ≈ {deriv:.8f}，精度 {order}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="optimal_step")
def optimal_step(
    f: Union[str, Callable[[float], float]],
    x: float,
    method: str = "central",
) -> MathObject:
    """寻找数值微分的黄金步长（最优 h）。

    通过最小化截断误差 + 舍入误差的近似和来估计最优步长。

    Args:
        f: 目标函数。
        x: 求导点。
        method: 差分方法。

    Returns:
        MathObject: result 为最优步长（float）。
    """
    try:
        f_fn = parse_func(f, var)
        eps_machine = np.finfo(float).eps

        # 估计函数值的量级
        f_val = abs(f_fn(x)) + 1e-15

        if method == "central":
            # 中心差分 O(h²): 最优 h ≈ ε^{1/3}
            h_opt = eps_machine ** (1 / 3) * f_val
        elif method in ("forward", "backward"):
            # 前向/后向 O(h): 最优 h ≈ ε^{1/2}
            h_opt = eps_machine ** (1 / 2) * f_val
        else:
            h_opt = eps_machine ** (1 / 3) * f_val * 0.1

        # 缩放到一个合理范围
        h_opt = max(h_opt, 1e-12)
        h_opt = min(h_opt, 0.1)

        return MathObject(
            result=float(h_opt),
            steps=[
                f"机器精度 ε = {eps_machine:.2e}",
                f"函数值量级 ≈ {f_val:.2e}",
                f"最优步长估计: {h_opt:.2e}",
            ],
            meaning=f"数值微分最优步长约 {h_opt:.2e}，平衡截断误差与舍入误差",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 numerical_integration 模块。"""
    print("=== numerical_integration self_test ===")
    passed = 0
    total = 5

    # Test 1: trapezoidal_rule
    try:
        r = trapezoidal_rule("sin(x)", 0, np.pi, 100)
        assert r.ok
        assert abs(r.result - 2.0) < 0.001
        print(f"  [PASS] trapezoidal_rule(sin, 0, pi): {r.result:.6f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] trapezoidal_rule: {e}")

    # Test 2: simpson_rule
    try:
        r = simpson_rule("sin(x)", 0, np.pi, 100)
        assert r.ok
        assert abs(r.result - 2.0) < 0.0001
        print(f"  [PASS] simpson_rule(sin, 0, pi): {r.result:.8f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] simpson_rule: {e}")

    # Test 3: gauss_quadrature
    try:
        r = gauss_quadrature("x**2", 0, 1, n=3)
        assert r.ok
        assert abs(r.result - 1 / 3) < 0.0001
        print(f"  [PASS] gauss_quadrature(x², 0, 1): {r.result:.6f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] gauss_quadrature: {e}")

    # Test 4: numerical_derivative
    try:
        r = numerical_derivative("x**3", 2.0, method="central")
        assert r.ok
        assert abs(r.result - 12.0) < 0.001
        print(f"  [PASS] numerical_derivative(x³, x=2, central): {r.result:.6f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] numerical_derivative: {e}")

    # Test 5: optimal_step
    try:
        r = optimal_step("x**2", 1.0, method="central")
        assert r.ok
        assert r.result > 0
        print(f"  [PASS] optimal_step(x², x=1): h_opt={r.result:.2e}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] optimal_step: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
