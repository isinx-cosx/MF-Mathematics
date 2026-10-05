// integrals.cpp — 积分内核:自研符号积分(多项式规则 + 初等积分表 + 分部积分)
// + 数值辛普森 + 反常积分。
//
// antiderivative 返回符号原函数,无法积分时返回空(SymEngine RCP null);
// integrate_indefinite 无法积分时返回 "未实现",不编造结果。

#include "integrals.h"

#include <cmath>
#include <complex>
#include <cstdio>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/complex.h>
#include <symengine/constants.h>
#include <symengine/derivative.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/mul.h>
#include <symengine/parser.h>
#include <symengine/pow.h>
#include <symengine/printers.h>
#include <symengine/rational.h>
#include <symengine/real_double.h>
#include <symengine/simplify.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>
#include <symengine/visitor.h>

namespace mf::calculus {

namespace {

using SymEngine::RCP;
using SymEngine::Basic;
using SymEngine::Symbol;

enum class BoundKind { Finite, Pi, PosInf, NegInf };
struct Bound {
    BoundKind kind = BoundKind::Finite;
    double value = 0.0;
};

Bound parse_bound(const std::string& s) {
    std::string t = s;
    const std::string ws = " \t\r\n";
    const auto b = t.find_first_not_of(ws);
    const auto e = t.find_last_not_of(ws);
    t = (b == std::string::npos) ? "" : t.substr(b, e - b + 1);
    if (t == "pi" || t == "π") return {BoundKind::Pi, 3.14159265358979323846};
    if (t == "oo" || t == "inf" || t == "+oo" || t == "+inf" || t == "∞")
        return {BoundKind::PosInf, 0.0};
    if (t == "-oo" || t == "-inf" || t == "-∞")
        return {BoundKind::NegInf, 0.0};
    char* end = nullptr;
    const double v = std::strtod(t.c_str(), &end);
    if (end == t.c_str() || *end != '\0')
        throw std::invalid_argument("无法解析积分边界 '" + s + "'");
    return {BoundKind::Finite, v};
}

bool is_inf(const Bound& b) {
    return b.kind == BoundKind::PosInf || b.kind == BoundKind::NegInf;
}

RCP<const Basic> to_sym_number(double v) {
    const double r = std::round(v);
    if (std::abs(v - r) < 1e-12) return SymEngine::integer(static_cast<long long>(r));
    return SymEngine::real_double(v);
}

// ── 符号原函数 ──────────────────────────────────────────────────────────────

// u = m·x + b 线性(m≠0)。
bool is_linear(const RCP<const Basic>& u, const RCP<const Symbol>& x,
               RCP<const Basic>& m, RCP<const Basic>& b) {
    try {
        m = SymEngine::coeff(*u, *x, *SymEngine::integer(1));
        b = SymEngine::coeff(*u, *x, *SymEngine::integer(0));
        const auto recon = SymEngine::add({SymEngine::mul(m, x), b});
        if (!SymEngine::eq(*SymEngine::expand(SymEngine::sub(u, recon)),
                           *SymEngine::zero))
            return false;
        return !SymEngine::eq(*SymEngine::simplify(m), *SymEngine::zero);
    } catch (...) {
        return false;
    }
}

bool is_constant(const RCP<const Basic>& e, const RCP<const Symbol>& x) {
    return !SymEngine::has_symbol(*e, *x);
}

// 纯多项式节点(非负整数次幂、四则、常系数)。
//
// ⚠ 旧实现最后是 `for (args) if (!is_poly_node(a)) return false; return true;` ——
//   叶子节点（Sin/Log/Exp 这类没有子节点的）走完空循环后**直接返回 true**，
//   于是 is_poly_node(sin(x)) 为真、is_poly_in_x(sin(x), x) 也为真。
//   后果：「p(x)·g(x) 分部积分」那一支会把 sin(x)*cos(x) 里的 cos(x) 当成多项式因子
//   （见 by_parts 调用处），走错分支。
//   algebra 包的 poly_node 是同一缺陷模式（那边已修），这里对齐：
//   只有 数/常数/符号/Add/Mul/非负整数次幂 才算多项式节点，其余一律 false。
bool is_poly_node(const RCP<const Basic>& e) {
    if (SymEngine::is_a_Number(*e) || SymEngine::is_a<SymEngine::Constant>(*e))
        return true;
    if (SymEngine::is_a<SymEngine::Symbol>(*e)) return true;
    if (SymEngine::is_a<SymEngine::Pow>(*e)) {
        const auto args = e->get_args();
        if (args.size() != 2) return false;
        if (!SymEngine::is_a<SymEngine::Integer>(*args[1])) return false;
        if (SymEngine::down_cast<const SymEngine::Integer&>(*args[1]).as_int() < 0)
            return false;
        return is_poly_node(args[0]);
    }
    if (SymEngine::is_a<SymEngine::Add>(*e) || SymEngine::is_a<SymEngine::Mul>(*e)) {
        for (const auto& a : e->get_args())
            if (!is_poly_node(a)) return false;
        return true;
    }
    return false;   // 函数节点（sin/log/exp/…）不是多项式节点
}

// 含 x 的多项式(度 ≥ 1)。
bool is_poly_in_x(const RCP<const Basic>& e, const RCP<const Symbol>& x) {
    return SymEngine::has_symbol(*e, *x) && is_poly_node(e);
}

// 是否为 sin / cos / e^u 之一。
bool is_sin_cos_exp(const RCP<const Basic>& e) {
    if (SymEngine::is_a<SymEngine::Sin>(*e) ||
        SymEngine::is_a<SymEngine::Cos>(*e))
        return true;
    if (SymEngine::is_a<SymEngine::Pow>(*e)) {
        const auto args = e->get_args();
        return SymEngine::eq(*args[0], *SymEngine::E);
    }
    return false;
}

// f 为 sin(u)/cos(u) 且 u 线性 → 填充 (is_sin, u, m, b)。
bool trig_linear_info(const RCP<const Basic>& f, const RCP<const Symbol>& x,
                      bool& is_sin, RCP<const Basic>& u, RCP<const Basic>& m,
                      RCP<const Basic>& b) {
    if (SymEngine::is_a<SymEngine::Sin>(*f)) {
        is_sin = true;
        u = f->get_args()[0];
        return is_linear(u, x, m, b);
    }
    if (SymEngine::is_a<SymEngine::Cos>(*f)) {
        is_sin = false;
        u = f->get_args()[0];
        return is_linear(u, x, m, b);
    }
    return false;
}

// 积化和差 ∫sin(u)cos(v) 等。u=a1·x+b1, v=a2·x+b2 均线性。
RCP<const Basic> trig_product_integral(bool s1, const RCP<const Basic>& u1,
                                       const RCP<const Basic>& m1, bool s2,
                                       const RCP<const Basic>& u2,
                                       const RCP<const Basic>& m2,
                                       const RCP<const Basic>& x) {
    const auto sum = SymEngine::add(u1, u2);
    const auto diff = SymEngine::sub(u1, u2);
    const auto asum = SymEngine::add(m1, m2);
    const auto adiff = SymEngine::sub(m1, m2);
    const int kind = (s1 ? 2 : 0) + (s2 ? 1 : 0);  // sin=1, cos=0 的两位组合
    const auto half_x = SymEngine::div(x, SymEngine::integer(2));
    if (SymEngine::eq(*SymEngine::simplify(adiff), *SymEngine::zero)) {
        // a1==a2(可能相位不同):积化和差,φ = u1-u2 是常数。
        //   sin·cos → −cos(sum)/(4a) + sin(φ)·x/2
        //   sin·sin → cos(φ)·x/2 − sin(sum)/(4a)
        //   cos·sin → −cos(sum)/(4a) − sin(φ)·x/2
        //   cos·cos → sin(sum)/(4a) + cos(φ)·x/2
        const auto c4 = SymEngine::div(SymEngine::cos(sum),
                                       SymEngine::mul(SymEngine::integer(4), m1));
        const auto s4 = SymEngine::div(SymEngine::sin(sum),
                                       SymEngine::mul(SymEngine::integer(4), m1));
        const auto cphi = SymEngine::mul(SymEngine::cos(diff), half_x);
        const auto sphi = SymEngine::mul(SymEngine::sin(diff), half_x);
        switch (kind) {
            case 2:  // sin·cos
                return SymEngine::sub(sphi, c4);
            case 3:  // sin·sin
                return SymEngine::sub(cphi, s4);
            case 1:  // cos·sin
                return SymEngine::sub(SymEngine::neg(c4), sphi);
            default:  // cos·cos
                return SymEngine::add(s4, cphi);
        }
    }
    // a1 ≠ a2:一般积化和差。
    const auto csum = SymEngine::div(SymEngine::cos(sum),
                                     SymEngine::mul(SymEngine::integer(2), asum));
    const auto cdif = SymEngine::div(SymEngine::cos(diff),
                                     SymEngine::mul(SymEngine::integer(2), adiff));
    const auto ssum = SymEngine::div(SymEngine::sin(sum),
                                     SymEngine::mul(SymEngine::integer(2), asum));
    const auto sdif = SymEngine::div(SymEngine::sin(diff),
                                     SymEngine::mul(SymEngine::integer(2), adiff));
    switch (kind) {
        case 2:  // sin(u)cos(v) = [sin(u+v)+sin(u−v)]/2
            return SymEngine::sub(SymEngine::neg(csum), cdif);
        case 3:  // sin(u)sin(v) = [cos(u−v)−cos(u+v)]/2
            return SymEngine::sub(sdif, ssum);
        case 1:  // cos(u)sin(v) = [sin(u+v)−sin(u−v)]/2
            return SymEngine::sub(SymEngine::neg(csum), SymEngine::neg(cdif));
        default:  // cos(u)cos(v) = [cos(u+v)+cos(u−v)]/2
            return SymEngine::add(ssum, sdif);
    }
    return RCP<const Basic>();
}

// ── 下面几条形状判定只服务本批新增的积分规则（全部只看结构，不做任何"猜"）──

// base 是否形如 c + u²：c 关于 x 是常数、u 关于 x 线性。命中则给出 u 与它的斜率 m。
// 为什么要它：∫du/(c+u²) 那一族（含最基础的 ∫dx/(1+x²) = atan x）是教科书里
// 最先遇到的一类，而原来的 Pow 分支只认"底数线性"（(mx+b)^n）—— 二次底数一律 null。
bool is_c_plus_square(const RCP<const Basic>& base, const RCP<const Symbol>& x,
                      RCP<const Basic>& u, RCP<const Basic>& m) {
    if (!SymEngine::is_a<SymEngine::Add>(*base)) return false;
    const auto args = base->get_args();
    if (args.size() != 2) return false;
    for (int i = 0; i < 2; ++i) {
        const auto& sq = args[i];
        const auto& other = args[1 - i];
        if (!is_constant(other, x)) continue;          // 另一项必须是常数
        if (!SymEngine::is_a<SymEngine::Pow>(*sq)) continue;
        const auto sa = sq->get_args();
        if (sa.size() != 2) continue;
        if (!SymEngine::is_a<SymEngine::Integer>(*sa[1])) continue;
        if (SymEngine::down_cast<const SymEngine::Integer&>(*sa[1]).as_int() != 2)
            continue;                                   // 指数必须正好是 2
        RCP<const Basic> mm, bb;
        if (!is_linear(sa[0], x, mm, bb)) continue;
        u = sa[0];
        m = mm;
        return true;
    }
    return false;
}

// base 是否形如 u·ln(u)（u 关于 x 线性）→ ∫dx/(u·ln u) = ln(ln u)/m
bool is_u_log_u(const RCP<const Basic>& base, const RCP<const Symbol>& x,
                RCP<const Basic>& u, RCP<const Basic>& m) {
    if (!SymEngine::is_a<SymEngine::Mul>(*base)) return false;
    const auto args = base->get_args();
    if (args.size() != 2) return false;
    for (int i = 0; i < 2; ++i) {
        if (!SymEngine::is_a<SymEngine::Log>(*args[i])) continue;
        const auto la = args[i]->get_args();
        if (la.size() != 1) continue;
        const auto& cand = args[1 - i];
        if (!SymEngine::eq(*la[0], *cand)) continue;    // ln 的参数必须**就是**另一个因子
        RCP<const Basic> mm, bb;
        if (!is_linear(cand, x, mm, bb)) continue;
        u = cand;
        m = mm;
        return true;
    }
    return false;
}

// base 是否形如 k + x²（k 常数）→ 配合因子 x 得 ∫x dx/(k+x²) = ½ln(k+x²)
bool is_k_plus_x_squared(const RCP<const Basic>& base,
                         const RCP<const Symbol>& x) {
    RCP<const Basic> u, m;
    if (!is_c_plus_square(base, x, u, m)) return false;
    return SymEngine::eq(*u, *x);
}

// 两个因子是否形如 u^(−1) 与 (ln u)^(−1)（u 线性）→ ∫dx/(u·ln u) = ln(ln u)/m
//
// 为什么需要它（而不是直接用 Pow 分支）：SymEngine 里 1/(x·ln x) 的**规范形**是
// `x^(-1) · ln(x)^(-1)`（两个负幂相乘），**不是** `Pow(Mul(x, ln x), -1)`。
// 所以这条规则必须在 Mul 分支上接；只看 Pow 分支永远匹配不到。
bool is_inv_u_times_inv_log_u(const RCP<const Basic>& a,
                              const RCP<const Basic>& b,
                              const RCP<const Symbol>& x,
                              RCP<const Basic>& u, RCP<const Basic>& m) {
    const auto inv_base = [](const RCP<const Basic>& e) -> RCP<const Basic> {
        if (!SymEngine::is_a<SymEngine::Pow>(*e)) return RCP<const Basic>();
        const auto args = e->get_args();
        if (args.size() != 2) return RCP<const Basic>();
        if (!SymEngine::is_a<SymEngine::Integer>(*args[1]))
            return RCP<const Basic>();
        if (SymEngine::down_cast<const SymEngine::Integer&>(*args[1]).as_int() != -1)
            return RCP<const Basic>();
        return args[0];
    };
    for (int i = 0; i < 2; ++i) {
        const auto ba = inv_base(i == 0 ? a : b);
        const auto bb = inv_base(i == 0 ? b : a);
        if (ba.is_null() || bb.is_null()) continue;
        if (!SymEngine::is_a<SymEngine::Log>(*bb)) continue;
        const auto la = bb->get_args();
        if (la.size() != 1 || !SymEngine::eq(*la[0], *ba)) continue;
        RCP<const Basic> mm, cc;
        if (!is_linear(ba, x, mm, cc)) continue;
        u = ba;
        m = mm;
        return true;
    }
    return false;
}

// e 是否 x^p（p 关于 x 常数，且 p ≠ −1）。裸 x 记作 p = 1。
//
// 排除 p = −1 是因为分母 (p+1) 会变 0 —— 那一条是 ∫ln x/x = ½ln²x，公式不同。
// 允许任意常数 p（不只整数）：√x·ln x 就是 p = ½ 的情形。
bool is_x_pow_const(const RCP<const Basic>& e, const RCP<const Symbol>& x,
                    RCP<const Basic>& p) {
    if (SymEngine::is_a<SymEngine::Symbol>(*e) && SymEngine::eq(*e, *x)) {
        p = SymEngine::integer(1);
        return true;
    }
    if (!SymEngine::is_a<SymEngine::Pow>(*e)) return false;
    const auto a = e->get_args();
    if (a.size() != 2) return false;
    if (!SymEngine::eq(*a[0], *x)) return false;
    if (SymEngine::has_symbol(*a[1], *x)) return false;   // 指数必须与 x 无关
    if (SymEngine::eq(*SymEngine::simplify(
                          SymEngine::add(a[1], SymEngine::integer(1))),
                      *SymEngine::zero))
        return false;                                     // p == −1 排除
    p = a[1];
    return true;
}

// base 是否 1 + x² 或 1 − x²。返回 0=不是、+1=1+x²、−1=1−x²。
// 用于 ∫√(1+x²)（arcsinh 闭式）与 ∫√(1−x²)（arcsin 闭式）。
int one_pm_x_squared(const RCP<const Basic>& base, const RCP<const Symbol>& x) {
    if (!SymEngine::is_a<SymEngine::Add>(*base)) return 0;
    const auto args = base->get_args();
    if (args.size() != 2) return 0;
    bool has_one = false;
    int sign = 0;
    for (const auto& a : args) {
        if (SymEngine::eq(*a, *SymEngine::integer(1))) {
            has_one = true;
            continue;
        }
        if (SymEngine::is_a<SymEngine::Pow>(*a)) {
            const auto pa = a->get_args();
            if (pa.size() == 2 && SymEngine::eq(*pa[0], *x) &&
                SymEngine::eq(*pa[1], *SymEngine::integer(2))) {
                sign = +1;
                continue;
            }
        }
        if (SymEngine::is_a<SymEngine::Mul>(*a)) {
            const auto ma = a->get_args();
            if (ma.size() == 2) {
                for (int i = 0; i < 2; ++i) {
                    if (!SymEngine::eq(*ma[i], *SymEngine::integer(-1))) continue;
                    if (!SymEngine::is_a<SymEngine::Pow>(*ma[1 - i])) continue;
                    const auto pa = ma[1 - i]->get_args();
                    if (pa.size() == 2 && SymEngine::eq(*pa[0], *x) &&
                        SymEngine::eq(*pa[1], *SymEngine::integer(2)))
                        sign = -1;
                }
            }
        }
    }
    if (!has_one || sign == 0) return 0;
    return sign;
}

// base 是否 1 + x⁴（∫dx/(1+x⁴) 的判别）
bool is_one_plus_x_fourth(const RCP<const Basic>& base,
                          const RCP<const Symbol>& x) {
    if (!SymEngine::is_a<SymEngine::Add>(*base)) return false;
    const auto args = base->get_args();
    if (args.size() != 2) return false;
    bool has_one = false, has_x4 = false;
    for (const auto& a : args) {
        if (SymEngine::eq(*a, *SymEngine::integer(1))) {
            has_one = true;
            continue;
        }
        if (!SymEngine::is_a<SymEngine::Pow>(*a)) continue;
        const auto pa = a->get_args();
        if (pa.size() == 2 && SymEngine::eq(*pa[0], *x) &&
            SymEngine::eq(*pa[1], *SymEngine::integer(4)))
            has_x4 = true;
    }
    return has_one && has_x4;
}

// ∫dx/(1+x⁴) 的标准闭式（1+x⁴ = (x²+√2x+1)(x²−√2x+1) 分解而来）：
//   (1/(4√2))·ln((x²+√2x+1)/(x²−√2x+1)) + (1/(2√2))·(atan(√2x−1) + atan(√2x+1))
// 正确性不靠这段注释背书 —— 测试里对它求导再与 1/(1+x⁴) 数值比对。
RCP<const Basic> antideriv_one_plus_x4(const RCP<const Basic>& x) {
    const auto one = SymEngine::integer(1);
    const auto two = SymEngine::integer(2);
    const auto four = SymEngine::integer(4);
    const auto x2 = SymEngine::pow(x, two);
    const auto s2 = SymEngine::sqrt(two);
    const auto s2x = SymEngine::mul(s2, x);
    const auto pp = SymEngine::add(SymEngine::add(x2, s2x), one);   // x²+√2x+1
    const auto mm = SymEngine::add(SymEngine::sub(x2, s2x), one);   // x²−√2x+1
    const auto log_term = SymEngine::div(
        SymEngine::log(SymEngine::div(pp, mm)), SymEngine::mul(four, s2));
    const auto atan_term = SymEngine::div(
        SymEngine::add(SymEngine::atan(SymEngine::sub(s2x, one)),
                       SymEngine::atan(SymEngine::add(s2x, one))),
        SymEngine::mul(two, s2));
    return SymEngine::add(log_term, atan_term);
}

// e 是否为 e^(a·x+c)（a≠0、a 与 c 关于 x 常数）→ 给出 u = a·x+c 与 a、c。
// 用于 ∫e^(a x+c)·sin(b x+d) 那一对闭式（两次分部积分的结果）。
bool exp_linear_info(const RCP<const Basic>& e, const RCP<const Symbol>& x,
                     RCP<const Basic>& u, RCP<const Basic>& a,
                     RCP<const Basic>& c) {
    if (!SymEngine::is_a<SymEngine::Pow>(*e)) return false;
    const auto args = e->get_args();
    if (args.size() != 2) return false;
    if (!SymEngine::eq(*args[0], *SymEngine::E)) return false;
    if (!is_linear(args[1], x, a, c)) return false;
    u = args[1];
    return true;
}

// 这里必须保留两行前向声明：antiderivative 与 by_parts 互相递归
// （by_parts 要调 antiderivative 求 ∫g；antiderivative 的 Mul 分支要调 by_parts）。
RCP<const Basic> antiderivative(const RCP<const Basic>& e,
                                const RCP<const Symbol>& x);
RCP<const Basic> by_parts(const RCP<const Basic>& p, const RCP<const Basic>& g,
                          const RCP<const Symbol>& x, int depth);

// 分部积分:∫p·g dx = p·G − ∫(dp/dx)·G, G = ∫g。p 为多项式,dp 常数时一步到位。
RCP<const Basic> by_parts(const RCP<const Basic>& p, const RCP<const Basic>& g,
                          const RCP<const Symbol>& x, int depth) {
    if (depth > 4) return RCP<const Basic>();
    const auto G = antiderivative(g, x);  // ∫g
    if (G.is_null()) return RCP<const Basic>();
    const auto dp = SymEngine::diff(p, x);
    RCP<const Basic> rest;
    if (is_constant(dp, x)) {
        // ∫dp·G = dp·∫G
        const auto GG = antiderivative(G, x);
        if (GG.is_null()) return RCP<const Basic>();
        rest = SymEngine::mul(dp, GG);
    } else {
        rest = by_parts(dp, G, x, depth + 1);  // 递归降次
        if (rest.is_null()) return RCP<const Basic>();
    }
    return SymEngine::sub(SymEngine::mul(p, G), rest);
}

RCP<const Basic> antiderivative(const RCP<const Basic>& e,
                                const RCP<const Symbol>& x) {
    if (SymEngine::eq(*e, *SymEngine::zero)) return SymEngine::integer(0);
    // 常数 → c·x
    if (is_constant(e, x)) return SymEngine::mul(e, x);
    // 裸变量 x → x²/2
    if (SymEngine::is_a<SymEngine::Symbol>(*e))
        return SymEngine::div(SymEngine::pow(x, SymEngine::integer(2)),
                              SymEngine::integer(2));
    // Add → 线性性 ∫(f+g) = ∫f + ∫g
    if (SymEngine::is_a<SymEngine::Add>(*e)) {
        RCP<const Basic> acc = SymEngine::integer(0);
        for (const auto& a : e->get_args()) {
            const auto fa = antiderivative(a, x);
            if (fa.is_null()) return RCP<const Basic>();
            acc = SymEngine::add(acc, fa);
        }
        return acc;
    }
    // Mul → 提出常数因子 ∫cf = c∫f;剩余多项因子做分部积分
    if (SymEngine::is_a<SymEngine::Mul>(*e)) {
        RCP<const Basic> cc = SymEngine::integer(1);
        std::vector<RCP<const Basic>> vf;
        for (const auto& a : e->get_args()) {
            if (is_constant(a, x))
                cc = SymEngine::mul(cc, a);
            else
                vf.push_back(a);
        }
        if (vf.size() == 1) {
            const auto fv = antiderivative(vf[0], x);
            if (fv.is_null()) return RCP<const Basic>();
            return SymEngine::mul(cc, fv);
        }
        if (vf.size() == 2) {
            // x/(k+x²) → ½·ln(k+x²)
            // 自证：d/dx[½ln(k+x²)] = ½·(2x)/(k+x²) = x/(k+x²)
            // 这条走不到下面的"多项式×{sin,cos,exp}"分支（分母不是三角/指数），
            // 也不属于积化和差，所以原来直接落到 null。
            {
                const RCP<const Basic>* num = &vf[0];
                const RCP<const Basic>* den = &vf[1];
                if (!(SymEngine::is_a<SymEngine::Symbol>(**num) &&
                      SymEngine::eq(**num, *x))) {
                    num = &vf[1];
                    den = &vf[0];
                }
                if (SymEngine::is_a<SymEngine::Symbol>(**num) &&
                    SymEngine::eq(**num, *x) &&
                    SymEngine::is_a<SymEngine::Pow>(**den)) {
                    const auto da = (*den)->get_args();
                    if (da.size() == 2 &&
                        SymEngine::is_a<SymEngine::Integer>(*da[1]) &&
                        SymEngine::down_cast<const SymEngine::Integer&>(*da[1])
                                .as_int() == -1 &&
                        is_k_plus_x_squared(da[0], x)) {
                        return SymEngine::mul(
                            cc, SymEngine::div(SymEngine::log(da[0]),
                                               SymEngine::integer(2)));
                    }
                }
            }
            // 1/(u·ln u) → ln(ln u)/m（规范形是两个负幂相乘，见 helper 的注释）
            // 自证：d/dx[ln(ln u)/m] = 1/(u·ln u)
            {
                RCP<const Basic> u, mm;
                if (is_inv_u_times_inv_log_u(vf[0], vf[1], x, u, mm)) {
                    return SymEngine::mul(
                        cc, SymEngine::div(
                                SymEngine::log(SymEngine::log(u)), mm));
                }
            }
            // x^p·ln x（p 常数、p ≠ −1）→ x^(p+1)/(p+1)·ln x − x^(p+1)/(p+1)²
            // 自证：d/dx = x^p·ln x + x^p − x^p = x^p·ln x
            //   p=1 → x·ln x；p=1/2 → √x·ln x（同一条公式）
            //
            // ⚠ 这条**不能**交给 by_parts：那套是按"多项式 p 反复求导直到常数"设计的，
            //    而这里要微分的是 ln x —— dp = 1/x → −1/x² → … 永不终止，
            //    只会一路递归到深度上限、返回 null（实测就是这么失败的）。
            {
                RCP<const Basic> pp;
                const RCP<const Basic>* pw = &vf[0];
                const RCP<const Basic>* lg = &vf[1];
                if (!SymEngine::is_a<SymEngine::Log>(**lg)) {
                    pw = &vf[1];
                    lg = &vf[0];
                }
                if (SymEngine::is_a<SymEngine::Log>(**lg) &&
                    is_x_pow_const(*pw, x, pp)) {
                    const auto pp1 = SymEngine::add(pp, SymEngine::integer(1));
                    const auto xp = SymEngine::pow(x, pp1);
                    return SymEngine::mul(
                        cc,
                        SymEngine::sub(
                            SymEngine::mul(SymEngine::div(xp, pp1), *lg),
                            SymEngine::div(
                                xp, SymEngine::pow(pp1, SymEngine::integer(2)))));
                }
            }
            // e^(a·x+c)·sin(b·x+d) 或 ·cos(b·x+d)：两次分部积分的闭式
            //   ∫e^u·sin v = e^u·(a·sin v − b·cos v)/(a²+b²)
            //   ∫e^u·cos v = e^u·(a·cos v + b·sin v)/(a²+b²)
            // 自证：以 sin 为例，求导 = e^u·a·(a sin−b cos)/D + e^u·(ab cos + b² sin)/D
            //                       = e^u·(a²+b²)·sin/D = e^u·sin v
            {
                RCP<const Basic> ue, ae, ce;
                const RCP<const Basic>* ex = &vf[0];
                const RCP<const Basic>* tr = &vf[1];
                if (!exp_linear_info(*ex, x, ue, ae, ce)) {
                    ex = &vf[1];
                    tr = &vf[0];
                }
                RCP<const Basic> ue2, ae2, ce2;
                if (exp_linear_info(*ex, x, ue2, ae2, ce2) &&
                    (SymEngine::is_a<SymEngine::Sin>(**tr) ||
                     SymEngine::is_a<SymEngine::Cos>(**tr))) {
                    const auto v = (*tr)->get_args()[0];
                    RCP<const Basic> bt, ct;
                    if (is_linear(v, x, bt, ct)) {
                        const bool is_sin = SymEngine::is_a<SymEngine::Sin>(**tr);
                        const auto den = SymEngine::add(
                            SymEngine::pow(ae2, SymEngine::integer(2)),
                            SymEngine::pow(bt, SymEngine::integer(2)));
                        const auto num =
                            is_sin
                                ? SymEngine::sub(
                                      SymEngine::mul(ae2, SymEngine::sin(v)),
                                      SymEngine::mul(bt, SymEngine::cos(v)))
                                : SymEngine::add(
                                      SymEngine::mul(ae2, SymEngine::cos(v)),
                                      SymEngine::mul(bt, SymEngine::sin(v)));
                        return SymEngine::mul(
                            cc, SymEngine::div(SymEngine::mul(*ex, num), den));
                    }
                }
            }
            // 积化和差:两个线性三角因子(sin/cos)
            bool s1, s2;
            RCP<const Basic> u1, u2, m1, b1, m2, b2;
            if (trig_linear_info(vf[0], x, s1, u1, m1, b1) &&
                trig_linear_info(vf[1], x, s2, u2, m2, b2)) {
                const auto r = trig_product_integral(s1, u1, m1, s2, u2, m2, x);
                if (r.is_null()) return RCP<const Basic>();
                return SymEngine::mul(cc, r);
            }
            // p(x)·g(x):p 多项式,g ∈ {sin,cos,exp}
            RCP<const Basic> p, g;
            if (is_poly_in_x(vf[0], x) && is_sin_cos_exp(vf[1])) {
                p = vf[0];
                g = vf[1];
            } else if (is_sin_cos_exp(vf[0]) && is_poly_in_x(vf[1], x)) {
                p = vf[1];
                g = vf[0];
            } else {
                return RCP<const Basic>();
            }
            const auto r = by_parts(p, g, x, 0);
            if (r.is_null()) return RCP<const Basic>();
            return SymEngine::mul(cc, r);
        }
        return RCP<const Basic>();
    }
    // Pow(base, n)
    if (SymEngine::is_a<SymEngine::Pow>(*e)) {
        const auto args = e->get_args();
        const auto& base = args[0];
        const auto& n = args[1];
        // 幂降:sin(u)² → u/(2a) − sin(2u)/(4a);cos(u)² → u/(2a) + sin(2u)/(4a)
        if ((SymEngine::is_a<SymEngine::Sin>(*base) ||
             SymEngine::is_a<SymEngine::Cos>(*base)) &&
            SymEngine::is_a<SymEngine::Integer>(*n) &&
            SymEngine::down_cast<const SymEngine::Integer&>(*n).as_int() == 2) {
            const bool is_sin = SymEngine::is_a<SymEngine::Sin>(*base);
            const auto u = base->get_args()[0];
            RCP<const Basic> m, b;
            if (is_linear(u, x, m, b)) {
                const auto u_term =
                    SymEngine::div(u, SymEngine::mul(SymEngine::integer(2), m));
                const auto sin_term = SymEngine::div(
                    SymEngine::sin(
                        SymEngine::mul(SymEngine::integer(2), u)),
                    SymEngine::mul(SymEngine::integer(4), m));
                return is_sin ? SymEngine::sub(u_term, sin_term)
                              : SymEngine::add(u_term, sin_term);
            }
            return RCP<const Basic>();
        }
        // ── 幂型三角与有理式（本批新增；每条都由 tests 里的"求导自证"保证）──
        const bool n_is_int = SymEngine::is_a<SymEngine::Integer>(*n);
        const long n_val = n_is_int
            ? SymEngine::down_cast<const SymEngine::Integer&>(*n).as_int()
            : 0;
        // tan(u)² = sec(u)²−1 → ∫ = tan(u)/m − x
        // 自证：d/dx[tan(mx+b)/m − x] = sec²(mx+b) − 1 = tan²(mx+b)
        if (n_is_int && n_val == 2 && SymEngine::is_a<SymEngine::Tan>(*base)) {
            const auto u = base->get_args()[0];
            RCP<const Basic> mm, bb;
            if (is_linear(u, x, mm, bb))
                return SymEngine::sub(SymEngine::div(SymEngine::tan(u), mm), x);
        }
        // sin³/​cos³（奇次幂）：∫sin³u = (−cos u + cos³u/3)/m，∫cos³u = (sin u − sin³u/3)/m
        // 自证：d/dx[−cos u + cos³u/3] = sin u − cos²u·sin u = sin u(1−cos²u) = sin³u
        if (n_is_int && n_val == 3 &&
            (SymEngine::is_a<SymEngine::Sin>(*base) ||
             SymEngine::is_a<SymEngine::Cos>(*base))) {
            const bool is_sin = SymEngine::is_a<SymEngine::Sin>(*base);
            const auto u = base->get_args()[0];
            RCP<const Basic> mm, bb;
            if (is_linear(u, x, mm, bb)) {
                // ∫sin³u = (−cos u + cos³u/3)/m
                // ∫cos³u = (+sin u − sin³u/3)/m   ← 注意是**减** sin³u/3
                //   （写错成加号时，本批的求导自证立刻以 maxrel=0.635 抓到 —— 见测试）
                const auto p3 = SymEngine::div(
                    SymEngine::pow(is_sin ? SymEngine::cos(u) : SymEngine::sin(u),
                                   SymEngine::integer(3)),
                    SymEngine::integer(3));
                const auto cube = is_sin ? p3 : SymEngine::neg(p3);
                const auto lead = is_sin ? SymEngine::neg(SymEngine::cos(u))
                                         : SymEngine::sin(u);
                return SymEngine::div(SymEngine::add(lead, cube), mm);
            }
            return RCP<const Basic>();
        }
        // sec³(u)：∫sec³u = ½(sec u·tan u + ln(sec u + tan u))/m
        // 自证：d/dx[½sec u·tan u] = ½(sec u·tan²u + sec³u)；d/dx[½ln(sec u+tan u)] = ½sec u
        //       相加 = ½[sec u(tan²u+1) + sec³u] = ½[sec³u + sec³u] = sec³u
        if (n_is_int && n_val == 3 && SymEngine::is_a<SymEngine::Sec>(*base)) {
            const auto u = base->get_args()[0];
            RCP<const Basic> mm, bb;
            if (is_linear(u, x, mm, bb)) {
                const auto half = SymEngine::div(
                    SymEngine::add(
                        SymEngine::mul(SymEngine::sec(u), SymEngine::tan(u)),
                        SymEngine::log(SymEngine::add(SymEngine::sec(u),
                                                      SymEngine::tan(u)))),
                    SymEngine::integer(2));
                return SymEngine::div(half, mm);
            }
            return RCP<const Basic>();
        }
        // √(1+x²) / √(1−x²)：教科书的 arcsinh / arcsin 闭式
        //   ∫√(1+x²) = (x·√(1+x²) + asinh x)/2
        //   ∫√(1−x²) = (x·√(1−x²) + asin  x)/2
        // 自证：两条求导后分别回到 √(1+x²) / √(1−x²)
        if (SymEngine::eq(*n, *SymEngine::div(SymEngine::integer(1),
                                              SymEngine::integer(2)))) {
            const int kind = one_pm_x_squared(base, x);
            if (kind != 0) {
                const auto root = SymEngine::sqrt(base);
                const auto inner =
                    kind > 0 ? SymEngine::asinh(x) : SymEngine::asin(x);
                return SymEngine::div(
                    SymEngine::add(SymEngine::mul(x, root), inner),
                    SymEngine::integer(2));
            }
        }
        if (n_is_int && n_val == -1) {
            // 1/(c+u²) → atan(u)/m（u 线性、c 常数；含最基础的 1/(1+x²)）
            // 自证：d/dx[atan(u)/m] = 1/(1+u²)（u=mx+b 时链式恰好抵消）
            RCP<const Basic> u, mm;
            if (is_c_plus_square(base, x, u, mm))
                return SymEngine::div(SymEngine::atan(u), mm);
            // 1/(u·ln u) → ln(ln u)/m
            // 自证：d/dx[ln(ln u)/m] = 1/(u·ln u)
            RCP<const Basic> u2, m2;
            if (is_u_log_u(base, x, u2, m2))
                return SymEngine::div(SymEngine::log(SymEngine::log(u2)), m2);
            // 1/(1+x⁴)：教科书的经典闭式（见 antideriv_one_plus_x4 的注释）
            // 自证：求导后回到 1/(1+x⁴)
            if (is_one_plus_x_fourth(base, x))
                return antideriv_one_plus_x4(x);
        }
        RCP<const Basic> m, b;
        if (SymEngine::has_symbol(*base, *x)) {
            // 底数线性:∫(mx+b)^n = (mx+b)^(n+1)/((n+1)·m);n=-1 → ln(mx+b)/m
            // 指数 n 必须不含 x(否则是 x^x 型,非初等)。
            if (!is_linear(base, x, m, b) || !is_constant(n, x))
                return RCP<const Basic>();
            const auto n1 = SymEngine::add(n, SymEngine::integer(1));
            if (SymEngine::eq(*SymEngine::simplify(n1), *SymEngine::zero))
                return SymEngine::div(SymEngine::log(base), m);
            return SymEngine::div(SymEngine::pow(base, n1),
                                  SymEngine::mul(n1, m));
        }
        // 指数型 a^(mx+b):e 底 → e^(mx+b)/m;a^x → a^x/ln a
        if (is_linear(n, x, m, b)) {
            if (SymEngine::eq(*base, *SymEngine::E))
                return SymEngine::div(e, m);
            const bool unit =
                SymEngine::eq(*SymEngine::simplify(
                                  SymEngine::sub(m, SymEngine::integer(1))),
                              *SymEngine::zero) &&
                SymEngine::eq(*SymEngine::simplify(b), *SymEngine::zero);
            if (unit) return SymEngine::div(e, SymEngine::log(base));
        }
        return RCP<const Basic>();
    }
    // 积分表:sin(u) → -cos(u)/m, cos(u) → sin(u)/m(u 线性)
    if (SymEngine::is_a<SymEngine::Sin>(*e)) {
        const auto u = e->get_args()[0];
        RCP<const Basic> m, b;
        if (is_linear(u, x, m, b))
            return SymEngine::div(SymEngine::neg(SymEngine::cos(u)), m);
        return RCP<const Basic>();
    }
    if (SymEngine::is_a<SymEngine::Cos>(*e)) {
        const auto u = e->get_args()[0];
        RCP<const Basic> m, b;
        if (is_linear(u, x, m, b))
            return SymEngine::div(SymEngine::sin(u), m);
        return RCP<const Basic>();
    }
    // tan(u) → −ln(cos(u))/m（u 线性）
    // 自证：d/dx[−ln cos(mx+b)/m] = −(−sin(mx+b)·m)/(m·cos(mx+b)) = tan(mx+b)
    if (SymEngine::is_a<SymEngine::Tan>(*e)) {
        const auto u = e->get_args()[0];
        RCP<const Basic> m, b;
        if (is_linear(u, x, m, b))
            return SymEngine::div(
                SymEngine::neg(SymEngine::log(SymEngine::cos(u))), m);
        return RCP<const Basic>();
    }
    // sec(u) → ln(sec u + tan u)/m（u 线性）
    // 自证：d/dx[ln(sec u + tan u)/m] = (sec u·tan u + sec²u)·m /(m·(sec u+tan u)) = sec u
    if (SymEngine::is_a<SymEngine::Sec>(*e)) {
        const auto u = e->get_args()[0];
        RCP<const Basic> m, b;
        if (is_linear(u, x, m, b))
            return SymEngine::div(
                SymEngine::log(SymEngine::add(SymEngine::sec(u),
                                              SymEngine::tan(u))),
                m);
        return RCP<const Basic>();
    }
    // ln(x) → x·ln(x) - x
    if (SymEngine::is_a<SymEngine::Log>(*e)) {
        const auto u = e->get_args()[0];
        if (SymEngine::eq(*u, *x))
            return SymEngine::sub(SymEngine::mul(x, SymEngine::log(x)), x);
        return RCP<const Basic>();
    }
    // 反三角（自变量正好是 x）：分部积分闭式
    //   ∫atan x = x·atan x − ½ln(1+x²)
    //   ∫acos x = x·acos x − √(1−x²)
    //   ∫asin x = x·asin x + √(1−x²)
    // 自证：三条分别求导后回到 atan x / acos x / asin x（测试里已固化）。
    if (SymEngine::is_a<SymEngine::ATan>(*e) || SymEngine::is_a<SymEngine::ACos>(*e) ||
        SymEngine::is_a<SymEngine::ASin>(*e)) {
        const auto u = e->get_args()[0];
        if (SymEngine::eq(*u, *x)) {
            const auto one = SymEngine::integer(1);
            const auto root = SymEngine::sqrt(
                SymEngine::sub(one, SymEngine::pow(x, SymEngine::integer(2))));
            if (SymEngine::is_a<SymEngine::ATan>(*e))
                return SymEngine::sub(
                    SymEngine::mul(x, SymEngine::atan(x)),
                    SymEngine::div(
                        SymEngine::log(SymEngine::add(
                            one, SymEngine::pow(x, SymEngine::integer(2)))),
                        SymEngine::integer(2)));
            if (SymEngine::is_a<SymEngine::ACos>(*e))
                return SymEngine::sub(SymEngine::mul(x, SymEngine::acos(x)), root);
            return SymEngine::add(SymEngine::mul(x, SymEngine::asin(x)), root);
        }
        return RCP<const Basic>();
    }
    return RCP<const Basic>();
}

// ── 数值积分(符号失败兜底)─────────────────────────────────────────────────

// 通用辛普森(函数值回调)。n 须为偶数。
//
// 端点处若不可求值（如 ∫₀¹ sin(x)/x：x=0 是 0/0），先把端点朝内挪一点点试试：
// 可去奇点处极限存在，挪动 (b−a)·10⁻¹² 对积分的改动远小于任何实用精度，
// 于是 sin(x)/x 能算出真值 Si(1)≈0.946083，而不是报"被积函数无界"（那是误报）。
// 但必须**确认是真可去奇点**：往内挪 δ、10δ、100δ 三点，只有三者彼此接近
// （极限存在）才采用；像 1/x 那样 1e12→1e11→1e10 的量级跳变要如实报无界。
double simpson_fv(const std::function<double(double)>& fv, double a, double b,
                  int n) {
    if (n % 2 != 0) ++n;
    const double h = (b - a) / n;
    const auto safe_fv = [&](double t) -> double {
        double v = 0.0;
        bool ok = false;
        try {
            v = fv(t);
            ok = std::isfinite(v);
        } catch (const std::exception&) {
            ok = false;
        }
        if (ok) return v;
        const double base = (std::max)(1.0, std::abs(b - a));
        double v1 = 0.0, v10 = 0.0, v100 = 0.0;
        bool g1 = false, g10 = false, g100 = false;
        for (int s : {-1, +1}) {
            const double d = base * 1e-12;
            const double t1 = t + s * d, t10 = t + s * 10 * d, t100 = t + s * 100 * d;
            if (t1 <= a || t1 >= b) continue;
            try {
                v1 = fv(t1);
                g1 = std::isfinite(v1);
                v10 = fv(t10);
                g10 = std::isfinite(v10);
                v100 = fv(t100);
                g100 = std::isfinite(v100);
            } catch (const std::exception&) {
                g1 = g10 = g100 = false;
            }
            if (g1 && g10 && g100) break;
        }
        if (g1 && g10 && g100) {
            const double tol = 1e-6 * (std::max)(1.0, std::abs(v1));
            if (std::abs(v1 - v10) <= tol && std::abs(v10 - v100) <= tol) return v1;
        }
        throw std::domain_error(
            "被积函数在区间内无界（存在瑕点）：该处函数值不收敛，"
            "不是常义积分，请用 improper_integral 或分段处理");
    };
    double s = safe_fv(a) + safe_fv(b);
    for (int i = 1; i < n; ++i) {
        const double xi = a + i * h;
        s += (i % 2 == 1) ? 4.0 * safe_fv(xi) : 2.0 * safe_fv(xi);
    }
    return s * h / 3.0;
}

// 表达式求值回调(数值点处无界 → 抛 domain_error)。
std::function<double(double)> make_fv(const RCP<const Basic>& f,
                                      const RCP<const Symbol>& x) {
    return [f, x](double t) -> double {
        const auto sub = f->subs({{x, SymEngine::real_double(t)}});
        const double v = SymEngine::eval_double(*sub);
        if (!std::isfinite(v)) throw std::domain_error("被积函数在区间内无界（存在瑕点）");
        // 数值路径的安全阀：区间内若有极点，采样点会贴近它、给出 1e13 量级的
        // "有限值"，求和后就是一个**看着像答案的错数**（tan(x) 在 [0, π/2] 曾给
        // 8.55e12，真值发散）。常义积分不会出现这种量级，直接如实报错。
        if (std::abs(v) > 1e12)
            throw std::domain_error(
                "被积函数在区间内某点趋于无穷（采样到 |f| > 1e12），"
                "该积分不是常义积分，请用 improper_integral 或分段处理");
        return v;
    };
}

// ∫_a^∞ f(t) dt:按数量级分段(每 10 倍一段),末段贡献趋于 0 视为收敛。
double improper_pos(const std::function<double(double)>& fv, double a) {
    const double c = std::max(a, 1.0);
    double total = 0.0;
    if (c > a) total += simpson_fv(fv, a, c, 400);
    double L = c;
    double last = 0.0;
    for (int k = 0; k < 8; ++k) {
        const double H = L * 10.0;
        const double d = simpson_fv(fv, L, H, 400);
        total += d;
        last = d;
        L = H;
    }
    if (last > 1e-6 * std::max(1.0, std::abs(total)))
        throw std::invalid_argument("积分发散");
    return total;
}

// ── 瑕点检测（常义积分的前提校验）───────────────────────────────────────────
//
// 背景：integrate 走的是「求符号原函数 F，再算 F(b) - F(a)」这条路。这个做法只在
// 被积函数在 [a,b] 上处处有限时才成立。一旦区间**内部**有瑕点，F(b)-F(a) 会跨过
// 一个无穷跳跃，给出一个**错误的有限值**：
//
//     ∫_{-1}^{1} 1/x² dx 真值发散到 +∞，引擎曾返回 -2（F = -1/x，(-1) - 1 = -2）。
//
// 正被积函数给出负的有限值，是最坏的一类错误：用户完全无从察觉。
// 所以这里先把瑕点找出来 —— 收集表达式里的分母，求其在 [a,b] 上的实根
// （奇重根必然变号，用变号 + 二分定位），再用「原函数在该点附近是否有界」
// 判断该处积分是否收敛。后者正是判据本身：
//     F 在瑕点附近有界  ⟺  该侧积分收敛
// 例：∫₀¹ 1/√x 收敛（F = 2√x → 0），∫₀¹ 1/x 发散（F = ln x → -∞），
//     ∫₀¹ ln x dx 收敛 = -1（F = x·ln x - x → 0），全部判对。

void collect_denominators(const RCP<const Basic>& e,
                          std::vector<RCP<const Basic>>& out, int depth = 0) {
    if (depth > 12 || e.is_null()) return;
    const auto& args = e->get_args();
    // 注意：SymEngine 里没有 Div 节点，除法一律表示为 Mul(a, Pow(b, -1))，
    // 所以只要看 Pow 的负指数就覆盖了所有分母（含 1/√x 这种 -1/2 次幂）。
    if (SymEngine::is_a<SymEngine::Pow>(*e) && args.size() == 2) {
        double exp_val = 1.0;
        bool numeric_exp = true;
        try {
            exp_val = SymEngine::eval_double(*args[1]);
        } catch (const std::exception&) {
            numeric_exp = false;  // 符号指数（如 x^y）无法判断，不动
        }
        if (numeric_exp && exp_val < 0.0) out.push_back(args[0]);
    }
    for (const auto& s : args) collect_denominators(s, out, depth + 1);
}

// 分母在 [a,b] 上的实根（只找奇重根：变号 + 二分）。
std::vector<double> denominator_roots(const RCP<const Basic>& D,
                                      const RCP<const Symbol>& x,
                                      double a, double b, int n = 4000) {
    const auto fv = [&](double t) -> double {
        try {
            const auto sub = D->subs({{x, SymEngine::real_double(t)}});
            return SymEngine::eval_double(*sub);
        } catch (const std::exception&) {
            return std::numeric_limits<double>::quiet_NaN();
        }
    };
    std::vector<double> roots;
    // 端点也要查：1/√x 的瑕点就在 x = a 上
    for (double e : {a, b}) {
        const double v = fv(e);
        if (std::isfinite(v) && v == 0.0) roots.push_back(e);
    }
    double prev_x = a, prev_v = fv(a);
    for (int i = 1; i <= n; ++i) {
        const double cur_x = a + (b - a) * static_cast<double>(i) / n;
        const double cur_v = fv(cur_x);
        if (std::isfinite(cur_v) && std::isfinite(prev_v) &&
            ((prev_v < 0.0) != (cur_v < 0.0))) {
            double lo = prev_x, hi = cur_x;
            for (int k = 0; k < 80; ++k) {
                const double mid = 0.5 * (lo + hi);
                const double mv = fv(mid);
                if (!std::isfinite(mv)) break;
                if ((mv < 0.0) == (prev_v < 0.0)) lo = mid; else hi = mid;
            }
            roots.push_back(0.5 * (lo + hi));
        }
        prev_x = cur_x;
        prev_v = cur_v;
    }
    // 二分结果可能落在极靠近 0 的地方（如 -2e-28），报给用户时归整成 0
    for (double& r : roots) {
        const double s = std::max(1.0, std::max(std::abs(a), std::abs(b)));
        if (std::abs(r) < 1e-12 * s) r = 0.0;
    }
    return roots;
}

// 从瑕点 s 的 side 一侧（-1 左 / +1 右）看，|F| 是否随靠近 s 而无界增长。
//
// 判据要点：**不能**要求每一步都按固定倍数增长。对数型发散增长极慢
// （ln 每靠近一个数量级只增加 2.3；相邻两步的比值约 1.17，低于任何"明显增长"
// 的阈值），按每步倍数判会把 ∫₀¹ 1/x dx 误判成收敛 —— 实测会退回端点取值，
// 给出 |ln(1e-14)| = 32.24 这种假值。所以只要求整体单调不减、且末端比首端
// 显著大一截。
bool antiderivative_unbounded_near(const RCP<const Basic>& F,
                                   const RCP<const Symbol>& x,
                                   double s, double scale, int side) {
    double first = 0.0, last = 0.0, prev = 0.0;
    bool have = false, monotone_up = true;
    for (int k = 2; k <= 7; ++k) {
        const double d = scale * std::pow(10.0, -k);
        const double t = s + side * d;
        double v = 0.0;
        try {
            const auto sub = F->subs({{x, SymEngine::real_double(t)}});
            v = std::abs(SymEngine::eval_double(*sub));
        } catch (const std::exception&) {
            return true;  // 求值都失败，按无界处理（保守）
        }
        if (!std::isfinite(v)) return true;
        if (v > 1e12) return true;  // 已经大到不可能是有限可积
        if (have) {
            if (v < prev * (1.0 - 1e-9)) monotone_up = false;
        } else {
            first = v;
            have = true;
        }
        prev = v;
        last = v;
    }
    if (!have) return false;
    return monotone_up && last > first * 1.25 && last > 1.0;
}

std::string fmt_point(double v) {
    char buf[40];
    std::snprintf(buf, sizeof(buf), "%.10g", v);
    return std::string(buf);
}

}  // namespace

std::string integrate_indefinite(const std::string& expr,
                                 const std::string& var) {
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    const auto F = antiderivative(ex, x);
    if (F.is_null()) return "未实现";
    // 分部积分递归会产生未分配的嵌套减法,先 expand 再 simplify 归整。
    return SymEngine::str(
        *SymEngine::simplify(SymEngine::expand(F))) +
           " + C";
}

double integrate_definite(const std::string& expr, const std::string& var,
                          const std::string& a_str, const std::string& b_str) {
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    const Bound a = parse_bound(a_str);
    const Bound b = parse_bound(b_str);
    if (is_inf(a) || is_inf(b))
        throw std::invalid_argument("无穷边界请使用 improper_integral");
    if (!(a.value < b.value))
        throw std::invalid_argument("积分下限须小于上限");

    // 符号原函数 → F(b)-F(a)(精确)。
    const auto F = antiderivative(ex, x);
    if (!F.is_null()) {
        // 先排除瑕点：区间内有发散性瑕点时，F(b)-F(a) 是**错的**
        // （∫_{-1}^{1} 1/x² 曾返回 -2，真值发散到 +∞）。
        // 只有落在 (a,b) 内部的瑕点会破坏"端点取值作差"；
        // 端点上的瑕点要单独判：∫₀¹ 1/√x（收敛）与 ∫₀¹ 1/x（发散）都长在端点上。
        const double scale = std::max(1.0, std::abs(b.value - a.value));
        std::vector<RCP<const Basic>> dens;
        collect_denominators(ex, dens);
        for (const auto& D : dens) {
            for (double s : denominator_roots(D, x, a.value, b.value)) {
                const bool interior = (s > a.value + 1e-12 * scale) &&
                                      (s < b.value - 1e-12 * scale);
                if (interior) {
                    const bool left = antiderivative_unbounded_near(F, x, s, scale, -1);
                    const bool right = antiderivative_unbounded_near(F, x, s, scale, +1);
                    if (left || right)
                        throw std::invalid_argument(
                            "积分发散：区间内部 x = " + fmt_point(s) +
                            " 处是被积函数的瑕点，原函数在该点一侧无界，"
                            "F(b) − F(a) 不代表积分值。请改用 improper_integral "
                            "分段判断收敛性。");
                } else {
                    // 端点瑕点：从区间内侧看原函数是否有界
                    const int side = (std::abs(s - a.value) <= std::abs(s - b.value))
                                         ? +1 : -1;
                    if (antiderivative_unbounded_near(F, x, s, scale, side))
                        throw std::invalid_argument(
                            "积分发散：端点 x = " + fmt_point(s) +
                            " 处是被积函数的瑕点，原函数在该侧无界，"
                            "该积分不是常义积分（请用 improper_integral）。");
                }
            }
        }
        const auto to_sym = [&](const Bound& bb) {
            return bb.kind == BoundKind::Pi ? RCP<const Basic>(SymEngine::pi)
                                            : to_sym_number(bb.value);
        };
        // 首选：符号相减后求值（保留 π 等精确边界、以及大数相消的精度）。
        try {
            const auto Fa = F->subs({{x, to_sym(a)}});
            const auto Fb = F->subs({{x, to_sym(b)}});
            const double v =
                SymEngine::eval_double(*SymEngine::simplify(SymEngine::sub(Fb, Fa)));
            if (std::isfinite(v)) return v;
        } catch (const std::exception&) {
            // 落到下面的端点内侧取值
        }
        // 兜底：端点处原函数"形式上有定义、代入后却是 NaN/inf"。
        // 例：∫₀¹ ln x dx 的 F = x·ln x − x，在 x = 0 处是 0·(−∞)，
        // SymEngine 直接抛 "Not Implemented" —— 一个收敛积分（真值 −1）
        // 却把内部英文错误抛给用户。上面的瑕点检查已确认 F 在该端点附近有界，
        // 所以退到端点内侧取一点即可，误差量级 O(ε·|ln ε|)（ε=1e-14 时约 3e-13）。
        const auto endpoint_value = [&](const Bound& bb) -> double {
            for (int k : {14, 12, 10, 8, 6}) {
                const double eps = scale * std::pow(10.0, -k);
                const bool at_upper = (bb.value == b.value);
                const double t = bb.value + (at_upper ? -eps : eps);
                try {
                    const auto sub = F->subs({{x, SymEngine::real_double(t)}});
                    const double v = SymEngine::eval_double(*sub);
                    if (std::isfinite(v)) return v;
                } catch (const std::exception&) {
                    continue;
                }
            }
            throw std::invalid_argument(
                "原函数在积分限 x = " + fmt_point(bb.value) +
                " 处无法求值（形式上有奇性），这条积分路径暂不支持该积分。");
        };
        return endpoint_value(b) - endpoint_value(a);
    }
    // 回退数值辛普森。
    return simpson_fv(make_fv(ex, x), a.value, b.value, 1000);
}

double integrate_numeric(const std::string& expr, const std::string& var,
                         double a, double b) {
    if (!(a < b)) throw std::invalid_argument("积分下限须小于上限");
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    return simpson_fv(make_fv(ex, x), a, b, 1000);
}

double improper_integral(const std::string& expr, const std::string& var,
                         const std::string& a_str, const std::string& b_str) {
    const auto x = SymEngine::symbol(var);
    const auto ex = SymEngine::parse(expr);
    const Bound a = parse_bound(a_str);
    const Bound b = parse_bound(b_str);
    const bool a_inf = is_inf(a);
    const bool b_inf = is_inf(b);
    if (!a_inf && !b_inf) return integrate_definite(expr, var, a_str, b_str);

    // 符号路径:原函数 F 存在 → F(±R) 截断 + 收敛判断(精确)。
    const auto F = antiderivative(ex, x);
    if (!F.is_null()) {
        const double R = 1e8;
        const double lo = a.kind == BoundKind::Finite
                              ? a.value
                              : (a.kind == BoundKind::PosInf ? R : -R);
        const double hi = b.kind == BoundKind::Finite
                              ? b.value
                              : (b.kind == BoundKind::PosInf ? R : -R);
        const auto evalF = [&](double t) {
            return SymEngine::eval_double(
                *F->subs({{x, SymEngine::real_double(t)}}));
        };
        // 无穷端收敛判定:漂移 |F(10t)-F(t)| 随 t 增大应稳定衰减。
        // 漂移不衰减(≈1/x)或增大(发散)则抛异常。
        const auto inf_ok = [&](double t) {
            const double d1 = std::abs(evalF(t) - evalF(t * 10.0));
            const double d2 = std::abs(evalF(t * 10.0) - evalF(t * 100.0));
            const double scale = std::max(1.0, std::abs(evalF(t)));
            if (d1 <= 1e-9 * scale) return true;  // 漂移可忽略 → 收敛
            if (d2 > d1) return false;            // 漂移增大 → 发散
            if (d2 > 0.9 * d1) return false;      // 几乎不衰减 → 发散
            return true;
        };
        if (b.kind == BoundKind::PosInf && !inf_ok(hi))
            throw std::invalid_argument("积分发散");
        if (b.kind == BoundKind::NegInf && !inf_ok(-hi))
            throw std::invalid_argument("积分发散");
        if (a.kind == BoundKind::PosInf && !inf_ok(lo))
            throw std::invalid_argument("积分发散");
        if (a.kind == BoundKind::NegInf && !inf_ok(-lo))
            throw std::invalid_argument("积分发散");
        return evalF(hi) - evalF(lo);
    }

    // 数值回退。
    const auto fv = make_fv(ex, x);
    const auto fv_neg = [fv](double t) { return fv(-t); };

    if (a.kind == BoundKind::Finite && b.kind == BoundKind::PosInf)
        return improper_pos(fv, a.value);
    if (a.kind == BoundKind::Finite && b.kind == BoundKind::NegInf)
        return -improper_pos(fv_neg, -a.value);
    if (a.kind == BoundKind::NegInf && b.kind == BoundKind::Finite)
        return improper_pos(fv_neg, -b.value);
    if (a.kind == BoundKind::PosInf && b.kind == BoundKind::Finite)
        return -improper_pos(fv, b.value);
    throw std::invalid_argument("两端无穷的反常积分暂不支持");
}

// ── 二重/三重积分 ───────────────────────────────────────────────────────────

// 不定二重积分 ∫∫ f(x,y) dy dx:内层对 y、外层对 x 逐次求原函数。
//
// ⚠ 这里的"积分常数"**不是常数**：对 y 积分时把 x 当常数，那一层的常数是
// **x 的任意函数**；再对 x 积分又引入 **y 的任意函数**。所以通解是
//     H(x,y) + A(x) + B(y)
// 这里把 A、B 显式写出来，而不是含糊地加一个 "+ C" —— 否则用户会以为它和
// 单变量不定积分一样只差一个常数。（单变量的 integrate_indefinite 用 "+ C" 是对的。）
std::string integrate_double_indefinite(const std::string& expr,
                                        const std::string& x,
                                        const std::string& y) {
    const auto xs = SymEngine::symbol(x);
    const auto ys = SymEngine::symbol(y);
    const auto e = SymEngine::parse(expr);
    const auto Fy = antiderivative(e, ys);    // 内层：x 视为常数
    if (Fy.is_null()) return "未实现";
    const auto Fx = antiderivative(Fy, xs);   // 外层：y 视为常数
    if (Fx.is_null()) return "未实现";
    return SymEngine::str(*SymEngine::simplify(SymEngine::expand(Fx))) +
           " + A(" + x + ") + B(" + y + ")";
}

// 不定三重积分 ∫∫∫ f(x,y,z) dz dy dx。
// 逐层引入的任意函数依次是 (x,y)、(x,z)、(y,z) 的函数 —— 同二重的道理，
// 每层的积分常数都是"被当作常数的那两个变量"的任意函数。
std::string integrate_triple_indefinite(const std::string& expr,
                                        const std::string& x,
                                        const std::string& y,
                                        const std::string& z) {
    const auto xs = SymEngine::symbol(x);
    const auto ys = SymEngine::symbol(y);
    const auto zs = SymEngine::symbol(z);
    const auto e = SymEngine::parse(expr);
    const auto Fz = antiderivative(e, zs);
    if (Fz.is_null()) return "未实现";
    const auto Fy = antiderivative(Fz, ys);
    if (Fy.is_null()) return "未实现";
    const auto Fx = antiderivative(Fy, xs);
    if (Fx.is_null()) return "未实现";
    return SymEngine::str(*SymEngine::simplify(SymEngine::expand(Fx))) +
           " + A(" + x + "," + y + ") + B(" + x + "," + z +
           ") + C(" + y + "," + z + ")";
}

double integrate_double(const std::string& expr, const std::string& x,
                        const std::string& y, const std::string& xa,
                        const std::string& xb, const std::string& ya,
                        const std::string& yb) {
    const auto xs = SymEngine::symbol(x);
    const auto ys = SymEngine::symbol(y);
    const auto e = SymEngine::parse(expr);
    const auto exa = SymEngine::parse(xa);
    const auto exb = SymEngine::parse(xb);
    const auto eya = SymEngine::parse(ya);
    const auto eyb = SymEngine::parse(yb);

    // 符号:内层对 y,外层对 x。
    const auto Fy = antiderivative(e, ys);
    if (!Fy.is_null()) {
        const auto g = SymEngine::simplify(SymEngine::sub(
            Fy->subs({{ys, eyb}}), Fy->subs({{ys, eya}})));
        const auto Fx = antiderivative(g, xs);
        if (!Fx.is_null()) {
            const auto v = SymEngine::simplify(SymEngine::sub(
                Fx->subs({{xs, exb}}), Fx->subs({{xs, exa}})));
            return SymEngine::eval_double(*v);
        }
    }

    // 数值回退:外层 Simpson × 内层 Simpson(内层边界可依赖 x)。
    const int N = 200;
    const double xa_v = SymEngine::eval_double(*exa);
    const double xb_v = SymEngine::eval_double(*exb);
    const auto fxy = [&](double xv, double yv) {
        return SymEngine::eval_double(*e->subs(
            {{xs, SymEngine::real_double(xv)}, {ys, SymEngine::real_double(yv)}}));
    };
    const auto inner = [&](double xv) {
        const double ya_v = SymEngine::eval_double(
            *eya->subs({{xs, SymEngine::real_double(xv)}}));
        const double yb_v = SymEngine::eval_double(
            *eyb->subs({{xs, SymEngine::real_double(xv)}}));
        const auto fy = [&](double yv) { return fxy(xv, yv); };
        return simpson_fv(fy, ya_v, yb_v, N);
    };
    return simpson_fv(inner, xa_v, xb_v, N);
}

double integrate_triple(const std::string& expr, const std::string& x,
                        const std::string& y, const std::string& z,
                        const std::string& xa, const std::string& xb,
                        const std::string& ya, const std::string& yb,
                        const std::string& za, const std::string& zb) {
    const auto xs = SymEngine::symbol(x);
    const auto ys = SymEngine::symbol(y);
    const auto zs = SymEngine::symbol(z);
    const auto e = SymEngine::parse(expr);
    const auto exa = SymEngine::parse(xa);
    const auto exb = SymEngine::parse(xb);
    const auto eya = SymEngine::parse(ya);
    const auto eyb = SymEngine::parse(yb);
    const auto eza = SymEngine::parse(za);
    const auto ezb = SymEngine::parse(zb);

    // 符号:对 z、y、x 逐层积分。
    const auto Fz = antiderivative(e, zs);
    if (!Fz.is_null()) {
        const auto g1 = SymEngine::simplify(SymEngine::sub(
            Fz->subs({{zs, ezb}}), Fz->subs({{zs, eza}})));
        const auto Fy = antiderivative(g1, ys);
        if (!Fy.is_null()) {
            const auto g2 = SymEngine::simplify(SymEngine::sub(
                Fy->subs({{ys, eyb}}), Fy->subs({{ys, eya}})));
            const auto Fx = antiderivative(g2, xs);
            if (!Fx.is_null()) {
                const auto v = SymEngine::simplify(SymEngine::sub(
                    Fx->subs({{xs, exb}}), Fx->subs({{xs, exa}})));
                return SymEngine::eval_double(*v);
            }
        }
    }

    // 数值回退:三层嵌套 Simpson。
    const int N = 100;
    const double xa_v = SymEngine::eval_double(*exa);
    const double xb_v = SymEngine::eval_double(*exb);
    const auto fxyz = [&](double xv, double yv, double zv) {
        return SymEngine::eval_double(*e->subs(
            {{xs, SymEngine::real_double(xv)}, {ys, SymEngine::real_double(yv)},
             {zs, SymEngine::real_double(zv)}}));
    };
    const auto inner_y = [&](double xv, double yv) {
        const double za_v = SymEngine::eval_double(*eza->subs(
            {{xs, SymEngine::real_double(xv)}, {ys, SymEngine::real_double(yv)}}));
        const double zb_v = SymEngine::eval_double(*ezb->subs(
            {{xs, SymEngine::real_double(xv)}, {ys, SymEngine::real_double(yv)}}));
        const auto fz = [&](double zv) { return fxyz(xv, yv, zv); };
        return simpson_fv(fz, za_v, zb_v, N);
    };
    const auto inner = [&](double xv) {
        const double ya_v = SymEngine::eval_double(
            *eya->subs({{xs, SymEngine::real_double(xv)}}));
        const double yb_v = SymEngine::eval_double(
            *eyb->subs({{xs, SymEngine::real_double(xv)}}));
        const auto fy = [&](double yv) { return inner_y(xv, yv); };
        return simpson_fv(fy, ya_v, yb_v, N);
    };
    return simpson_fv(inner, xa_v, xb_v, N);
}

// 复定积分:∫_a^b f(x) dx,返回复数(符号原函数;失败抛"未实现")。
std::complex<double> integrate_complex(const std::string& expr,
                                       const std::string& var,
                                       const std::string& a_str,
                                       const std::string& b_str) {
    const auto x = SymEngine::symbol(var);
    const auto e = SymEngine::parse(expr);
    const Bound a = parse_bound(a_str);
    const Bound b = parse_bound(b_str);
    if (is_inf(a) || is_inf(b))
        throw std::invalid_argument("无穷边界暂不支持复数积分");
    const auto F = antiderivative(e, x);
    if (F.is_null())
        throw std::invalid_argument("未实现:无法符号积分该复函数");
    const auto to_sym = [&](const Bound& bb) {
        return bb.kind == BoundKind::Pi ? RCP<const Basic>(SymEngine::pi)
                                        : to_sym_number(bb.value);
    };
    const auto Fa = F->subs({{x, to_sym(a)}});
    const auto Fb = F->subs({{x, to_sym(b)}});
    return SymEngine::eval_complex_double(*Fb) - SymEngine::eval_complex_double(*Fa);
}

}  // namespace mf::calculus
