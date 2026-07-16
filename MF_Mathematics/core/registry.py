"""函数注册表 — 用于注册、查询和调用 MF_Mathematics 中的所有公开函数。

支持 LRU 缓存避免重复 sympy 计算。
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable, Optional

_registry: dict[str, tuple[Callable, str, str]] = {}
"""注册表：key = 'module.action'，value = (func, module, action)"""

# ── 计算缓存 ──────────────────────────────────────────────────
_CACHE_SIZE = 256
_cache_enabled = True
_cache: OrderedDict[int, Any] = OrderedDict()
_cache_hits = 0
_cache_misses = 0


def set_cache_enabled(enabled: bool) -> None:
    """启用/禁用计算缓存。"""
    global _cache_enabled
    _cache_enabled = enabled
    if not enabled:
        clear_cache()


def clear_cache() -> None:
    """清空计算缓存。"""
    global _cache_hits, _cache_misses
    _cache.clear()
    _cache_hits = 0
    _cache_misses = 0


def cache_info() -> dict:
    """返回缓存统计信息。"""
    return {
        "enabled": _cache_enabled,
        "hits": _cache_hits,
        "misses": _cache_misses,
        "size": len(_cache),
        "maxsize": _CACHE_SIZE,
    }


def _make_cache_key(module: str, action: str, args: tuple, kwargs: dict) -> int:
    """生成缓存键 — 基于所有参数的 hash。"""
    kw_items = tuple(sorted(kwargs.items())) if kwargs else ()
    return hash((module, action, args, kw_items))


def register(module: str, action: str) -> Callable:
    """装饰器：将函数注册到全局注册表。

    Args:
        module: 所属模块名，如 "algebra"。
        action: 函数动作名，如 "simplify_polynomial"。

    Returns:
        装饰后的函数。
    """

    def decorator(func: Callable) -> Callable:
        key = f"{module}.{action}"
        _registry[key] = (func, module, action)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            from .math_object import MathObject

            if isinstance(result, MathObject):
                result.module = module
                result.action = action
            return result

        wrapper._registered_key = key  # type: ignore[attr-defined]
        return wrapper

    return decorator


def get_registered_functions(
    module: Optional[str] = None,
) -> dict[str, Callable]:
    """获取已注册的函数。

    Args:
        module: 模块名过滤，不传则返回全部。

    Returns:
        函数名到函数的映射字典。
    """
    result: dict[str, Callable] = {}
    for key, (func, mod, act) in _registry.items():
        if module is None or mod == module:
            result[key] = func
    return result


def list_registered() -> list[dict]:
    """列出所有已注册函数信息。"""
    return [
        {"key": key, "module": mod, "action": act}
        for key, (_, mod, act) in _registry.items()
    ]


def dispatch(module: str, action: str, *args: Any, **kwargs: Any) -> Any:
    """分发调用已注册的函数（带 LRU 缓存）。

    Args:
        module: 模块名。
        action: 动作名。
        *args, **kwargs: 传递给目标函数的参数。

    Returns:
        目标函数的返回值。

    Raises:
        KeyError: 未找到对应的注册函数。
    """
    global _cache_hits, _cache_misses

    key = f"{module}.{action}"
    if key not in _registry:
        raise KeyError(f"未找到注册函数: {key}")

    func, _, _ = _registry[key]

    # 缓存查找
    if _cache_enabled:
        ck = _make_cache_key(module, action, args, kwargs)
        if ck in _cache:
            _cache_hits += 1
            _cache.move_to_end(ck)
            return _cache[ck]

        _cache_misses += 1
        result = func(*args, **kwargs)

        # LRU 淘汰
        if len(_cache) >= _CACHE_SIZE:
            _cache.popitem(last=False)

        _cache[ck] = result
        return result

    return func(*args, **kwargs)


def self_test() -> tuple[int, int, int]:
    """自测试：验证注册和分发功能。"""
    try:
        @register(module="test", action="test")
        def test_func(x: int = 42) -> int:
            return x

        result = dispatch("test", "test")
        assert result == 42, f"dispatch 返回值不匹配: {result}"

        # 测试缓存
        result2 = dispatch("test", "test")
        assert result2 == 42
        info = cache_info()
        assert info["hits"] >= 1, f"缓存命中应为 >=1，实际: {info}"

        print("registry self_test: PASSED")
        return (1, 0, 0)
    except Exception as e:
        print(f"registry self_test: FAILED - {e}")
        return (0, 1, 0)
