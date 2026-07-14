"""复分析 (Complex Analysis) 模块测试。"""

import sys
sys.path.insert(0, r'C:\Users\fsafsafsa\Desktop\Multifunctional-Mathematics')


def test_complex_topology() -> bool:
    """测试复平面拓扑模块。"""
    from MF_Mathematics.complex_analysis.complex_topology import (
        is_open, is_connected, is_domain,
    )

    r1 = is_open("unit_disk", 0 + 0j)
    assert r1.ok and r1.result is True, f"0 should be open in unit disk: {r1.error}"

    r2 = is_open("unit_disk", 1 + 0j)
    assert r2.ok and r2.result is False, f"boundary point should not be open: {r2.error}"

    r3 = is_connected("unit_disk")
    assert r3.ok and r3.result is True, f"unit disk should be connected: {r3.error}"

    r4 = is_connected("separated_disks")
    assert r4.ok and r4.result is False, f"separated disks should not be connected: {r4.error}"

    r5 = is_domain("unit_disk")
    assert r5.ok and r5.result is True, f"unit disk should be a domain: {r5.error}"

    print("  [PASS] complex_topology: 5/5")
    return True


def test_elementary_funcs() -> bool:
    """测试初等复函数模块。"""
    from MF_Mathematics.complex_analysis.elementary_funcs import (
        exp_complex, log_complex, sqrt_complex, mobius_transform,
    )
    import cmath

    r1 = exp_complex(1j * cmath.pi)
    assert r1.ok, r1.error
    val = r1.result
    assert abs(val + 1) < 1e-6, f"e^(iπ) should be -1, got {val}"

    r2 = log_complex(-1)
    assert r2.ok, r2.error
    val = r2.result
    assert abs(val - 1j * cmath.pi) < 1e-6, f"log(-1) should be iπ"

    r3 = sqrt_complex(-1)
    assert r3.ok, r3.error
    val = r3.result
    assert abs(abs(val) - 1) < 1e-6, f"|sqrt(-1)| should be 1"
    assert abs(val.imag - 1) < 1e-6, f"sqrt(-1) should be i"

    r4 = mobius_transform(1 + 1j, 1, 2, 3, 4)
    assert r4.ok, r4.error

    r5 = mobius_transform(1, 0, 1, 1, 0)
    assert r5.ok, r5.error

    print("  [PASS] elementary_funcs: 5/5")
    return True


def test_holomorphic() -> bool:
    """测试全纯函数模块。"""
    from MF_Mathematics.complex_analysis.holomorphic import (
        is_holomorphic, cauchy_riemann, is_harmonic,
    )

    r1 = is_holomorphic("sin(z)", 0 + 0j)
    assert r1.ok and r1.result is True, f"sin(z) should be holomorphic at 0: {r1.error}"

    r2 = is_holomorphic("conjugate(z)", 0 + 0j)
    assert r2.ok and r2.result is False, f"conj(z) should not be holomorphic: {r2.error}"

    r3 = cauchy_riemann("x", "y")
    assert r3.ok, r3.error
    assert r3.result["both_hold"] is True, f"C-R should hold for u=x, v=y (identity): {r3.result}"

    r4 = is_harmonic("x**2 - y**2")
    assert r4.ok and r4.result is True, f"x^2-y^2 should be harmonic: {r4.error}"

    r5 = is_harmonic("x**2 + y**2")
    assert r5.ok and r5.result is False, f"x^2+y^2 should not be harmonic: {r5.error}"

    print("  [PASS] holomorphic: 5/5")
    return True


def test_complex_integral() -> bool:
    """测试复积分模块。"""
    from MF_Mathematics.complex_analysis.complex_integral import (
        contour_integral, cauchy_theorem, cauchy_integral_formula,
        derivative_formula,
    )

    r1 = cauchy_theorem("1", "circle(0, 1)")
    assert r1.ok and r1.result["zero"] is True, f"cauchy_theorem(1), expected zero=True: {r1.error}"

    r2 = cauchy_integral_formula("sin(z)", 0, "circle(0, 1)")
    assert r2.ok, r2.error
    val = r2.result["cauchy_formula"]
    assert abs(val) < 1e-12, f"sin(0) should be 0: {val}"

    r3 = derivative_formula("z**3", 0, 2, "circle(0, 1)")
    assert r3.ok, r3.error

    r4 = contour_integral("1/z", "circle(0, 1)", (0, 2 * 3.141592653589793))
    assert r4.ok, r4.error
    assert abs(abs(r4.result) - 6.2831853) < 0.01, f"∮1/z should be 2πi"

    print("  [PASS] complex_integral: 4/4")
    return True


def test_series() -> bool:
    """测试级数表示模块。"""
    from MF_Mathematics.complex_analysis.series import (
        taylor_series, laurent_series, singularity_classify, pole_order,
    )

    r1 = taylor_series("sin(z)", 0, 5)
    assert r1.ok, r1.error

    r2 = laurent_series("1/(z-1)", 1, 5)
    assert r2.ok, r2.error

    r3 = singularity_classify("1/(z-1)", 1)
    assert r3.ok and r3.result == "pole", f"1/(z-1) at 1 should be pole: {r3.result}"

    r4 = singularity_classify("sin(z)/z", 0)
    assert r4.ok and r4.result == "removable", f"sin(z)/z at 0 should be removable: {r4.result}"

    r5 = singularity_classify("exp(1/z)", 0)
    assert r5.ok and r5.result == "essential", f"exp(1/z) at 0 should be essential: {r5.result}"

    r6 = pole_order("1/(z-1)**3", 1)
    assert r6.ok and r6.result == 3, f"pole order should be 3: {r6.result}"

    print("  [PASS] series: 6/6")
    return True


def test_residue() -> bool:
    """测试留数定理模块。"""
    from MF_Mathematics.complex_analysis.residue import (
        residue, residue_theorem, real_integral,
        argument_principle, rouche_theorem,
    )

    r1 = residue("1/(z**2+1)", 1j)
    assert r1.ok, r1.error
    # 解析留数: 1/(2*1j) = -0.5j
    numeric_val = r1.result.get("numeric", r1.result)
    assert abs(numeric_val.imag + 0.5) < 1e-6 and abs(numeric_val.real) < 1e-6, f"residue: {numeric_val}"

    r2 = residue_theorem("1/(z**2+1)", "circle(0, 2)", [1j, -1j])
    assert r2.ok, r2.error

    r3 = real_integral("1/(1+x**2)", -float('inf'), float('inf'))
    assert r3.ok, r3.error
    val = r3.result["integral"]
    assert abs(val - 3.14159265) < 0.1, f"∫1/(1+x²)dx should be π: {val}"

    r4 = argument_principle("z**2", "circle(0, 1)")
    assert r4.ok, r4.error
    zp = r4.result["zeros_minus_poles"]
    assert abs(zp - 2) < 0.01, f"z² should have 2 zeros: {zp}"

    r5 = rouche_theorem("z**5", "z", "circle(0, 1.5)")
    assert r5.ok, r5.error
    assert r5.result["condition_holds"] is True, f"Rouche condition should hold: {r5.error}"

    print("  [PASS] residue: 5/5")
    return True


def test_conformal() -> bool:
    """测试共形映射模块。"""
    from MF_Mathematics.complex_analysis.conformal import (
        is_conformal, riemann_mapping, boundary_correspondence,
    )

    r1 = is_conformal("z**2", 1 + 0j)
    assert r1.ok and r1.result is True, f"z² should be conformal at 1: {r1.error}"

    r2 = is_conformal("z**2", 0 + 0j)
    assert r2.ok and r2.result is False, f"z² should not be conformal at 0: {r2.error}"

    r3 = is_conformal("exp(z)", 0 + 0j)
    assert r3.ok and r3.result is True, f"e^z should be conformal at 0: {r3.error}"

    r4 = riemann_mapping("upper_half_plane")
    assert r4.ok, r4.error
    assert "Cayley" in r4.result.get("map", ""), f"upper half plane mapping: {r4.result}"

    r5 = riemann_mapping("unit_disk")
    assert r5.ok, r5.error

    r6 = boundary_correspondence("Cayley", "unit")
    assert r6.ok, r6.error

    print("  [PASS] conformal: 6/6")
    return True


def test_zeta() -> bool:
    """测试黎曼 ζ 函数模块。"""
    import numpy as np
    from MF_Mathematics.complex_analysis.zeta import (
        zeta_series, analytic_continuation_zeta, functional_equation_zeta,
        nontrivial_zeros,
    )

    r1 = zeta_series(2, n_terms=10000)
    assert r1.ok, r1.error
    v = r1.result.real if isinstance(r1.result, complex) else r1.result
    assert abs(v - np.pi**2/6) < 0.01, f"ζ(2) should be π²/6: {v}"

    r2 = analytic_continuation_zeta(-1)
    assert r2.ok, r2.error
    v = r2.result.real if isinstance(r2.result, complex) else r2.result
    assert abs(v + 1/12) < 1e-6, f"ζ(-1) should be -1/12: {v}"

    r3 = functional_equation_zeta(0.5)
    assert r3.ok, r3.error
    assert r3.result["verified"] is True, f"functional equation failed: {r3.error}"

    r4 = nontrivial_zeros(5)
    assert r4.ok, r4.error
    assert len(r4.result["zeros"]) == 5, f"should have 5 zeros: {r4.result}"

    r5 = analytic_continuation_zeta(0)
    assert r5.ok, r5.error
    v = r5.result.real if isinstance(r5.result, complex) else r5.result
    assert abs(v + 0.5) < 1e-6, f"ζ(0) should be -1/2: {v}"

    print("  [PASS] zeta: 5/5")
    return True


def test_all() -> bool:
    """运行所有复分析测试。"""
    print("=" * 60)
    print("Testing: complex_analysis")
    print("=" * 60)
    results = [
        test_complex_topology(),
        test_elementary_funcs(),
        test_holomorphic(),
        test_complex_integral(),
        test_series(),
        test_residue(),
        test_conformal(),
        test_zeta(),
    ]
    passed = sum(results)
    total = len(results)
    print(f"\ncomplex_analysis: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
