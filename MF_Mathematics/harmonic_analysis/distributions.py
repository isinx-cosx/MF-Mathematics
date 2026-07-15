"""distributions.py — 分布与缓增分布。

涵盖 δ 函数（狄拉克分布）、分布意义下的傅里叶变换扩展、
常数与 δ 的对偶关系，缓增分布的概念性判断。
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import parse_func

from typing import Callable, Optional, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register

_PI = np.pi
def _to_callable(expr: sp.Expr, var: sp.Symbol = sp.Symbol("x", real=True)) -> Callable:
    """将 SymPy 表达式转为可调用的 numpy 函数。"""
    return sp.lambdify(var, expr, modules=["numpy"])


@register(module="harmonic_analysis", action="delta_distribution")
def delta_distribution(
    phi: Union[str, Callable],
    x0: float = 0.0,
) -> MathObject:
    """δ 函数作用于测试函数 φ：<δ_{x₀}, φ> = φ(x₀)。

    狄拉克 δ 分布定义：δ_{x₀}[φ] = φ(x₀)
    这是一个广义函数（分布），将测试函数映射到其在 x₀ 处的值。

    Args:
        phi: 测试函数 φ(x)。
        x0: δ 函数中心点。

    Returns:
        MathObject: result 为 φ(x₀) 的值。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr = parse_func(phi, x)
        fn = _to_callable(expr, x)

        val = float(fn(x0))

        steps = [
            f"δ 函数中心 x₀ = {x0}",
            f"φ(x) = {expr}",
            f"<δ_{{{x0}}}, φ> = φ({x0}) = {val}",
        ]
        meaning = f"δ 分布在 x₀={x0} 处作用于 φ：值为 φ(x₀) = {val}"

        return MathObject(result=val, steps=steps, meaning=meaning)
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="ft_delta")
def ft_delta() -> MathObject:
    """δ 函数的傅里叶变换：F[δ] = 1（常数函数）。

    F[δ](ξ) = ∫ δ(x) e^{-i x ξ} dx = e^{-i·0·ξ} = 1

    这说明了 δ 分布在傅里叶变换下的行为：
    δ 的傅里叶变换是常函数 1。

    Returns:
        MathObject: result 为 '1'（字符串表示常函数）。
    """
    try:
        steps = [
            "F[δ](ξ) = ∫_{-∞}^{∞} δ(x) e^{-i x ξ} dx",
            "根据 δ 的筛选性质: = e^{-i·0·ξ}",
            "= 1",
        ]
        meaning = "δ 函数的傅里叶变换是常函数 1（在分布意义下）"

        return MathObject(
            result="1",
            steps=steps,
            meaning=meaning,
            data={"symbolic": "F[δ] = 1"},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="ft_constant")
def ft_constant() -> MathObject:
    """常数的傅里叶变换：F[1] = 2π δ（分布意义下）。

    在分布意义下：
    F[1](ξ) = ∫ 1 · e^{-i x ξ} dx = 2π δ(ξ)

    这体现了傅里叶变换的对偶性：δ ↔ 1。

    Returns:
        MathObject: result 为 '2π δ(ξ)'（符号表示）。
    """
    try:
        steps = [
            "F[1](ξ) = ∫_{-∞}^{∞} 1 · e^{-i x ξ} dx",
            "该积分在经典意义下发散",
            "在分布意义下，F[1] = 2π δ(ξ)",
            "验证：逆变换 (1/(2π)) ∫ 2π δ(ξ) e^{i x ξ} dξ = 1",
        ]
        meaning = "常数 1 的傅里叶变换是 2π δ(ξ)（分布意义下，体现对偶性）"

        return MathObject(
            result="2*pi*delta(xi)",
            steps=steps,
            meaning=meaning,
            data={"symbolic": "F[1] = 2π δ(ξ)"},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="tempered_distribution")
def tempered_distribution(
    func: Union[str, Callable],
    x_range: tuple = (-100.0, 100.0),
) -> MathObject:
    """判断给定函数是否对应一个缓增分布（概念性占位）。

    缓增分布是施瓦兹空间 S(Rⁿ) 上的连续线性泛函。
    粗略判断条件：函数多项式增长（即存在 C, N 使得 |f(x)| ≤ C(1+|x|)^N）。

    Args:
        func: 待判断的函数。
        x_range: 检查范围。

    Returns:
        MathObject: result 含判断结果和增长阶数估计。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr = parse_func(func, x)
        fn = _to_callable(expr, x)

        # 在多个点采样，估计增长
        x_samples = np.logspace(0, np.log10(max(x_range[1], 10)), 50)
        y_samples = np.abs(fn(x_samples))

        # 检查是否有 NaN 或 Inf
        if np.any(np.isnan(y_samples)) or np.any(np.isinf(y_samples)):
            return MathObject(
                result={"is_tempered": False, "growth_order": np.inf},
                steps=[f"f(x) = {expr}", "函数在采样点出现奇异或无穷大", "不是缓增分布"],
                meaning="不是缓增分布（存在不可积奇点）",
            )

        # 用 log-log 拟合估计多项式增长阶数
        valid_mask = y_samples > 0
        if np.sum(valid_mask) < 3:
            return MathObject(
                result={"is_tempered": True, "growth_order": 0.0},
                steps=[f"f(x) = {expr}", "函数快速衰减或恒为零", "是缓增分布"],
                meaning="是缓增分布（快速衰减函数）",
            )

        log_x = np.log(x_samples[valid_mask])
        log_y = np.log(y_samples[valid_mask])
        slope, _ = np.polyfit(log_x, log_y, 1)
        growth_order = float(slope)

        is_tempered = np.isfinite(growth_order)

        steps = [
            f"f(x) = {expr}",
            f"估计多项式增长阶数 N ≈ {growth_order:.2f}",
            f"{'是缓增分布' if is_tempered else '不是缓增分布'}",
        ]
        meaning = (
            f"缓增分布判断：{'是' if is_tempered else '不是'} "
            f"（估计增长阶 ≈ {growth_order:.2f}）"
        )

        return MathObject(
            result={"is_tempered": is_tempered, "growth_order": growth_order},
            steps=steps,
            meaning=meaning,
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测：至少 3 个典型用例。"""
    print("=" * 60)
    print("distributions 自测")
    print("=" * 60)

    passed = 0
    failed = 0

    # 测试 1: δ 分布的筛选性质
    print("\n[测试 1] delta_distribution(phi='x**2 + 1', x0=3) → 10")
    r = delta_distribution("x**2 + 1", x0=3.0)
    if r.ok and abs(r.result - 10.0) < 1e-8:
        print(f"  PASSED: φ(3) = {r.result}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 2: δ 的傅里叶变换
    print("\n[测试 2] ft_delta() → 1")
    r = ft_delta()
    if r.ok and r.result == "1":
        print(f"  PASSED: F[δ] = {r.result}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 3: 常数的傅里叶变换
    print("\n[测试 3] ft_constant() → 2π δ(ξ)")
    r = ft_constant()
    if r.ok and "delta" in str(r.result).lower():
        print(f"  PASSED: F[1] = {r.result}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 4: 缓增分布判断
    print("\n[测试 4] tempered_distribution(func='exp(-x**2)') → True")
    r = tempered_distribution("exp(-x**2)", x_range=(-10, 10))
    if r.ok and r.result.get("is_tempered", False):
        print(f"  PASSED: 是缓增分布（增长阶 ≈ {r.result['growth_order']:.2f}）")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    print(f"\n{'='*60}")
    print(f"结果: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    self_test()
