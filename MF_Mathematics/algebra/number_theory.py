"""数与运算 — 自然数/整数/有理数/实数运算律、绝对值、比例与百分比、科学记数法。

依赖: sympy, math
"""

from __future__ import annotations

import math
from typing import Any, Optional, Tuple, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register

# ---------------------------------------------------------------------------
# 运算律
# ---------------------------------------------------------------------------


@register(module="algebra", action="commutative_law")
def commutative_law(a: Union[int, float], b: Union[int, float], op: str = "+") -> MathObject:
    """验证交换律：a op b == b op a。

    Args:
        a: 第一个操作数。
        b: 第二个操作数。
        op: 运算符，支持 '+' 或 '*'。

    Returns:
        MathObject，result 为 (left, right, is_commutative)。
    """
    try:
        if op not in ("+", "*"):
            return MathObject(error=f"不支持的运算符 '{op}'，仅支持 '+' 和 '*'")
        if op == "+":
            left, right = a + b, b + a
        else:
            left, right = a * b, b * a
        is_comm = abs(left - right) < 1e-12
        return MathObject(
            result=(left, right, is_comm),
            steps=[
                f"计算左式: {a} {op} {b} = {left}",
                f"计算右式: {b} {op} {a} = {right}",
                f"{'满足' if is_comm else '不满足'}交换律",
            ],
            meaning=f"交换律：a {op} b = b {op} a",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="associative_law")
def associative_law(
    a: Union[int, float], b: Union[int, float], c: Union[int, float], op: str = "+"
) -> MathObject:
    """验证结合律：(a op b) op c == a op (b op c)。

    Args:
        a: 第一个操作数。
        b: 第二个操作数。
        c: 第三个操作数。
        op: 运算符，支持 '+' 或 '*'。

    Returns:
        MathObject，result 为 (left, right, is_associative)。
    """
    try:
        if op not in ("+", "*"):
            return MathObject(error=f"不支持的运算符 '{op}'，仅支持 '+' 和 '*'")
        if op == "+":
            left, right = (a + b) + c, a + (b + c)
        else:
            left, right = (a * b) * c, a * (b * c)
        is_assoc = abs(left - right) < 1e-12
        return MathObject(
            result=(left, right, is_assoc),
            steps=[
                f"计算左式: ({a} {op} {b}) {op} {c} = {left}",
                f"计算右式: {a} {op} ({b} {op} {c}) = {right}",
                f"{'满足' if is_assoc else '不满足'}结合律",
            ],
            meaning=f"结合律：(a {op} b) {op} c = a {op} (b {op} c)",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="distributive_law")
def distributive_law(
    a: Union[int, float], b: Union[int, float], c: Union[int, float]
) -> MathObject:
    """验证分配律：a * (b + c) == a * b + a * c。

    Args:
        a: 乘数。
        b: 第一个加数。
        c: 第二个加数。

    Returns:
        MathObject，result 为 (left, right, is_distributive)。
    """
    try:
        left = a * (b + c)
        right = a * b + a * c
        is_dist = abs(left - right) < 1e-12
        return MathObject(
            result=(left, right, is_dist),
            steps=[
                f"计算左式: {a} * ({b} + {c}) = {left}",
                f"计算右式: {a}*{b} + {a}*{c} = {right}",
                f"{'满足' if is_dist else '不满足'}分配律",
            ],
            meaning="分配律：a * (b + c) = a * b + a * c",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ---------------------------------------------------------------------------
# 绝对值
# ---------------------------------------------------------------------------


@register(module="algebra", action="abs_value")
def abs_value(x: Union[int, float, complex]) -> MathObject:
    """计算绝对值并描述几何意义。

    Args:
        x: 输入数值（支持复数）。

    Returns:
        MathObject，result 为绝对值，meaning 含几何解释。
    """
    try:
        val = abs(x)
        if isinstance(x, complex):
            meaning = f"复数 {x} 的模长 = √(a²+b²)，对应复平面上点到原点的距离"
            steps = [f"|{x}| = √({x.real}² + {x.imag}²) = {val}"]
        elif x >= 0:
            meaning = f"|{x}| = {val}，非负数的绝对值等于其自身"
            steps = [f"|{x}| = {val}"]
        else:
            meaning = f"|{x}| = {val}，负数绝对值等于其相反数，几何意义为数轴上到原点的距离"
            steps = [f"|{x}| = {val}"]
        return MathObject(result=val, steps=steps, meaning=meaning)
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="distance_on_number_line")
def distance_on_number_line(a: Union[int, float], b: Union[int, float]) -> MathObject:
    """数轴上两点间的距离。

    Args:
        a: 点 a 的坐标。
        b: 点 b 的坐标。

    Returns:
        MathObject，result 为距离值。
    """
    try:
        dist = abs(a - b)
        return MathObject(
            result=dist,
            steps=[
                f"点 A = {a}，点 B = {b}",
                f"距离 = |{a} - {b}| = |{a - b}| = {dist}",
            ],
            meaning=f"数轴上点 {a} 与点 {b} 之间的距离为 {dist}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ---------------------------------------------------------------------------
# 比例与百分比
# ---------------------------------------------------------------------------


@register(module="algebra", action="ratio")
def ratio(a: Union[int, float], b: Union[int, float]) -> MathObject:
    """化简比例 a:b。

    Args:
        a: 前项。
        b: 后项。

    Returns:
        MathObject，result 为 (simplified_a, simplified_b)。
    """
    try:
        if b == 0:
            return MathObject(error="分母不能为零")
        from fractions import Fraction
        # 使用 Fraction 将 a/b 化为最简分数
        if isinstance(a, float) or isinstance(b, float):
            frac = Fraction(str(a)).limit_denominator() / Fraction(str(b)).limit_denominator()
        else:
            frac = Fraction(int(a), int(b))
        num = frac.numerator
        den = frac.denominator
        return MathObject(
            result=(num, den),
            steps=[
                f"原始比例: {a} : {b}",
                f"化为分数: {a}/{b}",
                f"化简结果: {num} : {den}",
            ],
            meaning=f"{a}:{b} 的最简整数比为 {num}:{den}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="percentage")
def percentage(part: Union[int, float], total: Union[int, float]) -> MathObject:
    """计算部分占整体的百分比。

    Args:
        part: 部分量。
        total: 总量。

    Returns:
        MathObject，result 为百分比数值。
    """
    try:
        if total == 0:
            return MathObject(error="总量不能为零")
        pct = (part / total) * 100
        return MathObject(
            result=round(pct, 4),
            steps=[
                f"百分比 = ({part} / {total}) × 100%",
                f"= {pct}%",
            ],
            meaning=f"{part} 占 {total} 的 {pct:.2f}%",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="percentage_change")
def percentage_change(old: Union[int, float], new: Union[int, float]) -> MathObject:
    """计算新旧值之间的变化率。

    Args:
        old: 旧值。
        new: 新值。

    Returns:
        MathObject，result 为变化率（百分比）。
    """
    try:
        if old == 0:
            return MathObject(error="旧值不能为零，无法计算变化率")
        change = ((new - old) / abs(old)) * 100
        direction = "增加" if change > 0 else ("减少" if change < 0 else "不变")
        return MathObject(
            result=round(change, 4),
            steps=[
                f"变化率 = (({new} - {old}) / |{old}|) × 100%",
                f"= ({new - old} / {abs(old)}) × 100%",
                f"= {change:.2f}%",
            ],
            meaning=f"从 {old} 到 {new}，{direction}了 {abs(change):.2f}%",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ---------------------------------------------------------------------------
# 科学记数法与近似数
# ---------------------------------------------------------------------------


@register(module="algebra", action="to_scientific_notation")
def to_scientific_notation(x: Union[int, float]) -> MathObject:
    """将数值转为科学记数法表示。

    Args:
        x: 输入数值。

    Returns:
        MathObject，result 为 (coefficient, exponent) 元组。
    """
    try:
        if x == 0:
            return MathObject(
                result=(0.0, 0),
                steps=["0 的科学记数法表示为 0 × 10⁰"],
                meaning="零的特殊表示",
            )
        exponent = int(math.floor(math.log10(abs(x))))
        coefficient = x / (10 ** exponent)
        # 规范化：系数在 [1, 10)
        if coefficient < 1:
            coefficient *= 10
            exponent -= 1
        return MathObject(
            result=(round(coefficient, 10), exponent),
            steps=[
                f"|{x}| 的对数幂次: floor(log₁₀(|{x}|)) = {exponent}",
                f"系数: {x} / 10^{exponent} = {coefficient}",
                f"科学记数法: {coefficient} × 10^{exponent}",
            ],
            meaning=f"{x} 的科学记数法表示为 {coefficient} × 10^{exponent}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="significant_figures")
def significant_figures(x: Union[int, float], n: int) -> MathObject:
    """保留 n 位有效数字。

    Args:
        x: 输入数值。
        n: 有效数字位数。

    Returns:
        MathObject，result 为四舍五入后的数值。
    """
    try:
        if n <= 0:
            return MathObject(error="有效数字位数必须为正整数")
        if x == 0:
            return MathObject(result=0.0, steps=["0 的有效数字为 0"])
        exponent = int(math.floor(math.log10(abs(x))))
        factor = 10 ** (n - 1 - exponent)
        rounded = round(x * factor) / factor
        return MathObject(
            result=rounded,
            steps=[
                f"原始值: {x}",
                f"数量级: 10^{exponent}",
                f"保留 {n} 位有效数字: {rounded}",
            ],
            meaning=f"{x} 保留 {n} 位有效数字后为 {rounded}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------


def self_test() -> None:
    """自测 number_theory 模块。"""
    print("=== number_theory self_test ===")

    # 1. 交换律
    r = commutative_law(3, 5, "+")
    assert r.ok, r.error
    assert r.result[2] is True
    print("  commutative_law(+): pass")

    r = commutative_law(3, 5, "*")
    assert r.ok and r.result[2] is True
    print("  commutative_law(*): pass")

    # 2. 结合律
    r = associative_law(2, 3, 4, "+")
    assert r.ok and r.result[2] is True
    print("  associative_law(+): pass")

    # 3. 分配律
    r = distributive_law(2, 3, 4)
    assert r.ok and r.result[2] is True
    print("  distributive_law: pass")

    # 4. 绝对值
    r = abs_value(-5)
    assert r.ok and r.result == 5
    print("  abs_value: pass")

    # 5. 距离
    r = distance_on_number_line(3, 8)
    assert r.ok and r.result == 5
    print("  distance_on_number_line: pass")

    # 6. 百分比
    r = percentage(25, 200)
    assert r.ok and r.result == 12.5
    print("  percentage: pass")

    # 7. 变化率
    r = percentage_change(100, 120)
    assert r.ok and r.result == 20.0
    print("  percentage_change: pass")

    # 8. 科学记数法
    r = to_scientific_notation(12345)
    assert r.ok and r.result == (1.2345, 4)
    print("  to_scientific_notation: pass")

    # 9. 有效数字
    r = significant_figures(3.14159, 3)
    assert r.ok and r.result == 3.14
    print("  significant_figures: pass")

    print("=== number_theory self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
