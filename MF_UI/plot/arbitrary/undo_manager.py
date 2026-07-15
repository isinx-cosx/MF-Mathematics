# -*- coding: utf-8 -*-
"""撤销/重做管理器 — 全量形状列表快照。

在每次变更前调用 push() 存储当前状态。
undo() / redo() 返回上一个/下一个状态。
最大深度 50 级，超出时丢弃最旧记录。
"""

from __future__ import annotations

import copy
from MF_UI.plot.arbitrary.shapes import GeometricShape


class UndoManager:
    """全量快照式撤销/重做栈。

    用法:
        manager = UndoManager()
        manager.push(shapes)        # 变更前快照
        ...
        prev = manager.undo(curr)   # Undo → 返回旧状态
        next_ = manager.redo(curr)  # Redo → 返回重做状态
    """

    def __init__(self, max_depth: int = 50):
        self._undo: list[list[GeometricShape]] = []
        self._redo: list[list[GeometricShape]] = []
        self._max_depth = max_depth

    def push(self, shapes: list[GeometricShape]) -> None:
        """存储当前状态。推入后清空 redo 栈。"""
        snapshot = [copy.deepcopy(s) for s in shapes]
        self._undo.append(snapshot)
        if len(self._undo) > self._max_depth:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self, current: list[GeometricShape]) -> list[GeometricShape] | None:
        """撤销一步。将 current 推入 redo，返回 undo 栈顶。"""
        if not self._undo:
            return None
        self._redo.append([copy.deepcopy(s) for s in current])
        return self._undo.pop()

    def redo(self, current: list[GeometricShape]) -> list[GeometricShape] | None:
        """重做一步。将 current 推入 undo，返回 redo 栈顶。"""
        if not self._redo:
            return None
        self._undo.append([copy.deepcopy(s) for s in current])
        return self._redo.pop()

    @property
    def can_undo(self) -> bool:
        return len(self._undo) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo) > 0

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()


# ── 自测 ──────────────────────────────────────────────────

def self_test() -> str:
    """运行 undo_manager 自测。"""
    from MF_UI.plot.arbitrary.shapes import ShapeType, create_shape

    ok = 0; fail = 0
    mgr = UndoManager(max_depth=3)

    # 1. 空栈不能 undo/redo
    assert mgr.undo([]) is None; ok += 1
    assert mgr.redo([]) is None; ok += 1

    # 2. push → undo → redo
    s1 = [create_shape(ShapeType.POINT, (0, 0))]
    mgr.push(s1)
    assert mgr.can_undo; ok += 1
    assert not mgr.can_redo; ok += 1

    # 3. undo 返回 s1
    s2 = [create_shape(ShapeType.POINT, (1, 1))]
    prev = mgr.undo(s2)
    assert prev is not None and len(prev) == 1; ok += 1
    assert prev[0].data == (0, 0); ok += 1
    assert mgr.can_redo; ok += 1

    # 4. redo 返回 s2
    curr = mgr.redo(prev)
    assert curr is not None and len(curr) == 1; ok += 1
    assert curr[0].data == (1, 1); ok += 1

    # 5. push 后 redo 清空
    mgr.push(s2)
    assert not mgr.can_redo; ok += 1

    # 6. 超出 max_depth 丢弃最旧
    for i in range(5):
        mgr.push([create_shape(ShapeType.POINT, (float(i), 0))])
    assert len(mgr._undo) == 3, f"应有 3，实际 {len(mgr._undo)}"; ok += 1

    # 7. clear
    mgr.clear()
    assert not mgr.can_undo and not mgr.can_redo; ok += 1

    print(f"[PASS] undo_manager: {ok} 通过, {fail} 失败")
    return f"{ok} pass, {fail} fail"


if __name__ == "__main__":
    self_test()
