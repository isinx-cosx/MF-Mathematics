"""实分析子模块测试。"""

from __future__ import annotations

import sys
import os

# 确保可以导入 MF_Mathematics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_real_numbers() -> bool:
    """测试 real_numbers 模块。"""
    from MF_Mathematics.real_analysis.real_numbers import (
        supremum,
        infimum,
        archimedean_property,
        dedekind_cut,
    )

    ok = True

    # supremum: {x | x < 2} → 2
    r = supremum("{x | x < 2}")
    if not r.ok or r.result != 2.0:
        print(f"  FAIL supremum: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS supremum({'{x | x < 2}'}): {r.result}")

    # supremum on finite set
    r = supremum([1, 3, 5, 2, 4])
    if not r.ok or r.result != 5.0:
        print(f"  FAIL supremum (finite): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS supremum([1,3,5,2,4]): {r.result}")

    # infimum: {x | x > 1} → 1
    r = infimum("{x | x > 1}")
    if not r.ok or r.result != 1.0:
        print(f"  FAIL infimum: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS infimum({'{x | x > 1}'}): {r.result}")

    # archimedean_property
    r = archimedean_property(100.0, 1.0)
    if not r.ok or r.result != 101:
        print(f"  FAIL archimedean_property: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS archimedean_property(100, 1): n={r.result}")

    # dedekind_cut valid
    r = dedekind_cut([1, 2, 3], [4, 5, 6])
    if not r.ok or r.result is not True:
        print(f"  FAIL dedekind_cut (valid): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS dedekind_cut(valid)")

    # dedekind_cut invalid
    r = dedekind_cut([1, 2, 4], [3, 4, 5])
    if not r.ok or r.result is not False:
        print(f"  FAIL dedekind_cut (invalid): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS dedekind_cut(invalid)")

    return ok


def test_sequence_limit() -> bool:
    """测试 sequence_limit 模块。"""
    from MF_Mathematics.real_analysis.sequence_limit import (
        sequence_limit,
        sequence_convergence,
        cauchy_criterion,
    )

    ok = True

    # sequence_limit: 1/n → 0
    r = sequence_limit("1/n", "n", "oo")
    if not r.ok or "0" not in r.result:
        print(f"  FAIL sequence_limit(1/n): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS sequence_limit(1/n): {r.result}")

    # sequence_convergence: 1/n → 收敛
    r = sequence_convergence("1/n", "n")
    if not r.ok or "收敛" != r.result:
        print(f"  FAIL sequence_convergence(1/n): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS sequence_convergence(1/n): {r.result}")

    # sequence_convergence: n → 发散
    r = sequence_convergence("n", "n")
    if not r.ok or "发散" not in r.result:
        print(f"  FAIL sequence_convergence(n): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS sequence_convergence(n): {r.result}")

    # cauchy_criterion: 1/n → True
    r = cauchy_criterion("1/n", epsilon=0.01, max_n=500)
    if not r.ok or r.result is not True:
        print(f"  FAIL cauchy_criterion(1/n): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS cauchy_criterion(1/n): {r.result}")

    # cauchy_criterion: (-1)**n → False
    r = cauchy_criterion("(-1)**n", epsilon=0.01, max_n=500)
    if not r.ok:
        print(f"  FAIL cauchy_criterion((-1)^n): {r.error}")
        ok = False
    else:
        print(f"  PASS cauchy_criterion((-1)^n): {r.result}")

    return ok


def test_function_limit() -> bool:
    """测试 function_limit 模块。"""
    from MF_Mathematics.real_analysis.function_limit import (
        limit_epsilon_delta,
        is_continuous,
        uniform_continuity,
        discontinuity_classify,
        extreme_value,
        intermediate_value,
    )

    ok = True

    # is_continuous: sin(x) at 0
    r = is_continuous("sin(x)", "x", 0)
    if not r.ok or r.result is not True:
        print(f"  FAIL is_continuous(sin(x), 0): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS is_continuous(sin(x), 0): {r.result}")

    # is_continuous: 1/(x-1) at 1
    r = is_continuous("1/(x-1)", "x", 1)
    if not r.ok or r.result is not False:
        print(f"  FAIL is_continuous(1/(x-1), 1): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS is_continuous(1/(x-1), 1): {r.result}")

    # discontinuity_classify
    r = discontinuity_classify("1/(x-1)", "x", 1)
    if not r.ok or "无穷" not in r.result:
        print(f"  FAIL discontinuity_classify: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS discontinuity_classify(1/(x-1), 1): {r.result}")

    # extreme_value
    r = extreme_value("x**2", "x", [0, 1])
    if not r.ok:
        print(f"  FAIL extreme_value: {r.error}")
        ok = False
    else:
        print(f"  PASS extreme_value(x^2, [0,1]): max={r.result['max']:.4f}, min={r.result['min']:.4f}")

    # intermediate_value
    r = intermediate_value("x**3", "x", [-1, 1], 0)
    if not r.ok:
        print(f"  FAIL intermediate_value: {r.error}")
        ok = False
    else:
        print(f"  PASS intermediate_value(x^3, [-1,1], c=0): ξ={r.result}")

    # uniform_continuity
    r = uniform_continuity("x**2", "x", [0, 1])
    if not r.ok or r.result is not True:
        print(f"  FAIL uniform_continuity: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS uniform_continuity(x^2, [0,1]): {r.result}")

    # limit_epsilon_delta
    r = limit_epsilon_delta("x**2", "x", 0, epsilon=0.01)
    if not r.ok:
        print(f"  FAIL limit_epsilon_delta: {r.error}")
        ok = False
    else:
        print(f"  PASS limit_epsilon_delta(x^2, x->0): L={r.result['L']}, δ={r.result['δ']}")

    return ok


def test_differentiability() -> bool:
    """测试 differentiability 模块。"""
    from MF_Mathematics.real_analysis.differentiability import (
        derivative_definition,
        is_differentiable,
        taylor_polynomial,
        taylor_remainder,
        rolle_theorem,
        lagrange_theorem,
    )

    ok = True

    # derivative_definition
    r = derivative_definition("x**2", "x", 0)
    if not r.ok or abs(r.result - 0) > 1e-6:
        print(f"  FAIL derivative_definition: {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS derivative_definition(x^2, 0): {r.result:.4f}")

    # is_differentiable: sin(x) at 0
    r = is_differentiable("sin(x)", "x", 0)
    if not r.ok or r.result is not True:
        print(f"  FAIL is_differentiable(sin(x), 0): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS is_differentiable(sin(x), 0): {r.result}")

    # taylor_polynomial: sin(x) at 0, n=3
    r = taylor_polynomial("sin(x)", "x", 0, 3)
    if not r.ok:
        print(f"  FAIL taylor_polynomial: {r.error}")
        ok = False
    else:
        print(f"  PASS taylor_polynomial(sin(x), 0, 3): {r.result}")

    # taylor_remainder
    r = taylor_remainder("sin(x)", "x", 0, 3)
    if not r.ok:
        print(f"  FAIL taylor_remainder: {r.error}")
        ok = False
    else:
        print(f"  PASS taylor_remainder(sin(x), 0, 3): {r.result}")

    # rolle_theorem
    r = rolle_theorem("x**2 - 1", "x", [-1, 1])
    if not r.ok:
        print(f"  FAIL rolle_theorem: {r.error}")
        ok = False
    else:
        print(f"  PASS rolle_theorem(x^2-1, [-1,1]): ξ={r.result}")

    # lagrange_theorem
    r = lagrange_theorem("x**2", "x", [0, 2])
    if not r.ok:
        print(f"  FAIL lagrange_theorem: {r.error}")
        ok = False
    else:
        print(f"  PASS lagrange_theorem(x^2, [0,2]): ξ={r.result['xi']:.4f}, slope={r.result['secant_slope']:.4f}")

    return ok


def test_riemann_integral() -> bool:
    """测试 riemann_integral 模块。"""
    from MF_Mathematics.real_analysis.riemann_integral import (
        darboux_sum,
        riemann_integrable,
        fundamental_theorem,
        integral_mean_value,
    )

    ok = True

    # darboux_sum
    r = darboux_sum("x**2", "x", 0, 1)
    if not r.ok:
        print(f"  FAIL darboux_sum: {r.error}")
        ok = False
    else:
        print(f"  PASS darboux_sum(x^2, [0,1]): L={r.result['lower_sum']:.4f}, U={r.result['upper_sum']:.4f}")

    # riemann_integrable: x^2 on [0,1] → True
    r = riemann_integrable("x**2", "x", 0, 1)
    if not r.ok or r.result is not True:
        print(f"  FAIL riemann_integrable(x^2, [0,1]): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS riemann_integrable(x^2, [0,1]): {r.result}")

    # fundamental_theorem
    r = fundamental_theorem("x**2", "x", 0, 1)
    if not r.ok:
        print(f"  FAIL fundamental_theorem: {r.error}")
        ok = False
    else:
        print(f"  PASS fundamental_theorem(x^2, [0,1]): {r.result['integral']:.4f}")

    # integral_mean_value
    r = integral_mean_value("x**2", "x", 0, 1)
    if not r.ok:
        print(f"  FAIL integral_mean_value: {r.error}")
        ok = False
    else:
        print(f"  PASS integral_mean_value(x^2, [0,1]): mean={r.result['mean_value']:.4f}, ξ={r.result['xi']:.4f}")

    return ok


def test_function_series() -> bool:
    """测试 function_series 模块。"""
    from MF_Mathematics.real_analysis.function_series import (
        pointwise_convergence,
        uniform_convergence,
        weierstrass_m_test,
        termwise_integration,
        termwise_differentiation,
    )

    ok = True

    # pointwise_convergence: x^n at x=0.5
    r = pointwise_convergence("x**n", "x", 0.5)
    if not r.ok or "0" not in r.result:
        print(f"  FAIL pointwise_convergence(x^n, 0.5): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS pointwise_convergence(x^n, 0.5): {r.result}")

    # uniform_convergence: x^n on [0, 0.5]
    r = uniform_convergence("x**n", "x", [0, 0.5])
    if not r.ok or "一致" not in r.result["convergence_type"]:
        print(f"  FAIL uniform_convergence(x^n, [0,0.5]): {r.error or r.result}")
        ok = False
    else:
        print(f"  PASS uniform_convergence(x^n, [0,0.5]): {r.result['convergence_type']}")

    # weierstrass_m_test
    r = weierstrass_m_test("x**n / n**2", None, "x", [0, 1])
    if not r.ok:
        print(f"  FAIL weierstrass_m_test: {r.error}")
        ok = False
    else:
        print(f"  PASS weierstrass_m_test(x^n/n^2): {r.result}")

    # termwise_integration
    r = termwise_integration("x**n / n**2", "x", 0, 1, n_terms=5)
    if not r.ok:
        print(f"  FAIL termwise_integration: {r.error}")
        ok = False
    else:
        print(f"  PASS termwise_integration(x^n/n^2): {r.result['termwise_sum']:.6f}")

    # termwise_differentiation
    r = termwise_differentiation("x**n / n**2", "x", n_terms=3)
    if not r.ok:
        print(f"  FAIL termwise_differentiation: {r.error}")
        ok = False
    else:
        print(f"  PASS termwise_differentiation(x^n/n^2): {r.result['derivative_series']}")

    return ok


def test_all() -> bool:
    """运行所有实分析测试。"""
    print("=" * 60)
    print("实分析 (real_analysis) 子模块测试")
    print("=" * 60)

    all_ok = True

    print("\n--- real_numbers ---")
    if not test_real_numbers():
        all_ok = False

    print("\n--- sequence_limit ---")
    if not test_sequence_limit():
        all_ok = False

    print("\n--- function_limit ---")
    if not test_function_limit():
        all_ok = False

    print("\n--- differentiability ---")
    if not test_differentiability():
        all_ok = False

    print("\n--- riemann_integral ---")
    if not test_riemann_integral():
        all_ok = False

    print("\n--- function_series ---")
    if not test_function_series():
        all_ok = False

    print("\n" + "=" * 60)
    print(f"实分析测试: {'ALL PASSED' if all_ok else 'SOME FAILED'}")
    print("=" * 60)
    return all_ok


if __name__ == "__main__":
    test_all()
