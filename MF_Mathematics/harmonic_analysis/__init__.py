"""harmonic_analysis — 调和分析子模块。

涵盖傅里叶级数、傅里叶变换、卷积与傅里叶变换、
分布与缓增分布、时频分析与不确定性原理、调和分析与数论。
"""

from .fourier_series import (
    fourier_coeff,
    fourier_series,
    complex_fourier_coeff,
    orthogonality_check,
)
from .fourier_transform import (
    fourier_transform,
    inverse_fourier_transform,
    plancherel_theorem,
    ft_of_gaussian,
)
from .convolution import (
    convolution,
    convolution_theorem,
    gaussian_blur,
    low_pass_filter,
)
from .distributions import (
    delta_distribution,
    ft_delta,
    ft_constant,
    tempered_distribution,
)
from .time_frequency import (
    uncertainty_principle,
    stft,
    wavelet_transform,
)
from .zeta_harmonic import (
    poisson_summation,
    theta_function,
    functional_equation_demo,
)

__all__ = [
    "fourier_coeff",
    "fourier_series",
    "complex_fourier_coeff",
    "orthogonality_check",
    "fourier_transform",
    "inverse_fourier_transform",
    "plancherel_theorem",
    "ft_of_gaussian",
    "convolution",
    "convolution_theorem",
    "gaussian_blur",
    "low_pass_filter",
    "delta_distribution",
    "ft_delta",
    "ft_constant",
    "tempered_distribution",
    "uncertainty_principle",
    "stft",
    "wavelet_transform",
    "poisson_summation",
    "theta_function",
    "functional_equation_demo",
]


def self_test():
    """自测 harmonic_analysis 包所有子模块。"""
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    total_pass = 0
    total_fail = 0
    total_error = 0

    print("=== harmonic_analysis package self_test ===")

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
