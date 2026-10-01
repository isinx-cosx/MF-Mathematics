#include "sequences.h"

#include <cmath>
#include <stdexcept>

#include "../math_input.h"   // 规则里的隐式乘法等归一化(必须在代入数值之后做)

#include <symengine/basic.h>
#include <symengine/eval_double.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

namespace mf::algebra {

namespace {
// 表达式在变量 var = val 处的值。
double eval_expr(const std::string& expr, const std::string& var, double val) {
    const auto vs = SymEngine::symbol(var);
    const auto e = SymEngine::parse(expr);
    const auto sub = e->subs({{vs, SymEngine::real_double(val)}});
    return SymEngine::eval_double(*sub);
}
}  // namespace

double sequence_term(const std::string& formula, long long n) {
    return eval_expr(formula, "n", (double)n);
}

std::vector<double> arithmetic_sequence(double a1, double d, long long n) {
    if (n <= 0) throw std::invalid_argument("项数必须为正");
    std::vector<double> out;
    for (long long i = 0; i < n; ++i) out.push_back(a1 + i * d);
    return out;
}

double arithmetic_sum(double a1, double d, long long n) {
    if (n <= 0) throw std::invalid_argument("项数必须为正");
    return n * (2 * a1 + (n - 1) * d) / 2.0;
}

std::string arithmetic_proof() { return "S_n = n(a₁ + a_n) / 2"; }

std::vector<double> geometric_sequence(double a1, double q, long long n) {
    if (n <= 0) throw std::invalid_argument("项数必须为正");
    std::vector<double> out;
    double term = a1;
    for (long long i = 0; i < n; ++i) {
        out.push_back(term);
        term *= q;
    }
    return out;
}

double geometric_sum(double a1, double q, long long n) {
    if (n <= 0) throw std::invalid_argument("项数必须为正");
    if (std::abs(q - 1.0) < 1e-15) return n * a1;
    return a1 * (1 - std::pow(q, (double)n)) / (1 - q);
}

std::string geometric_proof() {
    return std::string("q ≠ 1: S_n = a₁(1 - q^n)/(1 - q); q = 1: S_n = n·a₁");
}

std::vector<double> recurrence_sequence(const std::vector<double>& initial,
                                        const std::string& rule, long long n) {
    if (initial.empty()) throw std::invalid_argument("初始值不能为空");
    std::vector<double> out = initial;
    for (long long k = (long long)initial.size(); k < n; ++k) {
        std::string r = rule;
        // 替换 a[-1], a[-2], ... 为具体数值。
        //
        // ⚠ 顺序很关键：rule 必须拿**未经归一化**的原始串（分发层用 get_keyword 取，
        //   而不是 get_string）。输入归一化会在标识符与其后的 `[` 之间补隐式乘号，
        //   把 `a[-1]` 改写成 `a*[-1]`，这里的字面量替换就永远失配，最终在 SymEngine
        //   里炸成 "Unknown token: '['"。归一化改到代入数值之后再做 —— 那时串里已经
        //   没有 a[-k] 了，归一化只负责它真正该管的隐式乘法（如 2a[-1] → 2*(1.0)）。
        for (long long back = 1; back <= k; ++back) {
            const std::string token = "a[-" + std::to_string(back) + "]";
            std::size_t pos = 0;
            while ((pos = r.find(token, pos)) != std::string::npos) {
                const double val = out[k - back];
                // 带括号：避免与相邻数字/括号粘成一个数（a[-1]2 之类）。
                const std::string repl = "(" + std::to_string(val) + ")";
                r.replace(pos, token.size(), repl);
                pos += repl.size();
            }
        }
        if (r.find("a[") != std::string::npos)
            throw std::invalid_argument("递推规则引用了超出初始值历史范围的项");
        out.push_back(eval_expr(mf::input::normalize(r).text, "x", 0.0));
    }
    return out;
}

}  // namespace mf::algebra
