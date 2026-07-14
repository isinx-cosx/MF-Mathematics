# -*- coding: utf-8 -*-
"""Plot3D — 三维坐标系控件（Matplotlib mplot3d + PySide6）。

特性:
  - X/Y/Z 轴（红/绿/蓝，带箭头和标签）
  - 网格线（灰色虚线，三面墙）
  - 刻度标签（自适应步长，两位小数）
  - 鼠标拖拽旋转 + 滚轮缩放（NavigationToolbar2QT）
  - 多曲面叠加 + 独立可见性控制
  - 曲面数据缓存，避免重复 sympy 解析
"""

from __future__ import annotations

import json, math, os
import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

import matplotlib
matplotlib.use("Qt5Agg")
matplotlib.rcParams["font.family"] = "sans-serif"
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import matplotlib.ticker as ticker


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
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        p = os.path.join(root, "config.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

_CFG = _load_config()
_PLT = _CFG.get("plot", {})
_AX  = _PLT.get("axes", {})

AXIS_X_COLOR    = _AX.get("axis_3d_x", "#e74c3c")
AXIS_Y_COLOR    = _AX.get("axis_3d_y", "#2ecc71")
AXIS_Z_COLOR    = _AX.get("axis_3d_z", "#3498db")
GRID_COLOR      = _AX.get("grid_color",   "#888888")
BG_COLOR        = _AX.get("bg_color",     "#1e1e2e")
TEXT_COLOR      = _AX.get("text_color",   "#cccccc")
LABEL_FONT_SIZE = _AX.get("label_font_size", 10)
TICK_FONT_SIZE  = _AX.get("tick_font_size", 8)

_NICE_TABLE = (
    0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
    1, 2, 5, 10, 20, 50, 100, 200, 500, 1000,
)


def _nice_step(rng: float) -> float:
    if rng <= 0:
        return 1.0
    raw = rng / 8.0
    for n in _NICE_TABLE:
        if n >= raw:
            return n
    return _NICE_TABLE[-1]


def _surface_resolution(rng: float) -> int:
    """自适应曲面分辨率。"""
    if rng > 1000:
        return 80
    elif rng < 10:
        return 150
    return 100


class Plot3D(QWidget):
    """三维坐标系控件 — 多曲面叠加、独立可见性、参数联动。"""

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._surfaces: list[dict] = []
        self._range = 10.0

        # ── Figure + 3D Axes ──
        self._fig = Figure(figsize=(8, 6), dpi=100, facecolor=BG_COLOR)
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._ax.set_facecolor(BG_COLOR)
        self._ax.view_init(elev=25, azim=-50)
        self._ax.set_xlim(-self._range, self._range)
        self._ax.set_ylim(-self._range, self._range)
        self._ax.set_zlim(-self._range, self._range)

        # ── Canvas + Toolbar ──
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas, 1)

        self._draw_axes()
        self._canvas.draw_idle()

    # ═══════════════════════════════════════════════════════════════
    #  Public API — 坐标系
    # ═══════════════════════════════════════════════════════════════

    def set_axis_labels(self, xlabel: str = "x",
                        ylabel: str = "y", zlabel: str = "z") -> None:
        self._ax.set_xlabel(xlabel, color=TEXT_COLOR, fontsize=LABEL_FONT_SIZE)
        self._ax.set_ylabel(ylabel, color=TEXT_COLOR, fontsize=LABEL_FONT_SIZE)
        self._ax.set_zlabel(zlabel, color=TEXT_COLOR, fontsize=LABEL_FONT_SIZE)
        self._canvas.draw_idle()

    def set_view(self, elev: float = 25, azim: float = -50) -> None:
        self._ax.view_init(elev=elev, azim=azim)
        self._canvas.draw_idle()

    def set_range(self, rng: float) -> None:
        self._range = rng
        self._ax.set_xlim(-rng, rng)
        self._ax.set_ylim(-rng, rng)
        self._ax.set_zlim(-rng, rng)
        self._draw_axes()

    def clear(self) -> None:
        """清除所有曲面/曲线，保留坐标系。"""
        for coll in list(self._ax.collections):
            coll.remove()
        for line in list(self._ax.lines):
            line.remove()
        self._surfaces.clear()
        self._draw_axes()

    # ═══════════════════════════════════════════════════════════════
    #  Public API — 曲面管理
    # ═══════════════════════════════════════════════════════════════

    def add_surface(self, expr: str, color: str = "#3498db",
                    params: dict | None = None,
                    resolution: int | None = None) -> int:
        """添加曲面 z=f(x,y)，返回索引。

        Args:
            expr: sympy 兼容表达式（如 "sin(x)*cos(y)"）。
            color: 曲面颜色（十六进制）。
            params: 参数替换字典 {"a": 1.0, "b": 2.0}。
            resolution: 网格分辨率，None 则自适应。

        Returns:
            曲面索引，可用于 set_visible / update_surface。
        """
        import sympy as sp
        idx = len(self._surfaces)
        entry = {
            "expr": expr, "color": color,
            "params": params or {}, "visible": True,
            "surface_obj": None,   # Poly3DCollection 引用
        }
        self._surfaces.append(entry)

        if resolution is None:
            resolution = _surface_resolution(self._range * 2)

        try:
            expr_sym = sp.sympify(expr)
            for k, v in (params or {}).items():
                expr_sym = expr_sym.subs(sp.Symbol(k), v)

            x_sym, y_sym = sp.Symbol("x"), sp.Symbol("y")
            if expr_sym.free_symbols - {x_sym, y_sym}:
                return idx

            r = self._range
            xs = np.linspace(-r, r, resolution)
            ys = np.linspace(-r, r, resolution)
            X, Y = np.meshgrid(xs, ys)
            fn = sp.lambdify((x_sym, y_sym), expr_sym, "numpy")
            Z = fn(X, Y)
            if np.iscomplexobj(Z):
                Z = np.where(np.abs(Z.imag) < 1e-10, Z.real, np.nan)
            Z = np.clip(Z, -1e6, 1e6)

            surf = self._ax.plot_surface(
                X, Y, Z, alpha=0.85, color=color,
                linewidth=0, antialiased=True, shade=True)
            entry["surface_obj"] = surf
            self._canvas.draw_idle()
        except Exception:
            pass

        self._emit_status()
        return idx

    def update_surface(self, idx: int, expr: str,
                       color: str | None = None,
                       params: dict | None = None) -> None:
        """更新已有曲面（移除旧对象，重新绘制）。"""
        if not (0 <= idx < len(self._surfaces)):
            return
        entry = self._surfaces[idx]
        # 移除旧曲面对象
        old = entry.get("surface_obj")
        if old is not None:
            old.remove()
            entry["surface_obj"] = None

        # 更新元数据
        entry["expr"] = expr
        if color is not None:
            entry["color"] = color
        if params is not None:
            entry["params"] = params

        # 重新绘制
        if entry["visible"]:
            self._add_surface_internal(entry)

        self._canvas.draw_idle()
        self._emit_status()

    def set_visible(self, idx: int, visible: bool) -> None:
        """切换曲面可见性（不重建曲面数据）。"""
        if not (0 <= idx < len(self._surfaces)):
            return
        entry = self._surfaces[idx]
        entry["visible"] = visible
        obj = entry.get("surface_obj")
        if obj is not None:
            obj.set_visible(visible)
            self._canvas.draw_idle()

    def remove_surface(self, idx: int) -> None:
        """删除曲面并清理内存。"""
        if not (0 <= idx < len(self._surfaces)):
            return
        entry = self._surfaces[idx]
        obj = entry.get("surface_obj")
        if obj is not None:
            obj.remove()
        self._surfaces.pop(idx)
        self._canvas.draw_idle()
        self._emit_status()

    def clear_surfaces(self) -> None:
        """移除所有曲面（不清坐标系）。"""
        for entry in self._surfaces:
            obj = entry.get("surface_obj")
            if obj is not None:
                obj.remove()
        self._surfaces.clear()
        self._canvas.draw_idle()
        self._emit_status()

    def rebuild_all_surfaces(self, global_params: dict | None = None) -> None:
        """重建所有可见曲面（用于参数滑块变化后）。"""
        # 更新参数并重建
        for entry in self._surfaces:
            if global_params:
                for k, v in global_params.items():
                    if k in entry["params"]:
                        entry["params"][k] = v
            # 移除旧对象
            obj = entry.get("surface_obj")
            if obj is not None:
                obj.remove()
                entry["surface_obj"] = None

        for entry in self._surfaces:
            if entry["visible"]:
                self._add_surface_internal(entry)

        self._canvas.draw_idle()
        self._emit_status()

    # ═══════════════════════════════════════════════════════════════
    #  Internal
    # ═══════════════════════════════════════════════════════════════

    def _add_surface_internal(self, entry: dict) -> None:
        """内部：计算并绘制单个曲面（不更新 UI）。"""
        import sympy as sp
        try:
            expr_sym = sp.sympify(entry["expr"])
            for k, v in entry["params"].items():
                expr_sym = expr_sym.subs(sp.Symbol(k), v)

            x_sym, y_sym = sp.Symbol("x"), sp.Symbol("y")
            if expr_sym.free_symbols - {x_sym, y_sym}:
                return

            res = _surface_resolution(self._range * 2)
            r = self._range
            xs = np.linspace(-r, r, res)
            ys = np.linspace(-r, r, res)
            X, Y = np.meshgrid(xs, ys)
            fn = sp.lambdify((x_sym, y_sym), expr_sym, "numpy")
            Z = fn(X, Y)
            if np.iscomplexobj(Z):
                Z = np.where(np.abs(Z.imag) < 1e-10, Z.real, np.nan)
            Z = np.clip(Z, -1e6, 1e6)

            surf = self._ax.plot_surface(
                X, Y, Z, alpha=0.85, color=entry["color"],
                linewidth=0, antialiased=True, shade=True)
            entry["surface_obj"] = surf
        except Exception:
            pass

    def _draw_axes(self) -> None:
        """绘制/重绘三维坐标系。"""
        ax = self._ax
        r = self._range
        step = _nice_step(r * 2)

        ax.set_xlabel("x", color=AXIS_X_COLOR, fontsize=LABEL_FONT_SIZE, fontweight="bold")
        ax.set_ylabel("y", color=AXIS_Y_COLOR, fontsize=LABEL_FONT_SIZE, fontweight="bold")
        ax.set_zlabel("z", color=AXIS_Z_COLOR, fontsize=LABEL_FONT_SIZE, fontweight="bold")

        ticks = np.arange(-r, r + step * 0.5, step)
        ticks = ticks[np.abs(ticks) <= r]
        ax.set_xticks(ticks); ax.set_yticks(ticks); ax.set_zticks(ticks)

        def _fmt(v, _):
            if abs(v) < 1e-12:
                return "0"
            return f"{v:.2f}".rstrip("0").rstrip(".")

        ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt))
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(_fmt))
        ax.zaxis.set_major_formatter(ticker.FuncFormatter(_fmt))

        ax.tick_params(axis="x", colors=AXIS_X_COLOR, labelsize=TICK_FONT_SIZE)
        ax.tick_params(axis="y", colors=AXIS_Y_COLOR, labelsize=TICK_FONT_SIZE)
        ax.tick_params(axis="z", colors=AXIS_Z_COLOR, labelsize=TICK_FONT_SIZE)

        for axis_name in ("x", "y", "z"):
            ax.__getattribute__(f"{axis_name}axis")._axinfo["grid"].update(
                color=GRID_COLOR, linestyle="dashed", linewidth=0.5, alpha=0.6)

        ax.xaxis.pane.fill = False; ax.yaxis.pane.fill = False; ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor(GRID_COLOR)
        ax.yaxis.pane.set_edgecolor(GRID_COLOR)
        ax.zaxis.pane.set_edgecolor(GRID_COLOR)

        # 轴线
        ax.plot([-r, r], [0, 0], [0, 0], color=AXIS_X_COLOR, linewidth=2.0)
        ax.plot([0, 0], [-r, r], [0, 0], color=AXIS_Y_COLOR, linewidth=2.0)
        ax.plot([0, 0], [0, 0], [-r, r], color=AXIS_Z_COLOR, linewidth=2.0)

        # 箭头
        arr = r * 0.15
        for pos, color, dx, dy, dz in [
            ((r, 0, 0), AXIS_X_COLOR, arr, 0, 0),
            ((0, r, 0), AXIS_Y_COLOR, 0, arr, 0),
            ((0, 0, r), AXIS_Z_COLOR, 0, 0, arr),
        ]:
            ax.quiver(*pos, dx, dy, dz, color=color,
                      arrow_length_ratio=0.3, linewidth=1.5)

        ax.scatter([0], [0], [0], color="#ffffff", s=30, zorder=10)
        self._emit_status()

    def _emit_status(self) -> None:
        n = sum(1 for s in self._surfaces if s["visible"])
        self.status_message.emit(
            f"3D  曲面 {n}  "
            f"elev {self._ax.elev:.0f}°  azim {self._ax.azim:.0f}°  "
            f"范围 ±{self._range:.0f}"
        )


# ── 向后兼容别名 ──
Plot3DCanvas = Plot3D


# ═══════════════════════════════════════════════════════════════════════
#  Standalone test
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar

    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("Plot3D — 三维坐标系")
    win.resize(900, 700)

    canvas = Plot3D()
    status = QStatusBar()
    canvas.status_message.connect(lambda msg: status.showMessage(msg, 0))
    win.setStatusBar(status)
    win.setCentralWidget(canvas)

    canvas.add_surface("sin(x) * cos(y)", color="#e74c3c")
    canvas.add_surface("(x**2 + y**2) / 50", color="#3498db")

    win.show()
    sys.exit(app.exec())
