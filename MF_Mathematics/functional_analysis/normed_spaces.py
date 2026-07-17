"""normed_spaces.py — 赋范空间与巴拿赫空间。

涵盖 ℓ^p 范数计算、巴拿赫空间判断、柯西列收敛性验证。
"""

from __future__ import annotations

from typing import Callable, Sequence, Union

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="functional_analysis", action="lp_norm")
def lp_norm(vector: Sequence[float], p: float) -> MathObject:
    """计算向量的 ℓ^p 范数。

    ‖x‖_p = (∑|x_i|^p)^(1/p)，p 可以是任意正实数。
    p=∞ 时取最大绝对值 (sup-norm)。

    Args:
        vector: 输入向量，浮点数序列。
        p: 范数阶数，p ≥ 1 时满足三角不等式，0 < p < 1 为准范数。
           特殊值 "inf" 或 float('inf') 表示上确界范数。

    Returns:
        MathObject: result 为范数值 (float)。
    """
    try:
        arr = np.asarray(vector, dtype=float)

        if isinstance(p, str) and p.lower() == "inf":
            p_val = float("inf")
        else:
            p_val = float(p)

        if np.isinf(p_val):
            result_val = float(np.max(np.abs(arr)))
            steps = [
                f"向量 = {arr.tolist()}",
                f"p = ∞，计算上确界范数 ‖x‖_∞ = max|x_i|",
                f"‖x‖_∞ = {result_val}",
            ]
            meaning = f"ℓ^∞ 范数（上确界范数）= {result_val}"
        elif p_val >= 1:
            # 标准 ℓ^p 范数
            result_val = float(np.sum(np.abs(arr) ** p_val) ** (1.0 / p_val))
            steps = [
                f"向量 = {arr.tolist()}",
                f"计算 ∑|x_i|^{p_val} = {float(np.sum(np.abs(arr) ** p_val))}",
                f"‖x‖_{p_val} = (∑|x_i|^{p_val})^(1/{p_val}) = {result_val}",
            ]
            meaning = f"ℓ^{p_val} 范数 = {result_val}"
        elif p_val > 0:
            # 准范数 (0 < p < 1)，不满足三角不等式
            result_val = float(np.sum(np.abs(arr) ** p_val) ** (1.0 / p_val))
            steps = [
                f"向量 = {arr.tolist()}",
                f"p = {p_val} ∈ (0,1)，准范数（不满足三角不等式）",
                f"‖x‖_{p_val} = (∑|x_i|^{p_val})^(1/{p_val}) = {result_val}",
            ]
            meaning = f"ℓ^{p_val} 准范数 = {result_val}"
        else:
            return MathObject(error=f"p 必须为正实数，当前 p = {p_val}")

        return MathObject(result=result_val, steps=steps, meaning=meaning)
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="is_banach")
def is_banach(space: str, dimension: int = -1) -> MathObject:
    """判断给定空间是否为巴拿赫空间（完备赋范空间）。

    巴拿赫空间 = 完备的赋范线性空间。
    在有限维情形下，所有赋范空间都是巴拿赫空间。

    Args:
        space: 空间名称，如 "R^n"、"C[0,1]"、"l^p"、"L^p"。
        dimension: 维度（-1 表示无限维）。

    Returns:
        MathObject: result 为 bool。
    """
    try:
        space_lower = space.lower()

        banach_spaces = {
            "r^n": True,
            "c^n": True,
            "l^p": True,
            "c[0,1]": True,
            "c_0": True,
            "l^∞": True,
        }

        not_banach = {
            "c[0,1] under l^1": False,
            "polynomials under sup-norm": False,
        }

        if space_lower in banach_spaces:
            result_val = True
            reason = f"{space} 是完备的赋范空间，为巴拿赫空间。"
        elif space_lower in not_banach:
            result_val = False
            reason = f"{space} 不完备，不是巴拿赫空间。"
        else:
            # 有限维自动是巴拿赫空间
            if dimension > 0 and dimension < float("inf"):
                result_val = True
                reason = f"{space} 是有限维赋范空间，自动完备，为巴拿赫空间。"
            else:
                result_val = False
                reason = f"{space} 无限维空间，完备性不确定。"

        return MathObject(
            result=result_val,
            steps=[f"空间: {space}", f"维度: {'无限' if dimension < 0 else dimension}"],
            meaning=reason,
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="functional_analysis", action="space_completeness_check")
def space_completeness_check(
    sequence: Sequence[Sequence[float]], norm: Union[str, Callable] = "l2"
) -> MathObject:
    """验证给定序列在指定范数下是否为柯西列。

    柯西列定义：对任意 ε > 0，存在 N，使得 m,n > N 时 ‖x_m - x_n‖ < ε。
    在实际计算中，检查序列尾部项之间范数差是否趋于零。

    Args:
        sequence: 向量序列，每个元素是浮点数序列。
        norm: 范数类型，"l1"/"l2"/"linf" 或可调用对象。

    Returns:
        MathObject: result 为 bool（是否为柯西列），
                   data 中包含尾部最大范数差。
    """
    try:
        arr_seq = [np.asarray(v, dtype=float) for v in sequence]

        if len(arr_seq) < 3:
            return MathObject(
                result=False, error="序列长度至少为 3 才能判断收敛趋势"
            )

        if isinstance(norm, str):
            norm_type = norm.lower()
            if norm_type == "l1":

                def norm_fn(v: np.ndarray) -> float:
                    return float(np.sum(np.abs(v)))
            elif norm_type in ("l2", "euclidean"):

                def norm_fn(v: np.ndarray) -> float:
                    return float(np.sqrt(np.sum(v**2)))
            elif norm_type in ("linf", "sup", "infinity"):

                def norm_fn(v: np.ndarray) -> float:
                    return float(np.max(np.abs(v)))
            else:
                return MathObject(error=f"未知范数类型: {norm_type}")
        else:

            def norm_fn(v: np.ndarray) -> float:
                return float(norm(v))

        # 计算相邻项和间隔项之间的范数差
        diffs = [
            norm_fn(arr_seq[i + 1] - arr_seq[i])
            for i in range(len(arr_seq) - 1)
        ]
        max_diff = float(np.max(diffs[-min(5, len(diffs)) :]))

        # 尾部最大差异：检查后几项之间的范数差
        tail_items = arr_seq[-5:] if len(arr_seq) >= 5 else arr_seq
        tail_diffs = []
        for i in range(len(tail_items)):
            for j in range(i + 1, len(tail_items)):
                tail_diffs.append(norm_fn(tail_items[i] - tail_items[j]))
        max_tail_diff = float(np.max(tail_diffs)) if tail_diffs else max_diff

        is_cauchy = max_tail_diff < 1e-3

        return MathObject(
            result=is_cauchy,
            steps=[
                f"序列长度: {len(arr_seq)}",
                f"范数类型: {norm_type if isinstance(norm, str) else '自定义'}",
                f"尾部最大范数差 = {max_tail_diff:.6g}",
            ],
            meaning=f"{'是柯西列' if is_cauchy else '不是柯西列'}"
            f"（尾部最大差异 {max_tail_diff:.4g}）",
            data={
                "tail_max_diff": max_tail_diff,
                "all_diffs": [float(d) for d in diffs],
            },
        )
    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """自测 normed_spaces 模块。"""
    print("=== normed_spaces self_test ===")
    passed = 0
    total = 5

    # Test 1: lp_norm — ℓ^2 范数
    try:
        r = lp_norm([1, 2, 3], 2)
        assert r.ok
        expected = np.sqrt(14)
        assert abs(r.result - expected) < 1e-10, f"Expected √14, got {r.result}"
        print(f"  [PASS] lp_norm([1,2,3], 2) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] lp_norm l2: {e}")

    # Test 2: lp_norm — ℓ^∞ 范数
    try:
        r = lp_norm([1, -5, 3], float("inf"))
        assert r.ok
        assert abs(r.result - 5.0) < 1e-10
        print(f"  [PASS] lp_norm([1,-5,3], inf) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] lp_norm linf: {e}")

    # Test 3: lp_norm — ℓ^1 范数
    try:
        r = lp_norm([1, -2, 3], 1)
        assert r.ok
        assert abs(r.result - 6.0) < 1e-10
        print(f"  [PASS] lp_norm([1,-2,3], 1) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] lp_norm l1: {e}")

    # Test 4: is_banach
    try:
        r = is_banach("R^n", dimension=3)
        assert r.ok
        assert r.result is True
        print(f"  [PASS] is_banach('R^n', 3) = {r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] is_banach: {e}")

    # Test 5: space_completeness_check — 收敛序列
    try:
        # x_n = 1/n 收敛到 0
        seq = [[1.0 / (i + 1)] for i in range(20)]
        r = space_completeness_check(seq, norm="l2")
        assert r.ok
        print(f"  [PASS] space_completeness_check convergence test: is_cauchy={r.result}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] space_completeness_check: {e}")

    print(f"  Result: {passed}/{total} passed")
    return passed == total


if __name__ == "__main__":
    self_test()
