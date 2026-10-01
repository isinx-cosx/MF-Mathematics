#include "function_series.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/derivative.h>
#include <symengine/integer.h>
#include <symengine/parser.h>
#include <symengine/simplify.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include "ra_internal.h"

namespace mf::real_analysis {

namespace {
using mf::real_analysis::detail::eval_var;
using mf::real_analysis::detail::ExprEval2;
using mf::real_analysis::detail::integrate_expr;
using mf::real_analysis::detail::nan_d;
using mf::real_analysis::detail::sequence_limit_probe;

// 固定 x 处的数列极限 lim_{n→∞} f_n(x)。
//
// 旧实现比较 n = 1e6 与 n = 1e9 两项之差是否 < 1e-6(固定绝对容差)：
//   * 误差 ~1/n 的列(3/n、(2n+1)/(n+3)、n·x/(1+n·x))在 x 小的时候两项差
//     远大于 1e-6，于是被误报成「无极限」；
//   * 该判据本身也与 n 无关地固定，随 x 变化毫无道理。
// 现在改为：偶子列与奇子列各取 n_k = 1000·2^k 做 Richardson 外推，
// 两列都存在且相等才认定极限存在。
double fixed_x_limit(const ExprEval2& g, double x) {
    if (!g.ok()) return nan_d();
    const detail::SeqLimitProbe p =
        sequence_limit_probe([&](double n) { return g.at(x, n); });
    return p.ok ? p.value : nan_d();
}

// 级数通项代入 n=k 后的表达式字符串。
std::string term_at(const std::string& seq, long long k) {
    const auto n = SymEngine::symbol("n");
    const auto e = SymEngine::parse(seq);
    const auto sub = e->subs({{n, SymEngine::integer(k)}});
    return SymEngine::str(*sub);
}
}  // namespace

double pointwise_convergence(const std::string& seq_expr, double point) {
    const ExprEval2 g(seq_expr, "x", "n");
    return fixed_x_limit(g, point);
}

UniformConvergenceResult uniform_convergence(const std::string& seq_expr, double a,
                                            double b) {
    if (a > b) std::swap(a, b);
    const ExprEval2 g(seq_expr, "x", "n");
    const double width = b - a;

    auto f_of = [&](double xv) -> double { return fixed_x_limit(g, xv); };

    UniformConvergenceResult out;
    out.convergence_type = "逐点收敛（非一致）";

    // ── (1) 逐点极限函数 f(x) ────────────────────────────────────────────
    // 逐点极限在整个区间上存在是讨论一致收敛的前提；下面凡出现 ±∞/不收敛
    // 的点都单独记下来(连逐点收敛都不成立 ⇒ 更不可能一致)。
    const int NG = 200;
    std::vector<double> xs;
    std::vector<double> fv;
    xs.reserve(NG + 1);
    fv.reserve(NG + 1);
    for (int i = 0; i <= NG; ++i) {
        const double xv = a + width * i / NG;
        xs.push_back(xv);
        fv.push_back(f_of(xv));
    }
    bool pointwise_fails = false;
    for (std::size_t i = 0; i < xs.size(); ++i) {
        if (!std::isfinite(fv[i])) {
            const detail::SeqLimitProbe p =
                sequence_limit_probe([&](double n) { return g.at(xs[i], n); });
            // 无界 ⇒ 逐点收敛不成立；仅「数值上定不下来」则跳过该点。
            if (p.diverges) pointwise_fails = true;
            fv[i] = nan_d();
        }
    }

    // ── (2) 极限函数必须连续 ────────────────────────────────────────────
    // 各 f_n 连续时，一致收敛的极限函数必连续(Cantor/一致极限定理)。因此
    // 只要 f 在 [a,b] 上有一处跳跃，就一定不是一致收敛。这给出了「非一致」
    // 的一个严格充分判据，不依赖网格能否在 x 附近取到极值点。
    //   xⁿ 在 [0,1]: f(x)=0(x<1)、f(1)=1 ⇒ 在 1 处跳跃；
    //   n·x/(1+n·x): f(0)=0、f(x>0)=1 ⇒ 在 0 处跳跃。
    bool limit_discontinuous = false;
    if (!pointwise_fails) {
        const int nchk = 6;
        for (int j = 0; j <= nchk && !limit_discontinuous; ++j) {
            const double x0 = a + width * j / nchk;
            const double f0 = f_of(x0);
            if (!std::isfinite(f0)) continue;
            const double tol = 1e-6 * std::max(1.0, std::abs(f0));
            const double base = 0.25 * std::max(1.0, std::abs(x0));
            for (int s = 0; s < 2; ++s) {
                const double dir = (s == 0) ? -1.0 : 1.0;
                const double dist = dir < 0 ? (x0 - a) : (b - x0);
                if (!(dist > 0.0)) continue;  // 区间端点外侧不探测
                const double h0 = std::min(base, 0.5 * dist);
                const detail::LimitProbe p = detail::one_sided_limit(
                    [&](double t) { return f_of(t); }, x0, dir, h0);
                if (p.diverges ||
                    (p.ok && std::abs(p.value - f0) > tol)) {
                    limit_discontinuous = true;
                    break;
                }
            }
        }
    }

    // ── (3) sup_{[a,b]} |f_n − f| → 0 ──────────────────────────────────
    // n 逐级加倍，要求末三级都按正的幂次速度衰减(sup_{2n} ≤ 0.9·sup_n)，
    // 而不是与某个固定的 0.01 比较。
    const long long ns[5] = {10, 20, 40, 80, 160};
    for (long long nv : ns) {
        double mx = 0.0;
        for (std::size_t i = 0; i < xs.size(); ++i) {
            if (!std::isfinite(fv[i])) continue;
            const double fn = g.at(xs[i], static_cast<double>(nv));
            if (std::isfinite(fn)) mx = std::max(mx, std::abs(fn - fv[i]));
        }
        out.sup_diffs.push_back(mx);
    }
    const std::size_t K = out.sup_diffs.size() - 1;
    bool decays = (out.sup_diffs[K] == 0.0);  // sup 已精确为 0
    if (!decays) {
        decays = true;
        for (std::size_t k = K - 3; k < K; ++k)
            if (!(out.sup_diffs[k + 1] <= 0.9 * out.sup_diffs[k])) decays = false;
    }

    out.is_uniform = !pointwise_fails && !limit_discontinuous && decays;
    out.convergence_type = out.is_uniform ? "一致收敛" : "逐点收敛（非一致）";
    const double mid = 0.5 * (a + b);
    const double fm = f_of(mid);
    out.limit_function_value = std::isfinite(fm) ? fm : 0.0;
    return out;
}

WeierstrassResult weierstrass_m_test(const std::string& seq_expr, double a,
                                     double b) {
    WeierstrassResult r;
    for (long long nv : {10LL, 20LL, 50LL}) {
        double mx = 0.0;
        for (int i = 0; i <= 100; ++i) {
            const double x = a + (b - a) * i / 100;
            const double v = detail::eval_xn(seq_expr, x, (double)nv);
            if (std::isfinite(v)) mx = std::max(mx, std::abs(v));
        }
        r.M_values.push_back(mx);
    }
    // Σ M_n 收敛:末项小且递减。
    bool decreasing = r.M_values[0] >= r.M_values[1] &&
                      r.M_values[1] >= r.M_values[2];
    r.passes = decreasing && r.M_values[2] < 1e-3;
    return r;
}

TermwiseIntegralResult termwise_integration(const std::string& seq_expr, double a,
                                            double b, long long n_terms) {
    TermwiseIntegralResult r;
    for (long long k = 1; k <= n_terms; ++k) {
        const std::string term = term_at(seq_expr, k);
        try {
            r.termwise_sum += integrate_expr(term, a, b);
        } catch (...) {
        }
    }
    // 直接积分 Σ f_k。
    const auto n = SymEngine::symbol("n");
    const auto x = SymEngine::symbol("x");
    auto partial = SymEngine::parse("0");
    for (long long k = 1; k <= n_terms; ++k) {
        const auto e = SymEngine::parse(seq_expr);
        const auto term = e->subs({{n, SymEngine::integer(k)}});
        partial = SymEngine::add(partial, term);
    }
    const std::string partial_str = SymEngine::str(*partial);
    try {
        r.direct_integral = integrate_expr(partial_str, a, b);
    } catch (...) {
        r.direct_integral = r.termwise_sum;
    }
    return r;
}

TermwiseDiffResult termwise_differentiation(const std::string& seq_expr,
                                            long long n_terms) {
    TermwiseDiffResult r;
    const auto n = SymEngine::symbol("n");
    const auto x = SymEngine::symbol("x");
    auto diff_sum = SymEngine::parse("0");
    auto partial = SymEngine::parse("0");
    for (long long k = 1; k <= n_terms; ++k) {
        const auto e = SymEngine::parse(seq_expr);
        const auto term = e->subs({{n, SymEngine::integer(k)}});
        partial = SymEngine::add(partial, term);
        diff_sum = SymEngine::add(diff_sum, SymEngine::diff(term, x));
    }
    const auto direct = SymEngine::diff(partial, x);
    r.derivative_series = SymEngine::str(*SymEngine::simplify(diff_sum));
    const std::string direct_str = SymEngine::str(*SymEngine::simplify(direct));
    // 数值验证:两个结果在采样点上一致。
    r.verified = true;
    for (double xv : {0.0, 0.5, 1.5}) {
        const double a = eval_var(r.derivative_series, "x", xv);
        const double b = eval_var(direct_str, "x", xv);
        if (!(std::isfinite(a) && std::isfinite(b)) || std::abs(a - b) > 1e-9) {
            r.verified = false;
            break;
        }
    }
    return r;
}

}  // namespace mf::real_analysis
