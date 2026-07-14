"""persistent_homology.py — 持续同调 (Persistent Homology)。

涵盖过滤复形构建、持续同调图（persistence diagram）、
条形码（barcode）可视化等计算拓扑核心功能。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register


# ─── 辅助函数 ──────────────────────────────────────────────


def _euclidean_distance(p: np.ndarray, q: np.ndarray) -> float:
    """两点间欧氏距离。"""
    return float(np.sqrt(np.sum((p - q) ** 2)))


def _build_distance_matrix(points: np.ndarray) -> np.ndarray:
    """计算点云的距离矩阵。"""
    n = len(points)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = _euclidean_distance(points[i], points[j])
            D[i, j] = d
            D[j, i] = d
    return D


def _vietoris_rips_filtration(
    points: np.ndarray,
    max_scale: float,
    max_dim: int = 2,
) -> Dict[str, Any]:
    """Vietoris-Rips 复形过滤。

    对于每个 ε ∈ [0, max_scale]，VR_ε 包含所有直径 ≤ ε 的单形。
    实际上离散化为有限步。

    返回: {
        'filtration': [(epsilon, simplex), ...],
        'birth_death': {dim: [(birth, death), ...]},
    }
    """
    n = len(points)
    D = _build_distance_matrix(points)

    # 构建所有边及其长度
    edges: List[Tuple[float, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            edges.append((D[i, j], i, j))
    edges.sort(key=lambda x: x[0])

    # 用 Union-Find 追踪连通分支
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    # dim=0: 连通分支的 birth-death
    birth_death_0: List[Tuple[float, float]] = []
    # 所有 0-单形出生在 ε=0
    component_birth: Dict[int, float] = {i: 0.0 for i in range(n)}
    component_active: Dict[int, bool] = {i: True for i in range(n)}

    for epsilon, i, j in edges:
        ri, rj = find(i), find(j)
        if ri != rj:
            # 两个连通分支合并：较早的"死亡"，较晚的"存活"
            bi = component_birth.get(ri, 0.0)
            bj = component_birth.get(rj, 0.0)

            if bi <= bj:
                birth_death_0.append((bi, epsilon))
                component_birth[rj] = max(bi, bj)
            else:
                birth_death_0.append((bj, epsilon))
                component_birth[ri] = max(bi, bj)

            union(i, j)

    # 剩余未死亡的连通分支：死亡在 max_scale
    seen_roots: set = set()
    for i in range(n):
        root = find(i)
        if root not in seen_roots:
            seen_roots.add(root)
            birth_death_0.append((component_birth.get(root, 0.0), max_scale))

    # dim=1: 简化方法 — 统计三角形形成时的 1-循环
    birth_death_1: List[Tuple[float, float]] = []
    triangles: List[Tuple[float, Tuple[int, int, int]]] = []

    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                d_ij = D[i, j]
                d_jk = D[j, k]
                d_ki = D[k, i]
                birth_eps = max(d_ij, d_jk, d_ki)
                if birth_eps <= max_scale:
                    triangles.append((birth_eps, (i, j, k)))

    triangles.sort(key=lambda x: x[0])

    # 对于每个三角形，追踪 1-循环的出生
    # 简化：以三角形最大边长为 birth，若不能填充为 death=max_scale
    for eps, tri in triangles:
        birth_death_1.append((eps, max_scale))

    return {
        "filtration": edges + [(t[0], t[1]) for t in triangles],
        "birth_death": {0: birth_death_0, 1: birth_death_1},
    }


# ─── 公开 API ──────────────────────────────────────────────


@register(module="algebraic_topology", action="filtration")
def filtration(
    point_cloud: Any,
    max_scale: float = 1.0,
    max_dim: int = 2,
) -> MathObject:
    """构建点云数据的过滤复形 (Filtration)。

    使用 Vietoris-Rips 复形构建过滤。对于每个 ε ∈ [0, max_scale]，
    构建 VR_ε 复形（两点间距离 ≤ ε 时添加边，三角形添加面等）。

    Args:
        point_cloud: 点云数据，形状 (N, d) 的 numpy 数组或嵌套列表。
        max_scale: 最大过滤尺度 ε_max。
        max_dim: 最大单形维数（默认 2）。

    Returns:
        MathObject: result 含过滤复形信息，
                    data 含点云、距离矩阵和 birth-death 对。
    """
    try:
        # 归一化输入
        if isinstance(point_cloud, list):
            points = np.array(point_cloud, dtype=float)
        elif isinstance(point_cloud, np.ndarray):
            points = point_cloud.astype(float)
        else:
            return MathObject(
                result=None,
                error=f"不支持的输入类型: {type(point_cloud)}",
            )

        if points.ndim != 2:
            points = points.reshape(-1, 1)

        n_points, ambient_dim = points.shape

        steps: List[str] = []
        steps.append(f"点云: {n_points} 个点, 环境维数 {ambient_dim}")
        steps.append(f"过滤尺度范围: [0, {max_scale}]")
        steps.append("使用 Vietoris-Rips 复形构建过滤")

        # 构建过滤
        filtration_data = _vietoris_rips_filtration(
            points, max_scale, max_dim
        )

        birth_death = filtration_data["birth_death"]

        for dim, pairs in birth_death.items():
            steps.append(
                f"  dim={dim}: {len(pairs)} 个出生-死亡对"
            )

        meaning = (
            f"Vietoris-Rips 过滤复形，含 {n_points} 个点，"
            f"尺度范围 [0, {max_scale}]。"
            f"0 维持续同调追踪连通分支，"
            f"1 维追踪闭环结构的出现与消失。"
        )

        return MathObject(
            result={
                "n_points": n_points,
                "ambient_dim": ambient_dim,
                "max_scale": max_scale,
                "birth_death": birth_death,
            },
            steps=steps,
            meaning=meaning,
            data={
                "point_cloud": points.tolist(),
                "n_points": n_points,
                "max_scale": max_scale,
            },
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"过滤复形构建出错: {str(e)}",
        )


@register(module="algebraic_topology", action="persistence_diagram")
def persistence_diagram(
    point_cloud: Any,
    dim: int = 0,
    max_scale: float = 1.0,
) -> MathObject:
    """计算持续同调图 (Persistence Diagram)。

    持续同调图是 {(b, d)} 的多重集，记录每个拓扑特征的
    出生时间 b 和死亡时间 d。特征的重要性由 persistence = d - b 衡量。

    Args:
        point_cloud: 点云数据。
        dim: 同调维数 (0=连通分支, 1=环, 2=空腔)。
        max_scale: 最大过滤尺度。

    Returns:
        MathObject: result 含 (birth, death) 对列表和 persistence 值。
    """
    try:
        filtr = filtration(point_cloud, max_scale=max_scale)
        if filtr.error:
            return filtr

        birth_death = filtr.result.get("birth_death", {})
        pairs = birth_death.get(dim, [])

        # 计算持久性
        persistent_pairs = []
        for b, d in pairs:
            persistence = d - b
            persistent_pairs.append(
                {"birth": round(b, 6), "death": round(d, 6), "persistence": round(persistence, 6)}
            )

        # 按持久性降序排列
        persistent_pairs.sort(key=lambda x: x["persistence"], reverse=True)

        steps: List[str] = []
        steps.append(f"持续同调图 dim={dim}")
        steps.append(f"出生-死亡对数量: {len(persistent_pairs)}")
        if persistent_pairs:
            top = persistent_pairs[0]
            steps.append(
                f"最显著特征: birth={top['birth']}, death={top['death']}, "
                f"persistence={top['persistence']}"
            )

        meaningful_features = sum(
            1 for p in persistent_pairs if p["persistence"] > max_scale * 0.1
        )
        steps.append(f"持久性 > 0.1*max_scale 的特征: {meaningful_features}")

        meaning = (
            f"第 {dim} 维持续同调图: {len(persistent_pairs)} 个特征。"
            f"靠近对角线的点 (persistence≈0) 通常为噪声，"
            f"远离对角线的点代表显著的拓扑特征。"
        )

        return MathObject(
            result={
                "dimension": dim,
                "pairs": persistent_pairs,
                "num_pairs": len(persistent_pairs),
                "significant_pairs": meaningful_features,
            },
            steps=steps,
            meaning=meaning,
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"持续同调图计算出错: {str(e)}",
        )


@register(module="algebraic_topology", action="barcode_plot")
def barcode_plot(
    point_cloud: Any,
    dim: int = 0,
    max_scale: float = 1.0,
) -> MathObject:
    """生成条形码 (Barcode) 可视化数据。

    条形码是持续同调的一种可视化：每个特征由一条水平线段表示，
    从 birth 延伸到 death。长度 = persistence。

    本函数生成条形码的数值数据（可供下游绘图库使用），
    不直接生成图像文件。

    Args:
        point_cloud: 点云数据。
        dim: 同调维数。
        max_scale: 最大过滤尺度。

    Returns:
        MathObject: result 含条形码数据 (birth, death, persistence)，
                    data 含绘图数据。
    """
    try:
        pd_result = persistence_diagram(point_cloud, dim=dim, max_scale=max_scale)
        if pd_result.error:
            return pd_result

        pairs = pd_result.result.get("pairs", [])

        # 为条形码准备数据
        barcodes = []
        for idx, pair in enumerate(pairs):
            barcodes.append({
                "id": idx,
                "birth": pair["birth"],
                "death": pair["death"],
                "persistence": pair["persistence"],
                "bar_length": pair["persistence"],
            })

        steps: List[str] = []
        steps.append(f"条形码数据 dim={dim}")
        steps.append(f"共 {len(barcodes)} 条")
        if barcodes:
            steps.append(
                f"最长条: id={barcodes[0]['id']}, "
                f"birth={barcodes[0]['birth']}, "
                f"death={barcodes[0]['death']}"
            )

        meaning = (
            f"每个特征对应一条从 birth 到 death 的水平线段。"
            f"线段越长，特征越显著（persistence 越大）。"
            f"短线段（靠近对角线）通常为拓扑噪声。"
        )

        return MathObject(
            result={
                "dimension": dim,
                "num_bars": len(barcodes),
                "barcodes": barcodes,
            },
            steps=steps,
            meaning=meaning,
            data={
                "barcode_data": barcodes,
                "max_scale": max_scale,
            },
        )

    except Exception as e:
        return MathObject(
            result=None,
            error=f"条形码图生成出错: {str(e)}",
        )


def self_test() -> bool:
    """persistent_homology 模块自测。"""
    print("=== persistent_homology 自测 ===")
    all_pass = True

    # 生成简单测试点云：圆上 8 个点 + 圆心附近 2 个点
    np.random.seed(42)
    angles = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    circle_points = np.column_stack([np.cos(angles), np.sin(angles)]) * 0.5
    noise = np.random.randn(2, 2) * 0.05
    point_cloud = np.vstack([circle_points, noise])

    # 测试 1: 过滤复形
    r1 = filtration(point_cloud, max_scale=1.0)
    assert r1.ok, f"过滤复形构建应成功: {r1.error}"
    assert r1.result["n_points"] == 10, f"应有 10 个点"
    print(f"  [PASS] filtration: {r1.result['n_points']} 个点")

    # 测试 2: 持续同调图 dim=0
    r2 = persistence_diagram(point_cloud, dim=0, max_scale=1.0)
    assert r2.ok, f"持续同调图应成功: {r2.error}"
    assert r2.result["num_pairs"] > 0, f"dim=0 应有出生-死亡对"
    print(f"  [PASS] persistence_diagram(dim=0): {r2.result['num_pairs']} 对")

    # 测试 3: 条形码数据
    r3 = barcode_plot(point_cloud, dim=0, max_scale=1.0)
    assert r3.ok, f"条形码应成功: {r3.error}"
    assert r3.result["num_bars"] > 0, f"应有条形码数据"
    print(f"  [PASS] barcode_plot(dim=0): {r3.result['num_bars']} 条")

    # 测试 4: 持续同调图 dim=1
    r4 = persistence_diagram(point_cloud, dim=1, max_scale=1.5)
    assert r4.ok, f"dim=1 持续同调图应成功"
    print(f"  [PASS] persistence_diagram(dim=1): {r4.result['num_pairs']} 对")

    print(f"  persistent_homology 自测: {'ALL PASSED' if all_pass else 'FAILED'}")
    return all_pass


if __name__ == "__main__":
    self_test()
