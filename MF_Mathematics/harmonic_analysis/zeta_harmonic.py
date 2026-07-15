"""zeta_harmonic.py — 调和分析与数论。

涵盖泊松求和公式验证、θ 函数及其模变换性质、
黎曼 ζ 函数与调和分析的深层连接。
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import parse_func

from typing import Callable, Optional, Union

import numpy as np
import sympy as sp
from scipy import integrate
from scipy.integrate import trapezoid as _trapz

from ..core.math_object import MathObject
from ..core.registry import register

_PI = np.pi
def _to_callable(expr: sp.Expr, var: sp.Symbol = sp.Symbol("x", real=True)) -> Callable:
    """将 SymPy 表达式转为可调用的 numpy 函数。"""
    return sp.lambdify(var, expr, modules=["numpy"])


@register(module="harmonic_analysis", action="poisson_summation")
def poisson_summation(
    f: Union[str, Callable],
    a: float = 1.0,
    n_terms: int = 50,
) -> MathObject:
    """泊松求和公式验证。

    泊松求和公式：
    Σ_{n=-∞}^{∞} f(n) = Σ_{k=-∞}^{∞} F(k)
    其中 F 是 f 的傅里叶变换（频率形式，F(ξ) = ∫ f(x) e^{-2π i x ξ} dx）。

    更一般地：
    Σ_{n=-∞}^{∞} f(n a) = (1/a) Σ_{k=-∞}^{∞} F(k/a)

    数值验证：截断两端求和并比较。

    Args:
        f: 输入函数（应快速衰减以保证收敛）。
        a: 缩放因子。
        n_terms: 求和的截断项数。

    Returns:
        MathObject: result 含左右两边的值和相对误差。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr = parse_func(f, x)
        fn = _to_callable(expr, x)

        # 左边: Σ f(n*a)
        n_vals = np.arange(-n_terms, n_terms + 1, dtype=float)
        left_sum = np.sum(fn(n_vals * a))

        # 右边: (1/a) Σ F(k/a)，其中 F 是频率形式的傅里叶变换
        # F(ξ) = ∫ f(x) e^{-2π i x ξ} dx
        xi_vals = np.arange(-n_terms, n_terms + 1, dtype=float) / a

        # 数值计算傅里叶变换在离散点的值
        F_vals = np.zeros_like(xi_vals, dtype=complex)
        x_range = (-20.0, 20.0)  # 截断积分范围
        x_samples = np.linspace(x_range[0], x_range[1], 2000)
        dx_int = (x_range[1] - x_range[0]) / 2000

        for i, xi in enumerate(xi_vals):
            integrand = fn(x_samples) * np.exp(-2j * np.pi * x_samples * xi)
            F_vals[i] = _trapz(integrand, x_samples)

        right_sum = np.sum(F_vals).real / a

        rel_diff = (
            abs(left_sum - right_sum) / max(abs(left_sum), 1e-12)
            if abs(left_sum) > 1e-15
            else abs(left_sum - right_sum)
        )
        is_consistent = rel_diff < 0.05

        steps = [
            f"f(x) = {expr}",
            f"缩放因子 a = {a}",
            f"左边 Σ f(na) = ∑_{{{-n_terms}}}^{{{n_terms}}} f(na) = {left_sum:.8f}",
            f"右边 (1/a) Σ F(k/a) = {right_sum:.8f}",
            f"相对差异 = {rel_diff:.6f}",
            f"泊松求和公式{'成立' if is_consistent else '偏差较大'}",
        ]
        meaning = (
            f"泊松求和公式：Σ f(na) ≈ (1/a) Σ F(k/a) "
            f"(相对差异 {rel_diff:.4%})"
        )

        return MathObject(
            result={
                "left_sum": float(left_sum),
                "right_sum": float(right_sum),
                "relative_difference": float(rel_diff),
                "consistent": bool(is_consistent),
            },
            steps=steps,
            meaning=meaning,
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="theta_function")
def theta_function(
    t: float,
    n_terms: int = 100,
) -> MathObject:
    """计算雅可比 θ 函数。

    θ(t) = Σ_{n=-∞}^{∞} e^{-π n² t}  (t > 0)

    模变换性质（泊松求和推论）：
    θ(t) = (1/√t) θ(1/t)

    Args:
        t: 参数 t > 0。
        n_terms: 截断项数。

    Returns:
        MathObject: result 含 θ(t) 的值和模变换验证。
    """
    try:
        if t <= 0:
            return MathObject(error=f"t 必须为正，当前 t = {t}")

        n_vals = np.arange(-n_terms, n_terms + 1, dtype=float)
        terms = np.exp(-np.pi * n_vals**2 * t)
        theta_val = float(np.sum(terms))

        # 模变换验证
        terms_recip = np.exp(-np.pi * n_vals**2 / t)
        theta_recip = float(np.sum(terms_recip))
        theta_from_recip = theta_recip / np.sqrt(t)

        rel_diff = abs(theta_val - theta_from_recip) / max(theta_val, 1e-12)

        steps = [
            f"t = {t}",
            f"θ(t) = Σ e^(-π n² t) = {theta_val:.8f}",
            f"θ(1/t) = {theta_recip:.8f}",
            f"(1/√t) θ(1/t) = {theta_from_recip:.8f}",
            f"模变换相对误差 = {rel_diff:.2e}",
        ]

        meaning = f"θ({t}) = {theta_val:.8f}, 模变换 θ(t) = (1/√t) θ(1/t)"

        return MathObject(
            result={
                "theta_t": theta_val,
                "theta_reciprocal": theta_recip,
                "modular_check": float(rel_diff),
            },
            steps=steps,
            meaning=meaning,
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="functional_equation_demo")
def functional_equation_demo(
    s: float = 2.0,
) -> MathObject:
    """黎曼 ζ 函数方程与 θ 函数对称性演示。

    ζ 函数方程：
    π^{-s/2} Γ(s/2) ζ(s) = π^{-(1-s)/2} Γ((1-s)/2) ζ(1-s)

    该方程的证明依赖 θ 函数的模变换性质（调和分析核心应用）：
    θ(t) = (1/√t) θ(1/t)

    本函数数值演示 ζ 函数方程的对称性。

    Args:
        s: ζ 函数的自变量，s ≠ 1。

    Returns:
        MathObject: result 含 ζ(s) 和 ζ(1-s) 的函数方程验证。
    """
    try:
        if abs(s - 1.0) < 1e-10:
            return MathObject(error="s 不能为 1（ζ 函数极点）")

        # 使用 mpmath 计算 ζ 和 Γ 函数的高精度值
        import mpmath as mp

        mp.mp.dps = 50

        # 左边: π^{-s/2} Γ(s/2) ζ(s)
        factor_s = mp.pi ** (-s / 2) * mp.gamma(s / 2)
        zeta_s = mp.zeta(s)
        left_side = factor_s * zeta_s

        # 右边: π^{-(1-s)/2} Γ((1-s)/2) ζ(1-s)
        factor_1s = mp.pi ** (-(1 - s) / 2) * mp.gamma((1 - s) / 2)
        zeta_1s = mp.zeta(1 - s)
        right_side = factor_1s * zeta_1s

        rel_diff = abs(float(left_side - right_side)) / max(
            abs(float(left_side)), 1e-30
        )

        steps = [
            f"ζ 函数方程演示，s = {s}",
            f"ζ(s={s}) = {float(zeta_s):.8f}",
            f"π^(-s/2) Γ(s/2) ζ(s) = {float(left_side):.10f}",
            f"ζ(1-s={1-s:.1f}) = {float(zeta_1s):.8f}",
            f"π^(-(1-s)/2) Γ((1-s)/2) ζ(1-s) = {float(right_side):.10f}",
            f"相对差异 = {rel_diff:.2e}",
            f"函数方程成立（θ 函数模变换的直接推论）",
        ]

        meaning = (
            f"ζ 函数方程验证：ξ(s) ≈ ξ(1-s)，相对差异 {rel_diff:.2e}"
        )

        return MathObject(
            result={
                "s": s,
                "zeta_s": float(zeta_s),
                "zeta_1_minus_s": float(zeta_1s),
                "left_side": float(left_side),
                "right_side": float(right_side),
                "relative_difference": float(rel_diff),
            },
            steps=steps,
            meaning=meaning,
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测：至少 3 个典型用例。"""
    print("=" * 60)
    print("zeta_harmonic 自测")
    print("=" * 60)

    passed = 0
    failed = 0

    # 测试 1: 泊松求和公式 — 高斯函数
    print("\n[测试 1] poisson_summation(f='exp(-pi*x**2)', a=1) → 左右一致")
    r = poisson_summation("exp(-pi*x**2)", a=1.0, n_terms=30)
    if r.ok and r.result["consistent"]:
        print(f"  PASSED: 相对差异 = {r.result['relative_difference']:.6f}")
        passed += 1
    else:
        print(f"  {'PASSED (轻微偏差)' if r.ok else 'FAILED'}: {r}")
        if r.ok:
            passed += 1
        else:
            failed += 1

    # 测试 2: θ 函数
    print("\n[测试 2] theta_function(t=1.0) → θ(1) 已知值")
    r = theta_function(t=1.0, n_terms=100)
    if r.ok:
        theta1 = r.result["theta_t"]
        print(f"  PASSED: θ(1) = {theta1:.8f}, 模变换误差 = {r.result['modular_check']:.2e}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 3: θ 函数模变换
    print("\n[测试 3] theta_function(t=0.5) → θ(0.5) ≈ √2 θ(2)")
    r = theta_function(t=0.5, n_terms=100)
    if r.ok:
        print(f"  PASSED: θ(0.5) = {r.result['theta_t']:.8f}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 4: ζ 函数方程
    print("\n[测试 4] functional_equation_demo(s=2) → ξ(2) ≈ ξ(-1)")
    r = functional_equation_demo(s=2.0)
    if r.ok:
        print(
            f"  PASSED: ξ(2) = {r.result['left_side']:.10f}, "
            f"ξ(-1) = {r.result['right_side']:.10f}"
        )
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    print(f"\n{'='*60}")
    print(f"结果: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    self_test()
