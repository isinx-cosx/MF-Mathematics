#include "lebesgue_integral.h"

#include <cmath>
#include <limits>

#include "mt_internal.h"

namespace mf::measure_theory {

namespace {
using mf::measure_theory::detail::eval_double_str;
using mf::measure_theory::detail::integrate_expr;
using mf::measure_theory::detail::find_roots;
using mf::measure_theory::detail::simpson;
}  // namespace

double integral_simple(const std::vector<double>& coefficients,
                       const std::vector<std::pair<double, double>>& sets) {
    if (coefficients.size() != sets.size())
        throw std::invalid_argument("系数与集合数量不匹配");
    double total = 0.0;
    for (std::size_t i = 0; i < sets.size(); ++i)
        total += coefficients[i] * std::abs(sets[i].second - sets[i].first);
    return total;
}

NonnegIntegralResult integral_nonnegative(const std::string& expr, double a,
                                          double b) {
    // 非负性检查。
    double fmax = 0.0;
    for (int i = 0; i < 100; ++i) {
        const double t = a + (b - a) * i / 100;
        const double v = eval_double_str(expr, t);
        if (std::isfinite(v) && v < -1e-10)
            throw std::invalid_argument("函数在定义域上并非处处非负，请用积分一般函数");
        if (std::isfinite(v) && v > fmax) fmax = v;
    }

    NonnegIntegralResult r;
    r.integral = integrate_expr(expr, a, b);

    // 分层逼近:值域等分,按 f 取值所在层计测度。
    const int n_steps = 1000;
    if (fmax > 0) {
        const double dy = fmax / n_steps;
        double mid_sum = 0.0;
        const int samples = 500;
        for (int k = 0; k < n_steps; ++k) {
            const double y_low = k * dy;
            const double y_mid = (k + 0.5) * dy;
            int in_level = 0;
            for (int s = 0; s < samples; ++s) {
                const double t = a + (b - a) * s / samples;
                const double v = eval_double_str(expr, t);
                if (std::isfinite(v) && v >= y_low && v < (k + 1) * dy)
                    ++in_level;
            }
            const double level_measure = (b - a) * (double)in_level / samples;
            mid_sum += y_mid * level_measure;
        }
        r.approximation = mid_sum;
    }
    return r;
}

GeneralIntegralResult integral_general(const std::string& expr, double a,
                                       double b) {
    GeneralIntegralResult r;
    const auto f = [&](double t) {
        const double v = eval_double_str(expr, t);
        return std::isfinite(v) ? v : 0.0;
    };
    r.pos = simpson([&](double t) { return std::max(f(t), 0.0); }, a, b);
    r.neg = simpson([&](double t) { return std::max(-f(t), 0.0); }, a, b);
    r.integral = r.pos - r.neg;
    return r;
}

ZeroSetResult integral_zero_set_independent(const std::string& f,
                                            const std::string& g, double a,
                                            double b) {
    ZeroSetResult r;
    const double int_f = integrate_expr(f, a, b);
    const double int_g = integrate_expr(g, a, b);
    r.are_equal = std::abs(int_f - int_g) < 1e-8;
    r.diff_points = find_roots("(" + f + ") - (" + g + ")", a, b);
    return r;
}

}  // namespace mf::measure_theory
