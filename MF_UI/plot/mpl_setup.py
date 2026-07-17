# -*- coding: utf-8 -*-
"""Matplotlib 全局配置 — 中文字体 + 后端选择。

在创建任何 matplotlib Figure 之前导入此模块即可：
    import MF_UI.plot.mpl_setup  # noqa — 副作用：配置 rcParams
"""

import matplotlib
matplotlib.use("Qt5Agg")

# ── 中文字体探测 ───────────────────────────────────────────────
_CJK_CANDIDATES = [
    "Microsoft YaHei",  # 微软雅黑 (Windows)
    "SimHei",           # 黑体 (Windows)
    "SimSun",           # 宋体 (Windows)
    "KaiTi",            # 楷体 (Windows)
    "FangSong",         # 仿宋 (Windows)
    "Noto Sans CJK SC", "Noto Sans CJK",
    "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
    "AR PL UMing CN", "AR PL UKai CN",
]

try:
    import matplotlib.font_manager as fm
    _available = {f.name for f in fm.fontManager.ttflist}
    _found = [f for f in _CJK_CANDIDATES if f in _available]
    if _found:
        _current = list(matplotlib.rcParams.get("font.sans-serif", ["DejaVu Sans"]))
        # 去重后插入到最前面
        _merged = _found + [f for f in _current if f not in _found]
        matplotlib.rcParams["font.sans-serif"] = _merged
        _used = _found[0]
    else:
        _used = "DejaVu Sans (no CJK found)"
except Exception:
    _used = "DejaVu Sans (fallback)"
    matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]

matplotlib.rcParams["axes.unicode_minus"] = False

# ── 主题配置 ──────────────────────────────────────────────────
# 从 config.json 读取（回退为内置默认值）

import json, os as _os

_DEFAULT_MPL_THEME = {
    "figure_facecolor": "#f8fafc",
    "axes_facecolor": "#ffffff",
    "text_color": "#334155",
    "grid_color": "#e2e8f0",
}


def _load_mpl_colors() -> dict[str, str]:
    """从 config.json 加载 matplotlib 颜色主题。"""
    try:
        _cfg_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__))))
        _cfg_path = _os.path.join(_cfg_root, "config.json")
        if _os.path.exists(_cfg_path):
            with open(_cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            ax = cfg.get("plot", {}).get("axes", {})
            return {
                "figure_facecolor": ax.get("bg_color", _DEFAULT_MPL_THEME["figure_facecolor"]),
                "axes_facecolor": ax.get("axes_bg", _DEFAULT_MPL_THEME["axes_facecolor"]),
                "text_color": ax.get("text_color", _DEFAULT_MPL_THEME["text_color"]),
                "grid_color": ax.get("grid_color", _DEFAULT_MPL_THEME["grid_color"]),
            }
    except Exception:
        pass
    return dict(_DEFAULT_MPL_THEME)


_MPL_THEME = _load_mpl_colors()


def get_mpl_figure_facecolor() -> str:
    """获取 matplotlib 图形背景色。"""
    return _MPL_THEME.get("figure_facecolor", "#f8fafc")


def get_mpl_axes_facecolor() -> str:
    """获取 matplotlib 坐标区背景色。"""
    return _MPL_THEME.get("axes_facecolor", "#ffffff")


def get_mpl_text_color() -> str:
    """获取 matplotlib 文本颜色。"""
    return _MPL_THEME.get("text_color", "#334155")


def apply_mpl_theme(fig, ax=None) -> None:
    """为 matplotlib 图形应用统一主题（facecolor + 浅色坐标区）。"""
    fc = _MPL_THEME["figure_facecolor"]
    fig.set_facecolor(fc)
    if ax is not None:
        ax.set_facecolor(_MPL_THEME["axes_facecolor"])
        ax.tick_params(colors=_MPL_THEME["text_color"])
        for spine in ax.spines.values():
            spine.set_color(_MPL_THEME["text_color"])
