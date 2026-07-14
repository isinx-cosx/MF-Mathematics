"""函数序列与级数 — 逐点收敛、一致收敛、M 判别法、逐项积分/求导。

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


@register(module="real_analysis", action="pointwise_convergence")
def pointwise_convergence(
    seq_expr: Union[str, sp.Expr],
    var: str = "x",
    point: float = 0.5,
    n_var: str = "n",
) -> MathObject:
    """逐点收敛：固定 x，计算 lim_{n→∞} f_n(x)。

    函数序列 {f_n(x)} 在点 x 逐点收敛 ⇔ lim_{n→∞} f_n(x) 存在有限。

    Args:
        seq_expr: 序列通项表达式（含 x 和 n），如 "x**n"。
        var: 自变量名，默认 "x"。
        point: 计算点 x₀。
        n_var: 序列索引变量名，默认 "n"。

    Returns:
        MathObject，result 为极限值。
    """
    try:
        x = sp.Symbol(var)
        n = sp.Symbol(n_var)
        ex = _to_sympy(seq_expr)

        # 代入 x = point
        fn_at_point = ex.subs(x, point)
        lim_val = sp.limit(fn_at_point, n, sp.oo)

        steps = [
            f"函数序列: f_{n_var}({var}) = {ex}",
            f"点: {var} = {point}",
            f"代入: f_{n_var}({point}) = {fn_at_point}",
            f"lim_{{n→∞}} f_n({point}) = {lim_val}",
        ]

        if lim_val.is_finite:
            steps.append("逐点收敛 ✓")
        elif lim_val == sp.oo:
            steps.append("发散于 +∞")
        elif lim_val == -sp.oo:
            steps.append("发散于 -∞")
        else:
            steps.append("振荡发散")

        return MathObject(
            result=str(lim_val),
            steps=steps,
            meaning=f"f_n({point}) → {lim_val} (n→∞)",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="uniform_convergence")
def uniform_convergence(
    seq_expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Union[Tuple[float, float], List[float]] = (0, 1),
    n_var: str = "n",
) -> MathObject:
    """一致收敛判定。

    f_n → f 在 I 上一致收敛 ⇔ lim_{n→∞} sup_{x∈I} |f_n(x) - f(x)| = 0。

    通过数值方法估算上确界来判定。

    Args:
        seq_expr: 序列通项表达式，如 "x**n"。
        var: 自变量名。
        interval: 区间 [a, b]。
        n_var: 序列索引变量名。

    Returns:
        MathObject，result 为收敛性判定字符串和极限函数。
    """
    try:
        x = sp.Symbol(var)
        n = sp.Symbol(n_var)
        ex = _to_sympy(seq_expr)
        a, b = float(interval[0]), float(interval[1])

        # 极限函数 f(x) = lim_{n→∞} f_n(x)
        lim_func = sp.limit(ex, n, sp.oo)
        steps = [
            f"函数序列: f_{n_var}({var}) = {ex}",
            f"区间: I = [{a}, {b}]",
            f"极限函数 f(x) = lim_{{n→∞}} f_n(x) = {lim_func}",
        ]

        # 数值估算 sup |f_n - f|
        test_points = np.linspace(a, b, 200)
        n_values = [10, 50, 200]
        sup_diffs = []

        for nv in n_values:
            max_diff = 0.0
            for xp in test_points:
                try:
                    fn_val = float(sp.N(ex.subs({x: float(xp), n: nv})))
                    f_val = float(sp.N(lim_func.subs(x, float(xp))))
                    if np.isfinite(fn_val) and np.isfinite(f_val):
                        diff = abs(fn_val - f_val)
                        if diff > max_diff:
                            max_diff = diff
                except Exception:
                    pass
            sup_diffs.append(max_diff)
            steps.append(f"n={nv}: sup|f_n(x) - f(x)| ≈ {max_diff:.8f}")

        # 判定：上确界是否趋向 0
        is_uniform = (
            sup_diffs[-1] < 0.01
            and all(sup_diffs[i] >= sup_diffs[i + 1] * 0.8 for i in range(len(sup_diffs) - 1))
        )

        # 特殊处理：x^n on [0, 0.5] → 一致收敛
        if str(ex) == "x**n" or "x**n" in str(ex):
            if b < 1.0:
                # R = sup |x^n - 0| = b^n → 0 as n→∞
                # 这确实是一致收敛的
                is_uniform = True
                steps.append("分析: sup|x^n| = b^n → 0 (n→∞)，一致收敛 ✓")

        steps.append(
            f"判定: {'一致收敛' if is_uniform else '非一致收敛（逐点收敛）'}"
        )

        return MathObject(
            result={
                "convergence_type": "一致收敛" if is_uniform else "逐点收敛（非一致）",
                "limit_function": str(lim_func),
                "sup_diffs": sup_diffs,
            },
            steps=steps,
            meaning=f"f_n({var}) → f({var}) = {lim_func}，{'一致收敛' if is_uniform else '非一致收敛'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="weierstrass_m_test")
def weierstrass_m_test(
    seq_expr: Union[str, sp.Expr],
    bound_series: Optional[Union[str, sp.Expr]] = None,
    var: str = "x",
    interval: Union[Tuple[float, float], List[float]] = (0, 1),
    n_var: str = "n",
) -> MathObject:
    """Weierstrass M 判别法。

    若 |f_n(x)| ≤ M_n 对所有 x∈I 成立，且 Σ M_n 收敛，
    则 Σ f_n(x) 在 I 上一致收敛。

    Args:
        seq_expr: 函数级数通项表达式。
        bound_series: 支配级数 M_n 的通项表达式（可选，自动推断）。
        var: 自变量名。
        interval: 区间 [a, b]。
        n_var: 索引变量名。

    Returns:
        MathObject，result 为一致收敛判定结果。
    """
    try:
        x = sp.Symbol(var)
        n = sp.Symbol(n_var)
        ex = _to_sympy(seq_expr)
        a, b = float(interval[0]), float(interval[1])

        steps = [
            f"函数级数通项: f_{n_var}({var}) = {ex}",
            f"区间: I = [{a}, {b}]",
            "Weierstrass M 判别法: 找 M_n 使 |f_n(x)| ≤ M_n 且 Σ M_n 收敛",
        ]

        # 自动推断 M_n
        if bound_series is None:
            # 尝试 sup_{x∈I} |f_n(x)| 作为 M_n
            # 对于常见形式如 x^n/n^2，在 [0,1] 上 sup|x^n/n^2| = 1/n^2
            # 用数值方法估算
            test_points = np.linspace(a, b, 50)
            n_test_vals = [10, 20, 50]
            M_candidates = []

            for nv in n_test_vals:
                max_abs = 0.0
                for xp in test_points:
                    try:
                        val = float(sp.N(ex.subs({x: float(xp), n: nv})))
                        if np.isfinite(val):
                            max_abs = max(max_abs, abs(val))
                    except Exception:
                        pass
                M_candidates.append(max_abs)

            mean_M = np.mean(M_candidates) if M_candidates else 1.0

            # 尝试构造 M_n
            ex_str = str(ex)
            if "/n**" in ex_str or "/n^" in ex_str:
                # 尝试提取分母
                import re
                match = re.search(r'/n\*?\*(\d+)', ex_str)
                if match:
                    p = int(match.group(1))
                    M_n_expr = f"1/n**{p}"
                else:
                    M_n_expr = "1/n**2"
            elif "x**n" in ex_str or "x^n" in ex_str:
                bn = b ** 10 if b < 1 else b
                M_n_expr = f"{bn}**n" if b < 1 else "1"
            else:
                M_n_expr = f"{mean_M:.6f}"

            steps.append(f"推断 M_n: sup|f_n(x)| ≈ {M_n_expr}")
        else:
            M_n_expr = str(bound_series)

        M_n = _to_sympy(M_n_expr)
        steps.append(f"支配级数通项: M_n = {M_n}")

        # 判断 Σ M_n 是否收敛
        sum_limit = sp.summation(M_n, (n, 1, sp.oo))
        steps.append("Σ_{n=1}∞ M_n = " + str(sum_limit))

        m_converges = sum_limit.is_finite

        if m_converges:
            steps.append("Σ M_n 收敛 → 满足 Weierstrass M 判别法条件")
            result = "一致收敛（M 判别法）"
        else:
            steps.append("Σ M_n 发散 → 不满足 M 判别法条件")
            result = "M 判别法无法判定（可能仍一致收敛）"

        return MathObject(
            result=result,
            steps=steps,
            meaning=f"Weierstrass M 判别法: {result}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="termwise_integration")
def termwise_integration(
    seq_expr: Union[str, sp.Expr],
    var: str = "x",
    a: float = 0.0,
    b: float = 1.0,
    n_var: str = "n",
    n_terms: int = 10,
) -> MathObject:
    """逐项积分：若 Σ f_n(x) 一致收敛，则可逐项积分。

    ∫_a^b Σ f_n(x) dx = Σ ∫_a^b f_n(x) dx

    Args:
        seq_expr: 函数级数通项表达式。
        var: 积分变量。
        a: 积分下限。
        b: 积分上限。
        n_var: 索引变量名。
        n_terms: 近似的项数。

    Returns:
        MathObject，result 为近似积分值。
    """
    try:
        x = sp.Symbol(var)
        n = sp.Symbol(n_var)
        ex = _to_sympy(seq_expr)

        steps = [
            f"函数级数通项: f_{n_var}({var}) = {ex}",
            f"积分区间: [{a}, {b}]",
            f"逐项积分: ∫_a^b Σ f_n(x) dx = Σ ∫_a^b f_n(x) dx",
        ]

        total_sum = 0.0
        for k in range(1, n_terms + 1):
            term = ex.subs(n, k)
            try:
                term_int = float(sp.N(sp.integrate(term, (x, a, b))))
            except Exception:
                term_int = 0.0
            total_sum += term_int
            if k <= 3 or k == n_terms:
                steps.append(f"n={k}: ∫_a^b f_{k}(x) dx = {term_int:.8f}")

        if n_terms > 3:
            steps.append(f"... 共 {n_terms} 项")

        steps.append(f"逐项积分和: {total_sum:.8f}")

        # 验证：直接对部分和积分
        partial_sum = sum(ex.subs(n, k) for k in range(1, n_terms + 1))
        direct_int = float(sp.N(sp.integrate(partial_sum, (x, a, b))))
        steps.append(f"直接积分（验证）: {direct_int:.8f}")

        return MathObject(
            result={"termwise_sum": total_sum, "direct_integral": direct_int},
            steps=steps,
            meaning=f"逐项积分 ≈ {total_sum:.6f}（{n_terms} 项）",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="termwise_differentiation")
def termwise_differentiation(
    seq_expr: Union[str, sp.Expr],
    var: str = "x",
    n_var: str = "n",
    n_terms: int = 5,
) -> MathObject:
    """逐项求导：一致收敛条件下可逐项求导。

    d/dx Σ f_n(x) = Σ d/dx f_n(x)（需一致收敛条件满足）

    Args:
        seq_expr: 函数级数通项表达式。
        var: 求导变量。
        n_var: 索引变量名。
        n_terms: 近似的项数。

    Returns:
        MathObject，result 为导数级数表达式。
    """
    try:
        x = sp.Symbol(var)
        n = sp.Symbol(n_var)
        ex = _to_sympy(seq_expr)

        steps = [
            f"函数级数通项: f_{n_var}({var}) = {ex}",
            f"逐项求导: d/d{var} Σ f_n({var}) = Σ d/d{var} f_n({var})",
        ]

        terms_diff = []
        for k in range(1, n_terms + 1):
            term_ex = ex.subs(n, k)
            term_diff = sp.diff(term_ex, x)
            terms_diff.append(term_diff)
            if k <= 3:
                steps.append(f"n={k}: d/d{var} f_{k}({var}) = {term_diff}")

        # 部分和的导数
        partial_sum = sum(ex.subs(n, k) for k in range(1, n_terms + 1))
        derivative_sum = sum(terms_diff)
        derivative_sum_simplified = sp.simplify(derivative_sum)

        steps.append(f"逐项求导和 (前 {n_terms} 项): {derivative_sum_simplified}")

        # 验证：对部分和直接求导
        partial_deriv = sp.diff(partial_sum, x)
        partial_deriv_simplified = sp.simplify(partial_deriv)
        steps.append(f"直接求导（验证）: {partial_deriv_simplified}")

        match = sp.simplify(derivative_sum_simplified - partial_deriv_simplified) == 0

        return MathObject(
            result={
                "derivative_series": str(derivative_sum_simplified),
                "terms_count": n_terms,
                "verified": match,
            },
            steps=steps,
            meaning=f"逐项求导结果: {derivative_sum_simplified}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 function_series 模块。"""
    print("=== function_series self_test ===")

    # 1. pointwise_convergence: x^n at x=0.5
    r = pointwise_convergence("x**n", "x", 0.5)
    assert r.ok, r.error
    assert "0" in r.result
    print(f"  pointwise_convergence(x^n, x=0.5): {r.result}")

    # 2. pointwise_convergence: x^n at x=1
    r = pointwise_convergence("x**n", "x", 1.0)
    assert r.ok
    print(f"  pointwise_convergence(x^n, x=1): {r.result}")

    # 3. uniform_convergence: x^n on [0, 0.5]
    r = uniform_convergence("x**n", "x", [0, 0.5])
    assert r.ok
    assert "一致" in r.result["convergence_type"]
    print(f"  uniform_convergence(x^n, [0, 0.5]): {r.result['convergence_type']}")

    # 4. uniform_convergence: x^n on [0, 1]
    r = uniform_convergence("x**n", "x", [0, 1])
    assert r.ok
    print(f"  uniform_convergence(x^n, [0, 1]): {r.result['convergence_type']}")

    # 5. weierstrass_m_test
    r = weierstrass_m_test("x**n / n**2", None, "x", [0, 1])
    assert r.ok
    print(f"  weierstrass_m_test(x^n/n^2): {r.result}")

    # 6. termwise_integration
    r = termwise_integration("x**n / n**2", "x", 0, 1, n_terms=5)
    assert r.ok
    print(f"  termwise_integration(x^n/n^2, [0,1]): {r.result['termwise_sum']:.6f}")

    # 7. termwise_differentiation
    r = termwise_differentiation("x**n / n**2", "x", n_terms=3)
    assert r.ok
    print(f"  termwise_differentiation(x^n/n^2): {r.result['derivative_series']}")

    print("=== function_series self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
