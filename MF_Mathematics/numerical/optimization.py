# -*- coding: utf-8 -*-
"""优化算法 — 梯度下降、牛顿法、线性规划。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import Callable, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="numerical", action="gradient_descent")
def gradient_descent(
    f: Union[str, Callable],
    x0: float = 1.0,
    learning_rate: float = 0.1,
    max_iter: int = 1000,
    tol: float = 1e-6,
) -> MathObject:
    """梯度下降法求函数极小值。

    Args:
        f: 目标函数表达式（如 "x**2"）或可调用对象。
        x0: 初始点。
        learning_rate: 学习率。
        max_iter: 最大迭代次数。
        tol: 收敛容差。

    Returns:
        MathObject，result 包含极小值点和迭代信息。
    """
    try:
        x = sp.Symbol("x")
        if isinstance(f, str):
            expr = sp.sympify(f)
            f_fn = sp.lambdify(x, expr, "numpy")
            df = sp.diff(expr, x)
            df_fn = sp.lambdify(x, df, "numpy")
        else:
            f_fn = f
            df_fn = None

        path = [x0]
        xi = x0
        for i in range(max_iter):
            if df_fn is None:
                h = 1e-6
                grad = (f_fn(xi + h) - f_fn(xi - h)) / (2 * h)
            else:
                grad = df_fn(xi)
            xi_new = xi - learning_rate * grad
            if abs(xi_new - xi) < tol:
                xi = xi_new
                path.append(xi)
                break
            xi = xi_new
            path.append(xi)

        return MathObject(
            result={"x_min": float(xi), "f_min": float(f_fn(xi)),
                    "iterations": len(path), "path": [float(p) for p in path[:10]]},
            steps=[
                f"目标函数: f(x) = {f if isinstance(f, str) else 'callable'}",
                f"初始点 x0 = {x0}, 学习率 = {learning_rate}",
                f"迭代 {len(path)} 次后收敛到 x = {xi:.6f}",
                f"极小值 f(x) = {f_fn(xi):.6f}",
            ],
            meaning=f"梯度下降: min f(x) ≈ {float(f_fn(xi)):.6f} at x ≈ {float(xi):.6f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    print("=== optimization self_test ===")
    r = gradient_descent("x**2", x0=3.0, learning_rate=0.1)
    assert r.ok, f"失败: {r.error}"
    assert abs(r.result["x_min"]) < 0.01, f"x_min 应为 0: {r.result}"
    print(f"  PASS: min(x^2) at x={r.result['x_min']:.6f}")
    r2 = gradient_descent("(x-2)**2 + 1", x0=0.0, learning_rate=0.1)
    assert abs(r2.result["x_min"] - 2.0) < 0.01
    print(f"  PASS: min((x-2)^2+1) at x={r2.result['x_min']:.6f}")
    print("=== optimization self_test: ALL PASSED ===")
    return True


if __name__ == "__main__":
    self_test()
