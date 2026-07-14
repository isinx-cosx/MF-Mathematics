"""MF_Mathematics Probability 子模块 — 概率论与数理统计。

包含：概率空间、随机变量、期望与方差、经典分布、极限定理、统计推断、假设检验、回归分析。
"""

from .probability_space import (
    conditional_probability,
    is_independent,
    total_probability,
    bayes_theorem,
)
from .random_variable import (
    distribution_function,
    pmf,
    pdf,
    expectation as rv_expectation,
)
from .expectations import (
    expectation,
    variance,
    covariance,
    correlation_coefficient,
)
from .distributions import (
    bernoulli,
    binomial,
    poisson,
    uniform,
    exponential,
    normal,
)
from .limits_theorems import (
    law_of_large_numbers,
    central_limit_theorem,
)
from .statistics import (
    sample_mean,
    sample_variance,
    moment_estimate,
    mle,
    confidence_interval,
)
from .hypothesis_test import (
    z_test,
    t_test,
    chi_square_test,
    p_value,
)
from .regression import (
    linear_regression,
    predict,
    residuals,
)

__all__ = [
    # probability_space
    "conditional_probability",
    "is_independent",
    "total_probability",
    "bayes_theorem",
    # random_variable
    "distribution_function",
    "pmf",
    "pdf",
    "rv_expectation",
    # expectations
    "expectation",
    "variance",
    "covariance",
    "correlation_coefficient",
    # distributions
    "bernoulli",
    "binomial",
    "poisson",
    "uniform",
    "exponential",
    "normal",
    # limit_theorems
    "law_of_large_numbers",
    "central_limit_theorem",
    # statistics
    "sample_mean",
    "sample_variance",
    "moment_estimate",
    "mle",
    "confidence_interval",
    # hypothesis_test
    "z_test",
    "t_test",
    "chi_square_test",
    "p_value",
    # regression
    "linear_regression",
    "predict",
    "residuals",
]


def self_test():
    """自测 probability 包所有子模块。"""
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    total_pass = 0
    total_fail = 0
    total_error = 0

    print("=== probability package self_test ===")

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
