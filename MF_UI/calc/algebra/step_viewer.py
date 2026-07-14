# ————————————MF-Mathematics 步骤查看器————————————

"""
步骤查看器 — 以弹窗形式展示 MathObject 中的详细计算步骤（纯文本版）。
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class StepViewer(QDialog):
    """显示计算步骤的弹窗，纯文本显示。"""

    def __init__(self, title: str, steps: list[str], meaning: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"步骤详情 — {title}")
        self.resize(620, 460)
        self.setMinimumSize(460, 300)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # 步骤文本浏览器
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setFont(QFont("Consolas", 11))
        self.browser.setStyleSheet("""
            QTextBrowser {
                background-color: #fafbfc;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 12px;
                color: #0f172a;
            }
        """)

        # 构建步骤 HTML
        html_lines = [
            '<html><body style="font-family: Consolas, monospace; font-size: 13px;">'
        ]
        for i, step in enumerate(steps, 1):
            if not step.strip():
                continue
            html_lines.append(
                f'<p style="margin: 6px 0;"><b>[步骤 {i}]</b> {step}</p>'
            )
        if meaning:
            html_lines.append(
                f'<hr style="border: none; border-top: 1px solid #e2e8f0;">'
                f'<p style="color: #475569;">'
                f'<b>说明：</b>{meaning}</p>'
            )
        html_lines.append("</body></html>")

        self.browser.setHtml("\n".join(html_lines))
        layout.addWidget(self.browser, 1)

        # 关闭按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(100)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)