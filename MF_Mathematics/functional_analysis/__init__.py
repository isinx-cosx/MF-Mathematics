"""functional_analysis — 泛函分析子模块。

涵盖赋范空间与巴拿赫空间、内积空间与希尔伯特空间、
线性算子与泛函、四大核心定理、谱理论、对偶空间与弱拓扑。
"""

from .normed_spaces import lp_norm, is_banach, space_completeness_check
from .inner_product_spaces import (
    inner_product,
    is_orthogonal,
    gram_schmidt,
    is_hilbert,
)
from .linear_operators import (
    operator_norm,
    is_bounded,
    linear_functional_eval,
    kernel_dimension,
)
from .core_theorems import (
    hahn_banach_extension,
    uniform_boundedness,
    open_mapping,
    closed_graph,
)
from .spectral_theory import spectrum_approx, spectrum_classify, spectral_theorem
from .dual_spaces import dual_space_basis, weak_convergence, is_reflexive

__all__ = [
    "lp_norm",
    "is_banach",
    "space_completeness_check",
    "inner_product",
    "is_orthogonal",
    "gram_schmidt",
    "is_hilbert",
    "operator_norm",
    "is_bounded",
    "linear_functional_eval",
    "kernel_dimension",
    "hahn_banach_extension",
    "uniform_boundedness",
    "open_mapping",
    "closed_graph",
    "spectrum_approx",
    "spectrum_classify",
    "spectral_theorem",
    "dual_space_basis",
    "weak_convergence",
    "is_reflexive",
]


def self_test():
    """自测 functional_analysis 包所有子模块。"""
    import os
    from MF_Mathematics.core.test_utils import run_subpackage_tests

    return run_subpackage_tests(
        "functional_analysis",
        os.path.dirname(__file__),
        __package__,
    )