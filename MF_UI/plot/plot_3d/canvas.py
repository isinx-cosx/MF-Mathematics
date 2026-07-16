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

from MF_UI.plot import mpl_setup  # noqa — 中文字体 + 后端初始化
import matplotlib
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

    def add_surface(self, expr_spec, color: str = "#3498db",
                    params: dict | None = None,
                    resolution: int | None = None) -> int:
        """添加曲面，支持显式/隐式/参数三种类型。

        Args:
            expr_spec: str（向后兼容，显式 z=f(x,y)）或 dict
                       {"type": "explicit", "expr": "..."}
                       {"type": "implicit", "expr": "f(x,y,z)=0"}
                       {"type": "parametric", "axis": "x"/"y"/"z", "expr": "f(u,v)"}
            color: 曲面颜色。
            params: 参数替换字典。
            resolution: 网格分辨率。
        """
        import sympy as sp
        idx = len(self._surfaces)
        entry = {
            "spec": expr_spec, "color": color,
            "params": params or {}, "visible": True,
            "surface_obj": None,
        }
        self._surfaces.append(entry)

        if resolution is None:
            resolution = _surface_resolution(self._range * 2)

        try:
            # 归一化 expr_spec
            if isinstance(expr_spec, str):
                expr_spec = {"type": "explicit", "expr": expr_spec}

            stype = expr_spec.get("type", "explicit")
            sexpr = expr_spec.get("expr", "")

            if stype == "parametric":
                # 参数曲面：ws._rebuild_curves 会分组调用
                self._add_parametric_partial(entry, expr_spec, color, params)
            elif stype == "implicit":
                self._add_implicit_surface(entry, sexpr, color, params, resolution)
            else:
                self._add_explicit_surface(entry, sexpr, color, params, resolution)

            self._canvas.draw_idle()
        except Exception:
            pass

        self._emit_status()
        return idx

    def _add_explicit_surface(self, entry: dict, expr: str, color: str,
                              params: dict | None, resolution: int) -> None:
        """绘制显式曲面 z = f(x,y)。"""
        import sympy as sp
        expr_sym = sp.sympify(expr)
        for k, v in (params or {}).items():
            expr_sym = expr_sym.subs(sp.Symbol(k), v)

        x_sym, y_sym = sp.Symbol("x"), sp.Symbol("y")
        if expr_sym.free_symbols - {x_sym, y_sym}:
            return

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

    def _add_implicit_surface(self, entry: dict, expr: str, color: str,
                              params: dict | None, resolution: int) -> None:
        """绘制隐式曲面 f(x,y,z)=0（采样 z 切片 + 等高线投影）。"""
        import sympy as sp
        expr_sym = sp.sympify(expr)
        for k, v in (params or {}).items():
            expr_sym = expr_sym.subs(sp.Symbol(k), v)

        x_sym, y_sym, z_sym = sp.Symbol("x"), sp.Symbol("y"), sp.Symbol("z")
        if expr_sym.free_symbols - {x_sym, y_sym, z_sym}:
            return

        r = self._range
        fn = sp.lambdify((x_sym, y_sym, z_sym), expr_sym, "numpy")

        # 在多个 z 层面采样
        n_z = 15
        xs = np.linspace(-r, r, resolution)
        ys = np.linspace(-r, r, resolution)
        zs = np.linspace(-r, r, n_z)
        X, Y = np.meshgrid(xs, ys)

        all_points = []
        for z_val in zs:
            Z_vals = fn(X, Y, z_val)
            if np.iscomplexobj(Z_vals):
                Z_vals = np.where(np.abs(Z_vals.imag) < 1e-10, Z_vals.real, np.nan)
            # 在 z=z_val 平面找到 f=0 的等高线点
            try:
                from matplotlib import pyplot as plt
                fig_temp = plt.figure()
                cs = plt.contour(X, Y, Z_vals, levels=[0])
                plt.close(fig_temp)
                for seg_set in cs.allsegs[0]:
                    for seg in seg_set:
                        for px, py in seg:
                            all_points.append([px, py, z_val])
            except Exception:
                pass

        if len(all_points) > 3:
            pts = np.array(all_points)
            self._ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                           c=color, s=2, alpha=0.5, marker='.')
            # 存储引用以便清除
            entry["surface_obj"] = self._ax.collections[-1] if self._ax.collections else None

    def _add_parametric_partial(self, entry: dict, spec: dict, color: str,
                                params: dict | None) -> None:
        """参数曲面的单条轴记录 — 实际绘制由 add_parametric_surface 完成。"""
        # 此为占位 — 完整参数曲面由 rebuild 阶段分组处理
        pass

    def add_parametric_surface(self, specs: list[dict], color: str = "#3498db",
                               resolution: int = 40) -> int:
        """添加参数曲面: x=f(u,v), y=g(u,v), z=h(u,v)。

        Args:
            specs: [{"axis":"x","expr":"..."}, {"axis":"y","expr":"..."}, {"axis":"z","expr":"..."}]
            color: 曲面颜色。
            resolution: 网格分辨率。
        """
        import sympy as sp
        idx = len(self._surfaces)

        # 提取各轴表达式
        axis_exprs = {}
        for s in specs:
            axis_exprs[s.get("axis", "")] = s.get("expr", "")

        if len(axis_exprs) < 2:
            return idx  # 参数方程至少需要2个分量

        x_expr = axis_exprs.get("x", "u")
        y_expr = axis_exprs.get("y", "v")
        z_expr = axis_exprs.get("z", "0")

        try:
            u_sym, v_sym = sp.Symbol("u"), sp.Symbol("v")
            x_fn = sp.lambdify((u_sym, v_sym), sp.sympify(x_expr), "numpy")
            y_fn = sp.lambdify((u_sym, v_sym), sp.sympify(y_expr), "numpy")
            z_fn = sp.lambdify((u_sym, v_sym), sp.sympify(z_expr), "numpy")

            r = self._range * 0.7
            us = np.linspace(-r, r, resolution)
            vs = np.linspace(-r, r, resolution)
            U, V = np.meshgrid(us, vs)

            X = np.clip(x_fn(U, V), -1e6, 1e6)
            Y = np.clip(y_fn(U, V), -1e6, 1e6)
            Z = np.clip(z_fn(U, V), -1e6, 1e6)

            surf = self._ax.plot_surface(
                X, Y, Z, alpha=0.85, color=color,
                linewidth=0, antialiased=True, shade=True)

            entry = {
                "spec": {"type": "parametric", "exprs": [x_expr, y_expr, z_expr]},
                "color": color, "params": {}, "visible": True,
                "surface_obj": surf,
            }
            self._surfaces.append(entry)
            self._canvas.draw_idle()
        except Exception as e:
            self.status_message.emit(f"参数曲面错误: {e}")

        self._emit_status()
        return idx

    def update_surface(self, idx: int, expr_spec,
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
        if isinstance(expr_spec, str):
            expr_spec = {"type": "explicit", "expr": expr_spec}
        entry["spec"] = expr_spec
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
            spec = entry.get("spec", entry.get("expr", ""))
            if isinstance(spec, str):
                spec = {"type": "explicit", "expr": spec}

            stype = spec.get("type", "explicit")
            sexpr = spec.get("expr", "")

            if stype == "parametric":
                return  # 参数曲面由 add_parametric_surface 处理
            elif stype == "implicit":
                res = _surface_resolution(self._range * 2)
                self._add_implicit_surface(entry, sexpr, entry.get("color", "#3498db"),
                                          entry.get("params"), res)
            else:
                expr_sym = sp.sympify(sexpr)
                for k, v in (entry.get("params", {}) or {}).items():
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
