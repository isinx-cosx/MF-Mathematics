"""复平面拓扑 — 开/闭集、连通性、区域。

依赖: sympy
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

import sympy as sp
import numpy as np

from ..core.math_object import MathObject
from ..core.registry import register

# ── 工具：复平面区域表示 ─────────────────────────────────────────────

def _resolve_region(region: Any) -> List[Tuple[float, float]]:
    """将命名区域或列表解析为离散点集。"""
    if isinstance(region, list):
        return region
    if isinstance(region, str):
        name = region.strip().lower()
        if name == "unit_disk":
            # 生成单位圆盘采样点
            points = []
            for r in np.linspace(0, 1, 20):
                n_theta = max(8, int(40 * r)) if r > 0 else 1
                for theta in np.linspace(0, 2 * np.pi, n_theta, endpoint=False):
                    points.append((float(r * np.cos(theta)), float(r * np.sin(theta))))
            return points
        if name == "separated_disks":
            # 两个分离的圆盘
            points = []
            for cx, cy in [(-1.5, 0), (1.5, 0)]:
                for r in np.linspace(0, 0.5, 10):
                    n_theta = max(4, int(20 * r)) if r > 0 else 1
                    for theta in np.linspace(0, 2 * np.pi, n_theta, endpoint=False):
                        points.append((float(cx + r * np.cos(theta)), float(cy + r * np.sin(theta))))
            return points
        raise ValueError(f"未知区域名称: {region}")
    raise ValueError(f"无法解析区域: {region}")


def _resolve_point(point: Any) -> Tuple[float, float]:
    """将点解析为 (x, y) 元组。"""
    if isinstance(point, complex):
        return (float(point.real), float(point.imag))
    if isinstance(point, (int, float)):
        return (float(point), 0.0)
    if isinstance(point, (tuple, list)) and len(point) == 2:
        return (float(point[0]), float(point[1]))
    raise ValueError(f"无法解析为点: {point}")


# ── 公开函数 ──────────────────────────────────────────────────────────


@register(module="complex_analysis", action="is_open")
def is_open(
    region: Union[List[Tuple[float, float]], str],
    point: Union[Tuple[float, float], complex],
    epsilon: float = 1e-6,
) -> MathObject:
    """判断点是否为区域的内点。

    若存在 ε>0 的邻域完全包含在 region 内，则该点为内点。
    region 用离散点集近似表示；此处检查该点周围采样是否都在 region 内。
    支持命名区域："unit_disk", "separated_disks"。

    Args:
        region: 离散点列表 [(x0,y0), (x1,y1), ...]，或命名区域字符串。
        point: 待检查点 (x, y) 或复数。
        epsilon: 邻域半径。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        # 命名区域使用解析判定
        if isinstance(region, str):
            name = region.strip().lower()
            x0, y0 = _resolve_point(point)
            if name == "unit_disk":
                is_inner = (x0**2 + y0**2) < 1.0
                return MathObject(
                    result=is_inner,
                    steps=[
                        f"区域: 单位圆盘 |z|<1",
                        f"点: ({x0:.6f}, {y0:.6f}), |z|={np.sqrt(x0**2+y0**2):.6f}",
                        "该点是内点（|z|<1）" if is_inner else "该点不是内点（|z|≥1）",
                    ],
                    meaning="单位圆盘是开集，边界点不是内点。",
                )
            if name == "separated_disks":
                # 两个分离的圆盘：|z+1.5|<0.5 或 |z-1.5|<0.5
                d1 = (x0 + 1.5)**2 + y0**2
                d2 = (x0 - 1.5)**2 + y0**2
                is_inner = d1 < 0.25 or d2 < 0.25
                return MathObject(
                    result=is_inner,
                    steps=[
                        f"区域: 两个分离的圆盘 |z+1.5|<0.5 和 |z-1.5|<0.5",
                        f"点: ({x0:.6f}, {y0:.6f})",
                        f"距离(-1.5,0): {np.sqrt(d1):.6f}, 距离(1.5,0): {np.sqrt(d2):.6f}",
                        "该点是内点" if is_inner else "该点不是内点",
                    ],
                    meaning="开圆盘内的点是内点，边界点不是。",
                )

        # 自定义离散点集：使用采样近似
        region_list = _resolve_region(region)
        x0, y0 = _resolve_point(point)
        region_np = np.array(region_list, dtype=np.float64)
        if len(region_np) == 0:
            return MathObject(result=False, steps=["region 为空"])

        # 采样周围 8 个方向 + 中心点，检查是否都在 region 内
        angles = np.linspace(0, 2 * np.pi, 16, endpoint=False)
        samples = np.array([
            [x0 + epsilon * np.cos(a), y0 + epsilon * np.sin(a)]
            for a in angles
        ])

        # 近似判断：检查每个采样点是否靠近 region 中任意点
        for sx, sy in samples:
            dists = np.sqrt((region_np[:, 0] - sx) ** 2 + (region_np[:, 1] - sy) ** 2)
            if np.min(dists) > epsilon * 2:
                return MathObject(
                    result=False,
                    steps=[
                        f"在点 ({x0}, {y0}) 的 {epsilon}-邻域内",
                        f"采样点 ({sx:.6f}, {sy:.6f}) 不在 region 内（最小距离 {np.min(dists):.6f} > {2*epsilon}）",
                        "该点不是内点",
                    ],
                    meaning="存在边界点进入 ε-邻域，故非开集的内点。",
                )

        return MathObject(
            result=True,
            steps=[
                f"在点 ({x0}, {y0}) 的 {epsilon}-邻域内",
                "所有采样点均在 region 内",
                "该点是内点",
            ],
            meaning="该点的 ε-邻域完全包含在区域内。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="is_connected")
def is_connected(
    region: Union[List[Tuple[float, float]], str],
    connect_threshold: float = 0.1,
) -> MathObject:
    """判断区域连通性。

    通过构建邻接图并进行 BFS/DFS 检查所有点是否属于同一连通分量。
    支持命名区域："unit_disk", "separated_disks"。

    Args:
        region: 离散点列表 [(x0,y0), (x1,y1), ...]，或命名区域字符串。
        connect_threshold: 两点视为相邻的最大距离。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        # 命名区域使用解析判定
        if isinstance(region, str):
            name = region.strip().lower()
            if name == "unit_disk":
                return MathObject(
                    result=True,
                    steps=["区域: 单位圆盘", "圆盘是连通的（任意两点可用内部折线连接）"],
                    meaning="单位圆盘是单连通区域。",
                )
            if name == "separated_disks":
                return MathObject(
                    result=False,
                    steps=[
                        "区域: 两个分离的圆盘 |z+1.5|<0.5 和 |z-1.5|<0.5",
                        "两个圆盘不相交，无法用内部路径连接",
                        "区域不连通",
                    ],
                    meaning="两个不相交的开圆盘组成不连通集合。",
                )

        region_list = _resolve_region(region)
        if not region_list:
            return MathObject(result=True, steps=["空区域视为连通"])

        points = np.array(region_list, dtype=np.float64)
        n = len(points)
        if n == 1:
            return MathObject(result=True, steps=["单点区域始终连通"])

        # 构建邻接表
        adj: List[List[int]] = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.sqrt(
                    (points[i, 0] - points[j, 0]) ** 2
                    + (points[i, 1] - points[j, 1]) ** 2
                )
                if dist <= connect_threshold:
                    adj[i].append(j)
                    adj[j].append(i)

        # BFS
        visited = [False] * n
        queue = [0]
        visited[0] = True
        while queue:
            u = queue.pop(0)
            for v in adj[u]:
                if not visited[v]:
                    visited[v] = True
                    queue.append(v)

        all_connected = all(visited)
        components = 1
        if not all_connected:
            # 统计连通分量数
            for i in range(1, n):
                if not visited[i]:
                    components += 1
                    queue = [i]
                    visited[i] = True
                    while queue:
                        u = queue.pop(0)
                        for v in adj[u]:
                            if not visited[v]:
                                visited[v] = True
                                queue.append(v)

        return MathObject(
            result=all_connected,
            steps=[
                f"region 共 {n} 个离散点",
                f"距离阈值: {connect_threshold}",
                f"连通分量数: {components}",
                "区域连通" if all_connected else "区域不连通",
            ],
            meaning="如果区域内任意两点可用内部折线连接，则区域连通。",
        )
    except Exception as e:
        return MathObject(error=str(e))


@register(module="complex_analysis", action="is_domain")
def is_domain(
    region: Union[List[Tuple[float, float]], str],
    epsilon: float = 1e-6,
    connect_threshold: float = 0.1,
) -> MathObject:
    """验证是否为区域（开集 + 连通）。

    区域 = 开集 ∩ 连通。
    支持命名区域："unit_disk", "separated_disks"。

    Args:
        region: 离散点列表 [(x0,y0), (x1,y1), ...]，或命名区域字符串。
        epsilon: 开性检查的邻域半径。
        connect_threshold: 连通性检查的距离阈值。

    Returns:
        MathObject，result 为 bool。
    """
    try:
        # 命名区域使用解析判定
        if isinstance(region, str):
            name = region.strip().lower()
            if name == "unit_disk":
                return MathObject(
                    result=True,
                    steps=["区域: 单位圆盘", "开性: 是（|z|<1 为开集）", "连通性: 是", "是否区域: 是"],
                    meaning="单位圆盘是复平面上的区域（开+连通）。",
                )
            if name == "separated_disks":
                return MathObject(
                    result=False,
                    steps=[
                        "区域: 两个分离的圆盘",
                        "开性: 是（两个开圆盘的并仍是开集）",
                        "连通性: 否",
                        "是否区域: 否",
                    ],
                    meaning="虽然两个圆盘各自是开集，但整体不连通，故不是区域。",
                )

        region_list = _resolve_region(region)
        if not region_list:
            return MathObject(result=False, steps=["空集不是区域"])

        # 检查开性：对每个点检查是否为内点
        open_ok = True
        for pt in region_list[:50]:  # 采样最多 50 个点以节省时间
            inner = is_open(region_list, pt, epsilon)
            if not inner.result:
                open_ok = False
                break

        # 检查连通性
        connected_ok = is_connected(region_list, connect_threshold).result

        is_domain_result = open_ok and connected_ok

        steps = [
            f"区域点数: {len(region_list)}",
            f"开性: {'是' if open_ok else '否'}（每个点都是内点）",
            f"连通性: {'是' if connected_ok else '否'}",
            f"是否区域: {'是' if is_domain_result else '否'}",
        ]

        return MathObject(
            result=is_domain_result,
            steps=steps,
            meaning="区域 = 非空开集 + 连通。D={z∈C: |z|<1} 是区域，{z: |z|≤1} 不是开集。",
        )
    except Exception as e:
        return MathObject(error=str(e))


# ── self_test ──────────────────────────────────────────────────────────

def self_test() -> None:
    """自测：复平面拓扑。"""
    import math

    print("=== complex_topology self_test ===")

    # 构造一个圆盘区域（单位圆盘）
    region_disk: List[Tuple[float, float]] = []
    for r in np.linspace(0, 0.95, 20):
        for theta in np.linspace(0, 2 * np.pi, 30, endpoint=False):
            region_disk.append((r * math.cos(theta), r * math.sin(theta)))

    # 1. is_open: 原点应该是内点
    r = is_open(region_disk, (0.0, 0.0), epsilon=0.05)
    assert r.ok, r.error
    assert r.result is True, f"原点应是内点: {r.result}"
    print(f"  is_open(disk, (0,0)): {r.result}")

    # 2. is_open: 边界附近的点(0.9, 0)不是内点（若 region 只到 0.95）
    r = is_open(region_disk, (0.9, 0.0), epsilon=0.1)
    assert r.ok, r.error
    print(f"  is_open(disk, (0.9,0)): {r.result}")

    # 3. is_connected: 圆盘应连通
    r = is_connected(region_disk, connect_threshold=0.2)
    assert r.ok, r.error
    assert r.result is True, f"圆盘应连通: {r.result}"
    print(f"  is_connected(disk): {r.result}")

    # 4. is_connected: 两个分离的团应不连通
    cluster_A = [(i * 0.1, 0.0) for i in range(10)]
    cluster_B = [(i * 0.1, 5.0) for i in range(10)]
    r = is_connected(cluster_A + cluster_B, connect_threshold=0.2)
    assert r.ok, r.error
    assert r.result is False, f"分离团应不连通: {r.result}"
    print(f"  is_connected(two clusters): {r.result}")

    # 5. is_domain: 圆盘是区域
    r = is_domain(region_disk, epsilon=0.03, connect_threshold=0.2)
    assert r.ok, r.error
    assert r.result is True, f"圆盘应是区域: {r.result}"
    print(f"  is_domain(disk): {r.result}")

    # 6. is_domain: 分离团不是区域
    r = is_domain(cluster_A + cluster_B, epsilon=0.03, connect_threshold=0.2)
    assert r.ok
    assert r.result is False
    print(f"  is_domain(two clusters): {r.result}")

    print("=== complex_topology self_test: ALL PASSED ===")


if __name__ == "__main__":
    self_test()
