"""set_systems.py — 集合系。

涵盖σ-代数判定、最小σ-代数生成、Borel σ-代数等集合系基础概念。
"""

from __future__ import annotations

from itertools import combinations, product
from typing import Any, FrozenSet, List, Set, Tuple, Union

import sympy as sp

from ..core.math_object import MathObject
from ..core.registry import register


def _to_set_of_frozensets(
    collection: Union[List[Set], List[FrozenSet], List[List]],
    X: Union[Set, FrozenSet, List],
) -> Tuple[Set[FrozenSet], Set]:
    """将输入归一化为 frozenset 集合与全域集合。"""
    X_set = set(X) if not isinstance(X, (set, frozenset)) else set(X)
    coll_frozen: Set[FrozenSet] = set()
    for s in collection:
        if isinstance(s, (set, frozenset)):
            coll_frozen.add(frozenset(s))
        elif isinstance(s, list):
            coll_frozen.add(frozenset(s))
        else:
            raise TypeError(f"集合系元素类型错误: {type(s)}")
    return coll_frozen, X_set


def _complement(fs: FrozenSet, X_set: Set) -> FrozenSet:
    """计算 fs 在 X_set 中的补集。"""
    return frozenset(X_set - set(fs))


@register(module="measure_theory", action="is_sigma_algebra")
def is_sigma_algebra(
    collection: Union[List[Set], List[FrozenSet], List[List]],
    X: Union[Set, FrozenSet, List],
) -> MathObject:
    """验证给定的集合系是否为 (X 上的) σ-代数。

    σ-代数必须满足：
    1. 包含空集 ∅ 和全集 X。
    2. 对可数并封闭（此处近似为对有限并封闭，并验证可数性的概念）。
    3. 对补集封闭（相对于 X）。

    由于离散数学中"可数并"难以完全实现，本函数采用
    有限并 + 概念性判定：如果集合系有限且满足上述封闭性，
    则判定为 σ-代数。

    Args:
        collection: 集合系，每个元素为 set/frozenset/list。
        X: 全集。

    Returns:
        MathObject: result=True/False，含判定步骤和理由。
    """
    try:
        coll, X_set = _to_set_of_frozensets(collection, X)
        steps: List[str] = []
        X_fs = frozenset(X_set)
        empty_fs = frozenset()

        # 1. 包含空集和全集
        has_empty = empty_fs in coll
        has_full = X_fs in coll
        steps.append(f"检查空集: {'是' if has_empty else '否'}")
        steps.append(f"检查全集: {'是' if has_full else '否'}")

        if not has_empty or not has_full:
            return MathObject(
                result=False,
                steps=steps,
                meaning="缺少空集或全集 → 非 σ-代数",
            )

        # 2. 补封闭
        complement_ok = True
        for s in coll:
            comp = _complement(s, X_set)
            if comp not in coll:
                complement_ok = False
                steps.append(f"补集缺失: {set(s)} 的补集 {set(comp)} 不在集合系中")
                break
        if complement_ok:
            steps.append("补集封闭: 通过")

        # 3. 有限并封闭（可数并的近似）
        union_ok = True
        coll_list = list(coll)
        # 测试所有二元并
        for i in range(len(coll_list)):
            for j in range(i, len(coll_list)):
                u = frozenset(set(coll_list[i]) | set(coll_list[j]))
                if u not in coll:
                    union_ok = False
                    steps.append(
                        f"并集缺失: {set(coll_list[i])} ∪ {set(coll_list[j])} = {set(u)} 不在集合系中"
                    )
                    break
            if not union_ok:
                break
        if union_ok:
            steps.append("有限并封闭: 通过")

        is_sigma = complement_ok and union_ok and has_empty and has_full
        return MathObject(
            result=is_sigma,
            steps=steps,
            meaning=f"{'是' if is_sigma else '不是'} X 上的 σ-代数",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="generate_sigma_algebra")
def generate_sigma_algebra(
    sets: Union[List[Set], List[FrozenSet], List[List]],
    X: Union[Set, FrozenSet, List, None] = None,
) -> MathObject:
    """生成包含给定集合的最小 σ-代数（有限情况精确构造）。

    对于有限全集，通过反复添加补集和有限并直到封闭。
    如果 X 未给出，默认取所有给定集合元素的并作为全集。

    Args:
        sets: 生成元集合列表。
        X: 全集（可选），默认使用生成元的并。

    Returns:
        MathObject: result 为 frozenset 的 frozen set（最小 σ-代数）。
    """
    try:
        input_coll = set()
        for s in sets:
            if isinstance(s, (set, frozenset)):
                input_coll.add(frozenset(s))
            elif isinstance(s, list):
                input_coll.add(frozenset(s))

        if X is None:
            # 自动推断全集
            all_elements = set()
            for fs in input_coll:
                all_elements.update(fs)
            X_set = all_elements
        else:
            X_set = set(X) if not isinstance(X, (set, frozenset)) else set(X)

        X_fs = frozenset(X_set)
        empty_fs = frozenset()

        # 迭代直到封闭
        sigma = {empty_fs, X_fs} | input_coll
        changed = True
        max_iter = 10
        iteration = 0

        while changed and iteration < max_iter:
            changed = False
            iteration += 1
            # 补封闭
            for s in list(sigma):
                comp = _complement(s, X_set)
                if comp not in sigma:
                    sigma.add(comp)
                    changed = True
            # 并封闭
            sigma_list = list(sigma)
            for i in range(len(sigma_list)):
                for j in range(i, len(sigma_list)):
                    u = frozenset(set(sigma_list[i]) | set(sigma_list[j]))
                    if u not in sigma:
                        sigma.add(u)
                        changed = True

        # 转为可读列表
        readable = sorted([sorted(fs) for fs in sigma], key=lambda x: (len(x), x))

        return MathObject(
            result=readable,
            steps=[
                f"生成元: {[sorted(fs) for fs in input_coll]}",
                f"全集 X = {sorted(X_set)}",
                f"迭代 {iteration} 轮后封闭",
                f"共 {len(sigma)} 个集合",
            ],
            meaning="包含给定生成元的最小 σ-代数",
        )

    except Exception as e:
        return MathObject(error=str(e))


@register(module="measure_theory", action="borel_sigma_algebra")
def borel_sigma_algebra(
    space: Union[str, Tuple[float, float], List[float]],
) -> MathObject:
    """生成 Borel σ-代数（概念性描述与有限近似构造）。

    Borel σ-代数 B(R) 是实数轴 R 上由所有开区间生成的 σ-代数。
    对于有限离散空间，可精确构造；对于连续区间，给出开区间生成元
    并做概念性说明。

    Args:
        space: 空间描述：
            - "R" 或 "real": 实数轴（概念性）。
            - (a, b): 区间内的离散整点。
            - [1,2,3,...]: 离散点集。

    Returns:
        MathObject: result 为生成的 Borel σ-代数（离散情况）或生成元说明。
    """
    try:
        if isinstance(space, str):
            if space.lower() in ("r", "real", "实数"):
                generators = [
                    ("开区间 (a, b)", "所有 a < b"),
                    ("闭区间 [a, b]", "可表为可数个开区间的交"),
                    ("单点集 {x}", "可表为可数个开区间的交"),
                    ("有理区间 (q, r)", "q, r ∈ Q 的可数生成元族"),
                ]
                return MathObject(
                    result="B(R) — 实数轴上的 Borel σ-代数",
                    steps=[f"生成元: {g[0]} — {g[1]}" for g in generators],
                    meaning="由 R 上所有开区间生成的最小 σ-代数，是最重要的可测空间之一",
                )

        # 离散情况
        if isinstance(space, tuple) and len(space) == 2:
            elements = list(range(int(space[0]), int(space[1]) + 1))
        elif isinstance(space, list):
            elements = space
        else:
            elements = list(range(5))

        # 生成所有开区间（离散情况：每个点生成开区间即单点集邻域）
        open_intervals = []
        for i in range(len(elements)):
            # 对每个元素生成一个含该元素的"开区间"
            for j in range(i + 1, len(elements) + 1):
                open_intervals.append(elements[i:j])

        # 用开区间生成 σ-代数
        return generate_sigma_algebra(open_intervals, X=elements)

    except Exception as e:
        return MathObject(error=str(e))


def self_test() -> bool:
    """set_systems 模块自测。"""
    print("=== set_systems self_test ===")
    all_ok = True

    # 测试 1: 标准 σ-代数
    X = {1, 2, 3}
    coll = [set(), X, {1}, {2, 3}, {2}, {1, 3}, {3}, {1, 2}]
    r = is_sigma_algebra(coll, X)
    assert r.ok and r.result is True, f"失败: {r}"
    print(f"  [PASS] is_sigma_algebra 标准 σ-代数: {r.result}")

    # 测试 2: 非 σ-代数
    coll2 = [set(), X, {1}]
    r = is_sigma_algebra(coll2, X)
    assert r.ok and r.result is False, f"失败: {r}"
    print(f"  [PASS] is_sigma_algebra 非 σ-代数: {r.result}")

    # 测试 3: generate_sigma_algebra
    r = generate_sigma_algebra([{1}], X={1, 2})
    assert r.ok and len(r.result) == 4, f"失败: {r}"
    print(f"  [PASS] generate_sigma_algebra: {r.result}")

    # 测试 4: borel_sigma_algebra 概念性
    r = borel_sigma_algebra("R")
    assert r.ok, f"失败: {r}"
    print(f"  [PASS] borel_sigma_algebra(R): {r.result}")

    # 测试 5: borel_sigma_algebra 离散
    r = borel_sigma_algebra((0, 2))
    assert r.ok, f"失败: {r}"
    print(f"  [PASS] borel_sigma_algebra((0,2)): {len(r.result)} 个集合")

    print("=== set_systems: ALL PASSED ===\n")
    return all_ok


if __name__ == "__main__":
    self_test()
