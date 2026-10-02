#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stress_scan.py — 找出"会卡住/会崩"的引擎动作（病态输入压力扫描）

为什么要有它：引擎有 424 个动作，准确性套件只回答"算得对不对"，不回答"会不会卡死"。
用户真正会骂的是后者。这个工具不看源码猜，而是**按病态输入真跑一遍并计时**，
每个用例都在独立子进程里带墙钟超时，挂住就杀掉并精确指出是哪个动作、哪一组参数。

输入从哪来（不手写 424 份参数）：前端 `engineMap.js` / `engineMapExtra.js` 里已经
登记了每个动作的参数 schema（键名 + 类型），这里解析它生成参数：
  · base   —— 各类型的常规小值（先确认动作可用）
  · big    —— 把"规模类"参数放大到 1e4 量级
  · huge   —— 放大到 1e7 量级（只在规模类键上做）
  · hard   —— 把表达式类参数换成病态表达式（高次、嵌套、震荡、奇异积分…）
  · chain  —— 连续放大同一动作的多个规模参数（组合爆炸更容易在这里现形）

用法（默认 DLL 是本仓库构建产物）：
    python MF_Mathematics/tools/stress_scan.py                     # 全部动作，3 秒超时
    python MF_Mathematics/tools/stress_scan.py --timeout 8         # 放宽超时
    python MF_Mathematics/tools/stress_scan.py --only linear_algebra,calculus
    python MF_Mathematics/tools/stress_scan.py --list              # 只列用例不跑
输出：
    · 终端摘要（按耗时排序 + 挂住/崩溃清单）
    · docs/stress-scan.json —— 完整结果，便于与上一轮对比
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # MF_Mathematics/
V2 = os.path.dirname(ROOT)                        # v2.0 仓库根
UI_LIB = os.path.join(V2, "MF_UI", "MFMath.UI.Vue", "src", "lib", "engine")
DEFAULT_DLL = os.path.join(ROOT, "build", "bin", "Release", "mf_mathematics.dll")
OUT_JSON = os.path.join(V2, "docs", "stress-scan.json")

# ── 规模类参数：名字命中就把值放大（这是"卡住"最常见的来源）──────────────
SCALE_KEYS = re.compile(
    r"^(n|m|k|order|degree|max_iter|max_n|max_dim|n_terms|n_points|n_trajectories|"
    r"resolution|segment_size|window|prime_limit|limit|steps|count|size|dim|dimension|"
    r"ambient_dim|sphere_dim|subspace_dim|samples|iterations|n_values|depth|terms)$"
)

# ── 病态表达式：覆盖高次、嵌套、震荡、奇异、分支、极值点等典型"算不动"形态 ──
HARD_EXPRS = [
    "(x+1)^80",                          # 展开/化简：项数组合爆炸
    "(x+y+z+w)^30",
    "sin(20*x)*exp(cos(x))",             # 已知历史上能压栈的形态
    "exp(-x^2)/(1+x^4)",
    "1/(x^5+1)",                         # 符号积分经典难题
    "sqrt(1+sqrt(1+sqrt(1+x)))",         # 深嵌套
    "tan(x)^12",                         # 三角高次
    "1/(sin(x)-0.5)",                    # 奇点密集
    "gamma(x)*zeta(x)",
    "abs(x-1)+floor(x/3)",
    "x^x",
    "(x^2-1)^20/(x-1)^10",
    "exp(exp(exp(x)))",
    "sin(1/x)",
]
STRING_KEYS = re.compile(r"^(expr|expr1|expr2|f|g|func|eq|seq|seq_expr|rule|dx_dt|dy_dt|x_expr|y_expr|formula|contour|series)$")

# 各类型的常规小值（base 用）
BASE_BY_TYPE = {
    "int": 3,
    "double": 1.0,
    "string": "x",
    "string_or_number": "x",
    "matrix": [[1, 2], [3, 4]],
    "vec": [1, 2],
    "double_array": [1.0, 2.0, 3.0],
    "int_array": [1, 2, 3],
    "double_list": [1.0, 2.0],
    "int_list": [1, 2],
    "pair_list": [[1, 2], [2, 3]],
    "ll_array": [[1, 2], [3]],
    "ll_matrix": [[[1, 2]], [[3]]],
    "point_cloud": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]],
    "point": [1.0, 2.0],
    "bool": True,
}


def load_schema():
    """从 engineMap.js / engineMapExtra.js 里解析 {fn, module, args:[{key,type}]}。"""
    entries = {}
    for name in ("engineMap.js", "engineMapExtra.js"):
        path = os.path.join(UI_LIB, name)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        for var in ("RAW_MAP", "EXTRA_MAP"):
            m = re.search(var + r"\s*=\s*(\{.*?\});\s*\n", text, re.S)
            if not m:
                continue
            try:
                obj = json.loads(m.group(1))
            except json.JSONDecodeError as e:
                print(f"  [warn] {name} 的 {var} 解析失败：{e}", file=sys.stderr)
                continue
            for mode, spec in obj.items():
                fn = spec.get("fn")
                if fn:
                    entries.setdefault(fn, {"mode": mode, "module": spec.get("module", "?"),
                                             "args": spec.get("args", [])})
    return entries


def base_args(spec):
    out = {}
    for a in spec["args"]:
        t = a.get("type", "string")
        out[a["key"]] = BASE_BY_TYPE.get(t, 1.0 if "double" in t else 1)
    return out


def scaled_args(spec, factor):
    """把规模类参数放大到 factor；非规模参数保持 base。"""
    out = {}
    for a in spec["args"]:
        key, t = a["key"], a.get("type", "string")
        if SCALE_KEYS.match(key) and t in ("int", "double"):
            out[key] = factor if t == "int" else float(factor)
        else:
            out[key] = BASE_BY_TYPE.get(t, 1)
    return out


def hard_args(spec, hard_expr, factor=None):
    """表达式类参数换成病态表达式；可选同时放大规模参数。"""
    out = {}
    for a in spec["args"]:
        key, t = a["key"], a.get("type", "string")
        if factor and SCALE_KEYS.match(key) and t in ("int", "double"):
            out[key] = factor if t == "int" else float(factor)
        elif STRING_KEYS.match(key) and "string" in t:
            out[key] = hard_expr
        else:
            out[key] = BASE_BY_TYPE.get(t, 1)
    return out


# 组合类动作（计数会直接爆掉位数）单列，避免"算不出来"被当成"卡住"误判
BIGNUM_KEYS = {"n", "m", "k", "exp", "base", "mod", "prime_limit", "n_terms"}


def build_cases(entries):
    cases = []
    for fn, spec in sorted(entries.items()):
        mod = spec["module"]
        cases.append({"id": f"{fn}|base", "fn": fn, "module": mod, "kind": "base",
                      "args": base_args(spec)})
        if any(SCALE_KEYS.match(a["key"]) and a.get("type") in ("int", "double") for a in spec["args"]):
            cases.append({"id": f"{fn}|big", "fn": fn, "module": mod, "kind": "big",
                          "args": scaled_args(spec, 10000)})
            cases.append({"id": f"{fn}|huge", "fn": fn, "module": mod, "kind": "huge",
                          "args": scaled_args(spec, 10000000)})
        if any(STRING_KEYS.match(a["key"]) and "string" in a.get("type", "string") for a in spec["args"]):
            for i, ex in enumerate(HARD_EXPRS[:6]):
                cases.append({"id": f"{fn}|hard{i}", "fn": fn, "module": mod, "kind": "hard",
                              "args": hard_args(spec, ex)})
            # 表达式病态 + 规模放大：最容易出现"符号运算 × 大参数"的双重爆炸
            if any(SCALE_KEYS.match(a["key"]) for a in spec["args"]):
                cases.append({"id": f"{fn}|hard+big", "fn": fn, "module": mod, "kind": "chain",
                              "args": hard_args(spec, HARD_EXPRS[0], factor=1000)})
    return cases


# ── 子进程执行器：按"结果文件 + 进度文件"轮询，超时就杀并精确定位 ──────────
CHILD_SRC = r'''
import ctypes, json, os, sys, time
dll, cases_path, res_path, prog_path = sys.argv[1:5]
cases = json.load(open(cases_path, encoding="utf-8"))
lib = ctypes.CDLL(dll)
lib.math_call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
lib.math_call.restype = ctypes.c_int
res = open(res_path, "a", encoding="utf-8", buffering=1)
def report(obj):
    res.write(json.dumps(obj, ensure_ascii=False) + "\n"); res.flush()
for c in cases:
    with open(prog_path, "w", encoding="utf-8") as f:
        f.write(c["id"]); f.flush()
    buf = ctypes.create_string_buffer(1 << 22)
    t0 = time.perf_counter()
    err = ""
    try:
        n = lib.math_call(c["fn"].encode(), json.dumps(c["args"]).encode(), buf, 1 << 22)
        if n < 0:
            err = f"buffer too small (n={n})"
    except Exception as e:
        err = f"[{type(e).__name__}] {e}"
    ms = (time.perf_counter() - t0) * 1000
    report({"id": c["id"], "fn": c["fn"], "module": c["module"], "kind": c["kind"],
            "ms": round(ms, 1), "err": err, "args": c["args"]})
'''


def run_cases(dll, cases, timeout, verbose=False):
    """逐用例执行；返回结果列表（含 timeout 判定）。"""
    import tempfile

    tmp = tempfile.mkdtemp(prefix="mf-stress-")
    cases_path = os.path.join(tmp, "cases.json")
    res_path = os.path.join(tmp, "results.jsonl")
    prog_path = os.path.join(tmp, "progress.txt")
    child_path = os.path.join(tmp, "child.py")
    open(child_path, "w", encoding="utf-8").write(CHILD_SRC)
    open(res_path, "w", encoding="utf-8").close()

    results = []
    done = set()
    idx = 0
    by_id = {c["id"]: c for c in cases}
    while idx < len(cases):
        batch = [c for c in cases[idx:] if c["id"] not in done]
        if not batch:
            break
        json.dump(batch, open(cases_path, "w", encoding="utf-8"), ensure_ascii=False)
        # 每批都重新写一份结果文件（子进程 append），先清空避免重复
        open(res_path, "w", encoding="utf-8").close()
        if os.path.exists(prog_path):
            os.remove(prog_path)
        proc = subprocess.Popen([sys.executable, child_path, dll, cases_path, res_path, prog_path],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        while True:
            if proc.poll() is not None:
                break
            got = 0
            if os.path.exists(res_path):
                got = sum(1 for _ in open(res_path, encoding="utf-8"))
            if got >= len(batch):
                break
            if os.path.exists(prog_path):
                cur = open(prog_path, encoding="utf-8").read().strip()
                if time.time() - os.path.getmtime(prog_path) > timeout:
                    # 当前这个用例挂住了
                    c = by_id.get(cur, {})
                    results.append({"id": cur, "fn": c.get("fn", cur.split("|")[0]),
                                    "module": c.get("module", "?"), "kind": "TIMEOUT",
                                    "ms": round(timeout * 1000, 1),
                                    "err": f"超过 {timeout}s 未返回（已杀进程）", "args": c.get("args")})
                    done.add(cur)
                    if verbose:
                        print(f"  [HANG] {cur}  (> {timeout}s)")
                    proc.kill()
                    proc.wait()
                    break
            time.sleep(0.08)

        # 收本批已完成的结果
        if os.path.exists(res_path):
            for line in open(res_path, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r["id"] in done:
                    continue
                done.add(r["id"])
                results.append(r)
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        # 若子进程异常退出且还有没跑完的，继续下一轮（从没做完的开始）
        nxt = next((i for i, c in enumerate(cases) if c["id"] not in done), None)
        if nxt is None:
            break
        if nxt <= idx and proc.returncode not in (0, None):
            c = cases[nxt]
            results.append({"id": c["id"], "fn": c["fn"], "module": c["module"], "kind": "CRASH",
                            "ms": 0, "err": f"子进程异常退出 rc={proc.returncode}", "args": c["args"]})
            done.add(c["id"])
        idx = nxt
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dll", default=os.environ.get("MF_ACC_DLL") or DEFAULT_DLL)
    ap.add_argument("--timeout", type=float, default=3.0, help="单个用例的墙钟上限（秒）")
    ap.add_argument("--only", default="", help="只跑这些模块，逗号分隔")
    ap.add_argument("--kind", default="", help="只跑这些用例类型（base/big/huge/hard/chain）")
    ap.add_argument("--fn", default="", help="只跑这些动作，逗号分隔（定位单个动作时用）")
    ap.add_argument("--list", action="store_true", help="只列用例不执行")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.dll):
        print(f"找不到引擎 DLL：{args.dll}", file=sys.stderr)
        return 2
    entries = load_schema()
    if not entries:
        print("没能从前端 engineMap 解析出动作参数表", file=sys.stderr)
        return 2
    cases = build_cases(entries)
    if args.only:
        mods = {m.strip() for m in args.only.split(",")}
        cases = [c for c in cases if c["module"] in mods]
    if args.kind:
        kinds = {k.strip() for k in args.kind.split(",")}
        cases = [c for c in cases if c["kind"] in kinds]
    if args.fn:
        fns = {f.strip() for f in args.fn.split(",")}
        cases = [c for c in cases if c["fn"] in fns]

    print(f"动作数 {len(entries)}    用例数 {len(cases)}    超时 {args.timeout}s")
    print(f"DLL {args.dll}")
    if args.list:
        for c in cases[:400]:
            print(f"  {c['id']:44s} {json.dumps(c['args'], ensure_ascii=False)[:110]}")
        return 0

    t0 = time.time()
    results = run_cases(args.dll, cases, args.timeout, args.verbose)
    elapsed = time.time() - t0

    slow = sorted([r for r in results if r["kind"] != "TIMEOUT"], key=lambda r: -r["ms"])
    hangs = [r for r in results if r["kind"] == "TIMEOUT"]
    crashes = [r for r in results if r["kind"] == "CRASH"]
    errs = [r for r in results if r.get("err")]

    print(f"\n=== 结果（{len(results)} 个用例，用时 {elapsed:.0f}s）===")
    print(f"挂住 {len(hangs)}    崩溃 {len(crashes)}    报错(含正常拒绝) {len(errs)}")
    if hangs:
        print("\n── 挂住的用例（> 超时）──")
        for r in sorted(hangs, key=lambda r: r["id"]):
            print(f"  {r['id']:46s} {r['fn']}")
    if crashes:
        print("\n── 崩溃 ──")
        for r in crashes:
            print(f"  {r['id']:46s} {r['err']}")
    print("\n── 最慢的 25 个 ──")
    for r in slow[:25]:
        print(f"  {r['ms']:9.1f} ms  {r['id']:44s} {'ERR: ' + r['err'][:40] if r.get('err') else ''}")

    by_mod = defaultdict(lambda: [0, 0.0])
    for r in results:
        by_mod[r["module"]][0] += 1
        by_mod[r["module"]][1] += r["ms"]
    print("\n── 各模块总耗时（前 12）──")
    for mod, (cnt, tot) in sorted(by_mod.items(), key=lambda kv: -kv[1][1])[:12]:
        print(f"  {mod:22s} {cnt:4d} 用例   {tot/1000:8.1f} s")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump({"dll": args.dll, "timeout": args.timeout, "elapsed_s": round(elapsed, 1),
               "cases": len(results), "results": results},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n完整结果已写入 {OUT_JSON}")
    return 1 if (hangs or crashes) else 0


if __name__ == "__main__":
    sys.exit(main())
