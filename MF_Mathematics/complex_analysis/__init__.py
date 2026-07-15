"""MF_Mathematics Complex Analysis 子模块 — 复分析。

包含：复平面拓扑、初等复函数、全纯函数、复积分、级数表示、留数定理、
共形映射、黎曼 ζ 函数。
"""

from .complex_topology import (
    is_open,
    is_connected,
    is_domain,
)
from .elementary_funcs import (
    exp_complex,
    log_complex,
    sqrt_complex,
    mobius_transform,
)
from .holomorphic import (
    is_holomorphic,
    cauchy_riemann,
    is_harmonic,
)
from .complex_integral import (
    contour_integral,
    cauchy_theorem,
    cauchy_integral_formula,
    derivative_formula,
)
from .series import (
    taylor_series,
    laurent_series,
    singularity_classify,
    pole_order,
)
from .residue import (
    residue,
    residue_theorem,
    real_integral,
    argument_principle,
    rouche_theorem,
)
from .conformal import (
    is_conformal,
    riemann_mapping,
    boundary_correspondence,
)
from .zeta import (
    zeta_series,
    analytic_continuation_zeta,
    functional_equation_zeta,
    nontrivial_zeros,
)

__all__ = [
    # complex_topology
    "is_open",
    "is_connected",
    "is_domain",
    # elementary_funcs
    "exp_complex",
    "log_complex",
    "sqrt_complex",
    "mobius_transform",
    # holomorphic
    "is_holomorphic",
    "cauchy_riemann",
    "is_harmonic",
    # complex_integral
    "contour_integral",
    "cauchy_theorem",
    "cauchy_integral_formula",
    "derivative_formula",
    # series
    "taylor_series",
    "laurent_series",
    "singularity_classify",
    "pole_order",
    # residue
    "residue",
    "residue_theorem",
    "real_integral",
    "argument_principle",
    "rouche_theorem",
    # conformal
    "is_conformal",
    "riemann_mapping",
    "boundary_correspondence",
    # zeta
    "zeta_series",
    "analytic_continuation_zeta",
    "functional_equation_zeta",
    "nontrivial_zeros",
]


def self_test():
    """自测 complex_analysis 包所有子模块。"""
    import os
    from MF_Mathematics.core.test_utils import run_subpackage_tests

    return run_subpackage_tests(
        "complex_analysis",
        os.path.dirname(__file__),
        __package__,
    )