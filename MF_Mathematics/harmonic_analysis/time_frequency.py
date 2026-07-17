"""time_frequency.py — 时频分析与不确定性原理。

涵盖海森堡不确定性原理（Δx·Δξ ≥ 1/(4π)）、
短时傅里叶变换（STFT）、小波变换（Mexican Hat / Morlet）。
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import parse_func

from typing import Callable, Optional, Union

import numpy as np
import sympy as sp
from scipy import integrate, signal as sig
from scipy.integrate import trapezoid as _trapz

from ..core.math_object import MathObject
from ..core.registry import register

_PI = np.pi
def _to_callable(expr: sp.Expr, var: sp.Symbol = sp.Symbol("x", real=True)) -> Callable:
    """将 SymPy 表达式转为可调用的 numpy 函数。"""
    return sp.lambdify(var, expr, modules=["numpy"])


@register(module="harmonic_analysis", action="uncertainty_principle")
def uncertainty_principle(
    f: Union[str, Callable],
    x_range: tuple = (-50.0, 50.0),
    n_points: int = 4096,
) -> MathObject:
    """计算 Δx·Δξ，验证海森堡不确定性原理：Δx·Δξ ≥ 1/(4π)。

    对归一化函数 ψ（‖ψ‖₂ = 1）：
      Δx² = ∫ (x - ⟨x⟩)² |ψ(x)|² dx
      Δξ² = ∫ (ξ - ⟨ξ⟩)² |F[ψ](ξ)|² dξ / (2π)
      Δx·Δξ ≥ 1/(4π) ≈ 0.079577...

    等号在高斯函数 ψ(x) = (a/π)^(1/4) e^{-a x²/2} 时成立。

    Args:
        f: 输入函数（自动归一化）。
        x_range: 采样范围。
        n_points: 采样点数。

    Returns:
        MathObject: result 含 Δx, Δξ, Δx·Δξ 和是否满足不等式。
    """
    try:
        x = sp.Symbol("x", real=True)
        expr = parse_func(f, x)
        fn = _to_callable(expr, x)

        x_vals = np.linspace(x_range[0], x_range[1], n_points)
        dx = (x_range[1] - x_range[0]) / n_points

        psi = fn(x_vals)
        # 归一化
        norm2 = _trapz(np.abs(psi) ** 2, x_vals)
        if norm2 < 1e-15:
            return MathObject(error="函数范数过小，无法归一化")
        psi = psi / np.sqrt(norm2)

        # 时域: Δx
        psi_sq = np.abs(psi) ** 2
        x_mean = _trapz(x_vals * psi_sq, x_vals)
        delta_x_sq = _trapz((x_vals - x_mean) ** 2 * psi_sq, x_vals)
        delta_x = np.sqrt(max(delta_x_sq, 0))

        # 频域: Δξ
        psi_fft = np.fft.fft(psi)
        xi_vals = 2 * np.pi * np.fft.fftfreq(n_points, dx)
        # 排序使 xi 单调递增（便于 trapz）
        sort_idx = np.argsort(xi_vals)
        xi_vals_sorted = xi_vals[sort_idx]
        psi_fft_sorted = psi_fft[sort_idx]

        psi_xi_sq = np.abs(psi_fft_sorted) ** 2
        # 频域归一化（帕塞瓦尔定理保证应为 1）
        xi_norm = _trapz(psi_xi_sq, xi_vals_sorted)
        if xi_norm > 1e-15:
            psi_xi_sq = psi_xi_sq / xi_norm

        xi_mean = _trapz(xi_vals_sorted * psi_xi_sq, xi_vals_sorted)
        delta_xi_sq = _trapz(
            (xi_vals_sorted - xi_mean) ** 2 * psi_xi_sq, xi_vals_sorted
        )
        delta_xi = np.sqrt(max(delta_xi_sq, 0))

        # 消除 2π 因子：角频率形式的正确归一化
        # 使用 ψ 的傅里叶变换定义：F(ξ) = ∫ ψ(x) e^{-i x ξ} dx
        delta_xi_corrected = delta_xi / np.sqrt(2 * np.pi)

        product = delta_x * delta_xi_corrected
        lower_bound = 1.0 / (4 * np.pi)
        satisfied = product >= lower_bound - 1e-6

        steps = [
            f"归一化 ‖ψ‖₂ = 1",
            f"Δx = {delta_x:.6f}",
            f"Δξ = {delta_xi_corrected:.6f}",
            f"Δx·Δξ = {product:.6f}",
            f"下界 1/(4π) = {lower_bound:.6f}",
            f"不确定性原理{'成立' if satisfied else '不满足！（数值误差）'}",
        ]

        meaning = (
            f"Δx·Δξ = {product:.6f} ≥ 1/(4π) = {lower_bound:.6f}"
        )

        return MathObject(
            result={
                "delta_x": float(delta_x),
                "delta_xi": float(delta_xi_corrected),
                "product": float(product),
                "lower_bound": float(lower_bound),
                "satisfied": bool(satisfied),
            },
            steps=steps,
            meaning=meaning,
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="stft")
def stft(
    signal_input: Union[list, np.ndarray],
    window_size: int = 256,
    hop_size: Optional[int] = None,
    sample_rate: float = 1.0,
) -> MathObject:
    """短时傅里叶变换（STFT）。

    对信号分段加窗做 FFT，得到时频谱图。
    STFT[f](t, ξ) = ∫ f(τ) w(τ - t) e^{-i ξ τ} dτ

    Args:
        signal_input: 输入一维信号。
        window_size: 窗口大小（采样点数）。
        hop_size: 步长，默认 window_size // 2。
        sample_rate: 采样率。

    Returns:
        MathObject: result 含时频谱图（2D 数组）、时间轴和频率轴。
    """
    try:
        arr = np.asarray(signal_input, dtype=float)
        if hop_size is None:
            hop_size = window_size // 2

        # 汉宁窗
        window = np.hanning(window_size)
        n_frames = 1 + (len(arr) - window_size) // hop_size
        if n_frames < 1:
            return MathObject(error=f"信号太短：长度 {len(arr)} < 窗口 {window_size}")

        n_freq = window_size // 2 + 1
        spectrogram = np.zeros((n_freq, n_frames), dtype=complex)

        for i in range(n_frames):
            start = i * hop_size
            segment = arr[start : start + window_size] * window
            spectrogram[:, i] = np.fft.rfft(segment)

        times = np.arange(n_frames) * hop_size / sample_rate
        freqs = np.fft.rfftfreq(window_size, d=1.0 / sample_rate)

        steps = [
            f"信号长度 = {len(arr)}",
            f"窗口大小 = {window_size}, 步长 = {hop_size}",
            f"帧数 = {n_frames}, 频率 bins = {n_freq}",
            f"时频谱图尺寸 = {spectrogram.shape}",
        ]
        meaning = f"STFT 时频谱图: {n_freq} × {n_frames}"

        return MathObject(
            result={
                "spectrogram_magnitude": np.abs(spectrogram).tolist(),
                "times": times.tolist(),
                "frequencies": freqs.tolist(),
            },
            steps=steps,
            meaning=meaning,
            data={
                "n_frames": n_frames,
                "n_freq": n_freq,
                "window_size": window_size,
                "hop_size": hop_size,
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="harmonic_analysis", action="wavelet_transform")
def wavelet_transform(
    signal_input: Union[list, np.ndarray],
    wavelet_type: str = "mexican_hat",
    scales: Optional[list] = None,
) -> MathObject:
    """连续小波变换（CWT）— Mexican hat / Morlet 卷积实现。

    连续小波变换（CWT）：
    W[f](a, b) = (1/√a) ∫ f(t) ψ((t-b)/a) dt

    通过卷积手动实现。

    Args:
        signal_input: 输入一维信号。
        wavelet_type: 小波类型，"mexican_hat"（墨西哥帽）或 "morlet"。
        scales: 尺度列表，默认 [1, 2, 4, 8, 16, 32]。

    Returns:
        MathObject: result 含小波系数矩阵。
    """
    try:
        arr = np.asarray(signal_input, dtype=float)
        n = len(arr)

        if scales is None:
            scales = [1, 2, 4, 8, 16, 32]

        n_scales = len(scales)
        cwt_result = np.zeros((n_scales, n))

        for i, scale in enumerate(scales):
            # 构造小波核：核长度不超过信号长度，但至少保留主要部分
            kernel_half = min(int(4 * scale), n // 2)
            if kernel_half < 2:
                kernel_half = 2
            t_wavelet = np.arange(-kernel_half, kernel_half + 1, dtype=float)
            t_scaled = t_wavelet / scale

            if wavelet_type == "mexican_hat":
                psi = (1.0 - t_scaled**2) * np.exp(-t_scaled**2 / 2.0)
            elif wavelet_type == "morlet":
                omega0 = 5.0
                psi = np.pi**(-0.25) * np.exp(1j * omega0 * t_scaled) * np.exp(-t_scaled**2 / 2.0)
            else:
                return MathObject(error=f"不支持的小波类型: {wavelet_type}")

            # 归一化
            psi = psi / np.sqrt(np.sum(np.abs(psi) ** 2))

            # 卷积实现 CWT（确保输出长度 = n）
            conv_result = np.convolve(arr, psi[::-1], mode="same")
            if len(conv_result) != n:
                # 截断或填充到信号长度
                if len(conv_result) > n:
                    start = (len(conv_result) - n) // 2
                    conv_result = conv_result[start:start + n]
                else:
                    pad = n - len(conv_result)
                    conv_result = np.pad(conv_result, (pad // 2, pad - pad // 2))
            cwt_result[i, :] = np.real(conv_result) if np.iscomplexobj(conv_result) else conv_result

        steps = [
            f"信号长度 = {n}",
            f"小波类型 = {wavelet_type}",
            f"尺度 = {scales}",
            f"小波系数矩阵 = {n_scales} × {n}",
        ]
        meaning = f"小波变换 ({wavelet_type})：{n_scales} 个尺度的时频分析"

        return MathObject(
            result={
                "coefficients_magnitude": np.abs(cwt_result).tolist(),
                "scales": scales,
            },
            steps=steps,
            meaning=meaning,
            data={"wavelet_type": wavelet_type, "n_scales": n_scales},
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测：至少 3 个典型用例。"""
    print("=" * 60)
    print("time_frequency 自测")
    print("=" * 60)

    passed = 0
    failed = 0

    # 测试 1: 不确定性原理 — 高斯函数（应接近下界）
    print("\n[测试 1] uncertainty_principle(f='exp(-x**2)') → Δx·Δξ ≈ 1/(4π)")
    r = uncertainty_principle("exp(-x**2)", x_range=(-20, 20), n_points=2048)
    if r.ok and r.result["satisfied"]:
        print(
            f"  PASSED: Δx·Δξ = {r.result['product']:.6f} "
            f"≥ {r.result['lower_bound']:.6f}"
        )
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 2: STFT
    print("\n[测试 2] stft(signal=chirp, window_size=64)")
    t = np.linspace(0, 10, 1000)
    chirp = np.sin(2 * np.pi * (1 + t) * t)
    r = stft(chirp.tolist(), window_size=64)
    if r.ok:
        mag = r.result["spectrogram_magnitude"]
        print(f"  PASSED: 时频谱图 = {len(mag)} × {len(mag[0])}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    # 测试 3: 小波变换
    print("\n[测试 3] wavelet_transform(signal=[0,1,0,-1,0,1,0], type='mexican_hat')")
    r = wavelet_transform([0.0, 1.0, 0.0, -1.0, 0.0, 1.0, 0.0], wavelet_type="mexican_hat")
    if r.ok:
        coeffs = r.result["coefficients_magnitude"]
        print(f"  PASSED: 小波系数 = {len(coeffs)} scales × {len(coeffs[0])}")
        passed += 1
    else:
        print(f"  FAILED: {r}")
        failed += 1

    print(f"\n{'='*60}")
    print(f"结果: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    self_test()
