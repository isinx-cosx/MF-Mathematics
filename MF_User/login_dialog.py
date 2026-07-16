# -*- coding: utf-8 -*-
"""LoginDialog — 登录对话框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QWidget,
)

from MF_User.manager import UserManager

# ── 样式（颜色由 QSS 主题控制）──────────────────────────────

_BTN_SECONDARY = """
    QPushButton {
        background: #f1f5f9; color: #475569;
        border: 1px solid #d1d5db;
        border-radius: 6px; padding: 8px 16px;
        font-size: 12px;
    }
    QPushButton:hover { background: #e2e8f0; }
"""

_TITLE_STYLE = "font-size: 18px; font-weight: 700; background: transparent;"
_LABEL_STYLE = "font-size: 13px; background: transparent;"
_ERROR_STYLE = "font-size: 12px; color: #ef4444; background: transparent;"


# ═══════════════════════════════════════════════════════════════
#  LoginDialog
# ═══════════════════════════════════════════════════════════════

class LoginDialog(QDialog):
    """登录对话框。

    用法:
        dlg = LoginDialog(parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            user = UserManager().current_user
    """

    register_requested = None  # 由外部设置回调: register_requested()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录 — MF-Mathematics")
        self.setFixedSize(400, 340)
        self.setObjectName("loginDialog")

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(32, 28, 32, 24)

        # 标题
        title = QLabel("欢迎回来")
        title.setStyleSheet(_TITLE_STYLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # 用户名
        user_label = QLabel("用户名")
        user_label.setStyleSheet(_LABEL_STYLE)
        root.addWidget(user_label)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("输入用户名")
        root.addWidget(self._username_input)

        # 密码
        pwd_label = QLabel("密码")
        pwd_label.setStyleSheet(_LABEL_STYLE)
        root.addWidget(pwd_label)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("输入密码")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.returnPressed.connect(self._on_login)
        root.addWidget(self._password_input)

        # 错误提示
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(_ERROR_STYLE)
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        root.addWidget(self._error_label)

        root.addSpacing(4)

        # 登录按钮
        login_btn = QPushButton("登  录")
        login_btn.setObjectName("ai_send_btn")
        login_btn.clicked.connect(self._on_login)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        root.addWidget(login_btn)

        # 底部链接
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        bottom.addStretch()
        link_btn = QPushButton("还没有账号？立即注册")
        link_btn.setObjectName("ai_clear_btn")
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.clicked.connect(self._on_register)
        bottom.addWidget(link_btn)
        bottom.addStretch()
        root.addLayout(bottom)

        # 设置焦点
        self._username_input.setFocus()

        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, "登录")

    # ── 事件 ──────────────────────────────────────────────

    def _on_login(self) -> None:
        username = self._username_input.text()
        password = self._password_input.text()

        if not username.strip():
            self._show_error("请输入用户名")
            return
        if not password:
            self._show_error("请输入密码")
            return

        mgr = UserManager()
        user, err = mgr.login(username, password)
        if user is None:
            self._show_error(err)
            return

        self.accept()

    def _on_register(self) -> None:
        """切换到注册。"""
        self.reject()  # 关闭登录框
        from MF_User.register_dialog import RegisterDialog
        dlg = RegisterDialog(self.parent())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.accept()  # 注册成功 → 传播 accept 到调用方

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.show()


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """模块导入测试。"""
    passed, failed = 0, 0
    errors: list[str] = []
    print("=== MF_User.login_dialog self_test ===")
    try:
        from MF_User.login_dialog import LoginDialog
        assert LoginDialog is not None
        passed += 1
        print("  [PASS] LoginDialog 可导入")
    except Exception as e:
        failed += 1
        errors.append(str(e))
    print(f"  [{passed} passed, {failed} failed]")
    print("=== MF_User.login_dialog self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
