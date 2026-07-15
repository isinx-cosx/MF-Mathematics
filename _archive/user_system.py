# -*- coding: utf-8 -*-
"""UserSystem — 本地用户认证与数据隔离。

- 密码: SHA-256 + 随机盐值 → users_db.json（不存明文）
- 配置隔离: data/users/{username}/ 独立 config.json
- API Key: keyring (OS credential manager)
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any


class UserSystem:
    """本地用户认证与管理。"""

    _DB_PATH: str = ""
    _DATA_DIR: str = ""
    _current_user: str | None = None

    @classmethod
    def init(cls, base_dir: str) -> None:
        """初始化路径。"""
        cls._DB_PATH = os.path.join(base_dir, "data", "users_db.json")
        cls._DATA_DIR = os.path.join(base_dir, "data", "users")
        os.makedirs(os.path.dirname(cls._DB_PATH), exist_ok=True)
        os.makedirs(cls._DATA_DIR, exist_ok=True)
        if not os.path.exists(cls._DB_PATH):
            with open(cls._DB_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f)

    @classmethod
    def register(cls, username: str, password: str) -> tuple[bool, str]:
        """注册新用户。"""
        if not username or not password:
            return False, "用户名和密码不能为空"
        if len(username) < 3:
            return False, "用户名至少 3 个字符"
        if len(password) < 4:
            return False, "密码至少 4 个字符"

        db = cls._load_db()
        if username in db:
            return False, "用户名已存在"

        salt = os.urandom(32).hex()
        pw_hash = hashlib.sha256((password + salt).encode()).hexdigest()

        db[username] = {"salt": salt, "hash": pw_hash}
        cls._save_db(db)

        # 创建用户目录
        user_dir = os.path.join(cls._DATA_DIR, username)
        os.makedirs(user_dir, exist_ok=True)

        # 默认用户配置
        default_config = {
            "theme": "light",
            "font_size": 14,
            "auto_simplify": True,
        }
        config_path = os.path.join(user_dir, "config.json")
        if not os.path.exists(config_path):
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)

        return True, "注册成功"

    @classmethod
    def login(cls, username: str, password: str) -> tuple[bool, str]:
        """登录验证。"""
        db = cls._load_db()
        user = db.get(username)
        if not user:
            return False, "用户名不存在"

        pw_hash = hashlib.sha256((password + user["salt"]).encode()).hexdigest()
        if pw_hash != user["hash"]:
            return False, "密码错误"

        cls._current_user = username
        return True, "登录成功"

    @classmethod
    def logout(cls) -> None:
        cls._current_user = None

    @classmethod
    @property
    def current_user(cls) -> str | None:
        return cls._current_user

    @classmethod
    def get_user_config(cls) -> dict:
        """获取当前用户的 config.json。"""
        if not cls._current_user:
            return {}
        path = os.path.join(cls._DATA_DIR, cls._current_user, "config.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @classmethod
    def save_user_config(cls, config: dict) -> None:
        """保存当前用户的 config.json。"""
        if not cls._current_user:
            return
        path = os.path.join(cls._DATA_DIR, cls._current_user, "config.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    @classmethod
    def store_api_key(cls, provider: str, api_key: str) -> None:
        """使用 keyring 安全存储 API Key。"""
        try:
            import keyring
            svc = f"MF_Mathematics"
            uname = f"{cls._current_user or 'default'}_{provider}_api_key"
            keyring.set_password(svc, uname, api_key)
        except ImportError:
            # 无 keyring → 加密文件回退
            cls._store_api_key_file(provider, api_key)

    @classmethod
    def get_api_key(cls, provider: str) -> str | None:
        """获取 API Key。"""
        try:
            import keyring
            svc = f"MF_Mathematics"
            uname = f"{cls._current_user or 'default'}_{provider}_api_key"
            return keyring.get_password(svc, uname)
        except ImportError:
            return cls._get_api_key_file(provider)

    # ── Internal ────────────────────────────────────────────

    @classmethod
    def _load_db(cls) -> dict:
        with open(cls._DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def _save_db(cls, db: dict) -> None:
        with open(cls._DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)

    @classmethod
    def _store_api_key_file(cls, provider: str, api_key: str) -> None:
        d = os.path.join(cls._DATA_DIR, cls._current_user or "default")
        os.makedirs(d, exist_ok=True)
        # Simple XOR obfuscation
        key_bytes = api_key.encode()
        mask = os.urandom(len(key_bytes))
        enc = bytes(a ^ b for a, b in zip(key_bytes, mask))
        with open(os.path.join(d, f".{provider}_key.bin"), "wb") as f:
            f.write(mask + enc)

    @classmethod
    def _get_api_key_file(cls, provider: str) -> str | None:
        d = os.path.join(cls._DATA_DIR, cls._current_user or "default")
        path = os.path.join(d, f".{provider}_key.bin")
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            data = f.read()
        half = len(data) // 2
        mask, enc = data[:half], data[half:]
        return "".join(chr(a ^ b) for a, b in zip(mask, enc))
