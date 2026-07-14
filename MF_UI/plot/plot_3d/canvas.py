# -*- coding: utf-8 -*-
"""Plot3D — 三维坐标系控件（Matplotlib mplot3d + PySide6）。

特性:
  - X/Y/Z 轴（红/绿/蓝，带箭头和标签）
  - 网格线（灰色虚线，覆盖三个墙面）
  - 刻度标签（自动步长，两位小数）
  - 鼠标拖拽旋转 + 滚轮缩放（NavigationToolbar2QT）
  - 多曲面叠加支持
  - 配置从 config.json 读取（可选回退）
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

AXIS_X_COLOR   = _AX.get("axis_3d_x", "#e74c3c")   # X 红色
AXIS_Y_COLOR   = _AX.get("axis_3d_y", "#2ecc71")   # Y 绿色
AXIS_Z_COLOR   = _AX.get("axis_3d_z", "#3498db")   # Z 蓝色
GRID_COLOR     = _AX.get("grid_color",   "#888888")
BG_COLOR       = _AX.get("bg_color",     "#1e1e2e")
TEXT_COLOR     = _AX.get("text_color",   "#cccccc")
LABEL_FONT_SIZE = _AX.get("label_font_size", 10)
TICK_FONT_SIZE  = _AX.get("tick_font_size", 8)
AXIS_ARROW_SIZE = 1.2  # 箭头相对轴长比例

# tick 步长查找表
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


class Plot3D(QWidget):
    """三维坐标系控件。

    信号:
      status_message(str) — 状态栏消息
    """

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._surfaces: list[dict] = []
        self._range = 10.0  # 默认坐标轴范围 [-range, range]

        # ── Figure + 3D Axes ──
        self._fig = Figure(figsize=(8, 6), dpi=100, facecolor=BG_COLOR)
        self._ax = self._fig.add_subplot(111, projection="3d")
        self._ax.set_facecolor(BG_COLOR)
        self._ax.view_init(elev=25, azim=-50)

        # 初始坐标轴范围
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

        # ── 绘制初始坐标系 ──
        self._draw_axes()
        self._canvas.draw_idle()

    # ═══════════════════════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════════════════════

    def set_axis_labels(self, xlabel: str = "x",
                        ylabel: str = "y", zlabel: str = "z") -> None:
        """设置坐标轴标签。"""
        self._ax.set_xlabel(xlabel, color=TEXT_COLOR, fontsize=LABEL_FONT_SIZE)
        self._ax.set_ylabel(ylabel, color=TEXT_COLOR, fontsize=LABEL_FONT_SIZE)
        self._ax.set_zlabel(zlabel, color=TEXT_COLOR, fontsize=LABEL_FONT_SIZE)
        self._canvas.draw_idle()

    def set_view(self, elev: float = 25, azim: float = -50) -> None:
        """设置视角（仰角、方位角）。"""
        self._ax.view_init(elev=elev, azim=azim)
        self._canvas.draw_idle()

    def set_range(self, rng: float) -> None:
        """设置坐标轴范围 [-rng, rng]。"""
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

    def add_surface(self, expr: str, color: str = "#3498db",
                    params: dict | None = None,
                    resolution: int = 80) -> int:
        """添加曲面 z=f(x,y)，返回索引。"""
        import sympy as sp
        idx = len(self._surfaces)
        self._surfaces.append({
            "expr": expr, "color": color, "visible": True,
            "params": params or {},
        })
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

            self._ax.plot_surface(X, Y, Z, alpha=0.85, color=color,
                                  linewidth=0, antialiased=True, shade=True)
            self._canvas.draw_idle()
        except Exception:
            pass
        self._emit_status()
        return idx

    def clear_surfaces(self) -> None:
        """移除所有曲面（不清坐标系）。"""
        self.clear()

    # ═══════════════════════════════════════════════════════════════
    #  Internal — 坐标轴绘制
    # ═══════════════════════════════════════════════════════════════

    def _draw_axes(self) -> None:
        """绘制/重绘三维坐标系（轴 + 网格 + 刻度 + 箭头）。"""
        ax = self._ax
        r = self._range
        step = _nice_step(r * 2)

        # ── 轴标签 ──
        ax.set_xlabel("x", color=AXIS_X_COLOR, fontsize=LABEL_FONT_SIZE, fontweight="bold")
        ax.set_ylabel("y", color=AXIS_Y_COLOR, fontsize=LABEL_FONT_SIZE, fontweight="bold")
        ax.set_zlabel("z", color=AXIS_Z_COLOR, fontsize=LABEL_FONT_SIZE, fontweight="bold")

        # ── 刻度 ──
        ticks = np.arange(-r, r + step * 0.5, step)
        ticks = ticks[np.abs(ticks) <= r]
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.set_zticks(ticks)

        # 刻度标签格式化
        def _fmt(v, _):
            if abs(v) < 1e-12:
                return "0"
            return f"{v:.2f}".rstrip("0").rstrip(".")

        ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt))
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(_fmt))
        ax.zaxis.set_major_formatter(ticker.FuncFormatter(_fmt))

        # 刻度颜色
        ax.tick_params(axis="x", colors=AXIS_X_COLOR, labelsize=TICK_FONT_SIZE)
        ax.tick_params(axis="y", colors=AXIS_Y_COLOR, labelsize=TICK_FONT_SIZE)
        ax.tick_params(axis="z", colors=AXIS_Z_COLOR, labelsize=TICK_FONT_SIZE)

        # ── 网格线（灰色虚线，三面墙）──
        ax.xaxis._axinfo["grid"].update(
            color=GRID_COLOR, linestyle="dashed", linewidth=0.5, alpha=0.6)
        ax.yaxis._axinfo["grid"].update(
            color=GRID_COLOR, linestyle="dashed", linewidth=0.5, alpha=0.6)
        ax.zaxis._axinfo["grid"].update(
            color=GRID_COLOR, linestyle="dashed", linewidth=0.5, alpha=0.6)

        # ── 面板颜色 ──
        ax.xaxis.pane.fill = False
        ax.yaxis.pane.fill = False
        ax.zaxis.pane.fill = False
        ax.xaxis.pane.set_edgecolor(GRID_COLOR)
        ax.yaxis.pane.set_edgecolor(GRID_COLOR)
        ax.zaxis.pane.set_edgecolor(GRID_COLOR)

        # ── 轴线加粗 ──
        ax.plot([-r, r], [0, 0], [0, 0], color=AXIS_X_COLOR, linewidth=2.0)
        ax.plot([0, 0], [-r, r], [0, 0], color=AXIS_Y_COLOR, linewidth=2.0)
        ax.plot([0, 0], [0, 0], [-r, r], color=AXIS_Z_COLOR, linewidth=2.0)

        # ── 箭头（quiver）──
        arr_len = r * 0.15
        ax.quiver(r, 0, 0, arr_len, 0, 0, color=AXIS_X_COLOR,
                  arrow_length_ratio=0.3, linewidth=1.5)
        ax.quiver(0, r, 0, 0, arr_len, 0, color=AXIS_Y_COLOR,
                  arrow_length_ratio=0.3, linewidth=1.5)
        ax.quiver(0, 0, r, 0, 0, arr_len, color=AXIS_Z_COLOR,
                  arrow_length_ratio=0.3, linewidth=1.5)

        # ── 原点球 ──
        ax.scatter([0], [0], [0], color="#ffffff", s=30, zorder=10)

        self._emit_status()

    def _emit_status(self) -> None:
        n = sum(1 for s in self._surfaces if s["visible"])
        self.status_message.emit(
            f"3D  曲面 {n}  "
            f"elev {self._ax.elev:.0f}°  azim {self._ax.azim:.0f}°  "
            f"范围 ±{self._range:.0f}"
        )


# ═══════════════════════════════════════════════════════════════════════
#  Backward compat alias
# ═══════════════════════════════════════════════════════════════════════

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

    # 测试曲面
    canvas.add_surface("sin(x) * cos(y)", color="#e74c3c")
    canvas.add_surface("(x**2 + y**2) / 50", color="#3498db")

    win.show()
    sys.exit(app.exec())
