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
    import os
    from MF_Mathematics.core.test_utils import run_subpackage_tests

    return run_subpackage_tests(
        "numerical",
        os.path.dirname(__file__),
        __package__,
    )