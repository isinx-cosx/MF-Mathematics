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
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QGraphicsPathItem, QGraphicsScene, QGraphicsView, QWidget,
)


# ═══════════════════════════════════════════════════════════════════════
#  Config
# ═══════════════════════════════════════════════════════════════════════

def _load_config() -> dict:
    try:
        from MF_Mathematics.utils.config_manager import config
        return config.raw
    except Exception:
        pass
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        p = os.path.join(root, "config.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

_CFG = _load_config()
_PLT = _CFG.get("plot", {})

SCENE_RANGE  = 20_000_000
ZOOM_MIN     = 1e-6
ZOOM_MAX     = 2000
INITIAL_VIEW = QRectF(-20, -20, 40, 40)
MAX_RANGE_MSG = "±20,000,000"

TICK_PX   = 4        # 刻度线半长（像素）
FONT_PX   = 9        # 标签字号（像素）
AXIS_PX   = 2.0      # 坐标轴线宽（像素，恒定）
CURVE_PX  = 2.5      # 函数曲线线宽（像素，恒定）

CURVE_COLORS = _PLT.get("colors", [
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

AXIS_COLOR  = QColor("#334155")
GRID_COLOR  = QColor("#e8ecf0")
TICK_COLOR  = QColor("#94a3b8")
EDGE_COLOR  = QColor("#b0b8c0")
TEXT_COLOR  = QColor("#334155")
BG_COLOR    = QColor("#fafbfc")

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
        xa_ok = oy is not None and y0 <= 0 <= y1  # X 轴在视野内
        ya_ok = ox is not None and x0 <= 0 <= x1  # Y 轴在视野内

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

    def _after_view_change(self) -> None:
        """视图变化后的统一处理。"""
        self._clamp_view()
        self._update_curve_pens()
        self._rebuild_all_curves()
        self.viewport().update()

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        vs = _view_scale(self)
        if vs * factor < 1.0 / ZOOM_MAX or vs * factor > 1.0 / ZOOM_MIN:
            return
        self.scale(factor, factor)
        self._after_view_change()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
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
            self._curves.pop(idx)
            self._rebuild_all_curves()

    def set_visible(self, idx: int, v: bool) -> None:
        if 0 <= idx < len(self._curves):
            self._curves[idx]["visible"] = v
            self._rebuild_all_curves()

    def set_params(self, idx: int, p: dict) -> None:
        if 0 <= idx < len(self._curves):
            self._curves[idx]["params"] = p
            self._rebuild_all_curves()

    def clear_functions(self) -> None:
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
                path = self._eval_implicit_curve(f)
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

    def _eval_curve(self, f: dict) -> QPainterPath | None:
        try:
            import sympy as sp
            expr = sp.sympify(f["expr"])
        except Exception:
            return None
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        xs = np.linspace(
            max(vr.left(), -SCENE_RANGE), min(vr.right(), SCENE_RANGE), 2000)
        try:
            for k, v in f.get("params", {}).items():
                expr = expr.subs(sp.Symbol(k), v)
            # 仍有未解析的符号 → 跳过
            if expr.free_symbols - {sp.Symbol(f.get("var", "x"))}:
                return None
            var_sym = sp.Symbol(f.get("var", "x"))
            ys = sp.lambdify(var_sym, expr, "numpy")(xs)
            if not isinstance(ys, np.ndarray):
                return None
            if np.iscomplexobj(ys):
                ys = np.where(np.abs(ys.imag) < 1e-10, ys.real, np.nan)
        except Exception:
            return None
        yr = max(vr.height(), 1.0)
        path = QPainterPath()
        first = True
        for i in range(len(xs) - 1):
            a, b = ys[i], ys[i + 1]
            if np.isnan(a) or np.isnan(b):
                first = True; continue
            if abs(b - a) > yr * 2:
                first = True; continue
            if first:
                path.moveTo(xs[i], a); first = False
            else:
                path.lineTo(xs[i + 1], b)
        return path if not path.isEmpty() else None

    def _eval_implicit_curve(self, f: dict) -> QPainterPath | None:
        """Marching Squares 提取 f(x,y) = 0 等值线。"""
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

        # ── 自适应分辨率 ──
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        x_min, x_max = float(vr.left()), float(vr.right())
        y_min, y_max = float(vr.top()), float(vr.bottom())
        rng = max(x_max - x_min, y_max - y_min)
        if rng <= 0:
            return None
        res = max(60, min(300, int(300 * 20.0 / rng)))
        xs = np.linspace(x_min, x_max, res)
        ys = np.linspace(y_min, y_max, res)
        dx = float(xs[1] - xs[0])
        dy = float(ys[1] - ys[0])

        # ── 向量化求值 ──
        try:
            f_fn = sp.lambdify((x_sym, y_sym), expr, "numpy")
            X, Y = np.meshgrid(xs, ys)
            Z = f_fn(X, Y)
            if not isinstance(Z, np.ndarray):
                return None
            # 复数 → 实部（虚部极小则视为实数）
            if np.iscomplexobj(Z):
                Z = np.where(np.abs(Z.imag) < 1e-10, Z.real, np.nan)
        except Exception:
            return None

        # ── Marching Squares ──
        path = QPainterPath()

        for i in range(res - 1):
            for j in range(res - 1):
                z00, z10 = Z[i, j], Z[i + 1, j]
                z11, z01 = Z[i + 1, j + 1], Z[i, j + 1]

                if any(np.isnan(v) for v in (z00, z10, z11, z01)):
                    continue

                # 确定 case (0-15)
                case = 0
                if z00 >= 0: case |= 1
                if z10 >= 0: case |= 2
                if z11 >= 0: case |= 4
                if z01 >= 0: case |= 8

                if case == 0 or case == 15:
                    continue

                # 鞍点消歧：用网格中心值
                segs = _MS_EDGES.get(case, [])
                if case in (5, 10):
                    center_z = (z00 + z10 + z11 + z01) * 0.25
                    if (center_z >= 0) == (z00 >= 0):
                        segs = _MS_ALT.get(case, segs)

                # 计算 4 条边的交点坐标
                x0, y0 = xs[i], ys[j]
                x1, y1 = xs[i + 1], ys[j + 1]

                def _interp_bottom() -> float:
                    return x0 + dx * _safe_frac(z00, z10)
                def _interp_right() -> float:
                    return y0 + dy * _safe_frac(z10, z11)
                def _interp_top() -> float:
                    return x0 + dx * _safe_frac(z01, z11)
                def _interp_left() -> float:
                    return y0 + dy * _safe_frac(z00, z01)

                edge_pts = {
                    0: (_interp_bottom(), y0),
                    1: (x1, _interp_right()),
                    2: (_interp_top(), y1),
                    3: (x0, _interp_left()),
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
