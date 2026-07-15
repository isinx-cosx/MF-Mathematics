# -*- coding: utf-8 -*-
"""core/test_utils.py — 共享的 self_test 发现与运行逻辑。

消除 12 个 __init__.py 中重复的 pkgutil.iter_modules 遍历代码。
"""

from __future__ import annotations

import importlib
import os
import pkgutil


def run_subpackage_tests(
    pkg_name: str, pkg_path: str, package: str
) -> tuple[int, int, int]:
    """遍历子包中所有模块，运行其 self_test() 并汇总结果。

    Args:
        pkg_name: 包显示名称（如 "algebra"）。
        pkg_path: 包的目录路径（通常为 __file__ 的 dirname）。
        package: 包的全限定名（通常为 __package__）。

    Returns:
        (passed, failed, errors) 元组。
    """
    total_pass = 0
    total_fail = 0
    total_error = 0

    print(f"=== {pkg_name} package self_test ===")

    for _, mod_name, _ in pkgutil.iter_modules([pkg_path]):
        if mod_name.startswith('_') or mod_name == 'tests':
            continue
        try:
            mod = importlib.import_module(f'.{mod_name}', package=package)
        except Exception as e:
            total_error += 1
            print(f"  {mod_name}: ERROR importing - {e}")
            continue
        if not hasattr(mod, 'self_test'):
            continue
        try:
            mod.self_test()
            total_pass += 1
            print(f"  {mod_name}: pass")
        except AssertionError as e:
            total_fail += 1
            print(f"  {mod_name}: FAIL - {e}")
        except Exception as e:
            total_error += 1
            print(f"  {mod_name}: ERROR - {e}")

    print(f"  Summary: {total_pass} passed, {total_fail} failed, {total_error} errors")
    return (total_pass, total_fail, total_error)
