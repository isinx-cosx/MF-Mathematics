"""代数式 — 整式化简/展开、因式分解、分式运算、根式运算。

依赖: sympy
"""

from __future__ import annotations

from typing import Any, List, Optional, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


# ===================================================================
# 辅助：将字符串表达式转为 sympy 表达式
# ===================================================================


def _to_sympy(expr: Union[str, sp.Expr]) -> sp.Expr:
    """将字符串或 sympy 表达式统一转为 sympy 表达式。"""
    if isinstance(expr, sp.Expr):
        return expr
    return sp.sympify(str(expr))


# ===================================================================
# 整式
# ===================================================================


@register(module="algebra", action="simplify_polynomial")
def simplify_polynomial(expr: Union[str, sp.Expr]) -> MathObject:
    """合并同类项，化简多项式。

    Args:
        expr: 多项式表达式，如 "x^2 + 2*x + 1"。

    Returns:
        MathObject，result 为化简后的表达式字符串。
    """
    try:
        ex = _to_sympy(expr)
        s_orig = str(ex)
        simplified = sp.simplify(ex)
        factored = sp.factor(ex)
        s_s = str(simplified)
        s_f = str(factored)

        # 智能选择最简形式：
        # 1. 如果 simplify 和 factor 结果相同 → 任选
        # 2. 如果 factor 有效（不同于原始）且复杂度不超过 simplify 的 3 倍 → 选 factor
        # 3. 否则选 simplify（适用于三角化简等 factor 无法处理的情况）
        ops_s = sp.count_ops(simplified)
        ops_f = sp.count_ops(factored)

        if s_f != s_orig and s_f != s_s and ops_f <= max(ops_s * 3, ops_s + 10):
            # factor 产生了有意义的不同结果
            best = factored
            alt = simplified
        elif ops_s <= ops_f:
            best = simplified
            alt = factored
        else:
            best = factored
            alt = simplified

        steps = [
            f"原始表达式: {ex}",
            f"合并同类项: {simplified}",
        ]
        if s_f != s_s:
            steps.append(f"可因式分解为: {factored}")
        else:
            steps.append("已是最简形式")

        return MathObject(
            result=str(best),
            steps=steps,
            meaning=f"化简结果: {best}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="expand_expression")
def expand_expression(expr: Union[str, sp.Expr]) -> MathObject:
    """去括号展开表达式。

    Args:
        expr: 含括号的表达式，如 "(x+1)*(x+2)"。

    Returns:
        MathObject，result 为展开后的表达式字符串。
    """
    try:
        ex = _to_sympy(expr)
        expanded = sp.expand(ex)
        return MathObject(
            result=str(expanded),
            steps=[
                f"原始表达式: {ex}",
                f"去括号展开: {expanded}",
            ],
            meaning=f"展开结果: {expanded}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 因式分解
# ===================================================================


@register(module="algebra", action="factor_common")
def factor_common(expr: Union[str, sp.Expr]) -> MathObject:
    """提公因式法分解。

    Args:
        expr: 多项式表达式。

    Returns:
        MathObject，result 为分解结果。
    """
    try:
        ex = _to_sympy(expr)
        # 找到各项的公因式
        if isinstance(ex, sp.Add):
            terms = ex.as_ordered_terms()
            gcd_expr = terms[0]
            for t in terms[1:]:
                gcd_expr = sp.gcd(gcd_expr, t)
            factored = gcd_expr * (ex / gcd_expr)
        else:
            factored = sp.factor(ex)
        return MathObject(
            result=str(factored),
            steps=[
                f"原始表达式: {ex}",
                f"提取公因式: {factored}",
            ],
            meaning=f"提公因式结果: {factored}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="factor_perfect_square")
def factor_perfect_square(expr: Union[str, sp.Expr]) -> MathObject:
    """完全平方公式分解：a² ± 2ab + b² = (a ± b)²。

    Args:
        expr: 二次三项式。

    Returns:
        MathObject，result 为分解结果。
    """
    try:
        ex = _to_sympy(expr)
        factored = sp.factor(ex)
        is_square = "**2" in str(factored) or "^2" in str(factored) or str(factored).count("(") == 1
        return MathObject(
            result=str(factored),
            steps=[
                f"原始表达式: {ex}",
                f"因式分解: {factored}",
                "使用完全平方公式 a² ± 2ab + b² = (a ± b)²" if is_square else "",
            ],
            meaning=f"分解结果: {factored}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="factor_difference_squares")
def factor_difference_squares(expr: Union[str, sp.Expr]) -> MathObject:
    """平方差公式分解：a² - b² = (a+b)(a-b)。

    Args:
        expr: 平方差形式的表达式。

    Returns:
        MathObject，result 为分解结果。
    """
    try:
        ex = _to_sympy(expr)
        factored = sp.factor(ex)
        return MathObject(
            result=str(factored),
            steps=[
                f"原始表达式: {ex}",
                f"因式分解: {factored}",
                "使用平方差公式 a² - b² = (a+b)(a-b)",
            ],
            meaning=f"分解结果: {factored}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="factor_cross")
def factor_cross(expr: Union[str, sp.Expr]) -> MathObject:
    """十字相乘法分解二次三项式。

    Args:
        expr: 形如 ax² + bx + c 的二次三项式。

    Returns:
        MathObject，result 为分解结果。
    """
    try:
        ex = _to_sympy(expr)
        factored = sp.factor(ex)
        # 尝试用十字相乘法解释
        return MathObject(
            result=str(factored),
            steps=[
                f"原始表达式: {ex}",
                f"十字相乘分解: {factored}",
            ],
            meaning=f"十字相乘结果: {factored}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="factor_group")
def factor_group(expr: Union[str, sp.Expr]) -> MathObject:
    """分组分解法。

    Args:
        expr: 四项及以上的多项式。

    Returns:
        MathObject，result 为分解结果。
    """
    try:
        ex = _to_sympy(expr)
        factored = sp.factor(ex)
        return MathObject(
            result=str(factored),
            steps=[
                f"原始表达式: {ex}",
                f"分组分解: {factored}",
            ],
            meaning=f"分组分解结果: {factored}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="factor")
def factor(expr: Union[str, sp.Expr]) -> MathObject:
    """综合因式分解，自动选择最佳方法。

    Args:
        expr: 多项式表达式，如 "x^2 - 1"。

    Returns:
        MathObject，result 为因式分解结果。
    """
    try:
        ex = _to_sympy(expr)
        factored = sp.factor(ex)
        return MathObject(
            result=str(factored),
            steps=[
                f"原始表达式: {ex}",
                f"综合因式分解: {factored}",
            ],
            meaning=f"因式分解结果: {factored}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 分式
# ===================================================================


@register(module="algebra", action="simplify_fraction")
def simplify_fraction(expr: Union[str, sp.Expr]) -> MathObject:
    """约分：化简分式。

    Args:
        expr: 分式表达式，如 "(x^2-1)/(x-1)"。

    Returns:
        MathObject，result 为约分后的表达式。
    """
    try:
        ex = _to_sympy(expr)
        simplified = sp.simplify(ex)
        return MathObject(
            result=str(simplified),
            steps=[
                f"原始分式: {ex}",
                f"约分结果: {simplified}",
            ],
            meaning=f"约分后: {simplified}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="common_denominator")
def common_denominator(
    expr1: Union[str, sp.Expr], expr2: Union[str, sp.Expr]
) -> MathObject:
    """通分：将两个分式化为同分母。

    Args:
        expr1: 第一个分式。
        expr2: 第二个分式。

    Returns:
        MathObject，result 为 (通分后表达式1, 通分后表达式2, 公分母)。
    """
    try:
        e1 = _to_sympy(expr1)
        e2 = _to_sympy(expr2)
        together1 = sp.together(e1)
        together2 = sp.together(e2)
        # 获取公分母
        den1 = sp.denom(e1)
        den2 = sp.denom(e2)
        lcm_den = sp.lcm(den1, den2)
        new1 = sp.simplify(e1 * lcm_den / den1)
        new2 = sp.simplify(e2 * lcm_den / den2)
        return MathObject(
            result=(str(new1), str(new2), str(lcm_den)),
            steps=[
                f"分式1: {e1}，分母: {den1}",
                f"分式2: {e2}，分母: {den2}",
                f"公分母: {lcm_den}",
                f"通分结果: {new1} 和 {new2}",
            ],
            meaning=f"公分母 {lcm_den}，通分后为 {new1} 与 {new2}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="fraction_operations")
def fraction_operations(
    expr1: Union[str, sp.Expr], op: str, expr2: Union[str, sp.Expr]
) -> MathObject:
    """分式四则运算。

    Args:
        expr1: 第一个分式。
        op: 运算符 '+', '-', '*', '/'。
        expr2: 第二个分式。

    Returns:
        MathObject，result 为运算结果（已化简）。
    """
    try:
        e1 = _to_sympy(expr1)
        e2 = _to_sympy(expr2)
        if op == "+":
            result_expr = sp.simplify(e1 + e2)
        elif op == "-":
            result_expr = sp.simplify(e1 - e2)
        elif op == "*":
            result_expr = sp.simplify(e1 * e2)
        elif op == "/":
            result_expr = sp.simplify(e1 / e2)
        else:
            return MathObject(error=f"不支持的运算符 '{op}'，支持 + - * /")
        return MathObject(
            result=str(result_expr),
            steps=[
                f"运算: ({e1}) {op} ({e2})",
                f"结果: {result_expr}",
            ],
            meaning=f"({e1}) {op} ({e2}) = {result_expr}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="rationalize_denominator")
def rationalize_denominator(expr: Union[str, sp.Expr]) -> MathObject:
    """分母有理化。

    Args:
        expr: 含根式分母的分式，如 "1/sqrt(2)"。

    Returns:
        MathObject，result 为有理化后的表达式。
    """
    try:
        ex = _to_sympy(expr)
        num = sp.numer(ex)
        den = sp.denom(ex)
        # 使用 sympy 的 rationalize 功能
        rationalized = sp.ratsimp(ex)
        # 尝试用 sp.simplify + sp.radsimp 处理根式
        rationalized = sp.radsimp(rationalized)
        # 最终化简
        rationalized = sp.simplify(rationalized)
        return MathObject(
            result=str(rationalized),
            steps=[
                f"原始表达式: {ex}",
                f"分子: {num}，分母: {den}",
                f"有理化结果: {rationalized}",
            ],
            meaning=f"分母有理化后: {rationalized}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 根式
# ===================================================================


@register(module="algebra", action="simplify_radical")
def simplify_radical(expr: Union[str, sp.Expr]) -> MathObject:
    """化简二次根式。

    Args:
        expr: 根式表达式，如 "sqrt(8)"。

    Returns:
        MathObject，result 为化简结果。
    """
    try:
        ex = _to_sympy(expr)
        simplified = sp.simplify(ex)
        # 尝试进一步化简 sqrt
        simplified = sp.sqrtdenest(simplified)
        return MathObject(
            result=str(simplified),
            steps=[
                f"原始根式: {ex}",
                f"化简结果: {simplified}",
            ],
            meaning=f"根式化简: {simplified}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="like_radicals")
def like_radicals(expr1: Union[str, sp.Expr], expr2: Union[str, sp.Expr]) -> MathObject:
    """判断两个根式是否为同类根式。

    Args:
        expr1: 第一个根式。
        expr2: 第二个根式。

    Returns:
        MathObject，result 为 (是否同类, 化简后根式1, 化简后根式2)。
    """
    try:
        e1 = sp.simplify(_to_sympy(expr1))
        e2 = sp.simplify(_to_sympy(expr2))
        # 提取根式部分进行比较
        def _radical_part(expr: sp.Expr) -> sp.Expr:
            """提取根式部分（去掉系数）。"""
            if expr.is_Mul:
                radical_parts = [arg for arg in expr.args if arg.has(sp.sqrt)]
                return sp.Mul(*radical_parts) if radical_parts else 1
            elif expr.has(sp.sqrt):
                return expr
            return 1

        r1 = _radical_part(e1)
        r2 = _radical_part(e2)
        is_like = sp.simplify(r1 - r2) == 0
        return MathObject(
            result=(is_like, str(e1), str(e2)),
            steps=[
                f"根式1: {expr1} → 化简为 {e1}，根式部分: {r1}",
                f"根式2: {expr2} → 化简为 {e2}，根式部分: {r2}",
                f"{'是' if is_like else '不是'}同类根式",
            ],
            meaning=f"{e1} 与 {e2} {'是' if is_like else '不是'}同类根式",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="radical_operations")
def radical_operations(
    expr1: Union[str, sp.Expr], op: str, expr2: Union[str, sp.Expr]
) -> MathObject:
    """根式运算。

    Args:
        expr1: 第一个根式。
        op: 运算符 '+', '-', '*', '/'。
        expr2: 第二个根式。

    Returns:
        MathObject，result 为运算结果（已化简）。
    """
    try:
        e1 = _to_sympy(expr1)
        e2 = _to_sympy(expr2)
        if op == "+":
            result_expr = sp.simplify(e1 + e2)
        elif op == "-":
            result_expr = sp.simplify(e1 - e2)
        elif op == "*":
            result_expr = sp.simplify(e1 * e2)
        elif op == "/":
            result_expr = sp.simplify(e1 / e2)
        else:
            return MathObject(error=f"不支持的运算符 '{op}'，支持 + - * /")
        result_expr = sp.sqrtdenest(result_expr)
        return MathObject(
            result=str(result_expr),
            steps=[
                f"运算: ({e1}) {op} ({e2})",
                f"结果: {result_expr}",
            ],
            meaning=f"({e1}) {op} ({e2}) = {result_expr}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 expression 模块。"""
    print("=== expression self_test ===")

    # 1. simplify_polynomial
    r = simplify_polynomial("x^2 + 2*x + 1")
    assert r.ok, r.error
    assert "(x + 1)**2" in str(r.result) or "x**2 + 2*x + 1" in str(r.result)
    print("  simplify_polynomial: pass")

    # 2. expand_expression
    r = expand_expression("(x+1)*(x+2)")
    assert r.ok and "x**2" in r.result
    print("  expand_expression: pass")

    # 3. factor
    r = factor("x^2 - 1")
    assert r.ok
    print(f"  factor(x^2-1): {r.result}")
    print("  factor: pass")

    # 4. factor_difference_squares
    r = factor_difference_squares("x^2 - 4")
    assert r.ok
    print("  factor_difference_squares: pass")

    # 5. factor_perfect_square
    r = factor_perfect_square("x^2 + 2*x + 1")
    assert r.ok
    print("  factor_perfect_square: pass")

    # 6. simplify_fraction
    r = simplify_fraction("(x^2-1)/(x-1)")
    assert r.ok
    print(f"  simplify_fraction: {r.result}")

    # 7. simplify_radical
    r = simplify_radical("sqrt(8)")
    assert r.ok and "2" in r.result
    print(f"  simplify_radical(sqrt(8)): {r.result}")

    # 8. like_radicals
    r = like_radicals("sqrt(2)", "2*sqrt(2)")
    assert r.ok and r.result[0] is True
    print("  like_radicals: pass")

    # 9. radical_operations
    r = radical_operations("sqrt(2)", "*", "sqrt(8)")
    assert r.ok
    print(f"  radical_operations(sqrt(2)*sqrt(8)): {r.result}")

    # 10. rationalize_denominator
    r = rationalize_denominator("1/sqrt(2)")
    assert r.ok
    print(f"  rationalize_denominator: {r.result}")

    print("=== expression self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
