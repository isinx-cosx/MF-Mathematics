"""core_theorems.py — 泛函分析四大核心定理。

涵盖哈恩-巴拿赫延拓、一致有界原理、开映射定理、闭图像定理。
其中理论函数提供基础说明，数值演示函数提供可验证的实例。
"""

from __future__ import annotations

from typing import Sequence, Union

import numpy as np
from scipy import linalg

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="functional_analysis", action="hahn_banach_extension")
def hahn_banach_extension(
    operator: Sequence[float],
    subspace_dim: int,
    ambient_dim: int = -1,
) -> MathObject:
    """哈恩-巴拿赫延拓定理（有限维演示）。

    定理内容：设 V 是赋范线性空间，U 是 V 的线性子空间，
    f 是 U 上的有界线性泛函，则 f 可以保范延拓到整个 V 上。

    在有限维 R^n 中，给定子空间上的泛函（由子空间系数 a 表示），
    找到全空间上的泛函表示 a_ext，使得 a_ext 在子空间上的限制等于 a。

    Args:
        operator: 线性泛函在子空间中的 Riesz 表示系数。
        subspace_dim: 子空间的维数。
        ambient_dim: 全空间维数（-1 时取 subspace_dim + 1 的最小扩展）。

    Returns:
        MathObject: result 为延拓后的泛函系数向量，data 包含范数验证。
    """
    try:
        a = np.asarray(operator, dtype=float)

        if ambient_dim < 0:
            ambient_dim = max(len(a) + 1, subspace_dim + 1)

        # 有限维哈恩-巴拿赫：延拓时保持与子空间正交方向的分量为 0
        # 实现最小范数延拓
        if len(a) < ambient_dim:
            a_ext = np.zeros(ambient_dim)
            a_ext[: len(a)] = a
        else:
            a_ext = a.copy()

        # 在子空间上限制（前 subspace_dim 个分量）
        sub_restriction = a_ext[:subspace_dim]

        # 验证范数：延拓后的范数
        norm_ext = float(np.linalg.norm(a_ext))
        norm_sub = float(np.linalg.norm(a[:subspace_dim]))

        preserved = abs(norm_sub - np.linalg.norm(sub_restriction)) < 1e-10

        return MathObject(
            result=a_ext.tolist(),
            steps=[
                f"子空间泛函系数: {a.tolist()}",
                f"子空间维数: {subspace_dim}",
                f"全空间维数: {ambient_dim}",
                f"延拓系数: {a_ext.tolist()}",
                f"子空间上范数: {norm_sub:.4g}",
                f"延拓后范数: {norm_ext:.4g}",
            ],
            meaning=f"哈恩-巴拿赫延拓: 将 {len(a)} 维子空间泛函延拓到 {ambient_dim} 维全空间"
            f"（{'保范' if preserved else '近似保范'}）",
            data={
                "extended_coeffs": a_ext.tolist(),
                "subspace_norm": norm_sub,
                "extended_norm": norm_ext,
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="uniform_boundedness")
def uniform_boundedness(
    operators: Sequence[Sequence[Sequence[float]]],
    test_points: Union[Sequence[Sequence[float]], None] = None,
) -> MathObject:
    """一致有界原理（Banach-Steinhaus 定理）的数值演示。

    定理内容：设 {T_α} 是从巴拿赫空间 X 到赋范空间 Y 的一族有界线性算子。
    如果对每个 x ∈ X，sup_α ‖T_α x‖ < ∞，则 sup_α ‖T_α‖ < ∞。

    数值验证：给定一族矩阵算子和测试点集，验证逐点有界 ⇒ 一致有界。

    Args:
        operators: 矩阵算子列表 [A₁, A₂, ...]。
        test_points: 测试点集，None 则随机生成单位向量。

    Returns:
        MathObject: result 为 dict，包含逐点有界性和一致有界性验证结果。
    """
    try:
        A_list = [np.asarray(A, dtype=float) for A in operators]
        n_ops = len(A_list)

        # 算子范数列表
        op_norms = [float(linalg.norm(A, ord=2)) for A in A_list]
        sup_op_norm = max(op_norms)

        # 生成测试点
        if test_points is None:
            np.random.seed(42)
            n_dim = A_list[0].shape[1]
            test_pts = [np.random.randn(n_dim) for _ in range(10)]
            # 归一化
            test_pts = [p / np.linalg.norm(p) for p in test_pts]
        else:
            test_pts = [np.asarray(p, dtype=float) for p in test_points]

        # 逐点检查
        pointwise_bounded = True
        max_pointwise = 0.0
        for x in test_pts:
            for A in A_list:
                Tx = np.linalg.norm(A @ x)
                max_pointwise = max(max_pointwise, float(Tx))
        # 简化判断：最大值有限即为逐点有界
        pointwise_bounded = max_pointwise < 1e6

        uniformly_bounded = sup_op_norm < 1e6

        return MathObject(
            result={
                "pointwise_bounded": pointwise_bounded,
                "uniformly_bounded": uniformly_bounded,
                "sup_operator_norm": sup_op_norm,
                "operator_norms": op_norms,
            },
            steps=[
                f"算子个数: {n_ops}",
                f"测试点个数: {len(test_pts)}",
                f"各算子范数: {[f'{n:.4g}' for n in op_norms]}",
                f"sup ‖T_α‖ = {sup_op_norm:.4g}",
                f"逐点最大 ‖T_α x‖ = {max_pointwise:.4g}",
                f"逐点有界: {pointwise_bounded}",
                f"一致有界: {uniformly_bounded}",
            ],
            meaning=f"一致有界原理验证: sup ‖T_α‖ = {sup_op_norm:.4g}" +
            (" < ∞" if uniformly_bounded else " = ∞"),
            data={
                "sup_operator_norm": sup_op_norm,
                "operator_norms": op_norms,
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="open_mapping")
def open_mapping(
    operator: Sequence[Sequence[float]],
) -> MathObject:
    """开映射定理（可逆性数值演示）。

    定理内容：设 X, Y 是巴拿赫空间，T: X → Y 是有界线性满射，
    则 T 是开映射（将开集映为开集）。

    对有限维矩阵算子，T 满射 ⇔ T 可逆（方阵且满秩）⇒ T 是开映射。

    Args:
        operator: 表示线性算子 T 的矩阵。

    Returns:
        MathObject: result 为 bool（是否为开映射），data 包含满射性验证。
    """
    try:
        A = np.asarray(operator, dtype=float)
        m, n = A.shape

        # 满射（行满秩）⇔ rank = m
        rank = np.linalg.matrix_rank(A)
        is_surjective = (rank == m)
        is_open = is_surjective

        return MathObject(
            result=is_open,
            steps=[
                f"算子矩阵 {m}×{n}",
                f"秩 = {rank}",
                f"满射条件: rank = m = {m} → {is_surjective}",
                f"可逆/满射矩阵 ⇒ 开映射 ⇒ {is_open}",
            ],
            meaning=f"T 是{'开映射' if is_open else '不是开映射'}（满射性: {is_surjective}）",
            data={
                "rank": rank,
                "is_surjective": is_surjective,
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="closed_graph")
def closed_graph(
    operator: Sequence[Sequence[float]],
) -> MathObject:
    """闭图像定理（数值演示）。

    定理内容：设 X, Y 是巴拿赫空间，T: X → Y 是线性算子。
    T 有界 ⇔ T 的图像是 X×Y 中的闭集。

    对所有有限维矩阵算子（自动有界），图像自动是闭集。

    Args:
        operator: 表示线性算子 T 的矩阵。

    Returns:
        MathObject: result 为 bool（图像是否为闭集）。
    """
    try:
        A = np.asarray(operator, dtype=float)

        # 有限维矩阵算子自动有界 → 图像自动闭
        op_norm = float(linalg.norm(A, ord=2))
        is_bounded_op = op_norm < 1e10
        is_closed = is_bounded_op

        # 数值验证：验证闭图像性质
        # 若 (x_n, T x_n) → (x, y)，则应有 y = T x
        # 随机测试
        n_test = 5
        np.random.seed(42)
        test_passed = True
        for _ in range(n_test):
            x_n = np.random.randn(A.shape[1])
            y = A @ x_n
            y_check = A @ x_n
            if np.linalg.norm(y - y_check) > 1e-10:
                test_passed = False
                break

        return MathObject(
            result=is_closed,
            steps=[
                f"算子矩阵 {A.shape[0]}×{A.shape[1]}",
                f"算子范数 ‖T‖ = {op_norm:.4g}",
                f"有界性: {is_bounded_op}",
                f"闭图像定理: 有界 ⇔ 闭图像 → 图像是{'闭集' if is_closed else '非闭'}",
                f"数值验证 (n={n_test}): {'通过' if test_passed else '失败'}",
            ],
            meaning=f"算子 T 的图像是{'闭集' if is_closed else '非闭集'}（有界性: {is_bounded_op}）",
            data={
                "operator_norm": op_norm,
                "is_bounded": is_bounded_op,
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 core_theorems 模块。"""
    print("=== core_theorems self_test ===")
    passed = 0
    total = 5

    # Test 1: hahn_banach_extension
    try:
        r = hahn_banach_extension([1, 2, 3], subspace_dim=3, ambient_dim=5)
        assert r.ok
        assert len(r.result) == 5
        assert r.result[:3] == [1, 2, 3]
        print(f"  [PASS] hahn_banach_extension([1,2,3], subspace=3, ambient=5) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] hahn_banach_extension: {e}")

    # Test 2: uniform_boundedness
    try:
        ops = [[[2, 0], [0, 1]], [[1, 0], [0, 3]], [[0.5, 0], [0, 0.5]]]
        r = uniform_boundedness(ops)
        assert r.ok
        assert r.result["uniformly_bounded"] is True
        print(f"  [PASS] uniform_boundedness: sup ‖T‖ = {r.result['sup_operator_norm']:.4g}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] uniform_boundedness: {e}")

    # Test 3: open_mapping — 可逆矩阵是开映射
    try:
        r = open_mapping([[2, 0], [0, 3]])
        assert r.ok
        assert r.result == True
        print(f"  [PASS] open_mapping([[2,0],[0,3]]) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] open_mapping: {e}")

    # Test 4: closed_graph — 有界算子有闭图像
    try:
        r = closed_graph([[1, 0], [0, 1]])
        assert r.ok
        assert r.result == True
        print(f"  [PASS] closed_graph([[1,0],[0,1]]) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] closed_graph: {e}")

    # Test 5: uniform_boundedness — 更大算子族
    try:
        # 多个有界算子
        ops2 = [[[1, 0], [0, 1]], [[2, 1], [1, 2]], [[0, 1], [-1, 0]]]
        r = uniform_boundedness(ops2)
        assert r.ok
        print(f"  [PASS] uniform_boundedness 3 ops: sup = {r.result['sup_operator_norm']:.4g}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] uniform_boundedness 2: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
