# -*- coding: utf-8 -*-
"""TutorialEngine — 教程引擎单例，统一管理教程数据与用户进度。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from MF_Tutorial.models import (
    Tutorial, Step, Example, FAQ, TutorialProgress,
    Difficulty, Category,
)

# ── 进度文件路径 ──────────────────────────────────────────────

def _progress_path() -> str:
    root = Path(__file__).parent.parent
    return str(root / "tutorial_progress.json")


def _tutorials_dir() -> str:
    return str(Path(__file__).parent / "tutorials")


# ═══════════════════════════════════════════════════════════════
#  TutorialEngine
# ═══════════════════════════════════════════════════════════════

class TutorialEngine:
    """教程引擎 — 模块级单例。

    职责:
      - 加载 tutorials/ 下所有 YAML 文件
      - 按 ID / 分类 / 难度查询
      - 追踪用户进度（tutorial_progress.json）
      - 判断首次启动

    用法:
        engine = TutorialEngine()
        engine.load_all()
        tutorials = engine.list_by(category="calculation", difficulty="beginner")
    """

    _instance: TutorialEngine | None = None

    def __new__(cls) -> TutorialEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._tutorials: dict[str, Tutorial] = {}
        self._progress: TutorialProgress = TutorialProgress()
        self._load_progress()

    # ── 加载教程 ──────────────────────────────────────────

    def load_all(self) -> list[Tutorial]:
        """加载 tutorials/ 下所有 YAML 文件。

        Returns:
            按 order 排序的教程列表。
        """
        tut_dir = Path(_tutorials_dir())
        if not tut_dir.exists():
            return []

        loaded: list[Tutorial] = []
        for yaml_file in sorted(tut_dir.glob("*.yaml")):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                tutorial = self._parse_tutorial(data)
                self._tutorials[tutorial.id] = tutorial
                loaded.append(tutorial)
            except (yaml.YAMLError, KeyError, TypeError) as e:
                print(f"[TutorialEngine] 加载 {yaml_file.name} 失败: {e}")

        loaded.sort(key=lambda t: t.order)
        return loaded

    def reload(self) -> list[Tutorial]:
        """重新加载所有教程（内容更新后调用）。"""
        self._tutorials.clear()
        return self.load_all()

    # ── 查询 ──────────────────────────────────────────────

    def get(self, tutorial_id: str) -> Tutorial | None:
        """按 ID 获取教程。"""
        return self._tutorials.get(tutorial_id)

    def list_by(
        self,
        category: Category | None = None,
        difficulty: Difficulty | None = None,
    ) -> list[Tutorial]:
        """按分类和/或难度筛选，按 order 排序。

        Args:
            category: 分类筛选。None 表示不过滤。
            difficulty: 难度筛选。None 表示不过滤。

        Returns:
            匹配的教程列表。
        """
        result = list(self._tutorials.values())
        if category:
            result = [t for t in result if t.category == category]
        if difficulty:
            result = [t for t in result if t.difficulty == difficulty]
        result.sort(key=lambda t: t.order)
        return result

    def get_all(self) -> list[Tutorial]:
        """获取全部教程，按 order 排序。"""
        return sorted(self._tutorials.values(), key=lambda t: t.order)

    def get_categories(self) -> list[Category]:
        """获取所有分类。"""
        seen: set[Category] = set()
        for t in self._tutorials.values():
            seen.add(t.category)
        return sorted(seen, key=lambda c: {
            "general": 0, "calculation": 1, "plot": 2,
            "ai": 3, "tools": 4, "settings": 5,
        }.get(c, 99))

    def get_next_uncompleted(self) -> Tutorial | None:
        """获取下一篇未完成的教程。"""
        for t in self.get_all():
            if t.id not in self._progress.completed:
                return t
        return None

    # ── 进度管理 ──────────────────────────────────────────

    def mark_completed(self, tutorial_id: str) -> None:
        """标记某篇教程为已完成。"""
        if tutorial_id not in self._progress.completed:
            self._progress.completed.append(tutorial_id)
            self._save_progress()

    def mark_incomplete(self, tutorial_id: str) -> None:
        """取消完成标记（允许重新学习）。"""
        if tutorial_id in self._progress.completed:
            self._progress.completed.remove(tutorial_id)
            self._save_progress()

    def is_completed(self, tutorial_id: str) -> bool:
        """检查教程是否已完成。"""
        return tutorial_id in self._progress.completed

    def set_last_tutorial(self, tutorial_id: str) -> None:
        """记录上次浏览的教程。"""
        self._progress.last_tutorial = tutorial_id
        self._save_progress()

    def get_progress(self) -> dict:
        """获取全局进度快照。

        Returns:
            {"total": int, "completed": int, "percent": float}
        """
        total = len(self._tutorials)
        done = len([cid for cid in self._progress.completed
                     if cid in self._tutorials])
        percent = round(done / total * 100, 1) if total > 0 else 0.0
        return {"total": total, "completed": done, "percent": percent}

    # ── 首次启动 ──────────────────────────────────────────

    def is_first_launch(self) -> bool:
        """是否首次启动（未完成首次介绍）。"""
        return not self._progress.first_launch_done

    def mark_launched(self) -> None:
        """标记已完成首次启动介绍。"""
        self._progress.first_launch_done = True
        self._progress.launch_count += 1
        self._save_progress()

    def get_launch_count(self) -> int:
        """获取启动次数。"""
        return self._progress.launch_count

    # ── 快速操作 ──────────────────────────────────────────

    def load_example(
        self, tutorial_id: str, example_index: int = 0
    ) -> Example | None:
        """获取指定教程的示例，供调用方加载到工作区。

        Args:
            tutorial_id: 教程 ID。
            example_index: 示例索引。

        Returns:
            Example 对象，不存在则返回 None。
        """
        tutorial = self.get(tutorial_id)
        if not tutorial:
            return None
        if 0 <= example_index < len(tutorial.examples):
            return tutorial.examples[example_index]
        return None

    # ── 内部 ──────────────────────────────────────────────

    def _parse_tutorial(self, data: dict) -> Tutorial:
        """将 YAML dict 解析为 Tutorial 对象。"""
        steps = [
            Step(
                target=s.get("target", ""),
                text=s.get("text", ""),
                highlight=s.get("highlight", "rect"),
                placement=s.get("placement", "bottom"),
                action=s.get("action"),
                action_value=s.get("action_value", ""),
                image=s.get("image", ""),
            )
            for s in data.get("steps", [])
        ]

        examples = [
            Example(
                label=e.get("label", ""),
                expr=e.get("expr", ""),
                mode=e.get("mode", ""),
                action=e.get("action", ""),
                description=e.get("description", ""),
            )
            for e in data.get("examples", [])
        ]

        faq = [
            FAQ(q=f.get("q", ""), a=f.get("a", ""))
            for f in data.get("faq", [])
        ]

        return Tutorial(
            id=data.get("id", ""),
            title=data.get("title", ""),
            difficulty=data.get("difficulty", "beginner"),
            category=data.get("category", "general"),
            duration=data.get("duration", ""),
            order=data.get("order", 99),
            summary=data.get("summary", ""),
            steps=steps,
            examples=examples,
            faq=faq,
            prerequisites=data.get("prerequisites", []),
        )

    def _load_progress(self) -> None:
        """从 tutorial_progress.json 加载进度。"""
        path = _progress_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._progress = TutorialProgress(
                completed=data.get("completed", []),
                last_tutorial=data.get("last_tutorial", ""),
                first_launch_done=data.get("first_launch_done", False),
                launch_count=data.get("launch_count", 0),
            )
        except (FileNotFoundError, json.JSONDecodeError):
            self._progress = TutorialProgress()

    def _save_progress(self) -> None:
        """保存进度到 tutorial_progress.json。"""
        try:
            with open(_progress_path(), "w", encoding="utf-8") as f:
                json.dump({
                    "completed": self._progress.completed,
                    "last_tutorial": self._progress.last_tutorial,
                    "first_launch_done": self._progress.first_launch_done,
                    "launch_count": self._progress.launch_count,
                }, f, ensure_ascii=False, indent=2)
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """验证 TutorialEngine 基本功能。"""
    passed, failed = 0, 0
    errors: list[str] = []

    print("=== MF_Tutorial.engine self_test ===")

    engine = TutorialEngine()

    # 单例测试
    engine2 = TutorialEngine()
    assert engine is engine2, "TutorialEngine 应为单例"
    passed += 1

    # 默认状态
    progress = engine.get_progress()
    assert "total" in progress, "progress 应包含 total"
    assert "completed" in progress, "progress 应包含 completed"
    assert "percent" in progress, "progress 应包含 percent"
    passed += 1

    # 加载测试
    engine.load_all()
    all_tuts = engine.get_all()
    print(f"  已加载 {len(all_tuts)} 篇教程")
    passed += 1

    # 分类筛选
    for cat in engine.get_categories():
        cat_list = engine.list_by(category=cat)
        for t in cat_list:
            assert t.category == cat, f"教程 {t.id} 分类应为 {cat}"
    passed += 1

    # 进度标记
    if all_tuts:
        first = all_tuts[0]
        engine.mark_completed(first.id)
        assert engine.is_completed(first.id), "标记后应已完成"
        passed += 1

        engine.mark_incomplete(first.id)
        assert not engine.is_completed(first.id), "取消标记后应未完成"
        passed += 1

    print(f"  [PASS] {passed} passed, {failed} failed")
    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")
    print("=== MF_Tutorial.engine self_test: DONE ===\n")
    return passed, failed, errors


if __name__ == "__main__":
    self_test()
