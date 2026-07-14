# -*- coding: utf-8 -*-
"""坐标系绘制 — 贯穿全场景的网格/刻度线 + 固定像素字体。"""

from __future__ import annotations

import json, math, os
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsLineItem, QGraphicsTextItem


# ── Config loader ──────────────────────────────────────────

def _load_axes_config() -> dict:
    """从 config.json 读取坐标轴配置，失败时返回默认值。"""
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        p = os.path.join(root, "config.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f).get("plot", {}).get("axes", {})
    except Exception:
        pass
    return {}

_AX = _load_axes_config()

# ── Constants (config-driven with fallbacks) ────────────────
AXIS_COLOR    = QColor(_AX.get("axis_color", "#000000"))
GRID_COLOR    = QColor(_AX.get("grid_color", "#e8ecf0"))
TICK_COLOR    = QColor(_AX.get("tick_color", "#94a3b8"))
MINOR_COLOR   = QColor(_AX.get("minor_color", "#d0d5dc"))
EDGE_COLOR    = QColor(_AX.get("edge_color", "#b0b8c0"))
TEXT_COLOR    = QColor(_AX.get("text_color", "#475569"))
LABEL_FONT    = QFont(_AX.get("label_font", "Segoe UI"), _AX.get("label_font_size", 9))

TICK_PX       = _AX.get("tick_px", 8)
MINOR_PX      = _AX.get("minor_px", 4)
LABEL_OFF_PX  = _AX.get("label_offset_px", 8)
MINORS_PER    = _AX.get("minors_per", 4)

_NICE_TABLE = (
    0.0001, 0.0002, 0.0005,
    0.001, 0.002, 0.005,
    0.01, 0.02, 0.05,
    0.1, 0.2, 0.5,
    1, 2, 4, 5,
    10, 20, 40, 50,
    100, 200, 400, 500,
    1000, 2000, 4000, 5000,
    10000, 20000, 40000, 50000,
    100000, 200000, 400000, 500000,
    1000000, 2000000, 4000000, 5000000, 10000000,
)

_GROUP_ID = "__axes_grid_group__"

# 固定场景跨度，与 PlotCanvas._SCENE_RANGE 保持一致（避免循环导入）
_FULL_SPAN = 1_000_000


# ═══════════════════════════════════════════════════════════════
#  Public
# ═══════════════════════════════════════════════════════════════

def draw_axes(scene, vr: QRectF, view_transform=None) -> None:
    """绘制/更新坐标系到专用 QGraphicsItemGroup。"""

    px_to_scene = _px_scale(view_transform)
    view_scale  = _view_scale(view_transform)

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
    while max(x1 - x0, y1 - y0) / step > 25:
        step *= 2.0
    ox = math.floor(x0 / step) * step
    oy = math.floor(y0 / step) * step

    # 固定场景跨度 — 网格/刻度线始终覆盖全场景，消除平移裁剪
    span = _FULL_SPAN

    tick_scene   = TICK_PX * px_to_scene
    label_off_sc = LABEL_OFF_PX * px_to_scene

    # ── Pens ──
    gp = QPen(GRID_COLOR, 0); gp.setStyle(Qt.PenStyle.DotLine)
    ap = QPen(AXIS_COLOR, 0)
    tp = QPen(TICK_COLOR, 0)
    mp = QPen(MINOR_COLOR, 0)

    # ═══════════════════════════════════════════════════════
    #  网格 — 贯穿全场景 (-span .. +span)
    # ═══════════════════════════════════════════════════════
    xv = ox
    while xv <= x1:
        _add(group, _line(xv, -span, xv, span, gp), scene)
        xv += step
    yv = oy
    while yv <= y1:
        _add(group, _line(-span, yv, span, yv, gp), scene)
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

    minor_half = MINOR_PX * px_to_scene / 2  # 分度线半长（场景单位）

    # ═══════════════════════════════════════════════════════
    #  X 轴刻度 — 刻度线贯穿 Y 全范围，分度线为短线
    # ═══════════════════════════════════════════════════════
    xv = ox
    while xv <= x1:
        _add(group, _line(xv, -span, xv, span, tp), scene)
        _add(group, _mk_label(_fmt(xv), xv - label_off_sc * 2,
                              -label_off_sc - tick_scene, view_scale), scene)
        for j in range(1, MINORS_PER + 1):
            mx = xv + j * step / (MINORS_PER + 1)
            _add(group, _line(mx, -minor_half, mx, minor_half, mp), scene)
        xv += step

    # ═══════════════════════════════════════════════════════
    #  Y 轴刻度 — 刻度线贯穿 X 全范围，分度线为短线
    # ═══════════════════════════════════════════════════════
    yv = oy
    while yv <= y1:
        _add(group, _line(-span, yv, span, yv, tp), scene)
        _add(group, _mk_label(_fmt(yv), -tick_scene - label_off_sc * 3,
                              yv - label_off_sc / 2, view_scale), scene)
        for j in range(1, MINORS_PER + 1):
            my = yv + j * step / (MINORS_PER + 1)
            _add(group, _line(-minor_half, my, minor_half, my, mp), scene)
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
                  yv - label_off_sc / 2, view_scale, EDGE_COLOR), scene)
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
    """将 1 像素映射为场景坐标长度（支持缩放+旋转，点差法计算）。"""
    if view_transform is None:
        return 0.05
    try:
        p1 = view_transform.map(QPointF(0, 0))
        p2 = view_transform.map(QPointF(1, 0))
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        s = math.sqrt(dx * dx + dy * dy)  # 1 scene unit → s pixels
        return 1.0 / s if s > 1e-9 else 0.05
    except Exception:
        return 0.05


def _view_scale(view_transform) -> float:
    """返回视图当前缩放因子（点差法，支持非均匀缩放，用于字体补偿）。"""
    if view_transform is None:
        return 1.0
    try:
        p1 = view_transform.map(QPointF(0, 0))
        p2 = view_transform.map(QPointF(1, 0))
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        return math.sqrt(dx * dx + dy * dy) or 1.0
    except Exception:
        return 1.0


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
    """格式化刻度数值：极端值用 3 位有效数字的科学计数法，常规值用 6 位。"""
    if not math.isfinite(v):
        return "∞" if v > 0 else "-∞" if v < 0 else "NaN"
    if abs(v) < 1e-12:
        return "0"
    av = abs(v)
    # 科学计数法: |v| ≥ 1e5 或 0 < |v| < 0.001
    if av >= 1e5 or (0 < av < 0.001):
        e = int(math.floor(math.log10(av) + 1e-12))
        coeff = v / (10 ** e)
        # 保留 3 位有效数字，避免尾随零
        return f"{coeff:.3g}e{e}"
    # 常规小数，最多 6 位有效数字
    s = f"{v:.6g}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s.startswith("-."):
        s = "-0" + s[1:]
    if s.startswith("."):
        s = "0" + s
    return s
