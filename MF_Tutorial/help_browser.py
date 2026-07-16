# -*- coding: utf-8 -*-
"""HelpBrowser — 内置帮助文档窗口，可随时按 F1 打开。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QTextBrowser,
    QSplitter, QWidget,
)

from MF_Tutorial.engine import TutorialEngine
from MF_Tutorial.models import Tutorial, Difficulty, Category

# ── 样式（颜色由 QSS 主题控制）──────────────────────────────

_HEADER_STYLE = "font-size: 18px; font-weight: 700; background: transparent;"
_PROGRESS_STYLE = "font-size: 11px; background: transparent;"

# ── 分类映射 ──────────────────────────────────────────────────

_CATEGORY_LABELS: dict[Category, str] = {
    "general": "📖 入门指南",
    "calculation": "🧮 计算模块",
    "plot": "📊 绘图系统",
    "ai": "🤖 AI 功能",
    "tools": "🔧 工具",
    "settings": "⚙️ 设置",
}

_DIFFICULTY_TAGS: dict[Difficulty, str] = {
    "beginner": "🔵 入门",
    "intermediate": "🟡 进阶",
    "advanced": "🟣 高级",
}


# ═══════════════════════════════════════════════════════════════
#  HelpBrowser
# ═══════════════════════════════════════════════════════════════

class HelpBrowser(QDialog):
    """内置帮助文档浏览器。

    用法:
        browser = HelpBrowser(parent)
        browser.exec()
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("帮助文档 — MF-Mathematics")
        self.resize(900, 600)
        self.setMinimumSize(700, 450)
        self.setObjectName("helpBrowser")

        self._engine = TutorialEngine()
        self._engine.load_all()
        self._build_ui()
        self._populate_tree()

        # 默认选中第一篇
        all_tuts = self._engine.get_all()
        if all_tuts:
            self._show_tutorial(all_tuts[0])

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # 标题行
        hdr = QHBoxLayout()
        title = QLabel("帮助文档")
        title.setStyleSheet(_HEADER_STYLE)
        hdr.addWidget(title)
        hdr.addStretch()

        progress = self._engine.get_progress()
        self._progress_lbl = QLabel(
            f"已学 {progress['completed']}/{progress['total']} · {progress['percent']}%"
        )
        self._progress_lbl.setStyleSheet(_PROGRESS_STYLE)
        hdr.addWidget(self._progress_lbl)
        root.addLayout(hdr)

        # 主区域：左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧目录树
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumWidth(200)
        self._tree.setIndentation(16)
        self._tree.itemClicked.connect(self._on_item_clicked)
        left_layout.addWidget(self._tree)

        # 加载示例按钮
        self._load_example_btn = QPushButton("📥 加载示例到工作区")
        self._load_example_btn.setObjectName("ai_send_btn")
        self._load_example_btn.clicked.connect(self._on_load_example)
        self._load_example_btn.setEnabled(False)
        left_layout.addWidget(self._load_example_btn)

        splitter.addWidget(left_panel)

        # 右侧内容浏览器
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setFont(QFont("Microsoft YaHei", 10))
        splitter.addWidget(self._browser)

        splitter.setSizes([260, 620])
        root.addWidget(splitter, 1)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("ai_send_btn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, "帮助文档")

    # ── 目录树 ────────────────────────────────────────────

    def _populate_tree(self) -> None:
        """构建分类 → 教程的树形结构。"""
        self._tree.clear()
        self._item_map: dict[str, QTreeWidgetItem] = {}

        for cat in self._engine.get_categories():
            cat_label = _CATEGORY_LABELS.get(cat, cat)
            cat_item = QTreeWidgetItem([cat_label])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            cat_item.setData(0, Qt.ItemDataRole.UserRole, f"__cat__{cat}")
            cat_item.setExpanded(True)

            font = QFont()
            font.setBold(True)
            cat_item.setFont(0, font)

            self._tree.addTopLevelItem(cat_item)

            tutorials = self._engine.list_by(category=cat)
            for tut in tutorials:
                completed = self._engine.is_completed(tut.id)
                diff_tag = _DIFFICULTY_TAGS.get(tut.difficulty, "")
                prefix = "✅ " if completed else "   "
                label = f"{prefix}{tut.title}  ({tut.duration})"
                tut_item = QTreeWidgetItem([label])
                tut_item.setData(0, Qt.ItemDataRole.UserRole, tut.id)
                cat_item.addChild(tut_item)
                self._item_map[tut.id] = tut_item

    # ── 内容渲染 ──────────────────────────────────────────

    def _show_tutorial(self, tutorial: Tutorial) -> None:
        """在右侧浏览器渲染教程全文。"""
        self._current_tutorial = tutorial
        self._engine.set_last_tutorial(tutorial.id)
        self._load_example_btn.setEnabled(len(tutorial.examples) > 0)

        html = self._render_html(tutorial)
        self._browser.setHtml(html)

    def _render_html(self, tutorial: Tutorial) -> str:
        """将 Tutorial 渲染为 HTML。"""
        diff_tag = _DIFFICULTY_TAGS.get(tutorial.difficulty, "")
        completed = "✅ 已完成" if self._engine.is_completed(tutorial.id) else ""

        parts = [
            "<div style='font-family: Microsoft YaHei, sans-serif;'>",
            f"<h1 style='color:#0f172a; margin-bottom:4px;'>{tutorial.title}</h1>",
            f"<p style='color:#94a3b8; font-size:12px; margin-top:0;'>"
            f"{diff_tag} · ⏱ {tutorial.duration} · {completed}</p>",
            f"<hr style='border-color:#e2e8f0;'>",

            # 简介
            f"<h3 style='color:#334155;'>概述</h3>",
            f"<p style='color:#475569; line-height:1.8;'>{tutorial.summary}</p>",
        ]

        # 步骤
        if tutorial.steps:
            parts.append("<h3 style='color:#334155;'>操作步骤</h3>")
            parts.append("<ol style='color:#475569; line-height:1.8;'>")
            for i, step in enumerate(tutorial.steps, 1):
                # 去掉 HTML 标签，纯文本展示
                text = step.text.replace("<br>", " → ").replace("<b>", "").replace("</b>", "")
                parts.append(f"<li>{text}</li>")
            parts.append("</ol>")

        # 示例
        if tutorial.examples:
            parts.append("<h3 style='color:#334155;'>示例任务</h3>")
            parts.append("<table style='width:100%; border-collapse:collapse; color:#475569;'>")
            for ex in tutorial.examples:
                parts.append(
                    f"<tr>"
                    f"<td style='padding:4px 12px;'><b>{ex.label}</b></td>"
                    f"<td style='padding:4px 12px; font-family:monospace;'>{ex.expr}</td>"
                    f"<td style='padding:4px 12px; color:#94a3b8;'>{ex.mode}</td>"
                    f"</tr>"
                )
            parts.append("</table>")

        # 常见问题
        if tutorial.faq:
            parts.append("<h3 style='color:#334155;'>常见问题</h3>")
            for faq in tutorial.faq:
                parts.append(
                    f"<details style='margin:8px 0;'>"
                    f"<summary style='color:#3b82f6; cursor:pointer;'>{faq.q}</summary>"
                    f"<p style='color:#475569; margin-left:16px;'>{faq.a}</p>"
                    f"</details>"
                )

        # 完成按钮
        if not self._engine.is_completed(tutorial.id):
            parts.append(
                f"<br><button onclick='mark_done' "
                f"style='background:#10b981;color:#fff;border:none;"
                f"border-radius:6px;padding:8px 18px;font-size:13px;cursor:pointer;'>"
                f"✓ 标记为已学"
                f"</button>"
            )

        parts.append("</div>")
        return "\n".join(parts)

    # ── 事件 ──────────────────────────────────────────────

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        tutorial_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not tutorial_id or str(tutorial_id).startswith("__cat__"):
            return
        tutorial = self._engine.get(tutorial_id)
        if tutorial:
            self._show_tutorial(tutorial)

    def _on_load_example(self) -> None:
        """加载当前教程的第一个示例到工作区。"""
        if not hasattr(self, '_current_tutorial'):
            return
        tutorial = self._current_tutorial
        if tutorial.examples:
            from MF_Tutorial.engine import TutorialEngine
            engine = TutorialEngine()
            example = engine.load_example(tutorial.id, 0)
            if example:
                # 通过父窗口加载示例
                parent = self.parent()
                if parent and hasattr(parent, 'load_tutorial_example'):
                    parent.load_tutorial_example(example)
                else:
                    self._browser.append(
                        f"<p style='color:#f59e0b;'>请在工作区界面中使用示例加载功能。</p>"
                    )


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """模块导入测试。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_Tutorial.help_browser self_test ===")
    try:
        from MF_Tutorial.help_browser import HelpBrowser
        assert HelpBrowser is not None
        passed += 1
        print("  [PASS] HelpBrowser 类可导入")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    print(f"  [PASS] {passed} passed, {failed} failed")
    print("=== MF_Tutorial.help_browser self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
