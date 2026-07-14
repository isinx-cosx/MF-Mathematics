"""measure_theory — 测度论子模块。

涵盖集合系、测度构造、可测函数、勒贝格积分、
积分极限定理、乘积测度与Fubini定理、概率论中的测度论。
"""

from .set_systems import (
    is_sigma_algebra,
    generate_sigma_algebra,
    borel_sigma_algebra,
)
from .measure_construction import (
    outer_measure,
    caratheodory_measurable,
    lebesgue_measure,
    measure_properties,
)
from .measurable_functions import (
    is_measurable,
    simple_function,
    step_function_approx,
)
from .lebesgue_integral import (
    integral_simple,
    integral_nonnegative,
    integral_general,
    integral_zero_set_independent,
)
from .convergence_theorems import (
    monotone_convergence,
    fatou_lemma,
    dominated_convergence,
)
from .product_measure import (
    product_measure,
    fubini_theorem,
)
from .probability_measure import (
    probability_space,
    random_variable,
    expectation,
    conditional_expectation,
    independence_check,
)

__all__ = [
    "is_sigma_algebra",
    "generate_sigma_algebra",
    "borel_sigma_algebra",
    "outer_measure",
    "caratheodory_measurable",
    "lebesgue_measure",
    "measure_properties",
    "is_measurable",
    "simple_function",
    "step_function_approx",
    "integral_simple",
    "integral_nonnegative",
    "integral_general",
    "integral_zero_set_independent",
    "monotone_convergence",
    "fatou_lemma",
    "dominated_convergence",
    "product_measure",
    "fubini_theorem",
    "probability_space",
    "random_variable",
    "expectation",
    "conditional_expectation",
    "independence_check",
]


def self_test():
    """自测 measure_theory 包所有子模块。"""
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    total_pass = 0
    total_fail = 0
    total_error = 0

    print("=== measure_theory package self_test ===")

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
