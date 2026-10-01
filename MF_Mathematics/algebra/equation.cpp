// equation.cpp — 方程求解内核(基于 SymEngine)。

#include "equation.h"
#include "symbolic_util.h"

#include <algorithm>
#include <charconv>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/derivative.h>
#include <symengine/parser.h>
#include <symengine/pow.h>
#include <symengine/printers.h>
#include <symengine/sets.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>
#include <symengine/visitor.h>

namespace mf::algebra {

namespace {

using SymEngine::RCP;
using SymEngine::Basic;
using SymEngine::Symbol;

// "a = b" → "a - b"(移项为 =0 形式)。无 "=" 时原样返回。
std::string to_rhs_zero(const std::string& expr) {
    const std::string::size_type pos = expr.find('=');
    if (pos == std::string::npos) return expr;
    return "(" + expr.substr(0, pos) + ") - (" + expr.substr(pos + 1) + ")";
}

// double → 符号数:整数值用精确 Integer,避免 0.0 参与运算产生小数。
RCP<const Basic> to_sym_number(double v) {
    const double r = std::round(v);
    if (std::abs(v - r) < 1e-12) return SymEngine::integer(static_cast<long long>(r));
    return SymEngine::real_double(v);
}

// 求解 expr=0,返回集合元素字符串列表。SymEngine 求解失败时返回空。
std::vector<std::string> solve_expr(const std::string& expr, const std::string& var) {
    try {
        const auto x = SymEngine::symbol(var);
        const auto sol = SymEngine::solve(SymEngine::parse(expr), x);
        if (!SymEngine::is_a<SymEngine::FiniteSet>(*sol)) return {};
        const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*sol);
        std::vector<std::string> out;
        for (const auto& e : fs.get_args()) out.push_back(SymEngine::str(*e));
        return out;
    } catch (...) {
        return {};
    }
}

// 数值求根:扫描区间 [lo, hi] 上的符号变化并二分。用于 SymEngine 求解失败的情况。
std::vector<std::string> solve_numeric(const std::string& expr,
                                       const std::string& var,
                                       double lo, double hi) {
    const auto x = SymEngine::symbol(var);
    const auto e = SymEngine::parse(expr);
    const auto f = [&](double t) -> double {
        try {
            const auto sub = e->subs({{x, SymEngine::real_double(t)}});
            const double v = SymEngine::eval_double(*sub);
            return std::isfinite(v) ? v : std::numeric_limits<double>::quiet_NaN();
        } catch (...) {
            return std::numeric_limits<double>::quiet_NaN();
        }
    };
    std::vector<double> roots;
    const int N = 4000;
    double pt = lo;
    double pv = f(lo);
    for (int i = 1; i <= N; ++i) {
        const double t = lo + (hi - lo) * i / N;
        const double v = f(t);
        if (!std::isnan(pv) && !std::isnan(v) && pv * v < 0.0) {
            double a = pt, b = t, fa = pv;
            for (int it = 0; it < 60; ++it) {
                const double m = 0.5 * (a + b);
                const double fm = f(m);
                if (std::isnan(fm)) break;
                if (fa * fm <= 0.0) { b = m; } else { a = m; fa = fm; }
            }
            roots.push_back(0.5 * (a + b));
        }
        pt = t;
        pv = v;
    }
    // 去重:相距小于 1e-6 视为同一根。
    std::sort(roots.begin(), roots.end());
    std::vector<std::string> out;
    double last = std::numeric_limits<double>::lowest();
    char buf[32];
    for (double r : roots) {
        if (r - last < 1e-6) continue;
        last = r;
        const double rounded = std::round(r * 1e10) / 1e10;
        const auto res = std::to_chars(buf, buf + sizeof(buf), rounded,
                                       std::chars_format::general);
        out.push_back(std::string(buf, res.ptr));
    }
    return out;
}

// 提取分子分母:expr = num / den(合并通分)。
void split_num_den(const std::string& expr, std::string& num,
                   std::string& den) {
    const auto e = SymEngine::parse(expr);
    RCP<const Basic> n, d;
    SymEngine::as_numer_denom(e, outArg(n), outArg(d));
    num = SymEngine::str(*n);
    den = SymEngine::str(*d);
}

// 表达式是否恰好等于 a*x²+b*x+c(判断二次式并取系数)。
bool quad_coeffs(const std::string& expr, const std::string& var, double& a,
                 double& b, double& c) {
    const auto x = SymEngine::symbol(var);
    const auto e = SymEngine::parse(expr);
    const auto sa = SymEngine::coeff(*e, *x, *SymEngine::integer(2));
    const auto sb = SymEngine::coeff(*e, *x, *SymEngine::integer(1));
    const auto sc = SymEngine::coeff(*e, *x, *SymEngine::integer(0));
    // 校验表达式确为二次式:e - (a x² + b x + c) == 0
    const auto recon = SymEngine::add(
        {SymEngine::mul(sa, SymEngine::pow(x, SymEngine::integer(2))),
         SymEngine::mul(sb, x), sc});
    // 用 expand 展开差式,避免未消去的括号组误判。
    if (!SymEngine::eq(*SymEngine::expand(SymEngine::sub(e, recon)),
                       *SymEngine::zero))
        return false;
    // 系数含自由符号（如 x²-a 的常数项 -a）时无法数值化：
    // 显式说明并指引符号接口，而不是抛出 SymEngine 内部的
    // "Symbol cannot be evaluated."（调用方无法理解该错误）。
    if (mf::symutil::has_other_symbols(*sa, var) ||
        mf::symutil::has_other_symbols(*sb, var) ||
        mf::symutil::has_other_symbols(*sc, var)) {
        throw std::invalid_argument(
            "方程系数含自由参数（" + mf::symutil::join_names(mf::symutil::symbol_names(*e)) +
            "），判别式为参数表达式：请用 discriminant_sym 获取符号判别式，或指定参数值后再调用");
    }
    a = SymEngine::eval_double(*sa);
    b = SymEngine::eval_double(*sb);
    c = SymEngine::eval_double(*sc);
    return a != 0.0;  // 二次项系数为 0 → 不是二次方程
}

}  // namespace

std::string solve_linear(const std::string& expr, const std::string& var) {
    const auto roots = solve_expr(to_rhs_zero(expr), var);
    if (roots.empty()) return "无解";
    return roots.front();
}

LinearSystemResult solve_linear_system(const std::string& eq1,
                                       const std::string& eq2,
                                       const std::string& var1,
                                       const std::string& var2) {
    const auto x = SymEngine::symbol(var1);
    const auto y = SymEngine::symbol(var2);
    const auto e1 = SymEngine::parse(to_rhs_zero(eq1));
    const auto e2 = SymEngine::parse(to_rhs_zero(eq2));
    // 线性方程组 a1·x + b1·y + c1 = 0, a2·x + b2·y + c2 = 0
    const auto a1 = SymEngine::coeff(*e1, *x, *SymEngine::integer(1));
    const auto b1 = SymEngine::coeff(*e1, *y, *SymEngine::integer(1));
    const auto a2 = SymEngine::coeff(*e2, *x, *SymEngine::integer(1));
    const auto b2 = SymEngine::coeff(*e2, *y, *SymEngine::integer(1));
    const auto c1 = SymEngine::simplify(
        e1->subs({{x, SymEngine::integer(0)}, {y, SymEngine::integer(0)}}));
    const auto c2 = SymEngine::simplify(
        e2->subs({{x, SymEngine::integer(0)}, {y, SymEngine::integer(0)}}));
    // 用 Cramer 规则(符号),避免对矛盾方程组调用 linsolve(会段错误)。
    const auto det = SymEngine::simplify(
        SymEngine::sub(SymEngine::mul(a1, b2), SymEngine::mul(a2, b1)));
    LinearSystemResult r;
    if (SymEngine::eq(*det, *SymEngine::zero)) return r;  // 无解或无穷多解
    const auto x_num = SymEngine::sub(SymEngine::mul(b1, c2),
                                      SymEngine::mul(c1, b2));
    const auto y_num = SymEngine::sub(SymEngine::mul(a2, c1),
                                      SymEngine::mul(a1, c2));
    r.solvable = true;
    r.x = SymEngine::str(*SymEngine::simplify(SymEngine::div(x_num, det)));
    r.y = SymEngine::str(*SymEngine::simplify(SymEngine::div(y_num, det)));
    return r;
}

std::vector<std::string> solve_quadratic(const std::string& expr,
                                         const std::string& var) {
    return solve_expr(to_rhs_zero(expr), var);
}

DiscriminantResult discriminant(const std::string& expr, const std::string& var) {
    double a, b, c;
    if (!quad_coeffs(to_rhs_zero(expr), var, a, b, c))
        throw std::invalid_argument("表达式不是一元二次方程");
    DiscriminantResult r;
    r.delta = b * b - 4.0 * a * c;
    if (r.delta > 0) r.nature = "有两个不等实根";
    else if (r.delta == 0) r.nature = "有两个相等实根(重根)";
    else r.nature = "有一对共轭虚根";
    return r;
}

VietaResult vieta_theorem(const std::string& expr, const std::string& var) {
    double a, b, c;
    if (!quad_coeffs(to_rhs_zero(expr), var, a, b, c))
        throw std::invalid_argument("表达式不是一元二次方程");
    VietaResult r;
    r.sum_of_roots = -b / a;
    r.product_of_roots = c / a;
    r.roots = solve_expr(to_rhs_zero(expr), var);
    return r;
}

FractionalResult solve_fractional(const std::string& expr,
                                  const std::string& var) {
    std::string num, den;
    split_num_den(to_rhs_zero(expr), num, den);
    FractionalResult r;
    const auto cand = solve_expr(num, var);
    for (const auto& s : cand) {
        // 代入分母检验增根。
        bool extraneous = false;
        try {
            const auto sub = SymEngine::simplify(SymEngine::subs(
                SymEngine::parse(den), {{SymEngine::symbol(var),
                                         SymEngine::parse(s)}}));
            if (SymEngine::eq(*sub, *SymEngine::zero)) extraneous = true;
        } catch (...) {
        }
        (extraneous ? r.extraneous : r.valid).push_back(s);
    }
    return r;
}

FractionalResult solve_irrational(const std::string& expr,
                                  const std::string& var) {
    FractionalResult r;
    auto cand = solve_expr(to_rhs_zero(expr), var);
    // SymEngine 求解失败(如 sqrt 方程)→ 数值求根。
    if (cand.empty()) cand = solve_numeric(to_rhs_zero(expr), var, -1e4, 1e4);
    const auto x = SymEngine::symbol(var);
    for (const auto& s : cand) {
        // 代入原方程验证。
        bool valid = false;
        try {
            const auto sub = SymEngine::simplify(SymEngine::subs(
                SymEngine::parse(to_rhs_zero(expr)),
                {{x, SymEngine::parse(s)}}));
            const double v = SymEngine::eval_double(*sub);
            valid = std::isfinite(v) && std::abs(v) < 1e-9;
        } catch (...) {
        }
        (valid ? r.valid : r.extraneous).push_back(s);
    }
    if (r.valid.empty() && r.extraneous.empty()) r.extraneous = cand;
    return r;
}

}  // namespace mf::algebra
