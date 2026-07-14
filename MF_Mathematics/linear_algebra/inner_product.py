"""内积与正交 — 点积、范数、夹角、正交、格拉姆-施密特、正交投影。

依赖: sympy, numpy
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

import numpy as np
import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_vector(vec: Union[List[float], np.ndarray]) -> sp.Matrix:
    """统一转为 sympy 列向量。"""
    if isinstance(vec, sp.Matrix):
        return vec
    v = sp.Matrix(vec)
    if v.rows == 1 and v.cols > 1:
        v = v.T
    return v


@register(module="linear_algebra", action="dot")
def dot(
    u: Union[List[float], np.ndarray],
    v: Union[List[float], np.ndarray],
) -> MathObject:
    """计算两个向量的标准点积（内积）。

    Args:
        u: 第一个向量。
        v: 第二个向量。

    Returns:
        MathObject，result 为点积数值。
    """
    try:
        u_vec = _to_vector(u)
        v_vec = _to_vector(v)

        if u_vec.rows != v_vec.rows:
            return MathObject(error=f"向量维数不一致: {u_vec.rows} vs {v_vec.rows}")

        result_val = u_vec.dot(v_vec)

        return MathObject(
            result=float(result_val) if result_val.is_Float or result_val.is_Integer or result_val.is_Rational else str(result_val),
            steps=[
                f"u = {u_vec.tolist()}",
                f"v = {v_vec.tolist()}",
                f"u · v = {result_val}",
            ],
            meaning=f"点积 u·v = {result_val}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="norm")
def norm(
    vector: Union[List[float], np.ndarray],
) -> MathObject:
    """计算向量的欧氏模长（2-范数）。

    Args:
        vector: 输入向量。

    Returns:
        MathObject，result 为模长。
    """
    try:
        v = _to_vector(vector)
        n = v.norm()

        return MathObject(
            result=float(n) if n.is_Float or n.is_Integer or n.is_Rational else str(n),
            steps=[
                f"向量 v = {v.tolist()}",
                f"||v|| = sqrt(v·v) = {n}",
            ],
            meaning=f"向量的欧氏长度为 {n}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="angle")
def angle(
    u: Union[List[float], np.ndarray],
    v: Union[List[float], np.ndarray],
) -> MathObject:
    """计算两个向量之间的夹角。

    Args:
        u: 第一个向量。
        v: 第二个向量。

    Returns:
        MathObject，result 包含弧度值和角度值。
    """
    try:
        u_vec = _to_vector(u)
        v_vec = _to_vector(v)

        if u_vec.rows != v_vec.rows:
            return MathObject(error=f"向量维数不一致: {u_vec.rows} vs {v_vec.rows}")

        dot_val = float(u_vec.dot(v_vec))
        norm_u = float(u_vec.norm())
        norm_v = float(v_vec.norm())

        if abs(norm_u) < 1e-15 or abs(norm_v) < 1e-15:
            return MathObject(error="零向量无法计算夹角")

        cos_theta = dot_val / (norm_u * norm_v)
        cos_theta = max(-1.0, min(1.0, cos_theta))  # 数值精度修正
        rad = np.arccos(cos_theta)
        deg = np.degrees(rad)

        return MathObject(
            result={
                "radians": rad,
                "degrees": deg,
                "cos_theta": cos_theta,
            },
            steps=[
                f"u = {u_vec.tolist()}",
                f"v = {v_vec.tolist()}",
                f"u · v = {dot_val}",
                f"||u|| = {norm_u}, ||v|| = {norm_v}",
                f"cos θ = (u·v) / (||u||·||v||) = {cos_theta}",
                f"θ = {rad} rad = {deg}°",
            ],
            meaning=f"向量 u 和 v 的夹角为 {deg:.2f}°",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="is_orthogonal")
def is_orthogonal(
    u: Union[List[float], np.ndarray],
    v: Union[List[float], np.ndarray],
) -> MathObject:
    """判断两个向量是否正交。

    Args:
        u: 第一个向量。
        v: 第二个向量。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        u_vec = _to_vector(u)
        v_vec = _to_vector(v)

        if u_vec.rows != v_vec.rows:
            return MathObject(error=f"向量维数不一致: {u_vec.rows} vs {v_vec.rows}")

        dot_val = abs(float(u_vec.dot(v_vec)))
        is_orth = dot_val < 1e-12

        return MathObject(
            result=is_orth,
            steps=[
                f"u = {u_vec.tolist()}",
                f"v = {v_vec.tolist()}",
                f"u · v = {float(u_vec.dot(v_vec))}",
                f"正交: {is_orth} (点积是否 ≈ 0)",
            ],
            meaning=(
                "两向量正交（垂直）" if is_orth else "两向量非正交"
            ),
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="gram_schmidt")
def gram_schmidt(
    vectors: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """对向量组执行格拉姆-施密特正交化，返回标准正交基。

    Args:
        vectors: 线性无关的向量列表。

    Returns:
        MathObject，result 为标准正交基向量列表。
    """
    try:
        if isinstance(vectors, np.ndarray):
            vectors = vectors.tolist()
        vecs = [sp.Matrix(v) for v in vectors]

        if not vecs:
            return MathObject(result=[], meaning="空向量组")

        orthonormal_basis = []

        for i, v in enumerate(vecs):
            w = v
            for u in orthonormal_basis:
                proj = (v.dot(u)) * u
                w = w - proj
            w_norm = w.norm()
            if abs(float(w_norm)) < 1e-15:
                continue  # 跳过零向量
            e = w / w_norm
            orthonormal_basis.append(e)

        result_vectors = [e.tolist() for e in orthonormal_basis]

        return MathObject(
            result={
                "orthonormal_basis": result_vectors,
                "size": len(result_vectors),
            },
            steps=[
                f"输入向量组包含 {len(vecs)} 个向量",
                "执行格拉姆-施密特正交化:",
            ]
            + [
                f"  e{i+1} = {v}"
                for i, v in enumerate(result_vectors)
            ],
            meaning=f"标准正交基包含 {len(result_vectors)} 个两两正交的单位向量",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="linear_algebra", action="orthogonal_projection")
def orthogonal_projection(
    vector: Union[List[float], np.ndarray],
    basis: Union[List[List[float]], np.ndarray],
) -> MathObject:
    """计算向量在给定基（假设为标准正交基）张成的子空间上的正交投影。

    若基为标准正交基，投影 = Σ (v · e_i) e_i。
    若基未必正交，先通过 Gram-Schmidt 正交化。

    Args:
        vector: 待投影的向量。
        basis: 子空间的基向量列表。

    Returns:
        MathObject，result 为投影向量。
    """
    try:
        v = _to_vector(vector)

        if isinstance(basis, np.ndarray):
            basis = basis.tolist()
        basis_vecs = [sp.Matrix(b) for b in basis]

        if not basis_vecs:
            return MathObject(result=v.tolist(), meaning="空基，投影即自身")

        # 对基做 Gram-Schmidt 正交化
        ortho_basis = []
        for bi in basis_vecs:
            w = bi
            for u in ortho_basis:
                proj = (bi.dot(u)) * u
                w = w - proj
            w_norm = w.norm()
            if abs(float(w_norm)) > 1e-15:
                ortho_basis.append(w / w_norm)

        # 投影
        proj_vec = sp.zeros(v.rows, 1)
        for e in ortho_basis:
            proj_vec += (v.dot(e)) * e

        return MathObject(
            result=proj_vec.tolist(),
            steps=[
                f"向量 v = {v.tolist()}",
                f"子空间标准正交基: {[e.tolist() for e in ortho_basis]}",
                f"正交投影: proj(v) = Σ(v·e_i) e_i = {proj_vec.tolist()}",
            ],
            meaning=f"向量在子空间上的正交投影为 {proj_vec.tolist()}",
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> None:
    """模块自测。"""
    print("=== inner_product self_test ===")

    # 1. dot
    r1 = dot([1, 2, 3], [4, 5, 6])
    assert r1.ok, f"dot error: {r1.error}"
    assert abs(r1.result - 32.0) < 1e-9
    print("  test1 (dot): PASSED")

    # 2. norm
    r2 = norm([3, 4])
    assert r2.ok, f"norm error: {r2.error}"
    assert abs(r2.result - 5.0) < 1e-9
    print("  test2 (norm): PASSED")

    # 3. angle
    r3 = angle([1, 0], [0, 1])
    assert r3.ok, f"angle error: {r3.error}"
    assert abs(r3.result["degrees"] - 90.0) < 0.01
    print("  test3 (angle): PASSED")

    # 4. is_orthogonal
    r4 = is_orthogonal([1, 0], [0, 1])
    assert r4.ok, f"is_orthogonal error: {r4.error}"
    assert r4.result is True
    print("  test4 (orthogonal): PASSED")

    # 5. gram_schmidt
    r5 = gram_schmidt([[1, 1], [1, 0]])
    assert r5.ok, f"gram_schmidt error: {r5.error}"
    assert r5.result["size"] == 2
    print("  test5 (gram_schmidt): PASSED")

    # 6. orthogonal_projection
    r6 = orthogonal_projection([1, 2, 3], [[1, 0, 0], [0, 1, 0]])
    assert r6.ok, f"orthogonal_projection error: {r6.error}"
    print("  test6 (orthogonal_projection): PASSED")

    print("=== inner_product: ALL PASSED ===\n")


if __name__ == "__main__":
    self_test()
