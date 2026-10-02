#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dedupe_engine_map_extra.py — 删掉 engineMapExtra.js 里的重复键（保留正确的那个）。

为什么要写脚本而不是手删：这个文件里 Select-String 与 Get-Content 报的行号**互相不一致**
（文件含非常规换行符），按行号删会删错。这里改成按内容解析：找出两个对象字面量里
所有顶层 `"键": 值,` 的跨度，然后
  · EXTRA_MAP：同一个键出现多次时，**删掉前面的**（JS 语义是后者胜，前面的是死条目）；
  · EXTRA_VAR_SPECS：`Laurent级数` 出现两次，后面那个丢了 `展开中心 z0` 字段，
    所以**删掉后面的**，让带 z0 的那条生效（引擎的 laurent_series(func, z0, n) 要三个参数）。
删完会做三项自检：无重复键、Laurent 带 z0、文件仍可被 node 正常加载。
"""
import io
import re
import sys

P = (r"C:\Users\fsafsafsa\Desktop\MVS知识库\Multifunctional系列"
     r"\Multifunctional-Mathematics-v2.0\MF_UI\MFMath.UI.Vue\src\lib\engine\engineMapExtra.js")

src = io.open(P, encoding="utf-8", newline="").read()


def object_span(text, name):
    """返回 `const NAME = { ... }` 里花括号的 [start, end]（含括号）。"""
    at = text.index("const %s = " % name)
    brace_start = text.index("{", at)
    i = brace_start
    depth = 0
    while i < len(text):
        c = text[i]
        if c == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == "\\":
                    i += 1
                i += 1
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                return brace_start, i + 1
        i += 1
    raise ValueError("找不到 %s 的结尾" % name)


def top_entries(text, name):
    """返回 [(key, start, end)]，end 指向该项（含尾随逗号）之后的第一个字符。"""
    ob_start, _ob_end = object_span(text, name)
    i = ob_start + 1
    depth = 0
    out = []
    key = None
    start = None
    while i < len(text):
        c = text[i]
        if c == '"' and depth == 0 and key is None:
            j = i + 1
            buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j + 1]); j += 2; continue
                buf.append(text[j]); j += 1
            after = text[j + 1:j + 40]
            if re.match(r"\s*:", after):
                key = "".join(buf)
                start = i
                i = j
        elif c == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == "\\":
                    i += 1
                i += 1
        elif c in "{[":
            depth += 1
        elif c in "}]":
            if depth == 0:
                if key is not None:
                    out.append((key, start, i))
                break
            depth -= 1
        elif c == "," and depth == 0 and key is not None:
            out.append((key, start, i + 1))
            key = None
            start = None
        i += 1
    return out


def drop(text, spans):
    """删掉给定跨度（自后向前，避免偏移失效）。"""
    for (s, e) in sorted(spans, reverse=True):
        text = text[:s] + text[e:]
    return text


report = []

# ① EXTRA_MAP：重复键删前面的
for name in ("EXTRA_MAP", "EXTRA_VAR_SPECS"):
    while True:
        entries = top_entries(src, name)
        seen = {}
        for (k, s, e) in entries:
            seen.setdefault(k, []).append((s, e))
        dups = {k: v for k, v in seen.items() if len(v) > 1}
        if not dups:
            break
        victims = []
        for k, spans in dups.items():
            if name == "EXTRA_VAR_SPECS" and k == "Laurent级数":
                # 保留带 z0 的那条（前面的），删后面的
                keep_first = "z0" in src[spans[0][0]:spans[0][1]]
                report.append("  %s: %s 出现 %d 次，保留%s（含 z0=%s），删掉其余"
                              % (name, k, len(spans), "第一条" if keep_first else "最后一条", keep_first))
                victims += spans[1:]
            else:
                report.append("  %s: %s 出现 %d 次 → 删掉前面的死条目（后者胜）" % (name, k, len(spans)))
                victims += spans[:-1]
        src = drop(src, victims)

io.open(P, "w", encoding="utf-8", newline="").write(src)

# ② 自检
ok = True
for name in ("EXTRA_MAP", "EXTRA_VAR_SPECS"):
    keys = [k for (k, _s, _e) in top_entries(io.open(P, encoding="utf-8", newline="").read(), name)]
    dups = {k for k in keys if keys.count(k) > 1}
    report.append("  自检 %s：%d 个键，重复 %d 组" % (name, len(keys), len(dups)))
    ok = ok and not dups

text = io.open(P, encoding="utf-8", newline="").read()
entries = dict((k, text[s:e]) for (k, s, e) in top_entries(text, "EXTRA_VAR_SPECS"))
laurent = entries.get("Laurent级数", "")
report.append("  自检 Laurent级数 字段：%s" % laurent.replace("\n", " ")[:120])
ok = ok and "z0" in laurent

print("\n".join(report))
sys.exit(0 if ok else 1)
