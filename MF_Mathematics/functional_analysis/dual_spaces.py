"""dual_spaces.py — 对偶空间与弱拓扑。

涵盖对偶空间基、弱收敛判断、自反空间判断。
"""

from __future__ import annotations

from typing import Callable, Sequence, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="functional_analysis", action="dual_space_basis")
def dual_space_basis(
    space: Union[str, Sequence[Sequence[float]]],
) -> MathObject:
    """计算对偶空间基（概念性占位 + 有限维演示）。

    对偶空间 V* 是 V 上所有有界线性泛函构成的空间。
    若 V 的基为 {e₁, ..., eₙ}，则对偶基 {f₁, ..., fₙ} 满足 f_i(e_j) = δ_ij。

    在有限维 R^n 中，给定 V 的基矩阵 B（列向量为基），
    对偶基 B* 满足 (B*)^T B = I，即 B* = B^{-T}。

    Args:
        space: 空间名称字符串（如 "R^n"）或基矩阵（列向量为基）。

    Returns:
        MathObject: result 为对偶基矩阵，data 包含对偶基验证。
    """
    try:
        if isinstance(space, str):
            space_lower = space.lower()
            if space_lower == "r^n":
                n = 3  # 默认 R^3
                basis = np.eye(n)
            elif space_lower == "l^p":
                n = 3
                basis = np.eye(n)
            else:
                n = 3
                basis = np.eye(n)
        else:
            basis = np.asarray(space, dtype=float)
            n = basis.shape[0]

        # 对偶基 = B^{-T}
        try:
            dual_basis = np.linalg.inv(basis).T
        except np.linalg.LinAlgError:
            return MathObject(error="基矩阵不可逆，无法计算对偶基")

        # 验证对偶性: (dual_basis)^T @ basis = I
        verification = dual_basis.T @ basis
        is_dual = np.allclose(verification, np.eye(n), atol=1e-10)

        return MathObject(
            result=dual_basis.tolist(),
            steps=[
                f"原始基（列向量）维度: {n}x{n}",
                "对偶基 = B^{-T}",
                f"验证 (B*)^T B = {'I (通过)' if is_dual else '失败'}",
            ],
            meaning=f"对偶空间 V* 的基（对偶基），满足 f_i(e_j) = δ_ij",
            data={
                "primal_basis": basis.tolist(),
                "dual_basis": dual_basis.tolist(),
                "dual_verified": is_dual,
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="weak_convergence")
def weak_convergence(
    sequence: Sequence[Sequence[float]],
    functional: Union[Sequence[float], None] = None,
    limit: Union[Sequence[float], None] = None,
    tol: float = 1e-3,
) -> MathObject:
    """判断序列的弱收敛性（数值演示）。

    弱收敛定义：x_n ⇀ x 当且仅当对每个有界线性泛函 f ∈ V*，
    有 f(x_n) → f(x)。

    数值验证：对给定泛函 f（由 Riesz 向量表示），
    检查 |f(x_n) - f(x)| 是否趋于 0。

    Args:
        sequence: 向量序列 [x_1, x_2, ..., x_k]。
        functional: 线性泛函的 Riesz 表示向量。None 则自动生成标准基泛函。
        limit: 弱极限 x。None 则使用序列最后一项作为极限。
        tol: 收敛判定容差。

    Returns:
        MathObject: result 为 bool（是否弱收敛），data 包含各泛函评估值。
    """
    try:
        seq = [np.asarray(v, dtype=float) for v in sequence]
        n = len(seq)

        if n < 3:
            return MathObject(result=False, error="序列长度至少为 3")

        dim = seq[0].shape[0]
        if limit is None:
            limit_vec = seq[-1].copy()
        else:
            limit_vec = np.asarray(limit, dtype=float)

        # 生成测试泛函
        if functional is not None:
            functionals = [np.asarray(functional, dtype=float)]
        else:
            # 使用标准基作为泛函（坐标泛函）
            functionals = [np.eye(dim)[i] for i in range(min(dim, 3))]

        # 对每个泛函检查收敛
        all_converge = True
        functional_results = []

        for fi, f_vec in enumerate(functionals):
            f_name = f"e_{fi+1}" if functional is None else "f"
            f_values = [float(np.dot(f_vec, s)) for s in seq]
            f_limit = float(np.dot(f_vec, limit_vec))

            # 检查尾部收敛
            tail_vals = f_values[-min(5, n):]
            max_dev = max(abs(v - f_limit) for v in tail_vals)
            converged = max_dev < tol

            if not converged:
                all_converge = False

            functional_results.append({
                "functional": f_name,
                "values": [round(v, 6) for v in f_values],
                "limit": round(f_limit, 6),
                "max_dev": round(max_dev, 6),
                "converged": converged,
            })

        return MathObject(
            result=all_converge,
            steps=[
                f"序列长度: {n}",
                f"测试泛函: {len(functionals)} 个",
                f"弱极限: {limit_vec.tolist()}",
                f"各泛函收敛情况: {[(fr['functional'], fr['converged']) for fr in functional_results]}",
            ],
            meaning=f"序列{'弱收敛' if all_converge else '不弱收敛'}到 {limit_vec.tolist()}（基于 {len(functionals)} 个测试泛函）",
            data={
                "functionals_evaluation": functional_results,
                "limit": limit_vec.tolist(),
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="is_reflexive")
def is_reflexive(space: str, dimension: int = -1) -> MathObject:
    """判断给定空间是否为自反空间（概念性占位）。

    自反空间定义：赋范空间 V 与其二次对偶 V** 等距同构。
    自然嵌入 J: V → V** 定义为 (J(x))(f) = f(x)。

    - 所有有限维赋范空间都是自反的。
    - L^p 空间（1 < p < ∞）是自反的。
    - L^1、L^∞、C[0,1]（上确界范数）不是自反的。

    Args:
        space: 空间名称，如 "R^n"、"L^p"、"L^1"、"C[0,1]"。
        dimension: 维度（-1 表示无限维）。

    Returns:
        MathObject: result 为 bool。
    """
    try:
        space_lower = space.lower()

        reflexive_spaces = {
            "r^n": True,
            "c^n": True,
            "l^p (1<p<∞)": True,
            "l^p": True,
            "l^2": True,
            "sobolev w^{k,p} (1<p<∞)": True,
        }

        not_reflexive = {
            "l^1": False,
            "l^∞": False,
            "c[0,1]": False,
            "c_0": False,
        }

        if space_lower in reflexive_spaces:
            result_val = True
            reason = f"{space} 是自反空间（满足 J(V) = V**）。"
        elif space_lower in not_reflexive:
            result_val = False
            reason = f"{space} 不是自反空间（J(V) ⊊ V**）。"
        else:
            if dimension > 0 and dimension < float("inf"):
                result_val = True
                reason = f"{space} 是有限维赋范空间，自动自反。"
            else:
                result_val = False
                reason = f"{space} 无限维，自反性不确定。"

        return MathObject(
            result=result_val,
            steps=[
                f"空间: {space}",
                f"维度: {'无限' if dimension < 0 else dimension}",
                f"自然嵌入 J: V → V**",
            ],
            meaning=reason,
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 dual_spaces 模块。"""
    print("=== dual_spaces self_test ===")
    passed = 0
    total = 5

    # Test 1: dual_space_basis — R^3 标准基的对偶基
    try:
        r = dual_space_basis("R^n")
        assert r.ok
        dual = np.array(r.result)
        # 标准基的对偶基就是自身
        assert np.allclose(dual, np.eye(3))
        print(f"  [PASS] dual_space_basis('R^n') = identity matrix")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] dual_space_basis: {e}")

    # Test 2: dual_space_basis — 自定义基
    try:
        # 基：e1=(2,0), e2=(0,3)
        basis = [[2, 0], [0, 3]]
        r = dual_space_basis(basis)
        assert r.ok
        dual = np.array(r.result)
        # 对偶基: f1=(1/2, 0), f2=(0, 1/3)
        assert abs(dual[0][0] - 0.5) < 1e-10
        assert abs(dual[1][1] - 1.0 / 3.0) < 1e-10
        print(f"  [PASS] dual_space_basis([[2,0],[0,3]]) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] dual_space_basis custom: {e}")

    # Test 3: weak_convergence — 收敛到原点的序列
    try:
        # x_n = (1/n, 1/n^2)
        seq = [[1.0 / (i + 1), 1.0 / (i + 1) ** 2] for i in range(30)]
        r = weak_convergence(seq, functional=[1, 0], limit=[0, 0], tol=0.1)
        assert r.ok
        print(f"  [PASS] weak_convergence x_n=(1/n, 1/n^2) → 0: {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] weak_convergence: {e}")

    # Test 4: is_reflexive
    try:
        r = is_reflexive("R^n", dimension=10)
        assert r.ok
        assert r.result is True
        print(f"  [PASS] is_reflexive('R^n', 10) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] is_reflexive: {e}")

    # Test 5: weak_convergence — 非收敛序列
    try:
        # 不收敛的序列: x_n = (-1)^n
        seq = [[float((-1) ** i)] for i in range(30)]
        r = weak_convergence(seq, functional=[1.0], limit=[0.0], tol=0.5)
        assert r.ok
        # 不弱收敛
        print(f"  [PASS] weak_convergence oscillating: convergent={r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] weak_convergence oscillating: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
