"""homotopy.py — 同伦与基本群。

涵盖同伦、基本群 π₁、单连通性判定、路径同伦等核心概念。
"""

from __future__ import annotations

from typing import Any, List

from ..core.math_object import MathObject
from ..core.registry import register


@register(module="algebraic_topology", action="fundamental_group")
def fundamental_group(
    space: str,
    n: int = 1,
) -> MathObject:
    """计算给定空间的基本群 (fundamental group) π₁。

    支持的空间类型：
    - 'S1', 'S^1': 圆环 S¹ → π₁(S¹) = Z（整数加群）
    - 'Sn', 'S^n' (n≥2): n 维球面 → π₁(Sⁿ) = 0（平凡群）
    - 'T2', 'T^2': 二维环面 → π₁(T²) = Z × Z
    - 'RP2', 'RP^2': 实射影平面 → π₁(RP²) = Z₂
    - 'K': Klein 瓶 → π₁(K) = ⟨a,b | aba⁻¹b⟩
    - 'fig8': 8 字形 → π₁ = 秩为 2 的自由群 F₂
    - 'wedge_n': n 个 S¹ 的楔和 → π₁ = Fₙ (自由群)

    Args:
        space: 空间类型字符串，如 'S1'、'Sn'、'T2'。
        n: 球面维数（space='Sn' 时使用），默认 1。

    Returns:
        MathObject: result 为描述基本群的字符串（如 "Z"、"0"、"Z×Z"），
                    steps 含推导过程，meaning 含几何解释。
    """
    try:
        space_normalized = space.strip().upper().replace("^", "")
        steps: List[str] = []
        result: str = ""
        meaning: str = ""

        if space_normalized in ("S1",):
            steps.append("S¹ 是圆周，其万有覆盖空间为 ℝ，覆盖映射为 t ↦ e^{2πit}")
            steps.append("覆盖变换群为 Z（整数的平移），故 π₁(S¹) ≅ Z")
            result = "Z"
            meaning = "圆周的基本群是整数加群 Z，生成元为绕圆周一圈的环道"

        elif space_normalized in ("SN",) and n >= 2:
            steps.append(f"S^{n} (n={n}≥2) 是单连通的")
            steps.append(f"任何环道可在 S^{n} 上连续缩至一点（n≥2 时高维球面无「洞」阻挡）")
            result = "0"
            meaning = f"{n} 维球面单连通，基本群为平凡群"

        elif space_normalized in ("SN",) and n == 1:
            steps.append("S¹ 的万有覆盖为 ℝ，覆盖变换群为 Z")
            result = "Z"
            meaning = "S¹ 基本群为 Z"

        elif space_normalized in ("T2",):
            steps.append("T² = S¹ × S¹，积空间的基本群 = π₁(S¹) × π₁(S¹)")
            steps.append("故 π₁(T²) ≅ Z × Z")
            result = "Z×Z"
            meaning = "环面有两个独立的非平凡环道方向（经线/纬线），基本群为 Z⊕Z"

        elif space_normalized in ("RP2",):
            steps.append("RP² = S² / (对径点等同)，是 S² 的 Z₂ 商")
            steps.append("π₁(RP²) ≅ Z₂（二阶循环群）")
            result = "Z_2"
            meaning = "实射影平面的基本群为 Z₂，非平凡环道绕两圈才可缩为一点"

        elif space_normalized in ("K", "KLEIN"):
            steps.append("Klein 瓶的基本群为 ⟨a,b | aba⁻¹b = 1⟩")
            steps.append("这是一个非交换群")
            result = "<a,b | aba^{-1}b>"
            meaning = "Klein 瓶的基本群非交换，生成元 a,b 满足 aba⁻¹b=1"

        elif space_normalized in ("FIG8",):
            steps.append("8 字形 = S¹ ∨ S¹（两个圆的楔和）")
            steps.append("由 van Kampen 定理，π₁ ≅ F₂（两个生成元的自由群）")
            result = "F_2"
            meaning = "8 字形的基本群是秩为 2 的自由群"

        elif space_normalized == "WEDGEN" or space_normalized.startswith("WEDGE"):
            steps.append(f"{n} 个 S¹ 的楔和 = ∨^{n}S¹")
            steps.append(f"由 van Kampen 定理，π₁ ≅ F_{n}（{n} 个生成元的自由群）")
            result = f"F_{n}"
            meaning = f"{n} 个 S¹ 楔和的基本群是秩为 {n} 的自由群"

        else:
            steps.append(f"未知空间类型: {space}，返回概念性说明")
            result = f"π₁({space})"
            meaning = "基本群计算需指定具体拓扑空间"

        return MathObject(
            result=result,
            steps=steps,
            meaning=meaning,
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"基本群计算出错: {str(e)}",
            meaning="拓扑空间基本群计算",
        )


@register(module="algebraic_topology", action="is_simply_connected")
def is_simply_connected(
    space: str,
    n: int = 1,
) -> MathObject:
    """判断拓扑空间是否单连通（simply connected）。

    单连通 = 道路连通 且 基本群平凡 (π₁ = 0)。

    Args:
        space: 空间类型字符串（同 fundamental_group 参数）。
        n: 球面维数。

    Returns:
        MathObject: result 为 True/False，含推理过程。
    """
    try:
        fg = fundamental_group(space=space, n=n)
        if fg.error:
            return MathObject(
                result=None,
                error=f"无法判定单连通性: {fg.error}",
            )

        is_simply = fg.result == "0"
        steps: List[str] = []
        steps.append(f"基本群 π₁({space}) = {fg.result}")
        steps.append(
            "单连通" if is_simply else "非单连通（基本群非平凡）"
        )
        meaning = (
            "该空间单连通：道路连通且任何环道可连续缩为一点"
            if is_simply
            else f"该空间非单连通，基本群为 {fg.result}"
        )

        return MathObject(
            result=is_simply,
            steps=steps,
            meaning=meaning,
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"单连通性判断出错: {str(e)}",
        )


@register(module="algebraic_topology", action="path_homotopy")
def path_homotopy(
    f: Any = None,
    g: Any = None,
    space: str = "R^n",
) -> MathObject:
    """判断两条路径是否同伦（概念性占位）。

    在拓扑空间 X 中，两条有相同端点的路径 f, g : [0,1] → X
    称为路径同伦，若存在连续映射 H : [0,1] × [0,1] → X 使得
    H(s, 0) = f(s), H(s, 1) = g(s)，且端点固定。

    本函数为概念性占位，不执行实际路径比较。

    Args:
        f: 第一条路径（概念性参数）。
        g: 第二条路径（概念性参数）。
        space: 拓扑空间标识。

    Returns:
        MathObject: result 含概念性说明。
    """
    try:
        steps: List[str] = []
        steps.append(f"路径同伦判断基于空间 {space} 的基本群")
        steps.append("若 π₁ 平凡，则任意两条同端点的路径均同伦")
        steps.append("若 π₁ 非平凡，需比较路径在基本群中代表的元素")

        fg = fundamental_group(space=space, n=1)
        meaning = (
            f"空间 {space} 的基本群为 {fg.result}。"
            "路径同伦等价于路径在基本群中代表同一元素。"
        )

        return MathObject(
            result={
                "space": space,
                "fundamental_group": fg.result,
                "note": "概念性占位 — 完整实现需显式路径表示与同伦构造",
            },
            steps=steps,
            meaning=meaning,
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"路径同伦判断出错: {str(e)}",
        )


def self_test() -> tuple[int, int, int]:
    """homotopy 模块自测。返回 (passed, failed, errors)。"""
    print("=== homotopy 自测 ===")
    passed, failed, errors = 0, 0, 0
    tests = [
        ("fundamental_group(S1)", lambda: fundamental_group("S1"), lambda r: r.result == "Z"),
        ("fundamental_group(S2)", lambda: fundamental_group("Sn", n=2), lambda r: r.result == "0"),
        ("fundamental_group(T2)", lambda: fundamental_group("T2"), lambda r: r.result == "Z×Z"),
        ("is_simply_connected(S2)", lambda: is_simply_connected("Sn", n=2), lambda r: r.result is True),
        ("is_simply_connected(S1)", lambda: is_simply_connected("S1"), lambda r: r.result is False),
        ("path_homotopy(S1)", lambda: path_homotopy(space="S1"), lambda r: r.ok),
    ]
    for name, fn, check in tests:
        try:
            r = fn()
            assert check(r), f"未通过: {r}"
            passed += 1
            print(f"  [PASS] {name} = {r.result if hasattr(r, 'result') else r}")
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")
        except Exception as e:
            errors += 1
            print(f"  [ERROR] {name}: {e}")
    print(f"  homotopy 自测: {passed} pass, {failed} fail, {errors} error")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
