"""平面解析几何 — 坐标系、直线方程、圆的方程。

依赖: math, sympy
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register

# 点类型: (x, y)
Point = Tuple[Union[int, float], Union[int, float]]


# ===================================================================
# 坐标系
# ===================================================================


@register(module="algebra", action="distance")
def distance(p1: Point, p2: Point) -> MathObject:
    """计算平面上两点间距离。

    Args:
        p1: 第一个点 (x1, y1)。
        p2: 第二个点 (x2, y2)。

    Returns:
        MathObject，result 为距离值。
    """
    try:
        x1, y1 = p1
        x2, y2 = p2
        dx = x2 - x1
        dy = y2 - y1
        dist = math.sqrt(dx * dx + dy * dy)
        return MathObject(
            result=round(dist, 10),
            steps=[
                f"点 P₁({x1}, {y1})，P₂({x2}, {y2})",
                f"Δx = {dx}，Δy = {dy}",
                f"距离 d = √(Δx² + Δy²) = √({dx}² + {dy}²) = √({dx*dx + dy*dy})",
                f"    = {dist}",
            ],
            meaning=f"P₁({x1},{y1}) 与 P₂({x2},{y2}) 的距离为 {dist:.4f}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="midpoint")
def midpoint(p1: Point, p2: Point) -> MathObject:
    """计算两点中点。

    Args:
        p1: 第一个点 (x1, y1)。
        p2: 第二个点 (x2, y2)。

    Returns:
        MathObject，result 为中点坐标 (x, y)。
    """
    try:
        x1, y1 = p1
        x2, y2 = p2
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        return MathObject(
            result=(mx, my),
            steps=[
                f"P₁({x1}, {y1})，P₂({x2}, {y2})",
                f"中点公式: M = ((x₁+x₂)/2, (y₁+y₂)/2)",
                f"        = (({x1}+{x2})/2, ({y1}+{y2})/2)",
                f"        = ({mx}, {my})",
            ],
            meaning=f"P₁ 与 P₂ 的中点为 M({mx}, {my})",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 直线方程
# ===================================================================


@register(module="algebra", action="line_from_points")
def line_from_points(p1: Point, p2: Point) -> MathObject:
    """两点式求直线方程。

    Args:
        p1: 第一个点 (x1, y1)。
        p2: 第二个点 (x2, y2)。

    Returns:
        MathObject，result 包含各形式方程。
    """
    try:
        x1, y1 = p1
        x2, y2 = p2
        if x1 == x2:
            # 垂直于 x 轴
            k = float("inf")
            equation = f"x = {x1}"
            point_slope = "不存在（垂直于x轴）"
            slope_intercept = "不存在（垂直于x轴）"
            general = f"x - {x1} = 0  或  x = {x1}"
        else:
            k = (y2 - y1) / (x2 - x1)
            b = y1 - k * x1
            # 点斜式
            if b >= 0:
                point_slope = f"y - {y1} = {k}(x - {x1})"
                slope_intercept = f"y = {k}x + {b}"
            else:
                point_slope = f"y - {y1} = {k}(x - {x1})"
                slope_intercept = f"y = {k}x - {abs(b)}"
            # 一般式
            equation = slope_intercept
            general = f"{k}x - y + {b} = 0" if b >= 0 else f"{k}x - y - {abs(b)} = 0"

        return MathObject(
            result={
                "two_point": f"(y - {y1})/(x - {x1}) = ({y2} - {y1})/({x2} - {x1})",
                "point_slope": point_slope,
                "slope_intercept": slope_intercept,
                "general": general,
                "slope": k,
            },
            steps=[
                f"已知两点: P₁({x1}, {y1})，P₂({x2}, {y2})",
                f"斜率 k = (y₂ - y₁)/(x₂ - x₁) = ({y2}-{y1})/({x2}-{x1}) = {k}",
                f"两点式: (y - {y1})/(x - {x1}) = {k}",
                f"点斜式: {point_slope}",
                f"斜截式: {slope_intercept}",
                f"一般式: {general}",
            ],
            meaning=f"过 P₁({x1},{y1}) 和 P₂({x2},{y2}) 的直线斜率为 {k}，方程为 {slope_intercept}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="line_from_slope_intercept")
def line_from_slope_intercept(
    k: Union[int, float], b: Union[int, float]
) -> MathObject:
    """斜截式 y = kx + b。

    Args:
        k: 斜率。
        b: y轴截距。

    Returns:
        MathObject，result 为各形式方程。
    """
    try:
        if b >= 0:
            slope_intercept = f"y = {k}x + {b}"
        else:
            slope_intercept = f"y = {k}x - {abs(b)}"
        
        general = f"{k}x - y + {b} = 0" if b >= 0 else f"{k}x - y - {abs(b)} = 0"
        
        # 两点: 取 x=0,y=b; x=1,y=k+b
        p1 = (0, b)
        p2 = (1, k + b)

        return MathObject(
            result={
                "slope_intercept": slope_intercept,
                "general": general,
                "points": [p1, p2],
                "slope": k,
                "y_intercept": b,
            },
            steps=[
                f"斜截式: {slope_intercept}",
                f"斜率 k = {k}，y轴截距 b = {b}",
                f"一般式: {general}",
                f"过点 (0, {b}) 和 (1, {k+b})",
            ],
            meaning=f"直线 {slope_intercept}，过 (0,{b})，斜率 {k}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="line_from_point_slope")
def line_from_point_slope(
    p: Point, k: Union[int, float]
) -> MathObject:
    """点斜式 y - y₀ = k(x - x₀)。

    Args:
        p: 已知点 (x₀, y₀)。
        k: 斜率。

    Returns:
        MathObject，result 为各形式方程。
    """
    try:
        x0, y0 = p
        b = y0 - k * x0
        
        if b >= 0:
            pos = f"+ {b}"
        else:
            pos = f"- {abs(b)}"

        point_slope = f"y - {y0} = {k}(x - {x0})"
        slope_intercept = f"y = {k}x {pos}"
        general = f"{k}x - y {pos} = 0"

        return MathObject(
            result={
                "point_slope": point_slope,
                "slope_intercept": slope_intercept,
                "general": general,
                "slope": k,
                "point": p,
            },
            steps=[
                f"已知点: P({x0}, {y0})，斜率 k = {k}",
                f"点斜式: {point_slope}",
                f"展开: y - {y0} = {k}x - {k*x0}",
                f"斜截式: {slope_intercept}",
                f"一般式: {general}",
            ],
            meaning=f"过点 ({x0},{y0})，斜率 {k} 的直线: {slope_intercept}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="line_from_intercepts")
def line_from_intercepts(
    a: Union[int, float], b: Union[int, float]
) -> MathObject:
    """截距式 x/a + y/b = 1。

    Args:
        a: x轴截距。
        b: y轴截距。

    Returns:
        MathObject，result 为各形式方程。
    """
    try:
        if a == 0 or b == 0:
            return MathObject(error="截距不能为零")
        k = -b / a
        intercept_form = f"x/{a} + y/{b} = 1"
        slope_intercept = f"y = {k}x + {b}" if b >= 0 else f"y = {k}x - {abs(b)}"
        general = f"({b})x + ({a})y - {a*b} = 0"

        return MathObject(
            result={
                "intercept_form": intercept_form,
                "slope_intercept": slope_intercept,
                "general": general,
                "x_intercept": a,
                "y_intercept": b,
                "slope": k,
            },
            steps=[
                f"截距式: {intercept_form}",
                f"x轴截距 = {a}，y轴截距 = {b}",
                f"斜率 k = -b/a = {k}",
                f"斜截式: {slope_intercept}",
            ],
            meaning=f"直线 {intercept_form}，过 ({a},0) 和 (0,{b})，斜率 {k}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="line_general")
def line_general(
    A: Union[int, float], B: Union[int, float], C: Union[int, float]
) -> MathObject:
    """一般式 Ax + By + C = 0 的分析。

    Args:
        A: x 系数。
        B: y 系数。
        C: 常数项。

    Returns:
        MathObject，result 为转换为其他形式的分析。
    """
    try:
        if A == 0 and B == 0:
            return MathObject(error="A 和 B 不能同时为 0")

        general = f"{A}x + {B}y + {C} = 0"
        if B != 0:
            k = -A / B
            b = -C / B
            slope_intercept = f"y = {k}x + {b}" if b >= 0 else f"y = {k}x - {abs(b)}"
        else:
            k = float("inf")
            b = None
            slope_intercept = "x = " + str(round(-C / A, 4))

        # 截距
        x_intercept = -C / A if A != 0 else None
        y_intercept = -C / B if B != 0 else None

        return MathObject(
            result={
                "general": general,
                "slope": k,
                "slope_intercept": slope_intercept,
                "x_intercept": x_intercept,
                "y_intercept": y_intercept,
            },
            steps=[
                f"一般式: {general}",
                f"斜率 k = -A/B = {-A}/{B} = {k}" if B != 0 else "垂直于 x 轴（B=0），斜率不存在",
                f"斜截式: {slope_intercept}",
                f"x轴截距: {x_intercept}" if x_intercept is not None else "无x轴截距（平行于x轴）",
                f"y轴截距: {y_intercept}" if y_intercept is not None else "无y轴截距（平行于y轴）",
            ],
            meaning=f"直线 {general}，{'斜率 ' + str(k) if B != 0 else '垂直于x轴'}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 圆的方程
# ===================================================================


@register(module="algebra", action="circle_standard")
def circle_standard(
    center: Point, r: Union[int, float]
) -> MathObject:
    """圆的标准方程 (x - h)² + (y - k)² = r²。

    Args:
        center: 圆心 (h, k)。
        r: 半径。

    Returns:
        MathObject，result 包含标准方程和各形式。
    """
    try:
        if r <= 0:
            return MathObject(error="半径必须大于 0")
        h, k = center
        standard = f"(x - {h})² + (y - {k})² = {r}²"
        # 一般式展开
        D = -2 * h
        E = -2 * k
        F = h * h + k * k - r * r
        general = f"x² + y² + {D}x + {E}y + {F} = 0"

        return MathObject(
            result={
                "standard": standard,
                "general": general,
                "center": center,
                "radius": r,
                "diameter": 2 * r,
                "circumference": 2 * math.pi * r,
                "area": math.pi * r * r,
            },
            steps=[
                f"圆心: C({h}, {k})，半径 r = {r}",
                f"标准方程: {standard}",
                f"展开: (x² - {2*h}x + {h}²) + (y² - {2*k}y + {k}²) = {r}²",
                f"一般式: {general}",
                f"周长: 2πr = {2*math.pi*r:.4f}",
                f"面积: πr² = {math.pi*r*r:.4f}",
            ],
            meaning=f"圆心 C({h},{k})，半径 {r} 的圆",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="algebra", action="circle_general")
def circle_general(
    D: Union[int, float], E: Union[int, float], F: Union[int, float]
) -> MathObject:
    """圆的一般方程 x² + y² + Dx + Ey + F = 0 → 标准方程转换。

    配方得: (x + D/2)² + (y + E/2)² = (D² + E² - 4F) / 4

    Args:
        D: x 一次项系数。
        E: y 一次项系数。
        F: 常数项。

    Returns:
        MathObject，result 为圆心和半径分析。
    """
    try:
        h = -D / 2
        k = -E / 2
        r2 = (D * D + E * E - 4 * F) / 4

        if r2 < 0:
            return MathObject(
                result="表示一个虚圆（半径的平方为负数，无实数解）",
                steps=[
                    f"一般式: x² + y² + {D}x + {E}y + {F} = 0",
                    f"配方: (x + {D}/2)² + (y + {E}/2)² = {r2}",
                    f"r² = {r2} < 0 → 无实数圆",
                ],
                meaning="一般方程表示虚圆，不是实数曲线",
            )

        r = math.sqrt(r2)
        standard = f"(x + {D}/2)² + (y + {E}/2)² = {r}²"

        return MathObject(
            result={
                "center": (h, k),
                "radius": r,
                "r_squared": r2,
                "standard": standard,
                "general": f"x² + y² + {D}x + {E}y + {F} = 0",
            },
            steps=[
                f"一般式: x² + y² + {D}x + {E}y + {F} = 0",
                f"配方 x 项: x² + {D}x = (x + {D}/2)² - {D*D/4}",
                f"配方 y 项: y² + {E}y = (y + {E}/2)² - {E*E/4}",
                f"代入: (x + {D}/2)² + (y + {E}/2)² = {D*D/4} + {E*E/4} - {F} = {r2}",
                f"圆心: ({h}, {k})",
                f"半径: r = √({r2}) = {r}",
                f"标准方程: {standard}",
            ],
            meaning=f"圆心 ({h},{k})，半径 {r} 的圆: {standard}",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ===================================================================
# 自测
# ===================================================================


def self_test() -> None:
    """自测 analytic_geometry 模块。"""
    import sys

    def _print(*args, **kwargs):
        """GBK 安全打印 — 将不可编码字符替换为 ? 避免 crash。"""
        try:
            print(*args, **kwargs)
        except UnicodeEncodeError:
            safe_args = [
                str(a).encode(sys.stdout.encoding or 'gbk', errors='replace').decode(
                    sys.stdout.encoding or 'gbk')
                if isinstance(a, str) else a
                for a in args
            ]
            print(*safe_args, **kwargs)

    _print("=== analytic_geometry self_test ===")

    # 1. distance
    r = distance((0, 0), (3, 4))
    assert r.ok and r.result == 5.0
    _print(f"  distance((0,0),(3,4)): {r.result}")

    # 2. midpoint
    r = midpoint((0, 0), (4, 6))
    assert r.ok and r.result == (2.0, 3.0)
    _print(f"  midpoint((0,0),(4,6)): {r.result}")

    # 3. line_from_points
    r = line_from_points((0, 0), (1, 1))
    assert r.ok and r.result["slope"] == 1.0
    _print(f"  line_from_points((0,0),(1,1)): {r.result['slope_intercept']}")

    # 4. line_from_slope_intercept
    r = line_from_slope_intercept(2, 3)
    assert r.ok
    _print(f"  line_from_slope_intercept(2,3): {r.result['slope_intercept']}")

    # 5. line_from_point_slope
    r = line_from_point_slope((1, 2), 3)
    assert r.ok
    _print(f"  line_from_point_slope: {r.result['slope_intercept']}")

    # 6. circle_standard
    r = circle_standard((0, 0), 5)
    assert r.ok and r.result["radius"] == 5
    _print(f"  circle_standard: {r.result['standard']}")

    # 7. circle_general
    r = circle_general(-4, -6, 4)
    assert r.ok
    _print(f"  circle_general: center={r.result['center']}, r={r.result['radius']}")

    _print("=== analytic_geometry self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
