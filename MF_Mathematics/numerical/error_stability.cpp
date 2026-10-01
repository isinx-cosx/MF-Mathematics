#include "error_stability.h"

#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

#include "expr_util.h"

namespace mf::numerical {

namespace {

// 级数前 n+1 项部分和(与 Python self_test 的 exp_series 同构)。
double series_partial_sum(const std::string& series, double x, long long n) {
    if (series == "exp") {
        double s = 0.0, term = 1.0;
        for (long long k = 0; k <= n; ++k) {
            s += term;
            term *= x / static_cast<double>(k + 1);
        }
        return s;
    }
    if (series == "sin") {
        double s = 0.0;
        for (long long k = 0; k <= n; ++k) {
            const long long j = 2 * k + 1;
            const double fact = [&] {
                double f = 1.0;
                for (long long t = 2; t <= j; ++t) f *= t;
                return f;
            }();
            s += (k % 2 == 0 ? 1.0 : -1.0) * std::pow(x, j) / fact;
        }
        return s;
    }
    if (series == "cos") {
        double s = 0.0;
        for (long long k = 0; k <= n; ++k) {
            const long long j = 2 * k;
            const double fact = [&] {
                double f = 1.0;
                for (long long t = 2; t <= j; ++t) f *= t;
                return f;
            }();
            s += (k % 2 == 0 ? 1.0 : -1.0) * std::pow(x, j) / fact;
        }
        return s;
    }
    if (series == "ln") {
        double s = 0.0;
        for (long long k = 1; k <= n; ++k)
            s += (k % 2 == 1 ? 1.0 : -1.0) * std::pow(x, k) / static_cast<double>(k);
        return s;
    }
    if (series == "geometric") {
        double s = 0.0, term = 1.0;
        for (long long k = 0; k <= n; ++k) {
            s += term;
            term *= x;
        }
        return s;
    }
    throw std::invalid_argument("未知级数: " + series);
}

}  // namespace

double condition_number(const std::string& f, double x, double eps) {
    const auto ff = make_unary(f);
    const double fx = ff(x);
    if (std::abs(fx) < 1e-15) return std::numeric_limits<double>::infinity();
    const double f_prime = (ff(x + eps) - ff(x - eps)) / (2 * eps);
    return std::abs(x * f_prime / fx);
}

double truncation_error(const std::string& series, double x, long long n,
                        double true_value) {
    const double approx = series_partial_sum(series, x, n);
    if (std::abs(true_value) > 1e-15) return std::abs(approx - true_value);
    const double approx_next = series_partial_sum(series, x, n + 1);
    return std::abs(approx - approx_next);
}

double rounding_error_estimate(long long precision) {
    return std::pow(10.0, -static_cast<double>(precision));
}

bool is_stable(const std::string& f, double x) {
    const auto ff = make_unary(f);
    const double ref = ff(x);
    const double perturbed = ff(x * (1.0 + 1e-8));
    const double rel_diff =
        std::abs(perturbed - ref) / (std::abs(ref) + 1e-15);
    return rel_diff < 1e-4;
}

}  // namespace mf::numerical
