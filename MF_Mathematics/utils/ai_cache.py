# -*- coding: utf-8 -*-
"""AI 响应持久缓存 — 跨会话复用 AI 计算结果。

基于 OrderedDict 的 LRU 缓存，持久化到 ai_cache.json。
避免相同问题重复调用 AI API，节省配额和等待时间。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import OrderedDict
from typing import Any

# ── 配置 ──────────────────────────────────────────────────
_MAX_SIZE = 128
_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "ai_cache.json",
)


class AICache:
    """AI 响应 LRU 缓存（持久化）。"""

    def __init__(self) -> None:
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._load()

    # ── 公开 API ──────────────────────────────────────────

    def get(self, mode: str, expr: str, model: str = "") -> str | None:
        """查询缓存。命中返回响应文本，未命中返回 None。"""
        key = self._make_key(mode, expr, model)
        if key not in self._cache:
            return None
        entry = self._cache.pop(key)
        self._cache[key] = entry  # 移到末尾（LRU）
        return entry["response"]

    def set(self, mode: str, expr: str, response: str, model: str = "") -> None:
        """写入缓存。满时淘汰最旧条目。"""
        key = self._make_key(mode, expr, model)
        if key in self._cache:
            self._cache.pop(key)
        elif len(self._cache) >= _MAX_SIZE:
            self._cache.popitem(last=False)
        self._cache[key] = {
            "mode": mode,
            "expr": expr,
            "model": model,
            "response": response,
            "timestamp": time.time(),
        }
        self._save()

    def clear(self) -> None:
        """清空缓存。"""
        self._cache.clear()
        self._save()

    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> dict[str, Any]:
        return {
            "size": len(self._cache),
            "max_size": _MAX_SIZE,
            "file": _CACHE_FILE,
            "entries": [
                {"mode": v["mode"], "expr": v["expr"][:60], "model": v["model"]}
                for v in list(self._cache.values())[-5:]  # 最近 5 条
            ],
        }

    # ── 内部 ──────────────────────────────────────────────

    @staticmethod
    def _make_key(mode: str, expr: str, model: str) -> str:
        raw = f"{mode}|{expr}|{model}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _save(self) -> None:
        try:
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self._cache.values()), f, ensure_ascii=False, indent=2)
        except OSError:
            pass  # 磁盘写入失败不阻塞

    def _load(self) -> None:
        try:
            if os.path.exists(_CACHE_FILE):
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entry in data:
                    key = self._make_key(
                        entry.get("mode", ""),
                        entry.get("expr", ""),
                        entry.get("model", ""),
                    )
                    self._cache[key] = entry
                # 按时间戳排序
                sorted_items = sorted(
                    self._cache.items(), key=lambda x: x[1].get("timestamp", 0)
                )
                self._cache = OrderedDict(sorted_items)
        except (OSError, json.JSONDecodeError):
            pass


# ── 全局单例 ──────────────────────────────────────────────
_ai_cache: AICache | None = None


def get_ai_cache() -> AICache:
    global _ai_cache
    if _ai_cache is None:
        _ai_cache = AICache()
    return _ai_cache
