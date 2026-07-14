"""函数与图像 — 函数三要素、一次函数、反比例函数、二次函数、幂/指数/对数函数、三角函数初步。

依赖: sympy, math
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_sympy(expr: Union[str, sp.Expr]) -> sp.Expr:
    """字符串转 sympy 表达式。"""
    if isinstance(expr, sp.Expr):
        return expr
    return sp.sympify(str(expr))


# ===================================================================
# 函数三要素
# ===================================================================


@register(module="algebra", action="domain")
def domain(expr: Union[str, sp.Expr], var: str = "x") -> MathObject:
    """求函数的定义域。

    Args:
        expr: 函数表达式，如 "1/(x-2)" 或 "sqrt(x-1)"。
        var: 变量名。

    Returns:
        MathObject，result 为定义域描述。
    """
    try:
        ex = _to_sympy(expr)
        x = sp.Symbol(var, real=True)

        # 分析定义域约束
        constraints = []
        # 检查分母
        denom = sp.denom(ex) if ex.has(sp.Pow) or ex.is_rational_function(x) else None
        # 使用 sympy 的 singularities 和 conditions
        try:
            from sympy.calculus.util import continuous_domain
            dom = continuous_domain(ex, x, sp.S.Reals)
            domain_str = str(dom)
        except Exception:
            domain_str = "R (全体实数，未检测到明显限制)"
        
        # 更精确的分析
        restrictions: List[str] = []
        
        # 检测分母约束
        if ex.is_rational_function(x):
            denom_expr = sp.denom(ex)
            denom_roots = sp.solve(denom_expr, x)
            for root in denom_roots:
                restrictions.append(f"x ≠ {root}")
        
        # 检测偶次根式约束
        def _find_even_roots(expr: sp.Expr, x: sp.Symbol, constraints: List[str]) -> None:
            """递归查找偶次根式约束。"""
            if expr.is_Pow and expr.args[1].is_Rational:
                exp_val = expr.args[1]
                if sp.denom(exp_val) % 2 == 0:  # 偶次根
                    radicand = expr.args[0]
                    constraints.append(f"{radicand} ≥ 0")
                    # 求解 radicand >= 0
            for arg in expr.args:
                _find_even_roots(arg, x, constraints)

        _find_even_roots(ex, x, restrictions)

        if not restrictions:
            restrictions.append("x ∈ R (全体实数)")

        return MathObject(
            result=domain_str,
            steps=[
                f"函数: f({var}) = {ex}",
                "分析定义域约束:",
                *[f"  {r}" for r in restrictions],
                f"定义域: {domain_str}",
            ],
            meaning=f"函数 f({var}) = {ex} 的定义域: {domain_str}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="range_estimate")
def range_estimate(
    expr: Union[str, sp.Expr], var: str = "x", domain_interval: Optional[str] = None
) -> MathObject:
    """估算函数的值域。

    Args:
        expr: 函数表达式。
        var: 变量名。
        domain_interval: 定义域区间描述（可选）。

    Returns:
        MathObject，result 为值域描述。
    """
    try:
        ex = _to_sympy(expr)
        x = sp.Symbol(var, real=True)
        try:
            from sympy.calculus.util import function_range
            rng = function_range(ex, x, sp.S.Reals)
            range_str = str(rng)
        except Exception:
            range_str = "无法精确计算"

        return MathObject(
            result=range_str,
            steps=[
                f"函数: f({var}) = {ex}",
                f"值域估算: {range_str}",
            ],
            meaning=f"f({var}) = {ex} 的值域为 {range_str}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="correspondence_rule")
def correspondence_rule(expr: Union[str, sp.Expr]) -> MathObject:
    """描述函数的对应法则。

    Args:
        expr: 函数表达式。

    Returns:
        MathObject，result 为对应法则的描述。
    """
    try:
        ex = _to_sympy(expr)
        # 分析表达式类型
        expr_type = "代数表达式"
        if ex.is_Polynomial:
            expr_type = "多项式函数"
        elif ex.is_rational_function():
            expr_type = "有理函数"
        elif ex.has(sp.sqrt):
            expr_type = "含根式函数"
        elif ex.has(sp.log):
            expr_type = "对数函数"
        elif ex.has(sp.exp):
            expr_type = "指数函数"

        return MathObject(
            result=f"f(x) = {ex}",
            steps=[
                f"给定表达式: {ex}",
                f"函数类型: {expr_type}",
                f"对应法则: 每个 x 映射到 {ex}",
            ],
            meaning=f"f: x → {ex}，类型: {expr_type}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 正比例/一次函数
# ===================================================================


@register(module="algebra", action="linear_function")
def linear_function(
    k: Union[int, float], b: Union[int, float] = 0
) -> MathObject:
    """生成一次函数表达式 y = kx + b。

    Args:
        k: 斜率。
        b: 截距。

    Returns:
        MathObject，result 为函数表达式字符串和分析。
    """
    try:
        expr_str = f"{k}*x + {b}" if b >= 0 else f"{k}*x - {abs(b)}"
        if k == 0:
            expr_str = str(b)
        elif k == 1 and b == 0:
            expr_str = "x"
        elif k == 1:
            expr_str = f"x + {b}" if b >= 0 else f"x - {abs(b)}"
        elif k == -1 and b == 0:
            expr_str = "-x"
        elif k == -1:
            expr_str = f"-x + {b}" if b > 0 else f"-x - {abs(b)}"

        func_type = "正比例函数" if b == 0 and k != 0 else "一次函数" if k != 0 else "常数函数"
        return MathObject(
            result=f"y = {expr_str}",
            steps=[
                f"斜率 k = {k}，y轴截距 b = {b}",
                f"类型: {func_type}",
                f"表达式: y = {expr_str}",
                f"图像: {'过原点' if b==0 else f'与y轴交于 (0,{b})'}的直线，{'递增' if k>0 else '递减' if k<0 else '水平'}",
            ],
            meaning=f"一次函数 y = {k}x {'+' if b>=0 else '-'} {abs(b)}，图像为直线",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="slope_intercept")
def slope_intercept(
    k: Union[int, float], b: Union[int, float]
) -> MathObject:
    """描述斜率和截距的几何意义。

    Args:
        k: 斜率。
        b: y轴截距。

    Returns:
        MathObject，result 为几何意义分析。
    """
    try:
        alpha = math.degrees(math.atan(k))
        return MathObject(
            result={"slope": k, "intercept": b, "angle_degrees": round(alpha, 2)},
            steps=[
                f"斜率 k = {k}，表示直线倾斜程度",
                f"倾斜角 α = arctan({k}) = {alpha:.2f}°",
                f"y轴截距 b = {b}，直线与y轴交于 (0, {b})",
                f"x轴截距 = {-b/k if k != 0 else '不存在'}",
            ],
            meaning=f"斜率 {k} 决定倾斜方向与陡峭程度，截距 {b} 决定与y轴交点",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 反比例函数
# ===================================================================


@register(module="algebra", action="inverse_proportional")
def inverse_proportional(k: Union[int, float]) -> MathObject:
    """生成反比例函数 y = k/x。

    Args:
        k: 比例系数。

    Returns:
        MathObject，result 为函数分析。
    """
    try:
        if k == 0:
            return MathObject(error="k 不能为 0")
        quadrant = "一、三" if k > 0 else "二、四"
        return MathObject(
            result=f"y = {k}/x",
            steps=[
                f"反比例函数: y = {k}/x",
                f"定义域: x ≠ 0 (即 (-∞, 0) ∪ (0, +∞))",
                f"值域: y ≠ 0",
                f"图像: 双曲线，位于第{quadrant}象限",
                f"对称性: 关于原点中心对称",
            ],
            meaning=f"反比例函数 y = {k}/x，k={'正' if k>0 else '负'}，图像为双曲线",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 二次函数
# ===================================================================


@register(module="algebra", action="quadratic_function")
def quadratic_function(
    a: Union[int, float], b: Union[int, float], c: Union[int, float]
) -> MathObject:
    """分析二次函数 y = ax² + bx + c 的顶点、对称轴、开口。

    Args:
        a: 二次项系数。
        b: 一次项系数。
        c: 常数项。

    Returns:
        MathObject，result 为顶点/对称轴/开口分析字典。
    """
    try:
        if a == 0:
            return MathObject(error="a 不能为 0，否则不是二次函数")
        vertex_x = -b / (2 * a)
        vertex_y = a * vertex_x ** 2 + b * vertex_x + c
        axis = f"x = {vertex_x}"
        direction = "向上" if a > 0 else "向下"
        
        # 判别式
        delta = b * b - 4 * a * c
        if delta > 0:
            x_intercepts = f"两个交点: ({-b-math.sqrt(delta)})/(2*{a}) 和 ({-b+math.sqrt(delta)})/(2*{a})"
        elif delta == 0:
            x_intercepts = f"一个切点: x = {vertex_x}"
        else:
            x_intercepts = "无交点（不与x轴相交）"

        return MathObject(
            result={
                "vertex": (vertex_x, vertex_y),
                "axis_of_symmetry": axis,
                "direction": direction,
                "y_intercept": c,
                "x_intercepts": x_intercepts,
            },
            steps=[
                f"二次函数: y = {a}x² + {b}x + {c}",
                f"顶点横坐标 (对称轴): x = -b/(2a) = -{b}/(2×{a}) = {vertex_x}",
                f"顶点纵坐标: y = {vertex_y}",
                f"顶点: ({vertex_x}, {vertex_y})",
                f"开口方向: {direction} (a={'<' if a<0 else '>'}0)",
                f"y轴截距: (0, {c})",
                f"判别式 Δ = {delta}，{x_intercepts}",
            ],
            meaning=f"二次函数顶点({vertex_x}, {vertex_y})，对称轴 {axis}，开口{direction}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="quadratic_extrema")
def quadratic_extrema(
    a: Union[int, float], b: Union[int, float], c: Union[int, float]
) -> MathObject:
    """求二次函数的最值。

    Args:
        a: 二次项系数。
        b: 一次项系数。
        c: 常数项。

    Returns:
        MathObject，result 为最值信息。
    """
    try:
        if a == 0:
            return MathObject(error="a 不能为 0")
        vertex_x = -b / (2 * a)
        vertex_y = a * vertex_x ** 2 + b * vertex_x + c
        extrema_type = "最小值" if a > 0 else "最大值"
        return MathObject(
            result={"type": extrema_type, "x": vertex_x, "value": vertex_y},
            steps=[
                f"y = {a}x² + {b}x + {c}",
                f"a = {a} > 0 → 开口{'向上' if a>0 else '向下'}，在顶点处取{extrema_type}",
                f"顶点 x = -b/(2a) = {vertex_x}",
                f"{extrema_type} = {vertex_y}",
            ],
            meaning=f"函数在 x={vertex_x} 处取得{extrema_type} {vertex_y}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 幂/指数/对数函数
# ===================================================================


@register(module="algebra", action="power_function")
def power_function(x: Union[int, float, str], n: Union[int, float]) -> MathObject:
    """计算幂函数 x^n 的值。

    Args:
        x: 底数（数值或变量符号如 "x"）。
        n: 指数。

    Returns:
        MathObject，result 为计算结果或表达式。
    """
    try:
        if isinstance(x, str) and x.strip().isalpha():
            result_str = f"{x}^{n}" if n != 1 else x
            return MathObject(
                result=result_str,
                steps=[f"幂函数: f({x}) = {x}^{n}"],
                meaning=f"f({x}) = {x}^{n}",
            )
        val = float(x) ** n
        return MathObject(
            result=val,
            steps=[f"{x}^{n} = {val}"],
            meaning=f"幂次运算: {x}^{n} = {val}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="exponential_function")
def exponential_function(
    base: Union[int, float], x: Union[int, float]
) -> MathObject:
    """计算指数函数 a^x 的值。

    Args:
        base: 底数 a（a > 0 且 a ≠ 1）。
        x: 指数。

    Returns:
        MathObject，result 为计算结果和分析。
    """
    try:
        if base <= 0:
            return MathObject(error="指数函数底数 a 必须大于 0")
        if base == 1:
            return MathObject(error="底数为 1 时为常数函数 y=1")
        val = base ** x
        growth = "递增" if base > 1 else "递减"
        return MathObject(
            result=val,
            steps=[
                f"指数函数: y = {base}^{x}",
                f"y({x}) = {base}^{x} = {val}",
                f"底数 {base} {'>' if base>1 else '<'} 1 → 函数{growth}",
                f"恒过定点 (0, 1)",
                f"渐近线: y = 0 (x→-∞)" if base > 1 else "渐近线: y = 0 (x→+∞)",
            ],
            meaning=f"y = {base}^{x}，{growth}，过(0,1)，以x轴为渐近线",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="log_function")
def log_function(
    base: Union[int, float], x: Union[int, float]
) -> MathObject:
    """计算对数函数 log_a(x) 的值。

    Args:
        base: 底数 a（a > 0 且 a ≠ 1）。
        x: 真数（x > 0）。

    Returns:
        MathObject，result 为计算结果和分析。
    """
    try:
        if base <= 0 or base == 1:
            return MathObject(error="对数底数 a 必须 > 0 且 ≠ 1")
        if x <= 0:
            return MathObject(error="真数 x 必须 > 0")
        if base == math.e:
            val = math.log(x)
        elif base == 10:
            val = math.log10(x)
        else:
            val = math.log(x) / math.log(base)
        
        growth = "递增" if base > 1 else "递减"
        return MathObject(
            result=val,
            steps=[
                f"对数函数: y = log_{base}({x})",
                f"y = ln({x}) / ln({base}) = {val}",
                f"底数 {base} {'>' if base>1 else '<'} 1 → 函数{growth}",
                f"恒过定点 (1, 0)",
                f"渐近线: x = 0 (y轴)",
            ],
            meaning=f"log_{base}({x}) = {val}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 三角函数（初步）
# ===================================================================


@register(module="algebra", action="sine_cosine_tangent")
def sine_cosine_tangent(
    angle: Union[int, float], mode: str = "degrees"
) -> MathObject:
    """计算三角函数值（基于单位圆定义）。

    Args:
        angle: 角度值。
        mode: "degrees"（角度制）或 "radians"（弧度制）。

    Returns:
        MathObject，result 为 (sin, cos, tan) 元组。
    """
    try:
        if mode == "degrees":
            rad = math.radians(angle)
        else:
            rad = float(angle)
        
        sin_val = math.sin(rad)
        cos_val = math.cos(rad)
        tan_val = math.tan(rad) if abs(math.cos(rad)) > 1e-12 else float("inf")

        return MathObject(
            result={"sin": round(sin_val, 10), "cos": round(cos_val, 10), "tan": round(tan_val, 10)},
            steps=[
                f"角度: {angle}° {'= ' + str(rad) + ' rad' if mode=='degrees' else ''}",
                f"单位圆上点 (cos θ, sin θ) = ({cos_val:.4f}, {sin_val:.4f})",
                f"sin θ = {sin_val:.6f}",
                f"cos θ = {cos_val:.6f}",
                f"tan θ = sin/cos = {tan_val:.6f}" if abs(cos_val) > 1e-12 else "tan θ 无定义 (cos θ = 0)",
            ],
            meaning=f"角度 {angle}° 在单位圆上对应点 ({cos_val:.4f}, {sin_val:.4f})",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="trig_basic_identities")
def trig_basic_identities() -> MathObject:
    """展示三角函数的诱导公式。

    Returns:
        MathObject，result 为常见诱导公式列表。
    """
    identities = [
        "sin²θ + cos²θ = 1",
        "1 + tan²θ = sec²θ",
        "1 + cot²θ = csc²θ",
        "sin(-θ) = -sin θ (奇函数)",
        "cos(-θ) = cos θ (偶函数)",
        "tan(-θ) = -tan θ (奇函数)",
        "sin(π/2 - θ) = cos θ",
        "cos(π/2 - θ) = sin θ",
        "sin(π - θ) = sin θ",
        "cos(π - θ) = -cos θ",
        "sin(π + θ) = -sin θ",
        "cos(π + θ) = -cos θ",
        "sin(2π + θ) = sin θ",
        "cos(2π + θ) = cos θ",
    ]
    return MathObject(
        result=identities,
        steps=["三角函数诱导公式 (Induction Formulas):", *identities],
        meaning="基于单位圆的三角函数诱导公式",
    )


@register(module="algebra", action="trig_periodicity")
def trig_periodicity(func: str) -> MathObject:
    """描述三角函数的周期性。

    Args:
        func: 函数名 "sin", "cos", "tan" 之一。

    Returns:
        MathObject，result 为周期性信息。
    """
    try:
        info = {
            "sin": {"period": "2π", "frequency": "1/2π", "description": "sin(x + 2π) = sin x"},
            "cos": {"period": "2π", "frequency": "1/2π", "description": "cos(x + 2π) = cos x"},
            "tan": {"period": "π", "frequency": "1/π", "description": "tan(x + π) = tan x"},
        }
        if func.lower() not in info:
            return MathObject(error=f"不支持 '{func}'，仅支持 sin, cos, tan")

        data = info[func.lower()]
        return MathObject(
            result=data,
            steps=[
                f"函数: y = {func}(x)",
                f"最小正周期: T = {data['period']}",
                f"频率: f = {data['frequency']}",
                f"周期性: {data['description']}",
            ],
            meaning=f"{func}(x) 的最小正周期为 {data['period']}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 function 模块。"""
    print("=== function self_test ===")

    # 1. domain
    r = domain("1/(x-2)", "x")
    assert r.ok, r.error
    print(f"  domain: {r.result}")

    # 2. linear_function
    r = linear_function(2, 3)
    assert r.ok
    print(f"  linear_function: {r.result}")

    # 3. inverse_proportional
    r = inverse_proportional(5)
    assert r.ok
    print("  inverse_proportional: pass")

    # 4. quadratic_function
    r = quadratic_function(1, -4, 3)
    assert r.ok
    print(f"  quadratic_function: vertex={r.result['vertex']}")

    # 5. quadratic_extrema
    r = quadratic_extrema(1, -4, 3)
    assert r.ok
    print(f"  quadratic_extrema: {r.result}")

    # 6. sine_cosine_tangent
    r = sine_cosine_tangent(30, "degrees")
    assert r.ok
    assert abs(r.result["sin"] - 0.5) < 0.001
    print(f"  sine_cosine_tangent(30°): sin={r.result['sin']:.2f}, cos={r.result['cos']:.2f}")

    # 7. log_function
    r = log_function(2, 8)
    assert r.ok and abs(r.result - 3.0) < 0.001
    print(f"  log_function(log2(8)): {r.result}")

    print("=== function self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
