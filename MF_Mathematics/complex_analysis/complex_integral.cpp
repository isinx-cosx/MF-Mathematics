#include "complex_integral.h"

#include <cmath>

#include "ca_internal.h"

namespace mf::complex_analysis {

std::complex<double> contour_integral_circle(const std::string& func,
                                             std::complex<double> center,
                                             double radius, double a, double b,
                                             long long n_points) {
    if (n_points <= 0) throw std::invalid_argument("n_points 必须为正");
    const auto f = [&](double t) {
        const std::complex<double> z_t = center + radius * std::complex<double>(std::cos(t), std::sin(t));
        const std::complex<double> dz = radius * std::complex<double>(-std::sin(t), std::cos(t));
        return detail::eval_complex(func, z_t) * dz;
    };
    return detail::simpson_c(f, a, b, (int)n_points);
}

CauchyTheoremResult cauchy_theorem(const std::string& func,
                                   std::complex<double> center,
                                   double radius) {
    CauchyTheoremResult r;
    r.integral = contour_integral_circle(func, center, radius, 0.0, 2.0 * detail::kPi);
    r.zero = std::abs(r.integral) < 1e-8;
    return r;
}

CauchyFormulaResult cauchy_integral_formula(const std::string& func,
                                            std::complex<double> a,
                                            std::complex<double> center,
                                            double radius, long long n_points) {
    const auto f = [&](double t) {
        const std::complex<double> z_t = center + radius * std::complex<double>(std::cos(t), std::sin(t));
        if (std::abs(z_t - a) < 1e-12) return std::complex<double>(0.0, 0.0);
        const std::complex<double> dz = radius * std::complex<double>(-std::sin(t), std::cos(t));
        return detail::eval_complex(func, z_t) / (z_t - a) * dz;
    };
    CauchyFormulaResult r;
    const std::complex<double> integral = detail::simpson_c(f, 0.0, 2.0 * detail::kPi, (int)n_points);
    r.cauchy_formula = integral / (2.0 * detail::kPi * std::complex<double>(0.0, 1.0));
    r.direct_f_a = detail::eval_complex(func, a);
    r.error = std::abs(r.cauchy_formula - r.direct_f_a);
    return r;
}

DerivativeFormulaResult derivative_formula(const std::string& func,
                                           std::complex<double> a, long long n,
                                           std::complex<double> center,
                                           double radius, long long n_points) {
    const long long order = n + 1;
    const auto f = [&](double t) {
        const std::complex<double> z_t = center + radius * std::complex<double>(std::cos(t), std::sin(t));
        if (std::abs(z_t - a) < 1e-12) return std::complex<double>(0.0, 0.0);
        const std::complex<double> dz = radius * std::complex<double>(-std::sin(t), std::cos(t));
        return detail::eval_complex(func, z_t) / std::pow(z_t - a, (double)order) * dz;
    };
    DerivativeFormulaResult r;
    const std::complex<double> integral = detail::simpson_c(f, 0.0, 2.0 * detail::kPi, (int)n_points);
    double fact = 1.0;
    for (long long k = 2; k <= n; ++k) fact *= (double)k;
    r.derivative = fact * integral / (2.0 * detail::kPi * std::complex<double>(0.0, 1.0));
    // 符号验证:f^{(n)}(a)。
    const auto zs = SymEngine::symbol("z");
    auto d = SymEngine::parse(func);
    for (long long k = 0; k < n; ++k) d = SymEngine::diff(d, zs);
    const auto sub = d->subs({{zs, SymEngine::complex_double(a)}});
    r.symbolic = SymEngine::eval_complex_double(*sub);
    return r;
}

}  // namespace mf::complex_analysis
