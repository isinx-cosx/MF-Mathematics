"""algebraic_topology — 代数拓扑子模块。

涵盖同伦与基本群、同调群、上同调、映射度与不动点定理、
计算拓扑（持续同调）。
"""

from .homotopy import (
    fundamental_group,
    is_simply_connected,
    path_homotopy,
)
from .homology import (
    simplicial_complex,
    boundary_operator,
    homology_group,
    betti_numbers,
    euler_characteristic,
)
from .cohomology import (
    cohomology_group,
    cup_product,
    poincare_duality,
)
from .degree_fixedpoint import (
    mapping_degree,
    brouwer_fixed_point_theorem,
    hairy_ball_theorem,
)
from .persistent_homology import (
    filtration,
    persistence_diagram,
    barcode_plot,
)

__all__ = [
    "fundamental_group",
    "is_simply_connected",
    "path_homotopy",
    "simplicial_complex",
    "boundary_operator",
    "homology_group",
    "betti_numbers",
    "euler_characteristic",
    "cohomology_group",
    "cup_product",
    "poincare_duality",
    "mapping_degree",
    "brouwer_fixed_point_theorem",
    "hairy_ball_theorem",
    "filtration",
    "persistence_diagram",
    "barcode_plot",
]


def self_test():
    """自测 algebraic_topology 包所有子模块。"""
    import importlib
    import os
    import pkgutil

    pkg_path = os.path.dirname(__file__)
    total_pass = 0
    total_fail = 0
    total_error = 0

    print("=== algebraic_topology package self_test ===")

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
