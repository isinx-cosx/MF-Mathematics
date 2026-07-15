# -*- coding: utf-8 -*-
"""WelcomeDialog — 首次启动介绍，3-5 页滑动卡片。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QStackedWidget,
)

from MF_Tutorial.engine import TutorialEngine

# ── 样式 ──────────────────────────────────────────────────────

_DIALOG_STYLE = """
    QDialog { background: #f8fafc; }
"""

_CARD_STYLE = """
    QWidget#card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
    }
"""

_TITLE_STYLE = "font-size: 22px; font-weight: 700; color: #0f172a; background: transparent;"
_DESC_STYLE = "font-size: 14px; color: #475569; line-height: 1.7; background: transparent;"
_FEATURE_STYLE = (
    "font-size: 13px; color: #334155; background: #f1f5f9;"
    " padding: 8px 12px; border-radius: 8px;"
)

_BTN_PRIMARY = """
    QPushButton {
        background: #3b82f6; color: #fff; border: none;
        border-radius: 8px; padding: 12px 28px;
        font-size: 14px; font-weight: 600;
    }
    QPushButton:hover { background: #2563eb; }
"""

_BTN_SECONDARY = """
    QPushButton {
        background: #f1f5f9; color: #475569; border: 1px solid #d1d5db;
        border-radius: 8px; padding: 10px 20px;
        font-size: 13px;
    }
    QPushButton:hover { background: #e2e8f0; }
"""

_DOT_ACTIVE = "background: #3b82f6; border-radius: 4px; min-width: 8px; min-height: 8px;"
_DOT_INACTIVE = "background: #d1d5db; border-radius: 4px; min-width: 8px; min-height: 8px;"

# ── 卡片内容 ──────────────────────────────────────────────────

_WELCOME_CARDS = [
    {
        "icon": "🧮",
        "title": "欢迎使用 MF-Mathematics",
        "description": (
            "一款强大而优雅的数学工具，集成了<br>"
            "<b>符号计算 · 函数绘图 · AI 助手</b><br>"
            "三大核心能力，覆盖 12 个数学分支。"
        ),
        "features": [
            "📐 代数 · 微积分 · 线性代数 · 概率统计",
            "📊 2D/3D 绘图 · 复数着色 · 向量场 · 几何做图",
            "🤖 AI 步骤推导 · 智能加速 · 数学问答",
        ],
    },
    {
        "icon": "⚡",
        "title": "快速上手",
        "description": (
            "只需 3 步完成你的第一次数学计算："
        ),
        "features": [
            "① 在输入框中输入表达式，如 x² + 2x + 1",
            "② 在下拉菜单选择操作类型（化简/求导/积分…）",
            "③ 点击「计算」，查看结果和 AI 生成的推导步骤",
        ],
    },
    {
        "icon": "🎨",
        "title": "不只是计算",
        "description": (
            "MF-Mathematics 还能做更多："
        ),
        "features": [
            "📈 绘制精美函数图像，支持隐函数和参数方程",
            "🔍 联网搜索数学知识（DuckDuckGo + WolframAlpha）",
            "⌨️ 浮动数学键盘，快速输入各种符号",
            "🌓 亮色/暗色主题自由切换",
        ],
    },
    {
        "icon": "🚀",
        "title": "准备好了吗？",
        "description": (
            "接下来，我们为你准备了一个<br>"
            "<b>2 分钟的交互式引导</b>，<br>"
            "带你快速熟悉软件的核心操作。"
        ),
        "features": [
            "💡 引导过程会高亮每个按钮和输入区域",
            "📖 随时按 F1 打开完整帮助文档",
            "🧪 帮助文档中还有 30+ 示例任务等你探索",
        ],
    },
]


# ═══════════════════════════════════════════════════════════════
#  WelcomeDialog
# ═══════════════════════════════════════════════════════════════

class WelcomeDialog(QDialog):
    """首次启动介绍对话框。

    用法:
        dialog = WelcomeDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 用户选择开始引导
            walkthrough = GuidedWalkthrough(parent)
            walkthrough.start()
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("欢迎")
        self.setFixedSize(540, 420)
        self.setStyleSheet(_DIALOG_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self._current_index = 0
        self._build_ui()
        self._show_card(0)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(32, 28, 32, 24)

        # 卡片区域
        self._card_stack = QStackedWidget()
        self._card_stack.setObjectName("card")
        self._card_stack.setStyleSheet(_CARD_STYLE)
        root.addWidget(self._card_stack, 1)

        # 底部导航
        nav = QHBoxLayout()
        nav.setSpacing(12)

        # 圆点指示器
        self._dots: list[QLabel] = []
        for _ in range(len(_WELCOME_CARDS)):
            dot = QLabel()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(_DOT_INACTIVE)
            nav.addWidget(dot)
            self._dots.append(dot)

        nav.addStretch()

        # 跳过 / 上一步
        self._skip_btn = QPushButton("跳过")
        self._skip_btn.setStyleSheet(_BTN_SECONDARY)
        self._skip_btn.clicked.connect(self.reject)
        nav.addWidget(self._skip_btn)

        self._prev_btn = QPushButton("上一步")
        self._prev_btn.setStyleSheet(_BTN_SECONDARY)
        self._prev_btn.clicked.connect(self._prev)
        self._prev_btn.hide()
        nav.addWidget(self._prev_btn)

        # 下一步 / 开始引导
        self._next_btn = QPushButton("下一步")
        self._next_btn.setStyleSheet(_BTN_PRIMARY)
        self._next_btn.clicked.connect(self._next)
        nav.addWidget(self._next_btn)

        root.addLayout(nav)

    # ── 卡片 ──────────────────────────────────────────────

    def _show_card(self, index: int) -> None:
        """切换卡片。"""
        self._current_index = index

        # 更新圆点
        for i, dot in enumerate(self._dots):
            dot.setStyleSheet(_DOT_ACTIVE if i == index else _DOT_INACTIVE)

        # 按钮状态
        self._prev_btn.setVisible(index > 0)
        self._skip_btn.setVisible(index < len(_WELCOME_CARDS) - 1)
        if index == len(_WELCOME_CARDS) - 1:
            self._next_btn.setText("开始引导 🚀")
        else:
            self._next_btn.setText("下一步")

        # 构建卡片
        card_data = _WELCOME_CARDS[index]
        card = QWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(14)
        layout.setContentsMargins(36, 32, 36, 32)

        # 图标
        icon_lbl = QLabel(card_data["icon"])
        icon_lbl.setFont(QFont("Segoe UI Emoji", 36))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        # 标题
        title = QLabel(card_data["title"])
        title.setStyleSheet(_TITLE_STYLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 描述
        desc = QLabel(card_data["description"])
        desc.setStyleSheet(_DESC_STYLE)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 功能点
        for feat in card_data["features"]:
            feat_lbl = QLabel(feat)
            feat_lbl.setStyleSheet(_FEATURE_STYLE)
            feat_lbl.setWordWrap(True)
            layout.addWidget(feat_lbl)

        layout.addStretch()

        # 替换堆叠
        while self._card_stack.count():
            w = self._card_stack.widget(0)
            self._card_stack.removeWidget(w)
            w.deleteLater()
        self._card_stack.addWidget(card)

    # ── 导航 ──────────────────────────────────────────────

    def _next(self) -> None:
        if self._current_index < len(_WELCOME_CARDS) - 1:
            self._show_card(self._current_index + 1)
        else:
            # 最后一步：开始引导
            self.accept()

    def _prev(self) -> None:
        if self._current_index > 0:
            self._show_card(self._current_index - 1)


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """模块导入测试。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_Tutorial.welcome_dialog self_test ===")
    try:
        from MF_Tutorial.welcome_dialog import WelcomeDialog, _WELCOME_CARDS
        assert len(_WELCOME_CARDS) == 4, "应有 4 张欢迎卡片"
        passed += 1
        print("  [PASS] WelcomeDialog 可导入，卡片数=4")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    print(f"  [PASS] {passed} passed, {failed} failed")
    print("=== MF_Tutorial.welcome_dialog self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
