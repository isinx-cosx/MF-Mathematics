#include "limits.h"
#include "../real_analysis/differentiability.h"
#include "parser_lib.h"
#include <string>
#include <vector>
#include <iostream>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <functional>
#include <stdexcept>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/expression.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/symbol.h>
#include <symengine/add.h>
#include <symengine/mul.h>
#include <symengine/pow.h>
#include <symengine/parser.h>
#include <symengine/printers.h>
#include <symengine/subs.h>
#include <symengine/simplify.h>
#include <symengine/visitor.h>
#include <symengine/derivative.h>
#include <symengine/infinity.h>

using SymEngine::Expression;
using SymEngine::RCP;
using SymEngine::Basic;
using SymEngine::Symbol;
using SymEngine::vec_basic;
using SymEngine::symbol;
using SymEngine::add;
using SymEngine::mul;
using SymEngine::pow;
using SymEngine::div;
using SymEngine::diff;
using namespace mf::expr;

std::vector<std::string> split(const std::string& s, char delimiter) {
	std::vector<std::string> tokens;
	size_t start = 0, end = 0;
	while ((end = s.find(delimiter, start)) != std::string::npos) {
		tokens.push_back(s.substr(start, end - start));
		start = end + 1;
	}
	tokens.push_back(s.substr(start));
	return tokens;
}

// 字符串分隔符版本(用于 "**" 这类多字符分隔)。
std::vector<std::string> split(const std::string& s, const std::string& delimiter) {
	std::vector<std::string> tokens;
	size_t start = 0, end = 0;
	while ((end = s.find(delimiter, start)) != std::string::npos) {
		tokens.push_back(s.substr(start, end - start));
		start = end + delimiter.size();
	}
	tokens.push_back(s.substr(start));
	return tokens;
}



// ── 极限求解：形式判定 + 分层策略 ────────────────────────────────────────────
//
// 规则（2026-09 与作者确认后并入；先在沙盒 limits_lab 里 36 条用例全通过再移入，
// 由 tests/test_limits.cpp 长期守住）：
//   L1 形式判定：结构化判定该点的形式，**不用 ε**；拿不准一律判 Indet
//   L2 确定形式：Finite / Zero / ∞(符号确定) → 直接代入就是答案
//   L3 ∞ 兜底  ：x = 1/t（t→0±）；代数式的商/差先在 ∞ 上用"系数比 / 阶比较"解决
//   L4 不定式  ：0/0、∞/∞ → 洛必达（每轮**重新分类** num/den 的形式）
//               1^∞、0^0、∞^0 → exp(g·log f)
//               0·∞ → A/(1/B) 或 B/(1/A)（两种都试）
//               ∞−∞ → 通分 / 共轭有理化 / 阶比较
//   L5 诚实    ：解不出就抛异常并说明"是哪种形式、为什么"，**绝不给看着像结果的错值**
//
// 原实现（作者所写）的症结正是 L1 缺失：它用"分子/分母是否有限"猜形式，于是
//   · dv = +∞ 被当成 dv → 0   → lim 1/x (x→∞) 算成 ∞
//   · nv = dv = ∞ 直接抛"极限发散" → (2x+1)/(x−1) (x→∞) 本该是 2 却报错
// 洛必达本身沿用原思路，只把每轮的判据换成形式判定（见 lhopital_pair）。
namespace {

constexpr int kLimMaxDepth = 12;
constexpr int kLimMaxLhopital = 10;
constexpr int kLimMaxNormalize = 12;
constexpr int kLimMaxSteps = 3000;        // 策略搜索步数上限
constexpr double kLimBudgetMs = 1500.0;   // 墙钟预算：符号运算可能单步就极慢，必须封顶
int g_lim_steps = 0;
std::chrono::steady_clock::time_point g_lim_t0;

const double kLimInf = std::numeric_limits<double>::infinity();

enum class LimKind { Finite, Zero, Inf, Indet };

struct LimForm {
    LimKind k = LimKind::Indet;
    double v = 0.0;      // Finite/Zero 时的值
    int sign = 0;        // Inf 时的符号：±1；0 = 未知（如 1/x 在 0）
    std::string why;     // 形式名
};

LimForm lf_val(double v) {
    LimForm f;
    f.v = v;
    f.k = (v == 0.0) ? LimKind::Zero : LimKind::Finite;
    f.why = f.k == LimKind::Zero ? "0" : "有限";
    return f;
}
LimForm lf_inf(int sign) {
    LimForm f;
    f.k = LimKind::Inf;
    f.sign = sign;
    f.why = sign > 0 ? "+∞" : (sign < 0 ? "−∞" : "∞(符号不明)");
    return f;
}
LimForm lf_indet(const std::string& why) {
    LimForm f;
    f.k = LimKind::Indet;
    f.why = why;
    return f;
}
int lf_sgn(double v) { return v > 0 ? 1 : (v < 0 ? -1 : 0); }
bool lf_is_one(const RCP<const Basic>& e) { return SymEngine::eq(*e, *SymEngine::one); }

bool lim_budget_exhausted() {
    if (g_lim_steps > kLimMaxSteps) return true;
    const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                        std::chrono::steady_clock::now() - g_lim_t0)
                        .count();
    return ms > kLimBudgetMs;
}
void lim_spend(const char* where) {
    ++g_lim_steps;
    if (lim_budget_exhausted())
        throw std::domain_error(std::string("极限求解超出时间/步数预算（在 ") + where +
                                " 之后停止，不猜结果）");
}

/**
 * 方向词表：返回 +1 右极限、−1 左极限、0 双侧。
 * 界面的默认值是 "right"/"left"（见 engineMapExtra.js 的 VAR_SPECS），
 * 而 limits.h 的约定是 "+"/"-"，两套都要认 —— 原实现只判 "-"，
 * 于是 "left" 被当成右极限（这是个一直没人发现的老 bug）。
 */
int lf_side(const std::string& dir) {
    if (dir == "+" || dir == "right" || dir == "右侧" || dir == "右") return 1;
    if (dir == "-" || dir == "left" || dir == "左侧" || dir == "左") return -1;
    return 0;
}
struct LimCtx {
    RCP<const Symbol> x;
    std::string name;
};

bool lf_has_log(const RCP<const Basic>& e) {
    if (SymEngine::is_a<SymEngine::Log>(*e)) return true;
    for (const auto& a : e->get_args())
        if (lf_has_log(a)) return true;
    return false;
}
bool lf_has_half_pow(const RCP<const Basic>& e) {
    if (SymEngine::is_a<SymEngine::Pow>(*e) &&
        SymEngine::eq(*SymEngine::down_cast<const SymEngine::Pow&>(*e).get_exp(),
                      *SymEngine::div(SymEngine::one, SymEngine::integer(2))))
        return true;
    for (const auto& a : e->get_args())
        if (lf_has_half_pow(a)) return true;
    return false;
}
/** 是否含超越结构（exp/log/三角）：代数式的 ∞ 判定不能用在这些上面 */
bool lf_has_transcendental(const RCP<const Basic>& e) {
    if (SymEngine::is_a<SymEngine::Log>(*e) || SymEngine::is_a<SymEngine::Sin>(*e) ||
        SymEngine::is_a<SymEngine::Cos>(*e) || SymEngine::is_a<SymEngine::Tan>(*e) ||
        SymEngine::is_a<SymEngine::Cot>(*e) || SymEngine::is_a<SymEngine::Sec>(*e) ||
        SymEngine::is_a<SymEngine::Csc>(*e))
        return true;
    if (SymEngine::is_a<SymEngine::Pow>(*e) &&
        SymEngine::eq(*SymEngine::down_cast<const SymEngine::Pow&>(*e).get_base(), *SymEngine::E))
        return true;
    for (const auto& a : e->get_args())
        if (lf_has_transcendental(a)) return true;
    return false;
}

/**
 * 是否含"浮点指数"的幂（x^0.5、x^2.0 这类 RealDouble 指数的 Pow）。
 *
 * 用途：SymEngine 的 `as_numer_denom()` 在遇到 RealDouble 指数的 Pow 时会**无限递归**
 * 导致栈溢出（0xC0000005，整个进程死）。实测只要指数是 RealDouble 就崩，与取值无关：
 *   limit("x^2.0", x, 4)  崩      limit("x^2",   x, 4) → 16 ✓
 *   limit("x^0.5", x, 4)  崩      limit("x^0.5"→"x^(1/2)") → 2 ✓
 *   limit("x*2.0", x, 4)  正常（浮点在别处没事）
 * 所以分类前先探测：含浮点幂就**跳过** as_numer_denom 那一步，
 * 交给下面的结构分类（Pow 分支自己会算 base^expo，结果正确）。
 */
bool lf_has_float_pow(const RCP<const Basic>& e) {
    if (SymEngine::is_a<SymEngine::Pow>(*e)) {
        const auto& p = SymEngine::down_cast<const SymEngine::Pow&>(*e);
        if (SymEngine::is_a<SymEngine::RealDouble>(*p.get_exp())) return true;
    }
    for (const auto& a : e->get_args())
        if (lf_has_float_pow(a)) return true;
    return false;
}

/**
 * 把"整齐"的浮点指数换成精确有理数：2.0 → 2、0.5 → 1/2、0.25 → 1/4。
 *
 * 用户写 x^0.5 与 x^(1/2) 是一个意思，但 SymEngine 把前者存成 RealDouble、
 * 后者存成 Rational，两条路径的行为天差地别（前者会触发上面的崩溃路径，
 * 而且符号判定也拿不到精确指数）。入口处统一成有理数，语义不变、路径一致。
 * 只有**确实能用小分母逼近**的浮点才转换（|v−p/q| ≤ 1e-12），
 * 像 0.1234567 这种转不干净的保持原样——由 lf_has_float_pow 那条安全网兜住。
 */
RCP<const Basic> lf_exactify_pows(const RCP<const Basic>& e, int depth = 0) {
    using namespace SymEngine;
    if (e.is_null() || depth > 64) return e;
    if (is_a<Pow>(*e)) {
        const auto& p = down_cast<const Pow&>(*e);
        const RCP<const Basic> base = lf_exactify_pows(p.get_base(), depth + 1);
        RCP<const Basic> expo = p.get_exp();
        if (is_a<RealDouble>(*expo)) {
            const double v = down_cast<const RealDouble&>(*expo).as_double();
            const double r = std::round(v);
            if (std::isfinite(v) && std::abs(v - r) < 1e-12 && std::abs(r) < 1e15) {
                expo = integer(static_cast<long long>(r));
            } else if (std::isfinite(v)) {
                // 连分数逼近：找分母 ≤ 1e6 且误差 ≤ 1e-12 的有理数
                long long p0 = 0, q0 = 1, p1 = 1, q1 = 0;
                double x = v;
                for (int i = 0; i < 40; ++i) {
                    const double a = std::floor(x);
                    if (!std::isfinite(a) || std::abs(a) > 1e15) break;
                    const long long ai = static_cast<long long>(a);
                    const long long p2 = ai * p1 + p0, q2 = ai * q1 + q0;
                    if (q2 > 1000000) break;
                    p0 = p1; q0 = q1; p1 = p2; q1 = q2;
                    if (q1 != 0 && std::abs(v - static_cast<double>(p1) / q1) < 1e-12) {
                        expo = rational(p1, q1);
                        break;
                    }
                    const double frac = x - a;
                    if (frac < 1e-15) break;
                    x = 1.0 / frac;
                }
            }
        }
        if (base.get() != p.get_base().get() || expo.get() != p.get_exp().get())
            return pow(base, expo);
        return e;
    }
    if (e->get_args().empty()) return e;
    map_basic_basic repl;
    bool changed = false;
    for (const auto& a : e->get_args()) {
        const RCP<const Basic> na = lf_exactify_pows(a, depth + 1);
        if (na.get() != a.get()) {
            repl[a] = na;
            changed = true;
        }
    }
    if (!changed) return e;
    try {
        return e->xreplace(repl);
    } catch (const std::exception&) {
        return e;
    }
}


/**
 * 更细的"阶"（∞ 处判主导）：x^p → p，log → 0，exp → 1e6（哨兵），
 * 乘 → 相加，和 → 取最大。比"对数/幂/指数"三档细，能分清 x³ 与 x。
 */
double lf_order(const RCP<const Basic>& e, const std::string& var) {
    if (SymEngine::is_a<SymEngine::Symbol>(*e))
        return SymEngine::down_cast<const SymEngine::Symbol&>(*e).get_name() == var ? 1.0 : 0.0;
    if (SymEngine::is_a_Number(*e) || SymEngine::is_a<SymEngine::Constant>(*e)) return 0.0;
    if (SymEngine::is_a<SymEngine::Log>(*e)) return 0.0;
    if (SymEngine::is_a<SymEngine::Pow>(*e)) {
        const auto& p = SymEngine::down_cast<const SymEngine::Pow&>(*e);
        if (SymEngine::eq(*p.get_base(), *SymEngine::E)) return 1e6;
        const double inner = lf_order(p.get_base(), var);
        if (SymEngine::is_a_Number(*p.get_exp())) {
            try {
                return inner * SymEngine::eval_double(*p.get_exp());
            } catch (...) {
                return inner;
            }
        }
        return inner;
    }
    if (SymEngine::is_a<SymEngine::Mul>(*e)) {
        double s = 0.0;
        for (const auto& a : e->get_args()) s += lf_order(a, var);
        return s;
    }
    if (SymEngine::is_a<SymEngine::Add>(*e)) {
        double m = 0.0;
        for (const auto& a : e->get_args()) m = (std::max)(m, lf_order(a, var));
        return m;
    }
    return 0.0;
}

/** 整体乘 t^k，并把 t^k 塞进根号里：sqrt(A)·t^k = sqrt(A·t^{2k}) */
RCP<const Basic> lf_scale_t(const RCP<const Basic>& e, int k, const RCP<const Basic>& t) {
    if (k == 0) return e;
    const auto tk = SymEngine::pow(t, SymEngine::integer(k));
    if (SymEngine::is_a<SymEngine::Pow>(*e)) {
        const auto& p = SymEngine::down_cast<const SymEngine::Pow&>(*e);
        if (SymEngine::eq(*p.get_exp(), *SymEngine::div(SymEngine::one, SymEngine::integer(2))))
            return SymEngine::pow(lf_scale_t(p.get_base(), 2 * k, t),
                                  SymEngine::div(SymEngine::one, SymEngine::integer(2)));
        return SymEngine::expand(SymEngine::mul(e, tk));
    }
    if (SymEngine::is_a<SymEngine::Mul>(*e)) {
        // 整体只乘一次 t^k：交给**第一个含根号的因子**，否则每个因子都乘一遍会放大 k·因子数次
        const auto args = e->get_args();
        std::size_t target = args.size();
        for (std::size_t i = 0; i < args.size(); ++i)
            if (lf_has_half_pow(args[i])) { target = i; break; }
        if (target == args.size()) return SymEngine::expand(SymEngine::mul(e, tk));
        vec_basic fs;
        for (std::size_t i = 0; i < args.size(); ++i)
            fs.push_back(lf_scale_t(args[i], i == target ? k : 0, t));
        return SymEngine::expand(SymEngine::mul(fs));
    }
    if (SymEngine::is_a<SymEngine::Add>(*e)) {   // 和要逐项分配：(a+b)·t = a·t + b·t
        vec_basic ts;
        for (const auto& term : e->get_args()) ts.push_back(lf_scale_t(term, k, t));
        return SymEngine::expand(SymEngine::add(ts));
    }
    return SymEngine::expand(SymEngine::mul(e, tk));
}

LimForm lf_classify(const RCP<const Basic>& e, const std::string& var, double point);

/** 商的形式合成规则 */
LimForm lf_combine_quotient(const LimForm& n, const LimForm& d) {
    if (n.k == LimKind::Indet) return n;
    if (d.k == LimKind::Indet) return d;
    const bool n_fin = n.k != LimKind::Inf, d_fin = d.k != LimKind::Inf;
    if (n_fin && d_fin) {
        if (d.v != 0.0) return lf_val(n.v / d.v);
        if (n.v == 0.0) return lf_indet("0/0");
        return lf_inf(0);                     // k/0：符号未知，交给单侧探针
    }
    if (n_fin && !d_fin) return lf_val(0.0);  // 有限/∞ → 0
    if (!n_fin && d_fin) {
        if (d.v == 0.0) return lf_inf(0);
        return lf_inf(n.sign * lf_sgn(d.v));  // ∞/有限 → ±∞
    }
    return lf_indet("∞/∞");
}

/**
 * 代数式在 ∞ 处的商：同阶 → **系数比**（确定形式，不是 ∞/∞）。
 * 令 x=1/t，同乘 t^k 消掉负幂，再看 t→0 是否有限：
 *   (x+1)/x → (1+t)/1 → 1；  (x³+1)/(2x³−x) → (1+t³)/(2−t²) → 1/2
 */
bool lf_algebraic_ratio_at_inf(const RCP<const Basic>& num, const RCP<const Basic>& den,
                               const std::string& var, double& out) {
    if (lf_has_transcendental(num) || lf_has_transcendental(den)) return false;
    const auto t = SymEngine::symbol("_mf_lim_t2");
    RCP<const Basic> ns, ds;
    try {
        ns = num->subs({{SymEngine::symbol(var), SymEngine::div(SymEngine::one, t)}});
        ds = den->subs({{SymEngine::symbol(var), SymEngine::div(SymEngine::one, t)}});
    } catch (...) {
        return false;
    }
    for (int k = 1; k <= kLimMaxNormalize; ++k) {
        if (lim_budget_exhausted()) return false;
        RCP<const Basic> N, D;
        try {
            N = lf_scale_t(ns, k, t);
            D = lf_scale_t(ds, k, t);
        } catch (...) {
            return false;
        }
        const LimForm cn = lf_classify(N, "_mf_lim_t2", 0.0);
        const LimForm cd = lf_classify(D, "_mf_lim_t2", 0.0);
        const bool n_ok = cn.k == LimKind::Finite || cn.k == LimKind::Zero;
        const bool d_ok = cd.k == LimKind::Finite || cd.k == LimKind::Zero;
        if (n_ok && d_ok && cd.v != 0.0) {
            out = cn.v / cd.v;
            return true;
        }
    }
    return false;
}

LimForm lf_classify_pow(const RCP<const Basic>& base, const RCP<const Basic>& expo,
                        const std::string& var, double point) {
    const LimForm b = lf_classify(base, var, point);
    const LimForm g = lf_classify(expo, var, point);
    if (b.k == LimKind::Indet) return b;
    if (g.k == LimKind::Indet) return g;

    const bool b_inf = b.k == LimKind::Inf, b_zero = b.k == LimKind::Zero;
    const bool g_inf = g.k == LimKind::Inf;

    if (!b_inf && !b_zero && !g_inf) {                        // 有限^有限
        const double v = std::pow(b.v, g.v);
        if (std::isnan(v)) return lf_indet("有限^有限 无定义");
        if (std::isinf(v)) return lf_inf(v > 0 ? 1 : -1);
        return lf_val(v);
    }
    if (g_inf) {
        if (b_zero) return g.sign > 0 ? lf_val(0.0) : lf_inf(1);   // 0^∞=0、0^(−∞)=∞
        if (b_inf) return lf_indet("∞^∞");
        if (b.v == 1.0) return lf_indet("1^∞");                    // 按**值**判，不看写法
        if (b.v <= 0.0) return lf_indet("非正底数的无穷次幂");
        if (g.sign == 0) return lf_indet("指数→∞ 但符号不明");
        return ((b.v > 1.0) == (g.sign > 0)) ? lf_inf(1) : lf_val(0.0);
    }
    if (b_zero) {                                            // 0^有限
        if (g.k == LimKind::Zero) return lf_indet("0^0");
        if (g.v > 0) return lf_val(0.0);
        if (SymEngine::is_a<SymEngine::Integer>(*expo) &&
            SymEngine::down_cast<const SymEngine::Integer&>(*expo).as_int() % 2 == 0)
            return lf_inf(1);                                // 负偶次幂两侧同号
        return lf_inf(0);                                    // 负奇次幂符号随侧别
    }
    if (g.k == LimKind::Zero) return lf_indet("∞^0");         // ∞^有限
    if (SymEngine::is_a<SymEngine::Integer>(*expo)) {         // 整数次幂：符号可定
        const long iv = SymEngine::down_cast<const SymEngine::Integer&>(*expo).as_int();
        if (iv % 2 == 0) return lf_inf(1);                    // (−∞)² = +∞
        return lf_inf(b.sign > 0 ? 1 : (b.sign < 0 ? -1 : 0));
    }
    if (b.sign < 0) return lf_indet("(−∞)^有限");
    return g.v > 0 ? lf_inf(b.sign > 0 ? 1 : 0) : lf_val(0.0);
}

LimForm lf_classify(const RCP<const Basic>& e, const std::string& var, double point) {
    // ⓪ 先看是不是"商"：x^{-1} 是分母，不能按乘法的 0·∞ 规则处理
    //    （as_numer_denom 认得 x + 1/x 这类，比手工拆因子可靠）
    //
    // ⚠ 但含**浮点指数**的幂必须跳过这一步：SymEngine 的 as_numer_denom() 对
    //   Pow(x, RealDouble) 会无限递归 → 栈溢出（0xC0000005）直接杀进程。
    //   实测 limit("x^2.0"/"x^0.5"/"x^0.1234567") 全部崩溃，而 x^2、x^(1/2) 正常。
    //   跳过之后交给下面的结构分类：Pow 分支自己会算 base^expo，结果是对的。
    if (!lf_has_float_pow(e)) {
        RCP<const Basic> n, d;
        SymEngine::as_numer_denom(e, SymEngine::outArg(n), SymEngine::outArg(d));
        if (!lf_is_one(d)) {
            const LimForm cn = lf_classify(n, var, point);
            const LimForm cd = lf_classify(d, var, point);
            if (cn.k == LimKind::Inf && cd.k == LimKind::Inf && std::isinf(point)) {
                double r = 0.0;
                if (lf_algebraic_ratio_at_inf(n, d, var, r)) return lf_val(r);   // 同阶 → 系数比
            }
            return lf_combine_quotient(cn, cd);
        }
    }
    if (SymEngine::is_a<SymEngine::Infty>(*e)) {
        const auto& i = SymEngine::down_cast<const SymEngine::Infty&>(*e);
        return lf_inf(i.is_positive() ? 1 : (i.is_negative() ? -1 : 0));
    }
    if (SymEngine::is_a<SymEngine::Symbol>(*e)) {
        const auto& s = SymEngine::down_cast<const SymEngine::Symbol&>(*e);
        if (s.get_name() != var) return lf_indet("自由参数 " + s.get_name());
        return std::isinf(point) ? lf_inf(point > 0 ? 1 : -1) : lf_val(point);
    }
    if (SymEngine::is_a_Number(*e) || SymEngine::is_a<SymEngine::Constant>(*e)) {
        try {
            return lf_val(SymEngine::eval_double(*e));
        } catch (...) {
            return lf_indet("常量无法求值");
        }
    }
    if (SymEngine::is_a<SymEngine::Add>(*e)) {
        double sum = 0.0;
        std::vector<std::pair<RCP<const Basic>, LimForm>> infs;
        for (const auto& t : e->get_args()) {
            const LimForm c = lf_classify(t, var, point);
            if (c.k == LimKind::Indet) return c;
            if (c.k == LimKind::Inf) infs.push_back({t, c});
            else sum += c.v;
        }
        if (infs.empty()) return lf_val(sum);

        bool mixed = false;
        for (const auto& p : infs)
            if (p.second.sign != 0 && p.second.sign != infs[0].second.sign) mixed = true;
        if (!mixed) {
            int s = infs[0].second.sign;
            for (const auto& p : infs)
                if (p.second.sign == 0) s = 0;
            return lf_inf(s);
        }
        // 符号不一致：x³−x 在 ∞ 是**确定的** +∞（阶主导）；只有同阶（x²−x）才是 ∞−∞。
        // 阶只在 ∞ 点有意义。
        if (std::isinf(point)) {
            double omax = -1e300, omin = 1e300;
            for (const auto& p : infs) {
                const double o = lf_order(p.first, var);
                omax = (std::max)(omax, o);
                omin = (std::min)(omin, o);
            }
            if (omax > omin + 1e-9) {
                int s = 0;
                for (const auto& p : infs)
                    if (lf_order(p.first, var) > omax - 1e-9) s = p.second.sign;
                if (s != 0) return lf_inf(s);
            }
        }
        return lf_indet("∞−∞");
    }
    if (SymEngine::is_a<SymEngine::Mul>(*e)) {
        double prod = 1.0;
        int sign = 1;
        bool has_inf = false, has_zero = false;
        for (const auto& f : e->get_args()) {
            const LimForm c = lf_classify(f, var, point);
            if (c.k == LimKind::Indet) return c;
            if (c.k == LimKind::Inf) {
                has_inf = true;
                sign *= c.sign;
            } else if (c.k == LimKind::Zero) {
                has_zero = true;
            } else {
                prod *= c.v;
                sign *= lf_sgn(c.v);
            }
        }
        if (has_inf && has_zero) return lf_indet("0·∞");
        if (has_inf) return lf_inf(sign);
        if (has_zero) return lf_val(0.0);          // 有 0 因子 → 积为 0
        return lf_val(prod);
    }
    if (SymEngine::is_a<SymEngine::Pow>(*e)) {
        const auto& p = SymEngine::down_cast<const SymEngine::Pow&>(*e);
        return lf_classify_pow(p.get_base(), p.get_exp(), var, point);
    }
    if (SymEngine::is_a<SymEngine::Log>(*e)) {
        const LimForm a = lf_classify(e->get_args()[0], var, point);
        if (a.k == LimKind::Zero) return lf_inf(-1);              // ln(0⁺) → −∞
        if (a.k == LimKind::Indet) return a;
        if (a.k == LimKind::Inf) return a.sign > 0 ? lf_inf(1) : lf_indet("ln(−∞)");
        return a.v > 0 ? lf_val(std::log(a.v)) : lf_indet("ln(非正)");
    }
    const auto fargs = e->get_args();
    if (fargs.size() == 1) {
        const LimForm a = lf_classify(fargs[0], var, point);
        if (a.k == LimKind::Indet) return a;
        // ── 分段函数 sign / abs ────────────────────────────────────────────
        // 它们在**零点处不可导且表达式分段**，不能靠"代入求值"定极限：
        //   sign(0) 在 SymEngine 里是 0，于是 limit(sign(x), x→0⁺) 曾错答 0
        //   （真值 +1）；abs(x)/x 在 0 处更是直接落进"未识别的结构"。
        // 所以这里单独判：自变量趋于 0 时标为"分段不定式"，交给 limit_solve
        // 用单侧数值兜底（见 lf_piecewise_limit）。
        const bool is_abs = SymEngine::is_a<SymEngine::Abs>(*e);
        const bool is_sign = SymEngine::is_a<SymEngine::Sign>(*e);
        if (is_abs || is_sign) {
            if (a.k == LimKind::Inf) {
                if (is_abs) return lf_inf(1);
                return a.sign != 0 ? lf_val(static_cast<double>(a.sign))
                                   : lf_indet("sign(∞) 符号不明");
            }
            if (a.v != 0.0)
                return is_abs ? lf_val(std::abs(a.v))
                              : lf_val(static_cast<double>(lf_sgn(a.v)));
            return lf_indet(is_sign ? "sign 在零点（分段）" : "abs 在零点（分段）");
        }
        const bool trig = SymEngine::is_a<SymEngine::Sin>(*e) || SymEngine::is_a<SymEngine::Cos>(*e) ||
                          SymEngine::is_a<SymEngine::Tan>(*e) || SymEngine::is_a<SymEngine::Cot>(*e) ||
                          SymEngine::is_a<SymEngine::Sec>(*e) || SymEngine::is_a<SymEngine::Csc>(*e);
        // 有界超越函数在 ±∞ 处有**确定的有限极限** —— 这是教科书事实，不是"猜"：
        //   atan(±∞) = ±π/2 ; tanh(±∞) = ±1 ; erf(±∞) = ±1
        // 原先这几类一律落到下面的「函数在 ∞」不定式，而 lf_reduce_inf 把 x 换成 1/t
        // 之后又回到同一句分类，于是连 lim atan(x) 这种最基本的都解不出 ——
        // 直接后果是 y=atan(x) 这类函数的**水平渐近线全丢**（tests 里也有对应断言）。
        if (a.k == LimKind::Inf && a.sign != 0) {
            const double sg = static_cast<double>(a.sign);
            if (SymEngine::is_a<SymEngine::ATan>(*e)) return lf_val(sg * std::acos(-1.0) / 2.0);
            if (SymEngine::is_a<SymEngine::Tanh>(*e)) return lf_val(sg);
            if (SymEngine::is_a<SymEngine::Erf>(*e)) return lf_val(sg);
        }
        if (a.k == LimKind::Inf) return trig ? lf_indet("三角函数在 ∞（振荡）") : lf_indet("函数在 ∞");
        try {
            const auto x = SymEngine::symbol(var);
            // 三角极点：tan/sec 看 cos 是否为零（π/2），cot/csc 看 sin 是否为零
            if (SymEngine::is_a<SymEngine::Tan>(*e) || SymEngine::is_a<SymEngine::Sec>(*e)) {
                const double cv = SymEngine::eval_double(
                    *SymEngine::cos(fargs[0])->subs({{x, SymEngine::real_double(point)}}));
                if (std::fabs(cv) < 1e-12) return lf_indet("三角函数的极点");
            }
            if (SymEngine::is_a<SymEngine::Cot>(*e) || SymEngine::is_a<SymEngine::Csc>(*e)) {
                const double sv = SymEngine::eval_double(
                    *SymEngine::sin(fargs[0])->subs({{x, SymEngine::real_double(point)}}));
                if (std::fabs(sv) < 1e-12) return lf_indet("三角函数的极点");
            }
            const double v = SymEngine::eval_double(*e->subs({{x, SymEngine::real_double(point)}}));
            if (std::isnan(v)) return lf_indet("函数值未定义");
            if (std::isinf(v)) return lf_inf(v > 0 ? 1 : -1);
            return lf_val(v);
        } catch (...) {
            return lf_indet("函数值无法求值");
        }
    }
    return lf_indet("未识别的结构");
}

double limit_solve(const RCP<const Basic>& e, const LimCtx& ctx, double point,
                   const std::string& dir, int depth);

/** 在 point 的单侧附近取符号（数值探针；只在必须定号时用） */
int lf_sign_probe(const RCP<const Basic>& e, const LimCtx& ctx, double point, int side) {
    if (!std::isfinite(point)) {
        for (double h : {1e-3, 1e-4, 1e-5, 1e-6}) {
            const double at = (point > 0 ? 1.0 : -1.0) / h;
            try {
                const double v = SymEngine::eval_double(*e->subs({{ctx.x, SymEngine::real_double(at)}}));
                if (std::isfinite(v) && v != 0.0) return v > 0 ? 1 : -1;
            } catch (...) { /* 该点求不出值，换下一个步长 */
            }
        }
        return 0;
    }
    for (double rel : {1e-6, 1e-7, 1e-8, 1e-5, 1e-4}) {
        const double at = point + side * rel * (1.0 + std::fabs(point));
        try {
            const double v = SymEngine::eval_double(*e->subs({{ctx.x, SymEngine::real_double(at)}}));
            if (std::isfinite(v) && v != 0.0) return v > 0 ? 1 : -1;
        } catch (...) { /* 同上 */
        }
    }
    return 0;
}

/** 分母→0、分子非零：按单侧符号给 ±∞；两侧不等时如实说"不存在" */
double lf_diverge_by_sign(const RCP<const Basic>& num, const RCP<const Basic>& den,
                          const LimCtx& ctx, double point, const std::string& dir,
                          const std::string& form) {
    int nsign = 0;
    const LimForm cn = lf_classify(num, ctx.name, point);
    if (cn.k == LimKind::Inf) nsign = cn.sign;
    else if (cn.k == LimKind::Finite) nsign = lf_sgn(cn.v);
    if (nsign == 0)
        throw std::domain_error(form + " 型：分子也是 0（0/0）或符号不明，无法定发散方向");

    const int side = lf_side(dir);
    if (side != 0) {
        const int ds = lf_sign_probe(den, ctx, point, side);
        if (ds == 0) throw std::domain_error(form + " 型：分母→0 但符号无法判定");
        return nsign * ds * kLimInf;
    }
    const int dl = lf_sign_probe(den, ctx, point, -1);
    const int dr = lf_sign_probe(den, ctx, point, +1);
    if (dl != 0 && dr != 0 && dl != dr)
        throw std::domain_error(std::string("极限不存在：左 ") + (nsign * dl > 0 ? "+∞" : "−∞") +
                                "、右 " + (nsign * dr > 0 ? "+∞" : "−∞"));
    const int ds = dr != 0 ? dr : dl;
    if (ds == 0) throw std::domain_error(form + " 型：分母→0 但符号无法判定");
    return nsign * ds * kLimInf;
}

/** 洛必达：直接吃 (分子, 分母) 这一对，每轮**重新分类**（不靠 |dv|>1e-12 判零） */
double lf_lhopital_pair(const RCP<const Basic>& num0, const RCP<const Basic>& den0,
                        const LimCtx& ctx, double point, const std::string& dir, int depth) {
    RCP<const Basic> num = num0, den = den0;
    std::vector<std::string> seen;   // 循环检测：导数振荡时别白跑满轮数
    for (int i = 0; i < kLimMaxLhopital; ++i) {
        lim_spend("洛必达");
        const LimForm cn = lf_classify(num, ctx.name, point);
        const LimForm cd = lf_classify(den, ctx.name, point);
        const std::string form = cn.why + "/" + cd.why;
        const std::string key = SymEngine::str(*num) + " | " + SymEngine::str(*den);
        if (std::find(seen.begin(), seen.end(), key) != seen.end())
            throw std::domain_error("洛必达出现重复的分子分母对，判定为不收敛（不猜结果）");
        seen.push_back(key);

        if (cn.k == LimKind::Finite && cd.k == LimKind::Finite && cd.v != 0.0) return cn.v / cd.v;
        if (cn.k == LimKind::Zero && cd.k == LimKind::Finite && cd.v != 0.0) return 0.0;
        if (cn.k == LimKind::Finite && cd.k == LimKind::Inf) return 0.0;   // 有限/∞ → 0
        if (cn.k == LimKind::Inf && cd.k == LimKind::Finite && cd.v != 0.0)
            return cn.sign * lf_sgn(cd.v) * kLimInf;

        const bool both_zero = cn.k == LimKind::Zero && cd.k == LimKind::Zero;
        const bool both_inf = cn.k == LimKind::Inf && cd.k == LimKind::Inf;

        if (cn.k == LimKind::Indet || cd.k == LimKind::Indet) {
            // 分子/分母本身是不定式：各自求极限后再合成
            std::string why_n, why_d;
            double rn = 0.0, rd = 0.0;
            bool ok_n = true, ok_d = true;
            try { rn = limit_solve(num, ctx, point, dir, depth + 1); } catch (const std::exception& e) { ok_n = false; why_n = e.what(); }
            try { rd = limit_solve(den, ctx, point, dir, depth + 1); } catch (const std::exception& e) { ok_d = false; why_d = e.what(); }
            if (!ok_n || !ok_d)
                throw std::domain_error("分子/分母单独求极限也没成（" + why_n + " / " + why_d + "）");
            if (std::isinf(rd)) return 0.0;
            if (rd != 0.0) {
                if (std::isinf(rn)) return (rn > 0 ? 1 : -1) * (rd > 0 ? 1 : -1) * kLimInf;
                return rn / rd;
            }
            return lf_diverge_by_sign(num, den, ctx, point, dir, form);
        }
        if (!both_zero && !both_inf) return lf_diverge_by_sign(num, den, ctx, point, dir, form);

        const auto n2 = SymEngine::diff(num, ctx.x);
        const auto d2 = SymEngine::diff(den, ctx.x);
        if (SymEngine::str(*n2) == SymEngine::str(*num) &&
            SymEngine::str(*d2) == SymEngine::str(*den))
            throw std::domain_error("洛必达无进展（求导后分子分母不变）");
        num = n2;
        den = d2;
    }
    throw std::domain_error("洛必达超过 " + std::to_string(kLimMaxLhopital) + " 轮仍未定出");
}

/** 幂型不定式：f^g = exp(g·log f)，指数递归回 L1 */
double lf_power_exp_log(const RCP<const Basic>& e, const LimCtx& ctx, double point,
                        const std::string& dir, int depth) {
    const auto& p = SymEngine::down_cast<const SymEngine::Pow&>(*e);
    const auto x = SymEngine::mul(p.get_exp(), SymEngine::log(p.get_base()));
    const double l = limit_solve(x, ctx, point, dir, depth + 1);
    return std::exp(l);   // exp(−∞)=0、exp(+∞)=+∞ 都对
}

/** 0·∞：两种恒等改写都试；"幂 × 对数"这类阶关系确定的直接给 0 */
double lf_product_rewrite(const RCP<const Basic>& e, const LimCtx& ctx, double point,
                          const std::string& dir, int depth) {
    RCP<const Basic> A, B;   // A → 0，B → ∞
    for (const auto& f : e->get_args()) {
        const LimForm c = lf_classify(f, ctx.name, point);
        if (A.is_null() && c.k == LimKind::Zero) A = f;
        else if (B.is_null() && c.k == LimKind::Inf) B = f;
    }
    if (A.is_null() || B.is_null())
        throw std::domain_error("0·∞ 型：找不到过零因子与发散因子（暂不猜）");

    // x^p（p>0）乘 log(x)^k → 0，无论 k 多大：阶关系确定，不必洛必达
    // （实测 log x / (1/x) 硬走洛必达会一直振荡）。
    if (point == 0.0) {
        std::function<bool(const RCP<const Basic>&, double&)> pow_of_var;
        pow_of_var = [&](const RCP<const Basic>& ex, double& p) -> bool {
            if (SymEngine::is_a<SymEngine::Symbol>(*ex) &&
                SymEngine::down_cast<const SymEngine::Symbol&>(*ex).get_name() == ctx.name) {
                p = 1.0;
                return true;
            }
            if (SymEngine::is_a<SymEngine::Pow>(*ex)) {
                const auto& pw = SymEngine::down_cast<const SymEngine::Pow&>(*ex);
                if (SymEngine::is_a<SymEngine::Symbol>(*pw.get_base()) &&
                    SymEngine::down_cast<const SymEngine::Symbol&>(*pw.get_base()).get_name() == ctx.name &&
                    SymEngine::is_a_Number(*pw.get_exp())) {
                    try {
                        p = SymEngine::eval_double(*pw.get_exp());
                        return p > 0;
                    } catch (...) {
                        return false;
                    }
                }
                return false;
            }
            if (SymEngine::is_a<SymEngine::Mul>(*ex)) {   // 常数系数 × x^p
                double acc = 0.0;
                for (const auto& fac : ex->get_args()) {
                    if (SymEngine::is_a_Number(*fac) || SymEngine::is_a<SymEngine::Constant>(*fac)) continue;
                    double q = 0.0;
                    if (!pow_of_var(fac, q)) return false;
                    acc += q;
                }
                p = acc;
                return p > 0;
            }
            return false;
        };
        std::function<bool(const RCP<const Basic>&)> log_power;
        log_power = [&](const RCP<const Basic>& ex) -> bool {
            if (SymEngine::is_a<SymEngine::Log>(*ex)) return true;
            if (SymEngine::is_a<SymEngine::Pow>(*ex))
                return log_power(SymEngine::down_cast<const SymEngine::Pow&>(*ex).get_base());
            if (SymEngine::is_a<SymEngine::Mul>(*ex)) {
                for (const auto& fac : ex->get_args())
                    if (!SymEngine::is_a_Number(*fac) && !log_power(fac)) return false;
                return true;
            }
            return false;
        };
        double pA = 0.0, pB = 0.0;
        if ((pow_of_var(A, pA) && log_power(B)) || (pow_of_var(B, pB) && log_power(A)))
            return 0.0;
    }

    const auto one_over_A = SymEngine::div(SymEngine::one, A);
    const auto one_over_B = SymEngine::div(SymEngine::one, B);
    const bool a_is_log = lf_has_log(A) || lf_has_log(B);   // log 因子放分子更易收敛
    std::vector<std::pair<RCP<const Basic>, RCP<const Basic>>> tries;
    if (a_is_log) {
        tries.push_back({A, one_over_B});
        tries.push_back({B, one_over_A});
    } else {
        tries.push_back({B, one_over_A});
        tries.push_back({A, one_over_B});
    }
    for (const auto& t : tries) {
        try {
            return lf_lhopital_pair(t.first, t.second, ctx, point, dir, depth + 1);
        } catch (const std::exception&) {
            try {
                return limit_solve(SymEngine::div(t.first, t.second), ctx, point, dir, depth + 1);
            } catch (const std::exception&) { /* 换另一种改写 */
            }
        }
    }
    throw std::domain_error("0·∞ 型：两种恒等改写都没定出（暂不猜）");
}

/** ∞−∞：通分 → 共轭有理化 → 阶比较 */
double lf_diff_rewrite(const RCP<const Basic>& e, const LimCtx& ctx, double point,
                       const std::string& dir, int depth) {
    {
        RCP<const Basic> num, den;
        SymEngine::as_numer_denom(e, SymEngine::outArg(num), SymEngine::outArg(den));
        if (!lf_is_one(den)) {
            try {
                return lf_lhopital_pair(num, den, ctx, point, dir, depth + 1);
            } catch (const std::exception&) { /* 继续试别的办法 */
            }
        }
    }
    const auto args = e->get_args();
    if (args.size() == 2 && (lf_has_half_pow(args[0]) || lf_has_half_pow(args[1]))) {
        const auto A = args[0];
        const auto B = SymEngine::neg(args[1]);      // e = A − B
        const auto conj = SymEngine::div(
            SymEngine::sub(SymEngine::pow(A, SymEngine::integer(2)),
                           SymEngine::pow(B, SymEngine::integer(2))),
            SymEngine::add(A, B));
        try {
            return limit_solve(conj, ctx, point, dir, depth + 1);
        } catch (const std::exception&) { /* 落到阶比较 */
        }
    }
    if (std::isinf(point)) {
        double omax = -1e300, omin = 1e300;
        int sign_of_max = 0;
        for (const auto& t : args) {
            const double o = lf_order(t, ctx.name);
            omax = (std::max)(omax, o);
            omin = (std::min)(omin, o);
        }
        for (const auto& t : args) {
            if (lf_order(t, ctx.name) > omax - 1e-9) {
                const LimForm c = lf_classify(t, ctx.name, point);
                sign_of_max = c.k == LimKind::Inf ? c.sign : (c.k == LimKind::Finite ? lf_sgn(c.v) : 0);
                break;
            }
        }
        if (omax > omin + 1e-9 && sign_of_max != 0) return sign_of_max * kLimInf;
    }
    throw std::domain_error("∞−∞ 型：通分 / 共轭有理化 / 阶比较都没定出（暂不猜）");
}

/**
 * 分段函数（sign / abs 这类）在分界点处的单侧数值极限。
 *
 * 为什么必须数值做：这些函数在分界点**没有可用的符号展开**
 * （abs 不可导、sign 在 SymEngine 里 sign(0)=0），l'Hôpital、泰勒、
 * 共轭有理化都用不上，而"从哪一侧趋近"恰恰决定了答案：
 *   sign 在 0：右 → +1、左 → −1
 *   abs(x)/x 在 0：右 → +1、左 → −1
 * 做法：从指定一侧取一串递减的 h 采样，要求值收敛（相邻步差迅速变小），
 * 否则视为不可靠并如实报错（不猜）。
 */
double lf_piecewise_limit(const RCP<const Basic>& e, const LimCtx& ctx,
                          double point, const std::string& dir, const std::string& why) {
    // ── 首选：按侧别**代数改写** |g| / sign(g) ─────────────────────────────
    // g 在 point 处横向穿过零点时，单侧有确定符号：
    //   右：|g| → g、sign(g) → +1（若 g'(point) < 0 则相反）
    //   左：|g| → −g、sign(g) → −1
    // 于是 abs(x)/x 在右侧改写为 x/x → 精确的 1，左侧 → −x/x → −1。
    // 比数值采样可靠得多：实测 SymEngine 对"含 Abs 的商"做数值求值会失败，
    // 走采样那条路只会得到"未收敛"（而数值采样也拿不到精确的有理结果）。
    {
        std::vector<RCP<const Basic>> nodes;
        std::function<void(const RCP<const Basic>&, int)> walk =
            [&](const RCP<const Basic>& t, int depth) {
                if (t.is_null() || depth > 32) return;
                if (SymEngine::is_a<SymEngine::Abs>(*t) || SymEngine::is_a<SymEngine::Sign>(*t))
                    nodes.push_back(t);
                for (const auto& a : t->get_args()) walk(a, depth + 1);
            };
        walk(e, 0);
        struct Piece { RCP<const Basic> node, g; double gprime; bool is_abs; };
        std::vector<Piece> pieces;
        bool all_transversal = !nodes.empty();
        for (const auto& nd : nodes) {
            const auto& args = nd->get_args();
            if (args.size() != 1) { all_transversal = false; break; }
            const RCP<const Basic> g = args[0];
            double gp = 0.0;
            try {
                gp = SymEngine::eval_double(*SymEngine::diff(g, ctx.x)
                                                ->subs({{ctx.x, SymEngine::real_double(point)}}));
            } catch (const std::exception&) {
                all_transversal = false;
                break;
            }
            if (!std::isfinite(gp) || std::abs(gp) < 1e-12) {
                all_transversal = false;   // 高阶零点：两侧同号，不能这么改写
                break;
            }
            pieces.push_back({nd, g, gp, SymEngine::is_a<SymEngine::Abs>(*nd)});
        }
        const auto solve_side = [&](int side, bool& ok) -> double {
            ok = false;
            SymEngine::map_basic_basic repl;
            for (const auto& p : pieces) {
                const bool positive = (p.gprime > 0) == (side > 0);
                if (p.is_abs) {
                    repl[p.node] = positive ? p.g : SymEngine::neg(p.g);
                } else {
                    repl[p.node] = positive ? RCP<const Basic>(SymEngine::one)
                                            : RCP<const Basic>(SymEngine::integer(-1));
                }
            }
            RCP<const Basic> rw;
            try {
                rw = e->xreplace(repl);
            } catch (const std::exception&) {
                return 0.0;
            }
            try {
                const double v = limit_solve(rw, ctx, point, side > 0 ? "+" : "-", 0);
                if (std::isfinite(v)) { ok = true; return v; }
            } catch (const std::exception&) {
            }
            return 0.0;
        };
        if (all_transversal) {
            const int want = lf_side(dir);
            if (want != 0) {
                bool ok = false;
                const double v = solve_side(want, ok);
                if (ok) return v;
            } else {
                bool okl = false, okr = false;
                const double vl = solve_side(-1, okl);
                const double vr = solve_side(+1, okr);
                if (okl && okr) {
                    if (std::abs(vl - vr) < 1e-9 * (1.0 + std::abs(vl))) return 0.5 * (vl + vr);
                    throw std::domain_error("极限不存在：左 " + std::to_string(vl) +
                                            "、右 " + std::to_string(vr) + "（两侧不等）");
                }
            }
        }
    }

    // ── 兜底：单侧数值采样（高阶零点等改写不适用的情形）──────────────
    const auto one_side = [&](int side, bool& ok) -> double {
        ok = false;
        std::vector<double> hs, vs;
        double prev_delta = std::numeric_limits<double>::quiet_NaN();
        for (double h : {1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-7}) {
            const double t = point + side * h;
            double v = 0.0;
            try {
                v = SymEngine::eval_double(*e->subs({{ctx.x, SymEngine::real_double(t)}}));
            } catch (const std::exception&) {
                return 0.0;
            }
            if (!std::isfinite(v)) return 0.0;
            if (vs.size() >= 2) {
                const double delta = std::abs(v - vs.back());
                if (std::isfinite(prev_delta) && delta > prev_delta * 0.9)
                    return 0.0;   // 步长变小而差值不缩小 → 未收敛，不猜
                prev_delta = delta;
            }
            hs.push_back(h);
            vs.push_back(v);
        }
        if (vs.size() < 3) return 0.0;
        // **不能直接返回最小步长的采样值**：abs(x) 在 0 处那样线性趋于 0 的
        // 情况会返回 1e-7 而不是 0。
        // 按 v(h) ≈ L + c·h 用最小的两个步长外推，步长比从**实际序列**取：
        //   v₁ = v(h₁)、v₂ = v(h₂)、k = h₂/h₁ ⇒ L = (k·v₁ − v₂)/(k−1)
        //   （序列是 1e-2,1e-3,… ⇒ k = 10）
        //   abs(x)  → (10·1e-7 − 1e-6)/9 = 0 ✓
        //   sign(x) → (10·1 − 1)/9 = 1 ✓
        // ⚠ 别用 std::ldexp(1.0, -7) 去表达 1e-7 —— 那是 2⁻⁷ = 7.8e-3，
        //   会让 k 变成 2，abs(x) 于是算出 −8e-7、把"连续"误判成不连续。
        const std::size_t n_v = vs.size();
        const double h1 = hs[n_v - 1], h2 = hs[n_v - 2];
        const double k = h2 / h1;
        const double v_small = vs[n_v - 1];
        const double v_mid = vs[n_v - 2];
        const double L = (k * v_small - v_mid) / (k - 1.0);
        const double tol = (std::max)(1e-9, 0.01 * std::abs(L));
        if (std::isfinite(L) && std::abs(L - v_small) <= (std::max)(tol, 10.0 * std::abs(v_mid - v_small))) {
            ok = true;
            return L;
        }
        ok = true;
        return v_small;
    };

    const int want = lf_side(dir);
    if (want != 0) {
        bool ok = false;
        const double v = one_side(want, ok);
        if (ok) return v;
        throw std::domain_error(why + "：单侧数值采样未收敛（暂不猜结果）");
    }
    bool okl = false, okr = false;
    const double vl = one_side(-1, okl);
    const double vr = one_side(+1, okr);
    if (okl && okr) {
        if (std::abs(vl - vr) < 1e-6 * (1.0 + std::abs(vl))) return 0.5 * (vl + vr);
        throw std::domain_error("极限不存在：左 " + std::to_string(vl) +
                                "、右 " + std::to_string(vr) + "（两侧不等）");
    }
    throw std::domain_error(why + "：双侧数值采样未收敛（暂不猜结果）");
}

/** ∞ 兜底：x = 1/t，t→0±（x→+∞ ⇔ t→0⁺） */double lf_reduce_inf(const RCP<const Basic>& e, const LimCtx& ctx, double point, int depth) {
    const auto t = SymEngine::symbol("_mf_lim_t");
    RCP<const Basic> sub;
    try {
        sub = SymEngine::expand(
            e->subs({{ctx.x, SymEngine::div(SymEngine::one, t)}}));
    } catch (...) {
        throw std::domain_error("∞ 归约（t=1/x）时代换失败");
    }
    const std::string tdir = point > 0 ? "+" : "-";
    const LimCtx c2{t, "_mf_lim_t"};
    return limit_solve(sub, c2, 0.0, tdir, depth + 1);
}

double limit_solve(const RCP<const Basic>& e, const LimCtx& ctx, double point,
                   const std::string& dir, int depth) {
    if (depth > kLimMaxDepth) throw std::domain_error("极限策略递归过深（暂不猜）");
    lim_spend("形式判定");

    const LimForm c = lf_classify(e, ctx.name, point);

    // L2：不是不定式 → 直接代入就是答案
    if (c.k == LimKind::Finite) return c.v;
    if (c.k == LimKind::Zero) return 0.0;
    if (c.k == LimKind::Inf) {
        if (c.sign != 0) return c.sign * kLimInf;
        // 符号不明的发散（1/x 在 0 这种）：必须分侧判断，双侧不等就说"不存在"
        if (lf_side(dir) != 0)
            return lf_diverge_by_sign(RCP<const Basic>(SymEngine::one), e, ctx, point, dir, c.why);
        const int dl = lf_sign_probe(e, ctx, point, -1);
        const int dr = lf_sign_probe(e, ctx, point, +1);
        if (dl != 0 && dr != 0 && dl != dr)
            throw std::domain_error(std::string("极限不存在：左 ") + (dl > 0 ? "+∞" : "−∞") +
                                    "、右 " + (dr > 0 ? "+∞" : "−∞"));
        const int ds = dr != 0 ? dr : dl;
        if (ds != 0) return ds * kLimInf;
        throw std::domain_error(c.why + "：发散但符号无法判定");
    }

    // L4：不定式各路（先在当前点按形式走，∞ 的语义已在分类里体现）
    try {
        // 分段函数（sign/abs）在分界点：符号工具全用不上，走单侧数值
        if (c.why.find("（分段）") != std::string::npos)
            return lf_piecewise_limit(e, ctx, point, dir, c.why);
        if (c.why == "0/0" || c.why == "∞/∞") {
            RCP<const Basic> n, d;
            SymEngine::as_numer_denom(e, SymEngine::outArg(n), SymEngine::outArg(d));
            if (!lf_is_one(d)) return lf_lhopital_pair(n, d, ctx, point, dir, depth);
            throw std::domain_error(c.why + " 型：无法提取分子分母");
        }
        if (c.why == "1^∞" || c.why == "0^0" || c.why == "∞^0")
            return lf_power_exp_log(e, ctx, point, dir, depth);
        if (c.why == "0·∞") return lf_product_rewrite(e, ctx, point, dir, depth);
        if (c.why == "∞−∞") return lf_diff_rewrite(e, ctx, point, dir, depth);
    } catch (const std::exception&) {
        // 各路的失败原因不再往上叠（避免"未解出：未解出：…"的套娃），
        // 只在最后兜底尝试 ∞ 归约，仍不成则抛出**本条路**的理由。
        if (!std::isinf(point)) throw;
    }

    if (std::isinf(point)) return lf_reduce_inf(e, ctx, point, depth);
    throw std::domain_error("不定式「" + c.why + "」暂未实现该形式的求解（不猜结果）");
}

}  // namespace

// ── 公开 API ────────────────────────────────────────────────────────────────
// 这一段的函数原先定义在**全局命名空间**（连 series_limit / direct_eval /
// convert_* 这些内部助手也是）。现统一收进 mf::calculus，与 is_continuous_at /
// classify_discontinuity 保持一致。调用方：calculus_api.cpp（有 using
// namespace mf::calculus，无需改动）、extras/analysis.cpp、tests/test_limits.cpp。
namespace mf::calculus {

// 计算 f(x)/g(x)(f/g)在 point 处的极限。
// 完整规则见本文件顶部「极限求解：形式判定 + 分层策略」的说明；
// 长期回归见 tests/test_limits.cpp。
double limit(const std::string& expr, const std::string& var, double point,
             const std::string& direction) {
    try {
        // 入口统一把"整齐"的浮点指数换成精确有理数（x^0.5 → x^(1/2)）：
        // 语义不变，但让用户写的 0.5 与教材写的 1/2 走同一条路径。
        const auto e = lf_exactify_pows(SymEngine::parse(expr));
        g_lim_steps = 0;
        g_lim_t0 = std::chrono::steady_clock::now();
        const LimCtx ctx{SymEngine::symbol(var), var};
        return limit_solve(e, ctx, point, direction, 0);
    } catch (const std::domain_error&) {
        throw;   // 已经是写好的可读理由
    } catch (const std::exception& ex) {
        throw std::domain_error(std::string("极限求解失败：") + ex.what());
    }
}


// ── 极限形式分类与派发 ──────────────────────────────────────────────────────

// 表达式最外层形式:0 个或 1 个二元运算符。
enum class LimitType { Number, Variable, Function, Sum, Diff, Product, FG, Power };

// 识别表达式树最外层形式。
LimitType identify(const ExprNode* n) {
	switch (n->type) {
		case NodeType::Number:   return LimitType::Number;
		case NodeType::Variable: return LimitType::Variable;
		case NodeType::Function: return LimitType::Function;
		case NodeType::Binary:
			switch (n->op) {
				case '+': return LimitType::Sum;
				case '-': return LimitType::Diff;
				case '*': return LimitType::Product;
				case '/': return LimitType::FG;
				case '^': return LimitType::Power;
				default:  throw std::runtime_error("未知运算符");
			}
	}
	throw std::runtime_error("未知节点类型");
}

// ── 各形式极限函数(由调用方实现)────────────────────────────────────────────
double series_limit(const std::string& expr, const std::string& var, double point){
	return limit(expr, var, point);
}
double direct_eval(const std::string& expr, const std::string& var, double point) {
	auto x = SymEngine::symbol(var);
    return SymEngine::eval_double(
        *SymEngine::parse(expr)->subs({{x, SymEngine::real_double(point)}}));
}
double convert_diff(const std::string& expr, const std::string& var, double point) {
	auto x = SymEngine::symbol(var);
	bool at_inf = std::isinf(point) || point == std::numeric_limits<double>::infinity();
	std::vector<std::string> v = split(expr, '-');
	std::string f = v[0];
	std::string g = v[1];
	auto ex = SymEngine::parse(expr);
	if (at_inf){
		auto t = SymEngine::symbol("t");
		auto ex_t = SymEngine::subs(ex, { {x, 1/t} });
		point = 0;
		auto ex_taylor = expand_transcendental(ex_t, t, point, 20);
		return SymEngine::eval_double(*SymEngine::subs(ex_taylor, {{t, SymEngine::real_double(point)}}));
	}else {
		auto ex_taylor = expand_transcendental(ex, x, point, 20);
		return SymEngine::eval_double(*SymEngine::subs(ex_taylor, {{x, SymEngine::real_double(point)}}));
	}
}
double convert_product(const std::string& expr, const std::string& var, double point) {
	auto x = SymEngine::symbol(var);
	std::vector<std::string> v = split(expr, '*');
	std::string f = v[0];
	std::string g = v[1];
	auto f_ex = SymEngine::parse(f);
	auto g_ex = SymEngine::parse(g);
	auto e1 = SymEngine::parse("1");
	auto quot = SymEngine::div(e1, g_ex);
	g_ex = quot;

	auto num = expand_transcendental(f_ex, x, point, 20);
	auto den = expand_transcendental(g_ex, x, point, 20);

	// 主路径:expand 约分(可约单项式公因子,如 sin(x)/x),成功直接出值。
	double r;
	try {
		r = SymEngine::eval_double(*SymEngine::expand(
			SymEngine::div(num, den))->subs({ {x, SymEngine::real_double(point)} }));
	}
	catch (...) {
		r = NAN;
	}
	if (std::isfinite(r)) return r;

	// 退化:约不掉(0/0)→ 洛必达,分子分母各求导直到分母非零。
	for (int i = 0; i < 20; ++i) {
		const double nv = SymEngine::eval_double(
			*num->subs({ {x, SymEngine::real_double(point)} }));
		const double dv = SymEngine::eval_double(
			*den->subs({ {x, SymEngine::real_double(point)} }));
		if (std::abs(dv) > 1e-12) return nv / dv;
		if (std::abs(nv) > 1e-12)
			throw std::domain_error("极限发散");
		num = SymEngine::diff(num, x);
		den = SymEngine::diff(den, x);
	}
	throw std::domain_error("无法确定极限");
	return r;
}
double convert_power(const std::string& expr, const std::string& var, double point) {
	auto x = SymEngine::symbol(var);
	std::vector<std::string> v = split(expr, "**");
	std::string f = v[0];
	std::string g = v[1];
	auto f_ex = SymEngine::parse(f);
	auto g_ex = SymEngine::parse(g);
	f_ex = SymEngine::sub(f_ex, SymEngine::integer(1));
	auto prod = SymEngine::mul(f_ex, g_ex);

	auto prod_taylor = expand_transcendental(prod, x, point, 20);
	
	double L = SymEngine::eval_double(*SymEngine::subs(prod_taylor, {{x, SymEngine::real_double(point)}}));
	return std::exp(L);
}

// 分类派发:按最外层形式调用不同极限函数(各 convert_* 直接返回极限值)。
double spl(const std::string& expr, const std::string& var, double point) {
	auto root = parse(expr);
	switch (identify(root.get())) {
		case LimitType::FG:       // f/g(相除)→ 级数法
			return series_limit(expr, var, point);
		case LimitType::Diff:     // f-g(相减)
			return convert_diff(expr, var, point);
		case LimitType::Product:  // f*g(相乘)
			return convert_product(expr, var, point);
		case LimitType::Power:    // f^g(幂)
			return convert_power(expr, var, point);
		case LimitType::Sum:      // f+g(相加)→ 直接代值
		case LimitType::Number:
		case LimitType::Variable:
		case LimitType::Function: return direct_eval(expr, var, point);
		default:                  throw std::runtime_error("无法处理");
	}
}

// ── 只展开超越函数(sin/cos/tan/log/e^u),多项式/四则结构保持原样 ────────────

static RCP<const Basic> expand_to_sym(double v) {
	const double r = std::round(v);
	if (std::abs(v - r) < 1e-12)
		return SymEngine::integer(static_cast<long long>(r));
	return SymEngine::real_double(v);
}

static RCP<const Basic> expand_diff_order(const RCP<const Basic>& e,
	                                      const RCP<const Symbol>& x,
	                                      long long n) {
	RCP<const Basic> cur = e;
	for (long long i = 0; i < n; ++i) cur = SymEngine::diff(cur, x);
	return cur;
}

// 单个表达式 → 泰勒多项式(Basic)。
static RCP<const Basic> expand_taylor_basic(const RCP<const Basic>& f,
	                                        const RCP<const Symbol>& x,
	                                        double point, long long order) {
	const auto a = expand_to_sym(point);
	RCP<const Basic> t = SymEngine::zero;
	for (long long k = 0; k <= order; ++k) {
		const auto dk = expand_diff_order(f, x, k);
		const auto coeff = SymEngine::div(dk->subs({{x, a}}),
			SymEngine::factorial(static_cast<unsigned long>(k)));
		t = SymEngine::add(t, SymEngine::mul(
			coeff, SymEngine::pow(SymEngine::sub(x, a), SymEngine::integer(k))));
	}
	return t;
}

// 是否为超越函数节点(sin/cos/tan/log/e^u)。
static bool expand_is_trans(const RCP<const Basic>& e) {
	if (SymEngine::is_a<SymEngine::Sin>(*e) ||
	    SymEngine::is_a<SymEngine::Cos>(*e) ||
	    SymEngine::is_a<SymEngine::Tan>(*e) ||
	    SymEngine::is_a<SymEngine::Log>(*e))
		return true;
	if (SymEngine::is_a<SymEngine::Pow>(*e)) {
		const auto args = e->get_args();
		return SymEngine::eq(*args[0], *SymEngine::E);  // exp(u)
	}
	return false;
}

// 递归:只展开超越函数叶子,Add/Mul/Pow 重建,数字/符号保留。
static RCP<const Basic> expand_trans(const RCP<const Basic>& e,
	                                 const RCP<const Symbol>& x, double point,
	                                 long long order) {
	if (expand_is_trans(e)) return expand_taylor_basic(e, x, point, order);
	if (SymEngine::is_a<SymEngine::Add>(*e) ||
	    SymEngine::is_a<SymEngine::Mul>(*e)) {
		SymEngine::vec_basic args;
		for (const auto& a : e->get_args())
			args.push_back(expand_trans(a, x, point, order));
		return SymEngine::is_a<SymEngine::Add>(*e)
		           ? SymEngine::add(args)
		           : SymEngine::mul(args);
	}
	if (SymEngine::is_a<SymEngine::Pow>(*e)) {
		const auto args = e->get_args();
		return SymEngine::pow(expand_trans(args[0], x, point, order),
		                      expand_trans(args[1], x, point, order));
	}
	return e;  // Number / Symbol
}

// 输入 SymEngine 表达式,把其中超越函数就地展开成泰勒多项式,返回展开后的表达式。
RCP<const Basic> expand_transcendental(const RCP<const Basic>& expr,
                                       const RCP<const Symbol>& x,
                                       double point, long long order) {
    return expand_trans(expr, x, point, order);
}

namespace {
// 单侧极限(side: -1 左,+1 右);振荡/无法计算返回 NaN。
double eval_one_sided(const std::string& expr, const std::string& var,
                      double point, int side) {
    try {
        return limit(expr, var, point, side > 0 ? "+" : "-");
    } catch (...) {
        return std::numeric_limits<double>::quiet_NaN();
    }
}
}  // namespace

// 判断函数在某点是否连续:f(point) 有定义、双侧极限存在且等于 f(point)。
bool is_continuous_at(const std::string& expr, const std::string& var,
                      double point) {
    double fv = std::numeric_limits<double>::quiet_NaN();
    try {
        fv = direct_eval(expr, var, point);
    } catch (...) {
        fv = std::numeric_limits<double>::quiet_NaN();
    }
    if (!std::isfinite(fv)) return false;
    double lv = std::numeric_limits<double>::quiet_NaN();
    try {
        lv = limit(expr, var, point);
    } catch (...) {
        lv = std::numeric_limits<double>::quiet_NaN();
    }
    if (!std::isfinite(lv)) return false;
    return std::abs(lv - fv) < 1e-10;
}

// 间断点分类:无穷 / 振荡 / 可去 / 跳跃。
std::string classify_discontinuity(const std::string& expr,
                                   const std::string& var, double point) {
    const double ll = eval_one_sided(expr, var, point, -1);
    const double rl = eval_one_sided(expr, var, point, +1);
    if (std::isinf(ll) || std::isinf(rl)) return "无穷间断点";
    if (!std::isfinite(ll) || !std::isfinite(rl)) return "振荡间断点";
    if (std::abs(ll - rl) < 1e-9) return "可去间断点";
    return "跳跃间断点";
}

}  // namespace mf::calculus