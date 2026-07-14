"""ode_solver.py — 常微分方程初值问题数值解。

包括欧拉方法、四阶龙格-库塔方法、隐式欧拉方法（刚性方程）、刚性检测。
"""

from __future__ import annotations

from typing import Callable, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="numerical", action="euler_method")
def euler_method(
    f: Union[str, Callable[[float, float], float]],
    t0: float,
    y0: float,
    t_end: float,
    h: float = 0.1,
) -> MathObject:
    """欧拉方法（前向，显式）求解 y' = f(t, y)。

    y_{n+1} = y_n + h * f(t_n, y_n)

    Args:
        f: 右端函数 f(t, y)，字符串或可调用对象。
        t0: 初始时间。
        y0: 初始值。
        t_end: 终止时间。
        h: 步长。

    Returns:
        MathObject: result 为 (t_values, y_values) 的 dict。
    """
    try:
        if isinstance(f, str):
            expr = f

            def f_fn(t: float, y: float) -> float:
                return float(eval(expr, {"__builtins__": {}}, {"t": t, "y": y, "np": np, "sin": np.sin, "cos": np.cos, "exp": np.exp, "log": np.log, "sqrt": np.sqrt}))
        else:
            f_fn = f

        n_steps = max(1, int(np.ceil((t_end - t0) / h)))
        h_actual = (t_end - t0) / n_steps

        t_vals = np.linspace(t0, t_end, n_steps + 1)
        y_vals = np.zeros(n_steps + 1)
        y_vals[0] = y0

        for i in range(n_steps):
            y_vals[i + 1] = y_vals[i] + h_actual * f_fn(t_vals[i], y_vals[i])

        return MathObject(
            result={"t": t_vals.tolist(), "y": y_vals.tolist()},
            steps=[
                f"初始条件: y({t0}) = {y0}",
                f"积分区间: [{t0}, {t_end}]",
                f"步长 h = {h_actual:.6f}, 步数 = {n_steps}",
                f"终点 y({t_end}) ≈ {y_vals[-1]:.10f}",
            ],
            meaning=f"欧拉法 (h={h_actual:.4f})，y({t_end}) ≈ {y_vals[-1]:.6f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="rk4")
def rk4(
    f: Union[str, Callable[[float, float], float]],
    t0: float,
    y0: float,
    t_end: float,
    h: float = 0.1,
) -> MathObject:
    """四阶龙格-库塔方法求解 y' = f(t, y)。

    k1 = h·f(t_n, y_n)
    k2 = h·f(t_n+h/2, y_n+k1/2)
    k3 = h·f(t_n+h/2, y_n+k2/2)
    k4 = h·f(t_n+h, y_n+k3)
    y_{n+1} = y_n + (k1+2k2+2k3+k4)/6

    Args:
        f: 右端函数 f(t, y)。
        t0: 初始时间。
        y0: 初始值。
        t_end: 终止时间。
        h: 步长。

    Returns:
        MathObject: result 为 (t_values, y_values) 的 dict。
    """
    try:
        if isinstance(f, str):
            expr = f

            def f_fn(t: float, y: float) -> float:
                return float(eval(expr, {"__builtins__": {}}, {"t": t, "y": y, "np": np, "sin": np.sin, "cos": np.cos, "exp": np.exp, "log": np.log, "sqrt": np.sqrt}))
        else:
            f_fn = f

        n_steps = max(1, int(np.ceil((t_end - t0) / h)))
        h_actual = (t_end - t0) / n_steps

        t_vals = np.linspace(t0, t_end, n_steps + 1)
        y_vals = np.zeros(n_steps + 1)
        y_vals[0] = y0

        for i in range(n_steps):
            tn = t_vals[i]
            yn = y_vals[i]
            k1 = f_fn(tn, yn)
            k2 = f_fn(tn + h_actual / 2, yn + h_actual * k1 / 2)
            k3 = f_fn(tn + h_actual / 2, yn + h_actual * k2 / 2)
            k4 = f_fn(tn + h_actual, yn + h_actual * k3)
            y_vals[i + 1] = yn + (h_actual / 6) * (k1 + 2 * k2 + 2 * k3 + k4)

        return MathObject(
            result={"t": t_vals.tolist(), "y": y_vals.tolist()},
            steps=[
                f"初始条件: y({t0}) = {y0}",
                f"积分区间: [{t0}, {t_end}]",
                f"步长 h = {h_actual:.6f}, 步数 = {n_steps}",
                f"终点 y({t_end}) ≈ {y_vals[-1]:.10f}",
            ],
            meaning=f"RK4 (h={h_actual:.4f})，y({t_end}) ≈ {y_vals[-1]:.6f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="implicit_euler")
def implicit_euler(
    f: Union[str, Callable[[float, float], float]],
    t0: float,
    y0: float,
    t_end: float,
    h: float = 0.1,
) -> MathObject:
    """隐式欧拉方法（后向欧拉）求解 y' = f(t, y)。

    y_{n+1} = y_n + h * f(t_{n+1}, y_{n+1})
    用牛顿迭代解隐含方程。

    适用于刚性方程组。

    Args:
        f: 右端函数 f(t, y)。
        t0: 初始时间。
        y0: 初始值。
        t_end: 终止时间。
        h: 步长。

    Returns:
        MathObject: result 为 (t_values, y_values) 的 dict。
    """
    try:
        if isinstance(f, str):
            expr = f

            def f_fn(t: float, y: float) -> float:
                return float(eval(expr, {"__builtins__": {}}, {"t": t, "y": y, "np": np, "sin": np.sin, "cos": np.cos, "exp": np.exp, "log": np.log, "sqrt": np.sqrt}))
        else:
            f_fn = f

        n_steps = max(1, int(np.ceil((t_end - t0) / h)))
        h_actual = (t_end - t0) / n_steps

        t_vals = np.linspace(t0, t_end, n_steps + 1)
        y_vals = np.zeros(n_steps + 1)
        y_vals[0] = y0

        for i in range(n_steps):
            tn1 = t_vals[i + 1]
            yn = y_vals[i]
            # 牛顿迭代求解 y_{n+1}
            y_next = yn  # 初始猜测
            for _ in range(20):
                residual = y_next - yn - h_actual * f_fn(tn1, y_next)
                # 数值雅可比 ∂F/∂y ≈ 1 - h * f'(tn1, y_next)
                eps = 1e-8
                f_pert = f_fn(tn1, y_next + eps)
                jac = 1.0 - h_actual * (f_pert - f_fn(tn1, y_next)) / eps
                if abs(jac) < 1e-15:
                    break
                delta = residual / jac
                y_next = y_next - delta
                if abs(delta) < 1e-12:
                    break
            y_vals[i + 1] = y_next

        return MathObject(
            result={"t": t_vals.tolist(), "y": y_vals.tolist()},
            steps=[
                f"初始条件: y({t0}) = {y0}",
                f"积分区间: [{t0}, {t_end}]",
                f"步长 h = {h_actual:.6f}, 步数 = {n_steps}",
                f"终点 y({t_end}) ≈ {y_vals[-1]:.10f}",
            ],
            meaning=f"隐式欧拉 (h={h_actual:.4f})，y({t_end}) ≈ {y_vals[-1]:.6f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="stiff_detector")
def stiff_detector(
    f: Union[str, Callable[[float, float], float]],
    t0: float,
    y0: float,
    t_end: float,
) -> MathObject:
    """刚性方程组检测。

    用显式欧拉和隐式欧拉在同一小步长下求解，
    若二者差异超过阈值，则提示方程可能为刚性。

    Args:
        f: 右端函数 f(t, y)。
        t0: 初始时间。
        y0: 初始值。
        t_end: 终止时间。

    Returns:
        MathObject: result 为 True/False，表示是否检测到刚性。
    """
    try:
        if isinstance(f, str):
            expr = f

            def f_fn(t: float, y: float) -> float:
                return float(eval(expr, {"__builtins__": {}}, {"t": t, "y": y, "np": np, "sin": np.sin, "cos": np.cos, "exp": np.exp, "log": np.log, "sqrt": np.sqrt}))
        else:
            f_fn = f

        h = min(0.01, (t_end - t0) / 100)

        # 显式欧拉
        r_exp = euler_method(f_fn, t0, y0, t0 + h * 5, h)
        y_exp = r_exp.result["y"][-1]

        # 隐式欧拉
        r_imp = implicit_euler(f_fn, t0, y0, t0 + h * 5, h)
        y_imp = r_imp.result["y"][-1]

        rel_diff = abs(y_exp - y_imp) / (abs(y_exp) + abs(y_imp) + 1e-15)
        is_stiff = rel_diff > 0.1

        return MathObject(
            result=is_stiff,
            steps=[
                f"步长 h = {h}，积分 5 步",
                f"显式欧拉结果: {y_exp:.6f}",
                f"隐式欧拉结果: {y_imp:.6f}",
                f"相对差异: {rel_diff:.4f}",
            ],
            meaning=f"{'检测到刚性' if is_stiff else '未检测到刚性'}，显隐式差异 {rel_diff:.4f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 ode_solver 模块。"""
    print("=== ode_solver self_test ===")
    passed = 0
    total = 4

    # Test 1: euler_method
    try:
        r = euler_method(lambda t, y: y, 0, 1, 1, 0.1)
        assert r.ok
        y_end = r.result["y"][-1]
        # y(t) = e^t, y(1) ≈ e ≈ 2.71828
        assert abs(y_end - np.exp(1)) < 0.5  # coarse check
        print(f"  [PASS] euler_method(y'=y): y(1)={y_end:.6f}, e={np.exp(1):.6f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] euler_method: {e}")

    # Test 2: rk4
    try:
        r = rk4(lambda t, y: y, 0, 1, 1, 0.1)
        assert r.ok
        y_end = r.result["y"][-1]
        assert abs(y_end - np.exp(1)) < 0.001
        print(f"  [PASS] rk4(y'=y): y(1)={y_end:.8f}, e={np.exp(1):.8f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] rk4: {e}")

    # Test 3: implicit_euler
    try:
        r = implicit_euler(lambda t, y: y, 0, 1, 1, 0.1)
        assert r.ok
        y_end = r.result["y"][-1]
        assert abs(y_end - np.exp(1)) < 0.5
        print(f"  [PASS] implicit_euler(y'=y): y(1)={y_end:.6f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] implicit_euler: {e}")

    # Test 4: stiff_detector
    try:
        r = stiff_detector(lambda t, y: y, 0, 1, 1)
        assert r.ok
        # y'=y is not stiff
        assert r.result is False
        print(f"  [PASS] stiff_detector(y'=y): is_stiff={r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] stiff_detector: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
