# -*- coding: utf-8 -*-
"""任意做图工作区 — 交互式几何作图（类似 GeoGebra）。

左侧面板:
  - 3×3 工具按钮（选择、点、线段、圆、向量、直线、椭圆、矩形、多边形）
  - 网格吸附开关
  - 图形列表
  - 视图控制按钮（适应所有、重置视图）

右侧:
  - GeometryCanvas（matplotlib 画布 + 鼠标交互）

键盘:
  - Delete  — 删除选中图形
  - Ctrl+Z  — 撤销
  - Ctrl+Y  — 重做
  - Escape  — 取消当前构建
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QAction
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QListWidget, QListWidgetItem, QMenu,
    QPushButton, QVBoxLayout, QWidget,
)

from MF_UI.plot.arbitrary.geometry_canvas import GeometryCanvas, Tool
from MF_UI.plot.arbitrary.shapes import GeometricShape, ShapeType
from MF_UI.plot.arbitrary.undo_manager import UndoManager


# ═══════════════════════════════════════════════════════════════
#  工具定义
# ═══════════════════════════════════════════════════════════════

_TOOLS: list[tuple[str, str, Tool]] = [
    ("↖",  "选择/移动", Tool.SELECT),
    ("✋",  "拖拽平移",  Tool.PAN),
    ("●",  "点",        Tool.POINT),
    ("─",  "线段",      Tool.SEGMENT),
    ("◯",  "圆",        Tool.CIRCLE),
    ("→",  "向量",      Tool.VECTOR),
    ("╱",  "直线",      Tool.LINE),
    ("⬮",  "椭圆",      Tool.ELLIPSE),
    ("▭",  "矩形",      Tool.RECTANGLE),
    ("⬠",  "多边形",    Tool.POLYGON),
]

_SHAPE_ICONS: dict[ShapeType, str] = {
    ShapeType.POINT:    "●",
    ShapeType.SEGMENT:  "─",
    ShapeType.CIRCLE:   "◯",
    ShapeType.VECTOR:   "→",
    ShapeType.LINE:     "╱",
    ShapeType.ELLIPSE:  "⬮",
    ShapeType.RECTANGLE: "▭",
    ShapeType.POLYGON:  "⬠",
}


# ═══════════════════════════════════════════════════════════════
#  样式
# ═══════════════════════════════════════════════════════════════

_PANEL_STYLE = "background:#f8fafc; border-right: 1px solid #e2e8f0;"
_TOOL_ACTIVE = """
    QPushButton {
        background: #3b82f6; color: #fff; border: 1px solid #2563eb;
        border-radius: 6px; padding: 6px 8px; font-size: 14px; font-weight: 600;
    }
"""
_TOOL_INACTIVE = """
    QPushButton {
        background: #f1f5f9; color: #475569; border: 1px solid #d1d5db;
        border-radius: 6px; padding: 6px 8px; font-size: 14px;
    }
    QPushButton:hover { background: #e2e8f0; }
"""
_BTN_PRIMARY = """
    QPushButton {
        background: #3b82f6; color: #fff; border: none;
        border-radius: 4px; padding: 6px 16px; font-size: 12px; font-weight: 500;
    }
    QPushButton:hover { background: #2563eb; }
"""
_BTN_SECONDARY = """
    QPushButton {
        background: #f1f5f9; color: #475569; border: 1px solid #d1d5db;
        border-radius: 4px; padding: 6px 16px; font-size: 12px;
    }
    QPushButton:hover { background: #e2e8f0; }
"""


# ═══════════════════════════════════════════════════════════════
#  ArbitraryWorkspace
# ═══════════════════════════════════════════════════════════════

class ArbitraryWorkspace(QWidget):
    """任意做图工作区 — 完整的几何作图环境。

    信号:
        status_message(str) — 状态/坐标消息
    """

    status_message = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # ── 核心组件 ──
        self._undo_mgr = UndoManager(max_depth=50)

        # ── 全局布局 ──
        root = QVBoxLayout(self)
        root.setSpacing(0); root.setContentsMargins(0, 0, 0, 0)

        body = QHBoxLayout()
        body.setSpacing(0); body.setContentsMargins(0, 0, 0, 0)

        # ── 画布（先创建，左侧面板 _build_left_panel 引用 self._canvas）──
        self._canvas = GeometryCanvas(self)

        # ── 左侧面板 ──
        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel)
        body.addWidget(self._canvas, 1)

        root.addLayout(body)

        # ── 底部状态栏 ──
        self._status_label = QLabel("选择/移动 — 点击图形选中，拖拽移动")
        self._status_label.setStyleSheet(
            "font-size: 11px; color: #64748b; background: #f1f5f9;"
            " padding: 4px 12px; border-top: 1px solid #e2e8f0;")
        self._status_label.setFixedHeight(26)
        root.addWidget(self._status_label)

        # ── 信号连接 ──
        self._canvas.status_message.connect(self._status_label.setText)
        self._canvas.status_message.connect(self.status_message.emit)
        self._canvas.shape_created.connect(self._on_shape_created)
        self._canvas.shape_selected.connect(self._on_canvas_select)
        self._canvas.shape_modified.connect(self._on_shape_modified)

        # ── 键盘快捷键 ──
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.status_message.emit("任意做图 — 就绪")

    # ── 左侧面板 ──────────────────────────────────────────────

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(240)
        panel.setStyleSheet(_PANEL_STYLE)
        ll = QVBoxLayout(panel)
        ll.setSpacing(6); ll.setContentsMargins(10, 10, 10, 10)

        # 标题
        title = QLabel("几何作图")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #0f172a; background: transparent;")
        ll.addWidget(title)

        # 分隔
        ll.addWidget(_sep())

        # 工具按钮（3 列网格）
        ll.addWidget(QLabel("工具"))
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        self._tool_btns: dict[int, QPushButton] = {}

        grid = QVBoxLayout()
        grid.setSpacing(4)
        for row_start in range(0, len(_TOOLS), 3):
            row = QHBoxLayout()
            row.setSpacing(4)
            for i in range(row_start, min(row_start + 3, len(_TOOLS))):
                icon, name, tool = _TOOLS[i]
                btn = QPushButton(f"{icon}")
                btn.setToolTip(name)
                btn.setCheckable(True)
                btn.setStyleSheet(_TOOL_INACTIVE)
                btn.setFixedSize(62, 36)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, t=tool: self._on_tool_changed(t))
                self._tool_group.addButton(btn, i)
                self._tool_btns[tool.value] = btn
                row.addWidget(btn)
            grid.addLayout(row)
        ll.addLayout(grid)

        # 默认选中"选择"
        self._tool_btns[Tool.SELECT.value].setChecked(True)
        self._tool_btns[Tool.SELECT.value].setStyleSheet(_TOOL_ACTIVE)
        self._active_tool_btn = self._tool_btns[Tool.SELECT.value]

        ll.addWidget(_sep())

        # 网格吸附
        self._snap_check = QCheckBox("吸附到网格")
        self._snap_check.setChecked(True)
        self._snap_check.setStyleSheet(
            "QCheckBox { font-size: 12px; color: #334155; background: transparent; }")
        self._snap_check.toggled.connect(self._canvas.set_grid_snap)
        ll.addWidget(self._snap_check)

        ll.addWidget(_sep())

        # 图形列表标题
        list_header = QHBoxLayout()
        list_header.addWidget(QLabel("图形列表"))
        list_header.addStretch()
        self._shape_count_lbl = QLabel("(0)")
        self._shape_count_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background: transparent;")
        list_header.addWidget(self._shape_count_lbl)
        ll.addLayout(list_header)

        # 图形列表
        self._shape_list = QListWidget()
        self._shape_list.setStyleSheet(
            "QListWidget { border: 1px solid #e2e8f0; border-radius: 4px;"
            " background: #fff; font-size: 11px; }"
            "QListWidget::item { padding: 3px 6px; }"
            "QListWidget::item:selected { background: #dbeafe; color: #1e40af; }")
        self._shape_list.setMinimumHeight(150)
        self._shape_list.currentRowChanged.connect(self._on_list_select)
        self._shape_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._shape_list.customContextMenuRequested.connect(self._on_context_menu)
        ll.addWidget(self._shape_list, 1)

        ll.addWidget(_sep())

        # 视图控制
        view_row = QHBoxLayout()
        view_row.setSpacing(4)
        btn_fit = QPushButton("适应所有")
        btn_fit.setStyleSheet(_BTN_PRIMARY)
        btn_fit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_fit.clicked.connect(self._canvas.fit_all)
        view_row.addWidget(btn_fit)

        btn_reset = QPushButton("重置视图")
        btn_reset.setStyleSheet(_BTN_SECONDARY)
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.clicked.connect(self._canvas.reset_view)
        view_row.addWidget(btn_reset)
        ll.addLayout(view_row)

        return panel

    # ── 工具切换 ──────────────────────────────────────────────

    def _on_tool_changed(self, tool: Tool) -> None:
        """工具按钮切换。"""
        # 恢复旧按钮样式
        if hasattr(self, "_active_tool_btn") and self._active_tool_btn:
            self._active_tool_btn.setStyleSheet(_TOOL_INACTIVE)
        # 高亮新按钮
        btn = self._tool_btns.get(tool.value)
        if btn:
            btn.setStyleSheet(_TOOL_ACTIVE)
            self._active_tool_btn = btn
        self._canvas.set_tool(tool)

    # ── 图形列表同步 ──────────────────────────────────────────

    def _on_shape_created(self, shape: GeometricShape) -> None:
        """图形创建 → 推入 undo + 刷新列表。"""
        self._undo_mgr.push(self._canvas.get_shapes())
        self._rebuild_list()

    def _on_shape_modified(self) -> None:
        """图形被修改 → 刷新列表（不推 undo，由调用方管理）。"""
        self._rebuild_list()

    def _on_canvas_select(self, sid: int | None) -> None:
        """画布选中 → 同步列表高亮。"""
        if sid is None:
            self._shape_list.clearSelection()
        else:
            for i in range(self._shape_list.count()):
                item = self._shape_list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == sid:
                    self._shape_list.setCurrentRow(i)
                    return

    def _on_list_select(self, row: int) -> None:
        """列表点击 → 同步画布选中。"""
        if row < 0:
            return
        item = self._shape_list.item(row)
        if item:
            sid = item.data(Qt.ItemDataRole.UserRole)
            self._canvas.set_selected(sid)

    def _rebuild_list(self) -> None:
        """从 shapes 重建图形列表。"""
        self._shape_list.blockSignals(True)
        self._shape_list.clear()
        shapes = self._canvas.get_shapes()
        for s in shapes:
            icon = _SHAPE_ICONS.get(s.shape_type, "?")
            text = f"{icon} {s.label}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            # 颜色标记
            item.setForeground(QColor(s.color) if s.visible else QColor("#94a3b8"))
            self._shape_list.addItem(item)
        self._shape_count_lbl.setText(f"({len(shapes)})")
        self._shape_list.blockSignals(False)

    # ── 右键菜单 ──────────────────────────────────────────────

    def _on_context_menu(self, pos) -> None:
        item = self._shape_list.itemAt(pos)
        if not item:
            return
        sid = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #fff; border: 1px solid #e2e8f0; border-radius: 6px;"
            " padding: 4px; }"
            "QMenu::item { padding: 6px 24px; font-size: 12px; border-radius: 3px; }"
            "QMenu::item:selected { background: #dbeafe; }")

        act_delete = menu.addAction("🗑 删除")
        act_color = menu.addAction("🎨 修改颜色")
        act_label = menu.addAction("✏ 修改标签")
        act_hide = menu.addAction("👁 隐藏/显示")

        action = menu.exec(self._shape_list.mapToGlobal(pos))
        if action is None:
            return

        if action == act_delete:
            self._delete_shape(sid)
        elif action == act_color:
            self._edit_color(sid)
        elif action == act_label:
            self._edit_label(sid)
        elif action == act_hide:
            shapes = self._canvas.get_shapes()
            for s in shapes:
                if s.id == sid:
                    s.visible = not s.visible
                    break
            self._canvas.load_shapes(shapes)
            self._rebuild_list()

    # ── 删除 / 编辑 ──────────────────────────────────────────

    def _delete_shape(self, sid: int) -> None:
        """删除图形（带 undo 记录）。"""
        self._undo_mgr.push(self._canvas.get_shapes())
        self._canvas.delete_shape(sid)
        self._rebuild_list()
        self.status_message.emit(f"已删除图形 #{sid}")

    def _edit_color(self, sid: int) -> None:
        """修改图形颜色。"""
        color = QColorDialog.getColor(title="选择颜色", parent=self)
        if color.isValid():
            self._undo_mgr.push(self._canvas.get_shapes())
            self._canvas.set_shape_color(sid, color.name())
            self._rebuild_list()
            self.status_message.emit(f"已修改颜色 → {color.name()}")

    def _edit_label(self, sid: int) -> None:
        """修改图形标签。"""
        label, ok = QInputDialog.getText(self, "修改标签", "新标签:")
        if ok and label.strip():
            self._undo_mgr.push(self._canvas.get_shapes())
            self._canvas.set_shape_label(sid, label.strip())
            self._rebuild_list()
            self.status_message.emit(f"已修改标签 → {label.strip()}")

    # ── 键盘快捷键 ────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        """全局键盘快捷键。"""
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key_Key_Delete or key == Qt.Key_Key_Backspace:
            sid = self._canvas.get_selected()
            if sid is not None:
                self._delete_shape(sid)
            return

        if key == Qt.Key_Key_Escape:
            self._canvas.cancel()
            self._canvas.set_selected(None)
            self._rebuild_list()
            return

        if key == Qt.Key_Key_Z and mods == Qt.KeyboardModifier.ControlModifier:
            self._undo()
            return

        if key == Qt.Key_Key_Y and mods == Qt.KeyboardModifier.ControlModifier:
            self._redo()
            return

        super().keyPressEvent(event)

    # ── Undo / Redo ──────────────────────────────────────────

    def _undo(self) -> None:
        prev = self._undo_mgr.undo(self._canvas.get_shapes())
        if prev is not None:
            self._canvas.load_shapes(prev)
            self._rebuild_list()
            self.status_message.emit("撤销 (Ctrl+Z)")
        else:
            self.status_message.emit("无可撤销操作")

    def _redo(self) -> None:
        next_ = self._undo_mgr.redo(self._canvas.get_shapes())
        if next_ is not None:
            self._canvas.load_shapes(next_)
            self._rebuild_list()
            self.status_message.emit("重做 (Ctrl+Y)")
        else:
            self.status_message.emit("无可重做操作")


# ── 辅助 ──────────────────────────────────────────────────

def _sep() -> QFrame:
    s = QFrame()
    s.setFixedHeight(1)
    s.setStyleSheet("background: #e2e8f0; border: none;")
    return s
