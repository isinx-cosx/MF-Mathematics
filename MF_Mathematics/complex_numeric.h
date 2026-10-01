// complex_numeric.h — 复值表达式的数值求值（SymEngine::eval_complex_double 的补充）
//
// 为什么需要它：复平面绘图要在整个复网格上求 f(z)。实测 SymEngine 的
// eval_complex_double 覆盖范围是**初等函数**（加减乘除幂、exp/log/sqrt/abs、
// 三角与双曲及其反函数），而原版（PyQt + sympy/mpmath）明确支持的
//   zeta(z)、gamma(z)、erf(z)、erfc(z)
// 里：
//   · zeta(2) 能算，但 zeta(1+14.13i) 直接 "Not Implemented"
//   · gamma(0.5) 能算，但 gamma(1+i) 同样 "Not Implemented"
//   · erf / erfc 连实数都不支持
// 所以这几支必须自己实现。引擎里已经有复数 Γ（Lanczos + 反射公式）与 ζ
// （级数 / Euler–Maclaurin / 负整数用伯努利数），这里直接用它们，不重复造。
//
// 设计取舍：
//   · 数值叶子（Integer / Rational / RealDouble / Complex / 常数 π、e）统一交给
//     eval_complex_double，避免自己维护一份常数表。
//   · 函数按 **名字** 分派（FunctionSymbol::get_name()），而不是给每个函数类写一个
//     is_a<> 分支——后者漏一个就静默算错，前者漏了会明确报"不支持"。
//   · 算不出来一律返回 NaN 并把函数名记进 unsupported，由调用方决定是报错还是画成空白。
//     **绝不返回一个看起来正常的错值**（本项目一贯的规矩）。
//   · 整数幂走连乘：z^2 用 z*z 比 std::pow(z,2.0) 精确，且快。

#pragma once

#include <cmath>
#include <complex>
#include <string>

#include <symengine/basic.h>
#include <symengine/complex_double.h>
#include <symengine/constants.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/number.h>
#include <symengine/symbol.h>

#include "complex_analysis/ca_internal.h"
#include "complex_analysis/zeta.h"

namespace mf::cnum {

using cd = std::complex<double>;

inline constexpr double kPi = 3.14159265358979323846;

inline bool finite_c(const cd& v) {
    return std::isfinite(v.real()) && std::isfinite(v.imag());
}

/** 求值上下文：unsupported 用来记住第一个不认识的东西，便于报出可读的原因。 */
struct Ctx {
    std::string unsupported;
    int depth = 0;
    // 函数名缓存：节点指针 → 名字。表达式树在整个网格求值期间是同一棵树，
    // 所以名字只需算一次；而 str() 不便宜，绝不能每个点都调。
    std::map<const SymEngine::Basic*, std::string> nameCache;
};

/** 取函数名（带缓存）。 */
inline const std::string& fn_name_cached(const SymEngine::Basic& b, Ctx& ctx) {
    auto it = ctx.nameCache.find(&b);
    if (it != ctx.nameCache.end()) return it->second;
    const std::string s = SymEngine::str(b);
    const auto p = s.find('(');
    return ctx.nameCache.emplace(&b, p == std::string::npos ? s : s.substr(0, p))
        .first->second;
}

// ── 复数 erf / erfc ────────────────────────────────────────────────────────
//
// erf 是整函数（没有分支切割问题），但 C++ 标准库只有实数版。两段式：
//   |z| ≤ 4：泰勒级数 Σ (-1)^n z^(2n+1) / (n!(2n+1))，收敛快且稳定；
//   |z| > 4：渐近展开 1 - e^(−z²)/(z√π) · Σ (-1)^k (2k−1)!!/(2z²)^k，
//            它在右半平面才成立，所以先用奇函数性质 erf(−z) = −erf(z) 把
//            Re(z) < 0 折到右半平面。
// 精度：|z| ≤ 4 约 1e-15，|z| 更大时约 1e-8（渐近级数本质是发散的，取最小项截断）。
// 画图用途绰绰有余；文档里如实写明，不假装是全精度实现。

inline cd erf_complex(const cd& z) {
    if (std::abs(z) > 4.0) {
        if (z.real() < 0.0) return -erf_complex(-z);
        const cd z2 = z * z;
        cd sum(1.0, 0.0), term(1.0, 0.0);
        double prev = std::abs(term);
        for (int k = 1; k <= 60; ++k) {
            term *= -(2.0 * k - 1.0) / (2.0 * z2);
            const double cur = std::abs(term);
            // 渐近级数是发散的：项开始变大就说明已经越过最佳截断点，立刻停
            if (cur > prev) break;
            sum += term;
            prev = cur;
            if (cur < 1e-18 * std::abs(sum)) break;
        }
        return 1.0 - std::exp(-z2) * sum / (z * std::sqrt(kPi));
    }
    cd s(0.0, 0.0), t = z;
    for (int n = 0; n < 250; ++n) {
        s += t / (2.0 * n + 1.0);
        t *= -z * z / (n + 1.0);
        if (std::abs(t) < 1e-20) break;
    }
    return 2.0 / std::sqrt(kPi) * s;
}

inline cd erfc_complex(const cd& z) { return 1.0 - erf_complex(z); }

/** 复数 ζ：整数与非正整数用伯努利数、Re>1 用级数、其余 Euler–Maclaurin（引擎已实现）。 */
inline cd zeta_complex(const cd& s) {
    if (std::abs(s - 1.0) < 1e-12) return cd(std::numeric_limits<double>::quiet_NaN(), 0.0);
    return mf::complex_analysis::analytic_continuation_zeta(s);
}

// ── 递归求值 ──────────────────────────────────────────────────────────────

inline cd eval_node(const SymEngine::Basic& b, const cd& z, Ctx& ctx);

/** 出错时用来报告"是哪个函数算不出来"：str() 形如 "besselj(0, z)"，取括号前那段。 */
inline std::string fn_name_of(const SymEngine::Basic& b) {
    const std::string s = SymEngine::str(b);
    const auto p = s.find('(');
    return p == std::string::npos ? s : s.substr(0, p);
}

inline cd eval_node(const SymEngine::Basic& b, const cd& z, Ctx& ctx) {
    using namespace SymEngine;
    const cd NaN = cd(std::numeric_limits<double>::quiet_NaN(), 0.0);
    if (ctx.depth > 200) return NaN;             // 表达式深得离谱：直接放弃，别爆栈
    ++ctx.depth;
    struct Guard { Ctx& c; ~Guard() { --c.depth; } } guard{ctx};

    // ① 数值叶子（整数 / 有理数 / 实浮点 / 复数）与常数（π、e、欧拉常数）：
    //    交给 SymEngine 处理，省得自己维护一份常数表
    if (is_a_Number(b) || is_a<Constant>(b)) {
        try {
            return SymEngine::eval_complex_double(b);
        } catch (...) {
            return NaN;
        }
    }
    // ② 符号：z 是自变量；I 当虚数单位；其它符号（未绑定参数）算不出来
    if (is_a<Symbol>(b)) {
        const std::string n = down_cast<const Symbol&>(b).get_name();
        if (n == "z") return z;
        if (n == "I" || n == "i") return cd(0.0, 1.0);
        if (ctx.unsupported.empty()) ctx.unsupported = "未绑定的符号 " + n;
        return NaN;
    }
    // ③ 加减：逐项求和
    if (is_a<Add>(b)) {
        cd s(0.0, 0.0);
        for (const auto& a : b.get_args()) s += eval_node(*a, z, ctx);
        return s;
    }
    // ④ 乘：逐项连乘
    if (is_a<Mul>(b)) {
        cd p(1.0, 0.0);
        for (const auto& a : b.get_args()) p *= eval_node(*a, z, ctx);
        return p;
    }
    // ⑤ 幂：整数次幂走连乘（z^2 比 pow(z,2.0) 准且快），其余用 std::pow
    if (is_a<Pow>(b)) {
        const auto& pw = down_cast<const Pow&>(b);
        const cd base = eval_node(*pw.get_base(), z, ctx);
        const cd ex = eval_node(*pw.get_exp(), z, ctx);
        if (std::abs(ex.imag()) < 1e-15) {
            const double e = ex.real();
            if (std::abs(e - std::round(e)) < 1e-12 && std::abs(e) <= 64.0) {
                long long n = (long long)std::llround(e);
                if (n == 0) return cd(1.0, 0.0);
                cd r(1.0, 0.0), m = base;
                long long k = n < 0 ? -n : n;
                while (k > 0) {
                    if (k & 1) r *= m;
                    m *= m;
                    k >>= 1;
                }
                return n < 0 ? cd(1.0, 0.0) / r : r;
            }
        }
        return std::pow(base, ex);
    }
    // ⑥ 函数节点（sin / log / abs / gamma / zeta / erf …）
    //
    // 这里**不能**用 is_a<FunctionSymbol> 来判断：SymEngine 的层级是
    //   Function → OneArgFunction → Sin/Log/Gamma/…
    //   Function → MultiArgFunction → FunctionSymbol   （FunctionSymbol 只用于自定义的 f(x)）
    // 所以 is_a<FunctionSymbol> 对 Sin/Log/Zeta 一律**匹配不上**（编译能过，运行时恒 false，
    // 这个坑我踩了：sin/log/zeta 全被当成未知节点）。改成按"有没有实参"判断。
    //
    // 分工：
    //   · zeta / gamma / erf / erfc → 用引擎自己的复数实现（SymEngine 只支持实参数）
    //   · 其余（三角、双曲、exp、log、abs…）→ 先把实参数值化替换掉，
    //     再交回 SymEngine 的 eval_complex_double 算——它对初等函数是准的，
    //     没必要自己再实现一遍（自己实现就要自己担分支切割的错）。
    if (!b.get_args().empty() && !is_a<Add>(b) && !is_a<Mul>(b) && !is_a<Pow>(b)) {
        const auto args = b.get_args();

        if (args.size() == 1) {
            const cd a = eval_node(*args[0], z, ctx);
            if (!finite_c(a)) return NaN;
            // 按**名字**分派，不按类。
            //
            // 踩过的两个坑决定了这里只能按名字走：
            //   ① is_a<FunctionSymbol> 编译能过但运行时对 Sin/Log/Zeta 一律 false
            //      （FunctionSymbol 只用于自定义的 f(x)，实际函数走 OneArgFunction 那一支）；
            //   ② SymEngine 的 Zeta 继承 TwoArgFunction（它是 Hurwitz ζ，两个参数），
            //      于是单参数的 zeta(z) 既不是 Zeta、又不是 FunctionSymbol ——
            //      两条路都不匹配，最后被当成"未知函数"报不支持。
            // 名字靠 fn_name_cached 取（整棵树只算一次）。
            const std::string& nm = fn_name_cached(b, ctx);
            if (nm == "gamma") return mf::complex_analysis::detail::gamma_complex(a);
            if (nm == "zeta") return zeta_complex(a);
            if (nm == "erf") return erf_complex(a);
            if (nm == "erfc") return erfc_complex(a);
            // 其余一元函数：把实参换成数值再让 SymEngine 算
            std::map<RCP<const Basic>, RCP<const Basic>, RCPBasicKeyLess> m;
            m[args[0]] = complex_double(a);
            try {
                return SymEngine::eval_complex_double(*b.subs(m));
            } catch (...) {
                if (ctx.unsupported.empty()) ctx.unsupported = "不支持复参数的函数 " + fn_name_of(b);
                return NaN;
            }
        }

        // 两参数的 Zeta 是 Hurwitz ζ(s, a)。a=1 就是 Riemann ζ(s)，能用；
        // 其余 a 引擎没实现，明确报出来（而不是拿 a=1 的结果糊弄）。
        if (is_a<Zeta>(b) && args.size() == 2) {
            const cd s = eval_node(*args[0], z, ctx);
            const cd a2 = eval_node(*args[1], z, ctx);
            if (!finite_c(s) || !finite_c(a2)) return NaN;
            if (std::abs(a2 - 1.0) < 1e-12) return zeta_complex(s);
            if (ctx.unsupported.empty()) ctx.unsupported = "暂不支持 Hurwitz ζ(s, a)（a≠1）";
            return NaN;
        }

        // 多参数函数：全部实参先数值化，再交给 SymEngine
        std::map<RCP<const Basic>, RCP<const Basic>, RCPBasicKeyLess> m;
        for (const auto& a : args) {
            const cd v = eval_node(*a, z, ctx);
            if (!finite_c(v)) return NaN;
            m[a] = complex_double(v);
        }
        try {
            return SymEngine::eval_complex_double(*b.subs(m));
        } catch (...) {
            if (ctx.unsupported.empty()) ctx.unsupported = "不支持复参数的函数 " + fn_name_of(b);
            return NaN;
        }
    }
    // ⑦ 兜底：交给 SymEngine 试一次；它认了就当数值用
    try {
        return SymEngine::eval_complex_double(b);
    } catch (...) {
        if (ctx.unsupported.empty()) ctx.unsupported = "无法求值的表达式节点：" + fn_name_of(b);
        return NaN;
    }
}

}  // namespace mf::cnum
