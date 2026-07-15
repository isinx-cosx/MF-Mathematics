# -*- coding: utf-8 -*-
"""GeometryCanvas — 交互式几何作图画布。

QGraphicsView 驱动，坐标系渲染完全复刻 PlotCanvas.drawForeground。
图形渲染为 QGraphicsItem，鼠标事件复写 QGraphicsView 回调。
"""

from __future__ import annotations

import math
from enum import Enum
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem, QGraphicsItem, QGraphicsLineItem,
    QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsScene,
    QGraphicsSimpleTextItem, QGraphicsView, QVBoxLayout, QWidget,
)

from MF_UI.plot.arbitrary.shapes import (
    ShapeType, GeometricShape, create_shape, hit_test,
    translate_shape_inplace, compute_bounds,
)


# ═══════════════════════════════════════════════════════════════
#  枚举
# ═══════════════════════════════════════════════════════════════

class Tool(Enum):
    SELECT = 0
    POINT = 1
    SEGMENT = 2
    CIRCLE = 3
    VECTOR = 4
    LINE = 5
    ELLIPSE = 6
    RECTANGLE = 7
    POLYGON = 8
    PAN = 9


class _State(Enum):
    IDLE = "idle"
    AWAIT_SECOND = "await_second"
    DRAG_RADIUS = "drag_radius"
    AWAIT_H_RAD = "await_h_rad"
    AWAIT_V_RAD = "await_v_rad"
    AWAIT_CORNER = "await_corner"
    BUILD_POLY = "build_poly"
    DRAGGING = "dragging"


_TOOL_HINTS: dict[Tool, str] = {
    Tool.SELECT:   "选择/移动 — 点击图形选中，拖拽移动",
    Tool.PAN:      "拖拽 — 按住左键拖拽平移视图",
    Tool.POINT:    "点 — 点击画布创建点",
    Tool.SEGMENT:  "线段 — 点击起点，再点击终点",
    Tool.CIRCLE:   "圆 — 点击圆心，按住拖拽确定半径",
    Tool.VECTOR:   "向量 — 点击起点，再点击终点",
    Tool.LINE:     "直线 — 点击第一点，再点击第二点（无限延伸）",
    Tool.ELLIPSE:  "椭圆 — 点击中心 → 确定水平半轴 → 确定垂直半轴",
    Tool.RECTANGLE: "矩形 — 点击第一角，再点击对角",
    Tool.POLYGON:  "多边形 — 依次点击顶点，双击或右键闭合",
}


# ═══════════════════════════════════════════════════════════════
#  坐标系渲染参数（完全复制 PlotCanvas）
# ═══════════════════════════════════════════════════════════════

SCENE_RANGE = 20_000_000
ZOOM_MIN    = 1e-6
ZOOM_MAX    = 2000
INITIAL_VIEW = QRectF(-20, -20, 40, 40)

TICK_PX   = 4
FONT_PX   = 9
AXIS_PX   = 2.0
CURVE_PX  = 2.5

AXIS_COLOR  = QColor("#334155")
GRID_COLOR  = QColor("#e8ecf0")
TICK_COLOR  = QColor("#94a3b8")
EDGE_COLOR  = QColor("#b0b8c0")
TEXT_COLOR  = QColor("#334155")
BG_COLOR    = QColor("#fafbfc")

PREVIEW_COLOR   = QColor("#6366f1")
HIGHLIGHT_COLOR = QColor("#3b82f6")

NICE_TABLE = (
    0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50,
    100, 200, 500, 1000, 2000, 5000,
    10000, 20000, 50000,
    100000, 200000, 500000,
    1000000, 2000000, 5000000, 10000000,
)


def calculate_step(rng: float) -> float:
    """自适应步长（rng / 20，向上取整到 nice 值）。"""
    if rng <= 0:
        return 1.0
    raw = rng / 20.0
    for n in NICE_TABLE:
        if n >= raw:
            return n
    return NICE_TABLE[-1]


def format_tick(v: float, step: float = 1.0) -> str:
    """刻度数值格式化。"""
    if not math.isfinite(v):
        return "∞" if v > 0 else "-∞" if v < 0 else "NaN"
    if abs(v) < 1e-12:
        return "0"
    av = abs(v)
    if av >= 1e5 or (step > 0 and step < 0.0001 and 0 < av < 0.001):
        e = int(math.floor(math.log10(av) + 1e-12))
        coeff = v / (10 ** e)
        if step >= 1:       return f"{coeff:.3g}e{e}"
        elif step >= 0.1:   return f"{coeff:.4g}e{e}"
        elif step >= 0.01:  return f"{coeff:.5g}e{e}"
        else:               return f"{coeff:.6g}e{e}"
    if step >= 1:           decimals = 0
    elif step >= 0.1:       decimals = 1
    elif step >= 0.01:      decimals = 2
    elif step >= 0.001:     decimals = 3
    elif step >= 0.0001:    decimals = 4
    else:                   decimals = 5
    s = f"{v:.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s.startswith("-."):
        s = "-0" + s[1:]
    if s.startswith("."):
        s = "0" + s
    return s


# ═══════════════════════════════════════════════════════════════
#  GeometryCanvas — QGraphicsView（与 PlotCanvas 同架构）
# ═══════════════════════════════════════════════════════════════

class GeometryCanvas(QGraphicsView):
    """交互式几何作图画布 — QGraphicsView 驱动。

    坐标系渲染 = 完全复制 PlotCanvas.drawForeground。
    图形 = QGraphicsItem。
    """

    status_message = Signal(str)
    shape_created = Signal(object)
    shape_selected = Signal(object)
    shape_modified = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # ── Scene ──
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(
            QRectF(-SCENE_RANGE, -SCENE_RANGE, SCENE_RANGE * 2, SCENE_RANGE * 2))
        self.setScene(self._scene)

        # ── View ──
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(QBrush(BG_COLOR))
        self.scale(1, -1)
        self.fitInView(INITIAL_VIEW, Qt.AspectRatioMode.KeepAspectRatio)

        # ── 状态 ──
        self._tool = Tool.SELECT
        self._state = _State.IDLE
        self._grid_snap = True
        self._shapes: list[GeometricShape] = []
        self._selected_id: int | None = None

        # 图形 → QGraphicsItem 映射
        self._shape_items: dict[int, QGraphicsItem] = {}
        # 预览 item（虚线）
        self._preview_items: list[QGraphicsItem] = []

        # 临时数据（构建中）
        self._temp_pts: list[tuple[float, float]] = []
        self._cursor_pt: tuple[float, float] = (0.0, 0.0)
        self._drag_origin: QPointF | None = None
        self._drag_shape_id: int | None = None

        self._emit_status()
        self.status_message.emit(_TOOL_HINTS[Tool.SELECT])

    # ═══════════════════════════════════════════════════════════
    #  drawForeground — 完全复制 PlotCanvas 坐标系渲染
    # ═══════════════════════════════════════════════════════════

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """坐标系渲染 — 逐行复制自 PlotCanvas.drawForeground。"""
        super().drawForeground(painter, rect)

        painter.save()
        painter.resetTransform()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        x0, x1 = vr.left(), vr.right()
        y0, y1 = vr.top(), vr.bottom()
        rng = max(x1 - x0, y1 - y0)
        if rng <= 0:
            painter.restore(); return

        step = calculate_step(rng)
        ox = self._map_x(0); oy = self._map_y(0)
        xa_ok = oy is not None and y0 <= 0 <= y1
        ya_ok = ox is not None and x0 <= 0 <= x1

        # ── 坐标轴（固定 2px 粗线）──
        vp = self.viewport().rect()
        painter.setPen(QPen(AXIS_COLOR, AXIS_PX))
        if xa_ok:
            painter.drawLine(int(vp.left()), int(oy), int(vp.right()), int(oy))
        if ya_ok:
            painter.drawLine(int(ox), int(vp.top()), int(ox), int(vp.bottom()))

        # ── 网格线 ──
        painter.setPen(QPen(GRID_COLOR, 1))
        gx = math.floor(x0 / step) * step
        while gx <= x1:
            p1 = self.mapFromScene(QPointF(gx, y0))
            p2 = self.mapFromScene(QPointF(gx, y1))
            painter.drawLine(p1, p2)
            gx += step
        gy = math.floor(y0 / step) * step
        while gy <= y1:
            p1 = self.mapFromScene(QPointF(x0, gy))
            p2 = self.mapFromScene(QPointF(x1, gy))
            painter.drawLine(p1, p2)
            gy += step

        # ── 字体 ──
        font = painter.font()
        font.setPixelSize(FONT_PX)
        painter.setFont(font)

        half = TICK_PX
        spx = self._step_px(step)

        # ── X 轴刻度 ──
        sx = math.floor(x0 / step) * step
        while sx <= x1:
            vx = self._map_x(sx)
            vy = oy if xa_ok else self._map_y(0.0)
            if vx is not None and vy is not None:
                painter.setPen(QPen(TICK_COLOR, 1))
                painter.drawLine(int(vx), int(vy - half), int(vx), int(vy + half))
                painter.setPen(QPen(TEXT_COLOR, 1))
                painter.drawText(
                    int(vx - spx * 0.4), int(vy + half + 2),
                    int(spx * 0.8), 16,
                    int(Qt.AlignHCenter | Qt.AlignTop), format_tick(sx, step),
                )
            sx += step

        # ── Y 轴刻度 ──
        sy = math.floor(y0 / step) * step
        while sy <= y1:
            vx = ox if ya_ok else self._map_x(0.0)
            vy = self._map_y(sy)
            if vx is not None and vy is not None:
                painter.setPen(QPen(TICK_COLOR, 1))
                painter.drawLine(int(vx - half), int(vy), int(vx + half), int(vy))
                painter.setPen(QPen(TEXT_COLOR, 1))
                painter.drawText(
                    int(vx - half - 4 - 40), int(vy - 8), 36, 16,
                    int(Qt.AlignRight | Qt.AlignVCenter), format_tick(sy, step),
                )
            sy += step

        # ── 边缘刻度（主轴离开视野时）──
        if not xa_ok:
            edge_y = int(vp.bottom() - 20)
            painter.setPen(QPen(EDGE_COLOR, 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(vp.left()), edge_y, int(vp.right()), edge_y)
            sx = math.floor(x0 / step) * step
            while sx <= x1:
                vx = self._map_x(sx)
                if vx is not None:
                    painter.setPen(QPen(EDGE_COLOR, 1))
                    painter.drawLine(int(vx), edge_y - half, int(vx), edge_y + half)
                    painter.setPen(QPen(EDGE_COLOR, 1))
                    painter.drawText(
                        int(vx - spx * 0.4), edge_y + half + 2,
                        int(spx * 0.8), 16,
                        int(Qt.AlignHCenter | Qt.AlignTop), format_tick(sx, step),
                    )
                sx += step

        if not ya_ok:
            edge_x = int(vp.left() + 20)
            painter.setPen(QPen(EDGE_COLOR, 1, Qt.PenStyle.DashLine))
            painter.drawLine(edge_x, int(vp.top()), edge_x, int(vp.bottom()))
            sy = math.floor(y0 / step) * step
            while sy <= y1:
                vy = self._map_y(sy)
                if vy is not None:
                    painter.setPen(QPen(EDGE_COLOR, 1))
                    painter.drawLine(edge_x - half, int(vy), edge_x + half, int(vy))
                    painter.setPen(QPen(EDGE_COLOR, 1))
                    painter.drawText(
                        edge_x + half + 2, int(vy - 8), 40, 16,
                        int(Qt.AlignLeft | Qt.AlignVCenter), format_tick(sy, step),
                    )
                sy += step

        # ── 原点 O ──
        o_x = self._map_x(0); o_y = self._map_y(0)
        if o_x is not None and o_y is not None and (x0 <= 0 <= x1) and (y0 <= 0 <= y1):
            fb = painter.font(); fb.setPixelSize(10); fb.setBold(True)
            painter.setFont(fb)
            painter.setPen(QPen(QColor("#0f172a"), 1))
            painter.drawText(int(o_x + 3), int(o_y + 1), "O")

        # ── 轴名 ──
        fs = painter.font(); fs.setPixelSize(10); fs.setBold(True)
        painter.setFont(fs)
        painter.setPen(QPen(AXIS_COLOR, 1))
        painter.drawText(vp.right() - 18,
                         int(oy + 8) if xa_ok else vp.bottom() - 14, "x")
        painter.drawText(int(ox + 5) if ya_ok else 5,
                         vp.top() + 11, "y")

        painter.restore()

    # ── 坐标映射（复制 PlotCanvas）──────────────────────────

    def _map_x(self, sx: float) -> float | None:
        pt = self.mapFromScene(QPointF(sx, 0))
        return pt.x()

    def _map_y(self, sy: float) -> float | None:
        pt = self.mapFromScene(QPointF(0, sy))
        return pt.y()

    def _step_px(self, step: float) -> float:
        return abs(self._map_x(step) - (self._map_x(0) or 0))

    # ═══════════════════════════════════════════════════════════
    #  图形渲染 — QGraphicsItem
    # ═══════════════════════════════════════════════════════════

    def _rebuild_shape_items(self) -> None:
        """从 _shapes 重建所有 QGraphicsItem。

        笔宽随视图缩放保持恒定像素（与 PlotCanvas._update_curve_pens 同理）。
        """
        for item in self._shape_items.values():
            self._scene.removeItem(item)
        self._shape_items.clear()

        vs = _view_scale(self)
        lw_scale = 1.0 / vs if vs > 0 else 1.0

        for s in self._shapes:
            if not s.visible:
                continue
            is_sel = (s.id == self._selected_id)
            # 基础笔宽 × 视图缩放 → 恒定像素
            lw = (s.line_width + 1.5 if is_sel else s.line_width) * lw_scale
            color = QColor(HIGHLIGHT_COLOR if is_sel else s.color)

            try:
                item = self._create_item(s, color, lw, lw_scale)
                if item:
                    self._scene.addItem(item)
                    self._shape_items[s.id] = item
            except Exception:
                pass

    def _create_item(self, s: GeometricShape, color: QColor,
                     lw: float, lw_scale: float) -> QGraphicsItem | None:
        """根据图形类型创建 QGraphicsItem。"""
        pen = QPen(color)
        pen.setWidthF(lw)

        if s.shape_type == ShapeType.POINT:
            x, y = s.data
            r = 4.0 * lw_scale
            item = QGraphicsEllipseItem(x - r, y - r, r * 2, r * 2)
            item.setPen(QPen(color))
            item.setBrush(QBrush(color))
            item.setZValue(10)
            # 标签（ItemIgnoresTransformations 保证恒定像素）
            label = QGraphicsSimpleTextItem(s.label)
            offset = 6 * lw_scale
            label.setPos(x + offset, y + offset)
            label.setBrush(QBrush(QColor("#1e293b")))
            font = QFont(); font.setPixelSize(10); label.setFont(font)
            label.setZValue(11)
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            label.setParentItem(item)
            item.setData(0, "point")
            return item

        elif s.shape_type == ShapeType.SEGMENT:
            (x1, y1), (x2, y2) = s.data
            item = QGraphicsLineItem(x1, y1, x2, y2)
            item.setPen(pen); item.setZValue(5)
            # 端点
            ds = 2.0 * lw_scale
            for px, py in [(x1, y1), (x2, y2)]:
                dot = QGraphicsEllipseItem(px - ds, py - ds, ds * 2, ds * 2)
                dot.setPen(QPen(color)); dot.setBrush(QBrush(color))
                dot.setZValue(6); dot.setParentItem(item)
            # 中点标签（ItemIgnoresTransformations 保证恒定像素）
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            dist = math.hypot(x2 - x1, y2 - y1)
            offset = 4 * lw_scale
            lbl = QGraphicsSimpleTextItem(f"{s.label} ({dist:.2f})")
            lbl.setPos(mid_x + offset, mid_y + offset)
            lbl.setBrush(QBrush(QColor("#475569")))
            font = QFont(); font.setPixelSize(9); lbl.setFont(font)
            lbl.setZValue(7); lbl.setParentItem(item)
            lbl.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            return item

        elif s.shape_type == ShapeType.VECTOR:
            (x1, y1), (x2, y2) = s.data
            path = QPainterPath()
            path.moveTo(x1, y1)
            path.lineTo(x2, y2)
            # 箭头（大小随视图缩放）
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length > 0.001:
                ux, uy = dx / length, dy / length
                arrow_size = 0.4 * lw_scale
                path.moveTo(x2, y2)
                path.lineTo(x2 - arrow_size * ux + arrow_size * 0.3 * uy,
                            y2 - arrow_size * uy - arrow_size * 0.3 * ux)
                path.moveTo(x2, y2)
                path.lineTo(x2 - arrow_size * ux - arrow_size * 0.3 * uy,
                            y2 - arrow_size * uy + arrow_size * 0.3 * ux)
            item = QGraphicsPathItem(path)
            item.setPen(pen); item.setZValue(5)
            offset = 4 * lw_scale
            lbl = QGraphicsSimpleTextItem(s.label or f"({dx:.2f}, {dy:.2f})")
            lbl.setPos((x1 + x2) / 2 + offset, (y1 + y2) / 2 + offset)
            lbl.setBrush(QBrush(color))
            font = QFont(); font.setPixelSize(9); lbl.setFont(font)
            lbl.setZValue(7); lbl.setParentItem(item)
            lbl.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            return item

        elif s.shape_type == ShapeType.CIRCLE:
            (cx, cy), r = s.data
            item = QGraphicsEllipseItem(cx - r, cy - r, r * 2, r * 2)
            item.setPen(pen); item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            item.setZValue(5)
            # 圆心点
            ds = 3.0 * lw_scale
            dot = QGraphicsEllipseItem(cx - ds, cy - ds, ds * 2, ds * 2)
            dot.setPen(QPen(color)); dot.setBrush(QBrush(color))
            dot.setZValue(6); dot.setParentItem(item)
            return item

        elif s.shape_type == ShapeType.LINE:
            (x1, y1), (x2, y2) = s.data
            vr = self.mapToScene(self.viewport().rect()).boundingRect()
            x0, x1v = vr.left(), vr.right()
            y0, y1v = vr.top(), vr.bottom()
            pts = _line_viewport_intersection(x1, y1, x2, y2, x0, x1v, y0, y1v)
            if len(pts) >= 2:
                item = QGraphicsLineItem(pts[0][0], pts[0][1], pts[1][0], pts[1][1])
                item.setPen(pen); item.setZValue(5)
                return item
            return None

        elif s.shape_type == ShapeType.ELLIPSE:
            (cx, cy), rx, ry = s.data
            item = QGraphicsEllipseItem(cx - rx, cy - ry, rx * 2, ry * 2)
            item.setPen(pen); item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            item.setZValue(5)
            ds = 2.0 * lw_scale
            dot = QGraphicsEllipseItem(cx - ds, cy - ds, ds * 2, ds * 2)
            dot.setPen(QPen(color)); dot.setBrush(QBrush(color))
            dot.setZValue(6); dot.setParentItem(item)
            return item

        elif s.shape_type == ShapeType.RECTANGLE:
            (x1, y1), (x2, y2) = s.data
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            item = self._scene.addRect(x, y, w, h, pen, QBrush(Qt.BrushStyle.NoBrush))
            if item:
                item.setZValue(5)
            return item

        elif s.shape_type == ShapeType.POLYGON:
            pts = s.data
            if len(pts) >= 3:
                poly = QPolygonF([QPointF(x, y) for x, y in pts])
                item = QGraphicsPolygonItem(poly)
                item.setPen(pen); item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                item.setZValue(5)
                # 顶点（大小随视图缩放）
                ds = 2.0 * lw_scale
                for px, py in pts:
                    dot = QGraphicsEllipseItem(px - ds, py - ds, ds * 2, ds * 2)
                    dot.setPen(QPen(color)); dot.setBrush(QBrush(color))
                    dot.setZValue(6); dot.setParentItem(item)
                return item
            return None

        return None

    # ── 预览 ───────────────────────────────────────────────

    def _rebuild_preview(self) -> None:
        """重建构造预览（虚线 item）。"""
        for item in self._preview_items:
            self._scene.removeItem(item)
        self._preview_items.clear()

        if self._state == _State.IDLE:
            return

        cx, cy = self._cursor_pt
        pen = QPen(PREVIEW_COLOR)
        pen.setWidthF(1.2)
        pen.setStyle(Qt.PenStyle.DashLine)

        try:
            if self._state == _State.AWAIT_SECOND and self._temp_pts:
                px, py = self._temp_pts[0]
                line = self._scene.addLine(px, py, cx, cy, pen)
                line.setZValue(3); self._preview_items.append(line)

            elif self._state == _State.DRAG_RADIUS and self._temp_pts:
                px, py = self._temp_pts[0]
                r = math.hypot(cx - px, cy - py)
                circ = self._scene.addEllipse(px - r, py - r, r * 2, r * 2, pen)
                circ.setZValue(3); self._preview_items.append(circ)
                line = self._scene.addLine(px, py, cx, cy, QPen(PREVIEW_COLOR, 0.6))
                line.setZValue(3); self._preview_items.append(line)

            elif self._state == _State.AWAIT_H_RAD and self._temp_pts:
                px, py = self._temp_pts[0]
                line = self._scene.addLine(px, py, cx, py, pen)
                line.setZValue(3); self._preview_items.append(line)

            elif self._state == _State.AWAIT_V_RAD and len(self._temp_pts) >= 2:
                px, py = self._temp_pts[0]
                hx, _ = self._temp_pts[1]
                rx = abs(hx - px); ry = abs(cy - py)
                if rx > 0.01 and ry > 0.01:
                    ell = self._scene.addEllipse(px - rx, py - ry, rx * 2, ry * 2, pen)
                    ell.setZValue(3); self._preview_items.append(ell)

            elif self._state == _State.AWAIT_CORNER and self._temp_pts:
                px, py = self._temp_pts[0]
                x = min(px, cx); w = abs(cx - px)
                y = min(py, cy); h = abs(cy - py)
                rect = self._scene.addRect(x, y, w, h, pen)
                rect.setZValue(3); self._preview_items.append(rect)

            elif self._state == _State.BUILD_POLY and self._temp_pts:
                pts = self._temp_pts + [(cx, cy)]
                if len(pts) >= 2:
                    for i in range(len(pts) - 1):
                        a, b = pts[i], pts[i + 1]
                        line = self._scene.addLine(a[0], a[1], b[0], b[1], pen)
                        line.setZValue(3); self._preview_items.append(line)
                    for px, py in self._temp_pts:
                        dot = self._scene.addEllipse(px - 3, py - 3, 6, 6,
                                                      QPen(PREVIEW_COLOR), QBrush(PREVIEW_COLOR))
                        dot.setZValue(4); self._preview_items.append(dot)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    #  鼠标事件
    # ═══════════════════════════════════════════════════════════

    def _snap(self, v: float) -> float:
        if not self._grid_snap:
            return v
        step = self._grid_step()
        return round(v / step) * step

    def _grid_step(self) -> float:
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        rng = max(vr.width(), vr.height())
        return calculate_step(rng) / 5

    def _pick_shape(self, mx: float, my: float) -> int | None:
        step = self._grid_step()
        threshold = step * 0.8
        best, best_dist = None, float("inf")
        for s in self._shapes:
            if not s.visible:
                continue
            if hit_test(s, mx, my, threshold):
                dist = _shape_approx_dist(s, mx, my)
                if dist < best_dist:
                    best_dist = dist; best = s.id
        return best

    def mousePressEvent(self, event) -> None:
        # PAN 工具 — 全部交给 QGraphicsView 内建拖拽
        if self._tool == Tool.PAN:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            e = event.__class__(event.type(), event.pos(), Qt.MouseButton.LeftButton,
                                event.buttons(), event.modifiers())
            super().mousePressEvent(e)
            return

        if event.button() == Qt.MouseButton.RightButton:
            if self._state == _State.BUILD_POLY and len(self._temp_pts) >= 3:
                self._commit_polygon()
                return
            self._cancel_construction()
            self._redraw()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        pt = self.mapToScene(event.pos())
        mx = self._snap(pt.x()); my = self._snap(pt.y())

        if self._tool == Tool.SELECT:
            self._handle_select_press(mx, my)
        elif self._tool == Tool.POINT:
            self._handle_point_press(mx, my)
        elif self._tool in (Tool.SEGMENT, Tool.VECTOR, Tool.LINE):
            self._handle_two_point_press(mx, my)
        elif self._tool == Tool.CIRCLE:
            self._handle_circle_press(mx, my)
        elif self._tool == Tool.ELLIPSE:
            self._handle_ellipse_press(mx, my)
        elif self._tool == Tool.RECTANGLE:
            self._handle_rect_press(mx, my)
        elif self._tool == Tool.POLYGON:
            self._handle_poly_press(mx, my)

    def mouseMoveEvent(self, event) -> None:
        # PAN 工具 — 全部交给 QGraphicsView（ScrollHandDrag）
        if self._tool == Tool.PAN:
            super().mouseMoveEvent(event)
            return

        pt = self.mapToScene(event.pos())
        mx = self._snap(pt.x()); my = self._snap(pt.y())
        self._cursor_pt = (mx, my)

        self.status_message.emit(f"({mx:.2f}, {my:.2f})")

        if self._state == _State.DRAGGING and self._drag_origin and self._drag_shape_id is not None:
            ox, oy = self._drag_origin.x(), self._drag_origin.y()
            dx, dy = mx - ox, my - oy
            for s in self._shapes:
                if s.id == self._drag_shape_id:
                    translate_shape_inplace(s, dx, dy)
                    break
            self._drag_origin = QPointF(mx, my)
            self._redraw()
            return

        if self._state != _State.IDLE:
            self._redraw()

    def mouseReleaseEvent(self, event) -> None:
        # PAN 工具 — 全部交给 QGraphicsView（结束 ScrollHandDrag）
        if self._tool == Tool.PAN:
            super().mouseReleaseEvent(event)
            return

        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

        pt = self.mapToScene(event.pos())
        mx = self._snap(pt.x()); my = self._snap(pt.y())

        if self._state == _State.DRAG_RADIUS:
            self._commit_circle(mx, my)
        elif self._state == _State.DRAGGING:
            self._commit_drag()

        # 复制 PlotCanvas：左键释放后立即重绘
        if event.button() == Qt.MouseButton.LeftButton:
            self._after_view_change()
            self._emit_status()

    def mouseDoubleClickEvent(self, event) -> None:
        if self._state == _State.BUILD_POLY and len(self._temp_pts) >= 3:
            self._commit_polygon()

    def wheelEvent(self, event) -> None:
        """缩放 — 完全复制 PlotCanvas.wheelEvent。"""
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        vs = _view_scale(self)
        if vs * factor < 1.0 / ZOOM_MAX or vs * factor > 1.0 / ZOOM_MIN:
            return
        self.scale(factor, factor)
        self._clamp_view()
        self._redraw()
        event.accept()

    def resizeEvent(self, event) -> None:
        """保持纵横比 — 复制 PlotCanvas.resizeEvent。"""
        super().resizeEvent(event)
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        if vr.width() > 0 and vr.height() > 0:
            self.fitInView(vr, Qt.AspectRatioMode.KeepAspectRatio)

    # ═══════════════════════════════════════════════════════════
    #  View control — 复制 PlotCanvas
    # ═══════════════════════════════════════════════════════════

    def _clamp_view(self) -> None:
        """确保视口不超出场景边界 ±SCENE_RANGE — 复制 PlotCanvas。"""
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        R = SCENE_RANGE
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        if vr.left() < -R:
            h.setValue(h.value() - int(-R - vr.left()))
        if vr.right() > R:
            h.setValue(h.value() + int(vr.right() - R))
        if vr.top() < -R:
            v.setValue(v.value() - int(-R - vr.top()))
        if vr.bottom() > R:
            v.setValue(v.value() + int(vr.bottom() - R))

    def _after_view_change(self) -> None:
        """视图变化后统一处理 — 复制 PlotCanvas（曲线 pen 适配替换为重绘）。"""
        self._clamp_view()
        self._redraw()

    # ── 缩放 API ──────────────────────────────────────────────

    def zoom_in(self) -> None:
        """放大 — 复制 PlotCanvas.zoom_in。"""
        if _view_scale(self) * 1.15 > 1.0 / ZOOM_MIN:
            return
        self.scale(1.15, 1.15)
        self._after_view_change()

    def zoom_out(self) -> None:
        """缩小 — 复制 PlotCanvas.zoom_out。"""
        if _view_scale(self) / 1.15 < 1.0 / ZOOM_MAX:
            return
        self.scale(1.0 / 1.15, 1.0 / 1.15)
        self._after_view_change()

    def reset_view(self) -> None:
        """重置视图 — 复制 PlotCanvas.reset_view。"""
        self.fitInView(INITIAL_VIEW, Qt.AspectRatioMode.KeepAspectRatio)
        self._after_view_change()
        self._emit_status()

    # ═══════════════════════════════════════════════════════════
    #  工具分发（与旧版相同逻辑）
    # ═══════════════════════════════════════════════════════════

    def _handle_select_press(self, mx: float, my: float) -> None:
        sid = self._pick_shape(mx, my)
        if sid is not None:
            self._set_selection(sid)
            self._state = _State.DRAGGING
            self._drag_origin = QPointF(mx, my)
            self._drag_shape_id = sid
        else:
            self._set_selection(None)
            self._state = _State.IDLE
        self._redraw()

    def _handle_point_press(self, mx: float, my: float) -> None:
        s = create_shape(ShapeType.POINT, (mx, my))
        self._shapes.append(s)
        self.shape_created.emit(s); self.shape_modified.emit()
        self._redraw()

    def _handle_two_point_press(self, mx: float, my: float) -> None:
        if self._state == _State.IDLE:
            self._state = _State.AWAIT_SECOND
            self._temp_pts = [(mx, my)]
            self._redraw()
        elif self._state == _State.AWAIT_SECOND:
            self._commit_two_point(mx, my)

    def _handle_circle_press(self, mx: float, my: float) -> None:
        if self._state == _State.IDLE:
            self._state = _State.DRAG_RADIUS
            self._temp_pts = [(mx, my)]
            self._redraw()

    def _handle_ellipse_press(self, mx: float, my: float) -> None:
        if self._state == _State.IDLE:
            self._state = _State.AWAIT_H_RAD
            self._temp_pts = [(mx, my)]
            self._redraw()
        elif self._state == _State.AWAIT_H_RAD:
            self._state = _State.AWAIT_V_RAD
            self._temp_pts.append((mx, my))
            self._redraw()
        elif self._state == _State.AWAIT_V_RAD:
            self._commit_ellipse(mx, my)

    def _handle_rect_press(self, mx: float, my: float) -> None:
        if self._state == _State.IDLE:
            self._state = _State.AWAIT_CORNER
            self._temp_pts = [(mx, my)]
            self._redraw()
        elif self._state == _State.AWAIT_CORNER:
            self._commit_rect(mx, my)

    def _handle_poly_press(self, mx: float, my: float) -> None:
        if self._state != _State.BUILD_POLY:
            self._state = _State.BUILD_POLY
            self._temp_pts = [(mx, my)]
        else:
            if self._temp_pts and _dist(mx, my, *self._temp_pts[0]) < self._grid_step() * 0.5 \
               and len(self._temp_pts) >= 3:
                self._commit_polygon()
            else:
                self._temp_pts.append((mx, my))
        self._redraw()

    # ── 提交 ───────────────────────────────────────────────

    def _commit_two_point(self, mx: float, my: float) -> None:
        p1 = self._temp_pts[0]; p2 = (mx, my)
        if _dist(*p1, *p2) < 0.001:
            self._cancel_construction(); return
        st = {Tool.SEGMENT: ShapeType.SEGMENT, Tool.VECTOR: ShapeType.VECTOR,
              Tool.LINE: ShapeType.LINE}[self._tool]
        s = create_shape(st, (p1, p2))
        self._shapes.append(s)
        self.shape_created.emit(s); self.shape_modified.emit()
        self._cancel_construction(); self._redraw()

    def _commit_circle(self, mx: float, my: float) -> None:
        cx, cy = self._temp_pts[0]
        r = math.hypot(mx - cx, my - cy)
        if r < 0.01: self._cancel_construction(); return
        s = create_shape(ShapeType.CIRCLE, ((cx, cy), r))
        self._shapes.append(s)
        self.shape_created.emit(s); self.shape_modified.emit()
        self._cancel_construction(); self._redraw()

    def _commit_ellipse(self, mx: float, my: float) -> None:
        cx, cy = self._temp_pts[0]
        hx, hy = self._temp_pts[1]
        rx = abs(hx - cx); ry = abs(my - cy)
        if rx < 0.01 or ry < 0.01:
            self._cancel_construction(); self._redraw(); return
        s = create_shape(ShapeType.ELLIPSE, ((cx, cy), rx, ry))
        self._shapes.append(s)
        self.shape_created.emit(s); self.shape_modified.emit()
        self._cancel_construction(); self._redraw()

    def _commit_rect(self, mx: float, my: float) -> None:
        p1 = self._temp_pts[0]
        if abs(mx - p1[0]) < 0.01 or abs(my - p1[1]) < 0.01:
            self._cancel_construction(); self._redraw(); return
        s = create_shape(ShapeType.RECTANGLE, (p1, (mx, my)))
        self._shapes.append(s)
        self.shape_created.emit(s); self.shape_modified.emit()
        self._cancel_construction(); self._redraw()

    def _commit_polygon(self) -> None:
        if len(self._temp_pts) < 3:
            self._cancel_construction(); return
        s = create_shape(ShapeType.POLYGON, list(self._temp_pts))
        self._shapes.append(s)
        self.shape_created.emit(s); self.shape_modified.emit()
        self._cancel_construction(); self._redraw()

    def _commit_drag(self) -> None:
        if self._drag_shape_id is not None:
            self.shape_modified.emit()
        self._state = _State.IDLE
        self._drag_origin = None; self._drag_shape_id = None
        self._redraw()

    # ── 选择 / 取消 ────────────────────────────────────────

    def _set_selection(self, sid: int | None) -> None:
        self._selected_id = sid
        self.shape_selected.emit(sid)

    def _cancel_construction(self) -> None:
        self._state = _State.IDLE
        self._temp_pts.clear()
        self._drag_origin = None; self._drag_shape_id = None

    # ── 重绘 ──────────────────────────────────────────────

    def _redraw(self) -> None:
        """重建所有图形 + 预览 items，然后触发 viewport 重绘。"""
        self._rebuild_shape_items()
        self._rebuild_preview()
        self._emit_status()
        self.viewport().update()

    def _emit_status(self) -> None:
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        step = calculate_step(max(vr.width(), vr.height()))
        self.status_message.emit(
            f"图形 {len(self._shape_items)}  |  步长 {step:.4g}"
        )

    # ═══════════════════════════════════════════════════════════
    #  公开 API
    # ═══════════════════════════════════════════════════════════

    def set_tool(self, tool: Tool) -> None:
        self._cancel_construction()
        self._tool = tool
        self._set_selection(None)
        # 拖拽模式：PAN 时启用 ScrollHandDrag，其余禁用
        if tool == Tool.PAN:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._redraw()
        self.status_message.emit(_TOOL_HINTS.get(tool, ""))

    def set_grid_snap(self, enabled: bool) -> None:
        self._grid_snap = enabled

    @property
    def grid_snap(self) -> bool:
        return self._grid_snap

    @property
    def current_tool(self) -> Tool:
        return self._tool

    def set_selected(self, shape_id: int | None) -> None:
        self._cancel_construction()
        self._set_selection(shape_id)
        self._redraw()

    def get_selected(self) -> int | None:
        return self._selected_id

    def get_shapes(self) -> list[GeometricShape]:
        return list(self._shapes)

    def load_shapes(self, shapes: list[GeometricShape]) -> None:
        self._shapes = list(shapes)
        self._set_selection(None)
        self._redraw()

    def delete_shape(self, shape_id: int) -> None:
        self._shapes = [s for s in self._shapes if s.id != shape_id]
        if self._selected_id == shape_id:
            self._set_selection(None)
        self._redraw()
        self.shape_modified.emit()

    def set_shape_color(self, shape_id: int, color: str) -> None:
        for s in self._shapes:
            if s.id == shape_id:
                s.color = color; self._redraw()
                self.shape_modified.emit(); return

    def set_shape_label(self, shape_id: int, label: str) -> None:
        for s in self._shapes:
            if s.id == shape_id:
                s.label = label; self._redraw()
                self.shape_modified.emit(); return

    def fit_all(self) -> None:
        bounds = compute_bounds(self._shapes)
        if bounds is None:
            self.reset_view(); return
        xmin, xmax, ymin, ymax = bounds
        pad_x = max((xmax - xmin) * 0.15, 1.0)
        pad_y = max((ymax - ymin) * 0.15, 1.0)
        self.fitInView(QRectF(xmin - pad_x, ymin - pad_y,
                               xmax - xmin + 2 * pad_x, ymax - ymin + 2 * pad_y),
                       Qt.AspectRatioMode.KeepAspectRatio)
        self._redraw()

    def cancel(self) -> None:
        self._cancel_construction()
        self._redraw()


# ═══════════════════════════════════════════════════════════════
#  辅助函数（复制 PlotCanvas）
# ═══════════════════════════════════════════════════════════════

def _view_scale(view) -> float:
    """当前视图的像素/场景单位比 — 复制 PlotCanvas。"""
    t = view.transform()
    return abs(t.m11()) if abs(t.m11()) > 1e-9 else 1.0

def _dist(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


def _pt_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _pt_line_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    return abs(dx * (y1 - py) - (x1 - px) * dy) / math.hypot(dx, dy)


def _shape_approx_dist(s: GeometricShape, mx: float, my: float) -> float:
    if s.shape_type == ShapeType.POINT:
        x, y = s.data; return math.hypot(mx - x, my - y)
    elif s.shape_type in (ShapeType.SEGMENT, ShapeType.VECTOR):
        (x1, y1), (x2, y2) = s.data
        return _pt_seg_dist(mx, my, x1, y1, x2, y2)
    elif s.shape_type == ShapeType.CIRCLE:
        (cx, cy), r = s.data
        return abs(math.hypot(mx - cx, my - cy) - r)
    elif s.shape_type == ShapeType.LINE:
        (x1, y1), (x2, y2) = s.data
        return _pt_line_dist(mx, my, x1, y1, x2, y2)
    elif s.shape_type == ShapeType.ELLIPSE:
        (cx, cy), rx, ry = s.data
        if rx < 0.01 or ry < 0.01:
            return float("inf")
        nx = (mx - cx) / rx; ny = (my - cy) / ry
        return abs(math.hypot(nx, ny) - 1.0) * (rx + ry) / 2
    elif s.shape_type in (ShapeType.RECTANGLE, ShapeType.POLYGON):
        edges = _shape_edges(s)
        return min(_pt_seg_dist(mx, my, *e[0], *e[1]) for e in edges) if edges else float("inf")
    return float("inf")


def _shape_edges(s: GeometricShape) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    if s.shape_type == ShapeType.SEGMENT:
        return [s.data]
    elif s.shape_type == ShapeType.RECTANGLE:
        (x1, y1), (x2, y2) = s.data
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        corners = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        return [(corners[i], corners[(i+1)%4]) for i in range(4)]
    elif s.shape_type == ShapeType.POLYGON:
        pts = s.data
        return [(pts[i], pts[(i+1)%len(pts)]) for i in range(len(pts))]
    return []


def _line_viewport_intersection(x1, y1, x2, y2, vx0, vx1, vy0, vy1):
    """直线与视口边界的交点。"""
    dx, dy = x2 - x1, y2 - y1
    pts = []
    if abs(dx) < 1e-10:
        pts = [(x1, vy0), (x1, vy1)]
    elif abs(dy) < 1e-10:
        pts = [(vx0, y1), (vx1, y1)]
    else:
        m = dy / dx
        yl = y1 + m * (vx0 - x1)
        if vy0 <= yl <= vy1: pts.append((vx0, yl))
        yr = y1 + m * (vx1 - x1)
        if vy0 <= yr <= vy1: pts.append((vx1, yr))
        if len(pts) < 2:
            xb = x1 + (vy0 - y1) / m
            if vx0 <= xb <= vx1: pts.append((xb, vy0))
        if len(pts) < 2:
            xt = x1 + (vy1 - y1) / m
            if vx0 <= xt <= vx1: pts.append((xt, vy1))
    return pts
