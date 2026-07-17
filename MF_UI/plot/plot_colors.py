# -*- coding: utf-8 -*-
"""plot_colors — 绘图模块颜色配置单源（config.json → 全局共享）。"""
from __future__ import annotations

import json, os

# ── 从 config.json 加载（回退为内置默认值） ───────────────────────

_DEFAULT_CURVE_COLORS = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#e84393",
]

_DEFAULT_AXES = {
    "axis_color": "#334155", "grid_color": "#e8ecf0",
    "tick_color": "#94a3b8", "edge_color": "#b0b8c0",
    "text_color": "#334155", "bg_color": "#fafbfc",
}

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_config_path = os.path.join(_root, "config.json")

_curve_colors: list[str] = list(_DEFAULT_CURVE_COLORS)
_axes: dict[str, str] = dict(_DEFAULT_AXES)

try:
    if os.path.exists(_config_path):
        with open(_config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        pc = cfg.get("plot", {})
        if "colors" in pc and isinstance(pc["colors"], list) and pc["colors"]:
            _curve_colors = list(pc["colors"])
        ax = pc.get("axes", {})
        if isinstance(ax, dict):
            for k in _DEFAULT_AXES:
                if k in ax:
                    _axes[k] = ax[k]
except Exception:
    pass  # 配置读取失败，使用默认值

# ── 全局颜色计数器 ───────────────────────────────────────────────

_INDEX = 0


def next_color() -> str:
    """循环返回预设颜色（线程不安全，但仅在 UI 线程使用）。"""
    global _INDEX
    c = _curve_colors[_INDEX % len(_curve_colors)]
    _INDEX += 1
    return c


def get_colors() -> list[str]:
    """返回完整曲线颜色列表。"""
    return list(_curve_colors)


def get_axes_colors() -> dict[str, str]:
    """返回坐标轴主题颜色字典。"""
    return dict(_axes)


def get_curve_color(index: int) -> str:
    """按索引获取颜色（循环）。"""
    if not _curve_colors:
        return "#3498db"
    return _curve_colors[index % len(_curve_colors)]
