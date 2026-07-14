"""numerical — 数值分析子模块。

涵盖误差与稳定性、插值与逼近、数值积分与微分、
线性代数数值方法、常微分方程初值问题。
"""

from .error_stability import (
    condition_number,
    truncation_error,
    rounding_error_estimate,
    is_stable,
)
from .interpolation import (
    lagrange_interpolation,
    newton_interpolation,
    cubic_spline,
    least_squares_fit,
)
from .numerical_integration import (
    trapezoidal_rule,
    simpson_rule,
    gauss_quadrature,
    numerical_derivative,
    optimal_step,
)
from .matrix_numerical import (
    lu_decomposition,
    jacobi_iteration,
    gauss_seidel,
    conjugate_gradient,
    power_method,
    qr_algorithm,
)
from .ode_solver import (
    euler_method,
    rk4,
    implicit_euler,
    stiff_detector,
)

__all__ = [
    # error_stability
    "condition_number", "truncation_error", "rounding_error_estimate", "is_stable",
    # interpolation
    "lagrange_interpolation", "newton_interpolation", "cubic_spline", "least_squares_fit",
    # numerical_integration
    "trapezoidal_rule", "simpson_rule", "gauss_quadrature", "numerical_derivative", "optimal_step",
    # matrix_numerical
    "lu_decomposition", "jacobi_iteration", "gauss_seidel", "conjugate_gradient", "power_method", "qr_algorithm",
    # ode_solver
    "euler_method", "rk4", "implicit_euler", "stiff_detector",
]


def self_test():
    """自测 numerical 包所有子模块。"""
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    total_pass = 0
    total_fail = 0
    total_error = 0

    print("=== numerical package self_test ===")

    for _, mod_name, _ in pkgutil.iter_modules([pkg_path]):
        if mod_name.startswith('_') or mod_name == 'tests':
            continue
        try:
            mod = importlib.import_module(f'.{mod_name}', package=__package__)
        except Exception as e:
            total_error += 1
            print(f"  {mod_name}: ERROR importing - {e}")
            continue
        if not hasattr(mod, 'self_test'):
            continue
        try:
            mod.self_test()
            total_pass += 1
            print(f"  {mod_name}: pass")
        except AssertionError as e:
            total_fail += 1
            print(f"  {mod_name}: FAIL - {e}")
        except Exception as e:
            total_error += 1
            print(f"  {mod_name}: ERROR - {e}")

    print(f"  Summary: {total_pass} passed, {total_fail} failed, {total_error} errors")
    return (total_pass, total_fail, total_error)
