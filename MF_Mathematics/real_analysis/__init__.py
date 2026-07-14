"""MF_Mathematics Real Analysis 子模块 — 实分析。

包含：实数系、数列极限、函数极限与连续性、可微性、黎曼积分、函数序列与级数。
"""

from .real_numbers import (
    dedekind_cut,
    supremum,
    infimum,
    archimedean_property,
)
from .sequence_limit import (
    sequence_limit,
    sequence_convergence,
    cauchy_criterion,
)
from .function_limit import (
    limit_epsilon_delta,
    is_continuous,
    uniform_continuity,
    discontinuity_classify,
    extreme_value,
    intermediate_value,
)
from .differentiability import (
    derivative_definition,
    is_differentiable,
    taylor_polynomial,
    taylor_remainder,
    rolle_theorem,
    lagrange_theorem,
)
from .riemann_integral import (
    darboux_sum,
    riemann_integrable,
    fundamental_theorem,
    integral_mean_value,
)
from .function_series import (
    pointwise_convergence,
    uniform_convergence,
    weierstrass_m_test,
    termwise_integration,
    termwise_differentiation,
)

__all__ = [
    # real_numbers
    "dedekind_cut",
    "supremum",
    "infimum",
    "archimedean_property",
    # sequence_limit
    "sequence_limit",
    "sequence_convergence",
    "cauchy_criterion",
    # function_limit
    "limit_epsilon_delta",
    "is_continuous",
    "uniform_continuity",
    "discontinuity_classify",
    "extreme_value",
    "intermediate_value",
    # differentiability
    "derivative_definition",
    "is_differentiable",
    "taylor_polynomial",
    "taylor_remainder",
    "rolle_theorem",
    "lagrange_theorem",
    # riemann_integral
    "darboux_sum",
    "riemann_integrable",
    "fundamental_theorem",
    "integral_mean_value",
    # function_series
    "pointwise_convergence",
    "uniform_convergence",
    "weierstrass_m_test",
    "termwise_integration",
    "termwise_differentiation",
]


def self_test():
    """自测 real_analysis 包所有子模块。"""
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    total_pass = 0
    total_fail = 0
    total_error = 0

    print("=== real_analysis package self_test ===")

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
