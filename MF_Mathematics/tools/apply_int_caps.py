#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_int_caps.py — 把"用户给的整数直接当循环次数/分配尺寸"的参数统一收口成带上界的读取。

对应 stress_scan 的实测结果与静态审计：bernoulli_number/taylor/power_series/fourier_series/
termwise_*/poisson_summation/eratosthenes/prime_factors... 一个大数就能把界面卡死。

规则表里每一行都指定：文件、行号、参数键、是否可选、下限、上限、面向用户的中文名。
按行号**自下而上**替换，避免行号漂移。只替换该行第一个匹配，不做全局替换
（同一个文件里同名键的多个动作上限并不相同）。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (相对路径, 行号, 键, 模式, 下限, 上限, 中文名)
RULES = [
    # ── 数论：试除法家族（代价 ~√n），以及筛法/BSGS（按内存与时间定上限）──
    ("number_theory/number_theory_api.cpp", 113, "n", "req", 0, 10**12, "n"),
    ("number_theory/number_theory_api.cpp", 116, "n", "req", 0, 10**12, "n"),
    ("number_theory/number_theory_api.cpp", 119, "n", "req", 0, 10**12, "n"),
    ("number_theory/number_theory_api.cpp", 122, "n", "req", 0, 10**12, "n"),
    ("number_theory/number_theory_api.cpp", 125, "n", "req", 0, 10**7, "n"),
    ("number_theory/number_theory_api.cpp", 156, "p", "req", 2, 10**9, "p"),
    ("number_theory/number_theory_api.cpp", 161, "p", "req", 2, 10**12, "p"),
    ("number_theory/number_theory_api.cpp", 166, "n", "req", 2, 10**8, "n（筛法上限）"),
    ("number_theory/number_theory_api.cpp", 169, "n", "req", 2, 10**9, "n"),
    ("number_theory/number_theory_api.cpp", 170, "segment_size", "opt", 1000, 10**7, "segment_size"),
    ("number_theory/number_theory_api.cpp", 189, "n", "req", 0, 10**12, "n"),
    ("number_theory/number_theory_api.cpp", 192, "n", "req", 0, 10**12, "n"),
    ("number_theory/number_theory_api.cpp", 206, "n_terms", "opt", 1, 10**5, "连分数项数"),
    ("number_theory/number_theory_api.cpp", 223, "max_denom", "opt", 1, 10**9, "分母上限"),
    ("number_theory/number_theory_api.cpp", 234, "prime_limit", "opt", 2, 10**7, "素数上限"),
    ("number_theory/number_theory_api.cpp", 238, "n_terms", "opt", 1, 10**6, "级数项数"),
    ("number_theory/number_theory_api.cpp", 242, "n_terms", "opt", 1, 10**6, "级数项数"),
    ("number_theory/number_theory_api.cpp", 253, "n", "req", 0, 500, "伯努利数阶 n"),
    ("number_theory/number_theory_api.cpp", 256, "n", "req", 0, 500, "ζ 自变量的阶 n"),

    # ── 分形：宽高与迭代次数（w*h 的组合上限在下面单独加）──
    ("fractal_api.cpp", 25, "width", "opt", 1, 4000, "宽度"),
    ("fractal_api.cpp", 26, "height", "opt", 1, 4000, "高度"),
    ("fractal_api.cpp", 27, "max_iter", "opt", 1, 100000, "最大迭代次数"),

    # ── 调和分析：级数项数与 STFT 窗口 ──
    ("harmonic_analysis/harmonic_analysis_api.cpp", 90, "n", "req", 1, 2000, "项数"),
    ("harmonic_analysis/harmonic_analysis_api.cpp", 100, "n_terms", "req", 1, 2000, "傅里叶级数项数"),
    ("harmonic_analysis/harmonic_analysis_api.cpp", 116, "n", "req", 1, 2000, "项数"),
    ("harmonic_analysis/harmonic_analysis_api.cpp", 242, "window_size", "req", 2, 65536, "窗口长度"),
    ("harmonic_analysis/harmonic_analysis_api.cpp", 243, "hop_size", "opt", 0, 65536, "步长"),
    ("harmonic_analysis/harmonic_analysis_api.cpp", 276, "n_terms", "opt", 1, 2000, "泊松求和项数"),
    ("harmonic_analysis/harmonic_analysis_api.cpp", 290, "n_terms", "opt", 1, 2000, "项数"),

    # ── 复分析：围道点数（每点重新 parse）与级数阶数 ──
    ("complex_analysis/complex_analysis_api.cpp", 136, "n_points", "opt", 8, 10**4, "围道点数"),
    ("complex_analysis/complex_analysis_api.cpp", 156, "n_points", "opt", 8, 10**4, "围道点数"),
    ("complex_analysis/complex_analysis_api.cpp", 170, "n", "req", 0, 100, "阶数"),
    ("complex_analysis/complex_analysis_api.cpp", 171, "n_points", "opt", 8, 10**4, "围道点数"),
    ("complex_analysis/complex_analysis_api.cpp", 282, "n", "opt", 0, 200, "级数项数"),
    ("complex_analysis/complex_analysis_api.cpp", 288, "n", "opt", 0, 200, "级数项数"),
    ("complex_analysis/complex_analysis_api.cpp", 324, "n_terms", "opt", 1, 10**6, "级数项数"),

    # ── 微积分：求导阶数、泰勒/幂级数阶数 ──
    ("calculus/calculus_api.cpp", 47, "order", "opt", 0, 1000, "求导阶数"),
    ("calculus/calculus_api.cpp", 55, "order", "opt", 0, 1000, "求导阶数"),
    ("calculus/calculus_api.cpp", 218, "order", "opt", 0, 200, "泰勒展开阶数"),
    ("calculus/calculus_api.cpp", 278, "n", "opt", 0, 200, "幂级数项数"),

    # ── 测度论：阶梯函数逼近层数 ──
    ("measure_theory/measure_theory_api.cpp", 251, "n", "req", 1, 10**5, "阶梯数"),

    # ── 数值：积分节点数、相图分辨率、迭代次数、拟合阶数 ──
    ("numerical/numerical_api.cpp", 143, "n", "opt", 1, 10**7, "积分节点数"),
    ("numerical/numerical_api.cpp", 147, "n", "opt", 1, 10**7, "积分节点数"),
    ("numerical/numerical_api.cpp", 151, "n", "opt", 1, 10**7, "节点数"),
    ("numerical/numerical_api.cpp", 190, "n_trajectories", "opt", 1, 100, "轨迹条数"),
    ("numerical/numerical_api.cpp", 191, "resolution", "opt", 2, 200, "相图分辨率"),
    ("numerical/numerical_api.cpp", 233, "degree", "opt", 0, 20, "拟合阶数"),
    ("numerical/numerical_api.cpp", 251, "n", "req", 1, 10**6, "采样点数"),
    ("numerical/numerical_api.cpp", 266, "max_iter", "opt", 1, 10**5, "最大迭代次数"),
    ("numerical/numerical_api.cpp", 291, "max_iter", "opt", 1, 10**5, "最大迭代次数"),
    ("numerical/numerical_api.cpp", 301, "max_iter", "opt", 1, 10**5, "最大迭代次数"),
    ("numerical/numerical_api.cpp", 311, "max_iter", "opt", 1, 10**5, "最大迭代次数"),
    ("numerical/numerical_api.cpp", 318, "max_iter", "opt", 1, 10**5, "最大迭代次数"),
    ("numerical/numerical_api.cpp", 330, "max_iter", "opt", 1, 10**5, "最大迭代次数"),

    # ── 实分析：柯西准则样本数、逐项积分/微分项数 ──
    ("real_analysis/real_analysis_api.cpp", 61, "n", "opt", 1, 100, "项数"),
    ("real_analysis/real_analysis_api.cpp", 67, "n", "opt", 1, 100, "项数"),
    ("real_analysis/real_analysis_api.cpp", 113, "max_n", "opt", 1, 10**5, "最大项数"),
    ("real_analysis/real_analysis_api.cpp", 264, "n_terms", "opt", 1, 2000, "逐项积分项数"),
    ("real_analysis/real_analysis_api.cpp", 272, "n_terms", "opt", 1, 2000, "逐项微分项数"),

    # ── 泛函：内积采样点数 ──
    ("functional_analysis/fa_api.cpp", 264, "n_points", "opt", 1, 10**6, "采样点数"),

    # ── 代数：排列组合与数列项数 ──
    ("algebra/algebra_api.cpp", 86, "n", "req", 0, 10**6, "n"),
    ("algebra/algebra_api.cpp", 89, "n", "req", 0, 10**6, "n"),
    ("algebra/algebra_api.cpp", 100, "n", "req", 0, 1000, "二项式指数 n"),
    ("algebra/algebra_api.cpp", 105, "n", "req", 0, 1000, "二项式指数 n"),
    ("algebra/algebra_api.cpp", 577, "n", "req", 0, 10**5, "项数"),
    ("algebra/algebra_api.cpp", 591, "n", "req", 0, 10**5, "项数"),
    ("algebra/algebra_api.cpp", 598, "n", "req", 0, 10**5, "项数"),
    ("algebra/algebra_api.cpp", 612, "n", "req", 0, 10**5, "项数"),

    # ── 拓扑：同调/同伦的维数与球面维数（内部按维数组合式增长）──
    ("algebraic_topology/at_api.cpp", 136, "n", "req", 0, 100, "维数 n"),
    ("algebraic_topology/at_api.cpp", 143, "n", "req", 0, 100, "维数 n"),
    ("algebraic_topology/at_api.cpp", 150, "max_dim", "opt", 0, 20, "最大维数"),
    ("algebraic_topology/at_api.cpp", 196, "sphere_dim", "req", 0, 100, "球面维数"),
    ("algebraic_topology/at_api.cpp", 213, "sphere_dim", "req", 0, 100, "球面维数"),
    ("algebraic_topology/at_api.cpp", 221, "dimension", "req", 0, 100, "维数"),
    ("algebraic_topology/at_api.cpp", 239, "max_dim", "opt", 0, 20, "最大维数"),

    # ── 概率：二项/正态样本规模 ──
    ("probability/probability_api.cpp", 286, "n", "req", 0, 10**6, "试验次数"),
    ("probability/probability_api.cpp", 357, "n", "req", 1, 10**6, "样本数"),
    ("probability/probability_api.cpp", 367, "n", "req", 1, 10**6, "样本数"),
    ("probability/probability_api.cpp", 381, "n", "req", 1, 10**6, "样本数"),
    ("probability/probability_api.cpp", 517, "window", "opt", 1, 10**6, "窗口"),
    ("probability/probability_api.cpp", 535, "forecast_steps", "opt", 0, 10**6, "预测步数"),

    # ── extras：数值积分区间重复次数 ──
    ("extras/extras_api.cpp", 137, "b", "opt", 0, 10**6, "上界"),
]

DIAG = []


def apply_file(relpath, edits):
    path = os.path.join(ROOT, relpath)
    with io.open(path, encoding="utf-8") as f:
        lines = f.readlines()
    # 自下而上，行号不漂移
    for (line_no, key, mode, lo, hi, label) in sorted(edits, key=lambda e: -e[0]):
        idx = line_no - 1
        if idx < 0 or idx >= len(lines):
            DIAG.append(f"  [跳过] {relpath}:{line_no} 超出行范围")
            continue
        src = lines[idx]
        if mode == "req":
            pat = re.compile(r'get_int\(args,\s*"%s"\)' % re.escape(key))
            rep = 'get_int_bounded(args, "%s", %d, %d, "%s")' % (key, lo, hi, label)
        else:
            pat = re.compile(r'get_int_opt\(args,\s*"%s",\s*(-?\d+)\)' % re.escape(key))
            m = pat.search(src)
            if not m:
                DIAG.append(f"  [跳过] {relpath}:{line_no} 未匹配 get_int_opt(args, \"{key}\", N)")
                continue
            rep = 'get_int_opt_bounded(args, "%s", %s, %d, %d, "%s")' % (key, m.group(1), lo, hi, label)
        if not pat.search(src):
            DIAG.append(f"  [跳过] {relpath}:{line_no} 未匹配 {key} ({mode})")
            continue
        new = pat.sub(rep, src, count=1)
        lines[idx] = new
        DIAG.append(f"  {relpath}:{line_no}\n    - {src.strip()}\n    + {new.strip()}")
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)


def main():
    by_file = {}
    for rule in RULES:
        by_file.setdefault(rule[0], []).append(rule[1:])
    dry = "--dry" in sys.argv
    for relpath, edits in by_file.items():
        apply_file(relpath, edits)
    print("\n".join(DIAG))
    print(f"\n共 {len(RULES)} 条规则，实际改动 {sum(1 for d in DIAG if not d.startswith('  [跳过]'))} 处"
          f"，跳过 {sum(1 for d in DIAG if d.startswith('  [跳过]'))} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
