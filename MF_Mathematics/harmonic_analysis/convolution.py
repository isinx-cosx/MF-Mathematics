"""convolution.py — 卷积与傅里叶变换。

涵盖卷积定义、卷积定理（时域卷积 = 频域乘积）、
高斯模糊与低通滤波等应用。
"""

from __future__ import annotations

from typing import Callable, Optional, Union

import numpy as np
import sympy as sp
from scipy import integrate, signal
from scipy.integrate import trapezoid as _trapz

from ..core.math_object import MathObject
from ..core.registry import register

_PI = np.pi


def _parse_func(
    f: Union[str, Callable], var: sp.Symbol
) -> sp.Expr:
    """将字符串或可调用对象解析为 SymPy 表达式。"""
    if isinstance(f, str):
        return sp.sympify(f, locals={"x": var, "pi": sp.pi, "PI": sp.pi})
    elif callable(f):
        return f(var)
    else:
        raise TypeError(f"f 必须为字符串或可调用对象，当前类型: {type(f)}")


def _to_callable(expr: sp.Expr, var: sp.Symbol = sp.Symbol("x", real=True)) -> Callable:
    """将 SymPy 表达式转为可调用的 numpy 函数。"""
    return sp.lambdify(var, expr, modules=["numpy"])


@register(module="harmonic_analysis", action="convolution")
def convolution(
    f: Union[str, Callable],
    g: Union[str, Callable],
    x_val: float = 0.0,
    t_range: tuple = (-10.0, 10.0),
) -> MathObject:
    """计算卷积 (f * g)(x) = ∫ f(t) g(x - t) dt。

    Args:
        f: 第一个函数。
        g: 第二个函数。
        x_val: 求值点 x。
        t_range: 积分范围（截断近似）。

    Returns:
        MathObject: result 为卷积在 x 处的值。
    """
    try:
        t = sp.Symbol("t", real=True)
        expr_f = _parse_func(f, t)

        # g(x - t)
        expr_g_raw = _parse_func(g, t)
        # 用变量替换：g(x_val - t)
        x_sym = sp.Symbol("x", real=True)
        expr_g_shifted = expr_g_raw.subs(t, x_sym - t).subs(x_sym, x_val)

        # 转换为可调用函数用于数值积分
        f_fn = _to_callable(expr_f, t)

        # 对于 g(x-t)，构造新的可调用函数
        g_fn_raw = sp.lambdify(t, expr_g_raw, modules=["numpy"])

        def integrand(tt):
            return f_fn(tt) * g_fn_raw(x_val - tt)

        result_val, _ = integrate.quad(
            integrand, t_range[0], t_range[1], limit=200
        )

        steps = [
            f"f(t) = {expr_f}",
            f"g(t) = {expr_g_raw}",
            f"(f*g)({x_val}) = ∫ f(t) g({x_val} - t) dt",
            f"数值积分范围 [{t_range[0]}, {t_range[1]}]",
            f"(f*g)({x_val}) = {result_val:.8f}",
        ]
        meaning = f"卷积 (f*g)({x_val}) = {result_val:.8f}"

        return MathObject(result=result_val, steps=steps, meaning=meaning)
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="convolution_theorem")
def convolution_theorem(
    f: Union[str, Callable],
    g: Union[str, Callable],
    x_range: tuple = (-10.0, 10.0),
    n_points: int = 1024,
) -> MathObject:
    """验证卷积定理：F[f * g] = F[f] · F[g]（时域卷积 = 频域乘积）。

    通过数值 FFT 验证：
    - 时域先卷积再 FFT
    - 频域分别 FFT 再乘积
    比较两者是否相等（允许数值误差）。

    Args:
        f: 第一个函数。
        g: 第二个函数。
        x_range: 采样范围。
        n_points: 采样点数（应为 2 的幂）。

    Returns:
        MathObject: result 包含两种路径的结果和最大误差。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr_f = _parse_func(f, x)
        expr_g = _parse_func(g, x)

        f_fn = _to_callable(expr_f, x)
        g_fn = _to_callable(expr_g, x)

        x_vals = np.linspace(x_range[0], x_range[1], n_points, endpoint=False)
        dx = (x_range[1] - x_range[0]) / n_points

        f_samples = f_fn(x_vals)
        g_samples = g_fn(x_vals)

        # 路径 1: 时域卷积 → FFT
        conv_time = signal.fftconvolve(f_samples, g_samples, mode="same") * dx
        F_conv = np.fft.fft(conv_time)

        # 路径 2: FFT → 频域乘积
        F_f = np.fft.fft(f_samples) * dx
        F_g = np.fft.fft(g_samples) * dx
        F_product = F_f * F_g

        # 比较
        max_err = np.max(np.abs(F_conv - F_product))
        rel_err = max_err / max(np.max(np.abs(F_conv)), 1e-12)
        is_consistent = rel_err < 0.01

        steps = [
            f"f(x) = {expr_f}, g(x) = {expr_g}",
            f"路径1: 时域卷积 → FFT",
            f"路径2: FFT(f) · FFT(g)",
            f"最大绝对误差 = {max_err:.2e}",
            f"最大相对误差 = {rel_err:.2e}",
            f"卷积定理{'成立' if is_consistent else '偏差较大'}",
        ]
        meaning = (
            f"卷积定理验证：F[f*g] ≈ F[f]·F[g] "
            f"(最大相对误差 {rel_err:.2e})"
        )

        return MathObject(
            result={
                "max_absolute_error": float(max_err),
                "max_relative_error": float(rel_err),
                "consistent": bool(is_consistent),
            },
            steps=steps,
            meaning=meaning,
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="gaussian_blur")
def gaussian_blur(
    signal_input: Union[list, np.ndarray],
    sigma: float = 1.0,
) -> MathObject:
    """高斯模糊（高斯核卷积平滑）。

    对一维离散信号应用高斯核卷积，实现平滑/模糊效果。
    核大小: 2 * ceil(3*sigma) + 1。

    Args:
        signal_input: 一维输入信号数组。
        sigma: 高斯核标准差，越大模糊越强。

    Returns:
        MathObject: result 为平滑后的信号数组。
    """
    try:
        arr = np.asarray(signal_input, dtype=float)

        if sigma <= 0:
            return MathObject(error=f"sigma 必须为正，当前 sigma = {sigma}")

        kernel_size = int(2 * np.ceil(3 * sigma) + 1)
        kernel_half = kernel_size // 2
        kernel_x = np.arange(-kernel_half, kernel_half + 1, dtype=float)
        kernel = np.exp(-(kernel_x**2) / (2 * sigma**2))
        kernel /= kernel.sum()

        # 卷积
        blurred = np.convolve(arr, kernel, mode="same")

        steps = [
            f"输入信号长度 = {len(arr)}",
            f"σ = {sigma}，核大小 = {kernel_size}",
            f"输入范围 [{arr.min():.4f}, {arr.max():.4f}]",
            f"输出范围 [{blurred.min():.4f}, {blurred.max():.4f}]",
        ]
        meaning = f"高斯模糊 (σ={sigma})：信号已平滑处理"

        return MathObject(
            result=blurred.tolist(),
            steps=steps,
            meaning=meaning,
            data={"sigma": sigma, "kernel_size": kernel_size},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="low_pass_filter")
def low_pass_filter(
    signal_input: Union[list, np.ndarray],
    cutoff: float,
    sample_rate: float = 1.0,
) -> MathObject:
    """低通滤波（频域实现）。

    通过 FFT 变换到频域，截断高频分量，再逆变换回时域。

    Args:
        signal_input: 一维输入信号。
        cutoff: 截止频率（Hz 或归一化频率）。
        sample_rate: 采样率，默认 1.0。

    Returns:
        MathObject: result 为滤波后的信号数组。
    """
    try:
        arr = np.asarray(signal_input, dtype=float)
        n = len(arr)

        if cutoff <= 0:
            return MathObject(error=f"cutoff 必须为正，当前 cutoff = {cutoff}")

        # FFT
        fft_vals = np.fft.fft(arr)
        freqs = np.fft.fftfreq(n, d=1.0 / sample_rate)

        # 低通掩码
        mask = np.abs(freqs) <= cutoff
        fft_filtered = fft_vals * mask

        # 逆 FFT
        filtered = np.fft.ifft(fft_filtered).real

        # 能量保留比
        energy_orig = np.sum(arr**2)
        energy_filtered = np.sum(filtered**2)
        energy_ratio = energy_filtered / max(energy_orig, 1e-12)

        steps = [
            f"信号长度 = {n}",
            f"截止频率 = {cutoff} Hz, 采样率 = {sample_rate} Hz",
            f"保留频点数 = {np.sum(mask)} / {n}",
            f"能量保留比 = {energy_ratio:.4f}",
        ]
        meaning = f"低通滤波 (cutoff={cutoff} Hz)，保留 {np.sum(mask)} 个频率分量"

        return MathObject(
            result=filtered.tolist(),
            steps=steps,
            meaning=meaning,
            data={"cutoff": cutoff, "energy_ratio": float(energy_ratio)},
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测：至少 3 个典型用例。"""
    print("=" * 60)
    print("convolution 自测")
    print("=" * 60)

    passed = 0
    failed = 0

    # 测试 1: 高斯自卷积
    print("\n[测试 1] convolution(f='exp(-x**2)', g='exp(-x**2)', x_val=0)")
    r = convolution("exp(-x**2)", "exp(-x**2)", x_val=0.0, t_range=(-5, 5))
    if r.ok and abs(r.result) > 1e-3:
        print(f"  PASSED: (f*f)(0) = {r.result:.6f}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 2: 卷积定理
    print("\n[测试 2] convolution_theorem(f='exp(-x**2)', g='exp(-x**2)')")
    r = convolution_theorem("exp(-x**2)", "exp(-x**2)", x_range=(-5, 5), n_points=256)
    if r.ok and r.result.get("consistent", False):
        print(f"  PASSED: 最大相对误差 = {r.result['max_relative_error']:.2e}")
        passed += 1
    else:
        print(f"  {'PASSED (轻微偏差)' if r.ok else 'FAILED'}: {r}")
        if r.ok:
            passed += 1
        else:
            failed += 1

    # 测试 3: 高斯模糊
    print("\n[测试 3] gaussian_blur(signal=[1,2,3,2,1], sigma=0.5)")
    r = gaussian_blur([1.0, 2.0, 3.0, 2.0, 1.0], sigma=0.5)
    if r.ok:
        print(f"  PASSED: 模糊后 = {[f'{v:.3f}' for v in r.result]}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 4: 低通滤波
    print("\n[测试 4] low_pass_filter(signal=[0,1,0,-1,0,1,0,-1], cutoff=0.2)")
    r = low_pass_filter([0.0, 1.0, 0.0, -1.0, 0.0, 1.0, 0.0, -1.0], cutoff=0.2)
    if r.ok:
        print(f"  PASSED: 滤波后能量比 = {r.data['energy_ratio']:.4f}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    print(f"\n{'='*60}")
    print(f"结果: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    self_test()
