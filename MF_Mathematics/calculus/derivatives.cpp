#include "derivatives.h"

#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <string>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/derivative.h>
#include <symengine/eval_double.h>
#include <symengine/parser.h>
#include <symengine/printers.h>
#include <symengine/integer.h>
#include <symengine/real_double.h>
#include <symengine/simplify.h>
#include <symengine/visitor.h>
#include <symengine/symbol.h>

namespace mf::calculus {

namespace {
using SymEngine::RCP;
using SymEngine::Basic;
using SymEngine::Symbol;

// 代入点用的数：整点用**精确整数**，其余用实数。
//
// 为什么不用一律 real_double：那样会把系数变成浮点，于是
//   d/dx(a*x^2)|x=2  → "4.0*a"（难看，且结果弹窗里会显示 4.0a）
//   d/dx(k/x)|x=2    → "-0.25*k"（本来可以是精确的 -k/4）
// 用整数代入后是 "4*a" 与 "-k/4"，既干净又保持精确。
inline RCP<const Basic> point_at(double point) {
    if (point == std::floor(point) && std::fabs(point) < 9.0e15)
        return SymEngine::integer((long long)point);
    return SymEngine::real_double(point);
}

// 高阶导数:重复 diff order 次
RCP<const Basic> diff_order(const RCP<const Basic>& ex,
                            const RCP<const Symbol>& x, long long order) {
    RCP<const Basic> cur = ex;
    for (long long i = 0; i < order; ++i) cur = SymEngine::diff(cur, x);
    return cur;
}

bool is_zero(const RCP<const Basic>& b) {
    return SymEngine::eq(*SymEngine::simplify(b), *SymEngine::zero);
}
}  // namespace

std::string diff(const std::string& expr, const std::string& var, long long order) {
    if (order < 1) throw std::invalid_argument("求导阶数必须为正整数");
    const auto x = SymEngine::symbol(var);
    const auto d = diff_order(SymEngine::parse(expr), x, order);
    return SymEngine::str(*d);
}

double diff_at(const std::string& expr, const std::string& var, double point,
               long long order) {
    if (order < 1) throw std::invalid_argument("求导阶数必须为正整数");
    const auto x = SymEngine::symbol(var);
    const auto d = diff_order(SymEngine::parse(expr), x, order);
    const auto substituted = d->subs({{x, point_at(point)}});
    // 含参数时不能硬转 double —— 否则只会抛一句"无法数值求值"，
    // 而用户真正想要的是把这个参数留在结果里（见下面的 diff_at_str）。
    if (!SymEngine::free_symbols(*substituted).empty())
        throw std::invalid_argument(
            "表达式含参数，在某点求导得到的是含参数的表达式而不是一个数；"
            "请使用返回符号形式的结果（diff_at 的字符串结果）。");
    return SymEngine::eval_double(*substituted);
}

// 在某点求导，**含参数时给符号结果**。
//
// 为什么需要单独一个入口：原来只有 double diff_at(...)，最后一步固定是 eval_double，
// 于是 f(x)=a*x^2 在 x=2 处求导会直接抛"无法数值求值"——但数学上答案是 4a，
// 本来就可以是符号形式。这个函数把两种情况都表达清楚：
//   · 代入后不再含自由符号 → 给数值文本（%.17g，调用方转 double 无损）
//   · 还含自由符号         → 给化简后的符号表达式文本（如 "4*a"）
// 调用方据此决定返回 JSON 数字还是字符串，于是整条链（宿主 → 结果弹窗）自然就通了。
std::string diff_at_str(const std::string& expr, const std::string& var, double point,
                        long long order) {
    if (order < 1) throw std::invalid_argument("求导阶数必须为正整数");
    const auto x = SymEngine::symbol(var);
    const auto d = diff_order(SymEngine::parse(expr), x, order);
    const auto substituted = d->subs({{x, point_at(point)}});
    // 无自由符号 → 纯数值；否则走下面的符号分支
    if (SymEngine::free_symbols(*substituted).empty()) {
        const double v = SymEngine::eval_double(*substituted);
        if (!std::isfinite(v))
            throw std::invalid_argument("导数在该点处不是有限值");
        char buf[64];
        std::snprintf(buf, sizeof(buf), "%.17g", v);
        return std::string(buf);
    }
    // 先化简再输出：不化简会得到 "2*a*2" 这种没用的形式
    const auto simp = SymEngine::simplify(substituted);
    return SymEngine::str(*simp);
}

std::string implicit_diff(const std::string& eq, const std::string& var,
                          const std::string& dep_var) {
    const auto x = SymEngine::symbol(var);
    const auto y = SymEngine::symbol(dep_var);
    const auto ex = SymEngine::parse(eq);
    const auto Fx = SymEngine::diff(ex, x);
    const auto Fy = SymEngine::diff(ex, y);
    if (is_zero(Fy)) return "无法求解";
    const auto dydx = SymEngine::simplify(SymEngine::div(SymEngine::neg(Fx), Fy));
    return SymEngine::str(*dydx);
}

std::string parametric_diff(const std::string& x_expr, const std::string& y_expr,
                            const std::string& t) {
    const auto ts = SymEngine::symbol(t);
    const auto xe = SymEngine::parse(x_expr);
    const auto ye = SymEngine::parse(y_expr);
    const auto dx = SymEngine::diff(xe, ts);
    const auto dy = SymEngine::diff(ye, ts);
    if (is_zero(dx)) return "无穷大（切线垂直）";
    const auto dydx = SymEngine::simplify(SymEngine::div(dy, dx));
    return SymEngine::str(*dydx);
}

double differential(const std::string& expr, const std::string& var, double point,
                    double dx) {
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    const auto d = SymEngine::diff(ex, x);
    const auto substituted = d->subs({{x, point_at(point)}});
    const double deriv_at = SymEngine::eval_double(*substituted);
    return deriv_at * dx;
}

}  // namespace mf::calculus
