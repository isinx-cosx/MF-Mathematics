#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""relax_lower_bounds.py — 把统一收口时误加的**下限**交还给核心函数。

准确性套件第二轮又发现 17 处失败，全是同一个错误：
`get_int_bounded(..., lo, hi, ...)` 的 `lo` 抢在核心函数自己的语义校验之前报错，
既挡住了合法的小/负取值（eratosthenes(0)、euler_phi(-6)、combination(-1,0)），
也换掉了核心原来的报错文案（"项数必须为正整数" → "超出可计算范围"），
而套件断言的正是那些文案。

原则修正：**统一助手只负责"上限"（防卡死），下限交给每个动作自己的校验**。
只有"越界会导致崩溃/无意义分配"的少数键才保留下限：
  · segment_size ≥ 1（段长为 0 会除零）
  · window_size ≥ 2（stft 的汉宁窗与缺省步长）
  · hop_size ≥ 0（负步长会让帧索引倒退）
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERMISSIVE = "-9223372036854775807"          # INT64_MIN + 1：给核心自己判
KEEP_LO = {"segment_size": "1", "window_size": "2", "hop_size": "0"}

# 逐个动作单独处理的（助手不该介入的地方）
SPECIAL = [
    ("number_theory/number_theory_api.cpp", "mobius_prefix",
     'get_int_bounded(args, "n", 0, 10000000, "n")',
     'get_int(args, "n")',
     "核心自己就有 n ≤ 1e7 的守卫与文案，助手不该抢先报错"),
]

CALL_RE = re.compile(r'get_int(_opt)?_bounded\(\s*args,\s*"([a-z_0-9]+)"\s*,\s*'
                     r'(?:([^,]+),\s*)?'          # opt 的默认值
                     r'(-?\d+)\s*,\s*(-?\d+)')     # lo, hi

DIAG = []


def main():
    for dirpath, _dirs, files in os.walk(ROOT):
        if os.sep + "build" in dirpath:
            continue
        for name in files:
            if not name.endswith("_api.cpp"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, ROOT)
            text = io.open(path, encoding="utf-8").read()
            orig = text

            for (srel, action, old, new, why) in SPECIAL:
                if srel != rel:
                    continue
                if old in text:
                    text = text.replace(old, new, 1)
                    DIAG.append(f"  {rel} [{action}] {why}")

            def fix(m):
                opt, key, default, lo, hi = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
                want = KEEP_LO.get(key, PERMISSIVE)
                if lo == want:
                    return m.group(0)
                DIAG.append(f"  {rel} [{key}] 下限 {lo} → {want}")
                if opt:
                    return f'get_int_opt_bounded(args, "{key}", {default.strip()}, {want}, {hi}'
                return f'get_int_bounded(args, "{key}", {want}, {hi}'

            text = CALL_RE.sub(fix, text)
            if text != orig:
                io.open(path, "w", encoding="utf-8", newline="").write(text)

    print("\n".join(DIAG[:40]))
    print(f"\n共放宽 {len(DIAG)} 处下限（上限不变）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
