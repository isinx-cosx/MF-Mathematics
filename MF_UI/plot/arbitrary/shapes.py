# -*- coding: utf-8 -*-
"""几何图形数据模型 — 纯数据层，无 UI 依赖。

定义:
  - ShapeType 枚举（8 种图形类型）
  - GeometricShape dataclass（统一的图形容器）
  - 工厂函数 create_shape()
  - 碰撞检测 hit_test() / hit_test_*
  - 辅助函数 translate_shape() / compute_bounds()
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from enum import Enum
from itertools import count
from typing import Any

import numpy as np

# ── 全局 ID 计数器 ──────────────────────────────────────────
_id_counter = count(1)


class ShapeType(Enum):
    """几何图形类型枚举。"""
    POINT = "point"
    SEGMENT = "segment"
    CIRCLE = "circle"
    VECTOR = "vector"
    LINE = "line"
    ELLIPSE = "ellipse"
    RECTANGLE = "rectangle"
    POLYGON = "polygon"


@dataclass
class GeometricShape:
    """统一的几何图形容器。

    Attributes:
        id: 全局唯一标识
        shape_type: 图形类型
        color: 十六进制颜色字符串，如 "#e74c3c"
        line_width: 线宽，默认 1.5
        label: 显示标签，如 "A", "线段 AB", "圆 O"
        visible: 是否可见
        data: 类型相关的坐标数据
    """
    id: int
    shape_type: ShapeType
    color: str = "#3498db"
    line_width: float = 1.5
    label: str = ""
    visible: bool = True
    data: Any = None

    # ── data 格式（按 shape_type）─────────────────────────
    # POINT      → (x: float, y: float)
    # SEGMENT    → ((x1, y1), (x2, y2))
    # CIRCLE     → ((cx, cy), radius: float)
    # VECTOR     → ((x1, y1), (x2, y2))
    # LINE       → ((x1, y1), (x2, y2))  — 两点定义无限直线
    # ELLIPSE    → ((cx, cy), rx: float, ry: float)
    # RECTANGLE  → ((x1, y1), (x2, y2))  — 两对角顶点
    # POLYGON    → [(x1,y1), (x2,y2), ...]  — 有序顶点（闭合）


# ── 工厂函数 ──────────────────────────────────────────────

def create_shape(
    shape_type: ShapeType,
    data: Any,
    color: str = "#3498db",
    label: str = "",
    line_width: float = 1.5,
) -> GeometricShape:
    """创建几何图形，自动分配 ID。

    Args:
        shape_type: 图形类型枚举
        data: 类型相关坐标数据
        color: 十六进制颜色
        label: 显示标签
        line_width: 线宽

    Returns:
        GeometricShape 实例
    """
    shape_id = next(_id_counter)
    if not label:
        label = _default_label(shape_type, shape_id)
    return GeometricShape(
        id=shape_id, shape_type=shape_type,
        color=color, line_width=line_width,
        label=label, visible=True, data=data,
    )


def _default_label(st: ShapeType, sid: int) -> str:
    """生成默认标签。"""
    labels = {
        ShapeType.POINT:    lambda i: chr(64 + ((i - 1) % 26) + 1) if i <= 26 else f"P{i}",
        ShapeType.SEGMENT:  lambda i: f"线段 {i}",
        ShapeType.CIRCLE:   lambda i: f"圆 {i}",
        ShapeType.VECTOR:   lambda i: f"v{i}",
        ShapeType.LINE:     lambda i: f"直线 {i}",
        ShapeType.ELLIPSE:  lambda i: f"椭圆 {i}",
        ShapeType.RECTANGLE: lambda i: f"矩形 {i}",
        ShapeType.POLYGON:  lambda i: f"多边形 {i}",
    }
    return labels.get(st, lambda i: f"图形 {i}")(sid)


# ── 包围盒 ────────────────────────────────────────────────

def compute_bounds(shapes: list[GeometricShape]) -> tuple[float, float, float, float] | None:
    """计算所有可见图形的包围盒。

    Returns:
        (xmin, xmax, ymin, ymax) 或 None（如无可见图形）
    """
    pts: list[tuple[float, float]] = []
    for s in shapes:
        if not s.visible:
            continue
        pts.extend(_shape_points(s))
    if not pts:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys))


def _shape_points(s: GeometricShape) -> list[tuple[float, float]]:
    """提取图形的所有关键点。"""
    if s.shape_type in (ShapeType.POINT,):
        return [s.data]
    elif s.shape_type in (ShapeType.SEGMENT, ShapeType.VECTOR, ShapeType.LINE, ShapeType.RECTANGLE):
        return list(s.data)
    elif s.shape_type == ShapeType.CIRCLE:
        (cx, cy), r = s.data
        return [(cx - r, cy - r), (cx + r, cy + r)]
    elif s.shape_type == ShapeType.ELLIPSE:
        (cx, cy), rx, ry = s.data
        return [(cx - rx, cy - ry), (cx + rx, cy + ry)]
    elif s.shape_type == ShapeType.POLYGON:
        return list(s.data)
    return []


# ── 平移 ──────────────────────────────────────────────────

def translate_shape(s: GeometricShape, dx: float, dy: float) -> GeometricShape:
    """返回平移后的新图形副本。"""
    new_s = copy.deepcopy(s)
    if s.shape_type == ShapeType.POINT:
        x, y = s.data; new_s.data = (x + dx, y + dy)
    elif s.shape_type in (ShapeType.SEGMENT, ShapeType.VECTOR, ShapeType.LINE, ShapeType.RECTANGLE):
        new_s.data = tuple((x + dx, y + dy) for x, y in s.data)
    elif s.shape_type == ShapeType.CIRCLE:
        (cx, cy), r = s.data; new_s.data = ((cx + dx, cy + dy), r)
    elif s.shape_type == ShapeType.ELLIPSE:
        (cx, cy), rx, ry = s.data; new_s.data = ((cx + dx, cy + dy), rx, ry)
    elif s.shape_type == ShapeType.POLYGON:
        new_s.data = [(x + dx, y + dy) for x, y in s.data]
    return new_s


def translate_shape_inplace(s: GeometricShape, dx: float, dy: float) -> None:
    """原地平移图形（修改 data）。"""
    if s.shape_type == ShapeType.POINT:
        x, y = s.data; s.data = (x + dx, y + dy)
    elif s.shape_type in (ShapeType.SEGMENT, ShapeType.VECTOR, ShapeType.LINE, ShapeType.RECTANGLE):
        s.data = tuple((x + dx, y + dy) for x, y in s.data)
    elif s.shape_type == ShapeType.CIRCLE:
        (cx, cy), r = s.data; s.data = ((cx + dx, cy + dy), r)
    elif s.shape_type == ShapeType.ELLIPSE:
        (cx, cy), rx, ry = s.data; s.data = ((cx + dx, cy + dy), rx, ry)
    elif s.shape_type == ShapeType.POLYGON:
        s.data = [(x + dx, y + dy) for x, y in s.data]


# ── 碰撞检测 ──────────────────────────────────────────────

def hit_test(s: GeometricShape, mx: float, my: float, threshold: float) -> bool:
    """检测点 (mx, my) 是否距离图形在 threshold 范围内。"""
    if not s.visible:
        return False
    dispatcher = {
        ShapeType.POINT:    _hit_point,
        ShapeType.SEGMENT:  _hit_segment,
        ShapeType.CIRCLE:   _hit_circle,
        ShapeType.VECTOR:   _hit_segment,  # 向量同线段
        ShapeType.LINE:     _hit_line,
        ShapeType.ELLIPSE:  _hit_ellipse,
        ShapeType.RECTANGLE: _hit_rectangle,
        ShapeType.POLYGON:  _hit_polygon,
    }
    fn = dispatcher.get(s.shape_type)
    return fn(s, mx, my, threshold) if fn else False


def _dist2(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def _hit_point(s: GeometricShape, mx: float, my: float, th: float) -> bool:
    x, y = s.data
    return _dist2(mx, my, x, y) <= th


def _hit_segment(s: GeometricShape, mx: float, my: float, th: float) -> bool:
    (x1, y1), (x2, y2) = s.data
    return _point_to_segment_dist(mx, my, x1, y1, x2, y2) <= th


def _hit_circle(s: GeometricShape, mx: float, my: float, th: float) -> bool:
    (cx, cy), r = s.data
    return abs(_dist2(mx, my, cx, cy) - r) <= th


def _hit_line(s: GeometricShape, mx: float, my: float, th: float) -> bool:
    """点 → 无限直线距离。"""
    (x1, y1), (x2, y2) = s.data
    return _point_to_line_dist(mx, my, x1, y1, x2, y2) <= th


def _hit_ellipse(s: GeometricShape, mx: float, my: float, th: float) -> bool:
    """近似：检测点到椭圆曲线的距离。"""
    (cx, cy), rx, ry = s.data
    if rx < 1e-10 or ry < 1e-10:
        return False
    # 将点缩放到单位圆空间
    nx = (mx - cx) / rx
    ny = (my - cy) / ry
    dist_unit = abs(math.hypot(nx, ny) - 1.0)
    # 还原为近似真实距离
    avg_r = (rx + ry) / 2
    return dist_unit * avg_r <= th


def _hit_rectangle(s: GeometricShape, mx: float, my: float, th: float) -> bool:
    """检测点到矩形任一边的距离。"""
    (x1, y1), (x2, y2) = s.data
    xmin, xmax = min(x1, x2), max(x1, x2)
    ymin, ymax = min(y1, y2), max(y1, y2)
    corners = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
    for i in range(4):
        ax, ay = corners[i]
        bx, by = corners[(i + 1) % 4]
        if _point_to_segment_dist(mx, my, ax, ay, bx, by) <= th:
            return True
    return False


def _hit_polygon(s: GeometricShape, mx: float, my: float, th: float) -> bool:
    pts = s.data
    n = len(pts)
    if n < 3:
        return False
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if _point_to_segment_dist(mx, my, x1, y1, x2, y2) <= th:
            return True
    return False


# ── 几何距离工具 ──────────────────────────────────────────

def _point_to_segment_dist(px: float, py: float,
                           x1: float, y1: float,
                           x2: float, y2: float) -> float:
    """点到线段的最短距离。"""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _point_to_line_dist(px: float, py: float,
                        x1: float, y1: float,
                        x2: float, y2: float) -> float:
    """点到无限直线的最短距离。"""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    # 面积公式: |cross(p-p1, p2-p1)| / |p2-p1|
    return abs(dx * (y1 - py) - (x1 - px) * dy) / math.hypot(dx, dy)


# ── 自测 ──────────────────────────────────────────────────

def self_test() -> str:
    """运行 shapes.py 自测。"""
    ok = 0; fail = 0

    # 1. 工厂 + ID 递增
    p1 = create_shape(ShapeType.POINT, (1.0, 2.0), color="#ff0000")
    p2 = create_shape(ShapeType.POINT, (3.0, 4.0))
    assert p1.id != p2.id, "ID 应唯一"; ok += 1
    assert p1.shape_type == ShapeType.POINT; ok += 1
    assert p1.color == "#ff0000"; ok += 1
    assert p1.data == (1.0, 2.0); ok += 1

    # 2. 默认标签（A, B, C...）
    p_label = create_shape(ShapeType.POINT, (0, 0))
    assert p_label.label in ("A", "B", "C"), f"标签应为字母，实际: {p_label.label}"
    ok += 1

    # 3. 碰撞检测 — 点
    assert hit_test(p1, 1.01, 1.99, 0.1), "点应被命中"; ok += 1
    assert not hit_test(p1, 5.0, 5.0, 0.1), "远处不应命中"; ok += 1

    # 4. 碰撞检测 — 线段
    seg = create_shape(ShapeType.SEGMENT, ((0.0, 0.0), (10.0, 0.0)))
    assert hit_test(seg, 5.0, 0.1, 0.2), "线段中点附近"; ok += 1
    assert not hit_test(seg, 5.0, 5.0, 0.2), "远离线段"; ok += 1

    # 5. 碰撞检测 — 圆
    cir = create_shape(ShapeType.CIRCLE, ((0.0, 0.0), 5.0))
    assert hit_test(cir, 5.0, 0.0, 0.2), "圆上点"; ok += 1
    assert not hit_test(cir, 0.0, 0.0, 0.2), "圆心不应命中"; ok += 1

    # 6. 碰撞检测 — 直线
    ln = create_shape(ShapeType.LINE, ((0.0, 0.0), (10.0, 0.0)))
    assert hit_test(ln, 5.0, 0.1, 0.2), "直线上"; ok += 1

    # 7. 碰撞检测 — 椭圆
    el = create_shape(ShapeType.ELLIPSE, ((0.0, 0.0), 5.0, 3.0))
    assert hit_test(el, 5.0, 0.0, 0.5), "椭圆右顶点"; ok += 1
    assert hit_test(el, 0.0, 3.0, 0.5), "椭圆上顶点"; ok += 1

    # 8. 碰撞检测 — 矩形
    rect = create_shape(ShapeType.RECTANGLE, ((0.0, 0.0), (4.0, 3.0)))
    assert hit_test(rect, 2.0, 0.0, 0.2), "矩形底边"; ok += 1
    assert not hit_test(rect, 2.0, 1.5, 0.2), "矩形内部不应命中边"; ok += 1

    # 9. 碰撞检测 — 多边形
    poly = create_shape(ShapeType.POLYGON, [(0, 0), (3, 0), (1.5, 2.5)])
    assert hit_test(poly, 1.5, 0.0, 0.2), "多边形底边"; ok += 1

    # 10. 平移
    tp = translate_shape(p1, 10.0, -5.0)
    assert tp.data == (11.0, -3.0); ok += 1
    assert p1.data == (1.0, 2.0), "原始点不应改变"; ok += 1

    # 11. 平移 inplace
    translate_shape_inplace(p2, 1.0, 1.0)
    assert p2.data == (4.0, 5.0); ok += 1

    # 12. 包围盒
    shapes = [
        create_shape(ShapeType.POINT, (0, 0)),
        create_shape(ShapeType.POINT, (10, 10)),
    ]
    bounds = compute_bounds(shapes)
    assert bounds is not None and bounds == (0, 10, 0, 10), f"bounds={bounds}"; ok += 1

    print(f"[PASS] shapes: {ok} 通过, {fail} 失败")
    return f"{ok} pass, {fail} fail"


if __name__ == "__main__":
    self_test()
