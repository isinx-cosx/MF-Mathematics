// mt_internal.h — measure_theory 包共享辅助(仅头文件)。
//
// 提供:集合工具(表示为排序去重的 long long 向量)、表达式实数求值、
// 实数辛普森积分、含 n 参数的函数列求值/积分。

#pragma once

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/eval_double.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

namespace mf::measure_theory::detail {

inline constexpr double kPi = 3.14159265358979323846;

// ── 集合工具:集合表示为排序去重的 long long 向量 ──────────────────────────

inline std::vector<long long> sort_uniq(std::vector<long long> v) {
    std::sort(v.begin(), v.end());
    v.erase(std::unique(v.begin(), v.end()), v.end());
    return v;
}

inline std::vector<long long> set_union(const std::vector<long long>& a,
                                        const std::vector<long long>& b) {
    std::vector<long long> out;
    out.reserve(a.size() + b.size());
    out.insert(out.end(), a.begin(), a.end());
    out.insert(out.end(), b.begin(), b.end());
    return sort_uniq(std::move(out));
}

inline std::vector<long long> set_intersect(const std::vector<long long>& a,
                                            const std::vector<long long>& b) {
    std::vector<long long> out;
    std::set_intersection(a.begin(), a.end(), b.begin(), b.end(),
                          std::back_inserter(out));
    return out;
}

// 补集:全集中去掉 s 的元素。s 与 X 均已排序去重。
inline std::vector<long long> set_complement(const std::vector<long long>& s,
                                             const std::vector<long long>& X) {
    std::vector<long long> out;
    std::set_difference(X.begin(), X.end(), s.begin(), s.end(),
                        std::back_inserter(out));
    return out;
}

inline bool set_equal(const std::vector<long long>& a,
                      const std::vector<long long>& b) {
    return a == b;
}

// 归一化集合系:每个集合排序去重,整体去重(无序比较)。
inline std::vector<std::vector<long long>> normalize_collection(
    const std::vector<std::vector<long long>>& coll) {
    std::vector<std::vector<long long>> out;
    for (const auto& s : coll) {
        const auto ns = sort_uniq(s);
        if (std::find(out.begin(), out.end(), ns) == out.end())
            out.push_back(ns);
    }
    return out;
}

inline bool contains_set(const std::vector<std::vector<long long>>& coll,
                         const std::vector<long long>& s) {
    return std::find(coll.begin(), coll.end(), s) != coll.end();
}

// ── 表达式求值 ──────────────────────────────────────────────────────────────

// 表达式在实数点 x 处的值(纯实数表达式)。异常返回 NaN。
inline double eval_double_expr(
    const SymEngine::RCP<const SymEngine::Basic>& e,
    const SymEngine::RCP<const SymEngine::Symbol>& x, double t) {
    try {
        const auto sub = e->subs({{x, SymEngine::real_double(t)}});
        return SymEngine::eval_double(*sub);
    } catch (...) {
        return std::numeric_limits<double>::quiet_NaN();
    }
}

inline double eval_double_str(const std::string& expr, double t) {
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(expr);
    return eval_double_expr(e, x, t);
}

// 含 n 的函数列 f_n(x):代入 n 后求值。
inline double eval_fn(const std::string& expr_str, double x_val, double n_val) {
    const auto x = SymEngine::symbol("x");
    const auto n = SymEngine::symbol("n");
    const auto e = SymEngine::parse(expr_str);
    const auto sub = e->subs({{x, SymEngine::real_double(x_val)},
                              {n, SymEngine::real_double(n_val)}});
    return SymEngine::eval_double(*sub);
}

// ── 实数辛普森(std::function 版)─────────────────────────────────────────────

inline double simpson(const std::function<double(double)>& f, double a, double b,
                      int n = 2000) {
    if (n % 2 != 0) ++n;
    const double h = (b - a) / n;
    double s = f(a) + f(b);
    for (int i = 1; i < n; ++i) {
        const double x = a + i * h;
        s += (i % 2 == 1) ? 4.0 * f(x) : 2.0 * f(x);
    }
    return s * h / 3.0;
}

// 表达式在 [a,b] 上的辛普森积分。
inline double integrate_expr(const std::string& expr, double a, double b) {
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(expr);
    return simpson([&](double t) { return eval_double_expr(e, x, t); }, a, b);
}

// 含 n 的函数列在 [a,b] 上代入 n 后的积分。
inline double integrate_fn(const std::string& expr_str, double a, double b,
                           double n_val) {
    const auto x = SymEngine::symbol("x");
    const auto n = SymEngine::symbol("n");
    const auto e = SymEngine::parse(expr_str);
    const auto sub = e->subs({{n, SymEngine::real_double(n_val)}});
    return simpson([&](double t) {
        const auto s = sub->subs({{x, SymEngine::real_double(t)}});
        return SymEngine::eval_double(*s);
    }, a, b);
}

// f-g=0 在 [a,b] 内的实根(先试 symengine solve,给不出可用实根时用网格扫描兜底)。
//
// 网格兜底必须同时覆盖三类根,缺一都会漏根:
//   1) 根落在区间内部并把符号分开(奇数重根) → 二分细化;
//   2) 根**恰落在网格节点上** → 该点 f 恰为 0,严格变号判据 pv*v < 0 永远不成立,
//      必须显式检查 |f(节点)| ≈ 0(否则 π/4 这类"根正好等于 (b-a)·i/N"的情形会漏);
//   3) **偶数重根**(两侧不变号,如 (x-0.5)²) → 对 |f| 的局部极小做三分细化找候选,
//      细化后仍需 |f| ≈ 0 才认作根,避免把普通局部极小误判成根。
inline std::vector<double> find_roots(const std::string& expr, double a,
                                      double b) {
    std::vector<double> roots;
    const auto x = SymEngine::symbol("x");
    // 解析一次供后续复用(解析失败与原实现一致:异常直接抛给调用方/API 层)。
    const auto e = SymEngine::parse(expr);
    try {
        // 若恒为 0:处处是根,返回空(调用方按"相等"处理)。
        if (SymEngine::eq(*SymEngine::simplify(e), *SymEngine::zero)) return {};
        const auto sol = SymEngine::solve(e, x);
        if (SymEngine::is_a<SymEngine::FiniteSet>(*sol)) {
            const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*sol);
            for (const auto& r : fs.get_args()) {
                try {
                    const double v = SymEngine::eval_double(*r);
                    if (std::isfinite(v) && v >= a - 1e-9 && v <= b + 1e-9)
                        roots.push_back(v);
                } catch (...) {
                }
            }
        }
    } catch (...) {
    }
    std::sort(roots.begin(), roots.end());
    roots.erase(std::unique(roots.begin(), roots.end(),
                            [](double p, double q) { return std::abs(p - q) < 1e-6; }),
                roots.end());
    if (!roots.empty()) return roots;

    // ── 网格扫描兜底 ────────────────────────────────────────────────────────
    const auto f = [&](double t) { return eval_double_expr(e, x, t); };
    const int N = 2000;
    std::vector<double> vals(N + 1);
    double vmax = 0.0;
    for (int i = 0; i <= N; ++i) {
        const double v = f(a + (b - a) * i / N);
        vals[i] = v;
        if (std::isfinite(v)) vmax = std::max(vmax, std::abs(v));
    }
    // |f| ≈ 0 的判据:按函数自身量级取相对容差(对 f 整体缩放不敏感)。
    const double tol0 = 1e-12 * std::max(1.0, vmax);

    auto add_root = [&](double r) {
        if (std::isfinite(r) && r >= a - 1e-9 && r <= b + 1e-9) roots.push_back(r);
    };

    // (1)(2) 变号根与"根恰在节点上"。
    if (std::abs(vals[0]) <= tol0) add_root(a);
    for (int i = 1; i <= N; ++i) {
        const double t = a + (b - a) * i / N;
        const double pv = vals[i - 1], v = vals[i];
        if (std::isfinite(v) && std::abs(v) <= tol0) add_root(t);
        if (std::isfinite(pv) && std::isfinite(v) && pv * v < 0.0) {
            double lo = a + (b - a) * (i - 1) / N, hi = t, flo = pv;
            for (int it = 0; it < 60; ++it) {
                const double m = 0.5 * (lo + hi);
                const double fm = f(m);
                if (!std::isfinite(fm)) break;
                if (flo * fm <= 0.0) { hi = m; } else { lo = m; flo = fm; }
            }
            add_root(0.5 * (lo + hi));
        }
    }

    // (3) 偶数重根:|f| 在节点 i 处形成下凹(允许相邻节点取等值,即极小时恰在两节点之间)。
    for (int i = 1; i < N; ++i) {
        if (!std::isfinite(vals[i - 1]) || !std::isfinite(vals[i]) ||
            !std::isfinite(vals[i + 1]))
            continue;
        const double am = std::abs(vals[i]), al = std::abs(vals[i - 1]),
                     ar = std::abs(vals[i + 1]);
        if (am <= tol0) continue;                        // 已由节点判据处理
        if (!(am <= al && am <= ar && (am < al || am < ar))) continue;
        double lo = a + (b - a) * (i - 1) / N;
        double hi = a + (b - a) * (i + 1) / N;
        for (int it = 0; it < 100; ++it) {               // 三分搜索 |f| 的极小
            const double m1 = lo + (hi - lo) / 3.0, m2 = hi - (hi - lo) / 3.0;
            const double f1 = std::abs(f(m1)), f2 = std::abs(f(m2));
            if (!std::isfinite(f1) || !std::isfinite(f2)) break;
            if (f1 <= f2) hi = m2; else lo = m1;
        }
        const double m = 0.5 * (lo + hi);
        const double fm = std::abs(f(m));
        if (std::isfinite(fm) && fm <= tol0) add_root(m); // 只有真的落到 0 才算根
    }

    std::sort(roots.begin(), roots.end());
    roots.erase(std::unique(roots.begin(), roots.end(),
                            [](double p, double q) { return std::abs(p - q) < 1e-6; }),
                roots.end());
    return roots;
}

}  // namespace mf::measure_theory::detail
