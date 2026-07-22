# -*- coding: utf-8 -*-
"""LoginRegisterDialog — 统一登录/注册/邮箱验证对话框。

功能对标 C:/MVS/static/index.html 网站版认证模态框：
  - 登录/注册 Tab 切换 + 独立邮箱验证页
  - 发送验证码 → 60s 冷却倒计时
  - 注册成功 → 链式自动登录 → 获取余额
  - 所有 API 调用通过 AuthWorker 在线程中执行，不阻塞 UI

风格沿用桌面端 QSS 主题，使用 apply_dialog_title_bar() + apply_shadow()。

用法:
    from MF_User.login_dialog import LoginRegisterDialog

    dlg = LoginRegisterDialog(parent)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        # 登录成功，AuthService 已更新
        from MF_User.auth_service import AuthService
        print(AuthService().username)
"""

from __future__ import annotations

import re as _re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from MF_User.api_client import APIClient
from MF_User.auth_service import AuthService
from MF_User.auth_worker import AuthWorker


class LoginRegisterDialog(QDialog):
    """统一登录/注册对话框 — 含邮箱验证码流程。

    登录/注册成功时内部调用 AuthService().set_auth()，
    然后 accept() 关闭对话框。
    """

    # 登录成功信号（token, username）
    login_successful = Signal(str, str)

    def __init__(self, parent: QWidget | None = None,
                 start_page: int = 0) -> None:
        """初始化对话框。

        Args:
            parent: 父窗口。
            start_page: 初始页面索引（0=登录, 1=注册, 2=验证）。
        """
        super().__init__(parent)
        self.setWindowTitle("账户 — MF-Mathematics")
        self.setFixedSize(500, 680)
        self.setObjectName("loginRegisterDialog")

        # 内部状态
        self._pending_email: str = ""   # 用于验证页重新发送
        self._pending_username: str = ""
        self._pending_password: str = ""
        self._cooldown_timer: QTimer | None = None
        self._cooldown_seconds: int = 0
        self._active_worker: AuthWorker | None = None

        self._build_ui()
        self._switch_tab(start_page)

    # ═══════════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """构建完整对话框 UI。"""
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── MF-Mathematics 风格标题栏 ──
        from MF_UI.components.mf_dialog import apply_dialog_title_bar
        apply_dialog_title_bar(self, "账户")

        # ── Tab 栏 ──
        tab_row = QHBoxLayout()
        tab_row.setSpacing(0)
        tab_row.setContentsMargins(0, 0, 0, 0)

        self._tab_login = QPushButton("登  录")
        self._tab_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_login.clicked.connect(lambda: self._switch_tab(0))

        self._tab_register = QPushButton("注  册")
        self._tab_register.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_register.clicked.connect(lambda: self._switch_tab(1))

        tab_row.addWidget(self._tab_login)
        tab_row.addWidget(self._tab_register)
        tab_row.addStretch()

        tab_widget = QWidget()
        tab_widget.setLayout(tab_row)
        root.addWidget(tab_widget)

        # ── 页面栈 ──
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_login_page())
        self._stack.addWidget(self._build_register_page())
        self._stack.addWidget(self._build_verify_page())
        root.addWidget(self._stack, 1)

        # ── 继承父窗口 QSS ──
        if self.parent() and hasattr(self.parent(), 'styleSheet'):
            parent_qss = self.parent().styleSheet()
            if parent_qss:
                self.setStyleSheet(parent_qss)

    # ── 登录页 ────────────────────────────────────────────

    def _build_login_page(self) -> QWidget:
        """构建登录页面。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 16, 28, 20)

        # 标题
        title = QLabel("欢迎回来")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(8)

        # 用户名字段
        user_lbl = QLabel("用户名")
        user_lbl.setObjectName("fieldLabel")
        layout.addWidget(user_lbl)
        self._login_user = QLineEdit()
        self._login_user.setPlaceholderText("请输入用户名")
        layout.addWidget(self._login_user)

        # 密码字段
        pwd_lbl = QLabel("密码")
        pwd_lbl.setObjectName("fieldLabel")
        layout.addWidget(pwd_lbl)
        self._login_pwd = QLineEdit()
        self._login_pwd.setPlaceholderText("请输入密码")
        self._login_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._login_pwd.returnPressed.connect(self._on_login)
        layout.addWidget(self._login_pwd)

        # 消息标签
        self._login_msg = QLabel("")
        self._login_msg.setObjectName("loginMsg")
        self._login_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._login_msg.setWordWrap(True)
        self._login_msg.hide()
        layout.addWidget(self._login_msg)

        # 登录按钮
        login_btn = QPushButton("登  录")
        login_btn.setObjectName("primaryBtn")
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.clicked.connect(self._on_login)
        layout.addWidget(login_btn)

        layout.addStretch()

        # 底部切换链接
        bottom = QHBoxLayout()
        bottom.addStretch()
        link = QPushButton("还没有账号？立即注册")
        link.setObjectName("linkBtn")
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(lambda: self._switch_tab(1))
        bottom.addWidget(link)
        bottom.addStretch()
        layout.addLayout(bottom)

        return page

    # ── 注册页 ────────────────────────────────────────────

    def _build_register_page(self) -> QWidget:
        """构建注册页面（对标网站版 5 字段布局）。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(6)
        layout.setContentsMargins(28, 10, 28, 14)

        # 标题
        title = QLabel("创建账号")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # 用户名
        user_lbl = QLabel("用户名")
        user_lbl.setObjectName("fieldLabel")
        layout.addWidget(user_lbl)
        self._reg_user = QLineEdit()
        self._reg_user.setPlaceholderText("3-20 个字符，字母数字下划线")
        layout.addWidget(self._reg_user)

        # 邮箱 + 发送验证码
        email_lbl = QLabel("邮箱")
        email_lbl.setObjectName("fieldLabel")
        layout.addWidget(email_lbl)
        email_row = QHBoxLayout()
        email_row.setSpacing(8)
        self._reg_email = QLineEdit()
        self._reg_email.setPlaceholderText("your@email.com")
        email_row.addWidget(self._reg_email, 1)
        self._send_code_btn = QPushButton("发送验证码")
        self._send_code_btn.setObjectName("secondaryBtn")
        self._send_code_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_code_btn.clicked.connect(self._on_send_code)
        email_row.addWidget(self._send_code_btn)
        layout.addLayout(email_row)

        # 验证码
        code_lbl = QLabel("验证码")
        code_lbl.setObjectName("fieldLabel")
        layout.addWidget(code_lbl)
        self._reg_code = QLineEdit()
        self._reg_code.setPlaceholderText("输入 6 位验证码")
        self._reg_code.setMaxLength(6)
        self._reg_code.setObjectName("codeInput")
        layout.addWidget(self._reg_code)

        # 密码
        pwd_lbl = QLabel("密码")
        pwd_lbl.setObjectName("fieldLabel")
        layout.addWidget(pwd_lbl)
        self._reg_pwd = QLineEdit()
        self._reg_pwd.setPlaceholderText("至少 6 个字符")
        self._reg_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._reg_pwd)

        # 确认密码
        confirm_lbl = QLabel("确认密码")
        confirm_lbl.setObjectName("fieldLabel")
        layout.addWidget(confirm_lbl)
        self._reg_confirm = QLineEdit()
        self._reg_confirm.setPlaceholderText("再次输入密码")
        self._reg_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._reg_confirm.returnPressed.connect(self._on_register)
        layout.addWidget(self._reg_confirm)

        # 消息标签
        self._reg_msg = QLabel("")
        self._reg_msg.setObjectName("regMsg")
        self._reg_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._reg_msg.setWordWrap(True)
        self._reg_msg.hide()
        layout.addWidget(self._reg_msg)

        # 注册按钮
        reg_btn = QPushButton("注  册")
        reg_btn.setObjectName("primaryBtn")
        reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reg_btn.clicked.connect(self._on_register)
        layout.addWidget(reg_btn)

        layout.addStretch()

        # 底部切换链接
        bottom = QHBoxLayout()
        bottom.addStretch()
        link = QPushButton("已有账号？返回登录")
        link.setObjectName("linkBtn")
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(lambda: self._switch_tab(0))
        bottom.addWidget(link)
        bottom.addStretch()
        layout.addLayout(bottom)

        return page

    # ── 验证页 ────────────────────────────────────────────

    def _build_verify_page(self) -> QWidget:
        """构建独立邮箱验证页面。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 20, 28, 20)

        # 图标
        icon = QLabel("\U0001f4e7")  # 📧
        icon.setStyleSheet("font-size:40px;background:transparent;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        # 标题
        self._verify_title = QLabel("邮箱验证")
        self._verify_title.setObjectName("dialogTitle")
        self._verify_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._verify_title)

        # 提示文字
        self._verify_hint = QLabel("验证码已发送至 your@email.com")
        self._verify_hint.setObjectName("verifyHint")
        self._verify_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._verify_hint.setWordWrap(True)
        layout.addWidget(self._verify_hint)

        # 验证码输入
        self._verify_code_input = QLineEdit()
        self._verify_code_input.setPlaceholderText("输入 6 位验证码")
        self._verify_code_input.setMaxLength(6)
        self._verify_code_input.setObjectName("codeInput")
        self._verify_code_input.returnPressed.connect(self._on_verify)
        layout.addWidget(self._verify_code_input)

        # 消息标签
        self._verify_msg = QLabel("")
        self._verify_msg.setObjectName("verifyMsg")
        self._verify_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._verify_msg.setWordWrap(True)
        self._verify_msg.hide()
        layout.addWidget(self._verify_msg)

        # 验证按钮
        verify_btn = QPushButton("验  证")
        verify_btn.setObjectName("primaryBtn")
        verify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        verify_btn.clicked.connect(self._on_verify)
        layout.addWidget(verify_btn)

        # 重新发送
        resend_row = QHBoxLayout()
        resend_row.addStretch()
        self._resend_btn = QPushButton("重新发送验证码")
        self._resend_btn.setObjectName("linkBtn")
        self._resend_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._resend_btn.clicked.connect(self._on_resend)
        resend_row.addWidget(self._resend_btn)
        resend_row.addStretch()
        layout.addLayout(resend_row)

        layout.addStretch()
        return page

    # ═══════════════════════════════════════════════════════
    #  页面切换
    # ═══════════════════════════════════════════════════════

    def _switch_tab(self, index: int) -> None:
        """切换 QStackedWidget 页面并更新 tab 按钮样式。

        Args:
            index: 0=登录, 1=注册, 2=验证。
        """
        self._stack.setCurrentIndex(index)
        self._apply_tab_styles(index)
        self._hide_all_msgs()

        # 设置焦点
        if index == 0:
            self._login_user.setFocus()
        elif index == 1:
            self._reg_user.setFocus()
        elif index == 2:
            self._verify_code_input.setFocus()

    def _apply_tab_styles(self, active_index: int) -> None:
        """更新 tab 按钮的 objectName 以触发 QSS 样式切换。"""
        if active_index == 0:
            self._tab_login.setObjectName("tabBtnActive")
            self._tab_register.setObjectName("tabBtn")
        elif active_index == 1:
            self._tab_login.setObjectName("tabBtn")
            self._tab_register.setObjectName("tabBtnActive")
        else:
            # 验证页：两个 tab 都非活跃
            self._tab_login.setObjectName("tabBtn")
            self._tab_register.setObjectName("tabBtn")
        # 强制重新加载 QSS
        self._tab_login.style().unpolish(self._tab_login)
        self._tab_login.style().polish(self._tab_login)
        self._tab_register.style().unpolish(self._tab_register)
        self._tab_register.style().polish(self._tab_register)

    # ═══════════════════════════════════════════════════════
    #  登录
    # ═══════════════════════════════════════════════════════

    def _on_login(self) -> None:
        """处理登录表单提交。"""
        username = self._login_user.text().strip()
        password = self._login_pwd.text()

        if not username:
            self._show_msg(self._login_msg, "请输入用户名", True)
            return
        if not password:
            self._show_msg(self._login_msg, "请输入密码", True)
            return

        self._set_login_enabled(False)
        self._login_msg.hide()

        worker = AuthWorker(
            self, lambda: APIClient().login(username, password)
        )
        worker.succeeded.connect(
            lambda data: self._on_login_success(data, username)
        )
        worker.failed.connect(self._on_login_error)
        self._active_worker = worker
        worker.start()

    def _on_login_success(self, data: dict, username: str) -> None:
        """登录成功回调（主线程）。"""
        token = data.get("access_token", "")
        if not token:
            self._show_msg(self._login_msg, "服务器返回异常：缺少 token", True)
            self._set_login_enabled(True)
            return

        # 保存到 AuthService
        AuthService().set_auth(token, username)
        self.login_successful.emit(token, username)
        self.accept()

    def _on_login_error(self, msg: str) -> None:
        """登录失败回调（主线程）。"""
        self._show_msg(self._login_msg, msg, True)
        self._set_login_enabled(True)

    # ═══════════════════════════════════════════════════════
    #  发送验证码
    # ═══════════════════════════════════════════════════════

    def _on_send_code(self) -> None:
        """处理发送验证码按钮点击。"""
        email = self._reg_email.text().strip()
        if not email or not _re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            self._show_msg(self._reg_msg, "请先输入有效的邮箱地址", True)
            return

        if self._cooldown_seconds > 0:
            self._show_msg(self._reg_msg, f"请 {self._cooldown_seconds} 秒后再试", True)
            return

        self._reg_msg.hide()
        self._send_code_btn.setEnabled(False)
        self._send_code_btn.setText("发送中…")

        worker = AuthWorker(
            self, lambda: APIClient().send_code(email)
        )
        worker.succeeded.connect(
            lambda data: self._on_send_code_success(data, email)
        )
        worker.failed.connect(self._on_send_code_error)
        self._active_worker = worker
        worker.start()

    def _on_send_code_success(self, data: dict, email: str) -> None:
        """发送验证码成功回调。"""
        msg = data.get("msg", f"验证码已发送至 {email}，5 分钟内有效")
        self._show_msg(self._reg_msg, msg, False)
        self._reg_code.setFocus()
        self._start_cooldown()

    def _on_send_code_error(self, msg: str) -> None:
        """发送验证码失败回调。"""
        self._show_msg(self._reg_msg, msg, True)
        self._send_code_btn.setEnabled(True)
        self._send_code_btn.setText("发送验证码")

    # ═══════════════════════════════════════════════════════
    #  注册
    # ═══════════════════════════════════════════════════════

    def _on_register(self) -> None:
        """处理注册表单提交。"""
        username = self._reg_user.text().strip()
        email = self._reg_email.text().strip()
        code = self._reg_code.text().strip()
        pwd = self._reg_pwd.text()
        confirm = self._reg_confirm.text()

        # 客户端验证（与网站版一致）
        if not username or len(username) < 3:
            self._show_msg(self._reg_msg, "用户名至少需要 3 个字符", True)
            return
        if not _re.match(r"[a-zA-Z0-9_]+$", username):
            self._show_msg(self._reg_msg, "用户名仅支持字母、数字和下划线", True)
            return
        if not email or not _re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
            self._show_msg(self._reg_msg, "请输入有效的邮箱地址", True)
            return
        if len(code) != 6 or not code.isdigit():
            self._show_msg(self._reg_msg, "请输入 6 位数字验证码", True)
            return
        if len(pwd) < 6:
            self._show_msg(self._reg_msg, "密码至少需要 6 个字符", True)
            return
        if pwd != confirm:
            self._show_msg(self._reg_msg, "两次输入的密码不一致", True)
            return

        self._set_register_enabled(False)
        self._reg_msg.hide()

        # 保存待用（验证页回退用）
        self._pending_username = username
        self._pending_email = email
        self._pending_password = pwd

        worker = AuthWorker(
            self, lambda: APIClient().register(username, email, pwd, code)
        )
        worker.succeeded.connect(
            lambda data: self._on_register_success(data, username, pwd)
        )
        worker.failed.connect(self._on_register_error)
        self._active_worker = worker
        worker.start()

    def _on_register_success(self, data: dict, username: str, password: str) -> None:
        """注册成功回调 → 链式自动登录（与网站版一致）。"""
        msg = data.get("msg", "注册成功！正在登录…")
        self._show_msg(self._reg_msg, msg, False)

        # 链式自动登录
        worker = AuthWorker(
            self, lambda: APIClient().login(username, password)
        )
        worker.succeeded.connect(
            lambda login_data: self._on_register_auto_login(login_data, username)
        )
        worker.failed.connect(
            lambda err: self._on_register_login_failed(err, username, password)
        )
        self._active_worker = worker
        worker.start()

    def _on_register_error(self, msg: str) -> None:
        """注册失败回调。"""
        self._show_msg(self._reg_msg, msg, True)
        self._set_register_enabled(True)

    def _on_register_auto_login(self, data: dict, username: str) -> None:
        """注册后自动登录成功回调。"""
        token = data.get("access_token", "")
        if token:
            AuthService().set_auth(token, username)
            self.login_successful.emit(token, username)
        # 短暂延迟后关闭（让用户看到成功消息）
        QTimer.singleShot(800, self.accept)

    def _on_register_login_failed(self, msg: str, username: str,
                                   password: str) -> None:
        """注册成功但自动登录失败 → 切回登录页并预填。"""
        self._show_msg(self._reg_msg, "注册成功！请返回登录。", False)
        # 预填登录页
        self._login_user.setText(username)
        self._login_pwd.setText(password)
        QTimer.singleShot(1200, lambda: self._switch_tab(0))

    # ═══════════════════════════════════════════════════════
    #  邮箱验证（独立页）
    # ═══════════════════════════════════════════════════════

    def show_verify_page(self, email: str, username: str = "",
                          password: str = "") -> None:
        """从外部打开验证页（如登录时返回 403 未激活）。

        Args:
            email: 用户邮箱。
            username: 用户名（用于自动登录）。
            password: 密码（用于自动登录）。
        """
        self._pending_email = email
        self._pending_username = username
        self._pending_password = password
        self._verify_hint.setText(f"验证码已发送至 {email}")
        self._switch_tab(2)

    def _on_verify(self) -> None:
        """处理验证码提交。"""
        code = self._verify_code_input.text().strip()
        if len(code) != 6 or not code.isdigit():
            self._show_msg(self._verify_msg, "请输入 6 位数字验证码", True)
            return

        if not self._pending_username:
            self._show_msg(self._verify_msg, "缺少用户名信息，请重新注册", True)
            return

        self._set_verify_enabled(False)
        self._verify_msg.hide()

        worker = AuthWorker(
            self,
            lambda: APIClient().verify_code(self._pending_username, code)
        )
        worker.succeeded.connect(self._on_verify_success)
        worker.failed.connect(self._on_verify_error)
        self._active_worker = worker
        worker.start()

    def _on_verify_success(self, data: dict) -> None:
        """验证成功回调 → 链式自动登录。"""
        msg = data.get("msg", "验证成功！")
        self._show_msg(self._verify_msg, msg, False)

        if self._pending_username and self._pending_password:
            # 自动登录
            worker = AuthWorker(
                self,
                lambda: APIClient().login(
                    self._pending_username, self._pending_password
                )
            )
            worker.succeeded.connect(
                lambda d: self._on_verify_auto_login(d)
            )
            worker.failed.connect(
                lambda err: QTimer.singleShot(
                    1000, lambda: self._switch_tab(0)
                )
            )
            self._active_worker = worker
            worker.start()
        else:
            QTimer.singleShot(1000, self.accept)

    def _on_verify_error(self, msg: str) -> None:
        """验证失败回调。"""
        self._show_msg(self._verify_msg, msg, True)
        self._set_verify_enabled(True)

    def _on_verify_auto_login(self, data: dict) -> None:
        """验证后自动登录成功。"""
        token = data.get("access_token", "")
        if token and self._pending_username:
            AuthService().set_auth(token, self._pending_username)
        QTimer.singleShot(600, self.accept)

    # ── 重新发送验证码 ──────────────────────────────────────

    def _on_resend(self) -> None:
        """验证页重新发送验证码（向 /send-code 重新请求）。"""
        if not self._pending_email:
            self._show_msg(self._verify_msg, "无法重新发送，请返回注册", True)
            return

        self._verify_msg.hide()
        self._resend_btn.setEnabled(False)
        self._resend_btn.setText("发送中…")

        worker = AuthWorker(
            self,
            lambda: APIClient().send_code(self._pending_email)
        )
        worker.succeeded.connect(
            lambda data: self._on_resend_success(data)
        )
        worker.failed.connect(
            lambda msg: self._on_resend_error(msg)
        )
        self._active_worker = worker
        worker.start()

    def _on_resend_success(self, data: dict) -> None:
        """重新发送验证码成功。"""
        msg = data.get("msg", f"验证码已重新发送至 {self._pending_email}")
        self._show_msg(self._verify_msg, msg, False)
        self._verify_code_input.clear()
        self._verify_code_input.setFocus()
        self._resend_btn.setEnabled(True)
        self._resend_btn.setText("重新发送验证码")
        self._start_cooldown()

    def _on_resend_error(self, msg: str) -> None:
        """重新发送验证码失败。"""
        self._show_msg(self._verify_msg, msg, True)
        self._resend_btn.setEnabled(True)
        self._resend_btn.setText("重新发送验证码")

    # ═══════════════════════════════════════════════════════
    #  辅助方法
    # ═══════════════════════════════════════════════════════

    def _show_msg(self, label: QLabel, text: str, is_error: bool) -> None:
        """显示消息标签。

        Args:
            label: 目标 QLabel。
            text: 消息文本。
            is_error: True=红色错误, False=绿色成功。
        """
        label.setText(text)
        label.setStyleSheet(
            f"font-size:12px;color:{'#ef4444' if is_error else '#10b981'};"
            "background:transparent;"
        )
        label.show()

    def _hide_all_msgs(self) -> None:
        """隐藏所有消息标签。"""
        for lbl in [self._login_msg, self._reg_msg, self._verify_msg]:
            lbl.hide()

    def _set_login_enabled(self, enabled: bool) -> None:
        """启用/禁用登录页表单。"""
        self._login_user.setEnabled(enabled)
        self._login_pwd.setEnabled(enabled)
        # 查找登录按钮（primaryBtn）
        login_page = self._stack.widget(0)
        for child in login_page.findChildren(QPushButton):
            if child.objectName() == "primaryBtn":
                child.setEnabled(enabled)
                child.setText("处理中…" if not enabled else "登  录")

    def _set_register_enabled(self, enabled: bool) -> None:
        """启用/禁用注册页表单。"""
        self._reg_user.setEnabled(enabled)
        self._reg_email.setEnabled(enabled)
        self._reg_code.setEnabled(enabled)
        self._reg_pwd.setEnabled(enabled)
        self._reg_confirm.setEnabled(enabled)
        if enabled:
            self._send_code_btn.setEnabled(
                self._cooldown_seconds <= 0
            )
        reg_page = self._stack.widget(1)
        for child in reg_page.findChildren(QPushButton):
            if child.objectName() == "primaryBtn":
                child.setEnabled(enabled)
                child.setText("处理中…" if not enabled else "注  册")

    def _set_verify_enabled(self, enabled: bool) -> None:
        """启用/禁用验证页表单。"""
        self._verify_code_input.setEnabled(enabled)
        verify_page = self._stack.widget(2)
        for child in verify_page.findChildren(QPushButton):
            if child.objectName() == "primaryBtn":
                child.setEnabled(enabled)
                child.setText("处理中…" if not enabled else "验  证")

    # ── 60 秒倒计时 ──────────────────────────────────────

    def _start_cooldown(self) -> None:
        """启动 60 秒发送验证码冷却倒计时。"""
        self._cooldown_seconds = 60
        self._send_code_btn.setEnabled(False)
        self._send_code_btn.setText(f"{self._cooldown_seconds}s")

        if self._cooldown_timer is None:
            self._cooldown_timer = QTimer(self)
            self._cooldown_timer.timeout.connect(self._update_cooldown)

        self._cooldown_timer.start(1000)

    def _update_cooldown(self) -> None:
        """倒计时更新（每秒触发）。"""
        self._cooldown_seconds -= 1
        if self._cooldown_seconds <= 0:
            self._cooldown_timer.stop()
            self._send_code_btn.setEnabled(True)
            self._send_code_btn.setText("发送验证码")
        else:
            self._send_code_btn.setText(f"{self._cooldown_seconds}s")

    # ═══════════════════════════════════════════════════════
    #  生命周期
    # ═══════════════════════════════════════════════════════

    def closeEvent(self, event) -> None:
        """对话框关闭时清理：停止倒计时、取消活跃 Worker。"""
        if self._cooldown_timer is not None:
            self._cooldown_timer.stop()
        if self._active_worker is not None and self._active_worker.isRunning():
            self._active_worker.cancel()
        super().closeEvent(event)


# ═══════════════════════════════════════════════════════════════
#  向后兼容别名
# ═══════════════════════════════════════════════════════════════

LoginDialog = LoginRegisterDialog


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """验证对话框可导入和基本结构。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_User.login_dialog self_test ===")

    try:
        from MF_User.login_dialog import LoginRegisterDialog
        assert LoginRegisterDialog is not None
        assert issubclass(LoginRegisterDialog, QDialog)
        passed += 1
        print("  [PASS] LoginRegisterDialog 可导入，是 QDialog 子类")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        from MF_User.login_dialog import LoginDialog
        assert LoginDialog is LoginRegisterDialog
        passed += 1
        print("  [PASS] LoginDialog 别名指向 LoginRegisterDialog")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        # 验证所需方法存在
        dlg_class = LoginRegisterDialog
        assert hasattr(dlg_class, "login_successful")
        assert hasattr(dlg_class, "show_verify_page")
        for method in ["_on_login", "_on_send_code", "_on_register",
                        "_on_verify", "_on_resend"]:
            assert hasattr(dlg_class, method), f"缺少方法 {method}"
        passed += 1
        print("  [PASS] 所有关键方法存在")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    print(f"  [{passed} passed, {failed} failed]")
    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")
    print("=== MF_User.login_dialog self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
