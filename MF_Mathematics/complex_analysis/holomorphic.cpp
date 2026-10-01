#include "holomorphic.h"

#include <cmath>
#include <complex>
#include <limits>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/simplify.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include "ca_internal.h"
#include "conformal.h"

namespace mf::complex_analysis {

namespace {
using mf::complex_analysis::detail::eval_complex;

// 表达式是否恒为 0:符号简化,失败时多点数值验证。
bool expr_is_zero(const std::string& expr) {
    try {
        const auto e = SymEngine::parse(expr);
        if (SymEngine::eq(*SymEngine::simplify(e), *SymEngine::zero)) return true;
        const auto x = SymEngine::symbol("x");
        const auto y = SymEngine::symbol("y");
        for (double xv : {1.0, 2.0, -0.7}) {
            for (double yv : {1.0, 0.3, -1.5}) {
                const auto sub = e->subs({{x, SymEngine::real_double(xv)},
                                          {y, SymEngine::real_double(yv)}});
                const double v = SymEngine::eval_double(*sub);
                if (std::isfinite(v) && std::abs(v) > 1e-8) return false;
            }
        }
        return true;
    } catch (...) {
        return false;
    }
}

std::string diff_xy(const std::string& expr, char var, long long order) {
    const auto s = SymEngine::symbol(std::string(1, var));
    auto e = SymEngine::parse(expr);
    for (long long k = 0; k < order; ++k) e = SymEngine::diff(e, s);
    return SymEngine::str(*e);
}
}  // namespace

bool is_holomorphic(const std::string& func, std::complex<double> z) {
    const double h = 1e-5;
    const auto f = [&](double x, double y) -> std::complex<double> {
        try {
            return eval_complex(func, std::complex<double>(x, y));
        } catch (...) {
            return std::complex<double>(std::numeric_limits<double>::quiet_NaN(),
                                        std::numeric_limits<double>::quiet_NaN());
        }
    };
    const double u_x = (f(z.real() + h, z.imag()).real() - f(z.real() - h, z.imag()).real()) / (2.0 * h);
    const double u_y = (f(z.real(), z.imag() + h).real() - f(z.real(), z.imag() - h).real()) / (2.0 * h);
    const double v_x = (f(z.real() + h, z.imag()).imag() - f(z.real() - h, z.imag()).imag()) / (2.0 * h);
    const double v_y = (f(z.real(), z.imag() + h).imag() - f(z.real(), z.imag() - h).imag()) / (2.0 * h);
    const bool ok = std::isfinite(u_x) && std::isfinite(u_y) &&
                    std::isfinite(v_x) && std::isfinite(v_y);
    return ok && std::abs(u_x - v_y) < 1e-6 && std::abs(u_y + v_x) < 1e-6;
}

CauchyRiemannResult cauchy_riemann(const std::string& u, const std::string& v) {
    CauchyRiemannResult r;
    r.u_x = diff_xy(u, 'x', 1);
    r.u_y = diff_xy(u, 'y', 1);
    r.v_x = diff_xy(v, 'x', 1);
    r.v_y = diff_xy(v, 'y', 1);
    r.cr1 = expr_is_zero("(" + r.u_x + ") - (" + r.v_y + ")");
    r.cr2 = expr_is_zero("(" + r.u_y + ") + (" + r.v_x + ")");
    r.both = r.cr1 && r.cr2;
    return r;
}

bool is_harmonic(const std::string& func) {
    const std::string uxx = diff_xy(func, 'x', 2);
    const std::string uyy = diff_xy(func, 'y', 2);
    return expr_is_zero("(" + uxx + ") + (" + uyy + ")");
}

}  // namespace mf::complex_analysis
