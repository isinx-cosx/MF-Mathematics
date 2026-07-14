"""test_measure_theory.py — 测度论模块测试。"""

from __future__ import annotations


def test_all() -> bool:
    """运行测度论全部子模块的 self_test。"""
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from MF_Mathematics.measure_theory.set_systems import (
        self_test as test_ss,
    )
    from MF_Mathematics.measure_theory.measure_construction import (
        self_test as test_mc,
    )
    from MF_Mathematics.measure_theory.measurable_functions import (
        self_test as test_mf,
    )
    from MF_Mathematics.measure_theory.lebesgue_integral import (
        self_test as test_li,
    )
    from MF_Mathematics.measure_theory.convergence_theorems import (
        self_test as test_ct,
    )
    from MF_Mathematics.measure_theory.product_measure import (
        self_test as test_pm,
    )
    from MF_Mathematics.measure_theory.probability_measure import (
        self_test as test_prob,
    )

    results = []
    results.append(("set_systems", test_ss()))
    print()
    results.append(("measure_construction", test_mc()))
    print()
    results.append(("measurable_functions", test_mf()))
    print()
    results.append(("lebesgue_integral", test_li()))
    print()
    results.append(("convergence_theorems", test_ct()))
    print()
    results.append(("product_measure", test_pm()))
    print()
    results.append(("probability_measure", test_prob()))

    all_passed = all(ok for _, ok in results)
    print("\n" + "=" * 60)
    for name, ok in results:
        status = "PASSED" if ok else "FAILED"
        print(f"  {name:25s} {status}")
    print(
        f"测度论模块: {'ALL PASSED' if all_passed else 'SOME FAILED'}"
    )
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    ok = test_all()
    exit(0 if ok else 1)
