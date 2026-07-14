"""函数注册表 — 用于注册、查询和调用 MF_Mathematics 中的所有公开函数。"""

from __future__ import annotations

from typing import Any, Callable, Optional

_registry: dict[str, tuple[Callable, str, str]] = {}
"""注册表：key = 'module.action'，value = (func, module, action)"""


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
            # 如果返回 MathObject，注入 module/action 信息
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
    """分发调用已注册的函数。

    Args:
        module: 模块名。
        action: 动作名。
        *args, **kwargs: 传递给目标函数的参数。

    Returns:
        目标函数的返回值。

    Raises:
        KeyError: 未找到对应的注册函数。
    """
    key = f"{module}.{action}"
    if key not in _registry:
        raise KeyError(f"未找到注册函数: {key}")
    func, _, _ = _registry[key]
    return func(*args, **kwargs)


def self_test() -> tuple[int, int, int]:
    """自测试：验证注册和分发功能。"""
    try:
        @register(module="test", action="test")
        def test_func(x: int = 42) -> int:
            return x

        result = dispatch("test", "test")
        assert result == 42, f"dispatch 返回值不匹配: {result}"

        print("registry self_test: PASSED")
        return (1, 0, 0)
    except Exception as e:
        print(f"registry self_test: FAILED - {e}")
        return (0, 1, 0)
