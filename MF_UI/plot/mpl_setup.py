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

# 日志输出（仅首次导入）
_LOGGED = False
if not _LOGGED:
    _LOGGED = True
    # 静默设置，不打印 — 避免污染 UI 输出
