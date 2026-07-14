"""test_all.py — 统一测试运行器。

自动发现 MF_Mathematics 的所有子模块，执行每个模块中的 self_test 函数，
收集结果并输出汇总报告。仅依赖 Python 标准库。

用法:
    python -m MF_Mathematics.tests.test_all
    或从项目根目录: python run_tests.py
"""

import importlib
import pkgutil
import sys
import os
import traceback
from typing import Dict, List

# ── 跳过的目录（非数学模块） ──────────────────────────────────
SKIP_PACKAGES = {"core", "tests", "temp", "__pycache__"}


def _ensure_path():
    """确保项目根目录在 sys.path 中。"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


def discover_modules() -> Dict[str, List[str]]:
    """使用 pkgutil 发现 MF_Mathematics 下所有子包及其可测试模块。

    Returns:
        {子包名: [模块名列表]}，模块名为不含 .py 的文件名。
    """
    _ensure_path()
    import MF_Mathematics
    pkg_path = os.path.dirname(MF_Mathematics.__file__)

    modules_by_subpkg: Dict[str, List[str]] = {}

    for finder, subpkg_name, is_pkg in pkgutil.iter_modules([pkg_path]):
        if not is_pkg:
            continue
        if subpkg_name in SKIP_PACKAGES or subpkg_name.startswith("_"):
            continue

        subpkg_path = os.path.join(pkg_path, subpkg_name)
        py_files: List[str] = []

        for _f, mod_name, _is_pkg in pkgutil.iter_modules([subpkg_path]):
            if mod_name.startswith("_") or _is_pkg:
                continue
            py_files.append(mod_name)

        if py_files:
            modules_by_subpkg[subpkg_name] = sorted(py_files)

    return modules_by_subpkg


def run_all_tests() -> bool:
    """运行所有模块的 self_test，输出汇总报告。

    Returns:
        True 表示全部通过，False 表示存在失败或错误。
    """
    _ensure_path()

    modules_by_subpkg = discover_modules()

    print("=" * 60)
    print("MF_Mathematics 模块测试报告")
    print("=" * 60)

    # 已规划的模块（按顺序输出）
    planned_order = [
        "algebra", "calculus", "linear_algebra", "probability",
        "real_analysis", "complex_analysis", "numerical",
        "functional_analysis", "harmonic_analysis", "measure_theory",
        "algebraic_topology", "number_theory",
    ]

    found = set(modules_by_subpkg.keys())
    ordered = [m for m in planned_order if m in found]
    extras = sorted(found - set(planned_order))
    ordered.extend(extras)

    # 全局统计
    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_missing = 0
    all_ok = True

    for subpkg_name in planned_order + extras:
        # 未找到的模块
        if subpkg_name not in modules_by_subpkg:
            if subpkg_name in planned_order:
                print(f"⚠️ 模块 {subpkg_name} 未找到，跳过测试")
            continue

        module_files = modules_by_subpkg[subpkg_name]
        pkg_passed = 0
        pkg_failed = 0
        pkg_errors = 0
        pkg_missing = 0

        for mod_name in module_files:
            full_name = f"MF_Mathematics.{subpkg_name}.{mod_name}"
            label = f"{subpkg_name}.{mod_name}"

            try:
                mod = importlib.import_module(full_name)
            except Exception as e:
                pkg_errors += 1
                print(f"  ✗ {label} IMPORT ERROR: {e}")
                continue

            if not hasattr(mod, "self_test"):
                pkg_missing += 1
                continue

            test_fn = getattr(mod, "self_test")
            try:
                test_fn()
                pkg_passed += 1
            except AssertionError as e:
                pkg_failed += 1
                all_ok = False
                msg = str(e) if str(e) else "(no message)"
                print(f"  ✗ {label} FAILED: {msg}")
            except Exception as e:
                pkg_errors += 1
                all_ok = False
                tb_lines = traceback.format_exc().strip().split("\n")
                last_msg = tb_lines[-1] if tb_lines else str(e)
                print(f"  ✗ {label} ERROR: {last_msg}")

        # 模块级汇总行
        parts = []
        if pkg_passed:
            parts.append(f"{pkg_passed} passed")
        if pkg_failed:
            parts.append(f"{pkg_failed} failed")
        if pkg_errors:
            parts.append(f"{pkg_errors} errors")
        if pkg_missing:
            parts.append(f"{pkg_missing} no self_test")
        print(f"{subpkg_name} ... {', '.join(parts) if parts else 'no tests'}")

        total_passed += pkg_passed
        total_failed += pkg_failed
        total_errors += pkg_errors
        total_missing += pkg_missing

    # 总计
    total = total_passed + total_failed + total_errors
    print()
    summary_parts = [f"总计: {total} 个测试"]
    if total_passed:
        summary_parts.append(f"{total_passed} 通过")
    if total_failed:
        summary_parts.append(f"{total_failed} 失败")
    if total_errors:
        summary_parts.append(f"{total_errors} 错误")
    if total_missing:
        summary_parts.append(f"{total_missing} 缺少自测")
    print(", ".join(summary_parts))
    print("=" * 60)

    return all_ok


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
