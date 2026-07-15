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
    import os
    from MF_Mathematics.core.test_utils import run_subpackage_tests

    return run_subpackage_tests(
        "algebraic_topology",
        os.path.dirname(__file__),
        __package__,
    )