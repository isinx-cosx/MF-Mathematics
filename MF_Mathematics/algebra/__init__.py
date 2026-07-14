"""MF_Mathematics Algebra 子模块 — 基础代数。

包含：数与运算、代数式、方程、不等式、函数、数列、计数与二项式、平面解析几何。
"""

from .number_theory import (
    commutative_law,
    associative_law,
    distributive_law,
    abs_value,
    distance_on_number_line,
    ratio,
    percentage,
    percentage_change,
    to_scientific_notation,
    significant_figures,
)
from .expression import (
    simplify_polynomial,
    expand_expression,
    factor_common,
    factor_perfect_square,
    factor_difference_squares,
    factor_cross,
    factor_group,
    factor,
    simplify_fraction,
    common_denominator,
    fraction_operations,
    rationalize_denominator,
    simplify_radical,
    like_radicals,
    radical_operations,
)
from .equation import (
    solve_linear,
    linear_application,
    solve_linear_system,
    solve_quadratic,
    discriminant,
    vieta_theorem,
    solve_fractional,
    solve_irrational,
)
from .inequality import (
    inequality_properties,
    solve_linear_inequality,
    solve_inequality_system,
    solve_quadratic_inequality,
    am_gm_inequality,
    max_min_initial,
)
from .function import (
    domain,
    range_estimate,
    correspondence_rule,
    linear_function,
    slope_intercept,
    inverse_proportional,
    quadratic_function,
    quadratic_extrema,
    power_function,
    exponential_function,
    log_function,
    sine_cosine_tangent,
    trig_basic_identities,
    trig_periodicity,
)
from .sequences import (
    sequence_term,
    arithmetic_sequence,
    arithmetic_sum,
    arithmetic_proof,
    geometric_sequence,
    geometric_sum,
    geometric_proof,
    recurrence_sequence,
)
from .combinatorics import (
    addition_principle,
    multiplication_principle,
    permutation,
    combination,
    comb_identities,
    binomial_expand,
    binomial_term,
)
from .analytic_geometry import (
    distance,
    midpoint,
    line_from_points,
    line_from_slope_intercept,
    line_from_point_slope,
    line_from_intercepts,
    line_general,
    circle_standard,
    circle_general,
)

__all__ = [
    # number_theory
    "commutative_law",
    "associative_law",
    "distributive_law",
    "abs_value",
    "distance_on_number_line",
    "ratio",
    "percentage",
    "percentage_change",
    "to_scientific_notation",
    "significant_figures",
    # expression
    "simplify_polynomial",
    "expand_expression",
    "factor_common",
    "factor_perfect_square",
    "factor_difference_squares",
    "factor_cross",
    "factor_group",
    "factor",
    "simplify_fraction",
    "common_denominator",
    "fraction_operations",
    "rationalize_denominator",
    "simplify_radical",
    "like_radicals",
    "radical_operations",
    # equation
    "solve_linear",
    "linear_application",
    "solve_linear_system",
    "solve_quadratic",
    "discriminant",
    "vieta_theorem",
    "solve_fractional",
    "solve_irrational",
    # inequality
    "inequality_properties",
    "solve_linear_inequality",
    "solve_inequality_system",
    "solve_quadratic_inequality",
    "am_gm_inequality",
    "max_min_initial",
    # function
    "domain",
    "range_estimate",
    "correspondence_rule",
    "linear_function",
    "slope_intercept",
    "inverse_proportional",
    "quadratic_function",
    "quadratic_extrema",
    "power_function",
    "exponential_function",
    "log_function",
    "sine_cosine_tangent",
    "trig_basic_identities",
    "trig_periodicity",
    # sequences
    "sequence_term",
    "arithmetic_sequence",
    "arithmetic_sum",
    "arithmetic_proof",
    "geometric_sequence",
    "geometric_sum",
    "geometric_proof",
    "recurrence_sequence",
    # combinatorics
    "addition_principle",
    "multiplication_principle",
    "permutation",
    "combination",
    "comb_identities",
    "binomial_expand",
    "binomial_term",
    # analytic_geometry
    "distance",
    "midpoint",
    "line_from_points",
    "line_from_slope_intercept",
    "line_from_point_slope",
    "line_from_intercepts",
    "line_general",
    "circle_standard",
    "circle_general",
]


def self_test():
    """自测 algebra 包所有子模块。"""
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    total_pass = 0
    total_fail = 0
    total_error = 0

    print("=== algebra package self_test ===")

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
