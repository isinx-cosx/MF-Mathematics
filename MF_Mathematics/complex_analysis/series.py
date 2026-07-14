"""复级数 — 泰勒级数、洛朗级数、奇点分类。

依赖: sympy
"""

from __future__ import annotations

from typing import Any, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


# ── 工具 ───────────────────────────────────────────────────────────────

def _parse_expr_var(func: Any, var: Any = None):
    """解析函数表达式和变量。"""
    if isinstance(func, str):
        expr = sp.sympify(func)
    else:
        expr = func
    if var is None:
        syms = list(expr.free_symbols)
        var = syms[0] if syms else sp.Symbol('z')
    elif isinstance(var, str):
        var = sp.Symbol(var)
    return expr, var


# ── 公开函数 ──────────────────────────────────────────────────────────


@register(module="complex_analysis", action="taylor_series")
def taylor_series(
    func: Any,
    z0: Any,
    n: int = 6,
    var: Any = None,
) -> MathObject:
    """泰勒展开（符号）。

    f(z) = Σ_{k=0}^{∞} f^{(k)}(z₀)/k! · (z - z₀)^k

    Args:
        func: 函数表达式。
        z0: 展开中心（数值或 sympy 表达式）。
        n: 展开阶数（即截断到 z^n 项）。
        var: 复变量符号。

    Returns:
        MathObject，result 为泰勒多项式。
    """
    try:
        expr, var_sym = _parse_expr_var(func, var)
        z0_sym = sp.sympify(z0)

        series_result = sp.series(expr, var_sym, z0_sym, n + 1)
        series_removed = series_result.removeO() if hasattr(series_result, 'removeO') else series_result

        # 提取前几项系数
        terms = []
        for k in range(n + 1):
            coeff = sp.diff(expr, var_sym, k).subs(var_sym, z0_sym) / sp.factorial(k)
            terms.append(sp.simplify(coeff))

        steps = [
            f"f(z) = {expr}",
            f"展开中心: z₀ = {z0_sym}",
            f"阶数: n = {n}",
        ]
        for k in range(min(n + 1, 6)):
            c = terms[k]
            steps.append(f"f^({k})({z0_sym})/{k}! = {c}")

        steps.append(f"泰勒多项式: {series_removed}")

        return MathObject(
            result=str(series_removed),
            steps=steps,
            meaning="泰勒级数在全纯圆盘 |z-z₀|<R 内收敛到 f(z)。",
            data={"coefficients": [str(c) for c in terms], "z0": str(z0_sym), "order": n},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="laurent_series")
def laurent_series(
    func: Any,
    z0: Any,
    n: int = 5,
    var: Any = None,
) -> MathObject:
    """洛朗展开（符号）。

    f(z) = Σ_{k=-∞}^{∞} a_k (z - z₀)^k，在环形区域 r < |z-z₀| < R 内收敛。

    使用 sympy 的 series 方法在极点处展开。

    Args:
        func: 函数表达式。
        z0: 展开中心（奇点）。
        n: 展开阶数。
        var: 复变量符号。

    Returns:
        MathObject，result 为洛朗级数（主部 + 解析部）。
    """
    try:
        expr, var_sym = _parse_expr_var(func, var)
        z0_sym = sp.sympify(z0)

        # 使用 sympy 展开
        try:
            series_result = sp.series(expr, var_sym, z0_sym, n + 1)
            series_removed = series_result.removeO() if hasattr(series_result, 'removeO') else series_result
        except Exception:
            # 尝试用 1/w 替换
            w = sp.Symbol('w')
            expr_shifted = expr.subs(var_sym, z0_sym + 1 / w)
            series_w = sp.series(expr_shifted, w, 0, n + 2)
            series_removed = series_w.removeO() if hasattr(series_w, 'removeO') else series_w
            series_removed = series_removed.subs(w, 1 / (var_sym - z0_sym))

        # 计算洛朗系数
        coeffs = []
        for k in range(-n, n + 1):
            try:
                c = sp.limit((expr * (var_sym - z0_sym) ** (-k - 1)), var_sym, z0_sym)
                coeffs.append((k, sp.simplify(c)))
            except Exception:
                pass

        # 分类主部
        principal_part = []
        analytic_part = []
        for k, c in coeffs:
            if k < 0:
                principal_part.append((k, c))
            else:
                analytic_part.append((k, c))

        steps = [
            f"f(z) = {expr}",
            f"展开中心: z₀ = {z0_sym}",
            f"阶数范围: -{n} 到 {n}",
        ]
        for k, c in principal_part:
            steps.append(f"a_{{{k}}} = {c}  (主部)")
        for k, c in analytic_part:
            steps.append(f"a_{{{k}}} = {c}  (解析部)")

        steps.append(f"洛朗级数: {series_removed}")

        return MathObject(
            result=str(series_removed),
            steps=steps,
            meaning="洛朗级数包含负幂项（主部）和非负幂项（解析部），在环形区域内收敛。",
            data={
                "principal_part": [(k, str(c)) for k, c in principal_part],
                "analytic_part": [(k, str(c)) for k, c in analytic_part],
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="singularity_classify")
def singularity_classify(
    func: Any,
    z0: Any,
    var: Any = None,
) -> MathObject:
    """奇点分类（可去奇点 / 极点 / 本性奇点）。

    方法：
    - 若 lim_{z→z₀} f(z) 存在且有限 → 可去奇点
    - 若 lim_{z→z₀} (z-z₀)^m f(z) 存在且非零 → m 阶极点
    - 否则 → 本性奇点

    Args:
        func: 函数表达式。
        z0: 待检查点。
        var: 复变量符号。

    Returns:
        MathObject，result 为 "removable" / "pole" / "essential" 字符串。
    """
    try:
        expr, var_sym = _parse_expr_var(func, var)
        z0_sym = sp.sympify(z0)

        # 检查极限
        limit_val = sp.limit(expr, var_sym, z0_sym)

        if limit_val.is_finite:
            # 检查是否已在 z0 处有定义
            try:
                val_at = sp.simplify(expr.subs(var_sym, z0_sym))
                if val_at.is_finite:
                    classification = "regular"
                    pole_order_val = 0
                else:
                    classification = "removable"
                    pole_order_val = 0
            except Exception:
                classification = "removable"
                pole_order_val = 0

            steps = [
                f"f(z) = {expr}",
                f"lim_{{z→{z0_sym}}} f(z) = {limit_val} (有限)",
                f"分类: {classification}",
            ]
            return MathObject(
                result=classification,
                steps=steps,
                meaning="可去奇点：极限存在有限，可通过补充定义消除。",
                data={"pole_order": pole_order_val},
            )

        # 检查是否为极点
        m = 1
        found_pole = False
        while m <= 10:
            powered = sp.simplify(expr * (var_sym - z0_sym) ** m)
            lim_powered = sp.limit(powered, var_sym, z0_sym)
            if lim_powered.is_finite and lim_powered != 0:
                found_pole = True
                pole_order_val = m
                break
            m += 1

        if found_pole:
            classification = "pole"
            steps = [
                f"f(z) = {expr}",
                f"lim_{{z→{z0_sym}}} f(z) = {limit_val} (发散)",
                f"lim_{{z→{z0_sym}}} (z-{z0_sym})^{{{pole_order_val}}} f(z) = {lim_powered} (有限非零)",
                f"分类: {pole_order_val} 阶极点",
            ]
            return MathObject(
                result=classification,
                steps=steps,
                meaning=f"极点：lim (z-z₀)^{{m}} f(z) 有限非零，m={pole_order_val}。",
                data={"pole_order": pole_order_val},
            )

        # 否则为本性奇点
        classification = "essential"
        steps = [
            f"f(z) = {expr}",
            f"lim_{{z→{z0_sym}}} f(z) = {limit_val} (不存在或非有限)",
            "不存在正整数 m 使得 lim (z-z₀)^m f(z) 有限非零",
            f"分类: {classification}",
        ]
        return MathObject(
            result=classification,
            steps=steps,
            meaning="本性奇点：极限不存在且非极点，洛朗展开包含无穷多负幂项。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="pole_order")
def pole_order(
    func: Any,
    z0: Any,
    var: Any = None,
) -> MathObject:
    """计算极点阶数。

    Args:
        func: 函数表达式。
        z0: 极点位置。
        var: 复变量符号。

    Returns:
        MathObject，result 为极点阶数（整数），若不是极点则返回 0。
    """
    try:
        classify_result = singularity_classify(func, z0, var)
        if classify_result.error:
            return classify_result

        if classify_result.result == "pole":
            order = classify_result.data.get("pole_order", 0)
        else:
            order = 0

        steps = [
            f"f(z) = {func}",
            f"z₀ = {z0}",
            f"奇点类型: {classify_result.result}",
            f"极点阶数: {order}",
        ]

        return MathObject(
            result=order,
            steps=steps,
            meaning=f"若 f(z) = g(z)/(z-z₀)^m 且 g(z₀)≠0, g 全纯，则 m 阶极点。",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ── self_test ──────────────────────────────────────────────────────────

def self_test() -> None:
    """自测：复级数。"""
    print("=== series self_test ===")

    # 1. taylor_series: sin(z) 在 z=0
    r = taylor_series("sin(z)", 0, n=5)
    assert r.ok, r.error
    assert "z**3/6" in r.result or "z**3/6" in str(r.result) or "-z**3" in r.result
    print(f"  taylor_series(sin(z), 0, 5): {r.result}")

    # 2. taylor_series: e^z 在 z=0
    r = taylor_series("exp(z)", 0, n=4)
    assert r.ok, r.error
    print(f"  taylor_series(exp(z), 0, 4): {r.result}")

    # 3. laurent_series: 1/(z-1) 在 z=1
    r = laurent_series("1/(z-1)", 1, n=3)
    assert r.ok, r.error
    print(f"  laurent_series(1/(z-1), 1): {r.result}")

    # 4. singularity_classify: 1/(z-1) 在 z=1 → pole
    r = singularity_classify("1/(z-1)", 1)
    assert r.ok, r.error
    assert r.result == "pole"
    print(f"  singularity_classify(1/(z-1), 1): {r.result}")

    # 5. singularity_classify: sin(z)/z 在 z=0 → removable
    r = singularity_classify("sin(z)/z", 0)
    assert r.ok, r.error
    assert r.result in ("removable", "regular"), f"应为 removable，得到 {r.result}"
    print(f"  singularity_classify(sin(z)/z, 0): {r.result}")

    # 6. singularity_classify: e^(1/z) 在 z=0 → essential
    r = singularity_classify("exp(1/z)", 0)
    assert r.ok, r.error
    assert r.result == "essential", f"应为本性奇点，得到 {r.result}"
    print(f"  singularity_classify(exp(1/z), 0): {r.result}")

    # 7. pole_order: 1/(z-1)^3 在 z=1 → 3
    r = pole_order("1/(z-1)**3", 1)
    assert r.ok, r.error
    assert r.result == 3, f"应为 3 阶极点，得到 {r.result}"
    print(f"  pole_order(1/(z-1)³, 1): {r.result}")

    print("=== series self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
