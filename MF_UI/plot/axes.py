# -*- coding: utf-8 -*-
"""坐标系绘制 — 贯穿全场景的网格/刻度线 + 固定像素字体。"""

from __future__ import annotations

import math
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsLineItem, QGraphicsTextItem


# ── Constants ──────────────────────────────────────────────
FULL_SPAN     = 10_000_000    # 网格/刻度线贯穿范围

AXIS_COLOR    = QColor("#000000")
GRID_COLOR    = QColor("#e8ecf0")
TICK_COLOR    = QColor("#94a3b8")
MINOR_COLOR   = QColor("#d0d5dc")
EDGE_COLOR    = QColor("#b0b8c0")
TEXT_COLOR    = QColor("#475569")
LABEL_FONT    = QFont("Segoe UI", 9)

TICK_PX       = 8
MINOR_PX      = 4
LABEL_OFF_PX  = 8
MINORS_PER    = 4

_NICE_TABLE = (
    0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.005,
    0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
    1, 2, 5, 10, 20, 50,
    100, 200, 500,
    1000, 2000, 5000,
    10000, 20000, 50000,
    100000, 200000, 500000,
    1000000, 2000000, 5000000, 10000000,
)

_GROUP_ID = "__axes_grid_group__"


# ═══════════════════════════════════════════════════════════════
#  Public
# ═══════════════════════════════════════════════════════════════

def draw_axes(scene, vr: QRectF, view_transform=None) -> None:
    """绘制/更新坐标系到专用 QGraphicsItemGroup。"""

    px_to_scene = _px_scale(view_transform)
    view_scale  = _view_scale(view_transform)   # ≈ zoom level

    # ── Group ──
    group = getattr(scene, _GROUP_ID, None)
    if group is None or group.scene() is not scene:
        group = QGraphicsItemGroup()
        scene.addItem(group)
        setattr(scene, _GROUP_ID, group)

    for child in list(group.childItems()):
        group.removeFromGroup(child)
        scene.removeItem(child)

    x0, x1 = vr.left(), vr.right()
    y0, y1 = vr.top(), vr.bottom()
    step = _nice_step(max(x1 - x0, y1 - y0))
    # 限制每轴最多 25 个标签（合计 ≤50），超出则步长翻倍
    while max(x1 - x0, y1 - y0) / step > 25:
        step *= 2.0
    ox = math.floor(x0 / step) * step
    oy = math.floor(y0 / step) * step

    tick_scene   = TICK_PX * px_to_scene
    label_off_sc = LABEL_OFF_PX * px_to_scene

    # ── Pens ──
    gp = QPen(GRID_COLOR, 0); gp.setStyle(Qt.PenStyle.DotLine)
    ap = QPen(AXIS_COLOR, 0)
    tp = QPen(TICK_COLOR, 0)
    mp = QPen(MINOR_COLOR, 0)

    # ═══════════════════════════════════════════════════════
    #  网格 — 贯穿全场景 (-FULL_SPAN .. +FULL_SPAN)
    # ═══════════════════════════════════════════════════════
    xv = ox
    while xv <= x1:
        _add(group, _line(xv, -FULL_SPAN, xv, FULL_SPAN, gp), scene)
        xv += step
    yv = oy
    while yv <= y1:
        _add(group, _line(-FULL_SPAN, yv, FULL_SPAN, yv, gp), scene)
        yv += step

    # ═══════════════════════════════════════════════════════
    #  主轴 — Y 贯穿，X 贯穿
    # ═══════════════════════════════════════════════════════
    x_visible = y0 <= 0 <= y1
    y_visible = x0 <= 0 <= x1
    if x_visible:
        _add(group, _line(x0, 0, x1, 0, ap), scene)
    if y_visible:
        _add(group, _line(0, y0, 0, y1, ap), scene)

    # ═══════════════════════════════════════════════════════
    #  X 轴刻度 — 刻度线/分度线贯穿 Y 全范围
    # ═══════════════════════════════════════════════════════
    xv = ox
    while xv <= x1:
        _add(group, _line(xv, -FULL_SPAN, xv, FULL_SPAN, tp), scene)
        _add(group, _mk_label(_fmt(xv), xv - label_off_sc * 2,
                              -label_off_sc - tick_scene, view_scale), scene)
        for j in range(1, MINORS_PER + 1):
            mx = xv + j * step / (MINORS_PER + 1)
            _add(group, _line(mx, -FULL_SPAN, mx, FULL_SPAN, mp), scene)
        xv += step

    # ═══════════════════════════════════════════════════════
    #  Y 轴刻度 — 刻度线/分度线贯穿 X 全范围
    # ═══════════════════════════════════════════════════════
    yv = oy
    while yv <= y1:
        _add(group, _line(-FULL_SPAN, yv, FULL_SPAN, yv, tp), scene)
        _add(group, _mk_label(_fmt(yv), -tick_scene - label_off_sc * 3,
                              yv - label_off_sc // 2, view_scale), scene)
        for j in range(1, MINORS_PER + 1):
            my = yv + j * step / (MINORS_PER + 1)
            _add(group, _line(-FULL_SPAN, my, FULL_SPAN, my, mp), scene)
        yv += step

    # ═══════════════════════════════════════════════════════
    #  边缘刻度（主轴离开视野时）
    # ═══════════════════════════════════════════════════════
    if not x_visible:
        edge_y = y0 + label_off_sc if 0 < y0 else y1 - label_off_sc
        _add(group, _line(x0, edge_y, x1, edge_y,
              QPen(EDGE_COLOR, 0, Qt.PenStyle.DashLine)), scene)
        xv = ox
        while xv <= x1:
            _add(group, _mk_label(_fmt(xv), xv - label_off_sc * 2,
                  edge_y + 4 * px_to_scene, view_scale, EDGE_COLOR), scene)
            xv += step
    if not y_visible:
        edge_x = x0 + label_off_sc if 0 < x0 else x1 - label_off_sc
        _add(group, _line(edge_x, y0, edge_x, y1,
              QPen(EDGE_COLOR, 0, Qt.PenStyle.DashLine)), scene)
        yv = oy
        while yv <= y1:
            _add(group, _mk_label(_fmt(yv), edge_x + 4 * px_to_scene,
                  yv - label_off_sc // 2, view_scale, EDGE_COLOR), scene)
            yv += step

    # ═══════════════════════════════════════════════════════
    #  轴名
    # ═══════════════════════════════════════════════════════
    _add(group, _mk_label("x", x1 - 20 * px_to_scene,
          label_off_sc, view_scale, AXIS_COLOR), scene)
    _add(group, _mk_label("y", label_off_sc,
          y1 - 20 * px_to_scene, view_scale, AXIS_COLOR), scene)


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════

def _px_scale(view_transform) -> float:
    if view_transform is None:
        return 0.05
    return abs(1.0 / view_transform.m11()) if abs(view_transform.m11()) > 1e-9 else 0.05


def _view_scale(view_transform) -> float:
    """返回视图的 X 方向缩放因子（用于字体补偿）。"""
    if view_transform is None:
        return 1.0
    return abs(view_transform.m11())


def _line(x1, y1, x2, y2, pen):
    l = QGraphicsLineItem(x1, y1, x2, y2)
    l.setPen(pen)
    return l


def _mk_label(text, x, y, view_scale=1.0, color=TEXT_COLOR):
    """文本标签 — 像素固定 9pt（反向补偿视图缩放）+ Y 翻转补偿。"""
    lbl = QGraphicsTextItem(text)
    lbl.setDefaultTextColor(color)
    lbl.setFont(LABEL_FONT)
    lbl.setPos(x, y)
    # view has scale(1,-1) → need Y flip for upright text
    # view zoom m11 → need 1/m11 to keep constant pixel size
    if view_scale and abs(view_scale - 1.0) > 0.001:
        lbl.setTransform(QTransform.fromScale(1.0 / view_scale, -1.0 / view_scale))
    else:
        lbl.setTransform(QTransform.fromScale(1, -1))
    return lbl


def _add(group, item, scene):
    scene.addItem(item)
    group.addToGroup(item)


def _nice_step(rng: float) -> float:
    if rng <= 0:
        return 1.0
    raw = rng / 15.0
    step = _NICE_TABLE[-1]
    for n in _NICE_TABLE:
        if n >= raw:
            step = n
            break
    while rng / step > 30:
        step *= 2.0
    return step


def _fmt(v: float) -> str:
    if abs(v) < 1e-12:
        return "0"
    av = abs(v)
    # 科学计数法: 大数 (≥1e5) 或极小值 (<0.001)，保留 5 位有效数字
    if av >= 1e5 or (0 < av < 0.001):
        e = int(math.floor(math.log10(av)))
        coeff = v / (10 ** e)
        return f"{coeff:.5g}e{e}"
    # 常规小数，最多 5 位有效数字
    s = f"{v:.5g}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s.startswith("-."):
        s = "-0" + s[1:]
    if s.startswith("."):
        s = "0" + s
    return s
