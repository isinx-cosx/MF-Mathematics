# -*- coding: utf-8 -*-
"""PlotWorkspace — 绘图工作区（全局滑块 + 函数框列表 + 画布）。

架构:
  全局滑块区    — 顶部，独立于函数框，每个参数一个滑块行
  函数框列表    — 可滚动的编号卡片，支持显式/隐式模式
  虚框添加按钮  — 底部 "＋ 添加函数"，与计算模式 calc 工作区一致
  右侧画布      — PlotCanvas
"""

from __future__ import annotations

import json, os, re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSlider, QVBoxLayout, QWidget,
)
from MF_UI.plot.basic.plot_canvas import PlotCanvas
from MF_UI.plot.basic.function_box import FunctionBox
from MF_UI.plot.plot_3d import Plot3D


def _load_plot_colors() -> list[str]:
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(root, "config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("plot", {}).get(
                    "colors",
                    ["#e74c3c", "#3498db", "#2ecc71", "#f39c12",
                     "#9b59b6", "#1abc9c", "#e67e22", "#e84393"],
                )
    except (json.JSONDecodeError, OSError):
        pass
    return ["#e74c3c", "#3498db", "#2ecc71"]


_COLORS = _load_plot_colors()


class PlotWorkspace(QWidget):
    """绘图模式工作区。"""

    # 模式名 → 内部标识（从 main_window 传入的标题中提取关键词）
    _MODE_KEYWORDS: list[tuple[str, str]] = [
        ("普通模式", "normal"),
        ("3D",        "3d"),
        ("复数",      "complex"),
        ("向量",      "vector"),
        ("任意做图",  "arbitrary"),
    ]

    @staticmethod
    def _detect_mode(title: str) -> str:
        """从标题字符串识别绘图模式。"""
        for keyword, mode_id in PlotWorkspace._MODE_KEYWORDS:
            if keyword in title:
                return mode_id
        return "normal"

    def __init__(self, title: str = "2D Plot", parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title
        self._mode = self._detect_mode(title)
        self._color_idx = 0
        self._next_index = 1
        self._boxes: list[FunctionBox] = []
        self._separators: list[QFrame] = []
        self._global_sliders: dict[str, tuple[QSlider, QLineEdit]] = {}
        self._updating_slider = False

        root = QHBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        # ── 左侧面板 ──
        left = QWidget()
        left.setFixedWidth(340)
        left.setObjectName("plot_left_panel")
        ll = QVBoxLayout(left)
        ll.setSpacing(4); ll.setContentsMargins(12, 12, 12, 12)

        # 标题 + 描述
        title_label = QLabel(title)
        title_label.setObjectName("plot_title_label")
        desc_map = {
            "normal": "支持：显式 y=f(x)、隐式 f(x,y)=0、自然书写、参数滑块",
            "3d": "支持：三维曲面 z=f(x,y)、参数滑块、旋转/缩放/平移",
            "complex": "支持：复平面 RGB 域着色（功能预留）",
            "vector": "支持：2D/3D 向量场绘制（功能预留）",
        }
        desc_label = QLabel(desc_map.get(self._mode, desc_map["normal"]))
        desc_label.setObjectName("plot_desc_label")
        ll.addWidget(title_label); ll.addWidget(desc_label)

        self._status = QLabel("就绪")
        self._status.setStyleSheet("font-size:11px;"); self._status.setWordWrap(True)
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

        # ── 全局滑块区 ──
        self._slider_section = QWidget()
        self._slider_section.hide()
        self._slider_layout = QVBoxLayout(self._slider_section)
        self._slider_layout.setSpacing(2); self._slider_layout.setContentsMargins(4, 4, 4, 4)

        slider_header = QHBoxLayout()
        slider_header.addWidget(QLabel("参数滑块"))
        slider_header.addStretch()
        self._detect_params_btn = QPushButton("检测参数")
        self._detect_params_btn.setStyleSheet(
            "QPushButton { background: #f1f5f9; border: 1px solid #cbd5e1;"
            " border-radius: 3px; padding: 2px 8px; font-size: 11px; color: #475569; }"
            "QPushButton:hover { background: #e2e8f0; }")
        self._detect_params_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._detect_params_btn.clicked.connect(self._on_detect_params)
        self._detect_params_btn.setToolTip("从所有函数框检测未知参数")
        slider_header.addWidget(self._detect_params_btn)
        self._slider_layout.addLayout(slider_header)
        self._list_layout.addWidget(self._slider_section)

        # 分隔线
        self._slider_sep = QFrame()
        self._slider_sep.setFixedHeight(1)
        self._slider_sep.setStyleSheet("background: #e2e8f0; border: none;")
        self._slider_sep.hide()
        self._list_layout.addWidget(self._slider_sep)

        # 虚框添加按钮
        self._btn_add = QPushButton("＋ 添加函数")
        self._btn_add.setFlat(True); self._btn_add.setFixedHeight(50)
        self._btn_add.setObjectName("plot_btn_add")
        self._btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add.clicked.connect(self._add)
        self._list_layout.addWidget(self._btn_add)

        card_inner = QVBoxLayout(card)
        card_inner.setContentsMargins(0, 0, 0, 0); card_inner.addWidget(scroll)
        ll.addWidget(card, 1)
        root.addWidget(left)

        # ── 右侧画布（2D / 3D 使用真实画布，其余模式占位）──
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
            placeholder = self._make_placeholder(
                title, "功能开发中，敬请期待...")
            root.addWidget(placeholder, 1)
            self._canvas = None
            self._canvas_3d = None

        self._add()

    @property
    def canvas(self):
        return self._canvas

    def _make_placeholder(self, title: str, desc: str) -> QWidget:
        """创建占位页面。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        frame = QFrame()
        frame.setObjectName("placeholder_frame")
        frame.setMinimumHeight(400)
        inner = QVBoxLayout(frame)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.setSpacing(12)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("page_title")
        title_lbl.setStyleSheet("font-size: 20px; font-weight: 600;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(title_lbl)

        desc_lbl = QLabel(desc)
        desc_lbl.setObjectName("page_desc")
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(desc_lbl)

        layout.addWidget(frame)
        return page

    # ── 全局滑块 ──────────────────────────────────────────

    def _on_detect_params(self) -> None:
        """从所有函数框检测未知参数，引导用户添加滑块。"""
        all_params: set[str] = set()
        for b in self._boxes:
            if b.expr:
                all_params |= b.detected_params
        existing = set(self._global_sliders.keys())
        new_params = all_params - existing

        if new_params:
            for name in sorted(new_params):
                self._add_global_slider(name)
            self._status.setText(f"已添加参数: {', '.join(sorted(new_params))}")
        else:
            self._status.setText("未检测到新参数")

    def _add_global_slider(self, name: str) -> None:
        if name in self._global_sliders:
            return

        row = QHBoxLayout(); row.setSpacing(4)
        lbl = QLabel(f"{name} ="); lbl.setStyleSheet("font-size:12px; color:#475569;")
        lbl.setFixedWidth(30); row.addWidget(lbl)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-1000, 1000); slider.setValue(100)  # default 1.0
        row.addWidget(slider, 1)

        edit = QLineEdit("1.00")
        edit.setFixedWidth(52)
        edit.setObjectName("slider_edit")
        row.addWidget(edit)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(20, 20)
        del_btn.setObjectName("slider_del_btn")
        del_btn.setToolTip(f"删除参数 '{name}' 的滑块")
        del_btn.clicked.connect(lambda: self._remove_global_slider(name))
        row.addWidget(del_btn)

        slider.valueChanged.connect(
            lambda v, n=name, e=edit: self._on_global_slider(n, v, e))
        edit.editingFinished.connect(
            lambda s=slider, e=edit, n=name: self._on_global_edit(s, e, n))

        self._slider_layout.addLayout(row)
        self._global_sliders[name] = (slider, edit)

        self._slider_section.show()
        self._slider_sep.show()
        self._refresh_all_param_hints()
        self._rebuild_curves()

    def _remove_global_slider(self, name: str) -> None:
        pair = self._global_sliders.pop(name, None)
        if not pair:
            return
        slider, edit = pair
        for i in range(self._slider_layout.count()):
            item = self._slider_layout.itemAt(i)
            if item and item.layout():
                lbl_item = item.layout().itemAt(0)
                if lbl_item and lbl_item.widget() and lbl_item.widget().text() == f"{name} =":
                    _clear_layout(item.layout())
                    self._slider_layout.removeItem(item)
                    break
        slider.deleteLater(); edit.deleteLater()

        if len(self._global_sliders) <= 1:  # only header row left
            # remove header widgets and hide
            pass
        if not self._global_sliders:
            self._slider_section.hide()
            self._slider_sep.hide()
        self._refresh_all_param_hints()
        self._rebuild_curves()

    def _on_global_slider(self, name: str, value: int, edit: QLineEdit) -> None:
        if self._updating_slider:
            return
        v = value / 100.0
        edit.blockSignals(True); edit.setText(f"{v:.2f}"); edit.blockSignals(False)
        self._rebuild_curves()

    def _on_global_edit(self, slider: QSlider, edit: QLineEdit, name: str) -> None:
        if self._updating_slider:
            return
        try:
            v = float(edit.text()); v = max(-10.0, min(10.0, v))
            edit.setText(f"{v:.2f}")
            slider.blockSignals(True)
            slider.setValue(int(round(v * 100)))
            slider.blockSignals(False)
            self._rebuild_curves()
        except ValueError:
            edit.setText("0.00")

    def _global_params(self) -> dict[str, float]:
        return {k: s.value() / 100.0 for k, (s, _) in self._global_sliders.items()}

    def _refresh_all_param_hints(self) -> None:
        existing = set(self._global_sliders.keys())
        for b in self._boxes:
            b.refresh_param_hint(existing)

    # ── 函数框管理 ────────────────────────────────────────

    def clear_all(self) -> None:
        for b in self._boxes[:]:
            self._on_box_removed(b)

    def _add(self) -> None:
        color = _COLORS[self._color_idx % len(_COLORS)]
        self._color_idx += 1
        box = FunctionBox(
            index=self._next_index, color=color, mode=self._mode, parent=self)
        self._next_index += 1

        box.changed.connect(lambda: self._on_box_changed())
        box.removed.connect(self._on_box_removed)

        insert_idx = self._list_layout.indexOf(self._btn_add)

        if self._boxes:
            sep = QFrame(); sep.setFixedHeight(1)
            sep.setStyleSheet("background: #e2e8f0; border: none;")
            self._list_layout.insertWidget(insert_idx, sep)
            self._separators.append(sep)
            insert_idx += 1

        self._list_layout.insertWidget(insert_idx, box)
        self._boxes.append(box)
        self._update_delete_buttons()
        self._rebuild_curves()

    def _on_box_removed(self, box: FunctionBox) -> None:
        if len(self._boxes) <= 1:
            return
        if box not in self._boxes:
            return

        self._boxes.remove(box)
        layout_idx = self._list_layout.indexOf(box)
        if layout_idx > 0:
            above = self._list_layout.itemAt(layout_idx - 1)
            if above and above.widget() and isinstance(above.widget(), QFrame):
                w = above.widget()
                if w in self._separators:
                    self._separators.remove(w)
                    self._list_layout.removeWidget(w)
                    w.deleteLater()

        self._list_layout.removeWidget(box)
        box.deleteLater()
        self._update_delete_buttons()
        self._refresh_all_param_hints()
        self._rebuild_curves()

    def _on_box_changed(self) -> None:
        self._refresh_all_param_hints()
        self._rebuild_curves()

    def _rebuild_curves(self) -> None:
        gparams = self._global_params()

        # ── 收集用户定义函数 ──
        _KNOWN = {'sin','cos','tan','cot','sec','csc','sinh','cosh','tanh','coth',
                  'asin','acos','atan','arcsin','arccos','arctan',
                  'ln','log','log10','sqrt','exp','abs','ceiling','floor',
                  'diff','integrate','limit','Sum','sum','solve',
                  'e','pi','E','Pi','oo','nan','I'}
        definitions: dict[str, str] = {}
        for b in self._boxes:
            if not b.is_visible or not b.expr:
                continue
            if b.is_derivative:
                continue
            raw = b._input.text().strip()
            m = re.match(r"^([a-zA-Z]\w*)\s*\(\s*([a-zA-Z])\s*\)\s*=\s*(.+)$", raw)
            if m:
                name = m.group(1)
                if name not in _KNOWN:
                    definitions[name] = b.expr

        # ── 3D 模式 ──
        if self._mode == "3d" and self._canvas_3d is not None:
            # 同步函数框列表到 3D 曲面列表
            self._canvas_3d.clear_surfaces()
            for b in self._boxes:
                if not b.expr:
                    continue
                box_params = {k: v for k, v in gparams.items()
                              if k in b.detected_params}
                resolved = b.expr
                if b.is_derivative and b.referenced_function:
                    r = b.resolve_derivative(definitions)
                    if r:
                        resolved = r
                idx = self._canvas_3d.add_surface(
                    resolved, color=b.color, params=box_params)
                # 同步可见性
                self._canvas_3d.set_visible(idx, b.is_visible)
            return

        # ── 2D 模式 ──
        if self._canvas is None:
            return
        self._canvas.clear_functions()
        for b in self._boxes:
            if not b.is_visible or not b.expr:
                continue
            box_params = {k: v for k, v in gparams.items()
                          if k in b.detected_params}
            if b.is_derivative and b.referenced_function:
                resolved = b.resolve_derivative(definitions)
                if resolved:
                    self._canvas.add_function(
                        resolved, color=b.color, label=b.label,
                        var=b.independent_var, params=box_params,
                        implicit=False)
                    continue
            self._canvas.add_function(
                b.expr, color=b.color, label=b.label,
                var=b.independent_var, params=box_params,
                implicit=(b.expr_type == "implicit"))

    def _update_delete_buttons(self) -> None:
        visible = len(self._boxes) > 1
        for b in self._boxes:
            b._del_btn.setVisible(visible)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear_layout(item.layout())
