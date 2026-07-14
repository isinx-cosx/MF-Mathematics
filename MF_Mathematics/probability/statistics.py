"""统计推断 — 总体与样本、参数估计（点估计与区间估计）。

依赖: numpy, scipy.stats
"""

from __future__ import annotations

from typing import Any, List, Tuple, Union

import numpy as np
from scipy import stats as sc_stats

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="probability", action="sample_mean")
def sample_mean(data: List[float]) -> MathObject:
    """计算样本均值。

    Args:
        data: 样本数据列表。

    Returns:
        MathObject:
            - result: 样本均值。
    """
    try:
        arr = np.asarray(data, dtype=float)
        if len(arr) == 0:
            return MathObject(error="样本数据为空。")
        mean_val = float(np.mean(arr))
        return MathObject(
            result=mean_val,
            steps=[f"样本容量 n = {len(arr)}", f"X̄ = Σxi/n = {mean_val:.6f}"],
            meaning="样本均值是总体均值的无偏估计。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="sample_variance")
def sample_variance(data: List[float], ddof: int = 1) -> MathObject:
    """计算样本方差。

    Args:
        data: 样本数据列表。
        ddof: 自由度调整（1 = 无偏估计 s²，0 = 有偏估计）。

    Returns:
        MathObject:
            - result: 样本方差。
    """
    try:
        arr = np.asarray(data, dtype=float)
        n = len(arr)
        if n < 2 and ddof == 1:
            return MathObject(error="样本量 n < 2 时，无偏方差无定义 (ddof=1)。")
        var_val = float(np.var(arr, ddof=ddof))
        return MathObject(
            result=var_val,
            steps=[
                f"样本容量 n = {n}",
                f"样本均值 = {np.mean(arr):.6f}",
                f"{'无偏' if ddof == 1 else '有偏'}样本方差 = {var_val:.6f}",
            ],
            meaning=f"{'无偏' if ddof == 1 else '有偏'}样本方差"
                    f"{'s²' if ddof == 1 else 'σ̂²'} = {var_val:.6f}。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="moment_estimate")
def moment_estimate(
    data: List[float],
    dist: str,
) -> MathObject:
    """矩估计法：用样本矩替代总体矩求解参数。

    支持分布: 'normal' / 'exponential' / 'poisson' / 'uniform' / 'binomial'。

    Args:
        data: 样本数据。
        dist: 分布名。

    Returns:
        MathObject:
            - result: 参数估计值字典。
    """
    try:
        arr = np.asarray(data, dtype=float)
        n = len(arr)
        if n == 0:
            return MathObject(error="样本为空。")

        m1 = float(np.mean(arr))
        m2 = float(np.mean(arr**2))

        dist_lower = dist.lower()

        if dist_lower == "normal":
            mu_hat = m1
            sigma_hat = np.sqrt(m2 - m1**2)
            return MathObject(
                result={"mu_hat": mu_hat, "sigma_hat": sigma_hat},
                steps=[
                    f"样本一阶矩 m1 = {m1:.6f}",
                    f"样本二阶矩 m2 = {m2:.6f}",
                    f"μ̂ = m1 = {mu_hat:.6f}",
                    f"σ̂ = √(m2 - m1²) = {sigma_hat:.6f}",
                ],
                meaning=f"正态分布的矩估计: μ̂={mu_hat:.3f}, σ̂={sigma_hat:.3f}。",
            )
        elif dist_lower == "exponential":
            lam_hat = 1 / m1 if m1 > 0 else float("inf")
            return MathObject(
                result={"lambda_hat": lam_hat},
                steps=[f"样本均值 = {m1:.6f}", f"λ̂ = 1/X̄ = {lam_hat:.6f}"],
                meaning=f"指数分布的矩估计: λ̂={lam_hat:.3f}。",
            )
        elif dist_lower == "poisson":
            lam_hat = m1
            return MathObject(
                result={"lambda_hat": lam_hat},
                steps=[f"样本均值 = {m1:.6f}", f"λ̂ = X̄ = {lam_hat:.6f}"],
                meaning=f"泊松分布的矩估计: λ̂={lam_hat:.3f}。",
            )
        elif dist_lower == "uniform":
            # E[X] = (a+b)/2, Var = (b-a)²/12
            var_m = m2 - m1**2
            half_range = np.sqrt(3 * max(var_m, 0))
            a_hat = m1 - half_range
            b_hat = m1 + half_range
            return MathObject(
                result={"a_hat": a_hat, "b_hat": b_hat},
                steps=[
                    f"样本均值 = {m1:.6f}",
                    f"样本方差 = {var_m:.6f}",
                    f"â = X̄ - √3·S = {a_hat:.6f}",
                    f"b̂ = X̄ + √3·S = {b_hat:.6f}",
                ],
                meaning=f"均匀分布的矩估计: â={a_hat:.3f}, b̂={b_hat:.3f}。",
            )
        elif dist_lower == "binomial":
            # 需要指定 n？这里假设 n 由用户提供在 data 里无法推断
            var_m = m2 - m1**2
            if abs(m1) < 1e-12:
                return MathObject(error="样本均值为零，无法估计二项分布参数。")
            # p̂ = 1 - var/m1 仅当知道 n 时
            # 保守：p̂ = X̄/n，n 未知则设为 ceil 合理值
            return MathObject(
                error="二项分布的矩估计需要同时提供 n 或额外信息。",
                result={"method": "moment", "note": "需要 n 参数"},
            )
        else:
            return MathObject(error=f"不支持的分布: '{dist}'。可选: normal, exponential, poisson, uniform。")
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="mle")
def mle(data: List[float], dist: str) -> MathObject:
    """最大似然估计（MLE）占位实现。

    当前支持 scipy.stats 的 fit 方法进行 MLE。

    Args:
        data: 样本数据。
        dist: 分布名 ('normal', 'exponential', 'poisson')。

    Returns:
        MathObject:
            - result: MLE 参数估计值。
    """
    try:
        arr = np.asarray(data, dtype=float)
        if len(arr) == 0:
            return MathObject(error="样本为空。")

        dist_lower = dist.lower()

        if dist_lower == "normal":
            loc, scale = sc_stats.norm.fit(arr)
            return MathObject(
                result={"mu_mle": float(loc), "sigma_mle": float(scale)},
                steps=[
                    f"对数似然最大化 → μ̂_MLE = {loc:.6f}, σ̂_MLE = {scale:.6f}",
                ],
                meaning=f"正态分布 MLE: μ̂={loc:.3f}, σ̂={scale:.3f}。",
            )
        elif dist_lower == "exponential":
            loc, scale = sc_stats.expon.fit(arr, floc=0)
            lam_mle = 1 / scale
            return MathObject(
                result={"lambda_mle": float(lam_mle)},
                steps=[f"对数似然最大化 → λ̂_MLE = 1/X̄ = {lam_mle:.6f}"],
                meaning=f"指数分布 MLE: λ̂={lam_mle:.3f}。",
            )
        elif dist_lower == "poisson":
            lam_mle = float(np.mean(arr))
            return MathObject(
                result={"lambda_mle": lam_mle},
                steps=[f"λ̂_MLE = X̄ = {lam_mle:.6f}"],
                meaning=f"泊松分布 MLE: λ̂={lam_mle:.3f}。",
            )
        else:
            return MathObject(error=f"MLE 当前仅支持 normal / exponential / poisson，不支持 '{dist}'。")
    except Exception as e:
        return MathObject(error=str(e))


@register(module="probability", action="confidence_interval")
def confidence_interval(
    data: List[float],
    confidence: float = 0.95,
) -> MathObject:
    """计算正态总体均值的置信区间（σ 未知，t 分布）。

    Args:
        data: 样本数据列表。
        confidence: 置信水平，默认 0.95。

    Returns:
        MathObject:
            - result: {"lower": ..., "upper": ..., "confidence": ...}。
    """
    try:
        arr = np.asarray(data, dtype=float)
        n = len(arr)
        if n < 2:
            return MathObject(error="样本量 n < 2，无法计算 t 置信区间。")
        if not 0 < confidence < 1:
            return MathObject(error="置信水平必须在 (0, 1) 之间。")

        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr, ddof=1))
        alpha = 1 - confidence

        t_crit = sc_stats.t.ppf(1 - alpha / 2, df=n - 1)
        margin = t_crit * std_val / np.sqrt(n)

        lower = mean_val - margin
        upper = mean_val + margin

        return MathObject(
            result={
                "lower": float(lower),
                "upper": float(upper),
                "mean": mean_val,
                "margin": float(margin),
                "confidence": confidence,
                "n": n,
            },
            steps=[
                f"样本容量 n = {n}",
                f"样本均值 X̄ = {mean_val:.6f}",
                f"样本标准差 s = {std_val:.6f}",
                f"自由度 df = n-1 = {n - 1}",
                f"α = 1 - confidence = {alpha:.2f}",
                f"t_{{α/2}}({n - 1}) = {t_crit:.4f}",
                f"误差边际 = t·s/√n = {margin:.6f}",
                f"{confidence*100:.0f}% 置信区间: "
                f"({lower:.4f}, {upper:.4f})",
            ],
            meaning=f"有 {confidence*100:.0f}% 的把握认为总体均值落在 "
                    f"({lower:.4f}, {upper:.4f}) 内。",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """模块自测。"""
    print("=== statistics 自测 ===")

    # 样本均值
    r1 = sample_mean([1, 2, 3, 4, 5])
    assert r1.ok and abs(r1.result - 3.0) < 0.01, r1.error
    print(f"  sample_mean: {r1.result}  PASSED")

    # 样本方差
    r2 = sample_variance([1, 2, 3, 4, 5])
    assert r2.ok and abs(r2.result - 2.5) < 0.01, r2.result
    print(f"  sample_variance: {r2.result}  PASSED")

    # 矩估计（正态）
    r3 = moment_estimate([1, 2, 3, 4, 5], "normal")
    assert r3.ok, r3.error
    print(f"  moment_estimate (normal): μ̂={r3.result['mu_hat']:.3f}, σ̂={r3.result['sigma_hat']:.3f}  PASSED")

    # 矩估计（指数）
    r4 = moment_estimate([1, 2, 3], "exponential")
    assert r4.ok, r4.error
    print(f"  moment_estimate (exponential): λ̂={r4.result['lambda_hat']:.3f}  PASSED")

    # MLE（正态）
    r5 = mle([1, 2, 3, 4, 5], "normal")
    assert r5.ok, r5.error
    print(f"  mle (normal): μ̂={r5.result['mu_mle']:.3f}, σ̂={r5.result['sigma_mle']:.3f}  PASSED")

    # 置信区间
    r6 = confidence_interval([1, 2, 3, 4, 5], 0.95)
    assert r6.ok, r6.error
    assert r6.result["lower"] < 3.0 < r6.result["upper"], "均值不在区间内"
    print(f"  confidence_interval: [{r6.result['lower']:.3f}, {r6.result['upper']:.3f}]  PASSED")

    print("statistics 自测全部通过!\n")
    return True


if __name__ == "__main__":
    self_test()
