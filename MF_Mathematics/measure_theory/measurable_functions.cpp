#include "measurable_functions.h"

#include <cmath>

#include "mt_internal.h"

#include <symengine/basic.h>
#include <symengine/integer.h>
#include <symengine/symbol.h>

namespace mf::measure_theory {

namespace {
using mf::measure_theory::detail::eval_double_expr;
using mf::measure_theory::detail::eval_double_str;
}  // namespace

MeasurableResult is_measurable(const std::string& expr, double a, double b) {
    MeasurableResult r;
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(expr);

    // 分母奇点:as_numer_denom 提分母,解分母零点。
    try {
        SymEngine::RCP<const SymEngine::Basic> num, den;
        SymEngine::as_numer_denom(e, outArg(num), outArg(den));
        if (!SymEngine::is_a<SymEngine::Integer>(*den)) {
            const auto den_str = SymEngine::str(*den);
            for (double root : mf::measure_theory::detail::find_roots(den_str, a, b))
                r.singularities.push_back(root);
        }
    } catch (...) {
    }

    // 粗网格兜底:定义域内出现大幅值(疑似极点)。
    if (r.singularities.empty()) {
        const int N = 400;
        for (int i = 0; i <= N; ++i) {
            const double t = a + (b - a) * i / N;
            const double v = eval_double_expr(e, x, t);
            if (std::isfinite(v) && std::abs(v) > 1e10) {
                r.singularities.push_back(t);
                break;
            }
        }
    }

    // 逐段连续函数(可去奇点除外)仍 Borel 可测 → 恒为可测。
    r.is_measurable = true;
    return r;
}

double simple_function_eval(const std::vector<double>& coefficients,
                            const std::vector<std::pair<double, double>>& sets,
                            double x) {
    double total = 0.0;
    const std::size_t n = coefficients.size() < sets.size()
                              ? coefficients.size()
                              : sets.size();
    for (std::size_t i = 0; i < n; ++i) {
        if (sets[i].first <= x && x <= sets[i].second)
            total += coefficients[i];
    }
    return total;
}

StepApproxResult step_function_approx(const std::string& expr, long long n,
                                      double a, double b) {
    if (n <= 0) throw std::invalid_argument("分段数必须为正整数");
    StepApproxResult r;
    r.dx = (b - a) / n;
    for (long long i = 0; i < n; ++i) {
        const double left = a + i * r.dx;
        const double right = a + (i + 1) * r.dx;
        const double val = eval_double_str(expr, left);
        r.values.push_back(val);
        r.intervals.emplace_back(left, right);
        r.integral += val * r.dx;
    }
    return r;
}

}  // namespace mf::measure_theory
