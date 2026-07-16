# -*- coding: utf-8 -*-
"""core/precomputed.py — 常用数学表达式的预计算结果表。

启动时加载到 dispatch 缓存中，命中时跳过 sympy 直接返回。
覆盖最常用的积分/导数/极限，减少首次计算等待时间。
"""

from __future__ import annotations

from typing import Any, Callable

# ── 预计算表：{(module, action, args_hash): result} ──
# 使用 dispatch 缓存的 hash key 格式
_PRECOMPUTED: dict[tuple, Any] = {}


def _build_table() -> None:
    """构建预计算表。在应用空闲时调用。"""
    import sympy as sp
    from .math_object import MathObject

    x = sp.Symbol('x')
    y = sp.Symbol('y')
    n = sp.Symbol('n')

    # ── 常用导数 ──
    derivs = [
        (sp.sin(x), sp.cos(x)),
        (sp.cos(x), -sp.sin(x)),
        (sp.tan(x), sp.sec(x)**2),
        (sp.exp(x), sp.exp(x)),
        (sp.log(x), 1/x),
        (x**n, n*x**(n-1)),
        (x**2, 2*x),
        (x**3, 3*x**2),
        (sp.sqrt(x), 1/(2*sp.sqrt(x))),
        (1/x, -1/x**2),
        (sp.asin(x), 1/sp.sqrt(1-x**2)),
        (sp.acos(x), -1/sp.sqrt(1-x**2)),
        (sp.atan(x), 1/(1+x**2)),
    ]
    for func, result in derivs:
        key_base = ("calculus", "diff", str(func), "x")
        mo = MathObject(
            result=str(result),
            steps=[f"d/dx ({func}) = {result}"],
            meaning=f"导数: d/dx({func}) = {result}",
        )
        _PRECOMPUTED[hash(key_base)] = mo

    # ── 常用不定积分 ──
    integrals = [
        (sp.sin(x), -sp.cos(x)),
        (sp.cos(x), sp.sin(x)),
        (sp.exp(x), sp.exp(x)),
        (1/x, sp.log(sp.Abs(x))),
        (x**n, x**(n+1)/(n+1)),
        (x**2, x**3/3),
        (x**3, x**4/4),
        (1/(1+x**2), sp.atan(x)),
        (1/sp.sqrt(1-x**2), sp.asin(x)),
        (-1/sp.sqrt(1-x**2), sp.acos(x)),
        (sp.log(x), x*sp.log(x) - x),
        (sp.tan(x), -sp.log(sp.Abs(sp.cos(x)))),
        (sp.sec(x)**2, sp.tan(x)),
        (sp.exp(x)*sp.sin(x), sp.exp(x)*(sp.sin(x)-sp.cos(x))/2),
        (sp.exp(x)*sp.cos(x), sp.exp(x)*(sp.sin(x)+sp.cos(x))/2),
    ]
    for func, result in integrals:
        key_base = ("calculus", "integrate", str(func), "x")
        mo = MathObject(
            result=str(result) + " + C",
            steps=[f"∫ {func} dx = {result} + C"],
            meaning=f"不定积分: ∫ {func} dx = {result} + C",
        )
        _PRECOMPUTED[hash(key_base)] = mo

    # ── 常用极限 ──
    limits = [
        (sp.sin(x)/x, x, 0, 1),
        ((sp.exp(x)-1)/x, x, 0, 1),
        ((1-sp.cos(x))/x**2, x, 0, sp.Rational(1,2)),
        ((1+1/n)**n, n, sp.oo, sp.E),
        (sp.log(1+x)/x, x, 0, 1),
        (sp.tan(x)/x, x, 0, 1),
        ((sp.sin(x)-x)/x**3, x, 0, -sp.Rational(1,6)),
    ]
    for func, var, pt, result in limits:
        key_base = ("calculus", "limit", str(func), str(var), str(pt))
        mo = MathObject(
            result=str(result),
            steps=[f"lim_{{{var}→{pt}}} {func} = {result}"],
            meaning=f"极限: lim({func}, {var}→{pt}) = {result}",
        )
        _PRECOMPUTED[hash(key_base)] = mo

    # ── 常用化简/因子分解 ──
    simplifications = [
        (x**4 - 1, "(x - 1)*(x + 1)*(x**2 + 1)"),
        (x**2 - 1, "(x - 1)*(x + 1)"),
        (x**2 + 2*x + 1, "(x + 1)**2"),
        (x**3 - y**3, "(x - y)*(x**2 + x*y + y**2)"),
    ]
    for expr, result in simplifications:
        key_base = ("algebra", "factor", str(expr))
        mo = MathObject(
            result=result,
            steps=[f"因式分解: {expr} = {result}"],
            meaning=f"{expr} = {result}",
        )
        _PRECOMPUTED[hash(key_base)] = mo


def get_precomputed(key_hash: int) -> Any:
    """查询预计算表。命中返回 MathObject，未命中返回 None。"""
    return _PRECOMPUTED.get(key_hash)


def precomputed_count() -> int:
    """返回预计算条目数。"""
    return len(_PRECOMPUTED)


def warmup_cache() -> int:
    """预热：构建预计算表并将结果注入 dispatch 缓存。返回条目数。"""
    from . import registry
    _build_table()
    for key_hash, mo in _PRECOMPUTED.items():
        if key_hash not in registry._cache:
            if len(registry._cache) >= registry._CACHE_SIZE:
                registry._cache.popitem(last=False)
            registry._cache[key_hash] = mo
    return len(_PRECOMPUTED)
