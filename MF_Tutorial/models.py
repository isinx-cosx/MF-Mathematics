# -*- coding: utf-8 -*-
"""MF_Tutorial 数据模型 — Tutorial、Step、Example 等数据类。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ── 难度等级 ──────────────────────────────────────────────────

Difficulty = Literal["beginner", "intermediate", "advanced"]

# ── 教程分类 ──────────────────────────────────────────────────

Category = Literal[
    "calculation", "plot", "ai", "tools", "settings", "general"
]

# ── 高亮形状 ──────────────────────────────────────────────────

HighlightShape = Literal["rect", "circle"]

# ── tooltip 位置 ──────────────────────────────────────────────

Placement = Literal["top", "bottom", "left", "right"]

# ── 步骤中的动作 ──────────────────────────────────────────────

ActionType = Literal["click", "type", "select", "wait"]


# ═══════════════════════════════════════════════════════════════
#  Step — 引导中的单步
# ═══════════════════════════════════════════════════════════════

@dataclass
class Step:
    """交互式引导中的一步。

    Attributes:
        target: 要高亮的 UI 元素 ID（如 "toolbar.calc_button"）。
        text: tooltip 展示的说明文字。
        highlight: 高亮形状（rect / circle）。
        placement: tooltip 相对目标的位置。
        action: 用户需要执行的动作类型（可选）。
        action_value: 动作的预设值（可选，如自动填入的表达式）。
        image: 帮助文档用的截图路径（可选）。
    """
    target: str
    text: str
    highlight: HighlightShape = "rect"
    placement: Placement = "bottom"
    action: ActionType | None = None
    action_value: str = ""
    image: str = ""


# ═══════════════════════════════════════════════════════════════
#  Example — 示例任务
# ═══════════════════════════════════════════════════════════════

@dataclass
class Example:
    """示例任务 — 点击后可自动加载到工作区。

    Attributes:
        label: 示例名称（如"化简多项式"）。
        expr: 表达式内容。
        mode: 工作区模式（如"代数"）。
        action: 计算动作（如"化简"）。
        description: 补充说明（可选）。
    """
    label: str
    expr: str
    mode: str = ""
    action: str = ""
    description: str = ""


# ═══════════════════════════════════════════════════════════════
#  FAQ — 常见问题
# ═══════════════════════════════════════════════════════════════

@dataclass
class FAQ:
    """一对问答。"""
    q: str
    a: str


# ═══════════════════════════════════════════════════════════════
#  Tutorial — 单篇教程
# ═══════════════════════════════════════════════════════════════

@dataclass
class Tutorial:
    """单篇教程的完整数据。

    Attributes:
        id: 唯一标识（如 "basic-calc"）。
        title: 教程标题。
        difficulty: 难度等级。
        category: 分类。
        duration: 预计用时（如"2 分钟"）。
        order: 推荐排序序号。
        summary: 简介（用于卡片和列表展示）。
        steps: 交互式引导步骤列表。
        examples: 关联示例任务列表。
        faq: 常见问题列表。
        prerequisites: 前置教程 ID 列表。
    """
    id: str = ""
    title: str = ""
    difficulty: Difficulty = "beginner"
    category: Category = "general"
    duration: str = ""
    order: int = 99
    summary: str = ""
    steps: list[Step] = field(default_factory=list)
    examples: list[Example] = field(default_factory=list)
    faq: list[FAQ] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
#  TutorialProgress — 用户进度
# ═══════════════════════════════════════════════════════════════

@dataclass
class TutorialProgress:
    """用户教程进度快照。

    Attributes:
        completed: 已完成教程 ID 列表。
        last_tutorial: 上次浏览的教程 ID。
        first_launch_done: 是否已完成首次启动介绍。
        launch_count: 启动次数。
    """
    completed: list[str] = field(default_factory=list)
    last_tutorial: str = ""
    first_launch_done: bool = False
    launch_count: int = 0
