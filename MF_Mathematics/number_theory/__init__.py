"""number_theory — 数论子模块。

涵盖核心算法（欧几里得/扩展欧几里得/快速幂）、数论函数（欧拉函数/莫比乌斯函数）、
模算术与同余（中国剩余定理/原根/离散对数）、素数分布与筛法（埃氏筛/米勒-拉宾）、
连分数、与复分析/ζ 函数的接口。
"""

from .core_algorithms import (
    gcd,
    extended_gcd,
    mod_inverse,
    mod_pow,
)
from .arithmetic_functions import (
    euler_phi,
    divisor_count,
    divisor_sum,
    mobius,
    mobius_prefix,
)
from .modular_arithmetic import (
    crt,
    primitive_root,
    discrete_log,
)
from .prime_sieves import (
    eratosthenes,
    segmented_sieve,
    is_prime,
    prime_factors,
)
from .continued_fractions import (
    continued_fraction,
    convergents,
    best_rational_approximation,
)
from .zeta_interface import (
    euler_product,
    zeta_dirichlet_series,
    dirichlet_l_function,
    bernoulli_number,
    zeta_negative,
)

__all__ = [
    "gcd",
    "extended_gcd",
    "mod_inverse",
    "mod_pow",
    "euler_phi",
    "divisor_count",
    "divisor_sum",
    "mobius",
    "mobius_prefix",
    "crt",
    "primitive_root",
    "discrete_log",
    "eratosthenes",
    "segmented_sieve",
    "is_prime",
    "prime_factors",
    "continued_fraction",
    "convergents",
    "best_rational_approximation",
    "euler_product",
    "zeta_dirichlet_series",
    "dirichlet_l_function",
    "bernoulli_number",
    "zeta_negative",
]


def self_test():
    """自测 number_theory 包所有子模块。"""
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    total_pass = 0
    total_fail = 0
    total_error = 0

    print("=== number_theory package self_test ===")

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
