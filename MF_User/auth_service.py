# -*- coding: utf-8 -*-
"""AuthService — 运行时认证会话状态单例。

持有在线登录后的 token、用户名、余额等信息。纯内存存储，无文件 I/O。
所有状态修改在主线程的信号槽回调中执行，不需额外加锁。

用法:
    from MF_User.auth_service import AuthService

    auth = AuthService()
    auth.set_auth("eyJ...", "alice")
    print(auth.is_logged_in)  # True
    auth.logout()
"""

from __future__ import annotations


class AuthService:
    """运行时认证状态单例。

    Attributes:
        _token: Bearer token（来自 /login 响应）。
        _username: 当前用户名。
        _email: 用户邮箱（来自 /me 响应）。
        _balance: 账户余额（来自 /me 响应）。
        _is_active: 邮箱是否已验证激活。
    """

    _instance: AuthService | None = None

    def __new__(cls) -> AuthService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._token: str | None = None
        self._username: str = ""
        self._email: str = ""
        self._balance: int = 0
        self._is_active: bool = False

    # ── 属性 ──────────────────────────────────────────────

    @property
    def is_logged_in(self) -> bool:
        """是否已登录（有有效 token）。"""
        return self._token is not None

    @property
    def token(self) -> str | None:
        """Bearer access_token。"""
        return self._token

    @property
    def username(self) -> str:
        """当前用户名。"""
        return self._username

    @property
    def email(self) -> str:
        """当前用户邮箱。"""
        return self._email

    @property
    def balance(self) -> int:
        """账户余额（免费调用次数）。"""
        return self._balance

    @property
    def is_active(self) -> bool:
        """邮箱是否已验证。"""
        return self._is_active

    # ── 状态修改 ──────────────────────────────────────────

    def set_auth(self, token: str, username: str) -> None:
        """保存登录凭证（登录或注册自动登录成功后调用）。

        Args:
            token: Bearer access_token。
            username: 用户名。
        """
        self._token = token
        self._username = username

    def update_profile(self, data: dict) -> None:
        """根据 /me 响应更新用户资料。

        Args:
            data: /me 接口返回的 dict，
                  {"username", "email", "balance", "is_active"}。
        """
        self._email = data.get("email", self._email)
        self._balance = data.get("balance", self._balance)
        self._is_active = data.get("is_active", self._is_active)
        # /me 返回的 username 覆盖（以服务端为准）
        if "username" in data:
            self._username = data["username"]

    def logout(self) -> None:
        """登出，清空所有状态。"""
        self._token = None
        self._username = ""
        self._email = ""
        self._balance = 0
        self._is_active = False


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """验证 AuthService 单例和基本操作。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_User.auth_service self_test ===")

    # 清理单例以便测试
    AuthService._instance = None

    try:
        s1 = AuthService()
        s2 = AuthService()
        assert s1 is s2, "应为单例"
        passed += 1
        print("  [PASS] 单例模式")
    except AssertionError as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        s = AuthService()
        assert not s.is_logged_in, "初始未登录"
        assert s.token is None
        assert s.username == ""
        assert s.balance == 0
        passed += 1
        print("  [PASS] 初始状态（未登录）")
    except AssertionError as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        s = AuthService()
        s.set_auth("test-token-123", "alice")
        assert s.is_logged_in
        assert s.token == "test-token-123"
        assert s.username == "alice"
        passed += 1
        print("  [PASS] set_auth() 设置登录状态")
    except AssertionError as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        s = AuthService()
        s.update_profile({
            "username": "alice",
            "email": "alice@test.com",
            "balance": 15,
            "is_active": True,
        })
        assert s.email == "alice@test.com"
        assert s.balance == 15
        assert s.is_active
        passed += 1
        print("  [PASS] update_profile() 更新资料")
    except AssertionError as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        s = AuthService()
        s.logout()
        assert not s.is_logged_in
        assert s.token is None
        assert s.username == ""
        assert s.balance == 0
        passed += 1
        print("  [PASS] logout() 清空状态")
    except AssertionError as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    # 清理
    AuthService._instance = None

    print(f"  [{passed} passed, {failed} failed]")
    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")
    print("=== MF_User.auth_service self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
