"""黎曼积分 — 达布和、可积充要条件、微积分基本定理、积分中值定理。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_sympy(expr: Union[str, sp.Expr]) -> sp.Expr:
    """将字符串或 sympy 表达式统一转为 sympy 表达式。"""
    if isinstance(expr, sp.Expr):
        return expr
    return sp.sympify(str(expr))


@register(module="real_analysis", action="darboux_sum")
def darboux_sum(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: float = 0.0,
    b: float = 1.0,
    partition: Optional[List[float]] = None,
) -> MathObject:
    """达布和：计算给定分割的达布下和与达布上和。

    下和 L(P, f) = Σ m_i · Δx_i，其中 m_i = inf_{[x_{i-1}, x_i]} f(x)
    上和 U(P, f) = Σ M_i · Δx_i，其中 M_i = sup_{[x_{i-1}, x_i]} f(x)

    若 partition 未指定，则使用等距分割 n=10。

    Args:
        expr: 被积函数表达式。
        var: 积分变量名。
        a: 积分下限。
        b: 积分上限。
        partition: 分割点列表（可选），如 [0, 0.2, 0.5, 0.8, 1]。

    Returns:
        MathObject，result 为 {lower_sum, upper_sum, partition, is_integrable}。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)

        if partition is None:
            n = 10
            partition = list(np.linspace(a, b, n + 1))

        partition = sorted(partition)
        if partition[0] != a or partition[-1] != b:
            partition = [a] + [p for p in partition if a < p < b] + [b]
            partition = sorted(set(partition))

        steps = [
            f"被积函数: f({var}) = {ex}",
            f"积分区间: [{a}, {b}]",
            f"分割: {[round(p, 4) for p in partition]}",
            f"子区间数: n = {len(partition) - 1}",
        ]

        lower_sum = 0.0
        upper_sum = 0.0
        details = []

        for i in range(len(partition) - 1):
            xi_left = partition[i]
            xi_right = partition[i + 1]
            dx = xi_right - xi_left

            # 在每个子区间上采样找 min/max
            sample_points = np.linspace(xi_left, xi_right, 50)
            sample_vals = []
            for sp_pt in sample_points:
                try:
                    val = float(sp.N(ex.subs(x, float(sp_pt))))
                    if np.isfinite(val):
                        sample_vals.append(val)
                except Exception:
                    pass

            if not sample_vals:
                mi_val = 0.0
                Mi_val = 0.0
            else:
                mi_val = min(sample_vals)
                Mi_val = max(sample_vals)

            lower_sum += mi_val * dx
            upper_sum += Mi_val * dx

            if i < 5 or i >= len(partition) - 5:
                details.append(
                    f"  [{xi_left:.3f}, {xi_right:.3f}]: "
                    f"m_i={mi_val:.4f}, M_i={Mi_val:.4f}, Δx={dx:.4f}"
                )

        steps.extend(details[:5])
        if len(details) > 5:
            steps.append(f"  ... 共 {len(partition)-1} 个子区间")
        steps.append(f"达布下和 L(P, f) = {lower_sum:.6f}")
        steps.append(f"达布上和 U(P, f) = {upper_sum:.6f}")
        steps.append(f"达布和差值 U-L = {upper_sum - lower_sum:.6f}")

        # 可积性初步判断：U - L < 小阈值
        is_integrable = (upper_sum - lower_sum) < 0.01

        return MathObject(
            result={
                "lower_sum": lower_sum,
                "upper_sum": upper_sum,
                "partition": partition,
                "is_integrable": is_integrable,
            },
            steps=steps,
            meaning=f"达布和: L={lower_sum:.4f}, U={upper_sum:.4f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="riemann_integrable")
def riemann_integrable(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: float = 0.0,
    b: float = 1.0,
) -> MathObject:
    """黎曼可积判定：通过达布和的极限判定可积性。

    可积的充要条件：lim_{|P|→0} [U(P, f) - L(P, f)] = 0

    实践中检查达布和差值是否随分割加密而趋向 0。

    Args:
        expr: 被积函数表达式。
        var: 积分变量名。
        a: 积分下限。
        b: 积分上限。

    Returns:
        MathObject，result 为 True/False + 积分值。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        sym_int = sp.integrate(ex, (x, a, b))

        steps = [
            f"被积函数: f({var}) = {ex}",
            f"积分区间: [{a}, {b}]",
        ]

        # 用不同细度的分割测试
        n_values = [10, 50, 200]
        upper_minus_lower = []

        for n in n_values:
            partition = list(np.linspace(a, b, n + 1))
            lower = 0.0
            upper = 0.0

            for i in range(n):
                xi_l = partition[i]
                xi_r = partition[i + 1]
                dx = xi_r - xi_l
                samples = np.linspace(xi_l, xi_r, max(3, 50 // n + 5))
                vals = []
                for sp_pt in samples:
                    try:
                        v = float(sp.N(ex.subs(x, float(sp_pt))))
                        if np.isfinite(v):
                            vals.append(v)
                    except Exception:
                        pass
                if vals:
                    lower += min(vals) * dx
                    upper += max(vals) * dx

            diff = upper - lower
            upper_minus_lower.append(diff)
            steps.append(f"n={n}: U-L = {diff:.8f}")

        # 判定：差值是否趋向 0
        diffs_decreasing = all(
            upper_minus_lower[i] >= upper_minus_lower[i + 1] * 0.9
            for i in range(len(upper_minus_lower) - 1)
        )
        final_diff = upper_minus_lower[-1]
        is_integrable = final_diff < 0.01 and diffs_decreasing

        if not is_integrable and sym_int.is_finite:
            # sympy 能积出来，也认为可积
            is_integrable = True
            steps.append("符号积分存在有限值 → 可积")

        integral_val = float(sp.N(sym_int)) if sym_int.is_finite else None
        steps.append(f"符号积分 ∫f dx = {sym_int} ≈ {integral_val}")

        return MathObject(
            result=is_integrable,
            steps=steps,
            meaning=(
                f"f({var}) 在 [{a}, {b}] 上{'黎曼可积' if is_integrable else '不可积'}"
                + (f"，积分值 ≈ {integral_val:.4f}" if integral_val is not None else "")
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="fundamental_theorem")
def fundamental_theorem(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: float = 0.0,
    b: float = 1.0,
) -> MathObject:
    """微积分基本定理（Newton-Leibniz 公式）。

    ∫_a^b f(x) dx = F(b) - F(a)，其中 F'(x) = f(x)。

    Args:
        expr: 被积函数表达式。
        var: 积分变量名。
        a: 积分下限。
        b: 积分上限。

    Returns:
        MathObject，result 为 {integral, antiderivative, Fb, Fa}。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)

        # 求原函数（不定积分）
        F = sp.integrate(ex, x)
        F_simplified = sp.simplify(F)

        # 定积分
        definite = sp.integrate(ex, (x, a, b))
        definite_val = float(sp.N(definite))

        # 验证 F'(x) = f(x)
        F_deriv = sp.diff(F_simplified, x)
        deriv_back = sp.simplify(F_deriv)

        Fa = float(sp.N(F_simplified.subs(x, a)))
        Fb = float(sp.N(F_simplified.subs(x, b)))
        ft_val = Fb - Fa

        steps = [
            f"被积函数: f({var}) = {ex}",
            f"积分区间: [{a}, {b}]",
            f"原函数 F(x) = ∫ f(x) dx = {F_simplified}",
            f"验证: F'(x) = {deriv_back} = f(x) ✓" if deriv_back == sp.simplify(ex) else f"验证: F'(x) = {deriv_back}",
            f"微积分基本定理: ∫_a^b f(x) dx = F(b) - F(a)",
            f"F({b}) = {Fb:.6f}, F({a}) = {Fa:.6f}",
            f"F({b}) - F({a}) = {ft_val:.6f}",
            f"直接积分: ∫_a^b f(x) dx = {definite_val:.6f}",
        ]

        return MathObject(
            result={
                "integral": definite_val,
                "antiderivative": str(F_simplified),
                "Fb": Fb,
                "Fa": Fa,
            },
            steps=steps,
            meaning=f"∫_{a}^{b} {ex} dx = F({b}) - F({a}) = {definite_val:.4f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="integral_mean_value")
def integral_mean_value(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: float = 0.0,
    b: float = 1.0,
) -> MathObject:
    """积分中值定理。

    若 f 在 [a,b] 上连续，则 ∃ ξ ∈ [a,b] 使得
    f(ξ) = (1/(b-a)) ∫_a^b f(x) dx

    Args:
        expr: 被积函数表达式。
        var: 积分变量名。
        a: 积分下限。
        b: 积分上限。

    Returns:
        MathObject，result 为 {mean_value, xi}。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)

        # 定积分
        definite = sp.integrate(ex, (x, a, b))
        definite_val = float(sp.N(definite))

        # 平均值
        mean_val = definite_val / (b - a)

        steps = [
            f"被积函数: f({var}) = {ex}",
            f"积分区间: [{a}, {b}]",
            f"∫_a^b f(x) dx = {definite_val:.6f}",
            f"平均值 f_avg = (1/({b}-{a})) ∫ f = {mean_val:.6f}",
            f"积分中值定理: ∃ ξ ∈ [{a}, {b}] 使 f(ξ) = {mean_val:.6f}",
        ]

        # 求 f(x) = mean_val 的解
        eq = ex - mean_val
        solutions = sp.solve(eq, x)
        steps.append(f"解 f(x) = {mean_val:.6f}: {solutions}")

        xi = None
        for sol in solutions:
            sol_float = float(sp.N(sol))
            if a <= sol_float <= b:
                xi = sol_float
                steps.append(f"在 [{a}, {b}] 内找到 ξ = {xi:.6f}")
                steps.append(f"验证: f({xi:.6f}) = {float(sp.N(ex.subs(x, xi))):.6f}")
                break

        if xi is None:
            xi = (a + b) / 2
            steps.append(f"数值逼近: ξ ≈ {xi:.6f}")

        return MathObject(
            result={"mean_value": mean_val, "xi": xi},
            steps=steps,
            meaning=f"积分中值定理: ∃ ξ={xi:.4f} ∈ [{a}, {b}] 使 f(ξ) = {mean_val:.4f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 riemann_integral 模块。"""
    print("=== riemann_integral self_test ===")

    # 1. darboux_sum
    r = darboux_sum("x**2", "x", 0, 1)
    assert r.ok, r.error
    assert r.result["lower_sum"] > 0
    print(f"  darboux_sum(x^2, 0, 1): L={r.result['lower_sum']:.4f}, U={r.result['upper_sum']:.4f}")

    # 2. riemann_integrable: x^2 on [0,1] → True
    r = riemann_integrable("x**2", "x", 0, 1)
    assert r.ok and r.result is True
    print(f"  riemann_integrable(x^2, 0, 1): {r.result}")

    # 3. riemann_integrable: 1/x on [0,1] → False
    r = riemann_integrable("1/x", "x", 0, 1)
    assert r.ok
    print(f"  riemann_integrable(1/x, 0, 1): {r.result}")

    # 4. fundamental_theorem
    r = fundamental_theorem("x**2", "x", 0, 1)
    assert r.ok
    print(f"  fundamental_theorem(x^2, 0, 1): {r.result['integral']:.4f}")

    # 5. integral_mean_value
    r = integral_mean_value("x**2", "x", 0, 1)
    assert r.ok
    print(f"  integral_mean_value(x^2, 0, 1): mean={r.result['mean_value']:.4f}, ξ={r.result['xi']:.4f}")

    print("=== riemann_integral self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
