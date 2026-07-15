"""error_stability.py — 误差与稳定性分析。

包括条件数计算、截断误差估计、舍入误差估计、算法稳定性判断。
"""

from __future__ import annotations

from typing import Any, Callable, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="numerical", action="condition_number")
def condition_number(
    f: Union[str, Callable[[float], float]], x: float, eps: float = 1e-8
) -> MathObject:
    """计算函数 f 在点 x 处的条件数。

    条件数定义为 |x * f'(x) / f(x)|，度量输入扰动如何放大到输出。

    Args:
        f: 函数表达式字符串（如 "1/x"）或可调用对象。
        x: 求值点。
        eps: 数值微分的步长。

    Returns:
        MathObject: result 为条件数（float）。
    """
    try:
        if isinstance(f, str):
            import sympy as sp
            # 从表达式字符串中提取变量名
            var = "x"
            import re as _re_cn
            symbols = _re_cn.findall(r'[a-zA-Z]\b', f)
            if symbols:
                for s in symbols:
                    if s not in ("sin", "cos", "tan", "exp", "log", "sqrt", "abs",
                                 "sinh", "cosh", "tanh", "asin", "acos", "atan"):
                        var = s
                        break
            f_fn = sp.lambdify(sp.Symbol(var), sp.sympify(f), "numpy")
            expr = f
        else:
            f_fn = f
            expr = f.__name__ if hasattr(f, "__name__") else "f"

        fx = f_fn(x)
        if abs(fx) < 1e-15:
            return MathObject(
                result=float("inf"),
                steps=[
                    f"计算 f({x}) = {fx}",
                    "f(x) 接近 0，条件数趋于无穷",
                ],
                meaning=f"函数 {expr} 在 x={x} 处条件数无穷大（输出对输入扰动极度敏感）",
            )

        f_prime = (f_fn(x + eps) - f_fn(x - eps)) / (2 * eps)
        cond = abs(x * f_prime / fx)

        return MathObject(
            result=cond,
            steps=[
                f"f({x}) = {fx}",
                f"f'({x}) ≈ {f_prime}",
                f"条件数 = |x·f'(x)/f(x)| = {cond}",
            ],
            meaning=f"条件数 {cond:.4g}，表示输入相对误差最多放大 {cond:.4g} 倍到输出",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="truncation_error")
def truncation_error(
    series_func: Callable[[float, int], float],
    x: float,
    n: int,
    true_value: float = 0.0,
) -> MathObject:
    """估计级数展开的截断误差。

    将级数展开到 n 项，并与真值（如果提供）比较。

    Args:
        series_func: partial_sum(x, n) 返回前 n 项和的函数。
        x: 展开点。
        n: 展开项数。
        true_value: 真实值，若为 0 则只返回近似值。

    Returns:
        MathObject: result 为截断误差（float）。
    """
    try:
        approx = series_func(x, n)

        if abs(true_value) > 1e-15:
            error = abs(approx - true_value)
            return MathObject(
                result=error,
                steps=[
                    f"展开至第 {n} 项：近似值 = {approx}",
                    f"真实值 = {true_value}",
                    f"截断误差 = |近似值 - 真实值| = {error}",
                ],
                meaning=f"截断 {n} 项后的误差为 {error:.4g}",
            )
        else:
            # 用n+1项估计
            approx_next = series_func(x, n + 1)
            error_est = abs(approx - approx_next)
            return MathObject(
                result=error_est,
                steps=[
                    f"展开至第 {n} 项：近似值 = {approx}",
                    f"展开至第 {n+1} 项：近似值 = {approx_next}",
                    f"截断误差估计 = |第{n}项 - 第{n+1}项| = {error_est}",
                ],
                meaning=f"截断误差估计为 {error_est:.4g}（基于下一项估计）",
            )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="rounding_error_estimate")
def rounding_error_estimate(
    operation: str, precision: int = 16
) -> MathObject:
    """估计浮点运算的舍入误差。

    Args:
        operation: 运算类型描述，如 "sum(1e16, 1)"、"dot(1e6, 1e6)"。
        precision: IEEE 754 精度位数（默认 double = 16 位十进制有效数字）。

    Returns:
        MathObject: result 为相对舍入误差界（float）。
    """
    try:
        eps_machine = 10 ** (-precision)
        # 相对误差界约为机器精度 × 条件数（这里用简化估计）
        relative_bound = eps_machine

        return MathObject(
            result=relative_bound,
            steps=[
                f"机器精度 ε ≈ 10^{-precision} = {eps_machine}",
                f"运算：{operation}",
                f"估计相对舍入误差界 ≤ {relative_bound}",
            ],
            meaning=f"在 IEEE 754 {precision}位精度下，运算 {operation} 的相对舍入误差约 {relative_bound:.2g}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="numerical", action="is_stable")
def is_stable(
    algorithm: Callable[..., Any],
    *inputs: Any,
) -> MathObject:
    """判断算法的数值稳定性。

    通过比较正向/反向微小扰动后的结果差异来判断。

    Args:
        algorithm: 待评估算法函数。
        *inputs: 算法输入参数。

    Returns:
        MathObject: result 为 bool，附带稳定性分析。
    """
    try:
        ref = algorithm(*inputs)

        # 微小扰动测试
        perturbed_inputs = []
        for inp in inputs:
            if isinstance(inp, (int, float)):
                perturbed_inputs.append(inp * (1.0 + 1e-8))
            elif isinstance(inp, np.ndarray):
                perturbed_inputs.append(inp + 1e-8 * (np.random.randn(*inp.shape) if inp.size > 0 else inp))
            else:
                perturbed_inputs.append(inp)

        perturbed = algorithm(*perturbed_inputs)

        if isinstance(ref, (int, float, np.floating)) and isinstance(
            perturbed, (int, float, np.floating)
        ):
            rel_diff = abs(float(perturbed) - float(ref)) / (abs(float(ref)) + 1e-15)
            stable = rel_diff < 1e-4
        elif isinstance(ref, np.ndarray) and isinstance(perturbed, np.ndarray):
            rel_diff = float(np.linalg.norm(perturbed - ref) / (np.linalg.norm(ref) + 1e-15))
            stable = rel_diff < 1e-4
        else:
            stable = True

        return MathObject(
            result=stable,
            steps=[
                f"原始结果 = {ref}",
                f"扰动后结果 = {perturbed}",
                f"相对差异 = {rel_diff:.4g}",
            ],
            meaning=f"算法{'稳定' if stable else '不稳定'}，扰动放大系数约 {rel_diff:.4g}",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 error_stability 模块。"""
    print("=== error_stability self_test ===")
    passed = 0
    total = 4

    # Test 1: condition_number — f(x)=1/x 的相对条件数恒为 1
    try:
        r = condition_number("1/x", 1e-3)
        assert r.ok
        assert abs(r.result - 1.0) < 0.01, f"Expected cond ≈ 1, got {r.result}"
        print(f"  [PASS] condition_number('1/x', 1e-3) = {r.result:.4g}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] condition_number: {e}")

    # Test 1b: condition_number for an ill-conditioned function
    try:
        # f(x) = 1/(x-1) near x≈1 has large condition number
        r2 = condition_number("1/(x-1)", 1.001)
        assert r2.ok
        assert r2.result > 100, f"Expected large cond, got {r2.result}"
        print(f"  [PASS] condition_number('1/(x-1)', 1.001) = {r2.result:.4g}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] condition_number ill-conditioned: {e}")

    # Test 2: truncation_error
    try:
        def exp_series(x: float, n: int) -> float:
            s = 0.0
            term = 1.0
            for k in range(n + 1):
                s += term
                term *= x / (k + 1)
            return s

        r = truncation_error(exp_series, 1.0, 5, true_value=np.exp(1.0))
        assert r.ok
        assert r.result < 0.01, f"Expected error < 0.01, got {r.result}"
        print(f"  [PASS] truncation_error(exp, 1.0, 5) error = {r.result:.6f}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] truncation_error: {e}")

    # Test 3: is_stable
    try:
        def stable_algo(x: float) -> float:
            return x + 1.0

        r = is_stable(stable_algo, 1000.0)
        assert r.ok
        assert r.result is True
        print(f"  [PASS] is_stable(stable_algo, 1000) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] is_stable: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
