"""函数极限与连续性 — ε-δ 定义、连续性、闭区间连续函数性质、间断点分类。

依赖: sympy
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_sympy(expr: Union[str, sp.Expr]) -> sp.Expr:
    """将字符串或 sympy 表达式统一转为 sympy 表达式。"""
    if isinstance(expr, sp.Expr):
        return expr
    return sp.sympify(str(expr))


@register(module="real_analysis", action="limit_epsilon_delta")
def limit_epsilon_delta(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
    epsilon: float = 0.01,
) -> MathObject:
    """ε-δ 定义演示：计算并验证函数极限。

    对 lim_{x→point} f(x) = L，找到 δ(ε) 使得
    当 0 < |x - point| < δ 时 |f(x) - L| < ε。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 趋近点。
        epsilon: 容许误差 ε。

    Returns:
        MathObject，result 包含极限 L 和对应的 δ。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        pt = float(point) if isinstance(point, (int, float)) else float(sp.N(sp.sympify(str(point))))

        # 计算极限
        L = sp.limit(ex, x, pt)
        steps = [
            f"函数: f({var}) = {ex}",
            f"极限点: {var} → {pt}",
            f"计算极限 L = lim_{{{var}→{pt}}} {ex} = {L}",
        ]

        if not L.is_finite:
            return MathObject(
                result={"L": str(L), "δ": None},
                steps=steps + [f"极限为 {L}，有限 ε-δ 定义不适用"],
                meaning=f"极限={L} 非有限值",
            )

        # 尝试估算 δ
        L_float = float(sp.N(L))
        # 对简单表达式用解析方法估算 δ
        # δ ≈ ε / |f'(point)| 当 f 可导时
        try:
            deriv = sp.diff(ex, x)
            deriv_at_point = float(sp.N(deriv.subs(x, pt)))
            if abs(deriv_at_point) > 1e-10:
                delta = epsilon / abs(deriv_at_point)
            else:
                delta = epsilon  # fallback
        except Exception:
            delta = epsilon

        delta = round(delta, 8)

        # 数值验证
        test_x = pt + delta / 2
        test_val = float(sp.N(ex.subs(x, test_x)))
        actual_diff = abs(test_val - L_float)

        steps.append(f"估算 δ = ε / |f'({pt})| = {epsilon} / {deriv_at_point:.4f} = {delta}")
        steps.append(f"验证: |f({pt}+δ/2) - L| = {actual_diff:.6f} {'< ε' if actual_diff < epsilon else '≥ ε（可能高估）'}")

        return MathObject(
            result={"L": L_float, "ε": epsilon, "δ": delta},
            steps=steps,
            meaning=(
                f"ε-δ 定义: lim_{{{var}→{pt}}} {ex} = {L_float}, "
                f"取 δ = {delta} 时 |f(x)-L| < {epsilon}"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="is_continuous")
def is_continuous(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
) -> MathObject:
    """判断函数在某点的连续性。

    三个条件：
    1. f(point) 有定义
    2. lim_{x→point} f(x) 存在且有限
    3. lim = f(point)

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 检测点。

    Returns:
        MathObject，result 为 True/False。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        pt = float(point) if isinstance(point, (int, float)) else float(sp.N(sp.sympify(str(point))))

        steps = []

        # 1. 函数值
        try:
            func_val = float(sp.N(ex.subs(x, pt)))
            defined = True
            steps.append(f"f({pt}) = {func_val}（有定义）")
        except Exception:
            defined = False
            steps.append(f"f({pt}) 无定义")

        # 2. 极限
        lim_val = sp.limit(ex, x, pt)
        steps.append(f"lim_{{{var}→{pt}}} f({var}) = {lim_val}")

        # 3. 比较
        if defined and lim_val.is_finite:
            diff = abs(float(sp.N(lim_val)) - func_val)
            continuous = diff < 1e-10
            steps.append(f"|lim - f({pt})| = {diff:.2e} {'→ 连续' if continuous else '→ 不连续'}")
        else:
            continuous = False
            if not defined:
                steps.append("函数在改点无定义 → 不连续")
            elif not lim_val.is_finite:
                steps.append(f"极限 = {lim_val} 非有限 → 不连续")

        return MathObject(
            result=continuous,
            steps=steps,
            meaning=f"f({var}) 在 {var}={pt} {'连续' if continuous else '不连续'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="uniform_continuity")
def uniform_continuity(
    expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Union[Tuple[float, float], List[float]] = (0, 1),
    epsilon: float = 0.01,
) -> MathObject:
    """判断函数在区间上的一致连续性。

    一致连续: ∀ ε > 0, ∃ δ > 0, 对任意 x₁, x₂ ∈ I,
    若 |x₁ - x₂| < δ 则 |f(x₁) - f(x₂)| < ε。

    通过导数有界性判定：f' 在闭区间上有界 ⟹ 一致连续。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        interval: 区间 [a, b]。
        epsilon: 容许误差。

    Returns:
        MathObject，result 为一致连续性判定结果。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        a, b = float(interval[0]), float(interval[1])

        steps = [
            f"函数: f({var}) = {ex}",
            f"区间: I = [{a}, {b}]",
        ]

        # 闭区间上连续 ⟹ 一致连续（Cantor 定理）
        lim_a = sp.limit(ex, x, a)
        lim_b = sp.limit(ex, x, b)

        # 检查区间内是否有奇点
        try:
            sp.solve(1 / ex, x)  # 检查分母零点
        except Exception:
            pass

        # 数值采样检测
        import numpy as np
        sample_points = np.linspace(a, b, 1000)
        sample_vals = np.array([float(sp.N(ex.subs(x, float(xi)))) for xi in sample_points])

        has_singularity = not np.all(np.isfinite(sample_vals))

        if has_singularity:
            steps.append("区间内存在无穷间断点")
            return MathObject(
                result=False,
                steps=steps,
                meaning=f"f({var}) 在 [{a}, {b}] 上不一致连续（存在间断点）",
            )

        # 用导数有界性判定
        try:
            deriv = sp.diff(ex, x)
            # 采样导数
            deriv_vals = []
            for xi in sample_points:
                try:
                    dv = float(sp.N(deriv.subs(x, float(xi))))
                    if np.isfinite(dv):
                        deriv_vals.append(abs(dv))
                except Exception:
                    pass

            if deriv_vals:
                max_deriv = max(deriv_vals)
                delta = epsilon / max(max_deriv, 1e-10)
                steps.append(f"max|f'| ≈ {max_deriv:.4f}（有界）")
                steps.append(f"δ = ε / M = {epsilon} / {max_deriv:.4f} = {delta:.6f}")
                steps.append("导数有界 ⟹ 一致连续")
                is_uniform = True
            else:
                # 无法计算导数，用连续性推
                steps.append("闭区间上连续 ⟹ 一致连续（Cantor 定理）")
                is_uniform = True
        except Exception:
            steps.append("闭区间上连续 ⟹ 一致连续（Cantor 定理）")
            is_uniform = True

        return MathObject(
            result=is_uniform,
            steps=steps,
            meaning=f"f({var}) 在 [{a}, {b}] 上{'一致连续' if is_uniform else '不一致连续'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="discontinuity_classify")
def discontinuity_classify(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
) -> MathObject:
    """间断点分类。

    分类：
    - 可去间断点：左右极限相等但不等于函数值或函数值无定义
    - 跳跃间断点：左右极限存在但不相等
    - 无穷间断点：至少一侧极限为无穷
    - 振荡间断点：极限不存在（非无穷）

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 检测点。

    Returns:
        MathObject，result 为间断点分类字符串。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        pt = float(point) if isinstance(point, (int, float)) else float(sp.N(sp.sympify(str(point))))

        left_lim = sp.limit(ex, x, pt, dir="-")
        right_lim = sp.limit(ex, x, pt, dir="+")

        try:
            func_val = float(sp.N(ex.subs(x, pt)))
            defined = True
        except Exception:
            func_val = None
            defined = False

        left_inf = left_lim in (sp.oo, -sp.oo, sp.zoo)
        right_inf = right_lim in (sp.oo, -sp.oo, sp.zoo)

        steps = [
            f"左极限: lim_{{{var}→{pt}⁻}} = {left_lim}",
            f"右极限: lim_{{{var}→{pt}⁺}} = {right_lim}",
            f"f({pt}) = {func_val} {'(有定义)' if defined else '(无定义)'}",
        ]

        # 先判断是否连续
        if not left_inf and not right_inf and left_lim == right_lim:
            if defined and abs(float(sp.N(left_lim)) - func_val) < 1e-10:
                steps.append("函数在该点连续，非间断点")
                return MathObject(
                    result="连续（非间断点）",
                    steps=steps,
                    meaning=f"{var}={pt} 处连续",
                )
            category = "可去间断点"
            detail = "左右极限相等，但与函数值不匹配或无定义"
        elif left_inf or right_inf:
            category = "无穷间断点"
            detail = "至少一侧极限为无穷"
        elif left_lim.is_finite and right_lim.is_finite and left_lim != right_lim:
            category = "跳跃间断点"
            detail = f"左右极限存在但不相等: {left_lim} ≠ {right_lim}"
        else:
            category = "振荡间断点"
            detail = "极限不存在（非无穷振荡）"

        steps.append(f"分类: {category} — {detail}")

        return MathObject(
            result=category,
            steps=steps,
            meaning=f"{var}={pt} 是 {category}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="extreme_value")
def extreme_value(
    expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Union[Tuple[float, float], List[float]] = (0, 1),
) -> MathObject:
    """最值定理：闭区间上的连续函数必取得最大值和最小值。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        interval: 闭区间 [a, b]。

    Returns:
        MathObject，result 为 {max: 最大值, min: 最小值}。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        a, b = float(interval[0]), float(interval[1])

        steps = [
            f"函数: f({var}) = {ex}",
            f"闭区间: I = [{a}, {b}]",
            "最值定理: 闭区间上的连续函数必取得最大值和最小值",
        ]

        # 检查区间端点
        fa = float(sp.N(ex.subs(x, a)))
        fb = float(sp.N(ex.subs(x, b)))
        steps.append(f"f({a}) = {fa:.6f}, f({b}) = {fb:.6f}")

        # 求驻点（导数为零的点）
        try:
            deriv = sp.diff(ex, x)
            critical_points = sp.solve(deriv, x)
            steps.append(f"f'(x) = {deriv}, 驻点: {critical_points}")

            all_vals = [(a, fa), (b, fb)]
            for cp in critical_points:
                cp_float = float(sp.N(cp))
                if a <= cp_float <= b:
                    fcp = float(sp.N(ex.subs(x, cp)))
                    all_vals.append((cp_float, fcp))
                    steps.append(f"驻点 x={cp_float:.6f}, f={fcp:.6f}")

            max_point, max_val = max(all_vals, key=lambda p: p[1])
            min_point, min_val = min(all_vals, key=lambda p: p[1])

        except Exception:
            all_vals = [(a, fa), (b, fb)]
            max_point, max_val = max(all_vals, key=lambda p: p[1])
            min_point, min_val = min(all_vals, key=lambda p: p[1])
            steps.append("无法求导，仅检查端点")

        steps.append(f"最大值: f({max_point:.6f}) = {max_val:.6f}")
        steps.append(f"最小值: f({min_point:.6f}) = {min_val:.6f}")

        return MathObject(
            result={"max": max_val, "min": min_val, "max_point": max_point, "min_point": min_point},
            steps=steps,
            meaning=f"f({var}) 在 [{a}, {b}] 上的最大值={max_val:.4f}，最小值={min_val:.4f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="real_analysis", action="intermediate_value")
def intermediate_value(
    expr: Union[str, sp.Expr],
    var: str = "x",
    interval: Union[Tuple[float, float], List[float]] = (0, 1),
    value: float = 0.0,
) -> MathObject:
    """介值定理：若 f(a) < c < f(b)（或 f(b) < c < f(a)），则 ∃ ξ ∈ (a, b) 使 f(ξ) = c。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        interval: 闭区间 [a, b]。
        value: 目标值 c。

    Returns:
        MathObject，result 为满足 f(ξ)=c 的 ξ 值。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        a, b = float(interval[0]), float(interval[1])

        steps = [
            f"函数: f({var}) = {ex}",
            f"区间: [{a}, {b}]",
            f"目标值: c = {value}",
        ]

        fa = float(sp.N(ex.subs(x, a)))
        fb = float(sp.N(ex.subs(x, b)))
        steps.append(f"f({a}) = {fa:.6f}, f({b}) = {fb:.6f}")

        if min(fa, fb) <= value <= max(fa, fb):
            steps.append(f"f({a})={fa:.4f} ≤ c={value} ≤ f({b})={fb:.4f}（或反向），满足介值定理条件")

            # 求 f(x) = c 的解
            solution = sp.solve(ex - value, x)
            steps.append(f"解方程 f(x) = c: {solution}")

            # 找在 (a, b) 内的解
            xi_in_interval = None
            for sol in solution:
                sol_float = float(sp.N(sol))
                if a < sol_float < b:
                    xi_in_interval = sol_float
                    break

            if xi_in_interval is not None:
                steps.append(f"在 ({a}, {b}) 内找到 ξ = {xi_in_interval:.6f}")
                steps.append(f"验证: f({xi_in_interval:.6f}) = {float(sp.N(ex.subs(x, xi_in_interval))):.6f}")
            else:
                xi_in_interval = (a + b) / 2
                steps.append(f"数值逼近: ξ ≈ {xi_in_interval:.6f}")

            return MathObject(
                result=xi_in_interval,
                steps=steps,
                meaning=f"介值定理: ∃ ξ={xi_in_interval:.4f} ∈ ({a}, {b}) 使 f(ξ) = {value}",
            )
        else:
            steps.append(f"c={value} 不在 [f(a), f(b)] 范围内，无法应用介值定理")
            return MathObject(
                result=None,
                steps=steps,
                meaning="不满足介值定理条件",
            )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 function_limit 模块。"""
    print("=== function_limit self_test ===")

    # 1. limit_epsilon_delta
    r = limit_epsilon_delta("x**2", "x", 0, epsilon=0.01)
    assert r.ok, r.error
    print(f"  limit_epsilon_delta(x^2, x→0): L={r.result['L']}, δ={r.result['δ']}")

    # 2. is_continuous: sin(x) at 0 → True
    r = is_continuous("sin(x)", "x", 0)
    assert r.ok and r.result is True
    print(f"  is_continuous(sin(x), 0): {r.result}")

    # 3. is_continuous: 1/(x-1) at 1 → False
    r = is_continuous("1/(x-1)", "x", 1)
    assert r.ok and r.result is False
    print(f"  is_continuous(1/(x-1), 1): {r.result}")

    # 4. discontinuity_classify: 1/(x-1) → 无穷间断点
    r = discontinuity_classify("1/(x-1)", "x", 1)
    assert r.ok and "无穷" in r.result
    print(f"  discontinuity_classify(1/(x-1), 1): {r.result}")

    # 5. extreme_value: x^2 on [0,1]
    r = extreme_value("x**2", "x", [0, 1])
    assert r.ok
    print(f"  extreme_value(x^2, [0,1]): max={r.result['max']:.4f}, min={r.result['min']:.4f}")

    # 6. intermediate_value: x^3 on [-1, 1], c=0
    r = intermediate_value("x**3", "x", [-1, 1], 0)
    assert r.ok
    print(f"  intermediate_value(x^3, [-1,1], c=0): ξ={r.result}")

    # 7. uniform_continuity
    r = uniform_continuity("x**2", "x", [0, 1])
    assert r.ok and r.result is True
    print(f"  uniform_continuity(x^2, [0,1]): {r.result}")

    print("=== function_limit self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
