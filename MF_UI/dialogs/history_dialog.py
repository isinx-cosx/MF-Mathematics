# -*- coding: utf-8 -*-
"""HistoryDialog — 计算历史记录查看器。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel,
)


class HistoryDialog(QDialog):
    """显示计算表达式历史列表，点击回退到该表达式。"""

    def __init__(self, history: list[str], history_pos: int,
                 on_select: callable, parent=None):
        super().__init__(parent)
        self.setWindowTitle("计算历史记录")
        self.setMinimumSize(420, 400)
        self._history = history
        self._on_select = on_select
        self._history_pos = history_pos

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 标题
        title = QLabel(f"共 {len(history)} 条记录")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #334155;")
        layout.addWidget(title)

        # 列表
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e2e8f0; border-radius: 6px;
                font-size: 13px; padding: 4px;
            }
            QListWidget::item { padding: 6px 8px; }
            QListWidget::item:selected { background: #dbeafe; color: #1e40af; }
            QListWidget::item:hover { background: #f1f5f9; }
        """)
        for i, expr in enumerate(history):
            prefix = "→ " if i == history_pos else "  "
            item = QListWidgetItem(f"{prefix}{expr}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            if i == history_pos:
                font = item.font(); font.setBold(True); item.setFont(font)
            self._list.addItem(item)

        # 滚动到当前项
        if 0 <= history_pos < len(history):
            self._list.setCurrentRow(history_pos)
            self._list.scrollToItem(self._list.item(history_pos))

        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, 1)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        clear_btn = QPushButton("清空历史")
        clear_btn.setStyleSheet(
            "QPushButton { color: #dc2626; border: 1px solid #fca5a5; "
            "border-radius: 4px; padding: 6px 16px; }"
            "QPushButton:hover { background: #fef2f2; }")
        clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(clear_btn)
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(
            "QPushButton { border: 1px solid #d1d5db; border-radius: 4px; "
            "padding: 6px 16px; }"
            "QPushButton:hover { background: #f1f5f9; }")
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # 应用自定义标题栏
        try:
            from MF_UI.components.mf_dialog import apply_dialog_title_bar
            apply_dialog_title_bar(self)
        except Exception:
            pass

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is not None and 0 <= idx < len(self._history):
            self._on_select(self._history[idx])
            self._history_pos = idx
            self._update_items()

    def _on_clear(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        r = QMessageBox.question(self, "确认", "清空所有计算历史？",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._list.clear()
            self._history.clear()
            self._history_pos = -1
            self.findChild(QLabel).setText("共 0 条记录")

    def _update_items(self) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item:
                prefix = "→ " if i == self._history_pos else "  "
                item.setText(f"{prefix}{self._history[i]}")
                font = item.font(); font.setBold(i == self._history_pos); item.setFont(font)
