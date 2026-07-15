# -*- coding: utf-8 -*-
"""MF_Online 配置 — 搜索引擎、超时、缓存。"""

from __future__ import annotations

import os

_DEFAULT_ENGINE = "duckduckgo"
_DEFAULT_TIMEOUT = 10
_DEFAULT_CACHE_SIZE = 50


def _load_dotenv() -> dict[str, str]:
    result: dict[str, str] = {}
    for p in [os.path.join(os.getcwd(), ".env"),
              os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")]:
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        result[k.strip()] = v.strip().strip('"').strip("'")
        except FileNotFoundError:
            pass
    return result


_dotenv = _load_dotenv()


def get_engine() -> str:
    return os.environ.get("SEARCH_ENGINE", _dotenv.get("SEARCH_ENGINE", _DEFAULT_ENGINE))


def get_timeout() -> int:
    return int(os.environ.get("SEARCH_TIMEOUT", _dotenv.get("SEARCH_TIMEOUT", str(_DEFAULT_TIMEOUT))))


def get_wolfram_key() -> str:
    return os.environ.get("WOLFRAM_APP_ID", _dotenv.get("WOLFRAM_APP_ID", ""))


def get_custom_endpoint() -> str:
    return os.environ.get("SEARCH_CUSTOM_URL", _dotenv.get("SEARCH_CUSTOM_URL", ""))


def get_cache_size() -> int:
    return _DEFAULT_CACHE_SIZE
