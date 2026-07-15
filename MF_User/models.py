# -*- coding: utf-8 -*-
"""MF_User 数据模型 — User 数据类。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    """用户账户。

    Attributes:
        username: 用户名（唯一标识）。
        salt: 随机盐值（hex 字符串）。
        password_hash: SHA-256(盐值 + 密码) 的 hex 字符串。
        created_at: 注册时间。
    """
    username: str
    salt: str
    password_hash: str
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """序列化为 dict（用于存储）。"""
        return {
            "username": self.username,
            "salt": self.salt,
            "password_hash": self.password_hash,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> User:
        """从 dict 反序列化。"""
        return cls(
            username=data["username"],
            salt=data["salt"],
            password_hash=data["password_hash"],
            created_at=datetime.fromisoformat(data.get("created_at", "")),
        )
