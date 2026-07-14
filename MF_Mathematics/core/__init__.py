from .math_object import MathObject
from .registry import register, get_registered_functions

__all__ = ["MathObject", "register", "get_registered_functions"]


def self_test():
    """core 模块为数据结构/注册工具，无需自测。"""
    print("=== core package self_test ===")
    print("  core 模块无需测试")
    return (1, 0, 0)
