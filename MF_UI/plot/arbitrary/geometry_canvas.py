# -*- coding: utf-8 -*-
"""GeometryCanvas — 交互式几何作图画布。

基于 matplotlib FigureCanvasQTAgg，支持：
  - 平面直角坐标系（网格 + 轴 + 刻度标签）
  - 鼠标点击/拖拽构造几何图形
  - 实时预览（虚线 + 半透明）
  - 图形选中、拖拽移动
  - 滚轮缩放
"""

from __future__ import annotations

import math
import numpy as np
from enum import Enum
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from MF_UI.plot import mpl_setup  # noqa — 中文字体 + 后端初始化
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle as MplCircle, Ellipse as MplEllipse
from matplotlib.patches import Rectangle as MplRectangle, Polygon as MplPolygon
from matplotlib.patches import FancyArrow
import matplotlib.lines as mlines

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


class _State(Enum):
    IDLE = "idle"
    AWAIT_SECOND = "await_second"   # 线段/直线/向量：已有第一点
    DRAG_RADIUS = "drag_radius"     # 圆：已有圆心，拖拽中
    AWAIT_H_RAD = "await_h_rad"     # 椭圆：已有中心
    AWAIT_V_RAD = "await_v_rad"     # 椭圆：已有中心 + 水平半轴
    AWAIT_CORNER = "await_corner"   # 矩形：已有第一角点
    BUILD_POLY = "build_poly"       # 多边形：累积顶点中
    DRAGGING = "dragging"           # 选择/移动：拖拽中


# ═══════════════════════════════════════════════════════════════
#  工具提示文本
# ═══════════════════════════════════════════════════════════════

_TOOL_HINTS: dict[Tool, str] = {
    Tool.SELECT:   "选择/移动 — 点击图形选中，拖拽移动",
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
#  GeometryCanvas
# ═══════════════════════════════════════════════════════════════

class GeometryCanvas(QWidget):
    """交互式几何作图画布。

    信号:
        status_message(str)         — 状态/坐标显示
        shape_created(GeometricShape) — 图形已创建
        shape_selected(int | None)  — 选中图形 ID（None = 取消选中）
        shape_modified()            — 图形被修改（移动/删除/属性变更）
    """

    status_message = Signal(str)
    shape_created = Signal(object)
    shape_selected = Signal(object)      # int | None
    shape_modified = Signal()

    # ── 颜色常量 ──────────────────────────────────────────
    AXIS_COLOR  = "#334155"
    GRID_COLOR  = "#dee2e6"
    GRID_MAJOR  = "#c0c7cf"
    BG_COLOR    = "#f8fafc"
    PREVIEW_COLOR = "#6366f1"
    HIGHLIGHT_COLOR = "#3b82f6"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # ── 状态 ──
        self._tool = Tool.SELECT
        self._state = _State.IDLE
        self._grid_snap = True
        self._shapes: list[GeometricShape] = []
        self._selected_id: int | None = None

        # 临时数据（构建中）
        self._temp_pts: list[tuple[float, float]] = []
        self._cursor_pt: tuple[float, float] = (0.0, 0.0)
        self._drag_origin: tuple[float, float] | None = None
        self._drag_shape_id: int | None = None

        # ── 视图 ──
        self._view_xlim = (-10.0, 10.0)
        self._view_ylim = (-10.0, 10.0)

        # ── Matplotlib 初始化 ──
        self._fig = Figure(facecolor=self.BG_COLOR)
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor(self.BG_COLOR)
        self._canvas = FigureCanvasQTAgg(self._fig)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._canvas)

        self._setup_axes()
        self._connect_events()
        self._draw_all()

    # ── 初始化 ──────────────────────────────────────────────

    def _setup_axes(self) -> None:
        """设置坐标轴初始状态。"""
        ax = self._ax
        ax.set_xlim(*self._view_xlim)
        ax.set_ylim(*self._view_ylim)
        ax.set_aspect("equal")
        # 隐藏默认轴框/刻度标签（手绘网格 + 标签）
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    def _connect_events(self) -> None:
        """连接 matplotlib 鼠标事件。"""
        cid = self._canvas.mpl_connect
        cid("button_press_event", self._on_press)
        cid("button_release_event", self._on_release)
        cid("motion_notify_event", self._on_move)
        cid("scroll_event", self._on_scroll)

    # ═══════════════════════════════════════════════════════════
    #  渲染
    # ═══════════════════════════════════════════════════════════

    def _draw_all(self) -> None:
        """完整重绘：网格 → 轴 → 图形 → 预览 → 选中高亮。"""
        ax = self._ax
        # 保存视图状态
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        ax.clear()
        self._setup_axes()

        self._draw_grid()
        self._draw_axes()
        self._draw_shapes()
        self._draw_preview()

        # 恢复视图
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

        self._canvas.draw_idle()

    def _draw_grid(self) -> None:
        """绘制网格线 + 刻度标签。"""
        ax = self._ax
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        rng = max(x1 - x0, y1 - y0)

        # 自适应步长
        step = _nice_step(rng)
        minor_divisions = 5
        minor_step = step / minor_divisions

        # 主网格
        for v in _grid_values(x0, x1, step):
            ax.axvline(v, color=self.GRID_MAJOR, linewidth=0.6, linestyle="-", zorder=0)
        for v in _grid_values(y0, y1, step):
            ax.axhline(v, color=self.GRID_MAJOR, linewidth=0.6, linestyle="-", zorder=0)

        # 次网格
        for v in _grid_values(x0, x1, minor_step):
            ax.axvline(v, color=self.GRID_COLOR, linewidth=0.3, linestyle="-", zorder=0)
        for v in _grid_values(y0, y1, minor_step):
            ax.axhline(v, color=self.GRID_COLOR, linewidth=0.3, linestyle="-", zorder=0)

        # 刻度标签（使用 text 而非 tick labels，避免 matplotlib 默认行为）
        for v in _grid_values(x0, x1, step):
            if abs(v) < 1e-10: continue
            ax.text(v, 0, _fmt_tick(v, step), fontsize=7, color="#64748b",
                    ha="center", va="top", zorder=5)
        for v in _grid_values(y0, y1, step):
            if abs(v) < 1e-10: continue
            ax.text(0, v, _fmt_tick(v, step), fontsize=7, color="#64748b",
                    ha="right", va="center", zorder=5)

    def _draw_axes(self) -> None:
        """绘制坐标轴。"""
        ax = self._ax
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        ax.axhline(0, color=self.AXIS_COLOR, linewidth=1.5, zorder=4)
        ax.axvline(0, color=self.AXIS_COLOR, linewidth=1.5, zorder=4)
        # 原点 "O"
        ax.text(0, 0, "O", fontsize=9, fontweight="bold", color=self.AXIS_COLOR,
                ha="right", va="top", zorder=6)
        # 轴标签
        ax.text(x1, 0, "x", fontsize=9, fontweight="bold", color=self.AXIS_COLOR,
                ha="left", va="bottom", zorder=6)
        ax.text(0, y1, "y", fontsize=9, fontweight="bold", color=self.AXIS_COLOR,
                ha="left", va="bottom", zorder=6)
        # 箭头
        arr = (x1 - x0) * 0.02
        ax.plot(x1 - arr, 0, marker=(3, 0, 0), markersize=6, color=self.AXIS_COLOR, zorder=5)
        ax.plot(0, y1 - arr, marker=(3, 0, 90), markersize=6, color=self.AXIS_COLOR, zorder=5)

    def _draw_shapes(self) -> None:
        """渲染所有已完成的图形。"""
        for s in self._shapes:
            if not s.visible:
                continue
            is_sel = (s.id == self._selected_id)
            lw = s.line_width + 1.5 if is_sel else s.line_width
            color = self.HIGHLIGHT_COLOR if is_sel else s.color
            alpha = 1.0
            zorder = 10 if is_sel else 5

            try:
                if s.shape_type == ShapeType.POINT:
                    x, y = s.data
                    self._ax.plot(x, y, "o", color=color, markersize=8, zorder=zorder,
                                  markeredgecolor="white", markeredgewidth=0.5)
                    self._ax.text(x + 0.3, y + 0.3, s.label, fontsize=9,
                                  color="#1e293b", zorder=zorder + 1)

                elif s.shape_type == ShapeType.SEGMENT:
                    (x1, y1), (x2, y2) = s.data
                    self._ax.plot([x1, x2], [y1, y2], "-", color=color,
                                  linewidth=lw, zorder=zorder)
                    # 端点
                    self._ax.plot([x1, x2], [y1, y2], "o", color=color,
                                  markersize=4, zorder=zorder + 1)
                    mid = ((x1 + x2) / 2, (y1 + y2) / 2)
                    dist = math.hypot(x2 - x1, y2 - y1)
                    self._ax.text(mid[0] + 0.2, mid[1] + 0.2,
                                  f"{s.label}\n({dist:.2f})", fontsize=8,
                                  color="#475569", zorder=zorder + 1)

                elif s.shape_type == ShapeType.LINE:
                    (x1, y1), (x2, y2) = s.data
                    _draw_infinite_line(self._ax, x1, y1, x2, y2, color, lw, zorder)
                    # 控制点
                    self._ax.plot([x1, x2], [y1, y2], "s", color=color,
                                  markersize=4, zorder=zorder + 1)

                elif s.shape_type == ShapeType.VECTOR:
                    (x1, y1), (x2, y2) = s.data
                    dx, dy = x2 - x1, y2 - y1
                    self._ax.arrow(x1, y1, dx, dy, head_width=0.3, head_length=0.4,
                                   fc=color, ec=color, linewidth=lw,
                                   length_includes_head=True, zorder=zorder)
                    lbl = s.label or f"({dx:.2f}, {dy:.2f})"
                    self._ax.text((x1 + x2) / 2 + 0.3, (y1 + y2) / 2 + 0.3,
                                  lbl, fontsize=8, color=color, zorder=zorder + 1)

                elif s.shape_type == ShapeType.CIRCLE:
                    (cx, cy), r = s.data
                    circ = MplCircle((cx, cy), r, fill=False, edgecolor=color,
                                     linewidth=lw, zorder=zorder)
                    self._ax.add_patch(circ)
                    self._ax.plot(cx, cy, "o", color=color, markersize=5, zorder=zorder + 1)
                    self._ax.text(cx + 0.3, cy + 0.3, f"{s.label}", fontsize=8,
                                  color="#475569", zorder=zorder + 1)

                elif s.shape_type == ShapeType.ELLIPSE:
                    (cx, cy), rx, ry = s.data
                    ell = MplEllipse((cx, cy), 2 * rx, 2 * ry, fill=False,
                                     edgecolor=color, linewidth=lw, zorder=zorder)
                    self._ax.add_patch(ell)
                    self._ax.plot(cx, cy, "o", color=color, markersize=5, zorder=zorder + 1)
                    self._ax.text(cx + 0.3, cy + 0.3, s.label, fontsize=8,
                                  color="#475569", zorder=zorder + 1)

                elif s.shape_type == ShapeType.RECTANGLE:
                    (x1, y1), (x2, y2) = s.data
                    x, w = min(x1, x2), abs(x2 - x1)
                    y, h = min(y1, y2), abs(y2 - y1)
                    rect = MplRectangle((x, y), w, h, fill=False, edgecolor=color,
                                        linewidth=lw, zorder=zorder)
                    self._ax.add_patch(rect)
                    # 对角点
                    for px, py in [(x1, y1), (x2, y2)]:
                        self._ax.plot(px, py, "o", color=color, markersize=4, zorder=zorder + 1)

                elif s.shape_type == ShapeType.POLYGON:
                    pts = s.data
                    if len(pts) >= 3:
                        poly = MplPolygon(pts, fill=False, edgecolor=color,
                                          linewidth=lw, zorder=zorder)
                        self._ax.add_patch(poly)
                        for px, py in pts:
                            self._ax.plot(px, py, "o", color=color, markersize=4, zorder=zorder + 1)

                # 选中高亮效果
                if is_sel:
                    self._draw_highlight(s)

            except Exception:
                pass

    def _draw_highlight(self, s: GeometricShape) -> None:
        """绘制选中高亮。"""
        pass  # is_sel 已经通过颜色/线宽体现，无需额外高亮

    def _draw_preview(self) -> None:
        """绘制构建中的预览图形。"""
        cx, cy = self._cursor_pt
        ls = (0, (4, 4))  # 虚线
        preview_color = self.PREVIEW_COLOR
        alpha = 0.6

        if self._state == _State.IDLE:
            return

        try:
            if self._state == _State.AWAIT_SECOND:
                if self._temp_pts:
                    px, py = self._temp_pts[0]
                    self._ax.plot([px, cx], [py, cy], "--", color=preview_color,
                                  linewidth=1.2, alpha=alpha, zorder=3)

            elif self._state == _State.DRAG_RADIUS:
                if self._temp_pts:
                    px, py = self._temp_pts[0]
                    r = math.hypot(cx - px, cy - py)
                    circ = MplCircle((px, py), r, fill=False, linestyle="--",
                                     edgecolor=preview_color, linewidth=1.2, alpha=alpha, zorder=3)
                    self._ax.add_patch(circ)
                    self._ax.plot([px, cx], [py, cy], ":", color=preview_color,
                                  linewidth=0.8, alpha=alpha, zorder=3)

            elif self._state == _State.AWAIT_H_RAD:
                if self._temp_pts:
                    px, py = self._temp_pts[0]
                    self._ax.plot([px, cx], [py, py], "--", color=preview_color,
                                  linewidth=1.2, alpha=alpha, zorder=3)

            elif self._state == _State.AWAIT_V_RAD:
                if len(self._temp_pts) >= 2:
                    px, py = self._temp_pts[0]
                    hx, _ = self._temp_pts[1]
                    rx = abs(hx - px)
                    ry = abs(cy - py)
                    if rx > 0.01 and ry > 0.01:
                        ell = MplEllipse((px, py), 2 * rx, 2 * ry, fill=False,
                                         linestyle="--", edgecolor=preview_color,
                                         linewidth=1.2, alpha=alpha, zorder=3)
                        self._ax.add_patch(ell)

            elif self._state == _State.AWAIT_CORNER:
                if self._temp_pts:
                    px, py = self._temp_pts[0]
                    x = min(px, cx); w = abs(cx - px)
                    y = min(py, cy); h = abs(cy - py)
                    rect = MplRectangle((x, y), w, h, fill=False, linestyle="--",
                                        edgecolor=preview_color, linewidth=1.2,
                                        alpha=alpha, zorder=3)
                    self._ax.add_patch(rect)

            elif self._state == _State.BUILD_POLY:
                if self._temp_pts:
                    pts = self._temp_pts + [(cx, cy)]
                    if len(pts) >= 2:
                        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                        self._ax.plot(xs, ys, "--", color=preview_color,
                                      linewidth=1.2, alpha=alpha, zorder=3)
                        for px, py in self._temp_pts:
                            self._ax.plot(px, py, "s", color=preview_color,
                                          markersize=5, zorder=4)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    #  鼠标事件
    # ═══════════════════════════════════════════════════════════

    def _snap(self, v: float, step: float) -> float:
        """网格吸附。"""
        if not self._grid_snap:
            return v
        return round(v / step) * step

    def _grid_step(self) -> float:
        """当前缩放级别下的吸附步长。"""
        x0, x1 = self._ax.get_xlim()
        y0, y1 = self._ax.get_ylim()
        rng = max(x1 - x0, y1 - y0)
        return _nice_step(rng) / 5

    def _pick_shape(self, mx: float, my: float) -> int | None:
        """找到点击位置最近的可命中图形 ID。

        优先选点，其次按距离排序。"""
        step = self._grid_step()
        threshold = step * 0.8
        best = None; best_dist = float("inf")

        for s in self._shapes:
            if not s.visible:
                continue
            if hit_test(s, mx, my, threshold):
                # 点到图形距离估算
                dist = self._shape_approx_dist(s, mx, my)
                if dist < best_dist:
                    best_dist = dist
                    best = s.id
        return best

    def _shape_approx_dist(self, s: GeometricShape, mx: float, my: float) -> float:
        """点到图形的近似距离（用于最近选择）。"""
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
            pts = _shape_edges(s)
            return min(_pt_seg_dist(mx, my, *e[0], *e[1]) for e in pts) if pts else float("inf")
        return float("inf")

    def _hit_threshold(self) -> float:
        """碰撞检测阈值（数据坐标）。"""
        step = self._grid_step()
        return step * 0.8

    # ── Press ─────────────────────────────────────────────

    def _on_press(self, event) -> None:
        if event.xdata is None or event.ydata is None:
            return

        mx, my = float(event.xdata), float(event.ydata)
        step = self._grid_step()
        mx = self._snap(mx, step)
        my = self._snap(my, step)

        # 中键 = 停止任何构建，进入平移模式
        if event.button == 2:  # MouseButton.MIDDLE
            self._cancel_construction()
            return

        # 右键 = 取消 / 闭合多边形
        if event.button == 3:  # MouseButton.RIGHT
            if self._state == _State.BUILD_POLY and len(self._temp_pts) >= 3:
                self._commit_polygon()
                return
            self._cancel_construction()
            self._draw_all()
            return

        # 左键
        if event.button != 1:  # MouseButton.LEFT
            return

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

    # ── Release ───────────────────────────────────────────

    def _on_release(self, event) -> None:
        if event.xdata is None or event.ydata is None:
            return

        mx, my = float(event.xdata), float(event.ydata)
        step = self._grid_step()
        mx = self._snap(mx, step)
        my = self._snap(my, step)

        if self._state == _State.DRAG_RADIUS:
            # 圆：释放鼠标 → 确定半径
            self._commit_circle(mx, my)
        elif self._state == _State.DRAGGING:
            # 拖拽结束
            self._commit_drag()
        # 中键释放
        elif event.button == 2:
            return

    # ── Move ──────────────────────────────────────────────

    def _on_move(self, event) -> None:
        if event.xdata is None or event.ydata is None:
            return

        mx, my = float(event.xdata), float(event.ydata)
        step = self._grid_step()
        mx_s = self._snap(mx, step)
        my_s = self._snap(my, step)
        self._cursor_pt = (mx_s, my_s)

        # 状态栏坐标
        self.status_message.emit(f"({mx_s:.2f}, {my_s:.2f})")
        if self._grid_snap:
            self.status_message.emit(f"({mx_s:.2f}, {my_s:.2f})  吸附: {step:.2f}")

        # 拖拽移动图形
        if self._state == _State.DRAGGING and self._drag_origin and self._drag_shape_id is not None:
            ox, oy = self._drag_origin
            dx, dy = mx_s - ox, my_s - oy
            for s in self._shapes:
                if s.id == self._drag_shape_id:
                    translate_shape_inplace(s, dx, dy)
                    break
            self._drag_origin = (mx_s, my_s)
            self._draw_all()
            return

        # 构建预览
        if self._state != _State.IDLE:
            self._draw_all()

    # ── Scroll ────────────────────────────────────────────

    def _on_scroll(self, event) -> None:
        """滚轮缩放。"""
        if event.xdata is None or event.ydata is None:
            return
        factor = 0.85 if event.button == "up" else 1.15
        self._zoom_at(event.xdata, event.ydata, factor)

    def _zoom_at(self, cx: float, cy: float, factor: float) -> None:
        """以 (cx, cy) 为中心缩放。"""
        ax = self._ax
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()

        # 限制缩放范围
        new_w = (x1 - x0) * factor
        new_h = (y1 - y0) * factor
        if new_w > 10000 or new_h > 10000:
            return
        if new_w < 0.01 or new_h < 0.01:
            return

        rx = (cx - x0) / (x1 - x0)
        ry = (cy - y0) / (y1 - y0)
        ax.set_xlim(cx - new_w * rx, cx + new_w * (1 - rx))
        ax.set_ylim(cy - new_h * ry, cy + new_h * (1 - ry))
        self._draw_all()

    # ═══════════════════════════════════════════════════════════
    #  工具分发
    # ═══════════════════════════════════════════════════════════

    def _handle_select_press(self, mx: float, my: float) -> None:
        """选择工具：点击选中 / 拖拽移动。"""
        sid = self._pick_shape(mx, my)
        if sid is not None:
            self._set_selection(sid)
            self._state = _State.DRAGGING
            self._drag_origin = (mx, my)
            self._drag_shape_id = sid
        else:
            self._set_selection(None)
            self._state = _State.IDLE
        self._draw_all()

    def _handle_point_press(self, mx: float, my: float) -> None:
        """点工具：即时创建。"""
        s = create_shape(ShapeType.POINT, (mx, my))
        self._shapes.append(s)
        self.shape_created.emit(s)
        self.shape_modified.emit()
        self._draw_all()

    def _handle_two_point_press(self, mx: float, my: float) -> None:
        """线段/向量/直线：两次点击。"""
        if self._state == _State.IDLE:
            self._state = _State.AWAIT_SECOND
            self._temp_pts = [(mx, my)]
            self._draw_all()
        elif self._state == _State.AWAIT_SECOND:
            self._commit_two_point(mx, my)

    def _handle_circle_press(self, mx: float, my: float) -> None:
        """圆：点击放置圆心。"""
        if self._state == _State.IDLE:
            self._state = _State.DRAG_RADIUS
            self._temp_pts = [(mx, my)]
            self._draw_all()

    def _handle_ellipse_press(self, mx: float, my: float) -> None:
        """椭圆：三击（中心 → 水平半径 → 垂直半径）。"""
        if self._state == _State.IDLE:
            self._state = _State.AWAIT_H_RAD
            self._temp_pts = [(mx, my)]
            self._draw_all()
        elif self._state == _State.AWAIT_H_RAD:
            self._state = _State.AWAIT_V_RAD
            self._temp_pts.append((mx, my))
            self._draw_all()
        elif self._state == _State.AWAIT_V_RAD:
            self._commit_ellipse(mx, my)

    def _handle_rect_press(self, mx: float, my: float) -> None:
        """矩形：两次点击对角。"""
        if self._state == _State.IDLE:
            self._state = _State.AWAIT_CORNER
            self._temp_pts = [(mx, my)]
            self._draw_all()
        elif self._state == _State.AWAIT_CORNER:
            self._commit_rect(mx, my)

    def _handle_poly_press(self, mx: float, my: float) -> None:
        """多边形：累积顶点。双击闭合在 _on_press 中检测。"""
        if self._state != _State.BUILD_POLY:
            self._state = _State.BUILD_POLY
            self._temp_pts = [(mx, my)]
        else:
            # 检测双击（同一位置附近 = 闭合意图）
            if self._temp_pts and _dist(mx, my, *self._temp_pts[0]) < self._grid_step() * 0.5 \
               and len(self._temp_pts) >= 3:
                self._commit_polygon()
            else:
                self._temp_pts.append((mx, my))
        self._draw_all()

    # ═══════════════════════════════════════════════════════════
    #  提交
    # ═══════════════════════════════════════════════════════════

    def _commit_two_point(self, mx: float, my: float) -> None:
        p1 = self._temp_pts[0]
        p2 = (mx, my)
        if _dist(*p1, *p2) < 0.001:
            self._cancel_construction(); return
        st = {Tool.SEGMENT: ShapeType.SEGMENT, Tool.VECTOR: ShapeType.VECTOR,
              Tool.LINE: ShapeType.LINE}[self._tool]
        s = create_shape(st, (p1, p2))
        self._shapes.append(s)
        self.shape_created.emit(s)
        self.shape_modified.emit()
        self._cancel_construction()
        self._draw_all()

    def _commit_circle(self, mx: float, my: float) -> None:
        cx, cy = self._temp_pts[0]
        r = math.hypot(mx - cx, my - cy)
        if r < 0.01: self._cancel_construction(); return
        s = create_shape(ShapeType.CIRCLE, ((cx, cy), r))
        self._shapes.append(s)
        self.shape_created.emit(s)
        self.shape_modified.emit()
        self._cancel_construction()
        self._draw_all()

    def _commit_ellipse(self, mx: float, my: float) -> None:
        cx, cy = self._temp_pts[0]
        hx, hy = self._temp_pts[1]
        rx = abs(hx - cx)
        ry = abs(my - cy)
        if rx < 0.01 or ry < 0.01:
            self._cancel_construction(); self._draw_all(); return
        s = create_shape(ShapeType.ELLIPSE, ((cx, cy), rx, ry))
        self._shapes.append(s)
        self.shape_created.emit(s)
        self.shape_modified.emit()
        self._cancel_construction()
        self._draw_all()

    def _commit_rect(self, mx: float, my: float) -> None:
        p1 = self._temp_pts[0]
        if abs(mx - p1[0]) < 0.01 or abs(my - p1[1]) < 0.01:
            self._cancel_construction(); self._draw_all(); return
        s = create_shape(ShapeType.RECTANGLE, (p1, (mx, my)))
        self._shapes.append(s)
        self.shape_created.emit(s)
        self.shape_modified.emit()
        self._cancel_construction()
        self._draw_all()

    def _commit_polygon(self) -> None:
        if len(self._temp_pts) < 3:
            self._cancel_construction(); return
        s = create_shape(ShapeType.POLYGON, list(self._temp_pts))
        self._shapes.append(s)
        self.shape_created.emit(s)
        self.shape_modified.emit()
        self._cancel_construction()
        self._draw_all()

    def _commit_drag(self) -> None:
        """拖拽结束。"""
        if self._drag_shape_id is not None:
            self.shape_modified.emit()
        self._state = _State.IDLE
        self._drag_origin = None
        self._drag_shape_id = None
        self._draw_all()

    # ═══════════════════════════════════════════════════════════
    #  选择 + 取消
    # ═══════════════════════════════════════════════════════════

    def _set_selection(self, sid: int | None) -> None:
        self._selected_id = sid
        self.shape_selected.emit(sid)

    def _cancel_construction(self) -> None:
        self._state = _State.IDLE
        self._temp_pts.clear()
        self._drag_origin = None
        self._drag_shape_id = None

    # ═══════════════════════════════════════════════════════════
    #  公开 API
    # ═══════════════════════════════════════════════════════════

    def set_tool(self, tool: Tool) -> None:
        """切换当前工具。"""
        self._cancel_construction()
        self._tool = tool
        self._set_selection(None)
        self._draw_all()
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
        """外部设置选中。"""
        self._cancel_construction()
        self._set_selection(shape_id)
        self._draw_all()

    def get_selected(self) -> int | None:
        return self._selected_id

    def get_shapes(self) -> list[GeometricShape]:
        return list(self._shapes)

    def load_shapes(self, shapes: list[GeometricShape]) -> None:
        """替换整个图形列表（用于 undo/redo）。"""
        self._shapes = list(shapes)
        self._set_selection(None)
        self._draw_all()

    def delete_shape(self, shape_id: int) -> None:
        """删除指定图形（不 push undo，由调用方管理）。"""
        self._shapes = [s for s in self._shapes if s.id != shape_id]
        if self._selected_id == shape_id:
            self._set_selection(None)
        self._draw_all()
        self.shape_modified.emit()

    def set_shape_color(self, shape_id: int, color: str) -> None:
        for s in self._shapes:
            if s.id == shape_id:
                s.color = color
                self._draw_all()
                self.shape_modified.emit()
                return

    def set_shape_label(self, shape_id: int, label: str) -> None:
        for s in self._shapes:
            if s.id == shape_id:
                s.label = label
                self._draw_all()
                self.shape_modified.emit()
                return

    def reset_view(self) -> None:
        self._ax.set_xlim(-10, 10)
        self._ax.set_ylim(-10, 10)
        self._draw_all()

    def fit_all(self) -> None:
        """自适应显示所有图形。"""
        bounds = compute_bounds(self._shapes)
        if bounds is None:
            self.reset_view()
            return
        xmin, xmax, ymin, ymax = bounds
        pad_x = max((xmax - xmin) * 0.15, 1.0)
        pad_y = max((ymax - ymin) * 0.15, 1.0)
        self._ax.set_xlim(xmin - pad_x, xmax + pad_x)
        self._ax.set_ylim(ymin - pad_y, ymax + pad_y)
        self._draw_all()

    def cancel(self) -> None:
        """取消当前构建操作。"""
        self._cancel_construction()
        self._draw_all()


# ═══════════════════════════════════════════════════════════════
#  渲染辅助
# ═══════════════════════════════════════════════════════════════

def _draw_infinite_line(ax, x1, y1, x2, y2, color, lw, zorder):
    """绘制穿过两点并延伸到视口边界的直线。"""
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    x0, x1v = xlim; y0, y1v = ylim

    pts = []
    # 求直线与四条视口边界的交点
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) < 1e-10:
        pts = [(x1, y0), (x1, y1v)]
    elif abs(dy) < 1e-10:
        pts = [(x0, y1), (x1v, y1)]
    else:
        m = dy / dx
        # 左边界
        yl = y1 + m * (x0 - x1)
        if y0 <= yl <= y1v: pts.append((x0, yl))
        # 右边界
        yr = y1 + m * (x1v - x1)
        if y0 <= yr <= y1v: pts.append((x1v, yr))
        # 下边界
        xb = x1 + (y0 - y1) / m
        if x0 <= xb <= x1v and len(pts) < 2: pts.append((xb, y0))
        # 上边界
        xt = x1 + (y1v - y1) / m
        if x0 <= xt <= x1v and len(pts) < 2: pts.append((xt, y1v))

    if len(pts) >= 2:
        ax.plot([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]],
                "-", color=color, linewidth=lw, zorder=zorder)


def _nice_step(rng: float) -> float:
    """计算合适的网格/刻度步长。"""
    if rng <= 0:
        return 1.0
    raw = rng / 10.0
    table = (0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
             1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
    for n in table:
        if n >= raw:
            return n
    return table[-1]


def _grid_values(lo: float, hi: float, step: float) -> list[float]:
    """生成网格线位置列表。"""
    if step <= 0:
        return []
    start = math.floor(lo / step) * step
    vals = []
    v = start
    while v <= hi + step * 0.001:
        if abs(v) < step * 0.001:
            v = 0.0  # 避免浮点误差让 0 偏移
        vals.append(v)
        v += step
    return vals


def _fmt_tick(v: float, step: float) -> str:
    """格式化刻度标签。"""
    if abs(v) < 1e-12:
        return "0"
    if step >= 1:
        return f"{int(v)}"
    elif step >= 0.1:
        return f"{v:.1f}".rstrip("0").rstrip(".")
    elif step >= 0.01:
        return f"{v:.2f}".rstrip("0").rstrip(".")
    else:
        return f"{v:.3f}".rstrip("0").rstrip(".")


# ── 几何距离 ──────────────────────────────────────────────

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


def _dist(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


def _shape_edges(s: GeometricShape) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """获取图形的边列表。"""
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
