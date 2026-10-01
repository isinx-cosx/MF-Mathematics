#include "convergence_theorems.h"

#include <algorithm>
#include <cmath>

#include "mt_internal.h"

namespace mf::measure_theory {

namespace {
using mf::measure_theory::detail::eval_fn;
using mf::measure_theory::detail::integrate_expr;
using mf::measure_theory::detail::integrate_fn;
}  // namespace

MonotoneResult monotone_convergence(const std::string& fn_expr,
                                    const std::string& f_expr,
                                    const std::vector<long long>& n_values,
                                    double a, double b) {
    MonotoneResult r;
    for (long long n : n_values)
        r.integral_values.push_back(integrate_fn(fn_expr, a, b, (double)n));
    r.limit_of_integrals = r.integral_values.back();
    r.integral_of_limit = integrate_expr(f_expr, a, b);
    r.difference = std::abs(r.limit_of_integrals - r.integral_of_limit);
    r.converged = r.difference < 0.01;
    return r;
}

FatouResult fatou_lemma(const std::string& fn_expr,
                        const std::vector<long long>& n_values, double a,
                        double b) {
    FatouResult r;
    for (long long n : n_values) {
        const auto f = [&](double t) {
            return std::max(eval_fn(fn_expr, t, (double)n), 0.0);
        };
        r.integral_values.push_back(
            mf::measure_theory::detail::simpson(f, a, b));
    }
    // ∫(liminf f_n):逐点取 min。
    const int pts = 500;
    std::vector<double> liminf_vals(pts);
    for (int i = 0; i < pts; ++i) {
        const double t = a + (b - a) * i / pts;
        double m = std::numeric_limits<double>::infinity();
        for (long long n : n_values) m = std::min(m, std::max(eval_fn(fn_expr, t, (double)n), 0.0));
        liminf_vals[i] = std::isfinite(m) ? m : 0.0;
    }
    r.integral_of_liminf = 0.0;
    {   // 对采样点做梯形积分。
        const double h = (b - a) / pts;
        double s = 0.5 * (liminf_vals[0] + liminf_vals[pts - 1]);
        for (int i = 1; i < pts - 1; ++i) s += liminf_vals[i];
        r.integral_of_liminf = s * h;
    }
    r.liminf_of_integrals =
        *std::min_element(r.integral_values.begin(), r.integral_values.end());
    r.inequality_holds = r.integral_of_liminf <= r.liminf_of_integrals + 1e-8;
    return r;
}

DominatedResult dominated_convergence(const std::string& fn_expr,
                                      const std::string& f_expr,
                                      const std::string& g_expr,
                                      const std::vector<long long>& n_values,
                                      double a, double b) {
    DominatedResult r;
    r.dominated = true;
    for (long long n : n_values) {
        for (int i = 0; i < 100; ++i) {
            const double t = a + (b - a) * i / 100;
            const double fn = eval_fn(fn_expr, t, (double)n);
            const double g = mf::measure_theory::detail::eval_double_str(g_expr, t);
            if (std::isfinite(fn) && std::isfinite(g) &&
                std::abs(fn) > g + 1e-10) {
                r.dominated = false;
                break;
            }
        }
        if (!r.dominated) break;
    }
    for (long long n : n_values)
        r.integral_values.push_back(integrate_fn(fn_expr, a, b, (double)n));
    r.limit_of_integrals = r.integral_values.back();
    r.integral_of_limit = integrate_expr(f_expr, a, b);
    r.g_integral = integrate_expr(g_expr, a, b);
    r.difference = std::abs(r.limit_of_integrals - r.integral_of_limit);
    return r;
}

}  // namespace mf::measure_theory
