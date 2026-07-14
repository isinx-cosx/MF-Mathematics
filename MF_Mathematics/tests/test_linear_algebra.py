"""test_linear_algebra.py — 运行所有 linear_algebra 子模块的 self_test。

用法: python -m MF_Mathematics.tests.test_linear_algebra
"""

import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def test_all():
    """运行所有 linear_algebra 子模块的自测。"""
    print("=" * 60)
    print("MF_Mathematics Linear Algebra — 全量自测")
    print("=" * 60)

    modules = [
        ("linear_systems", "MF_Mathematics.linear_algebra.linear_systems"),
        ("vector_spaces", "MF_Mathematics.linear_algebra.vector_spaces"),
        ("linear_transforms", "MF_Mathematics.linear_algebra.linear_transforms"),
        ("inner_product", "MF_Mathematics.linear_algebra.inner_product"),
        ("eigen", "MF_Mathematics.linear_algebra.eigen"),
        ("quadratic_forms", "MF_Mathematics.linear_algebra.quadratic_forms"),
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

    all_passed = failed == 0
    print(f"\nLinear Algebra: {'PASSED' if all_passed else 'FAILED'}")
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    test_all()
