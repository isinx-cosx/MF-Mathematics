# -*- coding: utf-8 -*-
"""MF_AI — AI 服务模块（DeepSeek / OpenAI 兼容接口）。

高层 API:
    from MF_AI import chat, stream_chat, set_api_key, set_model

    set_api_key("sk-xxx")
    reply = chat([{"role": "user", "content": "什么是导数？"}])

    for chunk in stream_chat(messages):
        print(chunk, end="")
"""

from __future__ import annotations

from MF_AI.config import Config
from MF_AI.client import AIClient
from MF_AI.exceptions import (
    AIError, AIConfigError, AIAuthError,
    AIRateLimitError, AITimeoutError, AIResponseError,
)
from MF_AI.models import ChatMessage, ChatRequest, ChatResponse

# ── 全局单例 ──────────────────────────────────────────────

_config: Config | None = None
_client: AIClient | None = None


def _get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def get_ai_client() -> AIClient:
    """获取全局 AI 客户端（懒加载单例）。"""
    global _client
    if _client is None:
        _client = AIClient(_get_config())
    return _client


# ── 配置快捷函数 ──────────────────────────────────────────

def set_api_key(key: str) -> None:
    """运行时设置 API Key。"""
    _get_config().set_api_key(key)


def set_model(model: str) -> None:
    """切换模型。"""
    _get_config().set_model(model)


def set_base_url(url: str) -> None:
    """设置 API 端点。"""
    _get_config().set_base_url(url)


def set_system_prompt(prompt: str) -> None:
    """设置系统提示词。"""
    _get_config().set_system_prompt(prompt)


def set_temperature(t: float) -> None:
    """设置温度参数 (0.0-2.0)。"""
    _get_config().set_temperature(t)


def get_config() -> Config:
    """获取当前配置（只读）。"""
    return _get_config()


# ── 对话快捷函数 ──────────────────────────────────────────

def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs,
) -> str:
    """发送对话，返回完整回复文本。

    Args:
        messages: [{"role":"user","content":"..."}, ...]
        model: 模型名（可选，默认 Config.model）
        temperature: 温度（可选）
        max_tokens: 最大 token（可选）

    Returns:
        助手回复文本。

    Raises:
        AIConfigError: 未配置 API Key
        AIAuthError: 认证失败
        AIRateLimitError: 频率超限
        AITimeoutError: 请求超时
    """
    return get_ai_client().chat(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )


def stream_chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    **kwargs,
) -> str:
    """流式对话 — 返回 Generator。

    Yields:
        增量文本片段。

    用法:
        for chunk in stream_chat(messages):
            print(chunk, end="", flush=True)
    """
    return get_ai_client().stream_chat(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )


# ── 导出 ──────────────────────────────────────────────────

__all__ = [
    # 高层 API
    "get_ai_client", "get_config",
    "set_api_key", "set_model", "set_base_url",
    "set_system_prompt", "set_temperature",
    "chat", "stream_chat",
    # 类
    "AIClient", "Config",
    # 数据模型
    "ChatMessage", "ChatRequest", "ChatResponse",
    # 异常
    "AIError", "AIConfigError", "AIAuthError",
    "AIRateLimitError", "AITimeoutError", "AIResponseError",
]
