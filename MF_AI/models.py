# -*- coding: utf-8 -*-
"""AI 数据模型 — 请求/响应的结构化容器。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    """单条对话消息。"""
    role: str          # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> ChatMessage:
        return cls(role=d.get("role", "user"), content=d.get("content", ""))

    @classmethod
    def system(cls, content: str) -> ChatMessage:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> ChatMessage:
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> ChatMessage:
        return cls(role="assistant", content=content)


@dataclass
class ChatRequest:
    """对话请求。"""
    messages: list[ChatMessage]
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    extra: dict = field(default_factory=dict)  # 透传参数

    def to_payload(self) -> dict:
        return {
            "model": self.model,
            "messages": [m.to_dict() for m in self.messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": self.stream,
            **self.extra,
        }


@dataclass
class ChatResponse:
    """对话回复。"""
    content: str
    model: str = ""
    tokens_used: int = 0          # total_tokens
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.content)
