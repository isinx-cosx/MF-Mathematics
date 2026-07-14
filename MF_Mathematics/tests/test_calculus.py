"""test_calculus.py — 运行所有 calculus 子模块的 self_test。

用法: python -m MF_Mathematics.tests.test_calculus
"""

import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def test_all():
    """运行所有 calculus 子模块的自测。"""
    print("=" * 60)
    print("MF_Mathematics Calculus — 全量自测")
    print("=" * 60)

    modules = [
        ("limits", "MF_Mathematics.calculus.limits"),
        ("derivatives", "MF_Mathematics.calculus.derivatives"),
        ("derivatives_app", "MF_Mathematics.calculus.derivatives_app"),
        ("integrals", "MF_Mathematics.calculus.integrals"),
        ("integrals_app", "MF_Mathematics.calculus.integrals_app"),
        ("series", "MF_Mathematics.calculus.series"),
    ]

    passed = 0
    failed = 0
    errors = []

    for name, module_path in modules:
        print(f"\n--- {name} ---")
        try:
            module = __import__(module_path, fromlist=["self_test"])
            module.self_test()
            passed += 1
            print(f"  {name}: PASSED")
        except Exception as e:
            failed += 1
            errors.append((name, str(e)))
            print(f"  {name}: FAILED — {e}")

    print("\n" + "=" * 60)
    print(f"结果: {passed} 通过 / {failed} 失败")
    if errors:
        print("\n失败详情:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
