"""特征值与特征向量 — 特征多项式、对角化、若尔当标准型。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_matrix(mat: Union[List[List[float]], np.ndarray]) -> sp.Matrix:
    """统一转为 sympy Matrix。"""
    if isinstance(mat, sp.Matrix):
        return mat
    return sp.Matrix(mat)


@register(module="linear_algebra", action="eigenvalues")
def eigenvalues(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """计算矩阵的特征值。

    Args:
        matrix: 方阵。

    Returns:
        MathObject，result 为特征值列表（含重数）。
    """
    try:
        A = _to_matrix(matrix)
        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        eigvals = A.eigenvals()
        # eigvals 是一个 dict {eigenvalue: multiplicity}
        result_list = []
        for val, mult in eigvals.items():
            result_list.extend([val] * mult)

        # 尝试转为浮点数
        result_vals = []
        for v in result_list:
            try:
                result_vals.append(float(v))
            except (TypeError, ValueError):
                result_vals.append(v)

        return MathObject(
            result={
                "eigenvalues": result_vals,
                "with_multiplicity": [
                    {"value": k, "multiplicity": int(v)} for k, v in eigvals.items()
                ],
            },
            steps=[
                f"矩阵 A:\n{A}",
                f"特征值（含重数）: {result_vals}",
            ],
            meaning=f"矩阵的特征值为 {result_vals}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="eigenvectors")
def eigenvectors(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """计算矩阵的特征向量。

    Args:
        matrix: 方阵。

    Returns:
        MathObject，result 为 (特征值, 特征向量) 的配对列表。
    """
    try:
        A = _to_matrix(matrix)
        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        eigendata = A.eigenvects()
        # eigendata 是 [(特征值, 重数, [特征向量列表]), ...]

        result_pairs = []
        for val, mult, basis_vecs in eigendata:
            for vec in basis_vecs:
                result_pairs.append(
                    {
                        "eigenvalue": val,
                        "eigenvector": vec.tolist(),
                        "multiplicity": int(mult),
                    }
                )

        return MathObject(
            result={"eigenpairs": result_pairs},
            steps=[
                f"矩阵 A:\n{A}",
                f"求解 (A - λI) v = 0",
            ]
            + [
                f"  λ = {p['eigenvalue']}: v = {p['eigenvector']} (重数 {p['multiplicity']})"
                for p in result_pairs
            ],
            meaning=f"共有 {len(result_pairs)} 个特征向量（含重数）",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="characteristic_polynomial")
def characteristic_polynomial(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """计算矩阵的特征多项式 det(A - λI)。

    Args:
        matrix: 方阵。

    Returns:
        MathObject，result 为特征多项式表达式。
    """
    try:
        A = _to_matrix(matrix)
        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        lam = sp.Symbol("λ")
        I = sp.eye(A.rows)
        poly = (A - lam * I).det()
        poly_simplified = sp.simplify(poly)

        return MathObject(
            result=str(poly_simplified),
            steps=[
                f"矩阵 A:\n{A}",
                f"A - λI:\n{A - lam * I}",
                f"特征多项式 det(A - λI) = {poly_simplified}",
            ],
            meaning=f"特征多项式: {poly_simplified}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="is_diagonalizable")
def is_diagonalizable(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """判断矩阵是否可对角化。

    条件：特征向量的总数（几何重数之和）等于矩阵阶数。

    Args:
        matrix: 方阵。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        A = _to_matrix(matrix)
        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        n = A.rows
        eigendata = A.eigenvects()

        total_geom_multiplicity = sum(len(basis) for _, _, basis in eigendata)

        diag = total_geom_multiplicity == n

        return MathObject(
            result=diag,
            steps=[
                f"矩阵 A ({n}×{n}):\n{A}",
                f"特征向量总数（几何重数之和）= {total_geom_multiplicity}",
                f"矩阵阶数 = {n}",
                f"可对角化: {diag} "
                f"({'几何重数之和 == n' if diag else '几何重数之和 < n'})",
            ],
            meaning=(
                "矩阵可对角化" if diag
                else "矩阵不可对角化（几何重数不足）"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="diagonalize")
def diagonalize(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """若矩阵可对角化，返回 P 和 D 使得 A = PDP^{-1}。

    若不可对角化，提示并尝试给出若尔当标准型。

    Args:
        matrix: 方阵。

    Returns:
        MathObject，result 为 dict {"diagonalizable": bool, "P": ..., "D": ...}。
    """
    try:
        A = _to_matrix(matrix)
        if A.rows != A.cols:
            return MathObject(error="矩阵必须是方阵")

        n = A.rows
        eigendata = A.eigenvects()

        # 收集所有特征向量
        all_eigenvectors = []
        for val, mult, basis_vecs in eigendata:
            for vec in basis_vecs:
                all_eigenvectors.append(vec)

        total_geom = len(all_eigenvectors)

        if total_geom == n:
            # 可对角化
            P = sp.Matrix.hstack(*all_eigenvectors)
            D = sp.zeros(n, n)
            idx = 0
            for val, mult, basis_vecs in eigendata:
                for _ in range(len(basis_vecs)):
                    D[idx, idx] = val
                    idx += 1

            return MathObject(
                result={
                    "diagonalizable": True,
                    "P": P.tolist(),
                    "D": D.tolist(),
                },
                steps=[
                    f"矩阵 A:\n{A}",
                    "矩阵可对角化",
                    f"P (特征向量矩阵):\n{P}",
                    f"D (特征值对角矩阵):\n{D}",
                    "验证: P * D * P^{-1} = A",
                ],
                meaning=f"A = PDP⁻¹，D 的对角元素为特征值",
            )
        else:
            # 不可对角化 — 尝试 Jordan
            try:
                J = A.jordan_form()
                P_mat = J[0]  # 变换矩阵
                D_mat = J[1]  # Jordan 矩阵
                return MathObject(
                    result={
                        "diagonalizable": False,
                        "jordan_form": str(D_mat),
                        "P": P_mat.tolist() if P_mat else None,
                        "J": D_mat.tolist() if D_mat else None,
                    },
                    steps=[
                        f"矩阵 A:\n{A}",
                        f"几何重数之和 = {total_geom} < n = {n}，不可对角化",
                        f"若尔当标准型 J:\n{D_mat}",
                        "注: 此为简略形式，包含若尔当块",
                    ],
                    meaning="矩阵不可对角化，给出若尔当标准型",
                )
            except Exception:
                return MathObject(
                    result={
                        "diagonalizable": False,
                        "reason": "不可对角化（几何重数 < 代数重数），且若尔当计算失败",
                    },
                    steps=[
                        f"矩阵 A:\n{A}",
                        f"几何重数之和 = {total_geom} < n = {n}",
                        "不可对角化",
                    ],
                    meaning="矩阵不可对角化",
                )

    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> None:
    """模块自测。"""
    print("=== eigen self_test ===")

    # 1. eigenvalues — [[1,2],[2,1]] → [-1, 3]
    r1 = eigenvalues([[1, 2], [2, 1]])
    assert r1.ok, f"eigenvalues error: {r1.error}"
    vals = [v for v in r1.result["eigenvalues"] if isinstance(v, (int, float))]
    assert sorted(vals) == [-1.0, 3.0], f"Expected [-1, 3], got {vals}"
    print("  test1 (eigenvalues): PASSED")

    # 2. eigenvectors
    r2 = eigenvectors([[1, 2], [2, 1]])
    assert r2.ok, f"eigenvectors error: {r2.error}"
    assert len(r2.result["eigenpairs"]) >= 2
    print("  test2 (eigenvectors): PASSED")

    # 3. characteristic_polynomial
    r3 = characteristic_polynomial([[1, 2], [2, 1]])
    assert r3.ok, f"characteristic_polynomial error: {r3.error}"
    print("  test3 (characteristic_polynomial): PASSED")

    # 4. is_diagonalizable
    r4 = is_diagonalizable([[1, 0], [0, 2]])
    assert r4.ok, f"is_diagonalizable error: {r4.error}"
    assert r4.result is True
    print("  test4 (is_diagonalizable): PASSED")

    # 5. diagonalize
    r5 = diagonalize([[1, 0], [0, 2]])
    assert r5.ok, f"diagonalize error: {r5.error}"
    assert r5.result["diagonalizable"] is True
    print("  test5 (diagonalize): PASSED")

    print("=== eigen: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
