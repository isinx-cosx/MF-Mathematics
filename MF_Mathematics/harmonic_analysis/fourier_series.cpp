// fourier_series.cpp — 傅里叶级数内核(数值积分,基于 Simpson)。

#include "fourier_series.h"

#include <charconv>
#include <cmath>
#include <complex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/functions.h>
#include <symengine/mul.h>
#include <symengine/parser.h>
#include <symengine/symbol.h>

#include "ha_internal.h"

namespace mf::harmonic_analysis {

using detail::real_fv;
using detail::simpson;
using detail::complex_exp_integral;
using detail::kPi;

namespace {

using SymEngine::RCP;
using SymEngine::Basic;
using SymEngine::Symbol;

// 数值格式:整数去小数点。
std::string fmt(double v) {
    if (std::abs(v) < 1e-12) v = 0.0;
    char buf[32];
    const auto res = std::to_chars(buf, buf + sizeof(buf), v,
                                   std::chars_format::general);
    return std::string(buf, res.ptr);
}

// ∫_0^T f(x)·cos/sin(2πnx/T) dx(数值)。
double trig_integral(const std::string& f, long long n, double T,
                     const std::string& type) {
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(f);
    const double k = 2.0 * kPi * n / T;
    RCP<const Basic> integrand;
    if (type == "cos")
        integrand = SymEngine::mul(e, SymEngine::cos(SymEngine::mul(
                                          SymEngine::real_double(k), x)));
    else
        integrand = SymEngine::mul(e, SymEngine::sin(SymEngine::mul(
                                          SymEngine::real_double(k), x)));
    return simpson(detail::real_fv(integrand, x), 0.0, T, 2000);
}

// 复积分 ∫_0^T f(x)·e^{-i·k·x} dx(拆实虚部)。
std::complex<double> complex_integral(const std::string& f, double k, double T) {
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(f);
    return detail::complex_exp_integral(e, x, k, 0.0, T, 2000);
}

}  // namespace

FourierCoeffResult fourier_coeff(const std::string& f, long long n, double period,
                                 const std::string& coeff_type) {
    if (period <= 0) throw std::invalid_argument("周期必须为正");
    FourierCoeffResult r;
    if (coeff_type == "cos") {
        r.name = n == 0 ? "a_0" : "a_" + std::to_string(n);
        const double coeff = n == 0 ? 1.0 / period : 2.0 / period;
        if (n == 0) {
            const auto x = SymEngine::symbol("x");
            r.value = coeff * simpson(detail::real_fv(SymEngine::parse(f), x), 0.0,
                                      period, 2000);
        } else {
            r.value = coeff * trig_integral(f, n, period, "cos");
        }
    } else if (coeff_type == "sin") {
        r.name = "b_" + std::to_string(n);
        if (n == 0) {
            r.value = 0.0;  // b_0 ≡ 0
        } else {
            r.value = (2.0 / period) * trig_integral(f, n, period, "sin");
        }
    } else {
        throw std::invalid_argument("coeff_type 必须为 'cos' 或 'sin'");
    }
    return r;
}

FourierSeriesResult fourier_series(const std::string& f, long long n_terms,
                                   double period) {
    if (n_terms < 0) throw std::invalid_argument("项数不能为负");
    FourierSeriesResult r;
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(f);
    const double a0 = simpson(detail::real_fv(e, x), 0.0, period, 2000) / period;
    r.coeffs.emplace_back("a_0", fmt(a0));
    RCP<const Basic> series = SymEngine::real_double(a0);
    const double w = 2.0 * kPi / period;
    for (long long k = 1; k <= n_terms; ++k) {
        const double ak = (2.0 / period) * trig_integral(f, k, period, "cos");
        const double bk = (2.0 / period) * trig_integral(f, k, period, "sin");
        r.coeffs.emplace_back("a_" + std::to_string(k), fmt(ak));
        r.coeffs.emplace_back("b_" + std::to_string(k), fmt(bk));
        series = SymEngine::add(
            series, SymEngine::add(
                        SymEngine::mul(SymEngine::real_double(ak),
                                       SymEngine::cos(SymEngine::mul(
                                           SymEngine::real_double(w * k), x))),
                        SymEngine::mul(SymEngine::real_double(bk),
                                       SymEngine::sin(SymEngine::mul(
                                           SymEngine::real_double(w * k), x)))));
    }
    std::ostringstream oss;
    oss << series;
    r.expression = oss.str();
    return r;
}

ComplexCoeffResult complex_fourier_coeff(const std::string& f, long long n,
                                         double period) {
    if (period <= 0) throw std::invalid_argument("周期必须为正");
    ComplexCoeffResult r;
    const double k = 2.0 * kPi * n / period;
    r.value = complex_integral(f, k, period) / period;
    std::ostringstream oss;
    oss << "c_" << n;
    r.expression = oss.str();
    return r;
}

OrthogonalityResult orthogonality_check(long long n, long long m, double period) {
    if (period <= 0) throw std::invalid_argument("周期必须为正");
    OrthogonalityResult r;
    const double w = 2.0 * kPi / period;
    // ∫_0^T e^{i·nωx}·e^{-i·mωx} dx = ∫ e^{i(n-m)ωx} dx = ∫1·e^{-i(m-n)ωx} dx。
    const auto x = SymEngine::symbol("x");
    const auto one = SymEngine::integer(1);
    r.integral = detail::complex_exp_integral(one, x, w * (m - n), 0.0, period, 2000);
    r.orthogonal = std::abs(r.integral) < 1e-9;
    return r;
}

}  // namespace mf::harmonic_analysis
