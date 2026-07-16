# -*- coding: utf-8 -*-
"""时间序列 — 移动平均、指数平滑、简单预测。

依赖: numpy
"""

from __future__ import annotations

from typing import List, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="probability", action="moving_average")
def moving_average(
    data: List[float],
    window: int = 3,
) -> MathObject:
    """计算简单移动平均 (SMA)。

    Args:
        data: 时间序列数据。
        window: 滑动窗口大小。

    Returns:
        MathObject，result 包含平滑后的序列。
    """
    try:
        arr = np.array(data, dtype=float)
        if len(arr) < window:
            return MathObject(error=f"数据长度({len(arr)})必须 ≥ 窗口({window})")
        sma = np.convolve(arr, np.ones(window) / window, mode="valid")
        return MathObject(
            result={"smoothed": sma.tolist(), "window": window, "n": len(data)},
            steps=[
                f"原始序列: {len(data)} 个数据点",
                f"窗口大小: {window}",
                f"移动平均: {len(sma)} 个点",
                f"首值: {sma[0]:.4f}, 尾值: {sma[-1]:.4f}",
            ],
            meaning=f"{window}-点移动平均，序列长度 {len(data)}→{len(sma)}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="exp_smoothing")
def exp_smoothing(
    data: List[float],
    alpha: float = 0.3,
) -> MathObject:
    """指数平滑 (SES)。

    s_t = α·y_t + (1-α)·s_{t-1}

    Args:
        data: 时间序列数据。
        alpha: 平滑系数 (0 < α < 1)。

    Returns:
        MathObject，result 包含平滑序列和预测值。
    """
    try:
        if not 0 < alpha < 1:
            return MathObject(error="alpha 必须在 (0, 1) 之间")
        arr = np.array(data, dtype=float)
        smoothed = [arr[0]]
        for i in range(1, len(arr)):
            smoothed.append(alpha * arr[i] + (1 - alpha) * smoothed[-1])
        forecast = smoothed[-1]
        return MathObject(
            result={
                "smoothed": smoothed,
                "forecast": float(forecast),
                "alpha": alpha,
            },
            steps=[
                f"指数平滑 (α={alpha})",
                f"序列长度: {len(data)}",
                f"平滑值: s_1={smoothed[0]:.4f} → s_n={smoothed[-1]:.4f}",
                f"下期预测: {forecast:.4f}",
            ],
            meaning=f"指数平滑(α={alpha}): 预测 = {forecast:.4f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="linear_trend")
def linear_trend(
    data: List[float],
    forecast_steps: int = 3,
) -> MathObject:
    """线性趋势拟合与预测。

    Args:
        data: 时间序列数据。
        forecast_steps: 预测步数。

    Returns:
        MathObject，result 包含趋势线参数和预测值。
    """
    try:
        arr = np.array(data, dtype=float)
        n = len(arr)
        t = np.arange(n)
        slope, intercept = np.polyfit(t, arr, 1)
        trend = slope * t + intercept
        forecasts = [slope * (n + i) + intercept for i in range(1, forecast_steps + 1)]
        r2 = 1 - np.sum((arr - trend) ** 2) / np.sum((arr - arr.mean()) ** 2)

        return MathObject(
            result={
                "slope": float(slope),
                "intercept": float(intercept),
                "r_squared": float(r2),
                "forecasts": [float(f) for f in forecasts],
                "trend": trend.tolist(),
            },
            steps=[
                f"线性趋势: y = {intercept:.4f} + {slope:.4f}·t",
                f"R² = {r2:.4f}",
                f"预测 ({forecast_steps} 步): {[f'{f:.2f}' for f in forecasts]}",
            ],
            meaning=f"趋势: {slope:.4f}·t + {intercept:.4f}, R²={r2:.4f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    print("=== time_series self_test ===")
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    r = moving_average(data, 3)
    assert r.ok and len(r.result["smoothed"]) == 5
    print(f"  PASS SMA(3): {r.result['smoothed'][:3]}")

    r2 = exp_smoothing(data, 0.5)
    assert r2.ok and abs(r2.result["forecast"] - 7.0) < 2
    print(f"  PASS SES: forecast={r2.result['forecast']:.2f}")

    r3 = linear_trend(data, 2)
    assert r3.ok and r3.result["r_squared"] > 0.9
    print(f"  PASS Trend: R²={r3.result['r_squared']:.4f}, forecast={r3.result['forecasts']}")
    print("=== time_series self_test: ALL PASSED ===")
    return True


if __name__ == "__main__":
    self_test()
