# -*- coding: utf-8 -*-
"""Plot3DCanvas — Matplotlib mplot3d 三维曲面/曲线绘制画布。

嵌入 PySide6，交互体验参考 GeoGebra 3D。
支持旋转（鼠标拖拽）、缩放（滚轮）、平移（Shift+拖拽）。
"""

from __future__ import annotations

import numpy as np
import sympy as sp
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure


class Plot3DCanvas(QWidget):
    """三维绘图画布 — Matplotlib mplot3d 嵌入 PySide6。

    信号:
      status_message(str) — 状态栏消息
    """

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._surfaces: list[dict] = []

        # ── Matplotlib Figure + 3D Axes ──
        self._fig = Figure(figsize=(8, 6), dpi=100)
        self._fig.set_tight_layout(True)
        self._ax = self._fig.add_subplot(111, projection="3d")

        # 初始视角（GeoGebra 3D 风格：30°仰角，-60°方位角）
        self._ax.view_init(elev=30, azim=-60)
        self._ax.set_xlabel("x")
        self._ax.set_ylabel("y")
        self._ax.set_zlabel("z")

        # ── Canvas + Toolbar ──
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas, 1)

        self._emit_status()

    # ═══════════════════════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════════════════════

    def add_surface(self, expr: str, color: str = "#3498db",
                    label: str = "", var: str = "x",
                    params: dict | None = None,
                    resolution: int = 100) -> int:
        """添加三维曲面 z = f(x, y)。

        Args:
            expr: sympy 兼容表达式（如 "sin(x)*cos(y)"）。
            color: 曲面颜色（十六进制）。
            label: 显示标签。
            var: 自变量名（默认 "x"，3D 模式自动使用 x, y）。
            params: 参数替换字典。
            resolution: 网格分辨率（默认 100×100）。

        Returns:
            曲面索引。
        """
        idx = len(self._surfaces)
        self._surfaces.append({
            "expr": expr, "color": color, "label": label,
            "visible": True, "params": params or {},
        })
        self._rebuild_surface(idx)
        self._emit_status()
        return idx

    def clear_surfaces(self) -> None:
        """移除所有曲面。"""
        self._ax.clear()
        self._ax.view_init(elev=30, azim=-60)
        self._ax.set_xlabel("x")
        self._ax.set_ylabel("y")
        self._ax.set_zlabel("z")
        self._surfaces.clear()
        self._canvas.draw_idle()

    def set_visible(self, idx: int, visible: bool) -> None:
        """切换曲面可见性。"""
        if 0 <= idx < len(self._surfaces):
            self._surfaces[idx]["visible"] = visible
            self._rebuild_all()

    # ═══════════════════════════════════════════════════════════════
    #  Internal
    # ═══════════════════════════════════════════════════════════════

    def _rebuild_surface(self, idx: int) -> None:
        """重建单个曲面。"""
        s = self._surfaces[idx]
        if not s["visible"]:
            return

        try:
            expr = sp.sympify(s["expr"])
        except Exception:
            return

        # 代入参数
        for k, v in s["params"].items():
            expr = expr.subs(sp.Symbol(k), v)

        # 检查剩余符号（仅允许 x, y）
        x_sym, y_sym = sp.Symbol("x"), sp.Symbol("y")
        remaining = expr.free_symbols - {x_sym, y_sym}
        if remaining:
            return

        # ── 自适应分辨率 ──
        try:
            xlim = self._ax.get_xlim()
            ylim = self._ax.get_ylim()
            rng = max(abs(xlim[1] - xlim[0]), abs(ylim[1] - ylim[0]), 10)
        except Exception:
            rng = 10
        res = max(40, min(150, int(150 * 20.0 / rng)))

        xs = np.linspace(-10, 10, res)
        ys = np.linspace(-10, 10, res)
        X, Y = np.meshgrid(xs, ys)

        try:
            fn = sp.lambdify((x_sym, y_sym), expr, "numpy")
            Z = fn(X, Y)
            if not isinstance(Z, np.ndarray):
                return
            if np.iscomplexobj(Z):
                Z = np.where(np.abs(Z.imag) < 1e-10, Z.real, np.nan)
        except Exception:
            return

        # 限制 Z 范围避免极端值
        Z = np.clip(Z, -1e6, 1e6)

        # 清除旧曲面（通过重新绘制所有曲面）
        self._rebuild_all()

    def _rebuild_all(self) -> None:
        """重建所有可见曲面。"""
        self._ax.clear()
        self._ax.view_init(elev=30, azim=-60)
        self._ax.set_xlabel("x")
        self._ax.set_ylabel("y")
        self._ax.set_zlabel("z")

        for s in self._surfaces:
            if not s["visible"]:
                continue
            try:
                expr = sp.sympify(s["expr"])
            except Exception:
                continue

            for k, v in s["params"].items():
                expr = expr.subs(sp.Symbol(k), v)

            x_sym, y_sym = sp.Symbol("x"), sp.Symbol("y")
            remaining = expr.free_symbols - {x_sym, y_sym}
            if remaining:
                continue

            try:
                xlim = self._ax.get_xlim()
                ylim = self._ax.get_ylim()
                rng = max(abs(xlim[1] - xlim[0]), abs(ylim[1] - ylim[0]), 10)
            except Exception:
                rng = 10
            res = max(40, min(150, int(150 * 20.0 / rng)))

            xs = np.linspace(-10, 10, res)
            ys = np.linspace(-10, 10, res)
            X, Y = np.meshgrid(xs, ys)

            try:
                fn = sp.lambdify((x_sym, y_sym), expr, "numpy")
                Z = fn(X, Y)
                if isinstance(Z, np.ndarray):
                    if np.iscomplexobj(Z):
                        Z = np.where(np.abs(Z.imag) < 1e-10, Z.real, np.nan)
                    Z = np.clip(Z, -1e6, 1e6)
                    import matplotlib.colors as mcolors
                    try:
                        base = mcolors.to_rgb(s["color"])
                        alpha = 0.85
                        face_color = (*base, alpha)
                    except ValueError:
                        face_color = None
                    self._ax.plot_surface(
                        X, Y, Z, alpha=0.85, color=face_color,
                        linewidth=0, antialiased=True, shade=True,
                        label=s.get("label", ""))
            except Exception:
                continue

        self._canvas.draw_idle()
        self._emit_status()

    def _emit_status(self) -> None:
        n = sum(1 for s in self._surfaces if s["visible"])
        self.status_message.emit(
            f"3D 视图  曲面 {n}  仰角 {self._ax.elev:.0f}°  方位 {self._ax.azim:.0f}°"
        )


# ═══════════════════════════════════════════════════════════════════════
#  Standalone test
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QStatusBar

    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle("Plot3DCanvas — 3D 测试")
    win.resize(900, 700)

    canvas = Plot3DCanvas()
    status = QStatusBar()
    canvas.status_message.connect(lambda msg: status.showMessage(msg, 0))
    win.setStatusBar(status)
    win.setCentralWidget(canvas)

    # 添加测试曲面
    canvas.add_surface("sin(x) * cos(y)", color="#e74c3c", label="sin(x)cos(y)")
    canvas.add_surface("x**2 + y**2", color="#3498db", label="x² + y²")

    win.show()
    sys.exit(app.exec())
