"""积分 — 不定积分、定积分、数值积分、反常积分。

依赖: sympy, scipy（数值积分回退）
"""

from __future__ import annotations

from typing import Optional, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_sympy(expr: Union[str, sp.Expr]) -> sp.Expr:
    """将字符串或 sympy 表达式统一转为 sympy 表达式。"""
    if isinstance(expr, sp.Expr):
        return expr
    return sp.sympify(str(expr))


@register(module="calculus", action="integrate")
def integrate(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: Optional[Union[str, float, int]] = None,
    b: Optional[Union[str, float, int]] = None,
) -> MathObject:
    """不定积分（a,b 为 None）或定积分。

    Args:
        expr: 被积函数表达式。
        var: 积分变量名。
        a: 积分下限，None 表示不定积分。
        b: 积分上限，None 表示不定积分。

    Returns:
        MathObject，result 为积分结果表达式或数值。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)

        if a is not None and b is not None:
            # 定积分
            result = sp.integrate(ex, (x, a, b))
            # 尝试数值求解
            try:
                numeric_val = float(sp.N(result))
                result_str = str(sp.nsimplify(numeric_val, [sp.sqrt(2), sp.sqrt(3), sp.pi]))
                if result_str != str(numeric_val):
                    result_str = f"{result_str} ≈ {numeric_val}"
                else:
                    result_str = str(numeric_val)
            except Exception:
                result_str = str(result)

            return MathObject(
                result=result_str,
                steps=[
                    f"被积函数: f({var}) = {ex}",
                    f"定积分: ∫_{{{a}}}^{{{b}}} {ex} d{var}",
                    f"原函数: F({var}) = {sp.integrate(ex, x)}",
                    f"结果: F({b}) - F({a}) = {result}",
                ],
                meaning=f"∫_{{{a}}}^{{{b}}} {ex} d{var} = {result}",
            )
        else:
            # 不定积分
            result = sp.integrate(ex, x)
            return MathObject(
                result=str(result) + " + C",
                steps=[
                    f"被积函数: f({var}) = {ex}",
                    f"不定积分: ∫ {ex} d{var}",
                    f"结果: {result} + C",
                ],
                meaning=f"∫ {ex} d{var} = {result} + C",
            )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="integrate_numeric")
def integrate_numeric(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: float = 0,
    b: float = 1,
    method: str = "auto",
) -> MathObject:
    """数值积分（符号积分失败时回退，基于 sympy 数值积分或辛普森法则）。

    Args:
        expr: 被积函数表达式。
        var: 积分变量名。
        a: 积分下限。
        b: 积分上限。
        method: 方法 ("auto" / "simpson" / "quad")。

    Returns:
        MathObject，result 为数值结果。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        f = sp.lambdify(x, ex, "math")

        if method == "auto" or method == "quad":
            # 先尝试 sympy 高精度数值积分
            try:
                result = float(sp.N(sp.integrate(ex, (x, a, b))))
            except Exception:
                # 回退到数值积分
                try:
                    from scipy import integrate as scipy_integrate
                    result, _ = scipy_integrate.quad(f, a, b)
                except ImportError:
                    # 无 scipy，使用手写 Simpson 法则
                    n = 1000  # 子区间数
                    h = (b - a) / n
                    result = f(a) + f(b)
                    for i in range(1, n):
                        xi = a + i * h
                        result += 4 * f(xi) if i % 2 == 1 else 2 * f(xi)
                    result *= h / 3
        elif method == "simpson":
            n = 1000
            if n % 2 != 0:
                n += 1
            h = (b - a) / n
            result = f(a) + f(b)
            for i in range(1, n):
                xi = a + i * h
                result += 4 * f(xi) if i % 2 == 1 else 2 * f(xi)
            result *= h / 3
        else:
            return MathObject(error=f"不支持的方法 '{method}'，支持 auto/simpson/quad")

        return MathObject(
            result=result,
            steps=[
                f"被积函数: f({var}) = {ex}",
                f"数值积分: ∫_{{{a}}}^{{{b}}} {ex} d{var}",
                f"方法: {method}",
                f"结果: {result}",
            ],
            meaning=f"∫_{{{a}}}^{{{b}}} {ex} d{var} ≈ {result}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="improper_integral")
def improper_integral(
    expr: Union[str, sp.Expr],
    var: str = "x",
    a: Union[str, float, int] = 0,
    b: Union[str, float, int] = "oo",
) -> MathObject:
    """反常积分（无穷积分或瑕积分）。

    Args:
        expr: 被积函数表达式。
        var: 积分变量名。
        a: 积分下限。支持 "oo"、"inf"、"-oo" 等。
        b: 积分上限。支持 "oo"、"inf"、"-oo" 等。

    Returns:
        MathObject，result 为积分结果或发散发散描述。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)

        # 处理无穷符号
        a_val = sp.oo if str(a) in ("oo", "inf") else (-sp.oo if str(a) == "-oo" else sp.sympify(a))
        b_val = sp.oo if str(b) in ("oo", "inf") else (-sp.oo if str(b) == "-oo" else sp.sympify(b))

        result = sp.integrate(ex, (x, a_val, b_val))

        # 判断收敛性
        if result in (sp.oo, -sp.oo, sp.zoo, sp.nan):
            convergence = "发散"
            result_str = str(result)
        else:
            convergence = "收敛"
            try:
                numeric_val = float(sp.N(result))
                result_str = f"{result} ≈ {numeric_val}"
            except Exception:
                result_str = str(result)

        return MathObject(
            result=result_str,
            steps=[
                f"被积函数: f({var}) = {ex}",
                f"反常积分: ∫_{{{a}}}^{{{b}}} {ex} d{var}",
                f"结果: {result} ({convergence})",
            ],
            meaning=f"反常积分 {convergence}: ∫_{{{a}}}^{{{b}}} {ex} d{var} = {result}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 integrals 模块。"""
    print("=== integrals self_test ===")

    # 1. integrate (indefinite): sin(x) → -cos(x)
    r = integrate("sin(x)", "x")
    assert r.ok, r.error
    assert "cos" in r.result.lower()
    print(f"  integrate(sin(x)): {r.result}")
    print("  integrate (indefinite): pass")

    # 2. integrate (definite): x^2 from 0 to 1 → 1/3
    r = integrate("x**2", "x", 0, 1)
    assert r.ok
    assert "0.333" in r.result or "1/3" in r.result
    print(f"  integrate(x^2, 0, 1): {r.result}")
    print("  integrate (definite): pass")

    # 3. integrate (definite): sin(x) from 0 to pi → 2
    r = integrate("sin(x)", "x", 0, "pi")
    assert r.ok
    print(f"  integrate(sin(x), 0, pi): {r.result}")

    # 4. integrate_numeric
    r = integrate_numeric("x**2", "x", 0, 1)
    assert r.ok
    print(f"  integrate_numeric(x^2, 0, 1): {r.result}")

    # 5. improper_integral: 1/x^2 from 1 to oo → 1
    r = improper_integral("1/x**2", "x", 1, "oo")
    assert r.ok
    print(f"  improper_integral(1/x^2, 1, oo): {r.result}")

    print("=== integrals self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
