# -*- coding: utf-8 -*-
"""ExampleLibrary — 示例任务库面板，点击即可加载到工作区。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget, QGridLayout,
    QComboBox, QFrame,
)

from MF_Tutorial.engine import TutorialEngine
from MF_Tutorial.models import Tutorial, Example, Category

# ── 样式 ──────────────────────────────────────────────────────

_DIALOG_STYLE = "QDialog { background: #f8fafc; }"

_CARD_STYLE = """
    QFrame#example_card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
    }
    QFrame#example_card:hover {
        border-color: #3b82f6;
        background: #f8faff;
    }
"""

_TITLE_STYLE = "font-size: 14px; font-weight: 600; color: #0f172a; background: transparent;"
_EXPR_STYLE = (
    "font-size: 13px; color: #6366f1; font-family: 'Consolas', 'Monaco', monospace;"
    " background: #eef2ff; padding: 4px 8px; border-radius: 4px;"
    " margin-top: 6px;"
)
_DESC_STYLE = "font-size: 12px; color: #94a3b8; background: transparent; margin-top: 4px;"
_HEADER_STYLE = "font-size: 18px; font-weight: 700; color: #0f172a; background: transparent;"

_BTN_STYLE = """
    QPushButton {
        background: #3b82f6; color: #fff; border: none;
        border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: 500;
    }
    QPushButton:hover { background: #2563eb; }
"""

# ── 分类筛选 ──────────────────────────────────────────────────

_CATEGORY_FILTER: dict[str, str] = {
    "全部": "",
    "计算": "calculation",
    "绘图": "plot",
    "AI": "ai",
    "工具": "tools",
    "设置": "settings",
}


# ═══════════════════════════════════════════════════════════════
#  ExampleLibrary
# ═══════════════════════════════════════════════════════════════

class ExampleLibrary(QDialog):
    """示例任务库对话框。

    信号:
        example_selected: 用户选择了某个示例，传递 Example 对象。
    """

    example_selected = Signal(object)  # Example

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("示例任务库")
        self.resize(680, 480)
        self.setMinimumSize(500, 360)
        self.setStyleSheet(_DIALOG_STYLE)

        self._engine = TutorialEngine()
        self._engine.load_all()

        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 18, 20, 18)

        # 标题行
        hdr = QHBoxLayout()
        title = QLabel("示例任务库")
        title.setStyleSheet(_HEADER_STYLE)
        hdr.addWidget(title)
        hdr.addStretch()

        # 筛选
        filter_combo = QComboBox()
        filter_combo.addItems(list(_CATEGORY_FILTER.keys()))
        filter_combo.setStyleSheet(
            "QComboBox { border:1px solid #d1d5db; border-radius:6px;"
            " padding:6px 12px; font-size:13px; background:#fff; }"
        )
        filter_combo.currentTextChanged.connect(self._on_filter_changed)
        hdr.addWidget(QLabel("筛选："))
        hdr.addWidget(filter_combo)
        root.addLayout(hdr)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(14)
        self._grid.setContentsMargins(0, 8, 0, 8)
        scroll.setWidget(self._grid_container)
        root.addWidget(scroll, 1)

        # 底部
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── 内容 ──────────────────────────────────────────────

    def _refresh(self, category_filter: str = "") -> None:
        """刷新示例展示。"""
        # 清空
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 收集所有教程的示例
        tutorials = self._engine.get_all()
        if category_filter:
            tutorials = [
                t for t in tutorials
                if t.category == category_filter
            ]

        col = 0
        row = 0
        max_cols = 2

        for tut in tutorials:
            for i, example in enumerate(tut.examples):
                card = self._make_card(tut, example, i)
                self._grid.addWidget(card, row, col)

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

        # 如果没有示例
        if row == 0 and col == 0:
            empty = QLabel("该分类下暂无示例任务。")
            empty.setStyleSheet("font-size: 14px; color: #94a3b8;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(empty, 0, 0, 1, max_cols)

    def _make_card(self, tutorial: Tutorial, example: Example, index: int) -> QFrame:
        """创建一张示例卡片。"""
        card = QFrame()
        card.setObjectName("example_card")
        card.setStyleSheet(_CARD_STYLE)
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        # 标题
        title_lbl = QLabel(example.label)
        title_lbl.setStyleSheet(_TITLE_STYLE)
        layout.addWidget(title_lbl)

        # 表达式
        if example.expr:
            expr_lbl = QLabel(example.expr)
            expr_lbl.setStyleSheet(_EXPR_STYLE)
            expr_lbl.setWordWrap(True)
            layout.addWidget(expr_lbl)

        # 模式
        if example.mode:
            mode_lbl = QLabel(f"模式：{example.mode}")
            mode_lbl.setStyleSheet(_DESC_STYLE)
            layout.addWidget(mode_lbl)

        # 描述
        if example.description:
            desc_lbl = QLabel(example.description)
            desc_lbl.setStyleSheet(_DESC_STYLE)
            desc_lbl.setWordWrap(True)
            layout.addWidget(desc_lbl)

        # 加载按钮
        load_btn = QPushButton("加载到工作区 →")
        load_btn.setStyleSheet(_BTN_STYLE)
        load_btn.clicked.connect(lambda: self._on_select(tutorial.id, index))
        layout.addWidget(load_btn)

        return card

    # ── 事件 ──────────────────────────────────────────────

    def _on_filter_changed(self, text: str) -> None:
        category = _CATEGORY_FILTER.get(text, "")
        self._refresh(category)

    def _on_select(self, tutorial_id: str, example_index: int) -> None:
        """用户选择示例。"""
        example = self._engine.load_example(tutorial_id, example_index)
        if example:
            self.example_selected.emit(example)
            self.accept()


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """模块导入测试。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_Tutorial.example_library self_test ===")
    try:
        from MF_Tutorial.example_library import ExampleLibrary
        assert ExampleLibrary is not None
        passed += 1
        print("  [PASS] ExampleLibrary 类可导入")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    print(f"  [PASS] {passed} passed, {failed} failed")
    print("=== MF_Tutorial.example_library self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
