"""向量空间 — 线性组合、线性相关/无关、基与维数、子空间。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_vector_list(
    vectors: Union[List[List[float]], np.ndarray],
) -> List[sp.Matrix]:
    """将输入转换为 sympy 列向量列表。"""
    if isinstance(vectors, np.ndarray):
        vectors = vectors.tolist()
    return [sp.Matrix(v) for v in vectors]


def _to_matrix_from_vectors(vectors: List[sp.Matrix]) -> sp.Matrix:
    """将向量列表按列拼接为矩阵。"""
    if not vectors:
        return sp.Matrix([])
    return sp.Matrix.hstack(*vectors)


@register(module="linear_algebra", action="is_vector_space")
def is_vector_space(
    vectors: Union[List[List[float]], np.ndarray],
    operations: str = "standard",
) -> MathObject:
    """验证一组向量是否能构成向量空间（在标准运算下等同于判断是否为子空间）。

    在标准加法和标量乘法下，验证是否对加法和标量乘法封闭。
    此处简化：检查零向量是否属于该集合（必要非充分条件），
    以及集合是否对加法和标量乘法封闭。

    Args:
        vectors: 向量列表（R^n 中的一组向量）。
        operations: 运算类型，"standard" 为标准运算。

    Returns:
        MathObject，result 为 dict 包含各项公理验证结果。
    """
    try:
        vecs = _to_vector_list(vectors)
        if not vecs:
            return MathObject(result=False, meaning="空集合")

        n = vecs[0].rows

        # 检查所有向量是否同维
        for v in vecs:
            if v.rows != n:
                return MathObject(
                    result=False,
                    steps=["各向量维数不一致，不能构成向量空间"],
                    meaning="维数不一致",
                )

        # 检查零向量
        zero = sp.zeros(n, 1)
        has_zero = any(v == zero for v in vecs)

        # 检查加法封闭：对任意两向量之和
        closed_add = True
        add_counterexample = None
        for i, v1 in enumerate(vecs):
            for j, v2 in enumerate(vecs):
                if i <= j:
                    s = v1 + v2
                    if not any(s == v for v in vecs):
                        closed_add = False
                        add_counterexample = (v1, v2, s)
                        break
            if not closed_add:
                break

        # 检查标量乘法封闭（仅检查有限几个标量作为抽样）
        closed_scalar = True
        scalar_counterexample = None
        test_scalars = [-1, 2, 0.5]
        for v in vecs:
            for c in test_scalars:
                s = c * v
                if not any(s == w for w in vecs):
                    closed_scalar = False
                    scalar_counterexample = (c, v, s)
                    break
            if not closed_scalar:
                break

        is_vs = has_zero and closed_add and closed_scalar

        return MathObject(
            result={
                "is_vector_space": is_vs,
                "zero_vector": has_zero,
                "closed_under_addition": closed_add,
                "closed_under_scalar_multiplication": closed_scalar,
            },
            steps=[
                f"检查向量集合（{len(vecs)} 个向量）",
                f"零向量存在: {has_zero}",
                f"加法封闭: {closed_add}",
                f"标量乘法封闭: {closed_scalar}",
            ],
            meaning=(
                "该集合构成向量空间" if is_vs else "该集合不构成向量空间"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="linear_combination")
def linear_combination(
    vectors: Union[List[List[float]], np.ndarray],
    coeffs: List[float],
) -> MathObject:
    """计算向量组的线性组合。

    Args:
        vectors: 向量列表 [v1, v2, ..., vk]。
        coeffs: 系数列表 [c1, c2, ..., ck]。

    Returns:
        MathObject，result 为线性组合结果向量。
    """
    try:
        vecs = _to_vector_list(vectors)

        if len(vecs) != len(coeffs):
            return MathObject(
                error=f"向量的数量 ({len(vecs)}) 与系数的数量 ({len(coeffs)}) 不匹配"
            )

        result_vec = sp.zeros(vecs[0].rows, 1)
        steps = []
        for i, (v, c) in enumerate(zip(vecs, coeffs)):
            result_vec += c * v
            steps.append(f"  {c} * v{i+1} = {c} * {v.T}")

        return MathObject(
            result=result_vec.tolist(),
            steps=[
                f"计算线性组合: {' + '.join(f'{coeffs[i]}*v{i+1}' for i in range(len(coeffs)))}",
            ]
            + steps
            + [f"结果: {result_vec.tolist()}"],
            meaning=f"线性组合结果: {result_vec.tolist()}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="is_linear_independent")
def is_linear_independent(
    vectors: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """判断向量组是否线性无关。

    通过求向量组构成的矩阵的秩，若秩等于向量个数则为线性无关。

    Args:
        vectors: 向量列表，每个向量可以是行或列向量形式的列表。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        vecs = _to_vector_list(vectors)
        if not vecs:
            return MathObject(result=True, meaning="空向量组视为线性无关")

        k = len(vecs)
        M = _to_matrix_from_vectors(vecs)
        r = M.rank()
        is_independent = r == k

        return MathObject(
            result=is_independent,
            steps=[
                f"向量组包含 {k} 个向量",
                f"构成的矩阵:\n{M}",
                f"秩 = {r}，向量个数 = {k}",
                f"秩 == 向量个数: {is_independent}",
            ],
            meaning=(
                "向量组线性无关"
                if is_independent
                else f"向量组线性相关（秩 {r} < 向量数 {k}）"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="basis")
def basis(
    vectors: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """求向量组的一组基（返回极大线性无关组）。

    Args:
        vectors: 向量列表。

    Returns:
        MathObject，result 为基向量列表。
    """
    try:
        vecs = _to_vector_list(vectors)
        if not vecs:
            return MathObject(result=[], meaning="空向量组无基")

        M = _to_matrix_from_vectors(vecs)
        _, pivots = M.rref()
        basis_vectors = [vecs[p].tolist() for p in pivots]

        return MathObject(
            result={
                "basis": basis_vectors,
                "dimension": len(pivots),
            },
            steps=[
                f"原始向量组包含 {len(vecs)} 个向量",
                f"构成的矩阵:\n{M}",
                f"行阶梯形主元列: {pivots}",
                f"基向量为第 {'、'.join(str(p+1) for p in pivots)} 列",
            ],
            meaning=f"基包含 {len(pivots)} 个向量，维数为 {len(pivots)}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="dimension")
def dimension(
    vectors: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """计算向量组张成的子空间的维数。

    Args:
        vectors: 向量列表。

    Returns:
        MathObject，result 为维数（整数）。
    """
    try:
        vecs = _to_vector_list(vectors)
        if not vecs:
            return MathObject(result=0, meaning="空向量组维数为 0")

        M = _to_matrix_from_vectors(vecs)
        r = M.rank()

        return MathObject(
            result=int(r),
            steps=[
                f"向量组包含 {len(vecs)} 个向量",
                f"矩阵秩 = {r}",
            ],
            meaning=f"张成子空间的维数为 {r}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="subspace_span")
def subspace_span(
    vectors: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """求向量组生成的子空间 span(S)。

    Args:
        vectors: 向量列表。

    Returns:
        MathObject，result 包含生成子空间的基和维数。
    """
    try:
        vecs = _to_vector_list(vectors)
        if not vecs:
            return MathObject(
                result={"basis": [], "dimension": 0},
                meaning="空向量组生成的子空间为 {0}",
            )

        M = _to_matrix_from_vectors(vecs)
        _, pivots = M.rref()
        span_basis = [vecs[p].tolist() for p in pivots]
        dim_val = len(pivots)

        return MathObject(
            result={
                "span_basis": span_basis,
                "dimension": dim_val,
            },
            steps=[
                f"span(S) 由 {len(vecs)} 个向量生成",
                f"矩阵秩 = {dim_val}",
                f"生成子空间 span(S) 的一组基:",
            ]
            + [f"  {b}" for b in span_basis],
            meaning=f"span(S) 是 {dim_val} 维子空间",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> None:
    """模块自测。"""
    print("=== vector_spaces self_test ===")

    # 1. linear_combination
    r1 = linear_combination([[1, 0], [0, 1]], [3, 4])
    assert r1.ok, f"linear_combination error: {r1.error}"
    assert r1.result == [[3], [4]]
    print("  test1 (linear_combination): PASSED")

    # 2. is_linear_independent — 线性无关
    r2 = is_linear_independent([[1, 0], [0, 1]])
    assert r2.ok, f"is_linear_independent error: {r2.error}"
    assert r2.result is True, f"Expected True, got {r2.result}"
    print("  test2 (independent): PASSED")

    # 3. is_linear_independent — 线性相关
    r3 = is_linear_independent([[1, 2], [2, 4]])
    assert r3.ok, f"is_linear_independent error: {r3.error}"
    assert r3.result is False
    print("  test3 (dependent): PASSED")

    # 4. basis
    r4 = basis([[1, 0, 0], [0, 1, 0], [1, 1, 0]])
    assert r4.ok, f"basis error: {r4.error}"
    assert r4.result["dimension"] == 2
    print("  test4 (basis): PASSED")

    # 5. dimension
    r5 = dimension([[1, 2, 3], [2, 4, 6]])
    assert r5.ok, f"dimension error: {r5.error}"
    assert r5.result == 1
    print("  test5 (dimension): PASSED")

    # 6. is_vector_space — 标准 R^2 基向量
    r6 = is_vector_space([[1, 0], [0, 1], [1, 1], [0, 0]])
    assert r6.ok, f"is_vector_space error: {r6.error}"
    print("  test6 (is_vector_space): PASSED")

    # 7. subspace_span
    r7 = subspace_span([[1, 0, 0], [0, 1, 0]])
    assert r7.ok, f"subspace_span error: {r7.error}"
    assert r7.result["dimension"] == 2
    print("  test7 (subspace_span): PASSED")

    print("=== vector_spaces: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
