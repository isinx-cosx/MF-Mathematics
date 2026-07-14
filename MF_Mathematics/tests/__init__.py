"""Test runner — 运行所有 algebra 子模块的 self_test。"""

import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def run_all_tests():
    """运行所有 algebra 子模块的自测。"""
    print("=" * 60)
    print("MF_Mathematics Algebra — 全量自测")
    print("=" * 60)

    modules = [
        ("number_theory", "MF_Mathematics.algebra.number_theory"),
        ("expression", "MF_Mathematics.algebra.expression"),
        ("equation", "MF_Mathematics.algebra.equation"),
        ("inequality", "MF_Mathematics.algebra.inequality"),
        ("function", "MF_Mathematics.algebra.function"),
        ("sequences", "MF_Mathematics.algebra.sequences"),
        ("combinatorics", "MF_Mathematics.algebra.combinatorics"),
        ("analytic_geometry", "MF_Mathematics.algebra.analytic_geometry"),
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
    success = run_all_tests()
    sys.exit(0 if success else 1)
