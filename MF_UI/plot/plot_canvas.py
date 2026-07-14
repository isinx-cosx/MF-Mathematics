# -*- coding: utf-8 -*-
"""PlotCanvas — QGraphicsView 静态场景绘图画布。

核心原则:
  - 所有轴元素作为 QGraphicsItem 预创建在场景中
  - 缩放/拖拽不重建对象，仅 step 变化时替换刻度
  - 字体/线条在创建时固定像素值
  - 无 drawForeground 重写
"""

from __future__ import annotations

import json, os
import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsScene, QGraphicsView, QWidget,
)
from MF_UI.plot.axes import draw_axes

# ── Constants ─────────────────────────────────────────────
_SCENE_RANGE = 1_000_000        # ±1e6
_INIT_STEP   = 2.0
_ZOOM_MIN    = 0.01
_ZOOM_MAX    = 10000

# ── Step calculator (used by _check_step_update) ──────────

def _nice_step(view_range: float) -> float:
    if view_range <= 0:
        return _INIT_STEP
    raw = view_range / 15.0
    step = _INIT_STEP
    if raw > step:
        while step < raw:
            step *= 2.0
    else:
        while step / 2.0 >= raw and step > 0.125:
            step /= 2.0
    while view_range / step > 30:
        step *= 2.0
    return step


# ═══════════════════════════════════════════════════════════
#  PlotCanvas
# ═══════════════════════════════════════════════════════════

_COLORS = ["#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6","#1abc9c","#e67e22","#e84393"]


class PlotCanvas(QGraphicsView):
    """交互式 2D 绘图画布 — 静态场景 + 固定像素样式。"""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # ── Scene ──
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(
            QRectF(-_SCENE_RANGE, -_SCENE_RANGE, _SCENE_RANGE * 2, _SCENE_RANGE * 2)
        )
        self.setScene(self._scene)

        # ── View settings ──
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setBackgroundBrush(QBrush(QColor("#ffffff")))
        self.scale(1, -1)          # Y-up

        # ── State ──
        self._panning = False
        self._last_pos: QPointF | None = None
        self._zoom_level: float = 1.0
        self._current_step: float = _INIT_STEP  # 缓存步长，避免频繁重建
        self._funcs: list[dict] = []
        self._tick_group: list[QGraphicsItem] = []   # 可替换的刻度对象
        self._static_items: list[QGraphicsItem] = [] # 边界线等永久对象

        # ── Static items (survive replot) ──
        self._add_boundary()

        # ── Initial build ──
        self.fitInView(QRectF(-200, -200, 400, 400), Qt.AspectRatioMode.KeepAspectRatio)
        self.update_axes()

        # 性能优化：场景元素少时禁用索引
        self._scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)

    # ═══════════════════════════════════════════════════════
    #  Static scene items
    # ═══════════════════════════════════════════════════════

    def _add_boundary(self) -> None:
        d = 200
        r, R = int(-_SCENE_RANGE + d), int(_SCENE_RANGE - d)
        pen = QPen(QColor(239, 68, 68, 80), 0)
        pen.setStyle(Qt.PenStyle.DashLine)
        for a, b, c, d_ in [(r,r,R,r), (r,R,R,R), (r,r,r,R), (R,r,R,R)]:
            self._static_items.append(self._scene.addLine(a, b, c, d_, pen))

    # ═══════════════════════════════════════════════════════
    #  Tick rebuild (called only when step changes)
    # ═══════════════════════════════════════════════════════

    def update_axes(self) -> None:
        """更新坐标系：仅步长变化 >10% 时重建，否则跳过。"""
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        new_step = _nice_step(max(vr.width(), vr.height()))
        if (new_step > self._current_step * 1.1 or
                self._current_step > new_step * 1.1):
            self._current_step = new_step
            draw_axes(self._scene, vr, self.transform())

    # ═══════════════════════════════════════════════════════
    #  Pan
    # ═══════════════════════════════════════════════════════

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = True
            self._last_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning and self._last_pos:
            dx = event.position().x() - self._last_pos.x()
            dy = event.position().y() - self._last_pos.y()
            self._last_pos = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - dx)
            )
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - dy)
            )
            self._clamp()
            self.viewport().update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._panning = False
            self._last_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.viewport().update()
            self.update_axes()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _clamp(self) -> None:
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        R = _SCENE_RANGE
        if vr.left() < -R:   h.setValue(h.value() - int(-R - vr.left()))
        if vr.right() > R:   h.setValue(h.value() + int(vr.right() - R))
        if vr.top() < -R:    v.setValue(v.value() - int(-R - vr.top()))
        if vr.bottom() > R:  v.setValue(v.value() + int(vr.bottom() - R))

    # ═══════════════════════════════════════════════════════
    #  Zoom
    # ═══════════════════════════════════════════════════════

    def wheelEvent(self, event) -> None:
        d = event.angleDelta().y()
        f = 1.15 if d > 0 else 1.0 / 1.15
        nz = self._zoom_level * f
        if nz < _ZOOM_MIN or nz > _ZOOM_MAX:
            return
        self._zoom_level = nz
        self.scale(f, f)
        self._clamp()
        self.update_axes()
        event.accept()

    # ═══════════════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════════════

    def set_range(self, x_min: float, x_max: float, y_min: float, y_max: float) -> None:
        """设置视图显示范围。"""
        self.fitInView(QRectF(x_min, y_min, x_max - x_min, y_max - y_min),
                       Qt.AspectRatioMode.KeepAspectRatio)
        self._clamp()
        self.update_axes()

    def zoom_in(self) -> None:
        self.scale(1.15, 1.15)
        self._zoom_level *= 1.15
        self.update_axes()

    def zoom_out(self) -> None:
        f = 1.0 / 1.15
        if self._zoom_level * f >= _ZOOM_MIN:
            self.scale(f, f)
            self._zoom_level *= f
            self.update_axes()

    def reset_view(self) -> None:
        """重置视图到初始状态。"""
        self._zoom_level = 1.0
        self._current_step = _INIT_STEP
        self.update_axes()
        self.fitInView(QRectF(-200, -200, 400, 400), Qt.AspectRatioMode.KeepAspectRatio)

    # ═══════════════════════════════════════════════════════
    #  Function curve API (reserved)
    # ═══════════════════════════════════════════════════════

    def set_function_curves(self, curves: list[QPainterPath]) -> None:
        """替换所有函数曲线（预留接口）。"""
        for f in self._funcs:
            for item in self._scene.items():
                if isinstance(item, QGraphicsLineItem):
                    continue
        self._funcs.clear()

    def add_function(self, expr: str, color: str = "", label: str = "") -> int:
        """添加函数曲线。"""
        idx = len(self._funcs)
        if not color:
            color = _COLORS[idx % len(_COLORS)]
        self._funcs.append({
            "expr": expr, "color": color, "visible": True,
            "label": label or f"f{idx+1}", "params": {},
        })
        self._replot_curves()
        return idx

    def remove_function(self, idx: int) -> None:
        if 0 <= idx < len(self._funcs):
            self._funcs.pop(idx)
            self._replot_curves()

    def set_visible(self, idx: int, v: bool) -> None:
        if 0 <= idx < len(self._funcs):
            self._funcs[idx]["visible"] = v
            self._replot_curves()

    def set_params(self, idx: int, p: dict) -> None:
        if 0 <= idx < len(self._funcs):
            self._funcs[idx]["params"] = p
            self._replot_curves()

    def clear_functions(self) -> None:
        self._funcs.clear()
        self._replot_curves()

    def _replot_curves(self) -> None:
        """重绘函数曲线。"""
        # 仅移除曲线（保留轴和刻度）
        for item in list(self._scene.items()):
            if isinstance(item, QPainterPath):
                self._scene.removeItem(item)
        # Be more surgical: remove only paths
        keep = set(self._tick_group) | set(self._static_items)
        for item in list(self._scene.items()):
            if item not in keep:
                self._scene.removeItem(item)
        for f in self._funcs:
            if f.get("visible", True):
                self._draw_curve(f)

    def _draw_curve(self, f: dict) -> None:
        try:
            import sympy as sp
            e = sp.sympify(f["expr"])
        except Exception:
            return
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        xs = np.linspace(
            max(vr.left(), -_SCENE_RANGE), min(vr.right(), _SCENE_RANGE), 2000
        )
        try:
            for k, v in f.get("params", {}).items():
                e = e.subs(sp.Symbol(k), v)
            ys = sp.lambdify(sp.Symbol("x"), e, "numpy")(xs)
            if np.iscomplexobj(ys):
                ys = np.where(np.abs(ys.imag) < 1e-10, ys.real, np.nan)
        except Exception:
            return
        yr = vr.height()
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
        self._scene.addPath(path, QPen(QColor(f["color"]), 0))
