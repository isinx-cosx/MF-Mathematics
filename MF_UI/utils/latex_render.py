# -*- coding: utf-8 -*-
"""latex_render — 顶层加减号拆分 + 逐行 matplotlib 渲染。

核心功能
--------
- split_latex_by_top_level(latex) → list[str]
  按括号深度追踪，在深度为 0 的 +/- 处拆分。
  符号附着在后续项上（如 ``-x`` 保留完整）。

- latex_to_pixmap(latex, font_size=10, dpi=200, dark=False) → QPixmap | None
  单行 LaTeX → matplotlib → QPixmap。
"""

from __future__ import annotations

import re
from io import BytesIO

import matplotlib as _mpl

_mpl.use("agg")
_mpl.rcParams["mathtext.fontset"] = "cm"

DEFAULT_FONT_SIZE = 10


# ═══════════════════════════════════════════════════════════════════
#  split_latex_by_top_level
# ═══════════════════════════════════════════════════════════════════


def split_latex_by_top_level(latex: str) -> list[str]:
    """按顶层加减号拆分 LaTeX 字符串。

    使用括号深度追踪：仅当大括号 / 方括号 / 圆括号深度均为 0 时
    遇到的 ``+`` 或 ``-`` 才作为分割点。符号保留在它后面的项上。

    >>> split_latex_by_top_level("a + b - c")
    ['a', '+ b', '- c']
    >>> split_latex_by_top_level("{a + b} + c")
    ['{a + b}', '+ c']
    >>> split_latex_by_top_level("\\frac{x+y}{z}")
    ['\\frac{x+y}{z}']
    """
    if not latex or not latex.strip():
        return [latex] if latex else []

    # ── 扫描一遍，记录每个 +/- 是否在顶层 ──
    brace = 0   # {}
    sq    = 0   # []
    paren = 0   # ()
    n = len(latex)
    # 哪些索引是「顶层 +/-」：True = split here
    is_split = [False] * n

    i = 0
    while i < n:
        ch = latex[i]

        # ── 反斜杠 + 下一个字符（跳过命令名）──
        if ch == "\\":
            i += 1  # skip backslash
            if i < n:
                # skip command name (letters only)
                while i < n and latex[i].isalpha():
                    i += 1
                # optional *  (e.g. \begin{align*} )
                if i < n and latex[i] == '*':
                    i += 1
                # skip optional [ … ]  (e.g. \\[6pt])
                if i < n and latex[i] == '[':
                    while i < n and latex[i] != ']':
                        i += 1
                    if i < n:
                        i += 1  # skip ]
                # skip optional { … }  (e.g. \frac{…}{…})
                if i < n and latex[i] == '{':
                    brace += 1
                    i += 1
                continue
            else:
                break

        # ── 大括号 ──
        elif ch == '{':
            brace += 1
        elif ch == '}':
            if brace > 0:
                brace -= 1

        # ── 方括号 ──
        elif ch == '[':
            sq += 1
        elif ch == ']':
            if sq > 0:
                sq -= 1

        # ── 圆括号 ──
        elif ch == '(':
            paren += 1
        elif ch == ')':
            if paren > 0:
                paren -= 1

        # ── 顶层 +/- ──
        elif ch in ('+', '-') and brace == 0 and sq == 0 and paren == 0:
            # 检查不是数字的一部分（如 1.5e-10）
            if ch == '-' and i > 0:
                prev = latex[i - 1]
                if prev.isdigit() or prev in ('e', 'E'):
                    i += 1
                    continue
            # 检查前后有空格或运算符上下文（避免误拆）
            is_split[i] = True

        i += 1

    # ── 如果没有顶层 +/-，返回原串 ──
    if not any(is_split):
        return [latex]

    # ── 按 split 点切分 ──
    result = []
    start = 0
    for j in range(1, n):  # 从索引1开始，因为 j-1 是分割点
        if is_split[j]:
            # 分割点在 j 处，前面的块是 [start:j]
            if j > start:
                result.append(latex[start:j].strip())
            start = j  # 下一块从符号开始

    # 最后一块
    if start < n:
        result.append(latex[start:].strip())

    # 空项过滤
    return [r for r in result if r]


# ═══════════════════════════════════════════════════════════════════
#  sanitize
# ═══════════════════════════════════════════════════════════════════


def _sanitize(s: str) -> str:
    """LaTeX → mathtext 兼容格式。"""
    s = s.replace("\\displaystyle", "")
    s = re.sub(r"\\text\{([^}]*)\}", r"\\mathrm{\1}", s)
    s = re.sub(r"\\operatorname\{([^}]*)\}", r"\\mathrm{\1}", s)
    s = re.sub(r"\\\\\[\d+pt\]", r" ", s)
    s = s.replace("\\backslash", "").replace("\\$", "$")
    return s


# ═══════════════════════════════════════════════════════════════════
#  latex_to_pixmap
# ═══════════════════════════════════════════════════════════════════


def latex_to_pixmap(
    latex: str,
    font_size: int = DEFAULT_FONT_SIZE,
    dpi: int = 200,
    dark: bool = False,
) -> QPixmap | None:
    """单行 LaTeX → QPixmap。渲染失败返回 None。"""
    if not latex or not latex.strip():
        return None
    try:
        import matplotlib.pyplot as _plt

        face = "#1e293b" if dark else "#fafbfc"
        text_color = "#e2e8f0" if dark else "#0f172a"

        fig = _plt.figure(figsize=(8, 0.45), dpi=dpi, facecolor=face)
        safe = _sanitize(latex)
        fig.text(0.02, 0.5, f"$ {safe} $",
                 fontsize=font_size, va="center", ha="left",
                 color=text_color)

        fig.canvas.draw()
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=dpi,
                    bbox_inches="tight", pad_inches=0.08,
                    transparent=False, facecolor=face, edgecolor="none")
        _plt.close(fig)
        buf.seek(0)
        from PySide6.QtGui import QPixmap
        pix = QPixmap()
        pix.loadFromData(buf.getvalue(), "PNG")
        buf.close()
        return pix
    except Exception:
        return None
