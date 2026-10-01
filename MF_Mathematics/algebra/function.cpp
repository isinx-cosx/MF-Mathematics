// function.cpp — 函数分析内核(domain 基于 SymEngine,其余数值/静态)。

#include "function.h"

#include <cmath>
#include <charconv>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/complex.h>
#include <symengine/constants.h>
#include <symengine/mul.h>
#include <symengine/parser.h>
#include <symengine/pow.h>
#include <symengine/printers.h>
#include <symengine/real_double.h>
#include <symengine/sets.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/symbol.h>
#include <symengine/visitor.h>

namespace mf::algebra {

namespace {

using SymEngine::RCP;
using SymEngine::Basic;
using SymEngine::Symbol;
using SymEngine::Pow;
using SymEngine::Rational;

std::string fmt_num(double v) {
    char buf[32];
    const auto res = std::to_chars(buf, buf + sizeof(buf), v,
                                   std::chars_format::general);
    return std::string(buf, res.ptr);
}

bool is_int_val(double v) {
    return std::abs(v - std::round(v)) < 1e-9;
}

// 求解 expr=0 的根字符串列表。
std::vector<std::string> solve_expr(const RCP<const Basic>& expr,
                                    const RCP<const Symbol>& x) {
    try {
        const auto sol = SymEngine::solve(expr, x);
        if (!SymEngine::is_a<SymEngine::FiniteSet>(*sol)) return {};
        const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*sol);
        std::vector<std::string> out;
        for (const auto& e : fs.get_args()) out.push_back(SymEngine::str(*e));
        return out;
    } catch (...) {
        return {};
    }
}

// radicand ≥ 0 → 友好约束字符串。线性时给 "x ≥ r" / "x ≤ r",否则 "radicand ≥ 0"。
std::string ge0_restriction(const RCP<const Basic>& rad,
                            const std::string& var) {
    try {
        const auto x = SymEngine::symbol(var);
        const auto m = SymEngine::coeff(*rad, *x, *SymEngine::integer(1));
        const auto b = SymEngine::coeff(*rad, *x, *SymEngine::integer(0));
        const auto recon = SymEngine::add({SymEngine::mul(m, x), b});
        if (SymEngine::eq(*SymEngine::expand(SymEngine::sub(rad, recon)),
                          *SymEngine::zero)) {
            const double mv = SymEngine::eval_double(*m);
            if (mv != 0.0) {
                const auto root_expr =
                    SymEngine::simplify(SymEngine::div(SymEngine::neg(b), m));
                const std::string r = SymEngine::str(*root_expr);
                return mv > 0 ? var + " ≥ " + r : var + " ≤ " + r;
            }
        }
    } catch (...) {
    }
    return SymEngine::str(*rad) + " ≥ 0";
}

// 递归收集偶次根式约束(radicand ≥ 0)。
void collect_even_roots(const RCP<const Basic>& e, const std::string& var,
                        std::vector<std::string>& out) {
    if (SymEngine::is_a<Pow>(*e)) {
        const auto args = e->get_args();
        const double ev = SymEngine::eval_double(*args[1]);
        // 指数为分数且 2·指数为整数 → 偶次根(1/2, 3/2, ...)。
        if (!is_int_val(ev) && is_int_val(2.0 * ev)) {
            const std::string rad = SymEngine::str(*args[0]);
            if (rad.find(var) != std::string::npos)
                out.push_back(ge0_restriction(args[0], var));
        }
        collect_even_roots(args[0], var, out);
        collect_even_roots(args[1], var, out);
    } else {
        for (const auto& a : e->get_args()) collect_even_roots(a, var, out);
    }
}

// 递归检查表达式是否为多项式(仅含整数次幂与四则运算)。
bool is_numeric(const RCP<const Basic>& e) {
    return SymEngine::is_a<SymEngine::Integer>(*e) ||
           SymEngine::is_a<SymEngine::Rational>(*e) ||
           SymEngine::is_a<SymEngine::RealDouble>(*e) ||
           SymEngine::is_a<SymEngine::Complex>(*e);
}

bool poly_node(const RCP<const Basic>& e) {
    if (is_numeric(e)) return true;
    if (SymEngine::is_a<SymEngine::Constant>(*e)) return true;  // pi、E 等常数系数
    if (SymEngine::is_a<SymEngine::Symbol>(*e)) return true;
    if (SymEngine::is_a<Pow>(*e)) {
        const auto args = e->get_args();
        if (!SymEngine::is_a<SymEngine::Integer>(*args[1])) return false;
        if (SymEngine::down_cast<const SymEngine::Integer&>(*args[1]).as_int() < 0)
            return false;
        return poly_node(args[0]);
    }
    // 只有 Add / Mul 才允许递归到子节点。
    //
    // ⚠ 旧实现在这里对**任何**节点都递归 (即"子节点全是多项式 → 我也是多项式")，
    // 而叶子节点没有子节点、循环空转后返回 true，于是 sin(x)、log(x)、f(x) 这类
    // 节点一律被当成多项式 —— correspondence_rule 里"对数函数"等分支永远不可达。
    // 多项式由且仅由 数/常数/符号/Add/Mul/非负整数次幂 组成，其余节点一律不是。
    if (SymEngine::is_a<SymEngine::Add>(*e) || SymEngine::is_a<SymEngine::Mul>(*e)) {
        for (const auto& a : e->get_args())
            if (!poly_node(a)) return false;
        return true;
    }
    return false;  // 函数节点(sin/log/exp/…)、Piecewise 等超越对象
}

// 表达式是否为多项式:分母只能是常数,且分子是多项式。
bool is_polynomial(const RCP<const Basic>& e) {
    RCP<const Basic> num, den;
    SymEngine::as_numer_denom(e, outArg(num), outArg(den));
    if (!is_numeric(den)) return false;
    return poly_node(num);
}

}  // namespace

std::string domain(const std::string& expr, const std::string& var) {
    const auto x = SymEngine::symbol(var);
    const auto e = SymEngine::parse(expr);
    std::vector<std::string> restr;

    // 分母零点。
    RCP<const Basic> num, den;
    SymEngine::as_numer_denom(e, outArg(num), outArg(den));
    const std::string den_str = SymEngine::str(*den);
    if (den_str.find(var) != std::string::npos) {
        for (const auto& r : solve_expr(den, x))
            restr.push_back(var + " ≠ " + r);
    }
    // 偶次根式。
    collect_even_roots(e, var, restr);

    if (restr.empty()) return "x ∈ R (全体实数)";
    std::string out;
    for (std::size_t i = 0; i < restr.size(); ++i) {
        if (i) out += ", ";
        out += restr[i];
    }
    return out;
}

std::string range_estimate(const std::string& expr, const std::string& var) {
    const auto x = SymEngine::symbol(var);
    const auto e = SymEngine::parse(expr);
    double mn = std::numeric_limits<double>::infinity();
    double mx = -std::numeric_limits<double>::infinity();
    for (double t = -1000.0; t <= 1000.0; t += 0.5) {
        double v;
        try {
            const auto sub = e->subs({{x, SymEngine::real_double(t)}});
            v = SymEngine::eval_double(*sub);
        } catch (...) {
            continue;
        }
        if (std::isfinite(v)) {
            if (v < mn) mn = v;
            if (v > mx) mx = v;
        }
    }
    if (mn > mx) return "无法精确计算";
    return "[" + fmt_num(mn) + ", " + fmt_num(mx) + "]";
}

std::string correspondence_rule(const std::string& expr) {
    const auto e = SymEngine::parse(expr);
    if (is_polynomial(e)) return "多项式函数";
    RCP<const Basic> num, den;
    SymEngine::as_numer_denom(e, outArg(num), outArg(den));
    // 有理函数 = 分子与分母**都是多项式**，且分母确实带变量。
    // （旧判据只看"分母不是 1"，于是 sin(x)/x、log(x)/x 这类也被叫成有理函数。）
    if (!is_numeric(den) && is_polynomial(num) && is_polynomial(den))
        return "有理函数";
    const std::string s = SymEngine::str(*e);
    if (s.find("sqrt") != std::string::npos) return "含根式函数";
    if (s.find("log") != std::string::npos) return "对数函数";
    if (s.find("exp") != std::string::npos || s.find("E") != std::string::npos)
        return "指数函数";
    return "代数表达式";
}

std::string linear_function(double k, double b) {
    std::string es;
    if (k == 0.0) {
        es = fmt_num(b);
    } else if (k == 1.0 && b == 0.0) {
        es = "x";
    } else if (k == 1.0) {
        es = b >= 0 ? "x + " + fmt_num(b) : "x - " + fmt_num(-b);
    } else if (k == -1.0 && b == 0.0) {
        es = "-x";
    } else if (k == -1.0) {
        es = b > 0 ? "-x + " + fmt_num(b) : "-x - " + fmt_num(-b);
    } else {
        es = fmt_num(k) + "*x" + (b >= 0 ? " + " + fmt_num(b)
                                         : " - " + fmt_num(-b));
    }
    return "y = " + es;
}

SlopeInterceptResult slope_intercept(double k, double b) {
    SlopeInterceptResult r;
    r.slope = k;
    r.intercept = b;
    r.angle_degrees = std::round(std::atan(k) * 180.0 / std::acos(-1.0) * 100.0) /
                      100.0;
    r.x_intercept = k != 0 ? fmt_num(-b / k) : "不存在";
    return r;
}

std::string inverse_proportional(double k) {
    if (k == 0.0) throw std::invalid_argument("k 不能为 0");
    return "y = " + fmt_num(k) + "/x";
}

QuadraticResult quadratic_function(double a, double b, double c) {
    if (a == 0.0) throw std::invalid_argument("a 不能为 0,否则不是二次函数");
    QuadraticResult r;
    r.vertex_x = -b / (2.0 * a);
    r.vertex_y = a * r.vertex_x * r.vertex_x + b * r.vertex_x + c;
    r.axis = "x = " + fmt_num(r.vertex_x);
    r.direction = a > 0 ? "向上" : "向下";
    r.y_intercept = c;
    const double delta = b * b - 4.0 * a * c;
    if (delta > 0) {
        const double sq = std::sqrt(delta);
        r.x_intercepts = "两个交点: (" + fmt_num(-b - sq) + ")/(2*" +
                         fmt_num(a) + ") 和 (" + fmt_num(-b + sq) + ")/(2*" +
                         fmt_num(a) + ")";
    } else if (delta == 0.0) {
        r.x_intercepts = "一个切点: x = " + fmt_num(r.vertex_x);
    } else {
        r.x_intercepts = "无交点(不与x轴相交)";
    }
    return r;
}

ExtremaResult quadratic_extrema(double a, double b, double c) {
    if (a == 0.0) throw std::invalid_argument("a 不能为 0");
    ExtremaResult r;
    r.x = -b / (2.0 * a);
    r.value = a * r.x * r.x + b * r.x + c;
    r.type = a > 0 ? "最小值" : "最大值";
    return r;
}

PowerResult power_function(const std::string& base, double n) {
    PowerResult r;
    bool alpha = !base.empty();
    for (char ch : base)
        if (!((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z'))) alpha = false;
    if (alpha) {
        r.numeric = false;
        if (n == 1.0) {
            r.expr = base;
        } else {
            r.expr = base + "^" + fmt_num(n);
        }
        return r;
    }
    r.numeric = true;
    char* end = nullptr;
    const double v = std::strtod(base.c_str(), &end);
    if (end == base.c_str() || *end != '\0')
        throw std::invalid_argument("幂函数底数必须是数字或变量名");
    r.value = std::pow(v, n);
    return r;
}

double exponential_function(double base, double x) {
    if (base <= 0.0) throw std::invalid_argument("指数函数底数 a 必须大于 0");
    if (base == 1.0) throw std::invalid_argument("底数为 1 时为常数函数 y=1");
    return std::pow(base, x);
}

double log_function(double base, double x) {
    if (base <= 0.0 || base == 1.0)
        throw std::invalid_argument("对数底数 a 必须 > 0 且 ≠ 1");
    if (x <= 0.0) throw std::invalid_argument("真数 x 必须 > 0");
    if (base == std::exp(1.0)) return std::log(x);
    if (base == 10.0) return std::log10(x);
    return std::log(x) / std::log(base);
}

TrigResult sine_cosine_tangent(double angle, const std::string& mode) {
    TrigResult r;
    const double rad = mode == "degrees" ? angle * std::acos(-1.0) / 180.0
                                         : angle;
    r.sin_val = std::sin(rad);
    r.cos_val = std::cos(rad);
    r.tan_val = std::abs(std::cos(rad)) > 1e-12 ? std::tan(rad)
                                                : std::numeric_limits<double>::infinity();
    r.sin_val = std::round(r.sin_val * 1e10) / 1e10;
    r.cos_val = std::round(r.cos_val * 1e10) / 1e10;
    r.tan_val = std::round(r.tan_val * 1e10) / 1e10;
    return r;
}

std::vector<std::string> trig_basic_identities() {
    return {
        "sin²θ + cos²θ = 1",
        "1 + tan²θ = sec²θ",
        "1 + cot²θ = csc²θ",
        "sin(-θ) = -sin θ (奇函数)",
        "cos(-θ) = cos θ (偶函数)",
        "tan(-θ) = -tan θ (奇函数)",
        "sin(π/2 - θ) = cos θ",
        "cos(π/2 - θ) = sin θ",
        "sin(π - θ) = sin θ",
        "cos(π - θ) = -cos θ",
        "sin(π + θ) = -sin θ",
        "cos(π + θ) = -cos θ",
        "sin(2π + θ) = sin θ",
        "cos(2π + θ) = cos θ",
    };
}

PeriodicityResult trig_periodicity(const std::string& func) {
    std::string f = func;
    for (char& ch : f)
        if (ch >= 'A' && ch <= 'Z') ch = static_cast<char>(ch - 'A' + 'a');
    PeriodicityResult r;
    if (f == "sin") {
        r.period = "2π";
        r.frequency = "1/2π";
        r.description = "sin(x + 2π) = sin x";
    } else if (f == "cos") {
        r.period = "2π";
        r.frequency = "1/2π";
        r.description = "cos(x + 2π) = cos x";
    } else if (f == "tan") {
        r.period = "π";
        r.frequency = "1/π";
        r.description = "tan(x + π) = tan x";
    } else {
        throw std::invalid_argument("不支持 '" + func + "',仅支持 sin, cos, tan");
    }
    return r;
}

}  // namespace mf::algebra
