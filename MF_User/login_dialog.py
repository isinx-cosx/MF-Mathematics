# -*- coding: utf-8 -*-
"""LoginRegisterDialog — 统一登录/注册/邮箱验证对话框。

Tab 切换 + 邮箱验证码流程 + MF-Mathematics 双主题适配。
"""

from __future__ import annotations

import re as _re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from MF_User.api_client import APIClient

# ── 内联样式常量 ──────────────────────────────────────────

_TITLE_STYLE = "font-size:18px;font-weight:700;background:transparent;"
_LABEL_STYLE = "font-size:13px;background:transparent;"
_INPUT_STYLE = (
    "QLineEdit{font-size:13px;padding:10px 14px;border:1px solid #d1d5db;"
    "border-radius:6px;background:#fff;color:#1e293b;}"
    "QLineEdit:focus{border-color:#3b82f6;}"
)
_ERROR_STYLE = "font-size:12px;color:#ef4444;background:transparent;"
_SUCCESS_STYLE = "font-size:12px;color:#10b981;background:transparent;"
_HINT_STYLE = "font-size:12px;color:#94a3b8;background:transparent;"

_BTN_PRIMARY = (
    "QPushButton{background:#3b82f6;color:#fff;border:none;"
    "border-radius:6px;padding:10px 24px;font-size:13px;font-weight:500;}"
    "QPushButton:hover{background:#2563eb;}"
    "QPushButton:pressed{background:#1d4ed8;}"
)
_BTN_SECONDARY = (
    "QPushButton{background:#f1f5f9;color:#475569;border:1px solid #d1d5db;"
    "border-radius:6px;padding:8px 16px;font-size:12px;}"
    "QPushButton:hover{background:#e2e8f0;}"
)
_BTN_LINK = (
    "QPushButton{background:transparent;border:none;color:#94a3b8;font-size:11px;}"
    "QPushButton:hover{color:#ef4444;}"
)

_TAB_NORMAL = (
    "QPushButton{background:transparent;color:#94a3b8;border:none;"
    "border-bottom:2px solid transparent;padding:10px 24px;font-size:14px;font-weight:600;}"
    "QPushButton:hover{color:#475569;}"
)
_TAB_ACTIVE = (
    "QPushButton{background:transparent;color:#1e293b;border:none;"
    "border-bottom:2px solid #3b82f6;padding:10px 24px;font-size:14px;font-weight:700;}"
)


class LoginRegisterDialog(QDialog):
    """统一登录/注册对话框 — 含邮箱验证码流程。

    用法:
        dlg = LoginRegisterDialog(parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            token = dlg.get_token()
            username = dlg.get_username()
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("登录 — MF-Mathematics")
        self.setFixedSize(440, 480)
        self.setObjectName("loginDialog")

        self._api = APIClient()
        self._token: str | None = None
        self._username: str = ""
        self._registered_username: str = ""   # 注册成功后暂存，验证时用
        self._registered_password: str = ""   # 注册成功后暂存，验证完自动登录

        self._build_ui()
        self._apply_tab_styles(self._tab_login, self._tab_register)

    # ═══════════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── 标题栏（MF-Mathematics 风格） ──
        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, "账户")

        # ── Tab 栏 ──
        tab_row = QHBoxLayout()
        tab_row.setSpacing(0)
        tab_row.setContentsMargins(0, 0, 0, 0)

        self._tab_login = QPushButton("登  录")
        self._tab_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_login.clicked.connect(lambda: self._switch_page(0))
        tab_row.addWidget(self._tab_login)

        self._tab_register = QPushButton("注  册")
        self._tab_register.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_register.clicked.connect(lambda: self._switch_page(1))
        tab_row.addWidget(self._tab_register)

        tab_row.addStretch()
        tab_widget = QWidget()
        tab_widget.setObjectName("customTitleBar")  # 复用标题栏 QSS
        tab_widget.setLayout(tab_row)
        root.addWidget(tab_widget)

        # ── 页面栈 ──
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_login_page())
        self._stack.addWidget(self._build_register_page())
        self._stack.addWidget(self._build_verify_page())
        root.addWidget(self._stack, 1)

    # ── 登录页 ────────────────────────────────────────────

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        layout.setContentsMargins(32, 20, 32, 24)

        title = QLabel("欢迎回来")
        title.setStyleSheet(_TITLE_STYLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addWidget(QLabel("用户名"))
        self._login_user = self._make_input("输入用户名")
        self._login_user.returnPressed.connect(self._on_login)
        layout.addWidget(self._login_user)

        layout.addWidget(QLabel("密码"))
        self._login_pwd = self._make_input("输入密码", echo=QLineEdit.EchoMode.Password)
        self._login_pwd.returnPressed.connect(self._on_login)
        layout.addWidget(self._login_pwd)

        self._login_error = self._make_msg(_ERROR_STYLE)
        layout.addWidget(self._login_error)

        login_btn = QPushButton("登  录")
        login_btn.setStyleSheet(_BTN_PRIMARY)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self._on_login)
        layout.addWidget(login_btn)

        layout.addStretch()

        bottom = QHBoxLayout()
        bottom.addStretch()
        link = QPushButton("还没有账号？立即注册")
        link.setStyleSheet(_BTN_LINK)
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(lambda: self._switch_page(1))
        bottom.addWidget(link)
        bottom.addStretch()
        layout.addLayout(bottom)

        return page

    # ── 注册页 ────────────────────────────────────────────

    def _build_register_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.setContentsMargins(32, 16, 32, 20)

        title = QLabel("创建账号")
        title.setStyleSheet(_TITLE_STYLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addWidget(QLabel("用户名"))
        self._reg_user = self._make_input("3-20 个字符，字母数字下划线")
        layout.addWidget(self._reg_user)

        layout.addWidget(QLabel("邮箱"))
        self._reg_email = self._make_input("your@email.com")
        layout.addWidget(self._reg_email)

        layout.addWidget(QLabel("密码"))
        self._reg_pwd = self._make_input("至少 6 个字符", echo=QLineEdit.EchoMode.Password)
        layout.addWidget(self._reg_pwd)

        layout.addWidget(QLabel("确认密码"))
        self._reg_confirm = self._make_input("再次输入密码", echo=QLineEdit.EchoMode.Password)
        self._reg_confirm.returnPressed.connect(self._on_register)
        layout.addWidget(self._reg_confirm)

        self._reg_msg = self._make_msg(_ERROR_STYLE)
        layout.addWidget(self._reg_msg)

        reg_btn = QPushButton("注  册")
        reg_btn.setStyleSheet(_BTN_PRIMARY)
        reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reg_btn.clicked.connect(self._on_register)
        layout.addWidget(reg_btn)

        layout.addStretch()

        bottom = QHBoxLayout()
        bottom.addStretch()
        link = QPushButton("已有账号？返回登录")
        link.setStyleSheet(_BTN_LINK)
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(lambda: self._switch_page(0))
        bottom.addWidget(link)
        bottom.addStretch()
        layout.addLayout(bottom)

        return page

    # ── 验证码页 ───────────────────────────────────────────

    def _build_verify_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        layout.setContentsMargins(32, 24, 32, 24)

        icon = QLabel("📧")
        icon.setStyleSheet("font-size:40px;background:transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        self._verify_title = QLabel("邮箱验证")
        self._verify_title.setStyleSheet(_TITLE_STYLE)
        self._verify_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._verify_title)

        self._verify_hint = QLabel("验证码已发送至 your@email.com")
        self._verify_hint.setStyleSheet(_HINT_STYLE)
        self._verify_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._verify_hint.setWordWrap(True)
        layout.addWidget(self._verify_hint)

        self._verify_code_input = QLineEdit()
        self._verify_code_input.setPlaceholderText("输入 6 位验证码")
        self._verify_code_input.setMaxLength(6)
        self._verify_code_input.setStyleSheet(
            "QLineEdit{font-size:22px;padding:12px 16px;letter-spacing:8px;"
            "text-align:center;border:1px solid #d1d5db;border-radius:8px;"
            "background:#fff;color:#1e293b;}"
            "QLineEdit:focus{border-color:#3b82f6;}"
        )
        self._verify_code_input.returnPressed.connect(self._on_verify)
        layout.addWidget(self._verify_code_input)

        self._verify_msg = self._make_msg(_ERROR_STYLE)
        layout.addWidget(self._verify_msg)

        verify_btn = QPushButton("验  证")
        verify_btn.setStyleSheet(_BTN_PRIMARY)
        verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        verify_btn.clicked.connect(self._on_verify)
        layout.addWidget(verify_btn)

        resend_row = QHBoxLayout()
        resend_row.addStretch()
        resend_btn = QPushButton("重新发送验证码")
        resend_btn.setStyleSheet(_BTN_LINK)
        resend_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        resend_btn.clicked.connect(self._on_resend)
        resend_row.addWidget(resend_btn)
        resend_row.addStretch()
        layout.addLayout(resend_row)

        layout.addStretch()
        return page

    # ═══════════════════════════════════════════════════════
    #  事件处理
    # ═══════════════════════════════════════════════════════

    # ── 页面切换 ──────────────────────────────────────────

    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._apply_tab_styles(
            self._tab_login if index == 0 else self._tab_register,
            self._tab_register if index == 0 else self._tab_login,
        )
        # 清空消息
        self._login_error.hide()
        self._reg_msg.hide()
        self._verify_msg.hide()

        # 设置焦点
        if index == 0:
            self._login_user.setFocus()
        elif index == 1:
            self._reg_user.setFocus()

    def _apply_tab_styles(self, active_btn: QPushButton, inactive_btn: QPushButton) -> None:
        active_btn.setStyleSheet(_TAB_ACTIVE)
        inactive_btn.setStyleSheet(_TAB_NORMAL)

    # ── 登录 ──────────────────────────────────────────────

    def _on_login(self) -> None:
        username = self._login_user.text().strip()
        password = self._login_pwd.text()

        if not username:
            self._show_login_error("请输入用户名")
            return
        if not password:
            self._show_login_error("请输入密码")
            return

        self._login_error.hide()
        try:
            result = self._api.login(username, password)
            self._token = result.get("access_token", "")
            self._username = username
            self.accept()
        except RuntimeError as e:
            self._show_login_error(str(e))

    # ── 注册 ──────────────────────────────────────────────

    def _on_register(self) -> None:
        username = self._reg_user.text().strip()
        email = self._reg_email.text().strip()
        pwd = self._reg_pwd.text()
        confirm = self._reg_confirm.text()

        if not username or len(username) < 3:
            self._show_reg_msg("用户名至少需要 3 个字符", True)
            return
        if not _re.match(r"[a-zA-Z0-9_]+$", username):
            self._show_reg_msg("用户名仅支持字母、数字和下划线", True)
            return
        if not email or not _re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            self._show_reg_msg("请输入有效的邮箱地址", True)
            return
        if len(pwd) < 6:
            self._show_reg_msg("密码至少需要 6 个字符", True)
            return
        if pwd != confirm:
            self._show_reg_msg("两次输入的密码不一致", True)
            return

        self._reg_msg.hide()
        try:
            self._api.register(username, email, pwd)
            # 注册成功 → 跳到验证码页
            self._registered_username = username
            self._registered_password = pwd
            self._verify_hint.setText(f"验证码已发送至 {email}")
            self._verify_code_input.clear()
            self._verify_msg.hide()
            self._stack.setCurrentIndex(2)  # 验证页
            self._apply_tab_styles(self._tab_register, self._tab_login)
            self._verify_code_input.setFocus()
        except RuntimeError as e:
            self._show_reg_msg(str(e), True)

    # ── 验证码 ────────────────────────────────────────────

    def _on_verify(self) -> None:
        code = self._verify_code_input.text().strip()
        if len(code) != 6 or not code.isdigit():
            self._show_verify_msg("请输入 6 位数字验证码", True)
            return

        self._verify_msg.hide()
        try:
            self._api.verify_code(self._registered_username, code)
            # 验证成功 → 自动登录
            try:
                result = self._api.login(self._registered_username, self._registered_password)
                self._token = result.get("access_token", "")
                self._username = self._registered_username
                self.accept()
            except RuntimeError as e:
                # 激活成功但登录失败 → 切回登录页
                self._show_verify_msg(f"激活成功！请返回登录。", False)
                self._login_user.setText(self._registered_username)
                self._login_pwd.setText(self._registered_password)
                QTimer.singleShot(1200, lambda: self._switch_page(0))
        except RuntimeError as e:
            self._show_verify_msg(str(e), True)

    def _on_resend(self) -> None:
        """重新发送验证码（等同于重新注册）。"""
        if not self._registered_username:
            return
        try:
            # 用注册信息重新发送（后端会覆盖之前的验证码）
            self._api.register(
                self._registered_username,
                self._verify_hint.text().replace("验证码已发送至 ", ""),
                self._registered_password,
            )
            self._show_verify_msg("验证码已重新发送", False)
        except RuntimeError as e:
            self._show_verify_msg(str(e), True)

    # ═══════════════════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _make_input(placeholder: str, echo: QLineEdit.EchoMode | None = None) -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setStyleSheet(_INPUT_STYLE)
        if echo is not None:
            inp.setEchoMode(echo)
        return inp

    @staticmethod
    def _make_msg(style: str) -> QLabel:
        lbl = QLabel("")
        lbl.setStyleSheet(style)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.hide()
        return lbl

    def _show_login_error(self, msg: str) -> None:
        self._login_error.setText(msg)
        self._login_error.setStyleSheet(_ERROR_STYLE)
        self._login_error.show()

    def _show_reg_msg(self, msg: str, is_error: bool) -> None:
        self._reg_msg.setText(msg)
        self._reg_msg.setStyleSheet(_ERROR_STYLE if is_error else _SUCCESS_STYLE)
        self._reg_msg.show()

    def _show_verify_msg(self, msg: str, is_error: bool) -> None:
        self._verify_msg.setText(msg)
        self._verify_msg.setStyleSheet(_ERROR_STYLE if is_error else _SUCCESS_STYLE)
        self._verify_msg.show()

    # ═══════════════════════════════════════════════════════
    #  公共接口
    # ═══════════════════════════════════════════════════════

    def get_token(self) -> str | None:
        return self._token

    def get_username(self) -> str:
        return self._username

    def get_api_client(self) -> APIClient:
        return self._api


# ═══════════════════════════════════════════════════════════════
#  向后兼容 LoginDialog 别名
# ═══════════════════════════════════════════════════════════════

LoginDialog = LoginRegisterDialog


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """模块导入测试。"""
    passed, failed = 0, 0
    errors: list[str] = []
    print("=== MF_User.login_dialog self_test ===")
    try:
        from MF_User.login_dialog import LoginRegisterDialog
        assert LoginRegisterDialog is not None
        passed += 1
        print("  [PASS] LoginRegisterDialog 可导入")
    except Exception as e:
        failed += 1
        errors.append(str(e))
    try:
        from MF_User.api_client import APIClient
        assert APIClient is not None
        passed += 1
        print("  [PASS] APIClient 可导入")
    except Exception as e:
        failed += 1
        errors.append(str(e))
    print(f"  [{passed} passed, {failed} failed]")
    print("=== MF_User.login_dialog self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
