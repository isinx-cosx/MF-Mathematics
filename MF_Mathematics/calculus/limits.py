"""极限 — 双侧极限、左右极限、连续性判断、间断点分类。

依赖: sympy
"""

from __future__ import annotations
from MF_Mathematics.core.helpers import to_sympy

from typing import Optional, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register
@register(module="calculus", action="limit")
def limit(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
    direction: Optional[str] = None,
) -> MathObject:
    """计算函数在某点的极限。

    Args:
        expr: 函数表达式，如 "sin(x)/x"。
        var: 自变量名，默认 "x"。
        point: 趋近点，默认 0。支持符号如 "oo"（正无穷）、"-oo"（负无穷）。
        direction: 方向，None 为双侧，"+" 为右极限，"-" 为左极限。

    Returns:
        MathObject，result 为极限值。
    """
    try:
        x = sp.Symbol(var)
        ex = to_sympy(expr)

        if direction == "+":
            dir_str = "+"
            result = sp.limit(ex, x, point, dir="+")
            step_dir = f"计算右极限 lim_{{{var}→{point}⁺}} {ex}"
        elif direction == "-":
            dir_str = "-"
            result = sp.limit(ex, x, point, dir="-")
            step_dir = f"计算左极限 lim_{{{var}→{point}⁻}} {ex}"
        else:
            dir_str = ""
            result = sp.limit(ex, x, point)
            step_dir = f"计算极限 lim_{{{var}→{point}}} {ex}"

        return MathObject(
            result=str(result),
            steps=[
                step_dir,
                f"结果: {result}",
            ],
            meaning=f"lim_{{{var}→{point}{dir_str}}} {ex} = {result}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="is_continuous")
def is_continuous(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
) -> MathObject:
    """判断函数在某点是否连续。

    满足三个条件：
    1. f(point) 有定义
    2. lim_{x→point} f(x) 存在
    3. lim_{x→point} f(x) = f(point)

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 检测点。

    Returns:
        MathObject，result 为 True/False。
    """
    try:
        x = sp.Symbol(var)
        ex = to_sympy(expr)

        # 1. 函数值
        try:
            func_val = sp.N(ex.subs(x, point))
            defined = True
        except Exception:
            func_val = None
            defined = False

        # 2. 极限
        lim_val = sp.limit(ex, x, point)

        # 3. 比较
        if defined and lim_val.is_finite:
            diff = abs(float(sp.N(lim_val)) - float(func_val))
            continuous = diff < 1e-10
        elif lim_val == sp.oo or lim_val == -sp.oo or lim_val == sp.zoo:
            continuous = False
        else:
            continuous = False

        steps = [
            f"f({point}) = {func_val} {'(有定义)' if defined else '(无定义)'}",
            f"lim_{{{var}→{point}}} f({var}) = {lim_val}",
            f"两者{'相等' if continuous else '不相等或极限不存在'}",
        ]
        return MathObject(
            result=continuous,
            steps=steps,
            meaning=f"函数在 {var}={point} {'连续' if continuous else '不连续'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="discontinuity_classify")
def discontinuity_classify(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
) -> MathObject:
    """判断间断点类型。

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
        ex = to_sympy(expr)

        left_lim = sp.limit(ex, x, point, dir="-")
        right_lim = sp.limit(ex, x, point, dir="+")

        try:
            func_val = ex.subs(x, point)
            defined = True
        except Exception:
            func_val = None
            defined = False

        steps = [
            f"左极限: lim_{{{var}→{point}⁻}} = {left_lim}",
            f"右极限: lim_{{{var}→{point}⁺}} = {right_lim}",
            f"f({point}) = {func_val} {'(有定义)' if defined else '(无定义)'}",
        ]

        # 判断类型
        left_inf = left_lim in (sp.oo, -sp.oo, sp.zoo)
        right_inf = right_lim in (sp.oo, -sp.oo, sp.zoo)

        if left_inf or right_inf:
            category = "无穷间断点"
            detail = "至少一侧极限为无穷"
        elif left_lim == right_lim:
            category = "可去间断点"
            detail = "左右极限相等，但函数值不匹配或无定义"
        elif left_lim.is_finite and right_lim.is_finite and left_lim != right_lim:
            category = "跳跃间断点"
            detail = f"左右极限存在但不相等: {left_lim} ≠ {right_lim}"
        else:
            category = "振荡间断点"
            detail = "极限不存在（非无穷）"

        steps.append(f"分类: {category} — {detail}")

        return MathObject(
            result=category,
            steps=steps,
            meaning=f"{var}={point} 是 {category}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 limits 模块。"""
    print("=== limits self_test ===")

    # 1. limit: sin(x)/x → 1
    r = limit("sin(x)/x", "x", 0)
    assert r.ok, r.error
    assert "1" in r.result
    print(f"  limit(sin(x)/x, x→0): {r.result}")
    print("  limit: pass")

    # 2. limit: (x^2-1)/(x-1) → 2
    r = limit("(x**2 - 1)/(x - 1)", "x", 1)
    assert r.ok and "2" in r.result
    print(f"  limit((x^2-1)/(x-1), x→1): {r.result}")

    # 3. limit: 1/x x→0+ → oo
    r = limit("1/x", "x", 0, direction="+")
    assert r.ok
    print(f"  limit(1/x, x→0+): {r.result}")

    # 4. is_continuous: sin(x) at 0 → True
    r = is_continuous("sin(x)", "x", 0)
    assert r.ok and r.result is True
    print(f"  is_continuous(sin(x), 0): {r.result}")

    # 5. is_continuous: 1/(x-1) at x=1 → False
    r = is_continuous("1/(x-1)", "x", 1)
    assert r.ok and r.result is False
    print(f"  is_continuous(1/(x-1), 1): {r.result}")

    # 6. discontinuity_classify
    r = discontinuity_classify("1/(x-1)", "x", 1)
    assert r.ok
    print(f"  discontinuity_classify(1/(x-1), 1): {r.result}")

    print("=== limits self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
