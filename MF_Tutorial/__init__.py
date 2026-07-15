# -*- coding: utf-8 -*-
"""MF_Tutorial — 新手教程系统。

提供四种教程形式：
  - WelcomeDialog: 首次启动介绍
  - GuidedWalkthrough: 交互式逐步引导
  - HelpBrowser: 内置帮助文档
  - ExampleLibrary: 示例任务库

所有形式共用 TutorialEngine 和统一 YAML 教程内容。

用法:
    from MF_Tutorial import TutorialEngine

    engine = TutorialEngine()
    engine.load_all()
    progress = engine.get_progress()
"""

from __future__ import annotations

from MF_Tutorial.models import (
    Tutorial, Step, Example, FAQ, TutorialProgress,
    Difficulty, Category, HighlightShape, Placement, ActionType,
)
from MF_Tutorial.engine import TutorialEngine

__all__ = [
    # 引擎
    "TutorialEngine",
    # 数据模型
    "Tutorial", "Step", "Example", "FAQ", "TutorialProgress",
    # 类型别名
    "Difficulty", "Category", "HighlightShape", "Placement", "ActionType",
]


# ═══════════════════════════════════════════════════════════════
#  self_test
# ═══════════════════════════════════════════════════════════════

def self_test() -> tuple[int, int, list[str]]:
    """运行所有子模块的 self_test。"""
    total_passed, total_failed = 0, 0
    all_errors: list[str] = []

    modules = [
        ("engine", "MF_Tutorial.engine"),
        ("overlay", "MF_Tutorial.overlay"),
        ("welcome_dialog", "MF_Tutorial.welcome_dialog"),
        ("walkthrough", "MF_Tutorial.walkthrough"),
        ("help_browser", "MF_Tutorial.help_browser"),
        ("example_library", "MF_Tutorial.example_library"),
    ]

    print("=" * 60)
    print("MF_Tutorial 包级 self_test")
    print("=" * 60)

    for name, module_path in modules:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            if hasattr(mod, 'self_test'):
                p, f, e = mod.self_test()
                total_passed += p
                total_failed += f
                all_errors.extend(e)
                print(f"  [{name}] {p} passed, {f} failed")
            else:
                print(f"  [{name}] 无 self_test, 跳过")
        except Exception as e:
            total_failed += 1
            all_errors.append(f"{name}: {e}")
            print(f"  [{name}] ERROR: {e}")

    print(f"\n总计: {total_passed} passed, {total_failed} failed")
    if all_errors:
        for e in all_errors:
            print(f"  [ERROR] {e}")
    print("=" * 60)
    return total_passed, total_failed, all_errors


if __name__ == "__main__":
    self_test()
