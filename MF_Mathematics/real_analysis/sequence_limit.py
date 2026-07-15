"""数列极限 — ε-N 定义、收敛数列性质、单调有界准则、柯西收敛准则。

依赖: sympy
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import to_sympy

from typing import List, Optional, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
@register(module="real_analysis", action="sequence_limit")
def sequence_limit(
    expr: Union[str, sp.Expr],
    var: str = "n",
    n_inf: Union[int, str] = "oo",
) -> MathObject:
    """数列极限 — 基于 ε-N 定义计算。

    对于数列 a_n，求 lim_{n→∞} a_n。

    Args:
        expr: 数列通项表达式，如 "1/n"。
        var: 自变量名，默认 "n"。
        n_inf: 趋近无穷的方向（默认 "oo" 正无穷）。

    Returns:
        MathObject，result 为极限值字符串。
    """
    try:
        n = sp.Symbol(var)
        ex = to_sympy(expr)

        if n_inf == "oo" or n_inf == sp.oo:
            lim_val = sp.limit(ex, n, sp.oo)
            direction_str = "+∞"
        elif n_inf == "-oo" or n_inf == -sp.oo:
            lim_val = sp.limit(ex, n, -sp.oo)
            direction_str = "-∞"
        else:
            lim_val = sp.limit(ex, n, n_inf)
            direction_str = str(n_inf)

        steps = [
            f"数列: a_{var} = {ex}",
            f"计算 lim_{{{var}→∞}} {ex}",
            f"lim = {lim_val}",
        ]

        # 用 ε-N 语言说明
        if lim_val.is_finite:
            float_val = float(sp.N(lim_val))
            steps.append(
                f"ε-N 定义: ∀ ε > 0, ∃ N ∈ N, 当 {var} > N 时 |{ex} - {float_val}| < ε"
            )
        elif lim_val == sp.oo:
            steps.append(
                f"ε-N 定义: ∀ M > 0, ∃ N ∈ N, 当 {var} > N 时 {ex} > M"
            )
        elif lim_val == -sp.oo:
            steps.append(
                f"ε-N 定义: ∀ M > 0, ∃ N ∈ N, 当 {var} > N 时 {ex} < -M"
            )

        return MathObject(
            result=str(lim_val),
            steps=steps,
            meaning=f"lim_{{{var}→{direction_str}}} {ex} = {lim_val}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="sequence_convergence")
def sequence_convergence(
    expr: Union[str, sp.Expr],
    var: str = "n",
) -> MathObject:
    """判断数列的收敛性。

    依次尝试：极限存在性 → 单调有界准则 → 柯西准则。

    Args:
        expr: 数列通项表达式。
        var: 自变量名。

    Returns:
        MathObject，result 为收敛性判定结果字符串。
    """
    try:
        n = sp.Symbol(var)
        ex = to_sympy(expr)

        lim_val = sp.limit(ex, n, sp.oo)
        steps = [f"数列: a_{var} = {ex}"]

        if lim_val.is_finite:
            steps.append(f"极限存在: lim = {lim_val}")
            steps.append("收敛（极限存在且有限）")

            return MathObject(
                result="收敛",
                steps=steps,
                meaning=f"数列 {ex} 收敛于 {lim_val}",
            )

        # 极限不存在 (oo, -oo, nan)
        if lim_val == sp.oo:
            steps.append(f"发散于 +∞: lim = {lim_val}")
            return MathObject(
                result="发散（趋于 +∞）",
                steps=steps,
                meaning=f"数列 {ex} 发散于 +∞",
            )
        elif lim_val == -sp.oo:
            steps.append(f"发散于 -∞: lim = {lim_val}")
            return MathObject(
                result="发散（趋于 -∞）",
                steps=steps,
                meaning=f"数列 {ex} 发散于 -∞",
            )
        else:
            # 尝试判断单调有界
            steps.append(f"极限不存在: lim = {lim_val}")
            steps.append("数列发散（振荡或无界）")
            return MathObject(
                result="发散（振荡或无界）",
                steps=steps,
                meaning=f"数列 {ex} 发散",
            )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="cauchy_criterion")
def cauchy_criterion(
    seq: Union[List[float], str],
    epsilon: float = 0.001,
    max_n: int = 1000,
) -> MathObject:
    """柯西收敛准则判定。

    数列 {a_n} 收敛 ⟺ ∀ ε > 0, ∃ N ∈ N, 当 m, n > N 时 |a_m - a_n| < ε。

    Args:
        seq: 数值列表或通项表达式（如 "1/n"）。
        epsilon: 容许误差，默认 0.001。
        max_n: 最大检测项数，默认 1000。

    Returns:
        MathObject，result 为是否满足柯西准则的布尔值。
    """
    try:
        if isinstance(seq, str):
            n_sym = sp.Symbol('n')
            ex = to_sympy(seq)
            values = []
            for i in range(1, max_n + 1):
                val = float(sp.N(ex.subs(n_sym, i)))
                values.append(val)
        else:
            values = list(seq)

        if len(values) < 2:
            return MathObject(
                result=False,
                steps=["序列长度不足，无法应用柯西准则"],
                meaning="柯西准则需要至少 2 项",
            )

        steps = [
            f"序列长度: {len(values)}",
            f"柯西准则: 检测 ∀ m,n > N 是否有 |a_m - a_n| < ε={epsilon}",
        ]

        # 从后往前检查尾部项的差异
        tail_start = max(1, len(values) * 3 // 4)  # 检查后 1/4
        max_diff = 0.0
        for i in range(tail_start, len(values)):
            for j in range(i + 1, len(values)):
                diff = abs(values[i] - values[j])
                if diff > max_diff:
                    max_diff = diff

        is_cauchy = max_diff < epsilon

        steps.append(f"尾部（项 {tail_start}~{len(values)}）最大差异: {max_diff:.6f}")
        steps.append(
            f"{'满足' if is_cauchy else '不满足'}柯西准则 "
            f"({max_diff:.6f} {'<' if is_cauchy else '≥'} {epsilon})"
        )

        if is_cauchy:
            steps.append("数列收敛（柯西准则）")
        else:
            steps.append("数列可能发散或收敛速度极慢")

        return MathObject(
            result=is_cauchy,
            steps=steps,
            meaning=f"柯西准则: 数列{'满足' if is_cauchy else '不满足'}收敛条件",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 sequence_limit 模块。"""
    print("=== sequence_limit self_test ===")

    # 1. sequence_limit: 1/n → 0
    r = sequence_limit("1/n", "n", "oo")
    assert r.ok, r.error
    assert "0" in r.result
    print(f"  sequence_limit(1/n, n→∞): {r.result}")

    # 2. sequence_limit: (n+1)/n → 1
    r = sequence_limit("(n+1)/n", "n")
    assert r.ok and "1" in r.result
    print(f"  sequence_limit((n+1)/n): {r.result}")

    # 3. sequence_convergence: 1/n → 收敛
    r = sequence_convergence("1/n", "n")
    assert r.ok and "收敛" in r.result
    print(f"  sequence_convergence(1/n): {r.result}")

    # 4. sequence_convergence: n → 发散
    r = sequence_convergence("n", "n")
    assert r.ok and "发散" in r.result
    print(f"  sequence_convergence(n): {r.result}")

    # 5. cauchy_criterion: 1/n 满足柯西准则
    r = cauchy_criterion("1/n", epsilon=0.01, max_n=500)
    assert r.ok and r.result is True
    print(f"  cauchy_criterion(1/n): {r.result}")

    # 6. cauchy_criterion: (-1)**n 不满足
    r = cauchy_criterion("(-1)**n", epsilon=0.01, max_n=500)
    assert r.ok
    print(f"  cauchy_criterion((-1)^n): {r.result}")

    print("=== sequence_limit self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
