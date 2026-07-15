"""MF_Mathematics Calculus 子模块 — 微积分。

包含：极限、导数、导数应用、积分、积分应用、级数。
"""

from .limits import (
    limit,
    is_continuous,
    discontinuity_classify,
)
from .derivatives import (
    diff,
    diff_at,
    implicit_diff,
    parametric_diff,
    differential,
)
from .derivatives_app import (
    rolle_theorem,
    lagrange_theorem,
    lhopital,
    monotonicity,
    local_extrema,
    global_extrema,
    taylor,
)
from .integrals import (
    integrate,
    integrate_numeric,
    improper_integral,
)
from .integrals_app import (
    area_between,
    volume_disk,
    volume_shell,
    arc_length,
)
from .series import (
    series_sum,
    series_convergence,
    power_series,
    power_series_radius,
)

__all__ = [
    # limits
    "limit",
    "is_continuous",
    "discontinuity_classify",
    # derivatives
    "diff",
    "diff_at",
    "implicit_diff",
    "parametric_diff",
    "differential",
    # derivatives_app
    "rolle_theorem",
    "lagrange_theorem",
    "lhopital",
    "monotonicity",
    "local_extrema",
    "global_extrema",
    "taylor",
    # integrals
    "integrate",
    "integrate_numeric",
    "improper_integral",
    # integrals_app
    "area_between",
    "volume_disk",
    "volume_shell",
    "arc_length",
    # series
    "series_sum",
    "series_convergence",
    "power_series",
    "power_series_radius",
]


def self_test():
    """自测 calculus 包所有子模块。"""
    import os
    from MF_Mathematics.core.test_utils import run_subpackage_tests

    return run_subpackage_tests(
        "calculus",
        os.path.dirname(__file__),
        __package__,
    )