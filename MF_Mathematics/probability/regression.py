"""回归分析 — 一元线性回归（最小二乘法）、预测与残差分析。

依赖: numpy, scipy.stats
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="probability", action="linear_regression")
def linear_regression(
    x_data: List[float],
    y_data: List[float],
) -> MathObject:
    """一元线性回归 y = β₀ + β₁·x（最小二乘法）。

    β₁ = Sxy / Sxx,  β₀ = ȳ - β₁·x̄。
    R² = 1 - SS_res / SS_tot。

    Args:
        x_data: 自变量观测值列表。
        y_data: 因变量观测值列表。

    Returns:
        MathObject:
            - result: {"slope": β₁, "intercept": β₀, "r_squared": R²,
                       "model": "y = β₀ + β₁·x"}。
    """
    try:
        x = np.asarray(x_data, dtype=float)
        y = np.asarray(y_data, dtype=float)
        n = len(x)

        if n != len(y):
            return MathObject(error="x_data 和 y_data 长度必须相同。")
        if n < 2:
            return MathObject(error="至少需要 2 个数据点。")

        x_mean = float(np.mean(x))
        y_mean = float(np.mean(y))

        # 最小二乘估计
        Sxy = np.sum((x - x_mean) * (y - y_mean))
        Sxx = np.sum((x - x_mean) ** 2)

        if abs(Sxx) < 1e-15:
            return MathObject(error="x 方差为零，无法拟合回归线。")

        beta1 = Sxy / Sxx
        beta0 = y_mean - beta1 * x_mean

        # R²
        y_pred = beta0 + beta1 * x
        SS_res = np.sum((y - y_pred) ** 2)
        SS_tot = np.sum((y - y_mean) ** 2)
        r_squared = 1 - SS_res / SS_tot if SS_tot > 1e-15 else 1.0

        return MathObject(
            result={
                "slope": float(beta1),
                "intercept": float(beta0),
                "r_squared": float(r_squared),
                "model": f"y = {beta0:.4f} + {beta1:.4f}·x",
                "n": n,
            },
            steps=[
                f"样本量 n = {n}",
                f"x̄ = {x_mean:.4f},  ȳ = {y_mean:.4f}",
                f"Sxy = Σ(xi - x̄)(yi - ȳ) = {Sxy:.4f}",
                f"Sxx = Σ(xi - x̄)² = {Sxx:.4f}",
                f"β₁ = Sxy / Sxx = {beta1:.4f}",
                f"β₀ = ȳ - β₁·x̄ = {beta0:.4f}",
                f"SS_res = {SS_res:.4f},  SS_tot = {SS_tot:.4f}",
                f"R² = 1 - SS_res/SS_tot = {r_squared:.4f}",
            ],
            meaning=f"回归方程: y = {beta0:.4f} + {beta1:.4f}x, "
                    f"R² = {r_squared:.4f}（{'强' if r_squared > 0.7 else '中等' if r_squared > 0.4 else '弱'}拟合度）。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="predict")
def predict(
    model: Dict[str, Any],
    x: Union[float, List[float]],
) -> MathObject:
    """用线性回归模型做预测。

    Args:
        model: linear_regression 返回的 result 字典，至少包含 slope 和 intercept。
        x: 自变量值或列表。

    Returns:
        MathObject:
            - result: 预测值或预测值列表。
    """
    try:
        # 兼容 MathObject 和 dict 两种输入
        _model = model.result if hasattr(model, 'result') and isinstance(model.result, dict) else model
        beta0 = _model.get("intercept")
        beta1 = _model.get("slope")
        if beta0 is None or beta1 is None:
            return MathObject(error="模型字典必须包含 'intercept' 和 'slope'。")

        if isinstance(x, (int, float)):
            y_pred = beta0 + beta1 * x
            return MathObject(
                result=float(y_pred),
                steps=[f"ŷ = {beta0:.4f} + {beta1:.4f}·{x} = {y_pred:.4f}"],
                meaning=f"在 x = {x} 处，预测 y = {y_pred:.4f}。",
            )
        else:
            x_arr = np.asarray(x, dtype=float)
            y_pred_arr = beta0 + beta1 * x_arr
            return MathObject(
                result=y_pred_arr.tolist(),
                steps=[f"对 {len(x_arr)} 个点批量预测"],
                meaning=f"模型: y = {beta0:.4f} + {beta1:.4f}·x。",
            )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="residuals")
def residuals(
    model: Dict[str, Any],
    x_data: List[float],
    y_data: List[float],
) -> MathObject:
    """计算回归残差 ei = yi - ŷi。

    Args:
        model: linear_regression 返回的 result 字典。
        x_data: 自变量数据。
        y_data: 因变量观测值。

    Returns:
        MathObject:
            - result: {"residuals": [...], "SSE": ..., "MSE": ...}。
    """
    try:
        # 兼容 MathObject 和 dict 两种输入
        _model = model.result if hasattr(model, 'result') and isinstance(model.result, dict) else model
        beta0 = _model.get("intercept")
        beta1 = _model.get("slope")
        if beta0 is None or beta1 is None:
            return MathObject(error="模型字典必须包含 'intercept' 和 'slope'。")

        x = np.asarray(x_data, dtype=float)
        y = np.asarray(y_data, dtype=float)
        y_pred = beta0 + beta1 * x
        e = y - y_pred

        SSE = float(np.sum(e**2))
        MSE = SSE / (len(x) - 2) if len(x) > 2 else SSE

        return MathObject(
            result={
                "residuals": e.tolist(),
                "SSE": SSE,
                "MSE": float(MSE),
                "n": len(x),
            },
            steps=[
                f"ŷ_i = {beta0:.4f} + {beta1:.4f}·x_i",
                f"残差 e_i: {[f'{v:.4f}' for v in e]}",
                f"SSE = Σ e_i² = {SSE:.4f}",
                f"MSE = SSE/(n-2) = {MSE:.4f}",
            ],
            meaning=f"残差分析: SSE={SSE:.4f}, MSE={MSE:.4f}。"
                    f"MSE 越小拟合越好。",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """模块自测。"""
    print("=== regression 自测 ===")

    # 完美线性: (1,2), (2,4), (3,6)
    r1 = linear_regression([1, 2, 3], [2, 4, 6])
    assert r1.ok, r1.error
    assert abs(r1.result["slope"] - 2.0) < 0.01, f"slope={r1.result['slope']}"
    assert abs(r1.result["intercept"] - 0.0) < 0.01, f"intercept={r1.result['intercept']}"
    assert abs(r1.result["r_squared"] - 1.0) < 0.01, f"R²={r1.result['r_squared']}"
    print(f"  linear_regression: {r1.result['model']}, R²={r1.result['r_squared']:.4f}  PASSED")

    # 预测
    r2 = predict(r1.result, x=4)
    assert r2.ok, r2.error
    assert abs(r2.result - 8.0) < 0.01, r2.result
    print(f"  predict(x=4): {r2.result}  PASSED")

    # 残差
    r3 = residuals(r1.result, [1, 2, 3], [2, 4, 6])
    assert r3.ok, r3.error
    assert abs(r3.result["SSE"]) < 0.01, f"SSE={r3.result['SSE']}"
    print(f"  residuals: SSE={r3.result['SSE']:.6f}  PASSED")

    # 带噪声的回归
    r4 = linear_regression([0, 1, 2, 3, 4], [1, 3, 5, 7, 9])
    assert r4.ok, r4.error
    assert abs(r4.result["slope"] - 2.0) < 0.01, r4.result
    assert abs(r4.result["intercept"] - 1.0) < 0.01, r4.result
    print(f"  linear_regression (带截距): {r4.result['model']}  PASSED")

    print("regression 自测全部通过!\n")
    return True


if __name__ == "__main__":
    self_test()
