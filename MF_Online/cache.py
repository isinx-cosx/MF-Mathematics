# -*- coding: utf-8 -*-
"""搜索结果缓存 — 最近 N 条去重。"""

from __future__ import annotations

from collections import OrderedDict


class SearchCache:
    """LRU 风格缓存（key=query, value=results list）。"""

    def __init__(self, max_size: int = 50):
        self._data: OrderedDict[str, list[dict]] = OrderedDict()
        self._max_size = max_size

    def get(self, query: str) -> list[dict] | None:
        key = query.strip().lower()
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return None

    def put(self, query: str, results: list[dict]) -> None:
        key = query.strip().lower()
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = results
        while len(self._data) > self._max_size:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
