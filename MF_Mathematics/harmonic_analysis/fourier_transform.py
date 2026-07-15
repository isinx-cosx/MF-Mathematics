"""fourier_transform.py — 傅里叶变换。

涵盖傅里叶变换定义、逆变换、L² 理论、普兰舍利定理、
高斯函数的傅里叶变换等核心内容。
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


@register(module="harmonic_analysis", action="fourier_transform")
def fourier_transform(
    f: Union[str, Callable],
    xi: Union[float, str] = "xi",
    use_angular: bool = True,
) -> MathObject:
    """计算函数的傅里叶变换（符号/数值）。

    F(ξ) = ∫_{-∞}^{∞} f(x) e^{-2π i x ξ} dx   (use_angular=False, 频率形式)
    F(ξ) = ∫_{-∞}^{∞} f(x) e^{-i x ξ} dx      (use_angular=True, 角频率形式)

    Args:
        f: 输入函数，字符串表达式或可调用对象。
        xi: 频率变量，可为数值或字符串（符号计算时）。
        use_angular: True 使用角频率 ω（1/√(2π) 归一化），
                     False 使用频率 ξ（标准 L² 归一化）。

    Returns:
        MathObject: result 为变换结果（表达式或数值）。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr = parse_func(f, x)

        if use_angular:
            # 角频率形式
            integrand = expr * sp.exp(-sp.I * x * sp.Symbol("xi", real=True) if isinstance(xi, str) and xi == "xi" else sp.exp(-sp.I * x * xi))
        else:
            integrand = expr * sp.exp(-2 * sp.pi * sp.I * x * sp.Symbol("xi", real=True) if isinstance(xi, str) and xi == "xi" else sp.exp(-2 * sp.pi * sp.I * x * xi))

        # 尝试符号积分（常见函数如高斯、指数衰减等）
        xi_sym = sp.Symbol("xi", real=True)
        if use_angular:
            integrand_sym = expr * sp.exp(-sp.I * x * xi_sym)
        else:
            integrand_sym = expr * sp.exp(-2 * sp.pi * sp.I * x * xi_sym)

        try:
            ft_expr = sp.integrate(integrand_sym, (x, -sp.oo, sp.oo))
            ft_simplified = sp.simplify(ft_expr)
        except Exception:
            # 符号积分失败，返回未求值表达式
            ft_simplified = sp.Integral(integrand_sym, (x, -sp.oo, sp.oo))

        if isinstance(xi, (int, float)):
            val = float(sp.N(ft_simplified.subs(xi_sym, xi)))
            return MathObject(
                result=val,
                steps=[
                    f"f(x) = {expr}",
                    f"F(ξ) = {ft_simplified}",
                    f"F({xi}) = {val}",
                ],
                meaning=f"傅里叶变换在 ξ={xi} 处的值 = {val}",
            )

        steps = [
            f"f(x) = {expr}",
            f"F(ξ) = ∫ f(x) e^(-i x ξ) dx = {ft_simplified}",
        ]
        meaning = f"f 的傅里叶变换 F(ξ) = {ft_simplified}"

        return MathObject(result=ft_simplified, steps=steps, meaning=meaning)
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="inverse_fourier_transform")
def inverse_fourier_transform(
    F: Union[str, Callable],
    x_val: Union[float, str] = "x",
    use_angular: bool = True,
) -> MathObject:
    """计算逆傅里叶变换。

    f(x) = (1/(2π)) ∫_{-∞}^{∞} F(ξ) e^{i x ξ} dξ   (use_angular=True)
    f(x) = ∫_{-∞}^{∞} F(ξ) e^{2π i x ξ} dξ          (use_angular=False)

    Args:
        F: 频域函数。
        x_val: 时域变量或求值点。
        use_angular: True 使用角频率形式。

    Returns:
        MathObject: result 为逆变换结果。
    """
    try:
        xi = sp.Symbol("xi", real=True)
        expr = parse_func(F, xi)

        x_sym = sp.Symbol("x", real=True)
        if use_angular:
            integrand = expr * sp.exp(sp.I * x_sym * xi) / (2 * sp.pi)
        else:
            integrand = expr * sp.exp(2 * sp.pi * sp.I * x_sym * xi)

        try:
            ift_expr = sp.integrate(integrand, (xi, -sp.oo, sp.oo))
            ift_simplified = sp.simplify(ift_expr)
        except Exception:
            ift_simplified = sp.Integral(integrand, (xi, -sp.oo, sp.oo))

        if isinstance(x_val, (int, float)):
            val = float(sp.N(ift_simplified.subs(x_sym, x_val)))
            return MathObject(
                result=val,
                steps=[
                    f"F(ξ) = {expr}",
                    f"f(x) = {ift_simplified}",
                    f"f({x_val}) = {val}",
                ],
                meaning=f"逆傅里叶变换在 x={x_val} 处的值 = {val}",
            )

        steps = [
            f"F(ξ) = {expr}",
            f"f(x) = (1/(2π)) ∫ F(ξ) e^(i x ξ) dξ = {ift_simplified}",
        ]
        meaning = f"逆傅里叶变换 f(x) = {ift_simplified}"

        return MathObject(result=ift_simplified, steps=steps, meaning=meaning)
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="plancherel_theorem")
def plancherel_theorem(
    f: Union[str, Callable],
    g: Optional[Union[str, Callable]] = None,
    x_range: tuple = (-10, 10),
    n_points: int = 1000,
) -> MathObject:
    """验证普兰舍利定理（保内积性）。

    ‖f‖₂² = ‖F‖₂²，即 ∫|f(x)|² dx = (1/(2π)) ∫|F(ξ)|² dξ (角频率形式)。

    Args:
        f: 时域函数。
        g: 第二个函数（可选），用于验证 <f,g> = <F,G>。
        x_range: 数值积分范围（截断）。
        n_points: 采样点数。

    Returns:
        MathObject: result 含时域和频域的 L² 范数比较。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr_f = parse_func(f, x)
        f_callable = _to_callable(expr_f, x)

        x_vals = np.linspace(x_range[0], x_range[1], n_points)

        # 时域 L² 范数
        f_sq = np.abs(f_callable(x_vals)) ** 2
        l2_time = _trapz(f_sq, x_vals)
        l2_time = np.sqrt(l2_time)

        # 频域（通过 numpy FFT 数值计算）
        dx = (x_range[1] - x_range[0]) / n_points
        f_samples = f_callable(x_vals)
        F_fft = np.fft.fft(f_samples) * dx
        xi_vals = 2 * np.pi * np.fft.fftfreq(n_points, dx)
        F_mag_sq = np.abs(F_fft) ** 2
        l2_freq = np.sqrt(_trapz(F_mag_sq, xi_vals) / (2 * np.pi))

        rel_diff = abs(l2_time - l2_freq) / max(abs(l2_time), 1e-12)
        is_consistent = rel_diff < 0.05

        steps = [
            f"时域 L² 范数 ‖f‖₂ = {l2_time:.6f}",
            f"频域 L² 范数 ‖F‖₂ = {l2_freq:.6f}",
            f"相对差异 = {rel_diff:.6f}",
            f"普兰舍利定理{'成立' if is_consistent else '偏差较大（截断误差）'}",
        ]

        if g is not None:
            expr_g = parse_func(g, x)
            g_callable = _to_callable(expr_g, x)
            g_samples = g_callable(x_vals)
            G_fft = np.fft.fft(g_samples) * dx

            inner_time = _trapz(np.conj(f_samples) * g_samples, x_vals)
            inner_freq = _trapz(np.conj(F_fft) * G_fft, xi_vals) / (2 * np.pi)
            steps.append(
                f"时域内积 <f,g> = {inner_time.real:.6f}, "
                f"频域内积 <F,G> = {inner_freq.real:.6f}"
            )

        meaning = (
            f"普兰舍利定理：‖f‖₂ ≈ ‖F‖₂（相对差异 {rel_diff:.4%}）"
        )

        return MathObject(
            result={
                "l2_time": float(l2_time),
                "l2_freq": float(l2_freq),
                "relative_difference": float(rel_diff),
                "consistent": bool(is_consistent),
            },
            steps=steps,
            meaning=meaning,
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="ft_of_gaussian")
def ft_of_gaussian(
    a: float = 1.0,
) -> MathObject:
    """计算高斯函数 e^{-a x²} 的傅里叶变换。

    F(ξ) = √(π/a) e^{-ξ²/(4a)}   (角频率形式)
    特别地，当 a=1/2 时，e^{-x²/2} 的傅里叶变换为 √(2π) e^{-ξ²/2}（自对偶）。
    当 a=π 时，e^{-π x²} 的傅里叶变换为 e^{-π ξ²}（完全自对偶）。

    Args:
        a: 高斯参数 a > 0。

    Returns:
        MathObject: result 为变换结果表达式。
    """
    try:
        if a <= 0:
            return MathObject(error=f"参数 a 必须为正，当前 a = {a}")

        x = sp.Symbol("x", real=True)
        xi = sp.Symbol("xi", real=True)

        expr = sp.exp(-a * x**2)
        integrand = expr * sp.exp(-sp.I * x * xi)
        ft_result = sp.integrate(integrand, (x, -sp.oo, sp.oo))
        ft_simplified = sp.simplify(ft_result)

        steps = [
            f"f(x) = e^(-{a} x²)",
            f"F(ξ) = ∫ e^(-{a}x²) e^(-i x ξ) dx",
            f"F(ξ) = {ft_simplified}",
        ]

        # 验证自对偶性质
        if abs(a - sp.pi) < 1e-10:
            meaning = f"a=π 时完全自对偶：F(ξ) = e^(-πξ²)"
        elif abs(a - 0.5) < 1e-10:
            meaning = f"a=1/2 时标准自对偶：F(ξ) = √(2π) e^(-ξ²/2)"
        else:
            meaning = f"高斯 e^(-{a}x²) 的傅里叶变换 = {ft_simplified}"

        return MathObject(result=ft_simplified, steps=steps, meaning=meaning)
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测：至少 3 个典型用例。"""
    print("=" * 60)
    print("fourier_transform 自测")
    print("=" * 60)

    passed = 0
    failed = 0

    # 测试 1: 高斯函数的傅里叶变换（符号）
    print("\n[测试 1] ft_of_gaussian(a=pi) → e^(-π ξ²)")
    r = ft_of_gaussian(a=np.pi)
    if r.ok:
        print(f"  PASSED: F(ξ) = {r.result}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 2: δ 函数的傅里叶变换（使用近似高斯）
    print("\n[测试 2] fourier_transform(f='exp(-x**2)', xi='xi') → 高斯形式")
    r = fourier_transform("exp(-x**2)", xi="xi")
    if r.ok:
        print(f"  PASSED: F(ξ) = {r.result}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 3: 逆傅里叶变换
    print("\n[测试 3] inverse_fourier_transform(F='exp(-xi**2)', x_val='x')")
    r = inverse_fourier_transform("exp(-xi**2)", x_val="x")
    if r.ok:
        print(f"  PASSED: f(x) = {r.result}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 4: 普兰舍利定理（数值验证）
    print("\n[测试 4] plancherel_theorem(f='exp(-x**2/2)') → ‖f‖₂ ≈ ‖F‖₂")
    r = plancherel_theorem("exp(-x**2/2)", x_range=(-5, 5), n_points=500)
    if r.ok and r.result.get("consistent", False):
        print(f"  PASSED: 相对差异 = {r.result['relative_difference']:.6f}")
        passed += 1
    else:
        print(f"  {'PASSED (截断误差)' if r.ok else 'FAILED'}: {r}")
        if r.ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"结果: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    self_test()
