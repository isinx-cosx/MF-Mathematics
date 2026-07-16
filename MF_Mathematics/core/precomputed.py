# -*- coding: utf-8 -*-
"""core/precomputed.py — 常用数学表达式的预计算结果表。

启动时通过 warmup_cache() 加载到 dispatch 缓存中，
命中时跳过 sympy 直接返回 MathObject。
"""

from __future__ import annotations

from .math_object import MathObject


def _get_all_precomputed() -> list[tuple[str, str, tuple, dict, MathObject]]:
    """返回 [(module, action, args, kwargs, MathObject), ...]

    使用 sympy 现场计算，结果通过 dispatch 缓存复用。
    """
    import sympy as sp
    x, y, n = sp.Symbol('x'), sp.Symbol('y'), sp.Symbol('n')

    results = []

    # ── 常用导数 (calculus.diff) ──
    for func_str, var, result_str in [
        ("sin(x)", "x", "cos(x)"),
        ("cos(x)", "x", "-sin(x)"),
        ("tan(x)", "x", "tan(x)**2 + 1"),
        ("exp(x)", "x", "exp(x)"),
        ("log(x)", "x", "1/x"),
        ("x**2", "x", "2*x"),
        ("x**3", "x", "3*x**2"),
        ("sqrt(x)", "x", "1/(2*sqrt(x))"),
        ("1/x", "x", "-1/x**2"),
        ("asin(x)", "x", "1/sqrt(1 - x**2)"),
        ("atan(x)", "x", "1/(x**2 + 1)"),
    ]:
        results.append(("calculus", "diff", (func_str, var), {},
            MathObject(result=result_str, steps=[f"d/dx {func_str} = {result_str}"])))

    # ── 常用不定积分 (calculus.integrate) ──
    for func_str, var, result_str in [
        ("sin(x)", "x", "-cos(x)"),
        ("cos(x)", "x", "sin(x)"),
        ("exp(x)", "x", "exp(x)"),
        ("1/x", "x", "log(Abs(x))"),
        ("x**2", "x", "x**3/3"),
        ("x**3", "x", "x**4/4"),
        ("1/(1 + x**2)", "x", "atan(x)"),
        ("1/sqrt(1 - x**2)", "x", "asin(x)"),
        ("log(x)", "x", "x*log(x) - x"),
    ]:
        results.append(("calculus", "integrate", (func_str, var), {},
            MathObject(result=result_str + " + C", steps=[f"∫ {func_str} dx = {result_str} + C"])))

    # ── 常用化简 (algebra.factor) ──
    for expr_str, result_str in [
        ("x**4 - 1", "(x - 1)*(x + 1)*(x**2 + 1)"),
        ("x**2 - 1", "(x - 1)*(x + 1)"),
        ("x**2 + 2*x + 1", "(x + 1)**2"),
    ]:
        results.append(("algebra", "factor", (expr_str,), {},
            MathObject(result=result_str, steps=[f"{expr_str} = {result_str}"])))

    return results


def warmup_cache() -> int:
    """预热：将预计算结果注入 dispatch 缓存。返回注入条数。"""
    from .registry import _cache, _CACHE_SIZE, _make_cache_key

    count = 0
    for module, action, args, kwargs, mo in _get_all_precomputed():
        ck = _make_cache_key(module, action, args, kwargs)
        if ck not in _cache:
            if len(_cache) >= _CACHE_SIZE:
                _cache.popitem(last=False)
            _cache[ck] = mo
            count += 1

    return count
