"""test_algebraic_topology.py — 代数拓扑模块测试。"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_all() -> bool:
    """运行所有 algebraic_topology 模块自测并汇总。"""
    print("=" * 60)
    print("代数拓扑模块 (algebraic_topology) 全量测试")
    print("=" * 60)

    all_pass = True

    # homotopy
    print("\n--- homotopy ---")
    from MF_Mathematics.algebraic_topology import homotopy

    homotopy_ok = homotopy.self_test()
    all_pass = all_pass and homotopy_ok

    # homology
    print("\n--- homology ---")
    from MF_Mathematics.algebraic_topology import homology

    homology_ok = homology.self_test()
    all_pass = all_pass and homology_ok

    # cohomology
    print("\n--- cohomology ---")
    from MF_Mathematics.algebraic_topology import cohomology

    cohomology_ok = cohomology.self_test()
    all_pass = all_pass and cohomology_ok

    # degree_fixedpoint
    print("\n--- degree_fixedpoint ---")
    from MF_Mathematics.algebraic_topology import degree_fixedpoint

    degree_fp_ok = degree_fixedpoint.self_test()
    all_pass = all_pass and degree_fp_ok

    # persistent_homology
    print("\n--- persistent_homology ---")
    from MF_Mathematics.algebraic_topology import persistent_homology

    ph_ok = persistent_homology.self_test()
    all_pass = all_pass and ph_ok

    print("\n" + "=" * 60)
    status = "ALL PASSED" if all_pass else "SOME FAILED"
    print(f"代数拓扑测试结果: {status}")
    print(
        f"  homotopy: {'PASSED' if homotopy_ok else 'FAILED'}"
    )
    print(
        f"  homology: {'PASSED' if homology_ok else 'FAILED'}"
    )
    print(
        f"  cohomology: {'PASSED' if cohomology_ok else 'FAILED'}"
    )
    print(
        f"  degree_fixedpoint: {'PASSED' if degree_fp_ok else 'FAILED'}"
    )
    print(
        f"  persistent_homology: {'PASSED' if ph_ok else 'FAILED'}"
    )
    print("=" * 60)

    return all_pass


if __name__ == "__main__":
    ok = test_all()
    sys.exit(0 if ok else 1)
