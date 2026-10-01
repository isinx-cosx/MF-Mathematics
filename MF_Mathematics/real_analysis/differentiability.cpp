// differentiability.cpp — 可微性内核(基于 SymEngine)。

#include "differentiability.h"

#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/derivative.h>
#include <symengine/functions.h>
#include <symengine/parser.h>
#include <symengine/pow.h>
#include <symengine/printers.h>
#include <symengine/sets.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>
#include <symengine/visitor.h>

namespace mf::real_analysis {

namespace {

using SymEngine::RCP;
using SymEngine::Basic;
using SymEngine::Symbol;
using SymEngine::Set;

RCP<const Basic> to_sym_number(double v) {
    const double r = std::round(v);
    if (std::abs(v - r) < 1e-12) return SymEngine::integer(static_cast<long long>(r));
    return SymEngine::real_double(v);
}

RCP<const Basic> diff_order(const RCP<const Basic>& ex,
                            const RCP<const Symbol>& x, long long order) {
    RCP<const Basic> cur = ex;
    for (long long i = 0; i < order; ++i) cur = SymEngine::diff(cur, x);
    return cur;
}

double eval_at(const RCP<const Basic>& ex, const RCP<const Symbol>& x,
               double pt) {
    const auto sub = ex->subs({{x, to_sym_number(pt)}});
    return SymEngine::eval_double(*sub);
}

// 求解 expr=0 并返回区间 (a,b) 内的首个数值根。
bool find_root_in(const RCP<const Basic>& expr, const RCP<const Symbol>& x,
                  double a, double b, double& out) {
    const auto sol = SymEngine::solve(expr, x);
    if (SymEngine::is_a<SymEngine::FiniteSet>(*sol)) {
        const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*sol);
        for (const auto& e : fs.get_args()) {
            double v;
            try {
                v = SymEngine::eval_double(*e);
            } catch (...) {
                continue;
            }
            if (std::isfinite(v) && a < v && v < b) {
                out = v;
                return true;
            }
        }
    }
    return false;
}

}  // namespace

double derivative_definition(const std::string& expr, const std::string& var,
                             double point) {
    const auto x = SymEngine::symbol(var);
    const auto d = SymEngine::diff(SymEngine::parse(expr), x);
    return eval_at(d, x, point);
}

bool is_differentiable(const std::string& expr, const std::string& var,
                       double point) {
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    double f0, left, right;
    try {
        f0 = eval_at(ex, x, point);
        if (!std::isfinite(f0)) return false;
        const double h = 1e-7;
        const double f_left = eval_at(ex, x, point - h);
        const double f_right = eval_at(ex, x, point + h);
        left = (f_left - f0) / -h;
        right = (f_right - f0) / h;
    } catch (...) {
        return false;  // 无法数值求值(如 |x|)→ 不可判定,视为不可导
    }
    return std::isfinite(left) && std::isfinite(right) &&
           std::abs(left - right) < 1e-5;
}

std::string taylor_polynomial(const std::string& expr, const std::string& var,
                              double point, long long n) {
    if (n < 0) throw std::invalid_argument("展开阶数不能为负");
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    const auto a = to_sym_number(point);
    RCP<const Basic> taylor = SymEngine::zero;
    for (long long k = 0; k <= n; ++k) {
        const auto dk = diff_order(ex, x, k);
        const auto coeff = SymEngine::div(dk->subs({{x, a}}),
                                          SymEngine::factorial(static_cast<unsigned long>(k)));
        const auto term = SymEngine::mul(
            coeff, SymEngine::pow(SymEngine::sub(x, a),
                                  SymEngine::integer(k)));
        taylor = SymEngine::add(taylor, term);
    }
    return SymEngine::str(*SymEngine::simplify(taylor));
}

TaylorRemainderResult taylor_remainder(const std::string& expr,
                                       const std::string& var, double point,
                                       long long n, bool has_xi, double xi) {
    if (n < 0) throw std::invalid_argument("展开阶数不能为负");
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    const auto xi_sym = SymEngine::symbol("xi");
    const auto a = to_sym_number(point);
    const auto dn1 = diff_order(ex, x, n + 1);
    const auto formula = SymEngine::simplify(SymEngine::mul(
        SymEngine::div(dn1->subs({{x, xi_sym}}),
                       SymEngine::factorial(static_cast<unsigned long>(n + 1))),
        SymEngine::pow(SymEngine::sub(x, a), SymEngine::integer(n + 1))));

    TaylorRemainderResult r;
    r.formula = SymEngine::str(*formula);
    if (has_xi) {
        r.has_xi = true;
        const auto fv = SymEngine::eval_double(
            *dn1->subs({{x, to_sym_number(xi)}}));
        r.remainder_factor =
            fv / static_cast<double>(SymEngine::factorial(
                                         static_cast<unsigned long>(n + 1))
                                         ->as_int());
    }
    return r;
}

RolleResult rolle_theorem(const std::string& expr, const std::string& var,
                          double a, double b) {
    if (!(a < b)) throw std::invalid_argument("区间须满足 a < b");
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    RolleResult r;
    const double fa = eval_at(ex, x, a);
    const double fb = eval_at(ex, x, b);
    if (!std::isfinite(fa) || !std::isfinite(fb) || std::abs(fa - fb) > 1e-8)
        return r;  // satisfies = false
    r.satisfies = true;
    const auto deriv = SymEngine::diff(ex, x);
    if (!find_root_in(deriv, x, a, b, r.xi)) r.xi = 0.5 * (a + b);
    return r;
}

LagrangeResult lagrange_theorem(const std::string& expr, const std::string& var,
                                double a, double b) {
    if (!(a < b)) throw std::invalid_argument("区间须满足 a < b");
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    LagrangeResult r;
    const double fa = eval_at(ex, x, a);
    const double fb = eval_at(ex, x, b);
    r.secant_slope = (fb - fa) / (b - a);
    const auto deriv = SymEngine::diff(ex, x);
    const auto eq = SymEngine::sub(deriv, to_sym_number(r.secant_slope));
    if (!find_root_in(eq, x, a, b, r.xi)) r.xi = 0.5 * (a + b);
    return r;
}

}  // namespace mf::real_analysis
