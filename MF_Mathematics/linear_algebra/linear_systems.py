"""线性方程组 — 高斯消元、秩、解的结构、基础解系。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_matrix(mat: Union[List[List[float]], np.ndarray, sp.Matrix]) -> sp.Matrix:
    """将各种矩阵表示统一转为 sympy Matrix。"""
    if isinstance(mat, sp.Matrix):
        return mat
    return sp.Matrix(mat)


def _to_vector(
    vec: Union[List[float], np.ndarray, sp.Matrix, None],
) -> sp.Matrix:
    """将向量统一转为 sympy 列向量。"""
    if vec is None:
        return sp.Matrix([])
    if isinstance(vec, sp.Matrix):
        return vec
    return sp.Matrix(vec)


@register(module="linear_algebra", action="gaussian_elimination")
def gaussian_elimination(
    matrix: Union[List[List[float]], np.ndarray],
    b: Union[List[float], np.ndarray, None] = None,
) -> MathObject:
    """对增广矩阵执行高斯消元法，返回阶梯形并判断解的结构。

    Args:
        matrix: 系数矩阵 A（m×n）。
        b: 右侧常数向量（可选，长度 m）。不传则视为齐次方程组。

    Returns:
        MathObject:
            - result: 包含解的结构信息 dict
                {"type": "unique"|"infinite"|"none", "solution": ...}
    """
    try:
        A = _to_matrix(matrix)
        m, n = A.rows, A.cols

        if b is not None:
            b_vec = sp.Matrix(b)
            if b_vec.rows == 1:
                b_vec = b_vec.T
            aug = A.row_join(b_vec)
        else:
            aug = A.row_join(sp.zeros(m, 1))

        # 获取行阶梯形
        rref, pivots = aug.rref()

        # 提取阶梯矩阵的系数部分和常数部分
        A_rref = rref[:, :n]
        b_rref = rref[:, n]

        # 找 A 的秩（只计算原矩阵列范围内的主元）
        r = sum(1 for p in pivots if p < n)

        # 判断是否有解：检查系数全零但常数非零的行
        for i in range(m):
            if A_rref.row(i).is_zero_matrix and abs(float(b_rref[i])) > 1e-12:
                return MathObject(
                    result={"type": "none", "solution": None},
                    steps=[
                        "构建增广矩阵 [A|b]",
                        f"增广矩阵:\n{aug}",
                        f"行阶梯形:\n{rref}",
                        f"第 {i+1} 行出现矛盾: 0 = {float(b_rref[i])}",
                    ],
                    meaning="方程组无解",
                )

        if r == n:
            # 唯一解
            sol = [float(b_rref[i]) for i in range(r)]
            return MathObject(
                result={"type": "unique", "solution": sol},
                steps=[
                    "构建增广矩阵 [A|b]",
                    f"增广矩阵:\n{aug}",
                    f"行阶梯形:\n{rref}",
                    f"秩 r(A) = r([A|b]) = {r} = 未知数个数 n = {n}",
                    "方程组有唯一解",
                ],
                meaning=f"唯一解: {sol}",
            )
        else:
            # 无穷多解
            sol = sp.linsolve((A, b_vec)) if b is not None else sp.linsolve((A, sp.zeros(m, 1)))

            return MathObject(
                result={
                    "type": "infinite",
                    "solution": str(sol),
                    "rank": r,
                    "free_vars": n - r,
                },
                steps=[
                    "构建增广矩阵 [A|b]",
                    f"增广矩阵:\n{aug}",
                    f"行阶梯形:\n{rref}",
                    f"秩 r(A) = r([A|b]) = {r} < n = {n}",
                    f"自由变量个数 = {n - r}",
                    "方程组有无穷多解",
                ],
                meaning=f"无穷多解，自由变量 {n - r} 个",
            )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="rank")
def rank(matrix: Union[List[List[float]], np.ndarray]) -> MathObject:
    """计算矩阵的秩。

    Args:
        matrix: 输入矩阵。

    Returns:
        MathObject，result 为秩（整数）。
    """
    try:
        A = _to_matrix(matrix)
        r = A.rank()
        return MathObject(
            result=int(r),
            steps=[
                f"矩阵:\n{A}",
                f"行阶梯形:\n{A.rref()[0]}",
                f"非零行数 = 秩 = {r}",
            ],
            meaning=f"矩阵的秩为 {r}，表示列空间/行空间的维数",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="solve_linear_system")
def solve_linear_system(
    A: Union[List[List[float]], np.ndarray],
    b: Union[List[float], np.ndarray, None] = None,
) -> MathObject:
    """求解线性方程组 Ax = b，自动判断齐次/非齐次及解的存在性。

    Args:
        A: 系数矩阵。
        b: 常数向量（不传则为齐次方程组）。

    Returns:
        MathObject，result 为解（唯一解则列表，无穷多解则参数化表达式）。
    """
    try:
        A_mat = _to_matrix(A)
        m, n = A_mat.rows, A_mat.cols

        if b is not None:
            b_vec = sp.Matrix(b)
            if b_vec.rows == 1:
                b_vec = b_vec.T
            sol = sp.linsolve((A_mat, b_vec))
            is_homogeneous = all(abs(float(v)) < 1e-15 for v in b_vec)
        else:
            b_vec = sp.zeros(m, 1)
            sol = sp.linsolve((A_mat, b_vec))
            is_homogeneous = True

        sol_list = list(sol) if sol else []

        if len(sol_list) == 0:
            return MathObject(
                result={"type": "none", "solution": None},
                steps=["方程组无解"],
                meaning="方程组无解",
            )

        # 判断解的类型
        has_param = any(len(v.free_symbols) > 0 for v in sol_list[0]) if sol_list else False

        if not has_param:
            result_vals = [float(v) for v in sol_list[0]]
            return MathObject(
                result={
                    "type": "unique",
                    "homogeneous": is_homogeneous,
                    "solution": result_vals,
                },
                steps=[
                    f"方程组: {A_mat} * x = {b_vec}",
                    f"齐次: {is_homogeneous}",
                    "求解得唯一解",
                ],
                meaning=f"唯一解: {result_vals}",
            )
        else:
            return MathObject(
                result={
                    "type": "infinite",
                    "homogeneous": is_homogeneous,
                    "solution": str(sol_list[0]),
                },
                steps=[
                    f"方程组: {A_mat} * x = {b_vec}",
                    f"齐次: {is_homogeneous}",
                    "有无穷多解，自由变量参数化",
                ],
                meaning=f"通解: {sol_list[0]}",
            )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="nullspace")
def nullspace(A: Union[List[List[float]], np.ndarray]) -> MathObject:
    """计算齐次方程组 Ax=0 的解空间（基础解系）。

    Args:
        A: 系数矩阵。

    Returns:
        MathObject，result 为基础解系向量列表。
    """
    try:
        A_mat = _to_matrix(A)
        ns = A_mat.nullspace()
        basis_vectors = [v.tolist() for v in ns]

        return MathObject(
            result={
                "basis": basis_vectors,
                "dimension": len(ns),
            },
            steps=[
                f"系数矩阵:\n{A_mat}",
                f"零空间维数 = n - rank(A) = {A_mat.cols - A_mat.rank()}",
                "基础解系:",
            ]
            + [f"  v{i+1} = {v}" for i, v in enumerate(basis_vectors)],
            meaning=f"零空间维数为 {len(ns)}，基础解系由 {len(ns)} 个线性无关向量构成",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> None:
    """模块自测。"""
    print("=== linear_systems self_test ===")

    # 1. 唯一解
    r1 = gaussian_elimination([[1, 2], [3, 4]], [5, 6])
    assert r1.ok, f"gaussian_elimination error: {r1.error}"
    assert r1.result["type"] == "unique", f"Expected unique, got {r1.result['type']}"
    print("  test1 (unique solution): PASSED")

    # 2. 无穷多解
    r2 = gaussian_elimination([[1, 2, 3], [2, 4, 6]], [5, 10])
    assert r2.ok, f"gaussian_elimination error: {r2.error}"
    assert r2.result["type"] == "infinite", f"Expected infinite, got {r2.result['type']}"
    print("  test2 (infinite solutions): PASSED")

    # 3. 无解
    r3 = gaussian_elimination([[1, 2], [2, 4]], [5, 11])
    assert r3.ok, f"gaussian_elimination error: {r3.error}"
    print(f"  test3 (no solution): type={r3.result['type']}")

    # 4. rank
    r4 = rank([[1, 2, 3], [2, 4, 6]])
    assert r4.ok, f"rank error: {r4.error}"
    assert r4.result == 1, f"Expected rank=1, got {r4.result}"
    print("  test4 (rank): PASSED")

    # 5. solve_linear_system
    r5 = solve_linear_system([[1, 0], [0, 1]], [3, 4])
    assert r5.ok, f"solve_linear_system error: {r5.error}"
    assert r5.result["solution"] == [3.0, 4.0]
    print("  test5 (solve): PASSED")

    # 6. nullspace
    r6 = nullspace([[1, 2, 3]])
    assert r6.ok, f"nullspace error: {r6.error}"
    assert r6.result["dimension"] == 2
    print("  test6 (nullspace): PASSED")

    print("=== linear_systems: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
