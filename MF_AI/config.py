# -*- coding: utf-8 -*-
"""AI 配置管理 — 单例模式，支持环境变量 & .env 文件。

优先级: 运行时 set_xxx() > 环境变量 > .env > 默认值
"""

from __future__ import annotations

import os
from typing import ClassVar

from MF_AI.exceptions import AIConfigError

# 默认值
_DEFAULT_BASE_URL = "https://api.deepseek.com"
_DEFAULT_MODEL = "deepseek-chat"
_DEFAULT_MAX_TOKENS = 2048
_DEFAULT_TEMPERATURE = 0.7


def _load_dotenv(path: str | None = None) -> dict[str, str]:
    """手动解析 .env 文件（避免 python-dotenv 依赖）。

    支持: KEY=VALUE, KEY="VALUE", 注释 #, 空行。
    """
    search_paths = []
    if path:
        search_paths.append(path)
    # 默认搜索当前工作目录和项目根目录
    if os.getcwd():
        search_paths.append(os.path.join(os.getcwd(), ".env"))
    # 尝试 MF_AI 上级目录（项目根）
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        search_paths.append(os.path.join(root, ".env"))
    except Exception:
        pass

    result: dict[str, str] = {}
    for p in search_paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key:
                        result[key] = value
        except FileNotFoundError:
            pass
    return result


class Config:
    """AI 配置单例。

    用法:
        cfg = Config()
        cfg.set_api_key("sk-xxx")
        print(cfg.api_key)
    """

    _instance: ClassVar[Config | None] = None

    def __new__(cls) -> Config:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 加载 .env
        dotenv = _load_dotenv()

        # API Key — 必须从环境变量或 .env 获取
        self._api_key = os.environ.get("AI_API_KEY", dotenv.get("AI_API_KEY", ""))
        self._base_url = os.environ.get("AI_BASE_URL", dotenv.get("AI_BASE_URL", _DEFAULT_BASE_URL))
        self._model = os.environ.get("AI_MODEL", dotenv.get("AI_MODEL", _DEFAULT_MODEL))
        self._max_tokens = int(os.environ.get("AI_MAX_TOKENS", dotenv.get("AI_MAX_TOKENS", str(_DEFAULT_MAX_TOKENS))))
        self._temperature = float(os.environ.get("AI_TEMPERATURE", dotenv.get("AI_TEMPERATURE", str(_DEFAULT_TEMPERATURE))))
        self._system_prompt = os.environ.get("AI_SYSTEM_PROMPT", dotenv.get("AI_SYSTEM_PROMPT", ""))

        # 启动时未配置 API Key 仅警告，允许运行时设置
        if not self._api_key:
            import sys
            print("[MF_AI] 警告: AI_API_KEY 未设置。可通过 set_api_key() 运行时配置。",
                  file=sys.stderr)

    # ── 属性 ──────────────────────────────────────────────

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def model(self) -> str:
        return self._model

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def temperature(self) -> float:
        return self._temperature

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    # ── 运行时设置 ────────────────────────────────────────

    def set_api_key(self, key: str) -> None:
        """运行时设置 API Key。"""
        if not key or not key.strip():
            raise AIConfigError("API Key 不能为空")
        self._api_key = key.strip()

    def set_model(self, model: str) -> None:
        """切换模型。"""
        if not model or not model.strip():
            raise AIConfigError("模型名不能为空")
        self._model = model.strip()

    def set_base_url(self, url: str) -> None:
        self._base_url = url.strip()

    def set_temperature(self, t: float) -> None:
        self._temperature = max(0.0, min(2.0, t))

    def set_max_tokens(self, n: int) -> None:
        self._max_tokens = max(1, n)

    def set_system_prompt(self, prompt: str) -> None:
        self._system_prompt = prompt

    def validate(self) -> None:
        """校验必要配置，缺失则抛出 AIConfigError。"""
        if not self._api_key:
            raise AIConfigError(
                "AI_API_KEY 未设置。请设置环境变量或调用 set_api_key()。"
            )
