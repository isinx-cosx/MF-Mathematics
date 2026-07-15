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
    import os
    from MF_Mathematics.core.test_utils import run_subpackage_tests

    return run_subpackage_tests(
        "harmonic_analysis",
        os.path.dirname(__file__),
        __package__,
    )