# -*- coding: utf-8 -*-
"""RegisterDialog — 注册对话框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QWidget,
)

from MF_User.manager import UserManager

# ── 样式（与 LoginDialog 保持一致）───────────────────────────

_DIALOG_STYLE = """
    QDialog { background: #f8fafc; }
"""

_INPUT_STYLE = """
    QLineEdit {
        border: 1px solid #d1d5db; border-radius: 6px;
        padding: 10px 14px; font-size: 14px; background: #fff;
    }
    QLineEdit:focus { border-color: #3b82f6; }
"""

_BTN_PRIMARY = """
    QPushButton {
        background: #3b82f6; color: #fff; border: none;
        border-radius: 6px; padding: 10px 24px;
        font-size: 14px; font-weight: 500;
    }
    QPushButton:hover { background: #2563eb; }
    QPushButton:disabled { background: #94a3b8; }
"""

_BTN_SECONDARY = """
    QPushButton {
        background: #f1f5f9; color: #475569;
        border: 1px solid #d1d5db;
        border-radius: 6px; padding: 8px 16px;
        font-size: 12px;
    }
    QPushButton:hover { background: #e2e8f0; }
"""

_BTN_LINK = """
    QPushButton {
        background: transparent; color: #3b82f6;
        border: none; font-size: 12px;
    }
    QPushButton:hover { color: #2563eb; text-decoration: underline; }
"""

_TITLE_STYLE = "font-size: 18px; font-weight: 700; color: #0f172a; background: transparent;"
_LABEL_STYLE = "font-size: 13px; color: #475569; background: transparent;"
_ERROR_STYLE = "font-size: 12px; color: #ef4444; background: transparent;"
_SUCCESS_STYLE = "font-size: 12px; color: #10b981; background: transparent;"


# ═══════════════════════════════════════════════════════════════
#  RegisterDialog
# ═══════════════════════════════════════════════════════════════

class RegisterDialog(QDialog):
    """注册对话框。

    用法:
        dlg = RegisterDialog(parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            user = UserManager().current_user
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("注册 — MF-Mathematics")
        self.setFixedSize(400, 400)
        self.setStyleSheet(_DIALOG_STYLE)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(32, 28, 32, 24)

        # 标题
        title = QLabel("创建账号")
        title.setStyleSheet(_TITLE_STYLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        # 用户名
        user_label = QLabel("用户名")
        user_label.setStyleSheet(_LABEL_STYLE)
        root.addWidget(user_label)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("3-20 个字符，字母数字下划线")
        self._username_input.setMaxLength(20)
        self._username_input.setStyleSheet(_INPUT_STYLE)
        root.addWidget(self._username_input)

        # 密码
        pwd_label = QLabel("密码")
        pwd_label.setStyleSheet(_LABEL_STYLE)
        root.addWidget(pwd_label)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("至少 6 个字符")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setStyleSheet(_INPUT_STYLE)
        root.addWidget(self._password_input)

        # 确认密码
        confirm_label = QLabel("确认密码")
        confirm_label.setStyleSheet(_LABEL_STYLE)
        root.addWidget(confirm_label)

        self._confirm_input = QLineEdit()
        self._confirm_input.setPlaceholderText("再次输入密码")
        self._confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_input.setStyleSheet(_INPUT_STYLE)
        self._confirm_input.returnPressed.connect(self._on_register)
        root.addWidget(self._confirm_input)

        # 消息提示
        self._msg_label = QLabel("")
        self._msg_label.setStyleSheet(_ERROR_STYLE)
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._msg_label.setWordWrap(True)
        self._msg_label.hide()
        root.addWidget(self._msg_label)

        root.addSpacing(2)

        # 注册按钮
        reg_btn = QPushButton("注  册")
        reg_btn.setStyleSheet(_BTN_PRIMARY)
        reg_btn.clicked.connect(self._on_register)
        reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        root.addWidget(reg_btn)

        # 底部链接
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        bottom.addStretch()
        link_btn = QPushButton("已有账号？返回登录")
        link_btn.setStyleSheet(_BTN_LINK)
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.clicked.connect(self.reject)
        bottom.addWidget(link_btn)
        bottom.addStretch()
        root.addLayout(bottom)

        self._username_input.setFocus()

    # ── 事件 ──────────────────────────────────────────────

    def _on_register(self) -> None:
        username = self._username_input.text()
        password = self._password_input.text()
        confirm = self._confirm_input.text()

        # 基本验证
        if not username.strip():
            self._show_msg("请输入用户名", error=True)
            return
        if len(password) < 6:
            self._show_msg("密码至少需要 6 个字符", error=True)
            return
        if password != confirm:
            self._show_msg("两次输入的密码不一致", error=True)
            return

        mgr = UserManager()
        user, err = mgr.register(username, password)
        if user is None:
            self._show_msg(err, error=True)
            return

        self._show_msg(f"注册成功！欢迎，{username}", error=False)
        # 短暂延迟后关闭
        from PySide6.QtCore import QTimer
        QTimer.singleShot(800, self.accept)

    def _show_msg(self, msg: str, error: bool = True) -> None:
        self._msg_label.setText(msg)
        self._msg_label.setStyleSheet(_ERROR_STYLE if error else _SUCCESS_STYLE)
        self._msg_label.show()


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """模块导入测试。"""
    passed, failed = 0, 0
    errors: list[str] = []
    print("=== MF_User.register_dialog self_test ===")
    try:
        from MF_User.register_dialog import RegisterDialog
        assert RegisterDialog is not None
        passed += 1
        print("  [PASS] RegisterDialog 可导入")
    except Exception as e:
        failed += 1
        errors.append(str(e))
    print(f"  [{passed} passed, {failed} failed]")
    print("=== MF_User.register_dialog self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
