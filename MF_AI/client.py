# -*- coding: utf-8 -*-
"""AI 客户端 — 封装 OpenAI 兼容 API 调用。

优先使用 openai 库，回退至 httpx 手动 HTTP。
"""

from __future__ import annotations

import json
import time
from typing import Generator

from MF_AI.config import Config
from MF_AI.exceptions import (
    AIError, AIAuthError, AIRateLimitError, AITimeoutError, AIResponseError,
)
from MF_AI.models import ChatMessage, ChatRequest, ChatResponse

# ── 后端检测 ──────────────────────────────────────────────
_OPENAI_AVAILABLE = False
_httpx = None

try:
    import openai as _openai_mod
    _OPENAI_AVAILABLE = True
except ImportError:
    pass

if not _OPENAI_AVAILABLE:
    try:
        import httpx as _httpx
    except ImportError:
        pass  # 运行时再处理


class AIClient:
    """OpenAI 兼容 API 客户端。

    用法:
        from MF_AI.config import Config
        from MF_AI.client import AIClient

        cfg = Config()
        cfg.set_api_key("sk-xxx")
        client = AIClient(cfg)
        reply = client.chat([{"role": "user", "content": "什么是导数？"}])
    """

    def __init__(self, config: Config | None = None):
        self._config = config or Config()
        self._openai_client = None

        if _OPENAI_AVAILABLE:
            self._init_openai()
        elif _httpx is not None:
            self._backend = "httpx"
        else:
            raise AIError(
                "无可用的 HTTP 后端。请安装 openai 或 httpx:\n"
                "  pip install openai\n  pip install httpx"
            )

    def _init_openai(self) -> None:
        """初始化 OpenAI 客户端。"""
        try:
            import openai
            self._openai_client = openai.OpenAI(
                api_key=self._config.api_key,
                base_url=self._config.base_url,
                timeout=60.0,
            )
            self._backend = "openai"
        except Exception as e:
            raise AIError(f"OpenAI 客户端初始化失败: {e}")

    def _ensure_ready(self) -> None:
        """确保已配置 API Key。"""
        self._config.validate()

    # ═══════════════════════════════════════════════════════════
    #  chat — 同步对话
    # ═══════════════════════════════════════════════════════════

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """发送对话，返回回复文本。

        Args:
            messages: [{"role":"user","content":"..."}, ...]
            model: 模型名（默认从 Config 读取）
            temperature: 温度（默认从 Config 读取）
            max_tokens: 最大 token（默认从 Config 读取）

        Returns:
            助手回复文本。

        Raises:
            AIAuthError: 认证失败
            AIRateLimitError: 频率超限
            AITimeoutError: 请求超时
            AIResponseError: 响应为空或解析失败
            AIError: 其他错误
        """
        self._ensure_ready()

        model = model or self._config.model
        temperature = temperature if temperature is not None else self._config.temperature
        max_tokens = max_tokens or self._config.max_tokens

        # 注入系统提示词
        full_messages = list(messages)
        if self._config.system_prompt and not any(
            m.get("role") == "system" for m in full_messages
        ):
            full_messages.insert(0, {"role": "system", "content": self._config.system_prompt})

        if self._backend == "openai":
            return self._chat_openai(full_messages, model, temperature, max_tokens, **kwargs)
        else:
            return self._chat_httpx(full_messages, model, temperature, max_tokens, **kwargs)

    def _chat_openai(self, messages, model, temperature, max_tokens, **kwargs) -> str:
        try:
            response = self._openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            choice = response.choices[0]
            return choice.message.content or ""
        except _openai_mod.AuthenticationError as e:
            raise AIAuthError(str(e), code="auth_error") from e
        except _openai_mod.RateLimitError as e:
            raise AIRateLimitError(str(e), code="rate_limit") from e
        except _openai_mod.APITimeoutError as e:
            raise AITimeoutError(str(e), code="timeout") from e
        except _openai_mod.APIError as e:
            raise AIError(str(e), code="api_error") from e
        except Exception as e:
            raise AIError(f"OpenAI 调用失败: {e}") from e

    def _chat_httpx(self, messages, model, temperature, max_tokens, **kwargs) -> str:
        url = f"{self._config.base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            **kwargs,
        }

        try:
            response = _httpx.post(url, headers=headers, json=payload, timeout=60.0)
        except _httpx.TimeoutException as e:
            raise AITimeoutError(f"请求超时: {e}", code="timeout") from e
        except _httpx.NetworkError as e:
            raise AIError(f"网络错误: {e}", code="network_error") from e

        return self._parse_httpx_response(response)

    def _parse_httpx_response(self, response) -> str:
        if response.status_code == 401:
            raise AIAuthError("API Key 无效或已过期", code="auth_error")
        if response.status_code == 429:
            raise AIRateLimitError("请求频率超限，请稍后再试", code="rate_limit")
        if response.status_code >= 500:
            raise AIError(f"服务器错误 ({response.status_code})", code="server_error")
        if response.status_code != 200:
            detail = ""
            try:
                detail = response.json().get("error", {}).get("message", "")
            except Exception:
                detail = response.text[:200]
            raise AIError(f"API 错误 ({response.status_code}): {detail}", code="api_error")

        try:
            data = response.json()
            choice = data.get("choices", [{}])[0]
            return choice.get("message", {}).get("content", "") or ""
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise AIResponseError(f"响应解析失败: {e}") from e

    # ═══════════════════════════════════════════════════════════
    #  stream_chat — 流式对话
    # ═══════════════════════════════════════════════════════════

    def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> Generator[str, None, None]:
        """流式对话 — 逐段 yield 回复文本。

        Yields:
            增量文本片段。
        """
        self._ensure_ready()

        model = model or self._config.model
        temperature = temperature if temperature is not None else self._config.temperature
        max_tokens = max_tokens or self._config.max_tokens

        full_messages = list(messages)
        if self._config.system_prompt and not any(
            m.get("role") == "system" for m in full_messages
        ):
            full_messages.insert(0, {"role": "system", "content": self._config.system_prompt})

        if self._backend == "openai":
            yield from self._stream_openai(full_messages, model, temperature, max_tokens, **kwargs)
        else:
            yield from self._stream_httpx(full_messages, model, temperature, max_tokens, **kwargs)

    def _stream_openai(self, messages, model, temperature, max_tokens, **kwargs):
        try:
            stream = self._openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except _openai_mod.AuthenticationError as e:
            raise AIAuthError(str(e), code="auth_error") from e
        except _openai_mod.RateLimitError as e:
            raise AIRateLimitError(str(e), code="rate_limit") from e
        except _openai_mod.APITimeoutError as e:
            raise AITimeoutError(str(e), code="timeout") from e
        except _openai_mod.APIError as e:
            raise AIError(str(e), code="api_error") from e
        except Exception as e:
            raise AIError(f"流式调用失败: {e}") from e

    def _stream_httpx(self, messages, model, temperature, max_tokens, **kwargs):
        url = f"{self._config.base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs,
        }

        try:
            with _httpx.stream("POST", url, headers=headers, json=payload, timeout=120.0) as resp:
                if resp.status_code == 401:
                    raise AIAuthError("API Key 无效或已过期", code="auth_error")
                if resp.status_code == 429:
                    raise AIRateLimitError("请求频率超限", code="rate_limit")
                if resp.status_code != 200:
                    raise AIError(f"API 错误 ({resp.status_code})", code="api_error")

                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # 去掉 "data: "
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

        except _httpx.TimeoutException as e:
            raise AITimeoutError(f"流式请求超时: {e}", code="timeout") from e
        except _httpx.NetworkError as e:
            raise AIError(f"网络错误: {e}", code="network_error") from e
