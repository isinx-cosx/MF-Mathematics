"""MF_Mathematics — 多功能数学工具包。

包含代数(algebra)、几何(geometry)、微积分(calculus)、统计(statistics)等子模块。
"""

__version__ = "0.1.0"


def self_test():
    """自测所有子包，汇总最终结果。"""
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    skip = {"core", "tests", "temp", "__pycache__"}

    grand_total_pass = 0
    grand_total_fail = 0
    grand_total_error = 0

    print("=" * 60)
    print("MF_Mathematics 全局包 self_test")
    print("=" * 60)

    for _, subpkg_name, is_pkg in pkgutil.iter_modules([pkg_path]):
        if not is_pkg or subpkg_name in skip or subpkg_name.startswith('_'):
            continue
        try:
            pkg = importlib.import_module(f'.{subpkg_name}', package=__package__)
        except Exception as e:
            grand_total_error += 1
            print(f"  {subpkg_name}: ERROR importing package - {e}")
            continue
        if not hasattr(pkg, 'self_test'):
            print(f"  {subpkg_name}: no self_test")
            continue
        try:
            p_pass, p_fail, p_error = pkg.self_test()
            grand_total_pass += p_pass
            grand_total_fail += p_fail
            grand_total_error += p_error
        except Exception as e:
            grand_total_error += 1
            print(f"  {subpkg_name}: ERROR running self_test - {e}")

    total = grand_total_pass + grand_total_fail + grand_total_error
    print()
    print(f"总计: {total} 个测试, {grand_total_pass} 通过, {grand_total_fail} 失败, {grand_total_error} 错误")
    print("=" * 60)
    return (grand_total_pass, grand_total_fail, grand_total_error)
