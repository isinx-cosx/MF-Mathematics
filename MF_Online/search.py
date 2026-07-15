# -*- coding: utf-8 -*-
"""MF_Online 搜索后端 — DuckDuckGo / Wolfram Alpha / 自定义。"""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
import urllib.parse

from MF_Online.config import (
    get_engine, get_timeout, get_wolfram_key, get_custom_endpoint, get_cache_size,
)
from MF_Online.cache import SearchCache

_cache = SearchCache(max_size=get_cache_size())


def search(query: str, engine: str = "") -> list[dict]:
    """搜索并返回统一格式的结果列表。

    Args:
        query: 搜索关键词。
        engine: duckduckgo | wolfram | custom（默认从配置读取）。

    Returns:
        [{"title": str, "snippet": str, "url": str, "latex": str}, ...]
    """
    engine = engine or get_engine()

    # 1. 检查缓存
    cached = _cache.get(query)
    if cached is not None:
        return cached

    # 2. 调用搜索
    if engine == "wolfram":
        results = _search_wolfram(query)
    elif engine == "custom":
        results = _search_custom(query)
    else:
        results = _search_duckduckgo(query)

    # 3. 缓存 + 返回
    _cache.put(query, results)
    return results


def _search_duckduckgo(query: str) -> list[dict]:
    """DuckDuckGo Instant Answer API。"""
    url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MF-Mathematics/1.0"})
        with urllib.request.urlopen(req, timeout=get_timeout()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower() or "timeout" in str(e).lower():
            raise TimeoutError(f"搜索超时（{get_timeout()} 秒）")
        raise ConnectionError(f"网络不可用，请检查连接。 ({e})")
    except Exception as e:
        raise ConnectionError(f"搜索请求失败: {e}")

    results: list[dict] = []

    # 1. Abstract（主题定义/摘要）
    abstract = data.get("Abstract", "")
    abstract_url = data.get("AbstractURL", "")
    abstract_source = data.get("AbstractSource", "")
    if abstract:
        results.append({
            "title": abstract_source or "定义",
            "snippet": abstract,
            "url": abstract_url,
            "latex": _extract_latex(abstract),
        })

    # 2. Related Topics
    for topic in data.get("RelatedTopics", []):
        if isinstance(topic, dict):
            text = topic.get("Text", "")
            url_t = topic.get("FirstURL", "")
            if text:
                results.append({
                    "title": text.split(" - ")[0] if " - " in text else "相关内容",
                    "snippet": text,
                    "url": url_t,
                    "latex": _extract_latex(text),
                })

    # 3. 无结果 → 返回空
    return results[:8]  # 最多 8 条


def _search_wolfram(query: str) -> list[dict]:
    """Wolfram Alpha Short Answers API。"""
    app_id = get_wolfram_key()
    if not app_id:
        raise ValueError("Wolfram Alpha App ID 未配置。请在设置中配置。")

    url = (
        f"https://api.wolframalpha.com/v2/query"
        f"?input={urllib.parse.quote(query)}"
        f"&appid={urllib.parse.quote(app_id)}"
        f"&format=plaintext&output=json"
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=get_timeout()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ConnectionError(f"Wolfram Alpha 请求失败: {e}")

    results = []
    pods = data.get("queryresult", {}).get("pods", [])
    for pod in pods:
        title = pod.get("title", "结果")
        for sub in pod.get("subpods", []):
            plain = sub.get("plaintext", "")
            if plain:
                results.append({
                    "title": title,
                    "snippet": plain,
                    "url": f"https://www.wolframalpha.com/input?i={urllib.parse.quote(query)}",
                    "latex": _extract_latex(plain),
                })
    return results[:8]


def _search_custom(query: str) -> list[dict]:
    """自定义搜索端点（SearXNG 等）。"""
    endpoint = get_custom_endpoint()
    if not endpoint:
        raise ValueError("自定义搜索端点未配置。")

    url = f"{endpoint.rstrip('/')}/search?q={urllib.parse.quote(query)}&format=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MF-Mathematics/1.0"})
        with urllib.request.urlopen(req, timeout=get_timeout()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ConnectionError(f"自定义搜索失败: {e}")

    results = []
    for item in data.get("results", [])[:8]:
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("content", item.get("snippet", "")),
            "url": item.get("url", ""),
            "latex": _extract_latex(item.get("content", "")),
        })
    return results


def _extract_latex(text: str) -> str:
    """从文本中提取 LaTeX 表达式。"""
    if not text:
        return ""
    # $...$ 行内公式
    m = re.findall(r'\$(.+?)\$', text)
    if m:
        return " ".join(m)
    # \[...\] 独立公式
    m = re.findall(r'\\\[(.+?)\\\]', text)
    if m:
        return " ".join(m)
    return ""


def clear_cache() -> None:
    _cache.clear()
