#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_hang_fixes.py — 逐条验证"会卡死/崩溃"的输入现在会怎样。

与 stress_scan.py 的分工：那个从 engineMap 生成大批用例找问题，这个**针对已定位的
风险点**用真实病态参数逐个复核，判定标准是三者之一：
  · 快速明确的报错（期望：带上限的参数）—— 记为 REJECTED
  · 快速给出结果                    —— 记为 OK
  · 超时 / 子进程被杀 / 崩溃        —— 记为 HANG / CRASH（回归）

每个用例跑在独立子进程里带墙钟超时，挂住就杀掉，不会拖住整体。
"""
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time

# Windows 控制台默认是 GBK，报告里的中文/上标字符会直接抛 UnicodeEncodeError
# （实测：报告里一个 "O(N³)" 就能把整个批量验证打断）。统一按 UTF-8 输出。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DLL = os.path.join(ROOT, "build", "bin", "Release", "mf_mathematics.dll")

# (动作, 参数, 说明) —— 都是审计/实测里点过名的"一个大数就出事"的输入
CASES = [
    ("bernoulli_number", {"n": 100000}, "伯努利数阶数爆炸（原实测 >20s 不返回）"),
    ("zeta_negative", {"n": 100000}, "同一族：ζ(-n) 的伯努利递推"),
    ("analytic_continuation_zeta", {"s": [-1000000000, 0]}, "ζ 解析延拓负整数点按 |s| 分配"),
    ("functional_equation_zeta", {"s": [-1000000000, 0]}, "函数方程走同一路径"),
    ("euler_phi", {"n": 999999999999999989}, "试除法跑到 √n ≈ 1.5e9"),
    ("prime_factors", {"n": 999999999999999989}, "同上（素因数分解）"),
    ("divisor_count", {"n": 999999999999999989}, "同上"),
    ("primitive_root", {"p": 1000000000000000003}, "for(g=2;g<p;++g) 无上限"),
    ("discrete_log", {"g": 2, "h": 3, "p": 1000000000000000003}, "BSGS 建 1e9 项哈希表"),
    ("eratosthenes", {"n": 10000000000}, "筛法按 n 分配 1.25 GB"),
    ("segmented_sieve", {"n": 1000000000000, "segment_size": 1}, "分段筛段数×素数个数"),
    ("step_function_approx", {"f": "x", "n": 1000000000}, "阶梯数直接当循环上界"),
    ("borel_sigma_algebra", {"space": list(range(100000))}, "O(N³) 内存"),
    ("probability_space", {"Omega": "finite:1000000000"}, "字符串里的 n 直接展开"),
    ("generate_sigma_algebra", {"generators": [[i] for i in range(12)], "X": list(range(12))}, "σ-代数规模爆炸"),
    ("series_sum", {"expr": "1/n^2", "var": "n", "a": 1, "b": 100000000}, "有限和的上界是用户给的"),
    ("taylor", {"expr": "sin(x)", "var": "x", "point": 0, "order": 10000}, "高阶泰勒（原 11s）"),
    ("power_series", {"expr": "sin(x)", "var": "x", "point": 0, "n": 10000}, "同上（原 11s）"),
    ("fourier_series", {"f": "x", "n_terms": 10000, "period": 6.283185307179586}, "每项两次 2000 点辛普森"),
    ("poisson_summation", {"f": "exp(-x^2)", "a": 1.0, "n_terms": 1000000}, "2·n_terms+1 项"),
    ("termwise_integration", {"seq_expr": "x^n/n^2", "interval": [0, 1], "n_terms": 1000000}, "逐项累加进符号表达式"),
    ("termwise_differentiation", {"seq_expr": "x^n", "n_terms": 1000000}, "同上"),
    ("integral_test", {"expr": "(x+1)^80", "var": "x"}, "原实测 3.1s（100 万次求值）"),
    ("integral_test", {"expr": "1/n^2", "var": "n"}, "基准情形（原 1.0s）"),
    ("integral_nonnegative", {"f": "1/(sin(x)-0.5)", "range": [0, 1]}, "原实测 3.9s（50 万次求值）"),
    ("integral_nonnegative", {"f": "x^2", "range": [0, 1]}, "基准情形（原 0.5s）"),
    ("mandelbrot", {"width": 100000, "height": 100000, "max_iter": 100}, "8e10 个元素"),
    ("mandelbrot", {"width": 4000, "height": 4000, "max_iter": 100000}, "宽高各自合规但乘积爆"),
    ("expr_eval_grid", {"expr": "x+y", "xs": list(range(4000)), "ys": list(range(4000))}, "1.6e7 点"),
    ("stft", {"signal": [1.0], "window_size": 1}, "整数除零 → 进程死（SEH）"),
    ("gaussian_blur", {"signal": [1.0, 2.0, 3.0], "sigma": 1e9}, "核长整数溢出"),
    ("uncertainty_principle", {"f": "x", "n_points": 2000000000}, "左移溢出 → 死循环"),
    ("plancherel_theorem", {"f": "x", "n_points": 2000000000}, "同上"),
    ("convolution_theorem", {"f": "x", "g": "x", "n_points": 2000000000}, "同上"),
    ("trapezoidal_rule", {"f": "sin(x)", "a": 0, "b": 1, "n": 2000000000}, "n 直接当循环上界"),
    ("gradient_descent", {"f": "x^2", "max_iter": 10000000000}, "迭代数无上限且记路径"),
    ("phase_portrait", {"dx_dt": "-y", "dy_dt": "x", "x_range": [-1, 1], "y_range": [-1, 1], "resolution": 100000}, "res² 矩阵×4"),
    ("least_squares_fit", {"x": list(range(5001)), "y": list(range(5001)), "degree": 5000}, "法方程 (d+1)² + O(m³)"),
    ("continued_fraction", {"x": 1.4142135623730951, "n_terms": 10000000000}, "项数无上限"),
    ("euler_product", {"s": 2, "prime_limit": 1000000000}, "转发给无上限的筛法"),
    ("cauchy_criterion", {"seq": "1/n", "max_n": 1000000}, "max_n 次求值 + O(N²) 两两比较"),
    ("characteristic_polynomial", {"matrix": [[i * 3 + j for j in range(20)] for i in range(20)]}, "20×20 符号行列式 + simplify"),
    ("binomial_expand", {"a": "x", "b": "1", "n": 1000000000000}, "先按 n reserve"),
    ("expr_eval", {"expr": "(" * 50000 + "x" + ")" * 50000}, "解析器深嵌套 → 栈溢出（SEH）"),
]

CHILD = r'''
import ctypes, json, sys, time
# ⚠ 子进程也要强制 UTF-8 输出：Windows 默认 GBK，引擎返回的中文报错会让 print 抛
#   UnicodeEncodeError → 子进程以 1 退出 → 父进程误判成"崩溃"（实测假阳性）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
dll, fn, args_path = sys.argv[1], sys.argv[2], sys.argv[3]
args_json = open(args_path, encoding="utf-8").read()
lib = ctypes.CDLL(dll)
lib.math_call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
lib.math_call.restype = ctypes.c_int
buf = ctypes.create_string_buffer(1 << 22)
t0 = time.perf_counter()
n = lib.math_call(fn.encode(), args_json.encode(), buf, 1 << 22)
ms = (time.perf_counter() - t0) * 1000
raw = buf.value.decode("utf-8", "replace")
try:
    env = json.loads(raw)
    print(json.dumps({"ms": ms, "isError": bool(env.get("isError")),
                      "value": env.get("value") if env.get("isError") else "ok",
                      "n": n}, ensure_ascii=False))
except Exception as e:
    print(json.dumps({"ms": ms, "isError": None, "value": f"非法JSON: {raw[:120]}", "n": n}, ensure_ascii=False))
'''


def main():
    dll = os.environ.get("MF_ACC_DLL") or DEFAULT_DLL
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    tmp = tempfile.mkdtemp(prefix="mf-verify-")
    child = os.path.join(tmp, "child.py")
    open(child, "w", encoding="utf-8").write(CHILD)
    # 参数走**文件**而不是命令行：Windows 命令行有长度上限，
    # 十万个元素的数组直接把 CreateProcess 顶爆（实测 WinError 206）。
    args_path = os.path.join(tmp, "args.json")
    # 报告由脚本自己写成 UTF-8 文件：Windows 控制台是 GBK，中文与上标字符
    # 会让 print 直接抛 UnicodeEncodeError 打断整个批量验证（实测踩到）。
    report_path = os.path.join(os.path.dirname(ROOT), "docs", "hang-fix-verification.md")
    report = ["# 会卡住的算法：修复前后对照（自动生成，勿手改）", "",
              f"- 引擎：`{dll}`",
              f"- 单例墙钟超时：{timeout:g}s（每个用例独立子进程，挂住就杀掉）",
              f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
              "- 判定：REJECTED=快速明确拒绝 / OK=快速算出 / HANG=超时 / CRASH=进程死",
              "",
              "| 状态 | 动作 | 输入说明 | 详情 |",
              "| --- | --- | --- | --- |"]

    bad = []
    for fn, args, why in CASES:
        with open(args_path, "w", encoding="utf-8") as f:
            json.dump(args, f, ensure_ascii=False)
        t0 = time.time()
        try:
            p = subprocess.run([sys.executable, child, dll, fn, args_path],
                               capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace")
            wall = (time.time() - t0) * 1000
            if p.returncode != 0:
                status, detail = "CRASH", f"子进程退出码 {p.returncode}（可能是 SEH/栈溢出）"
            else:
                try:
                    r = json.loads(p.stdout.strip().splitlines()[-1])
                except Exception:
                    status, detail = "??", p.stdout.strip()[:160]
                else:
                    if r["isError"]:
                        status, detail = "REJECTED", str(r["value"])[:150]
                    else:
                        status = "OK"
                        detail = f"{r['ms']:.0f} ms"
        except subprocess.TimeoutExpired:
            status, detail = "HANG", f">{timeout}s 未返回（已杀）"
        wall = (time.time() - t0) * 1000      # 超时分支也要更新，否则打印的是上一条的耗时
        flag = {"HANG": "!!", "CRASH": "!!", "REJECTED": "  ", "OK": "  "}.get(status, "  ")
        # stdout 只打 ASCII：控制台编码不再是变量
        print(f"{flag} [{status:8s}] {fn:28s} wall={wall:.0f}ms")
        report.append(f"| {status} | `{fn}` | {why} | {detail.replace('|', '/')} |")
        if status in ("HANG", "CRASH", "??"):
            bad.append((fn, status, why))

    counts = {}
    for line in report:
        if line.startswith("| ") and not line.startswith("| 状态") and not line.startswith("| ---"):
            counts[line.split("|")[1].strip()] = counts.get(line.split("|")[1].strip(), 0) + 1
    report += ["", "## 汇总", "",
               "| 状态 | 个数 |", "| --- | --- |"]
    for k in ("OK", "REJECTED", "HANG", "CRASH", "??"):
        if counts.get(k):
            report.append(f"| {k} | {counts[k]} |")
    report.append("")
    report.append("结论：" + ("仍有 " + str(len(bad)) + " 处挂住/崩溃（见上表 HANG/CRASH）"
                            if bad else "全部风险输入都已变成「快速明确的结果或报错」，没有挂住/崩溃。"))
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")

    print(f"\nstatus counts: {counts}")
    print(f"report: {report_path}")
    if bad:
        print("STILL BROKEN: " + ", ".join(f"{fn}({st})" for fn, st, _ in bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
