"""degree_fixedpoint.py — 映射度与不动点定理。

涵盖映射度、布劳威尔不动点定理、毛球定理等拓扑学经典结果。
"""

from __future__ import annotations

from typing import Any, List

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="algebraic_topology", action="mapping_degree")
def mapping_degree(
    f: Any = None,
    sphere_dim: int = 1,
) -> MathObject:
    """计算映射度 (mapping degree) deg(f) : Sⁿ → Sⁿ。

    映射度是连续映射 f: Sⁿ → Sⁿ 的拓扑不变量。
    对于光滑映射，deg(f) = Σ_{x∈f^{-1}(y)} sign(det(df_x))，
    其中 y 是 Sⁿ 上的正则值。

    性质:
    - deg(id) = 1
    - deg(对径映射 A(x) = -x) = (-1)^{n+1}
    - deg(f∘g) = deg(f)·deg(g)
    - 同伦的映射具有相同的映射度

    Args:
        f: 映射（概念性参数，完整实现需显式映射表示）。
        sphere_dim: 球面维数 n。

    Returns:
        MathObject: result 含映射度概念描述和性质。
    """
    try:
        steps: List[str] = []
        steps.append(f"映射度 deg(f) 是映射 f: S^{sphere_dim} → S^{sphere_dim} 的拓扑不变量")
        steps.append("deg 由 f 在 n 维同调群上诱导的同态 f_* : H_n(Sⁿ) → H_n(Sⁿ) 决定")
        steps.append("即 f_*(1) = deg(f)·1 ∈ Z")

        # 演示性质
        antipodal_deg = (-1) ** (sphere_dim + 1)
        steps.append(f"对径映射 deg = {antipodal_deg}")
        steps.append("恒等映射 deg(id) = 1")

        meaning = (
            f"映射度衡量 f: S^{sphere_dim} → S^{sphere_dim} 将球面 '环绕' 自身的次数。"
            "恒等映射的映射度为 1，对径映射为 (-1)^{n+1}。"
        )

        return MathObject(
            result={
                "sphere_dim": sphere_dim,
                "antipodal_degree": antipodal_deg,
                "identity_degree": 1,
                "note": "概念性占位 — 完整实现需显式映射与同调群诱导同态",
            },
            steps=steps,
            meaning=meaning,
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"映射度计算出错: {str(e)}",
        )


@register(module="algebraic_topology", action="brouwer_fixed_point_theorem")
def brouwer_fixed_point_theorem(
    space: str = "D2",
) -> MathObject:
    """布劳威尔不动点定理 (Brouwer Fixed Point Theorem)。

    定理陈述: 任何从 n 维闭球体 Dⁿ 到自身的连续映射 f: Dⁿ → Dⁿ
    必存在不动点 x ∈ Dⁿ 使得 f(x) = x。

    经典应用:
    - n=1: 任何连续 f: [0,1] → [0,1] 有不动的（一维布劳威尔定理）
    - n=2: 搅拌咖啡时总有一点不动（二维情形）
    - 等价于: 不存在从 Dⁿ 到其边界 S^{n-1} 的收缩映射

    Args:
        space: 空间标识（'D1', 'D2', 'D3' 等）。

    Returns:
        MathObject: result 含定理陈述和证明概要。
    """
    try:
        space_normalized = space.strip().upper()
        dim_map = {"D1": 1, "D2": 2, "D3": 3}
        n = dim_map.get(space_normalized, 2)

        steps: List[str] = []
        steps.append(f"布劳威尔不动点定理 (n={n})")
        steps.append(f"任何连续 f: D^{n} → D^{n} 存在不动点 f(x) = x")
        steps.append("证明思路（反证）:")
        steps.append("  假设无不动点，则 f(x) ≠ x ∀x")
        steps.append("  构造收缩 r(x) = x + t(x)(x - f(x)) 交于 S^{n-1}")
        steps.append("  但不存在从 Dⁿ 到 S^{n-1} 的连续收缩（同调群矛盾）")
        steps.append("等价命题: 边界 S^{n-1} 不是 Dⁿ 的收缩核")

        meaning = (
            f"Brouwer 定理是拓扑学中最重要的不动点定理之一。"
            f"它保证了 D^{n} 上任何连续自映射必有不动点。"
            f"该定理在经济均衡、博弈论 Nash 均衡证明中有广泛应用。"
        )

        return MathObject(
            result={
                "theorem": "Brouwer Fixed Point",
                "dimension": n,
                "statement": f"任何 f: D^{n} → D^{n} 连续 ⇒ ∃ x ∈ D^{n}, f(x)=x",
                "holds": True,
            },
            steps=steps,
            meaning=meaning,
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"布劳威尔不动点定理验证出错: {str(e)}",
        )


@register(module="algebraic_topology", action="hairy_ball_theorem")
def hairy_ball_theorem(
    sphere_dim: int = 2,
) -> MathObject:
    """毛球定理 (Hairy Ball Theorem) 判断。

    定理陈述: 偶数维球面 S^{2n} 上不存在处处非零的连续切向量场。
    等价说法: "你无法梳平一个毛球（偶数维），总会有至少一个旋。"

    具体结果:
    - S² (2 维球面): 不存在处处非零切向量场 → 地球上总有风速为零的点
    - S¹ (1 维球面): 存在（可以梳平圆周） → 不是毛球定理范围
    - S³ (3 维球面): 存在（可以梳平） → 不是毛球定理范围
    - S⁴ (4 维球面): 不存在

    毛球定理的代数拓扑证明基于欧拉示性数:
    χ(S^{2n}) = 2 ≠ 0 → 不存在处处非零向量场

    Args:
        sphere_dim: 球面维数。

    Returns:
        MathObject: result 含 True（存在非零场）/ False（不存在）。
    """
    try:
        is_even = sphere_dim % 2 == 0
        non_zero_exists = not is_even

        steps: List[str] = []
        steps.append(f"S^{sphere_dim} ({'偶' if is_even else '奇'}数维球面)")
        if is_even:
            steps.append(f"毛球定理适用: 不存在处处非零连续切向量场")
            steps.append(f"原因: χ(S^{sphere_dim}) = 2 ≠ 0")
            steps.append("这意味着任何连续切向量场必有至少一个零点")
        else:
            steps.append(f"毛球定理不适用: 存在处处非零连续切向量场")
            steps.append(f"原因: χ(S^{sphere_dim}) = 0（奇数维时）")
            steps.append("可以构造 Lie 群作用得到非零向量场（如 S³ ≅ SU(2)）")

        meaning = (
            f"{'' if is_even else 'S' + str(sphere_dim) + ' 上可梳平。'}"
            f"毛球定理揭示: 偶数维球面必有向量场零点。"
            f"物理含义: 地球上任何时刻至少有一个点风速为零。"
        )

        return MathObject(
            result={
                "sphere_dim": sphere_dim,
                "nonzero_vector_field_exists": non_zero_exists,
                "euler_characteristic": 2 if is_even else 0,
            },
            steps=steps,
            meaning=meaning,
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"毛球定理判断出错: {str(e)}",
        )


def self_test() -> bool:
    """degree_fixedpoint 模块自测。"""
    print("=== degree_fixedpoint 自测 ===")
    all_pass = True

    # 测试 1: 映射度（概念性）
    r1 = mapping_degree(sphere_dim=1)
    assert r1.ok, "映射度 S¹ 应成功"
    assert r1.result["antipodal_degree"] == 1, (
        f"S¹ 对径映射度为 1, 得到 {r1.result['antipodal_degree']}"
    )
    print(f"  [PASS] mapping_degree(S1) = deg(antipodal)={r1.result['antipodal_degree']}")

    r2 = mapping_degree(sphere_dim=2)
    assert r2.result["antipodal_degree"] == -1, (
        f"S² 对径映射度为 -1, 得到 {r2.result['antipodal_degree']}"
    )
    print(f"  [PASS] mapping_degree(S2) = deg(antipodal)={r2.result['antipodal_degree']}")

    # 测试 2: 布劳威尔不动点
    r3 = brouwer_fixed_point_theorem("D2")
    assert r3.ok and r3.result["holds"], "布劳威尔定理应成立"
    print(f"  [PASS] brouwer_fixed_point_theorem(D2) holds={r3.result['holds']}")

    # 测试 3: 毛球定理
    r4 = hairy_ball_theorem(sphere_dim=2)
    assert r4.ok and r4.result["nonzero_vector_field_exists"] is False, (
        "S² 无处处非零场"
    )
    print(f"  [PASS] hairy_ball_theorem(S2) nonzero_exists={r4.result['nonzero_vector_field_exists']}")

    r5 = hairy_ball_theorem(sphere_dim=3)
    assert r5.result["nonzero_vector_field_exists"] is True, "S³ 有非零场"
    print(f"  [PASS] hairy_ball_theorem(S3) nonzero_exists={r5.result['nonzero_vector_field_exists']}")

    print(f"  degree_fixedpoint 自测: {'ALL PASSED' if all_pass else 'FAILED'}")
    return all_pass


if __name__ == "__main__":
    self_test()
