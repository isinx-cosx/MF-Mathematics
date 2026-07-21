# -*- coding: utf-8 -*-
"""UserManager — 用户管理单例，JSON 持久化 + 在线 API 鉴权。"""

from __future__ import annotations

import hashlib
import json
import os
import secrets

from MF_User.models import User
from MF_User.api_client import APIClient

_USER_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "users.json")


def _hash_password(password: str, salt: str) -> str:
    """SHA-256(盐值 + 密码)，返回 hex 字符串。"""
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


class UserManager:
    """用户管理单例 — JSON 文件持久化存储。

    用法:
        mgr = UserManager()
        user = mgr.register("alice", "secret123")
        user = mgr.login("alice", "secret123")
        mgr.logout()
    """

    _instance: UserManager | None = None

    def __new__(cls) -> UserManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._users: dict[str, User] = {}
        self._current_user: User | None = None
        self._api_token: str | None = None
        self._api_username: str = ""
        self._api_balance: int = 0
        self._load()

    # ── API 鉴权 ──────────────────────────────────────────

    @property
    def api_token(self) -> str | None:
        """在线 API 的 access_token。"""
        return self._api_token

    @property
    def api_balance(self) -> int:
        """在线账户余额。"""
        return self._api_balance

    def set_api_auth(self, token: str, username: str) -> None:
        """设置 API 鉴权信息（登录成功后调用）。"""
        self._api_token = token
        self._api_username = username
        self._current_user = User(username=username, salt="", password_hash="")

    def fetch_online_balance(self) -> int:
        """从在线 API 获取余额。"""
        if not self._api_token:
            return 0
        try:
            client = APIClient()
            client.token = self._api_token
            info = client.get_me()
            self._api_balance = info.get("balance", 0)
            return self._api_balance
        except Exception:
            return self._api_balance

    # ── 注册 ──────────────────────────────────────────────

    def register(self, username: str, password: str) -> tuple[User | None, str]:
        """注册新用户。

        Args:
            username: 用户名（≥3 字符，仅含字母数字下划线）。
            password: 密码（≥6 字符）。

        Returns:
            (User, "") 成功；或 (None, 错误信息) 失败。
        """
        # 验证用户名
        username = username.strip()
        if len(username) < 3:
            return None, "用户名至少需要 3 个字符"
        if not username.replace("_", "").isalnum():
            return None, "用户名只能包含字母、数字和下划线"

        # 检查重复
        if username.lower() in (u.lower() for u in self._users):
            return None, f"用户名 '{username}' 已被注册"

        # 验证密码
        if len(password) < 6:
            return None, "密码至少需要 6 个字符"

        # 生成盐值 + 哈希
        salt = secrets.token_hex(16)  # 32 字符随机盐
        password_hash = _hash_password(password, salt)

        user = User(username=username, salt=salt, password_hash=password_hash)
        self._users[username] = user
        self._current_user = user  # 注册即登录
        self._save()
        return user, ""

    # ── 持久化 ────────────────────────────────────────────

    def _save(self) -> None:
        """保存用户数据到 JSON 文件。"""
        try:
            data = {
                u: {"username": v.username, "salt": v.salt, "password_hash": v.password_hash}
                for u, v in self._users.items()
            }
            with open(_USER_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _load(self) -> None:
        """从 JSON 文件加载用户数据。"""
        try:
            if os.path.exists(_USER_FILE):
                with open(_USER_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for username, d in data.items():
                    self._users[username] = User(
                        username=d["username"], salt=d["salt"],
                        password_hash=d["password_hash"],
                    )
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    # ── 登录 ──────────────────────────────────────────────

    def login(self, username: str, password: str) -> tuple[User | None, str]:
        """用户登录。

        Args:
            username: 用户名。
            password: 密码。

        Returns:
            (User, "") 成功；或 (None, 错误信息) 失败。
        """
        username = username.strip()
        if not username:
            return None, "请输入用户名"

        # 大小写不敏感查找
        matched_key = None
        for key in self._users:
            if key.lower() == username.lower():
                matched_key = key
                break

        if matched_key is None:
            return None, "用户名或密码错误"

        user = self._users[matched_key]
        if _hash_password(password, user.salt) != user.password_hash:
            return None, "用户名或密码错误"

        self._current_user = user
        return user, ""

    # ── 登出 ──────────────────────────────────────────────

    def logout(self) -> None:
        """退出当前登录。"""
        self._current_user = None

    # ── 状态 ──────────────────────────────────────────────

    @property
    def is_logged_in(self) -> bool:
        return self._current_user is not None

    @property
    def current_user(self) -> User | None:
        return self._current_user

    @property
    def user_count(self) -> int:
        return len(self._users)

    def get_all_users(self) -> list[User]:
        """获取所有注册用户列表。"""
        return list(self._users.values())


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """验证 UserManager 基本功能。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_User.manager self_test ===")

    mgr = UserManager()

    # 单例
    mgr2 = UserManager()
    assert mgr is mgr2, "应为单例"
    passed += 1
    print("  [PASS] 单例模式")

    # 注册
    user, err = mgr.register("testuser", "pass123")
    assert user is not None, f"注册失败: {err}"
    assert user.username == "testuser"
    assert mgr.is_logged_in
    assert mgr.current_user is user
    passed += 1
    print("  [PASS] 注册 + 自动登录")

    # 密码哈希不为明文
    assert user.password_hash != "pass123", "密码不应存明文"
    passed += 1
    print("  [PASS] 密码已哈希")

    # 登出
    mgr.logout()
    assert not mgr.is_logged_in
    passed += 1
    print("  [PASS] 登出")

    # 登录
    user2, err = mgr.login("testuser", "pass123")
    assert user2 is not None, f"登录失败: {err}"
    assert mgr.is_logged_in
    passed += 1
    print("  [PASS] 登录成功")

    # 错误密码
    user3, err = mgr.login("testuser", "wrongpass")
    assert user3 is None, "错误密码应拒绝"
    passed += 1
    print("  [PASS] 错误密码拒绝")

    # 重复注册
    user4, err = mgr.register("testuser", "other")
    assert user4 is None, "重复用户名应拒绝"
    passed += 1
    print("  [PASS] 重复注册拒绝")

    # 短密码
    user5, err = mgr.register("newuser", "12345")
    assert user5 is None, "短密码应拒绝"
    passed += 1
    print("  [PASS] 短密码拒绝")

    # 大小写不敏感登录
    user6, err = mgr.login("TestUser", "pass123")
    assert user6 is not None, "大小写不敏感登录"
    passed += 1
    print("  [PASS] 大小写不敏感登录")

    print(f"  [{passed} passed, {failed} failed]")
    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")
    print("=== MF_User.manager self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
