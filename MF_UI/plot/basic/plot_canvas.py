# -*- coding: utf-8 -*-
"""PlotCanvas — drawForeground 全量刻度 + 固定像素轴 + 自适应曲线笔宽。

架构:
  场景（仅曲线，~0-8 项）:
    - 函数曲线（QGraphicsPathItem），笔宽按 view_scale 自适应

  drawForeground（每帧自动调用，固定像素）:
    - 坐标轴（2px 粗线）
    - 网格线（自适应步长）
    - 刻度线（8px）+ 刻度标签（9px）
    - 原点 O + 轴名 x / y
    - painter.resetTransform() 保证像素恒定
"""

from __future__ import annotations

import json, math, os
from typing import Any

import numpy as np
import sympy as sp
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QGraphicsPathItem, QGraphicsScene, QGraphicsView, QWidget,
)


# ═══════════════════════════════════════════════════════════════════════
#  lambdify 缓存 — 避免每次曲线重建重新编译
# ═══════════════════════════════════════════════════════════════════════
_lambdify_cache: dict[str, callable] = {}

def _cached_lambdify(var_sym, expr, modules="numpy"):
    """缓存 sp.lambdify 结果，避免重复编译。启用 CSE 减少生成代码量。"""
    key = str(expr) + str(var_sym)
    if key not in _lambdify_cache:
        _lambdify_cache[key] = sp.lambdify(var_sym, expr, modules, cse=True)
    return _lambdify_cache[key]

# ═══════════════════════════════════════════════════════════════════════
#  Config — 所有阈值从 config.json 读取，此处仅提供回退值
# ═══════════════════════════════════════════════════════════════════════

def _cfg():
    """获取 ConfigManager 或回退到直接读取 config.json。"""
    try:
        from MF_Mathematics.utils.config_manager import config
        return config
    except Exception:
        pass
    # 回退
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        p = os.path.join(root, "config.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                _fallback_data = json.load(f)
            # 构造简易访问器
            class _FB:
                def get(self, *keys, default=None):
                    d = _fallback_data
                    for k in keys:
                        if isinstance(d, dict) and k in d: d = d[k]
                        else: return default
                    return d
            return _FB()
    except Exception:
        pass
    class _Empty:
        def get(self, *keys, default=None): return default
    return _Empty()

_c = _cfg()

# ── 场景参数 ─────────────────────────────────────────────────
SCENE_RANGE  = _c.get("plot", "scene_range",  default=20_000_000)
ZOOM_MIN     = _c.get("plot", "zoom_min",     default=1e-6)
ZOOM_MAX     = _c.get("plot", "zoom_max",     default=2000)
_iv          = _c.get("plot", "initial_view", default=[-8, -6, 16, 12])
INITIAL_VIEW = QRectF(float(_iv[0]), float(_iv[1]), float(_iv[2]), float(_iv[3]))
MAX_RANGE_MSG = f"±{SCENE_RANGE:,}"

# ── 像素参数 ─────────────────────────────────────────────────
TICK_PX   = _c.get("plot", "tick_px",   default=4)
FONT_PX   = _c.get("plot", "font_px",   default=9)
AXIS_PX   = _c.get("plot", "axis_px",   default=2.0)
CURVE_PX  = _c.get("plot", "curve_px",  default=2.5)

# ── 颜色 ─────────────────────────────────────────────────────
_ax = _c.get("plot", "axes", default={})
AXIS_COLOR  = QColor(_ax.get("axis_color",  "#334155"))
GRID_COLOR  = QColor(_ax.get("grid_color",  "#e8ecf0"))
TICK_COLOR  = QColor(_ax.get("tick_color",  "#94a3b8"))
EDGE_COLOR  = QColor(_ax.get("edge_color",  "#b0b8c0"))
TEXT_COLOR  = QColor(_ax.get("text_color",  "#334155"))
BG_COLOR    = QColor(_ax.get("bg_color",     "#fafbfc"))

CURVE_COLORS = _c.get("plot", "colors", default=[
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#e84393",
])

# ── Marching Squares 查表 ──────────────────────────────────
# 边: 0=底 1=右 2=顶 3=左
_MS_EDGES: dict[int, list[tuple[int, int]]] = {
    0: [], 15: [],
    1: [(0, 3)], 2: [(0, 1)], 3: [(1, 3)], 4: [(1, 2)],
    5: [(0, 1), (2, 3)],               # 鞍点默认方案 A
    6: [(0, 2)], 7: [(2, 3)],
    8: [(2, 3)], 9: [(0, 2)],
    10: [(0, 3), (1, 2)],              # 鞍点默认方案 A
    11: [(1, 2)], 12: [(1, 3)],
    13: [(0, 1)], 14: [(0, 3)],
}
_MS_ALT: dict[int, list[tuple[int, int]]] = {  # 鞍点备选方案 B
    5: [(0, 3), (1, 2)], 10: [(0, 1), (2, 3)],
}

NICE_TABLE = (
    0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50,
    100, 200, 500, 1000, 2000, 5000,
    10000, 20000, 50000,
    100000, 200000, 500000,
    1000000, 2000000, 5000000, 10000000,
)


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════

def calculate_step(rng: float) -> float:
    if rng <= 0:
        return 1.0
    raw = rng / 20.0
    for n in NICE_TABLE:
        if n >= raw:
            return n
    return NICE_TABLE[-1]


def format_tick(v: float, step: float = 1.0) -> str:
    """刻度数值格式化。步长决定小数位数，极端值用科学计数法。"""
    if not math.isfinite(v):
        return "∞" if v > 0 else "-∞" if v < 0 else "NaN"
    if abs(v) < 1e-12:
        return "0"
    av = abs(v)

    # 科学计数法: 极大值 (≥1e5) 或步长极小时的小值
    if av >= 1e5 or (step > 0 and step < 0.0001 and 0 < av < 0.001):
        e = int(math.floor(math.log10(av) + 1e-12))
        coeff = v / (10 ** e)
        if step >= 1:       return f"{coeff:.3g}e{e}"
        elif step >= 0.1:   return f"{coeff:.4g}e{e}"
        elif step >= 0.01:  return f"{coeff:.5g}e{e}"
        else:               return f"{coeff:.6g}e{e}"

    # 步长 → 小数位数
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


def _safe_frac(a: float, b: float) -> float:
    """安全插值: a / (a - b)，用于 Marching Squares 边缘交点。"""
    denom = a - b
    if abs(denom) < 1e-15:
        return 0.5
    t = a / denom
    return max(0.0, min(1.0, t))


def _view_scale(view) -> float:
    """当前视图的像素/场景单位比。"""
    t = view.transform()
    return abs(t.m11()) if abs(t.m11()) > 1e-9 else 1.0


# ═══════════════════════════════════════════════════════════════════════
#  PlotCanvas
# ═══════════════════════════════════════════════════════════════════════

class PlotCanvas(QGraphicsView):
    """交互式 2D 绘图画布 — 场景仅含曲线，其余全量 drawForeground 绘制。"""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # ── Scene（仅曲线，无轴无网格）──
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(
            QRectF(-SCENE_RANGE, -SCENE_RANGE, SCENE_RANGE * 2, SCENE_RANGE * 2))
        self.setScene(self._scene)

        # ── View ──
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(BG_COLOR))
        self.scale(1, -1)  # Y-up

        self.fitInView(INITIAL_VIEW, Qt.AspectRatioMode.KeepAspectRatio)

        # ── 曲线 ──
        self._curves: list[dict[str, Any]] = []
        self._curve_items: list[QGraphicsPathItem] = []

        # ── 防抖定时器（避免缩放时频繁重绘隐函数）──
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(200)
        self._rebuild_timer.timeout.connect(self._do_deferred_rebuild)

        # ── 网格缓存（避免 drawForeground 每帧重绘网格/刻度）──
        self._grid_pixmap: Any = None

        # ── 曲线缓存（避免每次缩放重新 sympify + lambdify + Path）──
        self._expr_cache: dict[str, Any] = {}      # expr_str → sympy 表达式
        self._path_cache: dict[str, Any] = {}       # cache_key → QPainterPath
        self._grid_dirty = True
        self._last_view_rect: QRectF | None = None

        self._emit_status()

    # ═══════════════════════════════════════════════════════════════
    #  drawForeground — 轴 + 网格 + 刻度 + 标签（全部固定像素）
    # ═══════════════════════════════════════════════════════════════

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
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
        vp = self.viewport().rect()

        # ── 网格缓存：仅在视图变化时重建 QPixmap ──
        cache_key = (int(vp.width()), int(vp.height()), round(rng, 4),
                     round(x0, 4), round(y0, 4))
        if self._grid_dirty or self._grid_pixmap is None or \
           getattr(self, '_grid_cache_key', None) != cache_key:
            self._grid_pixmap = self._build_grid_pixmap(
                vp, x0, x1, y0, y1, step, ox, oy, xa_ok, ya_ok)
            self._grid_cache_key = cache_key
            self._grid_dirty = False

        # ── 绘制缓存网格 ──
        if self._grid_pixmap is not None:
            painter.drawPixmap(0, 0, self._grid_pixmap)

        # ── 坐标轴（在缓存之上，保证粗细恒定）──
        painter.setPen(QPen(AXIS_COLOR, AXIS_PX))
        if xa_ok:
            painter.drawLine(int(vp.left()), int(oy), int(vp.right()), int(oy))
        if ya_ok:
            painter.drawLine(int(ox), int(vp.top()), int(ox), int(vp.bottom()))

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

    def _build_grid_pixmap(self, vp, x0, x1, y0, y1, step, ox, oy,
                           xa_ok, ya_ok):
        """将网格线 + 刻度 + 标签预渲染到 QPixmap（仅在视图变化时调用）。"""
        from PySide6.QtGui import QPixmap

        pw, ph = int(vp.width()), int(vp.height())
        if pw <= 0 or ph <= 0:
            return None
        pix = QPixmap(pw, ph)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ── 网格线 ──
        p.setPen(QPen(GRID_COLOR, 1))
        gx = math.floor(x0 / step) * step
        while gx <= x1:
            pt1 = self.mapFromScene(QPointF(gx, y0))
            pt2 = self.mapFromScene(QPointF(gx, y1))
            p.drawLine(pt1, pt2)
            gx += step
        gy = math.floor(y0 / step) * step
        while gy <= y1:
            pt1 = self.mapFromScene(QPointF(x0, gy))
            pt2 = self.mapFromScene(QPointF(x1, gy))
            p.drawLine(pt1, pt2)
            gy += step

        # ── 字体 ──
        font = p.font()
        font.setPixelSize(FONT_PX)
        p.setFont(font)
        half = TICK_PX
        spx = self._step_px(step)

        # ── X 轴刻度 ──
        sx = math.floor(x0 / step) * step
        while sx <= x1:
            vx = self._map_x(sx)
            vy = oy if xa_ok else self._map_y(0.0)
            if vx is not None and vy is not None:
                p.setPen(QPen(TICK_COLOR, 1))
                p.drawLine(int(vx), int(vy - half), int(vx), int(vy + half))
                p.setPen(QPen(TEXT_COLOR, 1))
                p.drawText(
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
                p.setPen(QPen(TICK_COLOR, 1))
                p.drawLine(int(vx - half), int(vy), int(vx + half), int(vy))
                p.setPen(QPen(TEXT_COLOR, 1))
                p.drawText(
                    int(vx - half - 4 - 40), int(vy - 8), 36, 16,
                    int(Qt.AlignRight | Qt.AlignVCenter), format_tick(sy, step),
                )
            sy += step

        # ── 边缘刻度 ──
        if not xa_ok:
            edge_y = int(vp.bottom() - 20)
            p.setPen(QPen(EDGE_COLOR, 1, Qt.PenStyle.DashLine))
            p.drawLine(int(vp.left()), edge_y, int(vp.right()), edge_y)
            sx = math.floor(x0 / step) * step
            while sx <= x1:
                vx = self._map_x(sx)
                if vx is not None:
                    p.setPen(QPen(EDGE_COLOR, 1))
                    p.drawLine(int(vx), edge_y - half, int(vx), edge_y + half)
                    p.setPen(QPen(EDGE_COLOR, 1))
                    p.drawText(
                        int(vx - spx * 0.4), edge_y + half + 2,
                        int(spx * 0.8), 16,
                        int(Qt.AlignHCenter | Qt.AlignTop), format_tick(sx, step),
                    )
                sx += step

        if not ya_ok:
            edge_x = int(vp.left() + 20)
            p.setPen(QPen(EDGE_COLOR, 1, Qt.PenStyle.DashLine))
            p.drawLine(edge_x, int(vp.top()), edge_x, int(vp.bottom()))
            sy = math.floor(y0 / step) * step
            while sy <= y1:
                vy = self._map_y(sy)
                if vy is not None:
                    p.setPen(QPen(EDGE_COLOR, 1))
                    p.drawLine(edge_x - half, int(vy), edge_x + half, int(vy))
                    p.setPen(QPen(EDGE_COLOR, 1))
                    p.drawText(
                        edge_x + half + 2, int(vy - 8), 40, 16,
                        int(Qt.AlignLeft | Qt.AlignVCenter), format_tick(sy, step),
                    )
                sy += step

        p.end()
        return pix

    # ── Helpers ──────────────────────────────────────────────────

    def _map_x(self, sx: float) -> float | None:
        pt = self.mapFromScene(QPointF(sx, 0))
        return pt.x()

    def _map_y(self, sy: float) -> float | None:
        pt = self.mapFromScene(QPointF(0, sy))
        return pt.y()

    def _step_px(self, step: float) -> float:
        return abs(self._map_x(step) - (self._map_x(0) or 0))

    # ═══════════════════════════════════════════════════════════════
    #  Curve pen adaptation (constant visual width)
    # ═══════════════════════════════════════════════════════════════

    def _update_curve_pens(self) -> None:
        """按当前 view_scale 更新所有曲线笔宽，保持恒定的像素宽度。"""
        vs = _view_scale(self)
        width = CURVE_PX / vs if vs > 0 else 0
        for item in self._curve_items:
            pen = item.pen()
            pen.setWidthF(width)
            item.setPen(pen)

    # ═══════════════════════════════════════════════════════════════
    #  Aspect ratio lock — 始终等比例缩放
    # ═══════════════════════════════════════════════════════════════

    def resizeEvent(self, event) -> None:
        """窗口大小变化时保持纵横比，确保圆形始终为正圆。"""
        super().resizeEvent(event)
        self._mark_grid_dirty()
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        if vr.width() > 0 and vr.height() > 0:
            self.fitInView(vr, Qt.AspectRatioMode.KeepAspectRatio)

    # ═══════════════════════════════════════════════════════════════
    #  View control
    # ═══════════════════════════════════════════════════════════════

    def _clamp_view(self) -> None:
        """确保视口不超出场景边界 ±SCENE_RANGE。"""
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

    def _mark_grid_dirty(self) -> None:
        """标记网格缓存失效（视图变化时调用）。"""
        self._grid_dirty = True

    def _schedule_rebuild(self) -> None:
        """延迟重绘：缩放时启动防抖定时器，避免频繁计算。"""
        self._mark_grid_dirty()
        self._rebuild_timer.start()  # 重新计时 200ms

    def _do_deferred_rebuild(self) -> None:
        """定时器到期 → 执行实际重绘（曲线笔宽 + 曲线路径）。"""
        self._clamp_view()
        self._update_curve_pens()
        self._rebuild_all_curves()
        self._emit_status()
        self._mark_grid_dirty()
        self.viewport().update()

    def _after_view_change(self) -> None:
        """视图变化后的统一处理（拖拽/按钮缩放后立即重绘）。"""
        self._clamp_view()
        self._update_curve_pens()
        self._rebuild_all_curves()
        self._mark_grid_dirty()
        self.viewport().update()

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        vs = _view_scale(self)
        if vs * factor < 1.0 / ZOOM_MAX or vs * factor > 1.0 / ZOOM_MIN:
            return
        self.scale(factor, factor)
        self._clamp_view()
        self._update_curve_pens()
        self._schedule_rebuild()  # 防抖：200ms 内连续缩放只重绘一次
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self._rebuild_timer.stop()  # 停止防抖，立即重绘
            self._after_view_change()
            self._emit_status()

    def zoom_in(self) -> None:
        if _view_scale(self) * 1.15 > 1.0 / ZOOM_MIN:
            return
        self.scale(1.15, 1.15)
        self._after_view_change()

    def zoom_out(self) -> None:
        if _view_scale(self) / 1.15 < 1.0 / ZOOM_MAX:
            return
        self.scale(1.0 / 1.15, 1.0 / 1.15)
        self._after_view_change()

    def reset_view(self) -> None:
        self.fitInView(INITIAL_VIEW, Qt.AspectRatioMode.KeepAspectRatio)
        self._after_view_change()
        self._emit_status()

    def set_range(self, x_min: float, x_max: float,
                  y_min: float, y_max: float) -> None:
        self.fitInView(QRectF(x_min, y_min, x_max - x_min, y_max - y_min),
                       Qt.AspectRatioMode.KeepAspectRatio)
        self._after_view_change()

    # ═══════════════════════════════════════════════════════════════
    #  Curve API
    # ═══════════════════════════════════════════════════════════════

    def add_function(self, expr: str, color: str = "", label: str = "",
                     var: str = "x", params: dict | None = None,
                     implicit: bool = False) -> int:
        idx = len(self._curves)
        if not color:
            color = CURVE_COLORS[idx % len(CURVE_COLORS)]
        self._path_cache.clear()
        self._curves.append({
            "expr": expr, "color": color, "visible": True,
            "label": label or f"f{idx + 1}", "params": params or {},
            "var": var, "implicit": implicit,
        })
        self._rebuild_all_curves()
        self._update_curve_pens()
        return idx

    def remove_function(self, idx: int) -> None:
        if 0 <= idx < len(self._curves):
            self._path_cache.clear()
            self._curves.pop(idx)
            self._rebuild_all_curves()

    def set_visible(self, idx: int, v: bool) -> None:
        if 0 <= idx < len(self._curves):
            self._curves[idx]["visible"] = v
            self._rebuild_all_curves()

    def set_params(self, idx: int, p: dict) -> None:
        if 0 <= idx < len(self._curves):
            self._path_cache.clear()
            self._curves[idx]["params"] = p
            self._rebuild_all_curves()

    def clear_functions(self) -> None:
        self._path_cache.clear()
        self._expr_cache.clear()
        self._curves.clear()
        self._rebuild_all_curves()

    # ═══════════════════════════════════════════════════════════════
    #  Curve rendering
    # ═══════════════════════════════════════════════════════════════

    def _rebuild_all_curves(self) -> None:
        for item in self._curve_items:
            self._scene.removeItem(item)
        self._curve_items.clear()

        vs = _view_scale(self)
        width = CURVE_PX / vs if vs > 0 else 0

        for f in self._curves:
            if not f.get("visible", True) or not f.get("expr"):
                continue
            if f.get("implicit"):
                path = self._draw_implicit_curve(f)
            else:
                path = self._eval_curve(f)
            if path is not None:
                pen = QPen(QColor(f["color"]))
                pen.setWidthF(width)
                item = QGraphicsPathItem(path)
                item.setPen(pen)
                item.setZValue(10)
                self._scene.addItem(item)
                self._curve_items.append(item)

        self._emit_status()

    def _get_cached_expr(self, expr_str: str):
        """缓存 sympy 表达式解析（~5ms saving per render）。"""
        if expr_str not in self._expr_cache:
            try:
                e = sp.sympify(expr_str)
                if hasattr(e, 'doit'):
                    e = e.doit()
                self._expr_cache[expr_str] = e
            except Exception:
                self._expr_cache[expr_str] = None
        return self._expr_cache[expr_str]

    def _eval_curve(self, f: dict) -> QPainterPath | None:
        expr_str = f.get("expr", "")
        if not expr_str:
            return None

        # ── 表达式缓存 ──
        expr = self._get_cached_expr(expr_str)
        if expr is None:
            return None

        # ── 路径缓存键（含 10% 边距减少缩放时缓存失效）──
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        margin = vr.width() * 0.1
        x0 = math.floor((vr.left() - margin) / 10) * 10
        x1 = math.ceil((vr.right() + margin) / 10) * 10
        params = f.get("params", {})
        path_key = f"{expr_str}|{sorted(params.items())}|{x0}|{x1}"

        if path_key in self._path_cache:
            return self._path_cache[path_key]

        # ── 参数替换 ──
        for k, v in params.items():
            expr = expr.subs(sp.Symbol(k), v)
        var_sym = sp.Symbol(f.get("var", "x"))
        if expr.free_symbols - {var_sym}:
            return None

        # ── 求值 + Path 构建 ──
        # 自适应采样：远视图少采样，近视图多采样
        view_width = x1 - x0
        if view_width > 100:
            n_samples = 500
        elif view_width > 10:
            n_samples = 1000
        else:
            n_samples = 2000
        xs = np.linspace(max(x0, -SCENE_RANGE), min(x1, SCENE_RANGE), n_samples)
        try:
            fn = _cached_lambdify(var_sym, expr, "numpy")
            ys = fn(xs)
            if not isinstance(ys, np.ndarray):
                return None
            if np.iscomplexobj(ys):
                ys = np.where(np.abs(ys.imag) < 1e-10, ys.real, np.nan)
        except Exception:
            return None

        path = QPainterPath()
        first = True
        for i in range(len(xs) - 1):
            a, b = ys[i], ys[i + 1]
            # 跳过 NaN / Inf 点（不抬笔，不画线）
            if np.isnan(a) or np.isnan(b) or np.isinf(a) or np.isinf(b):
                continue
            # 渐近线检测：|Δy|>10 或 符号突变+大值（正负无穷）
            if abs(b - a) > 10.0 or (a * b < 0 and abs(a) > 100 and abs(b) > 100):
                first = True; continue
            if first:
                path.moveTo(xs[i], a); first = False
            path.lineTo(xs[i + 1], b)

        if not path.isEmpty():
            if len(self._path_cache) >= 32:
                self._path_cache.pop(next(iter(self._path_cache)))
            self._path_cache[path_key] = path
            return path
        return None

    def _draw_implicit_curve(self, f: dict) -> QPainterPath | None:
        """Marching Squares 提取 f(x,y) = 0 等值线。

        自适应分辨率 + 场景坐标 + 固定像素笔宽。
        """
        try:
            import sympy as sp
            expr = sp.sympify(f["expr"])
        except Exception:
            return None

        # 代入参数
        for k, v in f.get("params", {}).items():
            expr = expr.subs(sp.Symbol(k), v)

        # 仍有未解析符号
        x_sym, y_sym = sp.Symbol("x"), sp.Symbol("y")
        remaining = expr.free_symbols - {x_sym, y_sym}
        if remaining:
            return None

        # ── 获取视图范围（场景坐标）──
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        x_min, x_max = float(vr.left()), float(vr.right())
        y_min, y_max = float(vr.top()), float(vr.bottom())
        rng = max(x_max - x_min, y_max - y_min)
        if rng <= 0:
            return None

        # ── 自适应分辨率（防止卡顿，平衡精度与性能）──
        if rng > 1000:
            res = 50    # ~2,500 格点，极快
        elif rng > 100:
            res = 100   # ~10,000 格点
        elif rng > 10:
            res = 150   # ~22,500 格点
        else:
            res = 200   # ~40,000 格点（仅在极高缩放时）

        xs = np.linspace(x_min, x_max, res)
        ys = np.linspace(y_min, y_max, res)
        dx = float(xs[1] - xs[0])
        dy = float(ys[1] - ys[0])

        # ── 向量化求值（numpy 加速）──
        try:
            f_fn = _cached_lambdify((x_sym, y_sym), expr, "numpy")
            X, Y = np.meshgrid(xs, ys)
            Z = f_fn(X, Y)
            if not isinstance(Z, np.ndarray):
                return None
            if np.iscomplexobj(Z):
                Z = np.where(np.abs(Z.imag) < 1e-10, Z.real, np.nan)
        except Exception:
            return None

        # ── Marching Squares ──
        # 单元格四角（标准顺序）:
        #   z01=top-left    z11=top-right       3──2
        #   z00=bottom-left z10=bottom-right    0──1
        path = QPainterPath()

        for i in range(res - 1):
            for j in range(res - 1):
                # Z[i,j] 对应 (xs[j], ys[i])
                z00 = Z[i, j]         # bottom-left  → corner 0
                z10 = Z[i, j + 1]     # bottom-right → corner 1
                z11 = Z[i + 1, j + 1] # top-right    → corner 2
                z01 = Z[i + 1, j]     # top-left     → corner 3

                if any(np.isnan(v) for v in (z00, z10, z11, z01)):
                    continue

                # 确定 case (0-15): bit0=corner0, bit1=corner1, ...
                case = 0
                if z00 >= 0: case |= 1   # corner 0: bottom-left
                if z10 >= 0: case |= 2   # corner 1: bottom-right
                if z11 >= 0: case |= 4   # corner 2: top-right
                if z01 >= 0: case |= 8   # corner 3: top-left

                if case == 0 or case == 15:
                    continue

                # 鞍点消歧：用网格中心值
                segs = _MS_EDGES.get(case, [])
                if case in (5, 10):
                    center_z = (z00 + z10 + z11 + z01) * 0.25
                    if (center_z >= 0) == (z00 >= 0):
                        segs = _MS_ALT.get(case, segs)

                # 计算 4 条边与 f=0 的交点（场景坐标）
                # 边 0=底(bottom-left→bottom-right) 1=右(bottom-right→top-right)
                # 边 2=顶(top-left→top-right)       3=左(bottom-left→top-left)
                x0, y0 = xs[j], ys[i]
                x1, y1 = xs[j + 1], ys[i + 1]

                bx = x0 + dx * _safe_frac(z00, z10)  # 底边交点 x
                rx = y0 + dy * _safe_frac(z10, z11)  # 右边交点 y
                tx = x0 + dx * _safe_frac(z01, z11)  # 顶边交点 x
                lx = y0 + dy * _safe_frac(z00, z01)  # 左边交点 y

                edge_pts = {
                    0: (bx, y0),     # 底边
                    1: (x1, rx),     # 右边
                    2: (tx, y1),     # 顶边
                    3: (x0, lx),     # 左边
                }

                for e0, e1 in segs:
                    p0, p1 = edge_pts[e0], edge_pts[e1]
                    path.moveTo(p0[0], p0[1])
                    path.lineTo(p1[0], p1[1])

        return path if not path.isEmpty() else None

    def _emit_status(self) -> None:
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        step = calculate_step(max(vr.width(), vr.height()))
        R = SCENE_RANGE
        near = (abs(vr.left()) > R * 0.9 or abs(vr.right()) > R * 0.9 or
                abs(vr.top()) > R * 0.9 or abs(vr.bottom()) > R * 0.9)
        limit_msg = f"  最大范围 {MAX_RANGE_MSG}" if near else ""
        self.status_message.emit(
            f"x [{format_tick(vr.left())}, {format_tick(vr.right())}]  "
            f"y [{format_tick(vr.top())}, {format_tick(vr.bottom())}]  "
            f"曲线 {len(self._curve_items)}  步长 {step:.4g}{limit_msg}"
        )

    # ═══════════════════════════════════════════════════════════════
    #  Backward compat
    # ═══════════════════════════════════════════════════════════════

    def update_axes(self) -> None:
        self.viewport().update()


# ═══════════════════════════════════════════════════════════════════════
#  Standalone test
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar

    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("PlotCanvas")
    win.resize(900, 700)

    canvas = PlotCanvas()
    status = QStatusBar()
    canvas.status_message.connect(lambda msg: status.showMessage(msg, 0))
    win.setStatusBar(status)
    win.setCentralWidget(canvas)

    canvas.add_function("x**2", color="#e74c3c", label="x²")
    canvas.add_function("sin(x)", color="#3498db", label="sin(x)")

    win.show()
    sys.exit(app.exec())
