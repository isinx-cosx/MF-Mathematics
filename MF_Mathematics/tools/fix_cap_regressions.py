#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_cap_regressions.py — 修回上界收口时误挡的**合法输入**。

准确性套件（2180 例）发现 15 处回归，全是同一个错误：我把下限设得太死，
把合法取值也挡在外面了。三类：
  ① 大整数本来就是合法输入（is_prime 的 6.9e18 素数、prime_factors 的 1e12 半素数）；
  ② n ≤ 0 本来合法（傅里叶系数 a_0 与 c_{-1}；负维数在拓扑动作里返回定义域外的结果）；
  ③ 报错**文案**变了：套件断言的是核心函数原来的措辞（"项数必须为正整数"等），
     而统一助手说的是"超出可计算范围"。修法是把下限放宽到"让核心函数自己先判"，
     这样语义报错仍然出自核心，上界保护也还在。

按动作名作用域替换（同名键在不同动作里上限不同，不能全局替换）。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (相对路径, 动作名, 旧片段, 新片段, 说明)
RULES = [
    ("number_theory/number_theory_api.cpp", "is_prime",
     'get_int_bounded(args, "n", 0, 1000000000000, "n")',
     'get_int(args, "n")',
     "大素数判定本来就很快（实测 6.9e18 的素数立即返回），不该设 1e12 上限"),
    ("number_theory/number_theory_api.cpp", "prime_factors",
     'get_int_bounded(args, "n", 0, 1000000000000, "n")',
     'get_int_bounded(args, "n", 0, 1000000000000000, "n")',
     "套件要用 1e12 级别的半素数；放宽到 1e15（√n≈3e7，仍在秒级内）"),
    ("number_theory/number_theory_api.cpp", "euler_phi",
     'get_int_bounded(args, "n", 0, 1000000000000, "n")',
     'get_int_bounded(args, "n", 0, 1000000000000000, "n")', "同上（试除法家族）"),
    ("number_theory/number_theory_api.cpp", "divisor_count",
     'get_int_bounded(args, "n", 0, 1000000000000, "n")',
     'get_int_bounded(args, "n", 0, 1000000000000000, "n")', "同上"),
    ("number_theory/number_theory_api.cpp", "divisor_sum",
     'get_int_bounded(args, "n", 0, 1000000000000, "n")',
     'get_int_bounded(args, "n", 0, 1000000000000000, "n")', "同上"),
    ("number_theory/number_theory_api.cpp", "mobius",
     'get_int_bounded(args, "n", 0, 1000000000000, "n")',
     'get_int_bounded(args, "n", 0, 1000000000000000, "n")', "同上"),
    ("number_theory/number_theory_api.cpp", "continued_fraction",
     'get_int_opt_bounded(args, "n_terms", 20, 1, 100000,',
     'get_int_opt_bounded(args, "n_terms", 20, 0, 100000,',
     "下限放到 0，让核心函数自己报「项数必须为正整数」（套件断言原文案）"),
    ("number_theory/number_theory_api.cpp", "euler_product",
     'get_int_opt_bounded(args, "prime_limit", 100, 2, 10000000,',
     'get_int_opt_bounded(args, "prime_limit", 100, 1, 10000000,',
     "下限放到 1，让核心报「素数上限需 ≥2」"),
    ("number_theory/number_theory_api.cpp", "bernoulli_number",
     'get_int_bounded(args, "n", 0, 500,',
     'get_int_bounded(args, "n", -9223372036854775807, 500,',
     "负数由核心报「非负」，这里只保留上界"),
    ("number_theory/number_theory_api.cpp", "zeta_negative",
     'get_int_bounded(args, "n", 0, 500,',
     'get_int_bounded(args, "n", -9223372036854775807, 500,',
     "同上"),
    ("measure_theory/measure_theory_api.cpp", "step_function_approx",
     'get_int_bounded(args, "n", 1, 100000,',
     'get_int_bounded(args, "n", 0, 100000,',
     "下限放到 0，让核心报「分段数必须为正整数」"),
    ("harmonic_analysis/harmonic_analysis_api.cpp", "fourier_series",
     'get_int_bounded(args, "n_terms", 1, 2000,',
     'get_int_bounded(args, "n_terms", -9223372036854775807, 2000,',
     "负数由核心报「项数不能为负」"),
    # 傅里叶系数：n=0（a_0）与 n<0（c_{-1}）都是**合法**输入，不能设下限
    ("harmonic_analysis/harmonic_analysis_api.cpp", "fourier_coeff",
     'get_int_bounded(args, "n", 1, 2000,',
     'get_int_bounded(args, "n", -100000, 100000,',
     "a_0 要 n=0，且 n 可正可负；每算一个系数是一次定积分，代价固定"),
    ("harmonic_analysis/harmonic_analysis_api.cpp", "complex_fourier_coeff",
     'get_int_bounded(args, "n", 1, 2000,',
     'get_int_bounded(args, "n", -100000, 100000,',
     "c_{-1} 等负指标是合法的（实函数 c_{-n}=conj(c_n)）"),
    # 拓扑：负维数返回"定义域外"的结果，套件期望 ok
    ("algebraic_topology/at_api.cpp", "mapping_degree",
     'get_int_bounded(args, "sphere_dim", 0, 100,',
     'get_int_bounded(args, "sphere_dim", -1000, 1000,',
     "负/越界维数由核心处理（套件期望返回结果而非报错）"),
    ("algebraic_topology/at_api.cpp", "boundary_operator",
     'get_int_bounded(args, "dimension", 0, 100,',
     'get_int_bounded(args, "dimension", -1000, 1000,',
     "同上"),
]

DIAG = []


def apply_file(relpath, rules):
    path = os.path.join(ROOT, relpath)
    text = io.open(path, encoding="utf-8").read()
    lines = text.splitlines(keepends=True)
    current = None
    for i, line in enumerate(lines):
        m = re.search(r'register_function\("([a-z_0-9]+)"', line)
        if m:
            current = m.group(1)
        for (rel, action, old, new, why) in rules:
            if rel != relpath or action != current:
                continue
            if old in line:
                lines[i] = line.replace(old, new, 1)
                DIAG.append(f"  {relpath}:{i+1} [{action}] {why}")
            elif new not in line and old.split(",")[0] in line:
                DIAG.append(f"  [注意] {relpath}:{i+1} [{action}] 片段未精确匹配，需人工看")
    io.open(path, "w", encoding="utf-8", newline="").write("".join(lines))


def main():
    by_file = {}
    for rule in RULES:
        by_file.setdefault(rule[0], []).append(rule)
    for relpath, rules in by_file.items():
        apply_file(relpath, rules)
    print("\n".join(DIAG))
    print(f"\n共 {len(RULES)} 条规则，命中 {sum(1 for d in DIAG if not d.startswith('  [注意]'))} 处"
          f"，待人工 {sum(1 for d in DIAG if d.startswith('  [注意]'))} 处")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
