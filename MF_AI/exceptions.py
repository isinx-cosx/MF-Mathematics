# -*- coding: utf-8 -*-
"""MF_AI 自定义异常类。"""

from __future__ import annotations


class AIError(Exception):
    """AI 模块基础异常。"""
    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message)
        self.code = code


class AIConfigError(AIError):
    """配置缺失或无效（如未设置 API Key）。"""


class AIAuthError(AIError):
    """认证失败（API Key 无效或过期）。"""


class AIRateLimitError(AIError):
    """请求频率超限（429 / rate limit）。"""


class AITimeoutError(AIError):
    """请求超时。"""


class AIResponseError(AIError):
    """响应解析失败或内容为空。"""
