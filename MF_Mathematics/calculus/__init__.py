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
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    total_pass = 0
    total_fail = 0
    total_error = 0

    print("=== calculus package self_test ===")

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
