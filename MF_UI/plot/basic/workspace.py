# -*- coding: utf-8 -*-
"""PlotWorkspace — 绘图工作区（函数框 + 滑块框 + 画布）。"""

from __future__ import annotations

import json, os, re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from MF_UI.plot.basic.plot_canvas import PlotCanvas
from MF_UI.plot.basic.function_box import FunctionBox
from MF_UI.plot.basic.slider_function_box import SliderFunctionBox
from MF_UI.plot.plot_3d import Plot3D
from MF_UI.plot.plot_3d.function_box import FunctionBox as FB3D
from MF_UI.plot.complex.workspace import ComplexWorkspace


def _load_plot_colors() -> list[str]:
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(root, "config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("plot", {}).get("colors",
                    ["#e74c3c", "#3498db", "#2ecc71", "#f39c12",
                     "#9b59b6", "#1abc9c", "#e67e22", "#e84393"])
    except Exception:
        pass
    return ["#e74c3c", "#3498db", "#2ecc71"]


_COLORS = _load_plot_colors()


class PlotWorkspace(QWidget):
    """绘图模式工作区。"""

    _MODE_KEYWORDS: list[tuple[str, str]] = [
        ("普通模式", "normal"), ("3D", "3d"),
        ("复数", "complex"), ("向量", "vector"), ("任意做图", "arbitrary"),
    ]

    @staticmethod
    def _detect_mode(title: str) -> str:
        for kw, mid in PlotWorkspace._MODE_KEYWORDS:
            if kw in title: return mid
        return "normal"

    def __init__(self, title: str = "2D Plot", parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title
        self._mode = self._detect_mode(title)
        self._color_idx = 0
        self._next_index = 1
        self._boxes: list[QWidget] = []          # FunctionBox | SliderFunctionBox
        self._sliders: dict[str, SliderFunctionBox] = {}  # param_name → slider
        self._separators: list[QFrame] = []

        root = QHBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        self._status = QLabel("就绪")
        self._status.setStyleSheet("font-size:11px;"); self._status.setWordWrap(True)

        # ── 复数模式：整个区域使用 ComplexWorkspace ──
        if self._mode == "complex":
            self._complex = ComplexWorkspace()
            self._complex.status_message.connect(self._status.setText)
            root.addWidget(self._complex, 1)
            self._canvas = None; self._canvas_3d = None
            return

        # ── 左侧面板 ──
        left = QWidget()
        left.setFixedWidth(340); left.setObjectName("plot_left_panel")
        ll = QVBoxLayout(left)
        ll.setSpacing(4); ll.setContentsMargins(12, 12, 12, 12)

        title_label = QLabel(title); title_label.setObjectName("plot_title_label")
        desc_map = {
            "normal": "支持：显式 y=f(x)、隐式 f(x,y)=0、参数滑块",
            "3d": "支持：三维曲面 z=f(x,y)",
            "vector": "支持：2D/3D 向量场绘制（功能预留）",
        }
        desc_label = QLabel(desc_map.get(self._mode, desc_map["normal"]))
        desc_label.setObjectName("plot_desc_label")
        ll.addWidget(title_label); ll.addWidget(desc_label)

        ll.addWidget(self._status)

        # ── 卡片容器 ──
        card = QFrame(); card.setObjectName("plot_work_card")
        scroll = QScrollArea(card)
        scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setObjectName("plotScroll")

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(0); self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_container)

        # 虚框添加按钮
        self._btn_add = QPushButton("＋ 添加函数")
        self._btn_add.setFlat(True); self._btn_add.setFixedHeight(50)
        self._btn_add.setObjectName("plot_btn_add")
        self._btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add.clicked.connect(self._add_function_box)
        self._list_layout.addWidget(self._btn_add)

        card_inner = QVBoxLayout(card)
        card_inner.setContentsMargins(0, 0, 0, 0); card_inner.addWidget(scroll)
        ll.addWidget(card, 1)
        root.addWidget(left)

        # ── 右侧画布 ──
        if self._mode == "normal":
            self._canvas = PlotCanvas()
            self._canvas.status_message.connect(self._status.setText)
            root.addWidget(self._canvas, 1)
            self._canvas_3d = None
        elif self._mode == "3d":
            self._canvas_3d = Plot3D()
            self._canvas_3d.status_message.connect(self._status.setText)
            root.addWidget(self._canvas_3d, 1)
            self._canvas = None
        else:
            root.addWidget(self._make_placeholder(title, "功能开发中，敬请期待..."), 1)
            self._canvas = None; self._canvas_3d = None

        if self._mode in ("normal", "3d"):
            self._add_function_box()

    @property
    def canvas(self):
        return self._canvas

    def _make_placeholder(self, title: str, desc: str) -> QWidget:
        page = QWidget()
        l = QVBoxLayout(page); l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFrame(); f.setObjectName("placeholder_frame"); f.setMinimumHeight(400)
        inner = QVBoxLayout(f); inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.setSpacing(12)
        t = QLabel(title); t.setObjectName("page_title")
        t.setStyleSheet("font-size:20px;font-weight:600;"); t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(t)
        d = QLabel(desc); d.setObjectName("page_desc"); d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(d)
        l.addWidget(f)
        return page

    # ── 函数框管理 ──────────────────────────────────────────

    def _add_function_box(self) -> None:
        if self._mode not in ("normal", "3d"): return
        color = _COLORS[self._color_idx % len(_COLORS)]
        self._color_idx += 1
        cls = FB3D if self._mode == "3d" else FunctionBox
        box = cls(index=self._next_index, color=color, mode=self._mode, parent=self)
        self._next_index += 1

        box.changed.connect(self._on_changed)
        box.removed.connect(self._on_box_removed)
        if hasattr(box, 'param_added'):
            box.param_added.connect(self._add_slider_box)

        self._insert_widget(box)
        self._sync_global_sliders()

    def _sync_global_sliders(self) -> None:
        """通知所有函数框当前全局已有的滑块名称。"""
        names = set(self._sliders.keys())
        for b in self._boxes:
            if isinstance(b, FunctionBox):
                b.set_existing_sliders(names)

    def _add_slider_box(self, param_name: str) -> None:
        if param_name in self._sliders: return
        color = _COLORS[self._color_idx % len(_COLORS)]
        self._color_idx += 1
        sb = SliderFunctionBox(self._next_index, param_name, color=color, parent=self)
        self._next_index += 1

        sb.valueChanged.connect(self._on_slider_changed)
        sb.removed.connect(self._on_slider_removed)
        self._sliders[param_name] = sb

        self._insert_widget(sb)
        self._sync_global_sliders()

    def _insert_widget(self, w: QWidget) -> None:
        idx = self._list_layout.indexOf(self._btn_add)
        if self._boxes:
            sep = QFrame(); sep.setFixedHeight(1)
            sep.setStyleSheet("background: #e2e8f0; border: none;")
            self._list_layout.insertWidget(idx, sep)
            self._separators.append(sep)
            idx += 1
        self._list_layout.insertWidget(idx, w)
        self._boxes.append(w)
        self._update_delete_buttons()
        self._rebuild_curves()

    def _on_changed(self) -> None:
        self._rebuild_curves()

    def _on_slider_changed(self, _name: str, _value: float) -> None:
        self._rebuild_curves()

    def _on_box_removed(self, box: FunctionBox) -> None:
        if len(self._boxes) <= 1: return
        if box not in self._boxes: return
        self._boxes.remove(box)
        self._remove_widget(box)
        self._rebuild_curves()

    def _on_slider_removed(self, sb: SliderFunctionBox) -> None:
        name = sb.param_name
        self._sliders.pop(name, None)
        if sb in self._boxes: self._boxes.remove(sb)
        # 通知关联的函数框：该参数可重新添加
        for b in self._boxes:
            if isinstance(b, FunctionBox):
                b.mark_param_removed(name)
        self._remove_widget(sb)
        self._sync_global_sliders()
        self._rebuild_curves()

    def _remove_widget(self, w: QWidget) -> None:
        layout_idx = self._list_layout.indexOf(w)
        if layout_idx > 0:
            above = self._list_layout.itemAt(layout_idx - 1)
            if above and above.widget() and isinstance(above.widget(), QFrame):
                sep = above.widget()
                if sep in self._separators:
                    self._separators.remove(sep)
                    self._list_layout.removeWidget(sep)
                    sep.deleteLater()
        self._list_layout.removeWidget(w)
        w.deleteLater()
        self._update_delete_buttons()

    def _update_delete_buttons(self) -> None:
        visible = len(self._boxes) > 1
        for b in self._boxes:
            if hasattr(b, '_del_btn'):
                b._del_btn.setVisible(visible)

    # ── 重绘 ─────────────────────────────────────────────────

    def _collect_params(self) -> dict[str, float]:
        return {name: sb.value for name, sb in self._sliders.items() if sb.is_visible}

    def _rebuild_curves(self) -> None:
        gparams = self._collect_params()

        _KNOWN = {'sin','cos','tan','cot','sec','csc','sinh','cosh','tanh','coth',
                  'asin','acos','atan','arcsin','arccos','arctan',
                  'ln','log','log10','sqrt','exp','abs','ceiling','floor',
                  'diff','integrate','limit','Sum','sum','solve',
                  'e','pi','E','Pi','oo','nan','I'}
        definitions: dict[str, str] = {}
        for b in self._boxes:
            if not isinstance(b, FunctionBox): continue
            if not b.is_visible or not b.expr: continue
            if b.is_derivative: continue
            raw = b._input.text().strip()
            m = re.match(r"^([a-zA-Z]\w*)\s*\(\s*([a-zA-Z])\s*\)\s*=\s*(.+)$", raw)
            if m:
                name = m.group(1)
                if name not in _KNOWN: definitions[name] = b.expr

        # 3D
        if self._mode == "3d" and self._canvas_3d is not None:
            self._canvas_3d.clear_surfaces()
            for b in self._boxes:
                if not isinstance(b, FB3D): continue
                if not b.is_visible or not b.exprs: continue
                if len(b.exprs) == 1:
                    self._canvas_3d.add_surface(b.exprs[0], color=b.color)
                elif len(b.exprs) == 3:
                    for s in b.exprs:
                        self._canvas_3d.add_surface(s, color=b.color)
            return

        # 2D
        if self._canvas is None: return
        self._canvas.clear_functions()
        for b in self._boxes:
            if not isinstance(b, FunctionBox): continue
            if not b.is_visible or not b.expr: continue
            box_params = dict(gparams)
            if b.is_derivative and b.referenced_function:
                resolved = b.resolve_derivative(definitions)
                if resolved:
                    self._canvas.add_function(resolved, color=b.color, label=b.label,
                        var=b.independent_var, params=box_params, implicit=False)
                    continue
            self._canvas.add_function(b.expr, color=b.color, label=b.label,
                var=b.independent_var, params=box_params,
                implicit=(b.expr_type == "implicit"))
