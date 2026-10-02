#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add_bounded_using.py — 给用到新的"带上界取参"助手的 *_api.cpp 补 using 声明。

这些文件用的是**逐名引入**（`using mf::api::get_int;`），新助手不会自动可见，
所以调用处会报"找不到标识符"。这里在每个文件最后一条 `using mf::api::...;` 之后
补两行（已存在则跳过），并在文件里确实没用到时**不写**。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEED = ("get_int_bounded", "get_int_opt_bounded")
LINES = ("using mf::api::get_int_bounded;",
         "using mf::api::get_int_opt_bounded;")


def main():
    changed = []
    for dirpath, _dirs, files in os.walk(ROOT):
        if os.sep + "build" in dirpath:
            continue
        for name in files:
            if not name.endswith("_api.cpp"):
                continue
            path = os.path.join(dirpath, name)
            text = io.open(path, encoding="utf-8").read()
            if not any(n in text for n in NEED):
                continue
            # 已经在 using 里的名字不用重复加
            todo = [ln for ln in LINES if re.search(r"\b" + ln.split("::")[-1].rstrip(";") + r"\b\s*;",
                                                    text) is None
                    or ("using " + ln.split("using ", 1)[1]) not in text]
            todo = [ln for ln in LINES
                    if ("using mf::api::" + ln.split("::")[-1]) not in text]
            if not todo:
                continue
            lines = text.splitlines(keepends=True)
            # 找最后一条 using mf::api::...; 的位置
            idx = None
            for i, ln in enumerate(lines):
                if ln.strip().startswith("using mf::api::"):
                    idx = i
            if idx is None:
                print(f"  [跳过] {os.path.relpath(path, ROOT)} 没有 using mf::api:: 行，手工确认")
                continue
            insert = "".join(ln + "\n" for ln in todo)
            lines.insert(idx + 1, insert)
            io.open(path, "w", encoding="utf-8", newline="").write("".join(lines))
            changed.append((os.path.relpath(path, ROOT), todo))
    for rel, todo in changed:
        print(f"  {rel}  += {', '.join(t.split('::')[-1].rstrip(';') for t in todo)}")
    print(f"\n共 {len(changed)} 个文件补了 using")
    return 0


if __name__ == "__main__":
    sys.exit(main())
