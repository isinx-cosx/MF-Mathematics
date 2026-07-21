# -*- coding: utf-8 -*-
"""API 客户端 — 与 FastAPI 后端通信（登录、注册、验证码）。"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
import urllib.parse


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def _api_post(url: str, data: dict | str, headers: dict | None = None,
              is_form: bool = False) -> dict:
    """发送 POST 请求，返回解析后的 JSON。

    Args:
        url: 完整 URL。
        data: 请求体（dict → JSON 自动序列化；str → 直接发送）。
        headers: 额外请求头。
        is_form: True 时用 application/x-www-form-urlencoded。

    Returns:
        解析后的 dict。

    Raises:
        RuntimeError: 网络错误或 HTTP 非 2xx。
    """
    if is_form and isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode("utf-8")
    elif isinstance(data, dict):
        body = json.dumps(data).encode("utf-8")
    else:
        body = data.encode("utf-8") if isinstance(data, str) else data

    req_headers = {"Content-Type": "application/x-www-form-urlencoded" if is_form else "application/json"}
    if headers:
        req_headers.update(headers)

    try:
        req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            detail = err_body.get("detail", f"HTTP {e.code}")
        except Exception:
            detail = f"HTTP {e.code}: {e.reason}"
        raise RuntimeError(detail)
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接到服务器 ({e.reason})")
    except json.JSONDecodeError:
        raise RuntimeError("服务器返回了无效数据")


class APIClient:
    """与 MF-Mathematics FastAPI 后端通信的客户端。"""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._access_token: str | None = None

    @property
    def token(self) -> str | None:
        return self._access_token

    @token.setter
    def token(self, value: str | None) -> None:
        self._access_token = value

    # ── 登录 ──────────────────────────────────────────────

    def login(self, username: str, password: str) -> dict:
        """登录并获取 access_token。

        Returns:
            {"access_token": ..., "token_type": "bearer"}

        Raises:
            RuntimeError: 登录失败。
        """
        data = {"username": username, "password": password}
        result = _api_post(f"{self.base_url}/login", data, is_form=True)
        self._access_token = result.get("access_token")
        return result

    # ── 注册 ──────────────────────────────────────────────

    def register(self, username: str, email: str, password: str) -> dict:
        """注册新用户。

        Returns:
            {"msg": "..."}

        Raises:
            RuntimeError: 注册失败（用户名已存在、邮箱已注册等）。
        """
        data = {"username": username, "email": email, "password": password}
        return _api_post(f"{self.base_url}/register", data)

    # ── 验证码 ────────────────────────────────────────────

    def verify_code(self, username: str, code: str) -> dict:
        """提交邮箱验证码，激活账户。

        Returns:
            {"msg": "验证成功，账户已激活！"}

        Raises:
            RuntimeError: 验证失败（验证码错误、已过期等）。
        """
        data = {"username": username, "code": code}
        return _api_post(f"{self.base_url}/verify-code", data, is_form=True)

    # ── 用户信息 ──────────────────────────────────────────

    def get_me(self) -> dict:
        """获取当前登录用户信息。

        Returns:
            {"username": ..., "email": ..., "balance": ..., "is_active": ...}

        Raises:
            RuntimeError: Token 无效或已过期。
        """
        if not self._access_token:
            raise RuntimeError("未登录")
        headers = {"Authorization": f"Bearer {self._access_token}"}
        # GET 请求
        req = urllib.request.Request(
            f"{self.base_url}/me", headers=headers, method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self._access_token = None
                raise RuntimeError("登录已过期，请重新登录")
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                raise RuntimeError(err_body.get("detail", f"HTTP {e.code}"))
            except json.JSONDecodeError:
                raise RuntimeError(f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"无法连接到服务器 ({e.reason})")
