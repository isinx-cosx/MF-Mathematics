"""linear_operators.py — 线性算子与线性泛函。

涵盖算子范数计算、有界性/连续性判断、线性泛函求值、核的维数估计。
"""

from __future__ import annotations

from typing import Any, Callable, Sequence, Tuple, Union

import numpy as np
from scipy import linalg

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="functional_analysis", action="operator_norm")
def operator_norm(
    matrix: Sequence[Sequence[float]],
    p: Union[str, float] = 2,
) -> MathObject:
    """计算矩阵（线性算子）的算子范数。

    ‖T‖_p = sup_{‖x‖_p = 1} ‖Tx‖_p

    - p=2：最大奇异值（谱范数）
    - p=1：最大列和范数
    - p=∞ (inf)：最大行和范数
    - p='fro'：弗罗贝尼乌斯范数

    Args:
        matrix: 表示线性算子 T 的矩阵。
        p: 范数类型。2 为谱范数，1 为列和，'inf' 为行和，'fro' 为 Frobenius。

    Returns:
        MathObject: result 为算子范数值 (float)。
    """
    try:
        A = np.asarray(matrix, dtype=float)

        if isinstance(p, str):
            p_lower = p.lower()
            if p_lower in ("inf", "infty", "infinity"):
                # 最大行和范数
                result_val = float(np.max(np.sum(np.abs(A), axis=1)))
                norm_name = "行和范数 ‖T‖_∞"
            elif p_lower in ("fro", "frobenius"):
                result_val = float(np.sqrt(np.sum(A**2)))
                norm_name = "弗罗贝尼乌斯范数 ‖T‖_F"
            else:
                result_val = float(linalg.norm(A, ord=2))
                norm_name = "谱范数 ‖T‖_2 (最大奇异值)"
        elif p == 2:
            # 谱范数: 最大奇异值
            s = linalg.svdvals(A)
            result_val = float(s[0])
            norm_name = "谱范数 ‖T‖_2 (最大奇异值)"
        elif p == 1:
            result_val = float(np.max(np.sum(np.abs(A), axis=0)))
            norm_name = "列和范数 ‖T‖_1"
        else:
            # 回退到 scipy 的矩阵范数
            result_val = float(linalg.norm(A, ord=p))
            norm_name = f"‖T‖_{p} 范数"

        return MathObject(
            result=result_val,
            steps=[
                f"算子矩阵 = {A.tolist()}",
                f"范数类型: {norm_name}",
                f"算子范数 = {result_val}",
            ],
            meaning=f"线性算子 T 的 {norm_name} = {result_val}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="is_bounded")
def is_bounded(
    operator: Union[Sequence[Sequence[float]], Callable[[np.ndarray], np.ndarray]],
    domain: Tuple[float, float] = (-10, 10),
    n_samples: int = 50,
) -> MathObject:
    """判断线性算子是否有界（即连续）。

    有界性定义: 存在 M > 0 使得 ‖Tx‖ ≤ M‖x‖ 对所有 x 成立。
    数值方法: 采样单位球面上的 x，求 ‖Tx‖/‖x‖ 的上界估计。
    对矩阵算子：检查矩阵范数是否有限即自动有界。

    Args:
        operator: 算子矩阵或可调用对象（接受向量返回向量）。
        domain: 采样范围（当 operator 为函数时使用）。
        n_samples: 采样点数。

    Returns:
        MathObject: result 为 bool。
    """
    try:
        if isinstance(operator, (list, tuple, np.ndarray)):
            A = np.asarray(operator, dtype=float)
            op_norm = float(linalg.norm(A, ord=2))
            bounded = True if op_norm < 1e10 else False
            return MathObject(
                result=bounded,
                steps=[
                    f"矩阵算子 {A.shape[0]}×{A.shape[1]}",
                    f"算子范数 ‖T‖ = {op_norm:.4g}",
                    f"‖T‖ 有限 → 算子有界",
                ],
                meaning=f"矩阵算子的算子范数 = {op_norm:.4g}，{'有界（连续）' if bounded else '无界'}",
                data={"operator_norm": op_norm},
            )
        else:
            op_fn = operator
            # 在单位球面上采样
            max_ratio = 0.0
            for _ in range(n_samples):
                x = np.random.randn(2)  # 球面上均匀采样
                x_norm = np.linalg.norm(x)
                if x_norm > 1e-15:
                    x = x / x_norm
                    Tx = np.asarray(op_fn(x))
                    ratio = float(np.linalg.norm(Tx))
                    max_ratio = max(max_ratio, ratio)

            bounded = max_ratio < 1e8

            return MathObject(
                result=bounded,
                steps=[
                    f"采样 {n_samples} 个单位向量",
                    f"最大 ‖Tx‖/‖x‖ = {max_ratio:.4g}",
                ],
                meaning=f"{'有界（连续）' if bounded else '可能无界'}，上界估计 M ≈ {max_ratio:.4g}",
                data={"supremum_estimate": max_ratio},
            )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="linear_functional_eval")
def linear_functional_eval(
    func: Sequence[float],
    x: Sequence[float],
) -> MathObject:
    """求线性泛函的值。

    线性泛函 f: V → ℝ 由内积 f(x) = ⟨a, x⟩ 给出（Riesz 表示定理）。
    此处 func 是 Riesz 表示向量 a，返回 a^T x。

    Args:
        func: Riesz 表示向量 a（线性泛函的系数）。
        x: 自变量向量。

    Returns:
        MathObject: result 为泛函值 (float)。
    """
    try:
        a = np.asarray(func, dtype=float)
        x_vec = np.asarray(x, dtype=float)

        if a.shape != x_vec.shape:
            return MathObject(error=f"维度不匹配: func 维度 {a.shape}, x 维度 {x_vec.shape}")

        result_val = float(np.dot(a, x_vec))

        return MathObject(
            result=result_val,
            steps=[
                f"泛函表示向量 a = {a.tolist()}",
                f"自变量 x = {x_vec.tolist()}",
                f"f(x) = ⟨a, x⟩ = {result_val}",
            ],
            meaning=f"线性泛函值 f(x) = {result_val}",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="kernel_dimension")
def kernel_dimension(
    operator: Sequence[Sequence[float]],
    tol: float = 1e-10,
) -> MathObject:
    """计算线性算子的核（零空间）的维数（有限维近似）。

    ker(T) = {x | Tx = 0}。对于 m×n 矩阵，dim(ker(T)) = n - rank(T)。

    Args:
        operator: 表示线性算子 T 的矩阵。
        tol: 奇异值阈值，小于此值的奇异值视为零。

    Returns:
        MathObject: result 为核的维数 (int)，data 包含核的基向量。
    """
    try:
        A = np.asarray(operator, dtype=float)
        m, n = A.shape

        # 使用 SVD 计算秩
        s = linalg.svdvals(A)
        rank = int(np.sum(s > tol * max(s[0], 1.0)))
        dim_ker = n - rank

        # 计算核空间基向量
        kernel_basis = []
        if dim_ker > 0:
            # 通过 SVD 的右奇异向量获取零空间
            U, S, Vt = linalg.svd(A, full_matrices=True)
            # 对应零奇异值的 Vt 行
            for i in range(rank, n):
                kernel_basis.append(Vt[i, :].tolist())

        return MathObject(
            result=dim_ker,
            steps=[
                f"算子矩阵 {m}×{n}",
                f"奇异值: {[float(v) for v in s]}",
                f"数值秩 = {rank} (tol={tol})",
                f"dim(ker T) = n - rank = {n} - {rank} = {dim_ker}",
            ],
            meaning=f"核空间维数 = {dim_ker}{'，基向量见 data' if kernel_basis else ''}",
            data={
                "rank": rank,
                "kernel_basis": kernel_basis,
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 linear_operators 模块。"""
    print("=== linear_operators self_test ===")
    passed = 0
    total = 5

    # Test 1: operator_norm — [[2,0],[0,2]] 谱范数 = 2
    try:
        r = operator_norm([[2, 0], [0, 2]], p=2)
        assert r.ok
        assert abs(r.result - 2.0) < 1e-10, f"Expected 2, got {r.result}"
        print(f"  [PASS] operator_norm([[2,0],[0,2]], 2) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] operator_norm: {e}")

    # Test 2: operator_norm — 行和范数
    try:
        r = operator_norm([[1, 2], [3, 4]], p="inf")
        assert r.ok
        assert abs(r.result - 7.0) < 1e-10  # max row sum = max(3, 7) = 7
        print(f"  [PASS] operator_norm([[1,2],[3,4]], inf) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] operator_norm inf: {e}")

    # Test 3: is_bounded
    try:
        r = is_bounded([[2, 0], [0, 2]])
        assert r.ok
        assert r.result is True
        print(f"  [PASS] is_bounded([[2,0],[0,2]]) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] is_bounded: {e}")

    # Test 4: linear_functional_eval
    try:
        r = linear_functional_eval([1, 2, 3], [4, 5, 6])
        assert r.ok
        assert abs(r.result - 32.0) < 1e-10  # 1*4 + 2*5 + 3*6 = 32
        print(f"  [PASS] linear_functional_eval([1,2,3], [4,5,6]) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] linear_functional_eval: {e}")

    # Test 5: kernel_dimension
    try:
        # [[1,1],[1,1]] rank=1 → dim ker = 1
        r = kernel_dimension([[1, 1], [1, 1]])
        assert r.ok
        assert r.result == 1, f"Expected 1, got {r.result}"
        print(f"  [PASS] kernel_dimension([[1,1],[1,1]]) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] kernel_dimension: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
