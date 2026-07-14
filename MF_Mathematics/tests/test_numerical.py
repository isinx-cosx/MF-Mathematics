"""test_numerical.py — 数值分析模块测试。"""

from __future__ import annotations

import sys
import os

# 确保能找到 MF_Mathematics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np


def test_error_stability() -> bool:
    """测试 error_stability 模块。"""
    from MF_Mathematics.numerical.error_stability import (
        condition_number,
        truncation_error,
        rounding_error_estimate,
        is_stable,
    )

    # condition_number — f(x)=1/x 相对条件数恒为 1
    r = condition_number("1/x", 1e-3)
    assert r.ok, f"condition_number failed: {r.error}"
    assert abs(r.result - 1.0) < 0.01, f"Expected cond ≈ 1, got {r.result}"

    # condition_number ill-conditioned
    r2 = condition_number("1/(x-1)", 1.001)
    assert r2.ok
    assert r2.result > 100, f"Expected large cond, got {r2.result}"

    # truncation_error
    def exp_series(x: float, n: int) -> float:
        s = 0.0
        term = 1.0
        for k in range(n + 1):
            s += term
            term *= x / (k + 1)
        return s

    r = truncation_error(exp_series, 1.0, 5, true_value=np.exp(1.0))
    assert r.ok
    assert r.result < 0.01

    # rounding_error_estimate
    r = rounding_error_estimate("sum(1e16, 1)", precision=16)
    assert r.ok
    assert r.result > 0

    # is_stable
    r = is_stable(lambda x: x + 1, 1000.0)
    assert r.ok
    assert r.result is True

    return True


def test_interpolation() -> bool:
    """测试 interpolation 模块。"""
    from MF_Mathematics.numerical.interpolation import (
        lagrange_interpolation,
        newton_interpolation,
        cubic_spline,
        least_squares_fit,
    )

    # lagrange
    r = lagrange_interpolation([0, 1, 2], [0, 1, 0])
    assert r.ok
    assert abs(float(np.polyval(r.result, 1)) - 1.0) < 1e-10

    # newton
    r = newton_interpolation([0, 1, 2], [0, 1, 4])
    assert r.ok
    fn = r.data["interpolant"]
    assert abs(fn(2) - 4) < 1e-10

    # cubic_spline (at least 4 points)
    r = cubic_spline([0, 1, 2, 3], [0, 1, 0, 1])
    assert r.ok
    fn = r.data["spline_func"]
    assert abs(fn(1) - 1.0) < 1e-10

    # least_squares_fit
    x = np.linspace(0, 4, 10)
    y = 2 * x + 1 + 0.1 * np.random.RandomState(42).randn(10)
    r = least_squares_fit(x.tolist(), y.tolist(), degree=1)
    assert r.ok
    assert r.data["r_squared"] > 0.9

    return True


def test_numerical_integration() -> bool:
    """测试 numerical_integration 模块。"""
    from MF_Mathematics.numerical.numerical_integration import (
        trapezoidal_rule,
        simpson_rule,
        gauss_quadrature,
        numerical_derivative,
        optimal_step,
    )

    # trapezoidal
    r = trapezoidal_rule("sin(x)", 0, np.pi, 100)
    assert r.ok
    assert abs(r.result - 2.0) < 0.001

    # simpson
    r = simpson_rule("sin(x)", 0, np.pi, 100)
    assert r.ok
    assert abs(r.result - 2.0) < 0.0001

    # gauss_quadrature
    r = gauss_quadrature("x**2", 0, 1, n=3)
    assert r.ok
    assert abs(r.result - 1 / 3) < 0.0001

    # numerical_derivative
    r = numerical_derivative("x**3", 2.0, method="central")
    assert r.ok
    assert abs(r.result - 12.0) < 0.001

    # optimal_step
    r = optimal_step("x**2", 1.0, method="central")
    assert r.ok
    assert r.result > 0

    return True


def test_matrix_numerical() -> bool:
    """测试 matrix_numerical 模块。"""
    from MF_Mathematics.numerical.matrix_numerical import (
        lu_decomposition,
        jacobi_iteration,
        gauss_seidel,
        conjugate_gradient,
        power_method,
        qr_algorithm,
    )

    # LU
    r = lu_decomposition([[4, 3], [6, 3]])
    assert r.ok
    L = np.array(r.result["L"])
    U = np.array(r.result["U"])
    assert np.max(np.abs(L @ U - np.array([[4, 3], [6, 3]]))) < 1e-10

    # jacobi
    r = jacobi_iteration([[4, 1], [2, 5]], [1, 1], [0, 0], max_iter=100)
    assert r.ok
    expected = np.array([2 / 9, 1 / 9])
    assert np.linalg.norm(np.array(r.result) - expected) < 0.01

    # gauss_seidel
    r = gauss_seidel([[4, 1], [2, 5]], [1, 1], [0, 0], max_iter=100)
    assert r.ok
    assert np.linalg.norm(np.array(r.result) - expected) < 0.01

    # conjugate_gradient
    r = conjugate_gradient([[4, 0], [0, 2]], [1, 1], [0, 0])
    assert r.ok
    assert abs(np.array(r.result)[0] - 0.25) < 0.01

    # power_method
    r = power_method([[2, 1], [1, 2]])
    assert r.ok
    assert abs(r.result["eigenvalue"] - 3.0) < 0.01

    # qr_algorithm
    r = qr_algorithm([[4, 1], [2, 3]])
    assert r.ok
    eigs = r.result
    assert any(abs(ev - 5) < 0.2 for ev in eigs if isinstance(ev, (int, float)))

    return True


def test_ode_solver() -> bool:
    """测试 ode_solver 模块。"""
    from MF_Mathematics.numerical.ode_solver import (
        euler_method,
        rk4,
        implicit_euler,
        stiff_detector,
    )

    # euler
    r = euler_method(lambda t, y: y, 0, 1, 1, 0.1)
    assert r.ok
    assert abs(r.result["y"][-1] - np.exp(1)) < 0.5

    # rk4
    r = rk4(lambda t, y: y, 0, 1, 1, 0.1)
    assert r.ok
    assert abs(r.result["y"][-1] - np.exp(1)) < 0.001

    # implicit_euler
    r = implicit_euler(lambda t, y: y, 0, 1, 1, 0.1)
    assert r.ok
    assert abs(r.result["y"][-1] - np.exp(1)) < 0.5

    # stiff_detector
    r = stiff_detector(lambda t, y: y, 0, 1, 1)
    assert r.ok
    assert r.result is False

    return True


def test_all() -> bool:
    """运行全部测试。"""
    modules = {
        "error_stability": test_error_stability,
        "interpolation": test_interpolation,
        "numerical_integration": test_numerical_integration,
        "matrix_numerical": test_matrix_numerical,
        "ode_solver": test_ode_solver,
    }

    passed = 0
    total = len(modules)
    for name, test_fn in modules.items():
        try:
            test_fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")

    print(f"  Numerical: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    ok = test_all()
    print(f"\nNumerical {'PASSED' if ok else 'FAILED'}")
