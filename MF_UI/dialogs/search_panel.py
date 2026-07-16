# -*- coding: utf-8 -*-
"""联网搜索面板 — 非模态 QDialog，支持 DuckDuckGo / Wolfram Alpha。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

ENGINES = {"DuckDuckGo": "duckduckgo", "Wolfram Alpha": "wolfram", "自定义": "custom"}


class _SearchWorker(QThread):
    """后台搜索线程。"""
    finished = Signal(list)   # results list
    error = Signal(str)

    def __init__(self, query: str, engine: str, parent=None):
        super().__init__(parent)
        self._query = query
        self._engine = engine

    def run(self):
        try:
            from MF_Online import search
            results = search(self._query, self._engine)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class SearchPanel(QDialog):
    """联网搜索面板 — 非模态，记忆位置/大小。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("联网搜索")
        self.resize(520, 480)
        self.setMinimumSize(380, 320)
        self.setObjectName("searchDialog")
        self._results_data: list[dict] = []
        self._worker: _SearchWorker | None = None

        self._build_ui()
        self._restore_geometry()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # ── 搜索栏 ──
        bar = QHBoxLayout(); bar.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("搜索数学概念、公式、定理…")
        self._input.returnPressed.connect(self._do_search)
        bar.addWidget(self._input, 1)

        self._engine_combo = QComboBox()
        self._engine_combo.addItems(list(ENGINES.keys()))
        bar.addWidget(self._engine_combo)

        self._search_btn = QPushButton("搜索")
        self._search_btn.setObjectName("ai_send_btn")
        self._search_btn.clicked.connect(self._do_search)
        bar.addWidget(self._search_btn)
        root.addLayout(bar)

        # ── 结果列表 ──
        self._list = QListWidget()
        self._list.setWordWrap(True)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        root.addWidget(self._list, 1)

        # ── 底部 ──
        bottom = QHBoxLayout(); bottom.setSpacing(8)
        self._status = QLabel("就绪")
        self._status.setStyleSheet("font-size: 11px; color: #94a3b8;")
        bottom.addWidget(self._status, 1)

        insert_btn = QPushButton("插入到当前块")
        insert_btn.setStyleSheet(
            "QPushButton{background:#10b981;color:#fff;border:none;"
            "border-radius:6px;padding:6px 16px;font-size:12px;font-weight:500;}"
            "QPushButton:hover{background:#059669;}")
        insert_btn.clicked.connect(self._insert_current)
        bottom.addWidget(insert_btn)
        root.addLayout(bottom)

        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, "联网搜索")

    # ── 搜索 ──────────────────────────────────────────────

    def _do_search(self):
        query = self._input.text().strip()
        if not query:
            return
        if self._worker and self._worker.isRunning():
            return

        engine = ENGINES[self._engine_combo.currentText()]
        self._set_searching(True)

        self._worker = _SearchWorker(query, engine, self)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_results(self, results: list[dict]):
        self._set_searching(False)
        self._results_data = results
        self._list.clear()

        if not results:
            item = QListWidgetItem("未找到相关结果，请尝试其他关键词。")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._list.addItem(item)
            self._status.setText("无结果")
            return

        for r in results:
            title = r.get("title", "")
            snippet = r.get("snippet", "")
            text = f"{title}\n{snippet[:200]}"
            item = QListWidgetItem(text)
            item.setToolTip(snippet)
            self._list.addItem(item)

        self._status.setText(f"共 {len(results)} 条结果")

    def _on_error(self, msg: str):
        self._set_searching(False)
        QMessageBox.warning(self, "搜索失败", msg)

    def _set_searching(self, searching: bool):
        self._input.setEnabled(not searching)
        self._search_btn.setEnabled(not searching)
        self._status.setText("搜索中…" if searching else "就绪")

    # ── 插入 ──────────────────────────────────────────────

    def _on_double_click(self, _item):
        self._insert_current()

    def _insert_current(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._results_data):
            QMessageBox.information(self, "提示", "请先选中一条搜索结果。")
            return

        r = self._results_data[row]
        text = r.get("snippet", r.get("title", ""))
        latex = r.get("latex", "")
        if latex:
            text = f"${latex}$ {text}"

        widget = self._find_input()
        if widget is None:
            QMessageBox.information(self, "提示", "请先激活一个计算块输入框。")
            return

        if hasattr(widget, 'insert'):
            widget.insert(text)
        elif hasattr(widget, 'setText'):
            widget.setText(text)
        self._status.setText("已插入")

    @staticmethod
    def _find_input() -> QWidget | None:
        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit,)):
            return focus
        # 回退：查找 MainWindow → CalcBlock
        for w in QApplication.topLevelWidgets():
            if hasattr(w, '_stacked_widget'):
                sw = w._stacked_widget
                cw = sw.currentWidget()
                if cw:
                    for child in cw.findChildren(QLineEdit):
                        if child.isVisible() and child.isEnabled():
                            return child
        return None

    # ── 位置记忆 ──────────────────────────────────────────

    def _restore_geometry(self):
        if hasattr(SearchPanel, '_saved_geo'):
            self.restoreGeometry(SearchPanel._saved_geo)

    def closeEvent(self, event):
        SearchPanel._saved_geo = self.saveGeometry()
        super().closeEvent(event)
