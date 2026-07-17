# -*- coding: utf-8 -*-
"""grid_renderer.py — 共享网格/坐标轴/刻度绘制工具。

plot_canvas.py 和 geometry_canvas.py 的 drawForeground 中
~140 行重复代码抽取为此模块，统一维护。
"""

from __future__ import annotations

from typing import Sequence

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen


# ═══════════════════════════════════════════════════════════
#  Nice step table — 美观刻度步长
# ═══════════════════════════════════════════════════════════

NICE_TABLE: tuple[float, ...] = (
    0.001, 0.002, 0.005,
    0.01, 0.02, 0.05,
    0.1, 0.2, 0.5,
    1.0, 2.0, 5.0,
    10.0, 20.0, 50.0,
    100.0, 200.0, 500.0,
    1000.0, 2000.0, 5000.0,
    10000.0, 20000.0, 50000.0,
    100000.0,
)


def calculate_step(rng: float) -> float:
    """根据显示范围自动计算美观的刻度步长。"""
    for n in NICE_TABLE:
        if rng / n <= 8:
            return n
    return NICE_TABLE[-1]


def format_tick(v: float, step: float = 1.0) -> str:
    """刻度数值格式化 — 自适应小数位数。"""
    if abs(v) < 1e-10:
        return "0"
    if abs(step - int(step)) < 1e-10 and abs(v - int(v)) < 1e-10:
        return str(int(v))
    ad = max(0, -int(__import__("math").floor(__import__("math").log10(abs(step) + 1e-30))))
    return f"{v:.{ad}f}"


# ═══════════════════════════════════════════════════════════
#  GridRenderer — 封装 drawForeground 中的网格/轴/刻度绘制
# ═══════════════════════════════════════════════════════════

class GridRenderer:
    """共享网格/坐标轴/刻度绘制器。

    用法:
        renderer = GridRenderer(axis_color=..., grid_color=..., ...)
        # 在 drawForeground 中:
        renderer.draw(painter, viewport_rect, scene_rect,
                      map_x_func, map_y_func, step_px_func)
    """

    def __init__(
        self,
        axis_color: QColor = QColor("#94a3b8"),
        grid_color: QColor = QColor("#e2e8f0"),
        tick_color: QColor = QColor("#94a3b8"),
        edge_color: QColor = QColor("#cbd5e1"),
        text_color: QColor = QColor("#64748b"),
        bg_color: QColor = QColor("#f8fafc"),
        font_px: int = 9,
        tick_px: int = 4,
        axis_px: float = 2.0,
    ):
        self.axis_color = axis_color
        self.grid_color = grid_color
        self.tick_color = tick_color
        self.edge_color = edge_color
        self.text_color = text_color
        self.bg_color = bg_color
        self.font_px = font_px
        self.tick_px = tick_px
        self.axis_px = axis_px

    def draw(
        self,
        p: QPainter,
        vr: QRectF,          # viewport rect (scene coords)
        map_x,                # callable: scene_x → view_x
        map_y,                # callable: scene_y → view_y
        step_px_fn,           # callable: step → pixel count
    ) -> None:
        """在 QPainter 上绘制完整的网格+坐标轴+刻度。"""
        font = QFont()
        font.setPixelSize(self.font_px)
        p.setFont(font)

        step = calculate_step(vr.width())
        step_px = step_px_fn(step)

        # ── 网格线 ──
        pen = QPen(self.grid_color, 1)
        p.setPen(pen)
        x_start = int(vr.left() / step) * step
        x = x_start
        while x <= vr.right() + step * 0.5:
            p.drawLine(
                QPointF(map_x(x), map_y(vr.bottom())),
                QPointF(map_x(x), map_y(vr.top())),
            )
            x += step

        y_start = int(vr.bottom() / step) * step
        y = y_start
        while y <= vr.top() + step * 0.5:
            p.drawLine(
                QPointF(map_x(vr.left()), map_y(y)),
                QPointF(map_x(vr.right()), map_y(y)),
            )
            y += step

        # ── 刻度线 + 刻度标签 ──
        tick_pen = QPen(self.tick_color, 1)
        p.setPen(tick_pen)
        tl = self.tick_px
        fm = p.fontMetrics()

        # X 轴刻度
        x = x_start
        while x <= vr.right() + step * 0.5:
            sx = map_x(x)
            p.drawLine(QPointF(sx, map_y(0) - tl), QPointF(sx, map_y(0) + tl))
            label = format_tick(x, step)
            tw = fm.horizontalAdvance(label)
            p.drawText(
                QPointF(sx - tw / 2, map_y(0) + tl + fm.ascent() + 2), label
            )
            x += step

        # Y 轴刻度
        y = y_start
        while y <= vr.top() + step * 0.5:
            sy = map_y(y)
            p.drawLine(QPointF(map_x(0) - tl, sy), QPointF(map_x(0) + tl, sy))
            label = format_tick(y, step)
            tw = fm.horizontalAdvance(label)
            p.drawText(
                QPointF(map_x(0) - tw - tl - 4, sy + fm.ascent() / 3), label
            )
            y += step

        # ── 坐标轴 ──
        axis_pen = QPen(self.axis_color, self.axis_px)
        p.setPen(axis_pen)
        # X 轴
        p.drawLine(QPointF(map_x(vr.left()), map_y(0)),
                   QPointF(map_x(vr.right()), map_y(0)))
        # Y 轴
        p.drawLine(QPointF(map_x(0), map_y(vr.bottom())),
                   QPointF(map_x(0), map_y(vr.top())))

        # 原点 "O"
        p.setPen(QPen(self.text_color, 1))
        p.drawText(QPointF(map_x(0) - 12, map_y(0) - 6), "O")

        # 轴名
        p.drawText(
            QPointF(map_x(vr.right()) - 20, map_y(0) - 10), "x"
        )
        p.drawText(
            QPointF(map_x(0) + 6, map_y(vr.top()) + 16), "y"
        )

        # ── 边缘刻度（viewport 四边）──
        edge_pen = QPen(self.edge_color, 1)
        p.setPen(edge_pen)

        # 底边
        sx = map_x(x_start)
        while sx <= map_x(vr.right()):
            p.drawLine(QPointF(sx, map_y(vr.bottom())),
                       QPointF(sx, map_y(vr.bottom()) + tl))
            sx += step_px

        # 顶边
        sx = map_x(x_start)
        while sx <= map_x(vr.right()):
            p.drawLine(QPointF(sx, map_y(vr.top())),
                       QPointF(sx, map_y(vr.top()) - tl))
            sx += step_px

        # 左边
        sy = map_y(y_start)
        while sy >= map_y(vr.top()):
            p.drawLine(QPointF(map_x(vr.left()), sy),
                       QPointF(map_x(vr.left()) + tl, sy))
            sy -= step_px

        # 右边
        sy = map_y(y_start)
        while sy >= map_y(vr.top()):
            p.drawLine(QPointF(map_x(vr.right()), sy),
                       QPointF(map_x(vr.right()) - tl, sy))
            sy -= step_px
