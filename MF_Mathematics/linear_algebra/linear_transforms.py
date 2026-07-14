"""线性变换 — 矩阵表示、核与像、秩-零化度定理。

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


def _to_vector(vec: Union[List[float], np.ndarray]) -> sp.Matrix:
    """统一转为 sympy 列向量。"""
    if isinstance(vec, sp.Matrix):
        return vec
    v = sp.Matrix(vec)
    if v.rows == 1:
        v = v.T
    return v


@register(module="linear_algebra", action="linear_transform")
def linear_transform(
    matrix: Union[List[List[float]], np.ndarray],
    vector: Union[List[float], np.ndarray],
) -> MathObject:
    """计算线性变换 T(v) = Av（矩阵作用于向量）。

    Args:
        matrix: 线性变换的表示矩阵 A。
        vector: 输入向量 v。

    Returns:
        MathObject，result 为变换后的向量。
    """
    try:
        A = _to_matrix(matrix)
        v = _to_vector(vector)
        result_vec = A * v

        return MathObject(
            result=result_vec.tolist(),
            steps=[
                f"变换矩阵 A:\n{A}",
                f"输入向量 v = {v.tolist()}",
                f"T(v) = A * v = {result_vec.tolist()}",
            ],
            meaning=f"线性变换结果: {result_vec.tolist()}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="matrix_representation")
def matrix_representation(
    transform: Union[List[List[float]], np.ndarray],
    domain_basis: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """求线性变换在给定基下的矩阵表示。

    对于标准基，直接返回变换矩阵。
    对于非标准基，计算变换矩阵在给定基下的坐标表示。

    Args:
        transform: 线性变换在标准基下的矩阵表示 T。
        domain_basis: 定义域的基（列向量列表）。

    Returns:
        MathObject，result 为给定基下的矩阵表示。
    """
    try:
        T = _to_matrix(transform)

        # 将基转为列向量列表
        if isinstance(domain_basis, np.ndarray):
            domain_basis = domain_basis.tolist()
        basis_vecs = [sp.Matrix(v) for v in domain_basis]

        # 如果基是标准基，直接返回原始变换矩阵
        n = T.cols
        is_standard = True
        for i, bv in enumerate(basis_vecs):
            expected = sp.zeros(n, 1)
            expected[i] = 1
            if bv != expected:
                is_standard = False
                break

        if is_standard:
            return MathObject(
                result={
                    "matrix": T.tolist(),
                    "is_standard_basis": True,
                },
                steps=[
                    "给定基为标准基",
                    f"矩阵表示即为原变换矩阵:\n{T}",
                ],
                meaning="在标准基下，线性变换的矩阵表示就是自身",
            )

        # 非标准基：T' = B^{-1} * T * B
        B = sp.Matrix.hstack(*basis_vecs)
        B_inv = B.inv()
        T_prime = B_inv * T * B

        return MathObject(
            result={
                "matrix": T_prime.tolist(),
                "is_standard_basis": False,
                "basis_matrix": B.tolist(),
            },
            steps=[
                f"基矩阵 B:\n{B}",
                f"B 的逆:\n{B_inv}",
                f"T' = B^{-1} * T * B =\n{T_prime}",
            ],
            meaning="在给定基下的线性变换矩阵表示",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="kernel")
def kernel(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """计算线性变换的核（零空间）Ker(T) = {v | Av = 0}。

    Args:
        matrix: 线性变换的矩阵表示。

    Returns:
        MathObject，result 包含核的基和维数。
    """
    try:
        A = _to_matrix(matrix)
        ns = A.nullspace()
        kernel_basis = [v.tolist() for v in ns]
        nullity = len(ns)

        return MathObject(
            result={
                "kernel_basis": kernel_basis,
                "nullity": nullity,
            },
            steps=[
                f"变换矩阵:\n{A}",
                f"求解齐次方程组 Av = 0",
                f"核的维数 (零化度) = {nullity}",
            ]
            + (
                [f"核的基:"] + [f"  {v}" for v in kernel_basis]
                if kernel_basis
                else ["核仅包含零向量"]
            ),
            meaning=f"Ker(T) 是 {nullity} 维子空间",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="image")
def image(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """计算线性变换的像（列空间）Im(T) = {Av : v in V}。

    Args:
        matrix: 线性变换的矩阵表示。

    Returns:
        MathObject，result 包含像的基和维数（即秩）。
    """
    try:
        A = _to_matrix(matrix)
        _, pivots = A.rref()
        image_basis = [A.col(p).tolist() for p in pivots]
        rank_val = len(pivots)

        return MathObject(
            result={
                "image_basis": image_basis,
                "rank": rank_val,
            },
            steps=[
                f"变换矩阵:\n{A}",
                f"行阶梯形主元列: {[p+1 for p in pivots]}",
                f"像的维数 (秩) = {rank_val}",
            ]
            + [f"像的基:"] + [f"  {v}" for v in image_basis],
            meaning=f"Im(T) 是 {rank_val} 维子空间，由矩阵的列空间张成",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="rank_nullity")
def rank_nullity(
    matrix: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """计算秩和零化度，验证秩-零化度定理 rank(T) + nullity(T) = dim(V)。

    Args:
        matrix: 线性变换的矩阵表示（m×n）。

    Returns:
        MathObject，result 为 (rank, nullity) 元组。
    """
    try:
        A = _to_matrix(matrix)
        n = A.cols
        r = A.rank()
        nullity = len(A.nullspace())
        theorem_holds = r + nullity == n

        return MathObject(
            result={
                "rank": int(r),
                "nullity": int(nullity),
                "domain_dim": n,
                "theorem_holds": theorem_holds,
            },
            steps=[
                f"矩阵 A ({A.rows}×{A.cols}):\n{A}",
                f"秩 rank(A) = {r}",
                f"零化度 nullity(A) = {nullity}",
                f"秩-零化度定理: rank + nullity = {r} + {nullity} = {r + nullity}",
                f"定义域维数 dim(V) = {n}",
                f"定理成立: {theorem_holds}",
            ],
            meaning=f"rank(T)={r}, nullity(T)={nullity}, rank+nullity=dim(V)={n}",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> None:
    """模块自测。"""
    print("=== linear_transforms self_test ===")

    # 1. linear_transform
    r1 = linear_transform([[2, 1], [0, 3]], [1, 2])
    assert r1.ok, f"linear_transform error: {r1.error}"
    assert r1.result == [[4], [6]]
    print("  test1 (linear_transform): PASSED")

    # 2. matrix_representation — 标准基
    r2 = matrix_representation([[1, 0], [0, 2]], [[1, 0], [0, 1]])
    assert r2.ok, f"matrix_representation error: {r2.error}"
    assert r2.result["is_standard_basis"] is True
    print("  test2 (matrix_representation standard): PASSED")

    # 3. kernel
    r3 = kernel([[1, 2, 3], [0, 0, 0]])
    assert r3.ok, f"kernel error: {r3.error}"
    print("  test3 (kernel): PASSED")

    # 4. image
    r4 = image([[1, 0], [0, 1]])
    assert r4.ok, f"image error: {r4.error}"
    assert r4.result["rank"] == 2
    print("  test4 (image): PASSED")

    # 5. rank_nullity
    r5 = rank_nullity([[1, 2, 3], [4, 5, 6]])
    assert r5.ok, f"rank_nullity error: {r5.error}"
    assert r5.result["theorem_holds"] is True
    print("  test5 (rank_nullity): PASSED")

    print("=== linear_transforms: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
