#include "inequality.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/parser.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

namespace mf::algebra {

namespace {
using SymEngine::RCP;
using SymEngine::Basic;

// 从不等式字符串提取运算符。
std::string find_op(const std::string& s) {
    if (s.find(">=") != std::string::npos) return ">=";
    if (s.find(">") != std::string::npos) return ">";
    if (s.find("<=") != std::string::npos) return "<=";
    if (s.find("<") != std::string::npos) return "<";
    throw std::invalid_argument("不是有效的不等式");
}

// 提取左侧表达式(去运算符及其后)。
std::string lhs_part(const std::string& s, const std::string& op) {
    const std::size_t pos = s.find(op);
    return s.substr(0, pos);
}

std::string rhs_part(const std::string& s, const std::string& op) {
    const std::size_t pos = s.find(op);
    return s.substr(pos + op.size());
}

// 表达式 ax + b 的系数 a、b(基于变量 x)。
void linear_coeffs(const std::string& e, double& a, double& b) {
    const auto x = SymEngine::symbol("x");
    const auto expr = SymEngine::parse(e);
    const auto sa = SymEngine::coeff(*expr, *x, *SymEngine::integer(1));
    const auto sb = SymEngine::coeff(*expr, *x, *SymEngine::integer(0));
    a = SymEngine::eval_double(*sa);
    b = SymEngine::eval_double(*sb);
}

// 区间字符串(open=true 为开区间)。
std::string interval_str(double lo, double hi, bool lo_open, bool hi_open) {
    std::string lo_s = lo_open ? "(" : "[";
    std::string hi_s = hi_open ? ")" : "]";
    std::string ls = std::isinf(lo) ? "-oo" : std::to_string(lo);
    std::string hs = std::isinf(hi) ? "+oo" : std::to_string(hi);
    return lo_s + ls + ", " + hs + hi_s;
}

struct Interval {
    double lo = -std::numeric_limits<double>::infinity();
    double hi = std::numeric_limits<double>::infinity();
    bool lo_open = true;
    bool hi_open = true;
};

// 线性不等式 → 区间。
Interval linear_solution(const std::string& expr) {
    const std::string op = find_op(expr);
    const std::string lhs = lhs_part(expr, op);
    const std::string rhs = rhs_part(expr, op);
    double a, b;
    linear_coeffs("(" + lhs + ") - (" + rhs + ")", a, b);
    if (std::abs(a) < 1e-15)
        throw std::invalid_argument("未知数系数为零");
    const double root = -b / a;
    const bool gt = (op == ">" || op == ">=");
    const bool strict = (op == ">" || op == "<");
    bool greater = gt;
    if (a < 0) greater = !gt;  // 负系数方向反转。
    Interval iv;
    if (greater) {
        iv.lo = root;
        iv.lo_open = strict;
        iv.hi = std::numeric_limits<double>::infinity();
        iv.hi_open = true;
    } else {
        iv.lo = -std::numeric_limits<double>::infinity();
        iv.lo_open = true;
        iv.hi = root;
        iv.hi_open = strict;
    }
    return iv;
}

// 二次不等式 → 区间(单区间或两个)。
std::string quadratic_solution(const std::string& expr) {
    const std::string op = find_op(expr);
    const std::string lhs = lhs_part(expr, op);
    const std::string rhs = rhs_part(expr, op);
    const std::string comb = "(" + lhs + ") - (" + rhs + ")";
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(comb);
    const RCP<const Basic> sa = SymEngine::coeff(*e, *x, *SymEngine::integer(2));
    const double a = SymEngine::eval_double(*sa);
    const auto roots = SymEngine::solve(e, x);
    std::vector<double> rv;
    if (SymEngine::is_a<SymEngine::FiniteSet>(*roots)) {
        const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*roots);
        for (const auto& rt : fs.get_args()) {
            try {
                const double v = SymEngine::eval_double(*rt);
                if (std::isfinite(v)) rv.push_back(v);
            } catch (...) {
            }
        }
    }
    std::sort(rv.begin(), rv.end());
    rv.erase(std::unique(rv.begin(), rv.end(),
                         [](double p, double q) { return std::abs(p - q) < 1e-8; }),
             rv.end());
    const bool strict = (op == ">" || op == "<");
    const bool gt = (op == ">" || op == ">=");
    const bool upward = a > 0;  // 开口向上。
    // 符号 = a·(x-r1)(x-r2):两侧与 upward 同号,中间与 upward 反号。
    const auto both_sides = [&]() {
        return interval_str(-std::numeric_limits<double>::infinity(), rv[0], true, strict) +
               " ∪ " +
               interval_str(rv.back(), std::numeric_limits<double>::infinity(), strict, true);
    };
    const auto middle = [&]() {
        return interval_str(rv[0], rv.back(), strict, strict);
    };
    // 期望的符号:gt 要求正,非 gt 要求负。
    const bool want_positive = gt;
    // 两侧符号 = upward 的正负;中间 = !upward。
    const bool sides_positive = upward;

    if (rv.size() == 0) {
        // 无实根:符号恒定 = upward(全正或全负)。
        return (want_positive == upward) ? "(-∞, +∞)" : "∅";
    }
    if (rv.size() == 1) {
        // 重根 r:除 r 外符号 = upward;r 处 = 0。
        const double r = rv[0];
        if (upward) {
            if (want_positive) {
                if (strict) return interval_str(-std::numeric_limits<double>::infinity(), r, true, true) +
                                       " ∪ " + interval_str(r, std::numeric_limits<double>::infinity(), true, true);
                return "(-∞, +∞)";
            }
            if (strict) return "∅";
            return "{" + std::to_string(r) + "}";
        } else {
            if (!want_positive) {
                if (strict) return interval_str(-std::numeric_limits<double>::infinity(), r, true, true) +
                                       " ∪ " + interval_str(r, std::numeric_limits<double>::infinity(), true, true);
                return "(-∞, +∞)";
            }
            if (strict) return "∅";
            return "{" + std::to_string(r) + "}";
        }
    }
    // 两个不同根。
    if (want_positive == sides_positive) return both_sides();
    return middle();
}
}  // namespace

std::vector<std::string> inequality_properties(double a, double b, double c) {
    std::vector<std::string> out;
    out.push_back("加 " + std::to_string(c) + ": " + std::to_string(a + c) +
                  " < " + std::to_string(b + c) + "  (方向不变)");
    out.push_back("减 " + std::to_string(c) + ": " + std::to_string(a - c) +
                  " < " + std::to_string(b - c) + "  (方向不变)");
    if (c > 0)
        out.push_back("乘 " + std::to_string(c) + "(正): " + std::to_string(a * c) +
                      " < " + std::to_string(b * c) + "  (方向不变)");
    else if (c < 0)
        out.push_back("乘 " + std::to_string(c) + "(负): " + std::to_string(a * c) +
                      " > " + std::to_string(b * c) + "  (方向反转!)");
    else
        out.push_back("乘 0: 变为等式");
    if (c > 0)
        out.push_back("除以 " + std::to_string(c) + "(正): 方向不变");
    else if (c < 0)
        out.push_back("除以 " + std::to_string(c) + "(负): 方向反转!");
    else
        out.push_back("除以 0: 无意义");
    return out;
}

std::string solve_linear_inequality(const std::string& expr) {
    const Interval iv = linear_solution(expr);
    return interval_str(iv.lo, iv.hi, iv.lo_open, iv.hi_open);
}

std::string solve_inequality_system(const std::vector<std::string>& ineqs) {
    if (ineqs.empty()) return "∅";
    Interval result = linear_solution(ineqs[0]);
    for (std::size_t i = 1; i < ineqs.size(); ++i) {
        const Interval iv = linear_solution(ineqs[i]);
        // 取交集。
        if (iv.lo > result.lo) {
            result.lo = iv.lo;
            result.lo_open = iv.lo_open;
        } else if (iv.lo == result.lo) {
            result.lo_open = result.lo_open || iv.lo_open;
        }
        if (iv.hi < result.hi) {
            result.hi = iv.hi;
            result.hi_open = iv.hi_open;
        } else if (iv.hi == result.hi) {
            result.hi_open = result.hi_open || iv.hi_open;
        }
    }
    if (result.lo > result.hi || (result.lo == result.hi &&
                                  (result.lo_open || result.hi_open)))
        return "∅";
    return interval_str(result.lo, result.hi, result.lo_open, result.hi_open);
}

std::string solve_quadratic_inequality(const std::string& expr) {
    // 线性则用线性解法。
    const std::string op = find_op(expr);
    const std::string lhs = lhs_part(expr, op);
    const std::string rhs = rhs_part(expr, op);
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse("(" + lhs + ") - (" + rhs + ")");
    const RCP<const Basic> sa = SymEngine::coeff(*e, *x, *SymEngine::integer(2));
    double a2 = 0.0;
    try {
        a2 = SymEngine::eval_double(*sa);
    } catch (...) {
    }
    if (std::abs(a2) < 1e-15) return solve_linear_inequality(expr);
    return quadratic_solution(expr);
}

AmGmResult am_gm_inequality(double a, double b) {
    AmGmResult r;
    r.AM = (a + b) / 2.0;
    r.GM = std::sqrt(a * b);
    return r;
}

MaxMinResult max_min_initial(double a, double b) {
    MaxMinResult r;
    r.min = std::min(a, b);
    r.max = std::max(a, b);
    r.GM = std::sqrt(a * b);
    r.AM = (a + b) / 2.0;
    return r;
}

}  // namespace mf::algebra
