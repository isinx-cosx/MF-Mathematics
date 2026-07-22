# -*- coding: utf-8 -*-
"""API 客户端 — 与 FastAPI 后端通信（登录、注册、验证码、用户信息）。

所有方法为同步阻塞调用，由 AuthWorker 在后台线程中执行。
每个 AuthWorker 创建独立的 APIClient 实例，无跨线程共享状态。

用法:
    from MF_User.api_client import APIClient

    client = APIClient()
    result = client.login("alice", "mypassword")
    info = client.get_me("eyJ...token...")
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
import urllib.parse

DEFAULT_BASE_URL = "https://mf-vis-science.cn"
DEFAULT_TIMEOUT = 10  # 秒


def _api_post(url: str, data: dict, *,
              is_form: bool = False,
              headers: dict | None = None,
              timeout: int = DEFAULT_TIMEOUT) -> dict:
    """发送 POST 请求，返回解析后的 JSON dict。

    Args:
        url: 完整 URL。
        data: 请求体 dict。
        is_form: True 时用 application/x-www-form-urlencoded，否则 JSON。
        headers: 额外请求头。
        timeout: 超时秒数。

    Returns:
        解析后的 dict。

    Raises:
        RuntimeError: 网络错误、HTTP 非 2xx、或 JSON 解析失败。
    """
    if is_form:
        body = urllib.parse.urlencode(data).encode("utf-8")
    else:
        body = json.dumps(data).encode("utf-8")

    content_type = "application/x-www-form-urlencoded" if is_form else "application/json"
    req_headers: dict[str, str] = {"Content-Type": content_type}
    if headers:
        req_headers.update(headers)

    try:
        req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def _api_get(url: str, headers: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """发送 GET 请求，返回解析后的 JSON dict。

    Args:
        url: 完整 URL。
        headers: 请求头（需包含 Authorization）。
        timeout: 超时秒数。

    Returns:
        解析后的 dict。

    Raises:
        RuntimeError: 网络错误、HTTP 非 2xx、或 JSON 解析失败。
    """
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError("登录已过期，请重新登录")
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
    """MF-Mathematics FastAPI 后端客户端。

    所有方法为纯同步调用，无内部状态缓存。
    每个 AuthWorker 线程应创建独立的 APIClient 实例。
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        """初始化客户端。

        Args:
            base_url: API 服务器地址，默认 https://mf-vis-science.cn。
        """
        self.base_url: str = base_url.rstrip("/")

    # ── 登录 ──────────────────────────────────────────────

    def login(self, username: str, password: str) -> dict:
        """登录并获取 access_token。

        Args:
            username: 用户名。
            password: 密码。

        Returns:
            {"access_token": "...", "token_type": "bearer"}

        Raises:
            RuntimeError: 用户名或密码错误、账户未激活等。
        """
        data = {"username": username, "password": password}
        return _api_post(f"{self.base_url}/login", data, is_form=True)

    # ── 发送验证码 ──────────────────────────────────────

    def send_code(self, email: str) -> dict:
        """向指定邮箱发送 6 位验证码（5 分钟有效）。

        Args:
            email: 邮箱地址。

        Returns:
            {"msg": "验证码已发送至 ..."}

        Raises:
            RuntimeError: 邮箱已注册、频率限制等。
        """
        return _api_post(f"{self.base_url}/send-code", {"email": email})

    # ── 注册 ──────────────────────────────────────────────

    def register(self, username: str, email: str, password: str, code: str) -> dict:
        """注册新用户（需先通过 send_code 获取验证码）。

        Args:
            username: 用户名（≥3 字符，字母数字下划线）。
            email: 邮箱。
            password: 密码（≥6 字符）。
            code: 6 位数字验证码。

        Returns:
            {"msg": "注册成功！..."}

        Raises:
            RuntimeError: 参数不合法、验证码错误等。
        """
        data = {
            "username": username,
            "email": email,
            "password": password,
            "code": code,
        }
        return _api_post(f"{self.base_url}/register", data)

    # ── 邮箱验证 ──────────────────────────────────────────

    def verify_code(self, username: str, code: str) -> dict:
        """提交邮箱验证码激活账户。

        Args:
            username: 用户名。
            code: 6 位数字验证码。

        Returns:
            {"msg": "验证成功，账户已激活！"}

        Raises:
            RuntimeError: 验证码错误或已过期。
        """
        data = {"username": username, "code": code}
        return _api_post(f"{self.base_url}/verify-code", data, is_form=True)

    # ── 版本检测 ──────────────────────────────────────────

    def check_version(self) -> dict:
        """检测最新版本（应用启动时调用）。

        Returns:
            标准响应 {"code": 0, "data": {"latest", "date", "download_url", "changelog"}}

        Raises:
            RuntimeError: 网络错误。
        """
        return _api_get(f"{self.base_url}/api/version", {})

    # ── 登出 ──────────────────────────────────────────────

    def logout(self, token: str) -> dict:
        """登出：通知服务端废止当前 token（加入 JWT 黑名单）。

        Args:
            token: Bearer access_token。

        Returns:
            {"msg": "已成功登出"}

        Raises:
            RuntimeError: Token 无效或网络错误。
        """
        headers = {"Authorization": f"Bearer {token}"}
        return _api_post(f"{self.base_url}/logout", {}, headers=headers)

    # ── 用户信息 ──────────────────────────────────────────

    def get_me(self, token: str) -> dict:
        """获取当前登录用户信息。

        Args:
            token: Bearer access_token。

        Returns:
            {"username": ..., "email": ..., "balance": ..., "is_active": ...}

        Raises:
            RuntimeError: Token 无效或已过期（401）。
        """
        headers = {"Authorization": f"Bearer {token}"}
        return _api_get(f"{self.base_url}/me", headers)


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """验证 APIClient 基本结构。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_User.api_client self_test ===")

    try:
        client = APIClient()
        assert client is not None
        assert client.base_url == "https://mf-vis-science.cn"
        passed += 1
        print("  [PASS] APIClient 可实例化，默认 base_url 正确")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        client = APIClient("http://example.com:9000/")
        assert client.base_url == "http://example.com:9000"
        passed += 1
        print("  [PASS] 自定义 base_url，去除末尾 /")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        # 验证所有方法存在且可调用签名正确
        client = APIClient()
        assert callable(client.login)
        assert callable(client.send_code)
        assert callable(client.register)
        assert callable(client.verify_code)
        assert callable(client.get_me)
        assert callable(client.check_version)
        assert callable(client.logout)
        passed += 1
        print("  [PASS] 7 个 API 方法均存在")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    try:
        # 验证 _api_post / _api_get 函数存在
        from MF_User.api_client import _api_post, _api_get
        assert callable(_api_post)
        assert callable(_api_get)
        passed += 1
        print("  [PASS] _api_post / _api_get 工具函数存在")
    except Exception as e:
        failed += 1
        errors.append(str(e))
        print(f"  [FAIL] {e}")

    print(f"  [{passed} passed, {failed} failed]")
    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")
    print("=== MF_User.api_client self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
