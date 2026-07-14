"""级数 — 数项级数求和、收敛性判别、幂级数展开、收敛半径。

依赖: sympy
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


@register(module="calculus", action="series_sum")
def series_sum(
    expr: Union[str, sp.Expr],
    var: str = "n",
    a: Union[str, float, int] = 1,
    b: Union[str, float, int] = "oo",
) -> MathObject:
    """数项级数求和：∑_{n=a}^{b} expr。

    Args:
        expr: 通项表达式，如 "1/n**2"。
        var: 求和指标变量名，默认 "n"。
        a: 求和下限。
        b: 求和上限，"oo" 表示无穷。

    Returns:
        MathObject，result 为级数和。
    """
    try:
        n = sp.Symbol(var)
        ex = _to_sympy(expr)

        b_val = sp.oo if str(b) in ("oo", "inf") else sp.sympify(b)
        a_val = sp.sympify(a)

        result = sp.summation(ex, (n, a_val, b_val))

        try:
            numeric_val = float(sp.N(result))
            result_str = f"{result} ≈ {numeric_val}"
        except Exception:
            result_str = str(result)

        return MathObject(
            result=result_str,
            steps=[
                f"通项: a_{{{var}}} = {ex}",
                f"求和范围: {var} = {a} 到 {b}",
                f"∑a_{{{var}}} = {result}",
            ],
            meaning=f"∑_{{{var}={a}}}^{{{b}}} {ex} = {result}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="series_convergence")
def series_convergence(
    expr: Union[str, sp.Expr],
    var: str = "n",
) -> MathObject:
    """级数收敛性判别。

    使用比值判别法 (D'Alembert) 和根值判别法 (Cauchy)。

    Args:
        expr: 通项表达式。
        var: 求和指标变量名。

    Returns:
        MathObject，result 为收敛性结论。
    """
    try:
        n = sp.Symbol(var)
        ex = _to_sympy(expr)
        ex_next = sp.simplify(ex.subs(n, n + 1))
        ratio_expr = sp.simplify(sp.Abs(ex_next / ex))
        ratio_limit = sp.limit(ratio_expr, n, sp.oo)

        # 根值判别法: lim |a_n|^(1/n)
        root_expr = sp.simplify(sp.Abs(ex) ** (1 / n))
        root_limit = sp.limit(root_expr, n, sp.oo)

        steps = [
            f"通项: a_{{{var}}} = {ex}",
            f"比值判别法: lim |a_{{{var}+1}}/a_{{{var}}}| = {ratio_limit}",
            f"根值判别法: lim |a_{{{var}}}|^(1/{var}) = {root_limit}",
        ]

        # 判断结论
        if ratio_limit < 1 or root_limit < 1:
            conclusion = "绝对收敛"
            detail = "比值/根值 < 1"
        elif ratio_limit > 1 or root_limit > 1:
            conclusion = "发散"
            detail = "比值/根值 > 1"
        elif ratio_limit == 1 and root_limit == 1:
            conclusion = "判别法失效"
            detail = "比值=根值=1，需要其他方法"
        else:
            conclusion = "待定"
            detail = "结果不一致，建议进一步分析"

        steps.append(f"结论: {conclusion} — {detail}")

        return MathObject(
            result={"conclusion": conclusion, "ratio_test": str(ratio_limit), "root_test": str(root_limit)},
            steps=steps,
            meaning=f"级数 ∑{ex} 的收敛性: {conclusion}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="power_series")
def power_series(
    expr: Union[str, sp.Expr],
    var: str = "x",
    point: Union[str, float, int] = 0,
    n: int = 5,
) -> MathObject:
    """幂级数展开（同泰勒级数）。

    Args:
        expr: 函数表达式。
        var: 自变量名。
        point: 展开中心。
        n: 展开阶数。

    Returns:
        MathObject，result 为幂级数多项式。
    """
    try:
        x = sp.Symbol(var)
        ex = _to_sympy(expr)
        series = sp.series(ex, x, point, n + 1).removeO()
        poly = sp.expand(series)

        # 构造累加和形式
        terms = []
        for i in range(n + 1):
            coeff = sp.diff(ex, x, i).subs(x, point) / sp.factorial(i)
            if coeff != 0:
                term = sp.simplify(coeff * (x - point) ** i)
                terms.append(str(term))

        return MathObject(
            result=str(poly),
            steps=[
                f"f({var}) = {ex}",
                f"展开中心: {var} = {point}",
                f"展开至 {n} 阶",
                f"各阶项: {' + '.join(terms)}",
                f"结果: {poly}",
            ],
            meaning=f"{ex} 在 {var}={point} 处的幂级数（{n} 阶）= {poly}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="power_series_radius")
def power_series_radius(
    expr: Union[str, sp.Expr],
    var: str = "x",
) -> MathObject:
    """计算幂级数的收敛半径（比值法）。

    R = 1 / lim_{n→∞} |a_{n+1}/a_n|

    Args:
        expr: 幂级数通项系数表达式（仅含 n 的部分），如 "1/factorial(n)"。
        var: 系数中的指标变量名，默认 "n"（内部会映射到整数符号）。

    Returns:
        MathObject，result 为收敛半径 R。
    """
    try:
        n = sp.Symbol(var)
        ex = _to_sympy(expr)

        ex_next = sp.simplify(ex.subs(n, n + 1))
        ratio = sp.simplify(sp.Abs(ex_next / ex))
        ratio_limit = sp.limit(ratio, n, sp.oo)

        if ratio_limit == 0:
            R = sp.oo
        elif ratio_limit == sp.oo:
            R = 0
        else:
            R = 1 / ratio_limit

        return MathObject(
            result=str(R),
            steps=[
                f"系数: a_n = {ex}",
                f"a_{{n+1}}/a_n = {ratio}",
                f"lim |a_{{n+1}}/a_n| = {ratio_limit}",
                f"收敛半径 R = 1 / {ratio_limit} = {R}",
            ],
            meaning=f"收敛半径 R = {R}，收敛区间为 |x| < {R}" if R != sp.oo else "收敛半径 R = ∞，处处收敛",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 级数审敛法（新增）
# ===================================================================


def _abs_part(expr: sp.Expr, n: sp.Symbol) -> sp.Expr:
    """提取交错级数的绝对值部分（去掉 (-1)**n / (-1)**(n+1) 因子）。"""
    expr = sp.simplify(expr)
    # 尝试剥离 (-1)**(n) 或 (-1)**(n+1) 因子
    for factor in [(-1) ** n, (-1) ** (n + 1)]:
        simplified = sp.simplify(expr / factor)
        if simplified != expr:
            return sp.simplify(simplified)
    # 退化为取绝对值
    return sp.simplify(sp.Abs(expr))


def _is_alternating(expr: sp.Expr, n: sp.Symbol) -> bool:
    """判断是否为交错级数（含 (-1)**n 或 (-1)**(n+1) 因子）。"""
    expr = sp.simplify(expr)
    # 检查表达式或其因数中是否包含 (-1)^n 或 (-1)^(n+1)
    expr_atoms = expr.atoms(sp.Pow) if hasattr(expr, 'atoms') else set()
    for atom in expr_atoms:
        base, exp = atom.as_base_exp()
        if base == -1 and (exp == n or exp == n + 1):
            return True
    # 回退: 检查表达式中是否存在 (-1)**n 模式
    return ((-1) ** n in expr.args or (-1) ** (n + 1) in expr.args)


@register(module="calculus", action="leibniz_test")
def leibniz_test(
    expr: Union[str, sp.Expr],
    var: str = "n",
) -> MathObject:
    """莱布尼茨判别法（交错级数审敛法）。

    检测交错级数 ∑(-1)**n a_n：
    1. a_n 单调递减（对连续化函数求导 < 0）；
    2. lim a_n = 0。
    两者皆满足则级数收敛。

    Args:
        expr: 通项表达式（可含 (-1)**n 或 (-1)**(n+1)）。
        var: 求和指标变量名。

    Returns:
        MathObject，result 为 "convergent"/"divergent"/"inconclusive"。
    """
    try:
        n = sp.Symbol(var)
        ex = _to_sympy(expr)

        if not _is_alternating(ex, n):
            return MathObject(
                result="inconclusive",
                steps=[
                    f"通项: a_{{{var}}} = {ex}",
                    "未检测到 (-1)**n 或 (-1)**(n+1) 因子，非交错级数",
                ],
                meaning="莱布尼茨判别法仅适用于交错级数",
                data={"latex": r"\text{not alternating}"},
            )

        a_n = _abs_part(ex, n)

        # 条件 1: 单调递减 — 对连续化函数求导
        deriv = sp.diff(a_n, n)
        deriv_simplified = sp.simplify(deriv)
        # 判断导数是否恒 <= 0（取极限与符号）
        deriv_limit = sp.limit(deriv_simplified, n, sp.oo)
        decreasing = deriv_limit <= 0

        # 条件 2: 趋于 0
        limit_val = sp.limit(a_n, n, sp.oo)
        tends_to_zero = limit_val == 0

        steps = [
            f"通项: a_{{{var}}} = {ex}",
            f"绝对值部分: |a_{{{var}}}| = {a_n}",
            f"导数 d/d{var}(|a_{{{var}}}|) = {deriv_simplified}",
            f"lim 导数 = {deriv_limit} → 单调递减: {decreasing}",
            f"lim |a_{{{var}}}| = {limit_val} → 趋于 0: {tends_to_zero}",
        ]

        if decreasing and tends_to_zero:
            conclusion = "convergent"
            detail = "满足莱布尼茨条件（单调递减且趋于 0）"
        elif not tends_to_zero:
            conclusion = "divergent"
            detail="通项不趋于 0，级数发散"
        else:
            conclusion = "inconclusive"
            detail = "无法判定单调性，判别法失效"

        steps.append(f"结论: {conclusion} — {detail}")

        return MathObject(
            result=conclusion,
            steps=steps,
            meaning=f"交错级数 ∑{ex}: {conclusion}",
            data={"latex": r"\sum " + sp.latex(ex) + r" \text{ is } " + conclusion},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="limit_comparison_test")
def limit_comparison_test(
    expr: Union[str, sp.Expr],
    var: str = "n",
    compare_expr: Optional[Union[str, sp.Expr]] = None,
) -> MathObject:
    """极限比较判别法。

    计算 lim (a_n / b_n)，若结果为有限正数，则 ∑a_n 与 ∑b_n 同敛散。

    Args:
        expr: 待判别通项。
        var: 求和指标变量名。
        compare_expr: 比较级数通项；缺省时自动选择 p-级数 1/n**2 或几何级数。

    Returns:
        MathObject，result 为 "convergent"/"divergent"/"inconclusive"。
    """
    try:
        n = sp.Symbol(var)
        ex = _to_sympy(expr)

        if compare_expr is None:
            # 自动选择比较级数：若含指数衰减倾向用几何级数，否则用 p-级数 1/n^2
            if ex.has(sp.exp(n)) or ex.has(sp.exp(-n)):
                compare_expr = sp.Rational(1, 2) ** n
            else:
                compare_expr = 1 / n ** 2
        b_n = _to_sympy(compare_expr)

        ratio = sp.simplify(ex / b_n)
        L = sp.limit(ratio, n, sp.oo)
        L_val = sp.N(L)

        steps = [
            f"通项: a_{{{var}}} = {ex}",
            f"比较级数: b_{{{var}}} = {b_n}",
            f"lim (a_{{{var}}}/b_{{{var}}}) = lim {ratio} = {L}",
        ]

        if L.is_number and L > 0 and L != sp.oo:
            # 比较级数 1/n^2 收敛，几何级数收敛
            if b_n == 1 / n ** 2 or b_n == sp.Rational(1, 2) ** n:
                conclusion = "convergent"
                detail = f"极限 {L_val} 为有限正数，与收敛的比较级数同敛散"
            else:
                conclusion = "inconclusive"
                detail = "比较级数敛散性未知，无法判定"
        elif L == 0:
            conclusion = "inconclusive"
            detail = "极限为 0，需比较级数收敛才能推出收敛，信息不足"
        elif L == sp.oo:
            conclusion = "inconclusive"
            detail = "极限为 ∞，需比较级数发散才能推出发散，信息不足"
        else:
            conclusion = "inconclusive"
            detail = f"极限 {L} 非有限正数，判别法失效"

        steps.append(f"结论: {conclusion} — {detail}")

        return MathObject(
            result=conclusion,
            steps=steps,
            meaning=f"极限比较判别法 ∑{ex}: {conclusion}",
            data={"latex": r"\lim_{" + sp.latex(n) + r"\to\infty} \frac{" + sp.latex(ex) + r"}{" + sp.latex(b_n) + r"} = " + sp.latex(L)},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="integral_test")
def integral_test(
    expr: Union[str, sp.Expr],
    var: str = "n",
) -> MathObject:
    """积分判别法。

    将通项视为连续函数 f(x)，计算 ∫_1^∞ f(x) dx；
    若反常积分收敛，则正项级数 ∑a_n 收敛。

    Args:
        expr: 通项表达式（正项、连续、单调递减）。
        var: 求和指标变量名。

    Returns:
        MathObject，result 为 "convergent"/"divergent"/"inconclusive"。
    """
    try:
        n = sp.Symbol(var)
        x = sp.Symbol(var, positive=True)
        ex = _to_sympy(expr)
        f = sp.simplify(ex.subs(n, x))

        integral = sp.integrate(f, (x, 1, sp.oo))
        integral_val = sp.N(integral)

        steps = [
            f"通项: a_{{{var}}} = {ex}",
            f"连续化: f({var}) = {f}",
            f"∫_1^∞ f({var}) d{var} = {integral}",
        ]

        if integral == sp.oo or integral_val == sp.oo:
            conclusion = "divergent"
            detail = "反常积分发散，级数发散"
        elif integral.is_number and integral_val.is_finite:
            conclusion = "convergent"
            detail = "反常积分收敛，级数收敛"
        else:
            conclusion = "inconclusive"
            detail = "积分无法判定，判别法失效"

        steps.append(f"结论: {conclusion} — {detail}")

        return MathObject(
            result=conclusion,
            steps=steps,
            meaning=f"积分判别法 ∑{ex}: {conclusion}",
            data={"latex": r"\int_1^{\infty} " + sp.latex(f) + r"\,d" + sp.latex(x) + r" = " + sp.latex(integral)},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="direct_comparison_test")
def direct_comparison_test(
    expr: Union[str, sp.Expr],
    var: str = "n",
    compare_expr: Optional[Union[str, sp.Expr]] = None,
) -> MathObject:
    """比较判别法（直接比较）。

    通过不等式关系与已知敛散的级数比较：
    - 若 0 ≤ a_n ≤ b_n 且 ∑b_n 收敛，则 ∑a_n 收敛；
    - 若 0 ≤ b_n ≤ a_n 且 ∑b_n 发散，则 ∑a_n 发散。

    Args:
        expr: 待判别通项。
        var: 求和指标变量名。
        compare_expr: 比较级数通项；缺省时自动生成。

    Returns:
        MathObject，result 为 "convergent"/"divergent"/"inconclusive"。
    """
    try:
        n = sp.Symbol(var)
        ex = _to_sympy(expr)

        if compare_expr is None:
            # 自动生成：取主导项构造 p-级数或几何级数
            if ex.has(sp.exp(n)) or ex.has(sp.exp(-n)):
                compare_expr = sp.Rational(1, 2) ** n
            else:
                # 提取 n 的最高次幂，构造 1/n^p
                denom = sp.denom(ex) if ex.is_Mul or ex.is_Pow else ex
                # 简单启发：用 1/n^2 作为收敛上界
                compare_expr = 1 / n ** 2
        b_n = _to_sympy(compare_expr)

        diff = sp.simplify(ex - b_n)
        # 取大 n 处符号判断不等式方向
        sign_limit = sp.limit(sp.sign(diff), n, sp.oo)

        steps = [
            f"通项: a_{{{var}}} = {ex}",
            f"比较级数: b_{{{var}}} = {b_n}",
            f"a_{{{var}}} - b_{{{var}}} = {diff}",
        ]

        if sign_limit <= 0:
            # a_n <= b_n
            if b_n == 1 / n ** 2 or b_n == sp.Rational(1, 2) ** n:
                conclusion = "convergent"
                detail = f"0 ≤ a_n ≤ b_n 且比较级数收敛，故收敛"
            else:
                conclusion = "inconclusive"
                detail = "比较级数敛散性未知"
        elif sign_limit >= 0:
            # a_n >= b_n
            if b_n == 1 / n or b_n == 1:
                conclusion = "divergent"
                detail = "a_n ≥ b_n 且比较级数发散，故发散"
            else:
                conclusion = "inconclusive"
                detail = "比较级数敛散性未知"
        else:
            conclusion = "inconclusive"
            detail = "无法判定不等式关系"

        steps.append(f"结论: {conclusion} — {detail}")

        return MathObject(
            result=conclusion,
            steps=steps,
            meaning=f"直接比较判别法 ∑{ex}: {conclusion}",
            data={"latex": sp.latex(ex) + r" \lessgtr " + sp.latex(b_n)},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="p_series_test")
def p_series_test(
    expr: Union[str, sp.Expr],
    var: str = "n",
) -> MathObject:
    """p-级数判别法。

    匹配形如 1/n**p 的级数，提取指数 p：
    - p > 1 收敛；
    - p <= 1 发散。

    Args:
        expr: 通项表达式，形如 1/n**p。
        var: 求和指标变量名。

    Returns:
        MathObject，result 为 "convergent"/"divergent"/"inconclusive"。
    """
    try:
        n = sp.Symbol(var)
        ex = _to_sympy(expr)

        # 匹配 1/n**p 或 n**(-p)
        p = None
        simplified = sp.simplify(ex)
        if simplified.is_Pow and simplified.base == n:
            p = -simplified.exp
        elif simplified.is_Pow and simplified.base == 1 / n:
            p = simplified.exp
        elif simplified == 1 / n:
            p = sp.Integer(1)
        elif simplified.is_Pow and simplified.base.is_Pow and simplified.base.base == n:
            # n**(k) 形式
            p = -simplified.exp * simplified.base.exp if simplified.base.exp.is_number else None

        steps = [
            f"通项: a_{{{var}}} = {ex}",
        ]

        if p is None:
            return MathObject(
                result="inconclusive",
                steps=steps + ["无法匹配 1/n**p 形式，非 p-级数"],
                meaning="p-级数判别法仅适用于 1/n**p",
                data={"latex": r"\text{not a p-series}"},
            )

        p_val = sp.N(p)
        steps.append(f"提取指数 p = {p} ≈ {p_val}")

        if p_val > 1:
            conclusion = "convergent"
            detail = f"p = {p_val} > 1，p-级数收敛"
        else:
            conclusion = "divergent"
            detail = f"p = {p_val} <= 1，p-级数发散"

        steps.append(f"结论: {conclusion} — {detail}")

        return MathObject(
            result=conclusion,
            steps=steps,
            meaning=f"p-级数 ∑{ex}: {conclusion}",
            data={"latex": r"\sum \frac{1}{" + sp.latex(n) + r"^{" + sp.latex(p) + r"}} \text{ is } " + conclusion},
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="calculus", action="classify_and_test")
def classify_and_test(
    expr: Union[str, sp.Expr],
    var: str = "n",
) -> MathObject:
    """自动分类并依次尝试各级数审敛法。

    判别顺序：
    1. p-级数 → p_series_test
    2. 交错级数 → leibniz_test
    3. 正项且单调递减 → integral_test
    4. limit_comparison_test
    5. direct_comparison_test
    6. 否则 inconclusive

    Args:
        expr: 通项表达式。
        var: 求和指标变量名。

    Returns:
        MathObject，result 为最终收敛性结论。
    """
    try:
        n = sp.Symbol(var)
        ex = _to_sympy(expr)

        steps = [f"通项: a_{{{var}}} = {ex}", "自动分类流程:"]

        # 1. p-级数
        if _is_p_series(ex, n):
            steps.append("→ 匹配 p-级数，调用 p_series_test")
            r = p_series_test(ex, var)
            steps.extend(r.steps)
            return MathObject(result=r.result, steps=steps, meaning=r.meaning, data=r.data)

        # 2. 交错级数
        if _is_alternating(ex, n):
            steps.append("→ 检测到交错级数，调用 leibniz_test")
            r = leibniz_test(ex, var)
            steps.extend(r.steps)
            return MathObject(result=r.result, steps=steps, meaning=r.meaning, data=r.data)

        # 3. 正项且单调递减 → 积分判别法
        a_n = sp.simplify(sp.Abs(ex))
        deriv = sp.simplify(sp.diff(a_n, n))
        deriv_limit = sp.limit(deriv, n, sp.oo)
        if deriv_limit <= 0:
            steps.append("→ 正项且单调递减，调用 integral_test")
            r = integral_test(ex, var)
            steps.extend(r.steps)
            return MathObject(result=r.result, steps=steps, meaning=r.meaning, data=r.data)

        # 4. 极限比较判别法
        steps.append("→ 调用 limit_comparison_test")
        r = limit_comparison_test(ex, var)
        if r.result != "inconclusive":
            steps.extend(r.steps)
            return MathObject(result=r.result, steps=steps, meaning=r.meaning, data=r.data)

        # 5. 直接比较判别法
        steps.append("→ 调用 direct_comparison_test")
        r = direct_comparison_test(ex, var)
        if r.result != "inconclusive":
            steps.extend(r.steps)
            return MathObject(result=r.result, steps=steps, meaning=r.meaning, data=r.data)

        # 6. 否则
        steps.append("→ 所有方法均无法判定")
        return MathObject(
            result="inconclusive",
            steps=steps,
            meaning=f"级数 ∑{ex} 无法自动判定",
            data={"latex": r"\text{inconclusive}"},
        )
    except Exception as e:
        return MathObject(error=str(e))


def _is_p_series(expr: sp.Expr, n: sp.Symbol) -> bool:
    """判断是否为 p-级数 1/n**p 形式。"""
    simplified = sp.simplify(expr)
    if simplified.is_Pow and simplified.base == n and simplified.exp.is_number:
        return True
    if simplified.is_Pow and simplified.base == 1 / n:
        return True
    if simplified == 1 / n:
        return True
    return False


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 series 模块。"""
    print("=== series self_test ===")

    # 1. series_sum: 1/n^2 → π^2/6
    r = series_sum("1/n**2", "n", 1, "oo")
    assert r.ok, r.error
    assert "pi" in r.result.lower() or "π" in r.result.lower() or "1.64" in r.result
    print(f"  series_sum(1/n^2): {r.result}")
    print("  series_sum: pass")

    # 2. series_convergence: 1/n^2 → 收敛
    r = series_convergence("1/n**2", "n")
    assert r.ok
    print(f"  series_convergence(1/n^2): {r.result}")

    # 3. power_series: sin(x) → x - x^3/6 + ...
    r = power_series("sin(x)", "x", 0, 5)
    assert r.ok
    assert "x" in r.result
    print(f"  power_series(sin(x)): {r.result}")

    # 4. power_series_radius: 1/n! → ∞
    r = power_series_radius("1/factorial(n)")
    assert r.ok
    assert "oo" in r.result.lower() or r.result == "oo"
    print(f"  power_series_radius(1/n!): {r.result}")

    # ========== 新增审敛法自测 ==========

    # 5. leibniz_test: (-1)^n/n → convergent
    r = leibniz_test("(-1)**n/n", "n")
    assert r.ok, r.error
    assert r.result == "convergent", f"expected convergent, got {r.result}"
    print(f"  leibniz_test((-1)^n/n): {r.result}")
    print("  leibniz_test: pass")

    # 6. integral_test: 1/n^2 → convergent
    r = integral_test("1/n**2", "n")
    assert r.ok, r.error
    assert r.result == "convergent", f"expected convergent, got {r.result}"
    print(f"  integral_test(1/n^2): {r.result}")
    print("  integral_test: pass")

    # 7. p_series_test: 1/n^2 → convergent (p=2>1)
    r = p_series_test("1/n**2", "n")
    assert r.ok, r.error
    assert r.result == "convergent", f"expected convergent, got {r.result}"
    print(f"  p_series_test(1/n^2): {r.result}")
    print("  p_series_test: pass")

    # 8. limit_comparison_test: 1/(n^2+1) → convergent
    r = limit_comparison_test("1/(n**2+1)", "n")
    assert r.ok, r.error
    assert r.result == "convergent", f"expected convergent, got {r.result}"
    print(f"  limit_comparison_test(1/(n^2+1)): {r.result}")
    print("  limit_comparison_test: pass")

    # 9. classify_and_test: (-1)^n/n → convergent (via leibniz)
    r = classify_and_test("(-1)**n/n", "n")
    assert r.ok, r.error
    assert r.result == "convergent", f"expected convergent, got {r.result}"
    print(f"  classify_and_test((-1)^n/n): {r.result}")

    # 10. classify_and_test: 1/n → divergent (via p_series_test)
    r = classify_and_test("1/n", "n")
    assert r.ok, r.error
    assert r.result == "divergent", f"expected divergent, got {r.result}"
    print(f"  classify_and_test(1/n): {r.result}")
    print("  classify_and_test: pass")

    print("=== series self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
