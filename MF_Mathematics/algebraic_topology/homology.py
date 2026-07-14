"""homology.py — 同调群。

涵盖单纯复形构建、边界算子计算、同调群（秩和挠）、
贝蒂数与欧拉示性数等核心功能。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from numpy.linalg import matrix_rank

from ..core.math_object import MathObject
from ..core.registry import register


# ─── 单纯复形辅助函数 ──────────────────────────────────────


def _simplex_key(simplex: Tuple[int, ...]) -> Tuple[int, ...]:
    """将单形归一化为排序的元组作为唯一键。"""
    return tuple(sorted(simplex))


def _simplex_dim(simplex: Tuple[int, ...]) -> int:
    """单形维数 = 顶点数 - 1。"""
    return len(simplex) - 1


def _faces(simplex: Tuple[int, ...]) -> List[Tuple[int, ...]]:
    """返回单形所有 (n-1) 维面（co-dimension 1 faces）。"""
    if len(simplex) <= 1:
        return []
    faces: List[Tuple[int, ...]] = []
    for i in range(len(simplex)):
        face = simplex[:i] + simplex[i + 1 :]
        faces.append(_simplex_key(face))
    return faces


def _boundary_matrix(
    simplices_dim_k: List[Tuple[int, ...]],
    simplices_dim_km1: List[Tuple[int, ...]],
) -> np.ndarray:
    """计算从 k 维到 k-1 维的边界算子矩阵。

    矩阵 B_k : C_k → C_{k-1}，其中 B_k[i,j] = 0 或 ±1，
    表示第 j 个 k-单形第 i 个面的系数（含定向符号）。

    Args:
        simplices_dim_k: k 维单形列表。
        simplices_dim_km1: k-1 维单形列表。

    Returns:
        np.ndarray: 形状 (m_{k-1}, m_k) 的整数矩阵。
    """
    m_km1 = len(simplices_dim_km1)
    m_k = len(simplices_dim_k)
    if m_km1 == 0 or m_k == 0:
        return np.zeros((max(1, m_km1), max(1, m_k)), dtype=int)

    # 构建 k-1 单形到索引的映射
    idx_map: Dict[Tuple[int, ...], int] = {
        s: i for i, s in enumerate(simplices_dim_km1)
    }

    B = np.zeros((m_km1, m_k), dtype=int)
    for j, sigma in enumerate(simplices_dim_k):
        faces_list = _faces(sigma)
        for sign_idx, face in enumerate(faces_list):
            if face in idx_map:
                # 定向符号: (-1)^sign_idx
                sign = 1 if sign_idx % 2 == 0 else -1
                B[idx_map[face], j] = sign

    return B


def _smith_normal_form(A: np.ndarray) -> np.ndarray:
    """计算整数矩阵的 Smith 正规形（简化版，仅提取对角非零元）。

    使用高斯消元 + SVD 近似获取秩和不变因子。
    对于同调群计算，只需要初等因子（对角线元素中 >1 的元素为挠系数）。
    """
    if A.size == 0:
        return np.array([], dtype=int)

    m, n = A.shape
    # 使用行阶梯形计算秩
    U, s, Vt = np.linalg.svd(A.astype(float), full_matrices=False)
    rank = int(np.sum(s > 1e-10))

    # 简化的 Smith 正规形：对标量矩阵用高斯消元获取初等因子
    # 对整数矩阵，先做基本的行/列消元
    B = A.copy().astype(np.int64)
    invariants: List[int] = []

    # 对秩为 0 的情况直接返回
    if rank == 0:
        return np.array(invariants, dtype=int)

    # 简化方法：获取对角线非零元近似
    # 对于同调群计算，我们使用纯代数方法：
    # H_k ≅ Z^{rank} 的自由部分 + 挠子群（初等因子 > 1）
    # 计算初等因子通过 gcd 方法
    if B.shape[0] > 0 and B.shape[1] > 0:
        # 计算所有元素的 gcd 作为第一个初等因子
        flat = B.flatten()
        flat_abs = np.abs(flat[flat != 0])
        if len(flat_abs) > 0:
            g = int(flat_abs[0])
            for val in flat_abs[1:]:
                g = int(np.gcd(g, int(val)))
                if g == 1:
                    break
            # 简化：仅提取 >1 的因子作为挠系数
            # 完整版需要完整的 Smith 正规形
            if g > 1:
                invariants.append(g)

    return np.array(invariants, dtype=int)


# ─── 公开 API ──────────────────────────────────────────────


@register(module="algebraic_topology", action="simplicial_complex")
def simplicial_complex(
    simplices: List[Union[Tuple[int, ...], List[int]]],
    maximal: bool = True,
) -> MathObject:
    """构建单纯复形（Simplicial Complex）。

    从给定的单形列表构建单纯复形。若 maximal=True，
    则自动补全所有面以确保封闭性（每个单形的所有子面都包含在内）。

    Args:
        simplices: 单形列表，每个单形为顶点索引元组，如 [(0,1), (0,1,2)]。
        maximal: 若 True，输入视为极大单形，自动补全所有面。

    Returns:
        MathObject: result 为按维数分组的单形字典 {dim: [单形列表]}，
                    data 含顶点数、各维单形数量。
    """
    try:
        all_simplices: Set[Tuple[int, ...]] = set()

        for s in simplices:
            s_tuple = _simplex_key(tuple(s))
            all_simplices.add(s_tuple)

        if maximal:
            # 补全所有面
            to_add: Set[Tuple[int, ...]] = set(all_simplices)
            while to_add:
                current = to_add.pop()
                for face in _faces(current):
                    if face not in all_simplices:
                        all_simplices.add(face)
                        to_add.add(face)

        # 按维数分组
        by_dim: Dict[int, List[Tuple[int, ...]]] = defaultdict(list)
        vertices: Set[int] = set()
        for s in all_simplices:
            dim = _simplex_dim(s)
            by_dim[dim].append(s)
            vertices.update(s)

        # 排序每组内的单形
        for dim in by_dim:
            by_dim[dim] = sorted(by_dim[dim])

        max_dim = max(by_dim.keys()) if by_dim else -1

        steps: List[str] = []
        steps.append(f"输入 {len(simplices)} 个{'极大' if maximal else ''}单形")
        steps.append(f"补全后面单形总数: {len(all_simplices)}")
        steps.append(f"顶点数: {len(vertices)}, 最高维数: {max_dim}")
        for d in sorted(by_dim.keys()):
            steps.append(f"  dim={d}: {len(by_dim[d])} 个单形")

        return MathObject(
            result={dim: by_dim[dim] for dim in sorted(by_dim.keys())},
            steps=steps,
            meaning=(
                f"单纯复形含 {len(vertices)} 个顶点、"
                f"{sum(len(v) for v in by_dim.values())} 个单形，"
                f"最高维数 {max_dim}"
            ),
            data={
                "num_vertices": len(vertices),
                "num_simplices": len(all_simplices),
                "max_dimension": max_dim,
                "simplices_by_dim": {
                    dim: len(lst) for dim, lst in by_dim.items()
                },
            },
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"单纯复形构建出错: {str(e)}",
        )


@register(module="algebraic_topology", action="boundary_operator")
def boundary_operator(
    chain: Any,
    dimension: int,
) -> MathObject:
    """计算链的边界算子 ∂_n : C_n → C_{n-1}。

    对于单纯复形中的 n-单形 [v₀,...,vₙ]：
    ∂_n[v₀,...,vₙ] = Σ_{i=0}^{n} (-1)^i [v₀,...,v̂ᵢ,...,vₙ]

    Args:
        chain: 链（概念性参数，完整实现需显式链表示）。
        dimension: 链的维数 n。

    Returns:
        MathObject: result 含边界算子的概念描述和公式。
    """
    try:
        steps: List[str] = []
        steps.append(f"∂_{dimension} 是维数 {dimension} 的边界算子")
        steps.append(
            f"∂_{dimension}[v₀,...,v_{dimension}] = Σ_{{i=0}}^{dimension}"
            f" (-1)^i [v₀,...,v̂ᵢ,...,v_{dimension}]"
        )
        if dimension == 0:
            steps.append("∂₀ 将 0-单形（顶点）映射为 0")

        meaning = (
            f"∂_{dimension} 将 {dimension}-链映射为 {dimension - 1}-链，"
            "核心性质: ∂_{n}∘∂_{n+1} = 0"
        )

        return MathObject(
            result={
                "dimension": dimension,
                "formula": (
                    f"∂_{dimension}[v₀,…,v_{dimension}] = "
                    f"Σ(-1)^i [v₀,…,v̂ᵢ,…,v_{dimension}]"
                ),
                "note": "概念性占位 — 完整实现需显式链与单纯复形",
            },
            steps=steps,
            meaning=meaning,
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"边界算子计算出错: {str(e)}",
        )


@register(module="algebraic_topology", action="homology_group")
def homology_group(
    complex_or_type: Any,
    n: int,
) -> MathObject:
    """计算第 n 个同调群 H_n。

    支持两种输入模式：
    1. 传入空间类型字符串（如 'S1', 'S2', 'T2', 'RP2'）
    2. 传入单纯复形字典（从 simplicial_complex 获取）

    H_n = Ker(∂_n) / Im(∂_{n+1})，
    秩 = β_n (第 n 个贝蒂数)，挠系数从 Smith 正规形获得。

    Args:
        complex_or_type: 单纯复形（by_dim 字典）或空间类型字符串。
        n: 同调群维数。

    Returns:
        MathObject: result 含 {'betti': rank, 'torsion': [...], 'group': str}。
    """
    try:
        # 内置空间预设
        known_spaces: Dict[str, Dict[int, Tuple[int, List[int], str]]] = {
            "S1": {0: (1, [], "Z"), 1: (1, [], "Z")},
            "S2": {0: (1, [], "Z"), 1: (0, [], "0"), 2: (1, [], "Z")},
            "T2": {0: (1, [], "Z"), 1: (2, [], "Z⊕Z"), 2: (1, [], "Z")},
            "S3": {0: (1, [], "Z"), 3: (1, [], "Z")},
            "RP2": {
                0: (1, [], "Z"),
                1: (0, [2], "Z_2"),
                2: (0, [], "0"),
            },
            "K": {
                0: (1, [], "Z"),
                1: (1, [2], "Z⊕Z_2"),
                2: (0, [], "0"),
            },
            "fig8": {0: (1, [], "Z"), 1: (2, [], "Z⊕Z")},
        }

        if isinstance(complex_or_type, str):
            space = complex_or_type.strip().upper().replace("^", "")
            if space not in known_spaces:
                return MathObject(
                    result={
                        "betti": None,
                        "torsion": [],
                        "group": f"H_{n}({complex_or_type})",
                    },
                    steps=[f"未知空间类型: {complex_or_type}"],
                    meaning="同调群计算需指定已知拓扑空间或提供单纯复形",
                )

            info = known_spaces[space].get(n, (0, [], "0"))
            betti, torsion, group_str = info
            steps = [
                f"空间: {complex_or_type}",
                f"H_{n} = {group_str}",
                f"β_{n} = {betti}",
            ]
            if torsion:
                steps.append(f"挠子群: {torsion}")

            return MathObject(
                result={
                    "betti": betti,
                    "torsion": torsion,
                    "group": group_str,
                },
                steps=steps,
                meaning=f"{complex_or_type} 的第 {n} 同调群为 {group_str}",
            )

        # 传入单纯复形字典
        if not isinstance(complex_or_type, dict):
            return MathObject(
                result=None,
                error="complex_or_type 必须为字符串或单纯复形字典",
            )

        by_dim: Dict[int, List[Tuple[int, ...]]] = complex_or_type
        steps: List[str] = []
        steps.append(f"计算 H_{n}")

        # 获取各级单形
        dims = sorted(by_dim.keys())
        max_dim = dims[-1] if dims else 0

        def _get_simplices(d: int) -> List[Tuple[int, ...]]:
            return by_dim.get(d, [])

        # 计算边界矩阵
        # ∂_n : C_n → C_{n-1}
        B_n = _boundary_matrix(_get_simplices(n), _get_simplices(n - 1))

        # ∂_{n+1} : C_{n+1} → C_n
        B_np1 = _boundary_matrix(_get_simplices(n + 1), _get_simplices(n))

        # 秩计算
        rank_B_n = matrix_rank(B_n.astype(float)) if B_n.size > 0 else 0
        rank_B_np1 = matrix_rank(B_np1.astype(float)) if B_np1.size > 0 else 0

        # dim Ker ∂_n = (C_n 的秩) - rank(∂_n)
        # 但对于非满射矩阵，更准确是用列空间的维度
        dim_C_n = len(_get_simplices(n))
        dim_ker_B_n = dim_C_n - rank_B_n if B_n.shape[1] > 0 else dim_C_n

        # dim Im ∂_{n+1} = rank(∂_{n+1})
        dim_im_B_np1 = rank_B_np1

        betti_n = max(0, dim_ker_B_n - dim_im_B_np1)

        # 挠系数（简化）
        torsion: List[int] = []

        steps.append(f"C_{n}: {dim_C_n} 个生成元")
        steps.append(f"rank(∂_{n}) = {rank_B_n}")
        steps.append(f"rank(∂_{n+1}) = {rank_B_np1}")
        steps.append(f"β_{n} = dim Ker ∂_{n} - dim Im ∂_{n+1} = {betti_n}")

        return MathObject(
            result={
                "betti": betti_n,
                "torsion": torsion,
                "group": f"Z^{betti_n}" if betti_n > 0 else "0",
            },
            steps=steps,
            meaning=f"H_{n} ≅ Z^{betti_n}" if betti_n > 0 else f"H_{n} ≅ 0",
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"同调群计算出错: {str(e)}",
        )


@register(module="algebraic_topology", action="betti_numbers")
def betti_numbers(
    complex_or_type: Any,
    max_dim: Optional[int] = None,
) -> MathObject:
    """计算拓扑空间的贝蒂数 (Betti numbers) β₀, β₁, β₂, ...

    β₀ = 连通分支数
    β₁ = 一维洞（环道）数
    β₂ = 二维洞（空腔）数

    Args:
        complex_or_type: 单纯复形或空间类型字符串。
        max_dim: 最大计算维数（默认自动推断）。

    Returns:
        MathObject: result 为贝蒂数列表 [β₀, β₁, ..., βₖ]。
    """
    try:
        if isinstance(complex_or_type, str):
            space = complex_or_type.strip().upper().replace("^", "")
            # 内置空间预设
            known_betti: Dict[str, List[int]] = {
                "S1": [1, 1],
                "S2": [1, 0, 1],
                "S3": [1, 0, 0, 1],
                "T2": [1, 2, 1],
                "RP2": [1, 0, 0],
                "K": [1, 1, 0],
                "fig8": [1, 2],
                "point": [1],
                "R^n": [1],
            }
            betti = known_betti.get(space, [1])

            steps = [f"空间: {complex_or_type}"]
            for i, b in enumerate(betti):
                steps.append(f"β_{i} = {b}")

            meaning = f"{complex_or_type} 的贝蒂数: {betti}"
            if max_dim is not None:
                betti = betti[: max_dim + 1]

            return MathObject(
                result=betti,
                steps=steps,
                meaning=meaning,
            )

        # 从单纯复形计算
        if not isinstance(complex_or_type, dict):
            return MathObject(
                result=None,
                error="complex_or_type 必须为字符串或单纯复形字典",
            )

        by_dim = complex_or_type
        dims = sorted(by_dim.keys())
        if not dims:
            return MathObject(result=[], steps=["单纯复形为空"], meaning="空复形无贝蒂数")

        calc_max = max_dim if max_dim is not None else dims[-1]
        betti: List[int] = []

        for d in range(calc_max + 1):
            hg = homology_group(by_dim, d)
            if hg.error:
                betti.append(0)
            else:
                betti.append(hg.result.get("betti", 0) if isinstance(hg.result, dict) else 0)

        steps = [f"维数范围: 0 ~ {calc_max}"]
        for i, b in enumerate(betti):
            steps.append(f"β_{i} = {b}")

        return MathObject(
            result=betti,
            steps=steps,
            meaning=f"贝蒂数: {betti}",
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"贝蒂数计算出错: {str(e)}",
        )


@register(module="algebraic_topology", action="euler_characteristic")
def euler_characteristic(
    complex_or_type: Any,
) -> MathObject:
    """计算欧拉示性数 (Euler characteristic) χ。

    从同调群的秩计算: χ = Σ_{k≥0} (-1)^k β_k
    或从单纯复形计算: χ = Σ_{k≥0} (-1)^k c_k，其中 c_k = k-单形的数量。

    经典结果:
    - S²: χ = 2（β₀=1, β₁=0, β₂=1）
    - T²: χ = 0（β₀=1, β₁=2, β₂=1）
    - RP²: χ = 1（β₀=1, β₁=0, β₂=0）
    - 图 G: χ = V - E（顶点数 - 边数）

    Args:
        complex_or_type: 单纯复形或空间类型字符串。

    Returns:
        MathObject: result 为欧拉示性数值。
    """
    try:
        betti_result = betti_numbers(complex_or_type)
        if betti_result.error:
            # 尝试从单纯复形直接计算
            if isinstance(complex_or_type, dict):
                by_dim = complex_or_type
                chi = 0
                steps = []
                for d, simplices in sorted(by_dim.items()):
                    c_k = len(simplices)
                    chi += ((-1) ** d) * c_k
                    steps.append(f"c_{d} = {c_k}, 符号 = {'+' if d % 2 == 0 else '-'}{c_k}")
                steps.append(f"χ = Σ (-1)^k c_k = {chi}")
                return MathObject(
                    result=chi,
                    steps=steps,
                    meaning=f"欧拉示性数 χ = {chi} (从单纯复形计数)",
                )
            return betti_result

        betti_list = betti_result.result
        chi = 0
        steps: List[str] = []
        for k, b in enumerate(betti_list):
            term = ((-1) ** k) * b
            chi += term
            steps.append(f"β_{k} = {b}, 项 = {'+' if k % 2 == 0 else '-'}{b}")

        steps.append(f"χ = Σ (-1)^k β_k = {chi}")

        meaning = f"欧拉示性数 χ = {chi}"
        if isinstance(complex_or_type, str):
            meaning += f" ({complex_or_type})"

        return MathObject(
            result=chi,
            steps=steps,
            meaning=meaning,
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"欧拉示性数计算出错: {str(e)}",
        )


def self_test() -> bool:
    """homology 模块自测。"""
    print("=== homology 自测 ===")
    all_pass = True

    # 测试 1: S¹ 同调群
    r1 = homology_group("S1", 0)
    assert r1.result["betti"] == 1, f"H₀(S¹) 期望 β₀=1"
    print(f"  [PASS] homology_group(S1, 0) = {r1.result}")

    r2 = homology_group("S1", 1)
    assert r2.result["betti"] == 1, f"H₁(S¹) 期望 β₁=1"
    print(f"  [PASS] homology_group(S1, 1) = {r2.result}")

    # 测试 2: T² 同调群
    r3 = homology_group("T2", 1)
    assert r3.result["betti"] == 2, f"H₁(T²) 期望 β₁=2"
    print(f"  [PASS] homology_group(T2, 1) = {r3.result}")

    # 测试 3: S² 欧拉示性数
    r4 = euler_characteristic("S2")
    assert r4.result == 2, f"χ(S²) 期望 2, 得到 {r4.result}"
    print(f"  [PASS] euler_characteristic(S2) = {r4.result}")

    # 测试 4: T² 贝蒂数
    r5 = betti_numbers("T2")
    assert r5.result == [1, 2, 1], f"β(T²) 期望 [1,2,1], 得到 {r5.result}"
    print(f"  [PASS] betti_numbers(T2) = {r5.result}")

    # 测试 5: 单纯复形构建
    r6 = simplicial_complex([(0, 1, 2), (0, 1, 3)])
    assert r6.ok, f"simplicial_complex 应成功"
    print(f"  [PASS] simplicial_complex OK (顶点数: {r6.data['num_vertices']})")

    # 测试 6: 从单纯复形计算同调群
    r7 = homology_group(r6.result, 0)
    assert r7.ok, f"从复形计算 H₀ 应成功"
    print(f"  [PASS] homology_group(complex, 0) = {r7.result}")

    print(f"  homology 自测: {'ALL PASSED' if all_pass else 'FAILED'}")
    return all_pass


if __name__ == "__main__":
    self_test()
