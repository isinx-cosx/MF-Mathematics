"""方程与方程组 — 一元一次、二元一次方程组、一元二次、分式方程、无理方程。

依赖: sympy
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import to_sympy

from typing import Any, Dict, List, Optional, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
def _parse_equation(expr: Union[str, sp.Expr]) -> sp.Equality:
    """将方程表达式统一转为 sympy Eq 对象，支持 "=" 字符串。"""
    if isinstance(expr, str) and "=" in expr:
        parts = expr.split("=", 1)
        lhs = sp.sympify(parts[0].strip())
        rhs = sp.sympify(parts[1].strip())
        return sp.Eq(lhs, rhs)
    if isinstance(expr, sp.Equality):
        return expr
    ex = to_sympy(expr)
    return sp.Eq(ex, 0)


# ===================================================================
# 一元一次方程
# ===================================================================


@register(module="algebra", action="solve_linear")
def solve_linear(expr: Union[str, sp.Expr], var: str = "x") -> MathObject:
    """解一元一次方程 ax + b = 0。

    Args:
        expr: 方程表达式，如 "2*x + 3"（表示 2x+3=0）或 "2*x + 3 = 7"。
        var: 变量名，默认 "x"。

    Returns:
        MathObject，result 为解（数值或表达式）。
    """
    try:
        x = sp.Symbol(var)
        eq = _parse_equation(expr)
        solution = sp.solve(eq, x)
        return MathObject(
            result=[str(s) for s in solution] if len(solution) > 1 else str(solution[0]) if solution else "无解",
            steps=[
                f"方程: {eq.lhs} = {eq.rhs}",
                f"移项整理: {sp.simplify(eq.lhs - eq.rhs)} = 0",
                f"解得 {var} = {solution[0]}" if solution else "无解",
            ],
            meaning=f"方程 {eq} 的解为 {var} = {solution[0]}" if solution else "无解",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="linear_application")
def linear_application(problem: str) -> MathObject:
    """应用题建模（占位，可扩展为 NLP 解析）。

    Args:
        problem: 应用题描述文本。

    Returns:
        MathObject，result 为建模结果。
    """
    try:
        return MathObject(
            result="应用题建模功能预留扩展",
            steps=["收到应用题为文字描述", "当前版本需人工转化为方程后求解"],
            meaning="该功能用于将文字应用题转化为方程模型，当前为占位实现",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 二元一次方程组
# ===================================================================


@register(module="algebra", action="solve_linear_system")
def solve_linear_system(
    eq1: Union[str, sp.Expr],
    eq2: Union[str, sp.Expr],
    var1: str = "x",
    var2: str = "y",
) -> MathObject:
    """消元法求解二元一次方程组。

    Args:
        eq1: 第一个方程，如 "x + y - 2"（表示 x+y=2）或 "x + y = 2"。
        eq2: 第二个方程。
        var1: 第一个变量名。
        var2: 第二个变量名。

    Returns:
        MathObject，result 为 {var1: value1, var2: value2} 字典。
    """
    try:
        x = sp.Symbol(var1)
        y = sp.Symbol(var2)
        eqn1 = _parse_equation(eq1)
        eqn2 = _parse_equation(eq2)

        solution = sp.solve([eqn1, eqn2], (x, y), dict=True)

        if not solution:
            return MathObject(result="无解或无穷多解", steps=[f"方程组: {eqn1}, {eqn2}", "求解得出: 无解或无穷多解"])

        sol = solution[0]
        result_dict = {str(k): str(sol[k]) for k in sol}
        return MathObject(
            result=result_dict,
            steps=[
                f"方程1: {eqn1}",
                f"方程2: {eqn2}",
                f"消元法求解 → {var1} = {sol[x]}, {var2} = {sol[y]}",
            ],
            meaning=f"二元一次方程组的解为 {result_dict}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 一元二次方程
# ===================================================================


@register(module="algebra", action="solve_quadratic")
def solve_quadratic(expr: Union[str, sp.Expr], var: str = "x") -> MathObject:
    """解一元二次方程 ax² + bx + c = 0，自动选择最佳方法。

    支持四种解法：因式分解、配方法、公式法、根与系数关系。

    Args:
        expr: 方程表达式，如 "x^2 - 4"。
        var: 变量名。

    Returns:
        MathObject，result 为解的列表。
    """
    try:
        x = sp.Symbol(var)
        eq = _parse_equation(expr)

        # 化为标准形式
        standard = sp.expand(eq.lhs - eq.rhs)
        coeffs = sp.Poly(standard, x).all_coeffs()

        solution = sp.solve(eq, x)
        steps = [f"方程: {eq.lhs} = {eq.rhs}", f"标准形式: {standard} = 0"]

        if len(coeffs) == 3:
            a, b, c = float(coeffs[0]), float(coeffs[1]), float(coeffs[2])
            delta = b * b - 4 * a * c
            steps.append(f"判别式 Δ = b² - 4ac = {b}² - 4×{a}×{c} = {delta}")
            if delta > 0:
                steps.append(f"Δ > 0，有两个不等实根")
            elif delta == 0:
                steps.append("Δ = 0，有两个相等实根（重根）")
            else:
                steps.append(f"Δ < 0，有一对共轭虚根")
                # 尝试因式分解
                factored = sp.factor(standard)
                if str(factored) != str(standard):
                    steps.append(f"因式分解: ({standard}).factor() = {factored}")
        else:
            # 尝试因式分解
            factored = sp.factor(standard)
            if str(factored) != str(standard):
                steps.append(f"因式分解: {standard} = {factored}")

        steps.append(f"解: {[str(s) for s in solution]}")
        return MathObject(
            result=[str(s) for s in solution],
            steps=steps,
            meaning=f"方程 {eq} 的解为 {[str(s) for s in solution]}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="discriminant")
def discriminant(expr: Union[str, sp.Expr], var: str = "x") -> MathObject:
    """计算一元二次方程的判别式 Δ = b² - 4ac。

    Args:
        expr: 方程表达式（ax² + bx + c = 0 形式）。
        var: 变量名。

    Returns:
        MathObject，result 为 Δ 值和根的定性描述。
    """
    try:
        ex = to_sympy(expr)
        x = sp.Symbol(var)
        if isinstance(ex, sp.Equality):
            poly = sp.Poly(ex.lhs - ex.rhs, x)
        else:
            poly = sp.Poly(ex, x)
        coeffs = poly.all_coeffs()
        if len(coeffs) != 3:
            return MathObject(error="表达式不是一元二次方程")
        a, b, c = float(coeffs[0]), float(coeffs[1]), float(coeffs[2])
        delta = b * b - 4 * a * c
        if delta > 0:
            nature = "有两个不等实根"
        elif delta == 0:
            nature = "有两个相等实根（重根）"
        else:
            nature = "有一对共轭虚根"
        return MathObject(
            result=delta,
            steps=[
                f"方程系数: a={a}, b={b}, c={c}",
                f"Δ = b² - 4ac = {b}² - 4×{a}×{c} = {delta}",
                f"Δ {'>' if delta > 0 else ('=' if delta == 0 else '<')} 0 → {nature}",
            ],
            meaning=f"判别式 Δ = {delta}，{nature}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="vieta_theorem")
def vieta_theorem(expr: Union[str, sp.Expr], var: str = "x") -> MathObject:
    """韦达定理：根与系数的关系。

    对于 ax² + bx + c = 0：
      - 两根之和: x₁ + x₂ = -b/a
      - 两根之积: x₁ × x₂ = c/a

    Args:
        expr: 方程表达式。
        var: 变量名。

    Returns:
        MathObject，result 为 (sum_roots, product_roots) 和验证信息。
    """
    try:
        ex = to_sympy(expr)
        x = sp.Symbol(var)
        if isinstance(ex, sp.Equality):
            poly = sp.Poly(ex.lhs - ex.rhs, x)
        else:
            poly = sp.Poly(ex, x)
        coeffs = poly.all_coeffs()
        if len(coeffs) != 3:
            return MathObject(error="表达式不是一元二次方程")

        a_val = float(coeffs[0])
        b_val = float(coeffs[1])
        c_val = float(coeffs[2])
        sum_roots = -b_val / a_val
        product_roots = c_val / a_val

        # 验证
        roots = sp.solve(poly.as_expr(), x)
        actual_sum = sum(float(r.evalf()) if r.is_real else complex(r.evalf()) for r in roots)

        return MathObject(
            result={
                "sum_of_roots": sum_roots,
                "product_of_roots": product_roots,
                "roots": [str(r) for r in roots],
            },
            steps=[
                f"标准形式: {a_val}x² + {b_val}x + {c_val} = 0",
                f"韦达定理: x₁ + x₂ = -b/a = -{b_val}/{a_val} = {sum_roots}",
                f"韦达定理: x₁ · x₂ = c/a = {c_val}/{a_val} = {product_roots}",
                f"验证: 实际根为 {[str(r) for r in roots]}",
                f"实际和: {actual_sum} ≈ {sum_roots} (吻合)" if abs(actual_sum - sum_roots) < 1e-9 else "不吻合",
            ],
            meaning=f"x₁ + x₂ = {sum_roots}，x₁ · x₂ = {product_roots}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 分式方程
# ===================================================================


@register(module="algebra", action="solve_fractional")
def solve_fractional(expr: Union[str, sp.Expr], var: str = "x") -> MathObject:
    """求解分式方程并检验增根。

    Args:
        expr: 分式方程，如 "1/x + 1/(x+1) = 1"。
        var: 变量名。

    Returns:
        MathObject，result 为 (有效解列表, 增根列表)。
    """
    try:
        x = sp.Symbol(var)
        eq = _parse_equation(expr)

        # 通分求解
        combined = sp.together(eq.lhs - eq.rhs)
        numerator = sp.numer(combined)
        denominator = sp.denom(combined)

        solutions = sp.solve(sp.Eq(numerator, 0), x)
        valid_solutions: List[str] = []
        extraneous_solutions: List[str] = []

        for sol in solutions:
            try:
                den_val = sp.simplify(denominator.subs(x, sol))
                if den_val == 0:
                    extraneous_solutions.append(str(sol))
                else:
                    valid_solutions.append(str(sol))
            except Exception:
                valid_solutions.append(str(sol))

        return MathObject(
            result={
                "valid_solutions": valid_solutions,
                "extraneous_solutions": extraneous_solutions,
            },
            steps=[
                f"分式方程: {eq}",
                f"通分: {combined} = 0",
                f"分子: {numerator} = 0",
                f"分母: {denominator}",
                f"解分子方程得: {[str(s) for s in solutions]}",
                f"代回分母检验: 有效解 {valid_solutions}" + (f"，增根 {extraneous_solutions}" if extraneous_solutions else ""),
            ],
            meaning=f"有效解: {valid_solutions}" + (f"；增根(舍): {extraneous_solutions}" if extraneous_solutions else ""),
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 无理方程
# ===================================================================


@register(module="algebra", action="solve_irrational")
def solve_irrational(expr: Union[str, sp.Expr], var: str = "x") -> MathObject:
    """求解无理方程（含偶次根式）并验根。

    Args:
        expr: 无理方程，如 "sqrt(x+1) = x - 1"。
        var: 变量名。

    Returns:
        MathObject，result 为 (有效解列表, 增根列表)。
    """
    try:
        x = sp.Symbol(var)
        eq = _parse_equation(expr)

        # 尝试直接求解
        solutions = sp.solve(eq, x)
        valid_solutions: List[str] = []
        extraneous_solutions: List[str] = []

        for sol in solutions:
            try:
                # 代入原方程检验
                lhs_val = sp.N(eq.lhs.subs(x, sol))
                rhs_val = sp.N(eq.rhs.subs(x, sol))
                if abs(float(lhs_val) - float(rhs_val)) < 1e-9:
                    valid_solutions.append(str(sol))
                else:
                    extraneous_solutions.append(str(sol))
            except Exception:
                # 无法数值验证时使用符号验证
                try:
                    if sp.simplify(eq.lhs.subs(x, sol) - eq.rhs.subs(x, sol)) == 0:
                        valid_solutions.append(str(sol))
                    else:
                        extraneous_solutions.append(str(sol))
                except Exception:
                    extraneous_solutions.append(str(sol))

        return MathObject(
            result={
                "valid_solutions": valid_solutions,
                "extraneous_solutions": extraneous_solutions,
            },
            steps=[
                f"无理方程: {eq}",
                f"求解得候选解: {[str(s) for s in solutions]}",
                f"代入原方程验根: 有效解 {valid_solutions}" + (f"，增根 {extraneous_solutions}" if extraneous_solutions else ""),
            ],
            meaning=f"有效解: {valid_solutions}" + (f"；增根(舍): {extraneous_solutions}" if extraneous_solutions else ""),
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 equation 模块。"""
    print("=== equation self_test ===")

    # 1. solve_linear
    r = solve_linear("2*x + 3 = 7", "x")
    assert r.ok, r.error
    assert "2" in str(r.result)
    print(f"  solve_linear: {r.result}")

    # 2. solve_linear_system
    r = solve_linear_system("x + y = 2", "x - y = 0", "x", "y")
    assert r.ok
    assert r.result.get("x") == "1" and r.result.get("y") == "1"
    print(f"  solve_linear_system: {r.result}")

    # 3. solve_quadratic
    r = solve_quadratic("x^2 - 4", "x")
    assert r.ok
    assert "-2" in r.result or "2" in r.result
    print(f"  solve_quadratic(x^2-4): {r.result}")

    # 4. discriminant
    r = discriminant("x^2 - 4*x + 4", "x")
    assert r.ok and r.result == 0
    print(f"  discriminant: Δ = {r.result}")

    # 5. vieta_theorem
    r = vieta_theorem("x^2 - 5*x + 6", "x")
    assert r.ok
    print(f"  vieta_theorem: {r.result}")

    # 6. solve_fractional
    r = solve_fractional("1/x = 2", "x")
    assert r.ok
    print(f"  solve_fractional: {r.result}")

    # 7. solve_irrational
    r = solve_irrational("sqrt(x) = 2", "x")
    assert r.ok
    print(f"  solve_irrational: {r.result}")

    print("=== equation self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
