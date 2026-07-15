"""linear_algebra — 线性代数子模块。

包含: 线性方程组、向量空间、线性变换、内积与正交、特征值与特征向量、二次型与正定性。
"""

from .linear_systems import (
    gaussian_elimination,
    rank,
    solve_linear_system,
    nullspace,
)
from .vector_spaces import (
    is_vector_space,
    linear_combination,
    is_linear_independent,
    basis,
    dimension,
    subspace_span,
)
from .linear_transforms import (
    linear_transform,
    matrix_representation,
    kernel,
    image,
    rank_nullity,
)
from .inner_product import (
    dot,
    norm,
    angle,
    is_orthogonal,
    gram_schmidt,
    orthogonal_projection,
)
from .eigen import (
    eigenvalues,
    eigenvectors,
    characteristic_polynomial,
    is_diagonalizable,
    diagonalize,
)
from .quadratic_forms import (
    quadratic_form,
    standard_form,
    is_positive_definite,
    is_negative_definite,
    is_indefinite,
)

__all__ = [
    # linear_systems
    "gaussian_elimination", "rank", "solve_linear_system", "nullspace",
    # vector_spaces
    "is_vector_space", "linear_combination", "is_linear_independent",
    "basis", "dimension", "subspace_span",
    # linear_transforms
    "linear_transform", "matrix_representation", "kernel", "image", "rank_nullity",
    # inner_product
    "dot", "norm", "angle", "is_orthogonal", "gram_schmidt", "orthogonal_projection",
    # eigen
    "eigenvalues", "eigenvectors", "characteristic_polynomial",
    "is_diagonalizable", "diagonalize",
    # quadratic_forms
    "quadratic_form", "standard_form", "is_positive_definite",
    "is_negative_definite", "is_indefinite",
]


def self_test():
    """自测 linear_algebra 包所有子模块。"""
    import os
    from MF_Mathematics.core.test_utils import run_subpackage_tests

    return run_subpackage_tests(
        "linear_algebra",
        os.path.dirname(__file__),
        __package__,
    )