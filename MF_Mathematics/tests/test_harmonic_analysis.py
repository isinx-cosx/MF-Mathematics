"""test_harmonic_analysis.py — 调和分析模块测试。"""

from __future__ import annotations


def test_all() -> bool:
    """运行调和分析全部子模块的 self_test。"""
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from MF_Mathematics.harmonic_analysis.fourier_series import (
        self_test as test_fs,
    )
    from MF_Mathematics.harmonic_analysis.fourier_transform import (
        self_test as test_ft,
    )
    from MF_Mathematics.harmonic_analysis.convolution import (
        self_test as test_conv,
    )
    from MF_Mathematics.harmonic_analysis.distributions import (
        self_test as test_dist,
    )
    from MF_Mathematics.harmonic_analysis.time_frequency import (
        self_test as test_tf,
    )
    from MF_Mathematics.harmonic_analysis.zeta_harmonic import (
        self_test as test_zh,
    )

    results = []
    results.append(("fourier_series", test_fs()))
    print()
    results.append(("fourier_transform", test_ft()))
    print()
    results.append(("convolution", test_conv()))
    print()
    results.append(("distributions", test_dist()))
    print()
    results.append(("time_frequency", test_tf()))
    print()
    results.append(("zeta_harmonic", test_zh()))

    print("\n" + "=" * 60)
    status = ", ".join(f"{n} {'PASSED' if ok else 'FAILED'}" for n, ok in results)
    print(f"Harmonic Analysis: {status}")
    print("=" * 60)

    return all(ok for _, ok in results)


if __name__ == "__main__":
    ok = test_all()
    print(f"\n最终结果: {'ALL PASSED' if ok else 'SOME FAILED'}")
