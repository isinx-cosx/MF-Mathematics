"""test_algebra.py — algebra 子模块的单元测试。

用法: python -m MF_Mathematics.tests.test_algebra
"""

import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from MF_Mathematics.algebra.number_theory import self_test as test_number_theory
from MF_Mathematics.algebra.expression import self_test as test_expression
from MF_Mathematics.algebra.equation import self_test as test_equation
from MF_Mathematics.algebra.inequality import self_test as test_inequality
from MF_Mathematics.algebra.function import self_test as test_function
from MF_Mathematics.algebra.sequences import self_test as test_sequences
from MF_Mathematics.algebra.combinatorics import self_test as test_combinatorics
from MF_Mathematics.algebra.analytic_geometry import self_test as test_analytic_geometry


def test_all():
    """运行所有测试。"""
    print("=" * 60)
    print("MF_Mathematics Algebra — 单元测试")
    print("=" * 60)

    tests = [
        ("number_theory", test_number_theory),
        ("expression", test_expression),
        ("equation", test_equation),
        ("inequality", test_inequality),
        ("function", test_function),
        ("sequences", test_sequences),
        ("combinatorics", test_combinatorics),
        ("analytic_geometry", test_analytic_geometry),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
            print(f"  {name}: PASSED")
        except Exception as e:
            failed += 1
            print(f"  {name}: FAILED — {e}")

    print(f"\n结果: {passed}/8 通过")
    return failed == 0


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
