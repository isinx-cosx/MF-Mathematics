"""test_functional_analysis.py — 泛函分析模块测试。"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import math


def test_normed_spaces() -> bool:
    """测试 normed_spaces 模块。"""
    from MF_Mathematics.functional_analysis.normed_spaces import (
        lp_norm,
        is_banach,
        space_completeness_check,
    )

    # lp_norm — l^2 = sqrt(14)
    r = lp_norm([1, 2, 3], 2)
    assert r.ok, f"lp_norm l2 failed: {r.error}"
    assert abs(r.result - np.sqrt(14)) < 1e-10

    # lp_norm — l^inf
    r = lp_norm([1, -5, 3], float("inf"))
    assert r.ok
    assert abs(r.result - 5.0) < 1e-10

    # lp_norm — l^1
    r = lp_norm([1, -2, 3], 1)
    assert r.ok
    assert abs(r.result - 6.0) < 1e-10

    # is_banach
    r = is_banach("R^n", dimension=3)
    assert r.ok
    assert r.result is True

    # space_completeness_check
    seq = [[1.0 / (i + 1)] for i in range(20)]
    r = space_completeness_check(seq, norm="l2")
    assert r.ok

    return True


def test_inner_product_spaces() -> bool:
    """测试 inner_product_spaces 模块。"""
    from MF_Mathematics.functional_analysis.inner_product_spaces import (
        inner_product,
        is_orthogonal,
        gram_schmidt,
        is_hilbert,
    )

    # inner_product sin*cos = 0
    r = inner_product("sin(x)", "cos(x)", (0, 2 * math.pi), n_points=2000)
    assert r.ok
    assert abs(r.result) < 1e-4

    # is_orthogonal
    r = is_orthogonal("sin(x)", "cos(x)", (0, 2 * math.pi), tol=1e-4)
    assert r.ok
    assert r.result == True

    # gram_schmidt
    r = gram_schmidt([(1, 1), (1, 0)], inner_product_fn="dot")
    assert r.ok
    basis = r.result
    assert abs(np.linalg.norm(basis[0]) - 1.0) < 1e-10
    assert abs(np.linalg.norm(basis[1]) - 1.0) < 1e-10
    assert abs(np.dot(basis[0], basis[1])) < 1e-10

    # is_hilbert
    r = is_hilbert("R^n", dimension=5)
    assert r.ok
    assert r.result is True

    # inner_product sin*sin on [0,pi] = pi/2
    r = inner_product("sin(x)", "sin(x)", (0, math.pi))
    assert r.ok
    assert abs(r.result - math.pi / 2) < 0.01

    return True


def test_linear_operators() -> bool:
    """测试 linear_operators 模块。"""
    from MF_Mathematics.functional_analysis.linear_operators import (
        operator_norm,
        is_bounded,
        linear_functional_eval,
        kernel_dimension,
    )

    # operator_norm 谱范数 = 2
    r = operator_norm([[2, 0], [0, 2]], p=2)
    assert r.ok
    assert abs(r.result - 2.0) < 1e-10

    # operator_norm 行和 = 7
    r = operator_norm([[1, 2], [3, 4]], p="inf")
    assert r.ok
    assert abs(r.result - 7.0) < 1e-10

    # is_bounded
    r = is_bounded([[2, 0], [0, 2]])
    assert r.ok
    assert r.result is True

    # linear_functional_eval
    r = linear_functional_eval([1, 2, 3], [4, 5, 6])
    assert r.ok
    assert abs(r.result - 32.0) < 1e-10

    # kernel_dimension
    r = kernel_dimension([[1, 1], [1, 1]])
    assert r.ok
    assert r.result == 1

    return True


def test_core_theorems() -> bool:
    """测试 core_theorems 模块。"""
    from MF_Mathematics.functional_analysis.core_theorems import (
        hahn_banach_extension,
        uniform_boundedness,
        open_mapping,
        closed_graph,
    )

    # hahn_banach_extension
    r = hahn_banach_extension([1, 2, 3], subspace_dim=3, ambient_dim=5)
    assert r.ok
    assert len(r.result) == 5
    assert r.result[:3] == [1, 2, 3]

    # uniform_boundedness
    ops = [[[2, 0], [0, 1]], [[1, 0], [0, 3]], [[0.5, 0], [0, 0.5]]]
    r = uniform_boundedness(ops)
    assert r.ok
    assert r.result["uniformly_bounded"] is True

    # open_mapping
    r = open_mapping([[2, 0], [0, 3]])
    assert r.ok
    assert r.result == True

    # closed_graph
    r = closed_graph([[1, 0], [0, 1]])
    assert r.ok
    assert r.result == True

    return True


def test_spectral_theory() -> bool:
    """测试 spectral_theory 模块。"""
    from MF_Mathematics.functional_analysis.spectral_theory import (
        spectrum_approx,
        spectrum_classify,
        spectral_theorem,
    )

    # spectrum_approx
    r = spectrum_approx([[1, 2], [2, 1]])
    assert r.ok
    assert -1.0 in r.result or any(abs(x + 1) < 1e-10 for x in r.result)
    assert 3.0 in r.result or any(abs(x - 3) < 1e-10 for x in r.result)

    # spectrum_classify
    r = spectrum_classify([[1, 2], [2, 1]])
    assert r.ok
    assert "point_spectrum" in r.result

    # spectral_theorem
    r = spectral_theorem([[2, 0], [0, 2]])
    assert r.ok
    assert r.result["is_self_adjoint"] is True
    assert abs(r.result["reconstruction_error"]) < 1e-10

    # spectrum_approx 3x3
    r = spectrum_approx([[3, 0, 0], [0, 1, 0], [0, 0, 2]])
    assert r.ok
    assert sorted(r.result) == [1.0, 2.0, 3.0]

    return True


def test_dual_spaces() -> bool:
    """测试 dual_spaces 模块。"""
    from MF_Mathematics.functional_analysis.dual_spaces import (
        dual_space_basis,
        weak_convergence,
        is_reflexive,
    )

    # dual_space_basis
    r = dual_space_basis("R^n")
    assert r.ok
    dual = np.array(r.result)
    assert np.allclose(dual, np.eye(3))

    # dual_space_basis custom basis
    r = dual_space_basis([[2, 0], [0, 3]])
    assert r.ok
    dual = np.array(r.result)
    assert abs(dual[0][0] - 0.5) < 1e-10
    assert abs(dual[1][1] - 1.0 / 3.0) < 1e-10

    # weak_convergence
    seq = [[1.0 / (i + 1), 1.0 / (i + 1) ** 2] for i in range(30)]
    r = weak_convergence(seq, functional=[1, 0], limit=[0, 0], tol=0.1)
    assert r.ok

    # is_reflexive
    r = is_reflexive("R^n", dimension=10)
    assert r.ok
    assert r.result is True

    return True


def test_all() -> bool:
    """运行全部测试。"""
    modules = {
        "normed_spaces": test_normed_spaces,
        "inner_product_spaces": test_inner_product_spaces,
        "linear_operators": test_linear_operators,
        "core_theorems": test_core_theorems,
        "spectral_theory": test_spectral_theory,
        "dual_spaces": test_dual_spaces,
    }

    passed = 0
    total = len(modules)
    for name, test_fn in modules.items():
        try:
            test_fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")

    print(f"  Functional Analysis: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    ok = test_all()
    print(f"\nFunctional Analysis {'PASSED' if ok else 'FAILED'}")
