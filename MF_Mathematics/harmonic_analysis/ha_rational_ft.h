// ha_rational_ft.h — 有理函数的解析傅里叶变换(留数闭式, 仅头文件)。
//
// 为什么需要它(tests/accuracy/cases_harmonic_analysis.py 里 poisson_summation 的失败项):
//   F(ξ) = ∫_{-∞}^{∞} f(x)·e^{-2πiξx} dx(普通频率)。对 f = 1/(1+x²) 这类只有代数
//   衰减的函数, ha_numeric.h 的两条数值路径都拿不到高频项:
//     * 双指数(tanh-sinh)路径在 ω>0 时分辨不了振荡, 自称未收敛被拒;
//     * 面板 + 渐近尾路径对 1/R 的尾巴测不出收敛, 且几何面板外推会把结果压到
//       一个 ~1e-6 的"平台"上 —— 实测 F(1)=4.92e-3(真值 5.867e-3)、
//       F(2) 连符号都是错的, 于是 (1/a)ΣF(k/a) 只到 1.8e-3 的相对精度。
//
//   有理函数没有这个困难: f = P/Q 的奇点恰好是 Q 的全部复根, 全在实轴之外,
//   于是可以**精确闭式**地算:
//
//       F(ξ) = -2πi·Σ_{Im p<0} Res_{z=p}[ f(z)·e^{-2πiξz} ]      (ξ ≥ 0)
//       F(ξ) = +2πi·Σ_{Im p>0} Res_{z=p}[ f(z)·e^{-2πiξz} ]      (ξ < 0)
//
//   推导: ξ>0 时 e^{-2πiξz} 在下半平面 z=Re^{iθ}(θ<0) 上按 e^{2πξR sinθ} 指数衰减,
//   取实轴 + 下半大圆弧的顺时针围道, 弧上被积函数一致趋零 ⇒ 只剩极点留数, 符号 -2πi。
//   若 deg Q = deg P + 1(如 x/(1+x²): 条件收敛而非绝对可积), ξ≠0 时弧仍指数衰减,
//   但 **ξ=0 时弧不退**: f(z) ~ c/z(c = lead P / lead Q), 弧上 f(z)dz ~ c·i·dθ,
//   于是 ∫_弧 = -iπc, 实轴的 Cauchy 主值得加回 +iπc:
//
//       F(0) = -2πi·Σ_{Im p<0} Res + iπ·c     (deg Q = deg P + 1; deg Q ≥ deg P+2 时 c=0)
//
//   deg Q ≤ deg P(积分发散)一律拒绝。
//
//   实现: Q 的复根用 Durand–Kerner(Weierstrass)同时迭代 + 牛顿抛光; 单极点留数
//   直接 c₁ = P(p)/Q'(p)。这样得到的 (p_j, c_j) 必须能把 f 逐点重现:
//
//       Σ_j c_j/(x - p_j)  ==  f(x)      (若干实点上相对残差 < 1e-9)
//
//   这一条复核把"根找错 / 漏根 / 重根(P、Q 不互素或真重极点) / 系数提取出错"全部
//   拦下来; deg Q = deg P+1 时另用 Σ_j c_j == c(留数和定理)核对弧系数。
//   任何一条不满足就如实返回 ok=false, 由调用方回落到原来的数值路径。
//   绝不把没验过的闭式当成结果。
//
// 局限(如实声明): 只处理实系数有理函数且 Q 的根互异、离实轴不近(见下方阈值);
//   exp(-|x|)、sin(x)/(1+x²) 等非有理式仍走数值分支。
#pragma once

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstddef>
#include <vector>

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/integer.h>
#include <symengine/mul.h>
#include <symengine/pow.h>
#include <symengine/symbol.h>
#include <symengine/visitor.h>

#include "ha_internal.h"

namespace mf::harmonic_analysis::detail {

using SymEngine::Basic;
using SymEngine::RCP;
using SymEngine::Symbol;

// ── x 的多项式判定(只允许非负整数次幂, 分母由 split_rational 单独处理) ───────
inline bool is_poly_in_x(const RCP<const Basic>& e, const RCP<const Symbol>& x) {
    using namespace SymEngine;
    if (!has_symbol(*e, *x)) return true;   // 常数(含 π、有理数)
    if (is_a<Symbol>(*e)) return true;
    if (is_a<Add>(*e) || is_a<Mul>(*e)) {
        for (const auto& t : e->get_args())
            if (!is_poly_in_x(t, x)) return false;
        return true;
    }
    if (is_a<Pow>(*e)) {
        const auto args = e->get_args();
        if (has_symbol(*args[1], *x)) return false;         // x 在指数上
        if (!is_a<Integer>(*args[1])) return false;          // x^{1/2} 等
        if (down_cast<const Integer&>(*args[1]).as_int() < 0) return false;
        return is_poly_in_x(args[0], x);
    }
    return false;   // sin/exp/… 含 x ⇒ 非多项式
}

// ── 把表达式拆成 num/den(对 x 的有理式); 非有理式返回 false ─────────────────
inline bool split_rational(const RCP<const Basic>& e, const RCP<const Symbol>& x,
                           RCP<const Basic>& num, RCP<const Basic>& den) {
    using namespace SymEngine;
    if (!has_symbol(*e, *x)) { num = e; den = one; return true; }
    if (is_a<Symbol>(*e)) { num = e; den = one; return true; }   // 就是 x 本身
    if (is_a<Add>(*e)) {
        RCP<const Basic> n = zero, d = one;
        for (const auto& t : e->get_args()) {
            RCP<const Basic> tn, td;
            if (!split_rational(t, x, tn, td)) return false;
            n = add(mul(n, td), mul(tn, d));   // n/1 起步, 通分
            d = mul(d, td);
        }
        num = n; den = d; return true;
    }
    if (is_a<Mul>(*e)) {
        RCP<const Basic> n = one, d = one;
        for (const auto& t : e->get_args()) {
            RCP<const Basic> tn, td;
            if (!split_rational(t, x, tn, td)) return false;
            n = mul(n, tn); d = mul(d, td);
        }
        num = n; den = d; return true;
    }
    if (is_a<Pow>(*e)) {
        const auto args = e->get_args();
        if (has_symbol(*args[1], *x)) return false;
        if (!is_a<Integer>(*args[1])) return false;
        const long k = down_cast<const Integer&>(*args[1]).as_int();
        if (!is_poly_in_x(args[0], x)) return false;
        if (k >= 0) { num = e; den = one; return true; }
        num = one;
        den = pow(args[0], integer(-k));
        return true;
    }
    return false;
}

// ── 展开成 x 的系数(实系数; 任何非数值系数或缺项即失败) ────────────────────
inline bool poly_coeffs(const RCP<const Basic>& p, const RCP<const Symbol>& x,
                        std::vector<double>& c, int max_deg = 64) {
    using namespace SymEngine;
    RCP<const Basic> pe;
    try {
        pe = expand(p);
    } catch (...) {
        return false;
    }
    c.assign(static_cast<std::size_t>(max_deg) + 1, 0.0);
    int last = -1;
    for (int i = 0; i <= max_deg; ++i) {
        RCP<const Basic> ci;
        try {
            ci = coeff(*pe, *x, *integer(i));
        } catch (...) {
            return false;
        }
        double v;
        try {
            v = eval_double(*ci);   // 含 x ⇒ 抛异常(说明不是 x 的多项式)
        } catch (...) {
            return false;
        }
        if (!std::isfinite(v)) return false;
        c[static_cast<std::size_t>(i)] = v;
        if (v != 0.0) last = i;
    }
    if (last < 0) return false;          // 恒零多项式
    if (last >= max_deg) return false;   // 次数超过上限: 拒绝而不是静默截断
    c.resize(static_cast<std::size_t>(last) + 1);
    return true;
}

// ── 复系数多项式求值(Horner)与导数 ─────────────────────────────────────────
inline std::complex<double> cpoly_eval(const std::vector<double>& c,
                                       const std::complex<double>& z) {
    std::complex<double> s(0.0, 0.0);
    for (int i = static_cast<int>(c.size()) - 1; i >= 0; --i)
        s = s * z + c[static_cast<std::size_t>(i)];
    return s;
}

inline std::complex<double> cpoly_deriv_eval(const std::vector<double>& c,
                                             const std::complex<double>& z) {
    std::complex<double> s(0.0, 0.0);
    for (int i = static_cast<int>(c.size()) - 1; i >= 1; --i)
        s = s * z + static_cast<double>(i) * c[static_cast<std::size_t>(i)];
    return s;
}

// ── Durand–Kerner(Weierstrass)同时迭代求全部复根, 再逐根牛顿抛光 ────────────
inline bool poly_roots_complex(const std::vector<double>& c,
                               std::vector<std::complex<double>>& roots) {
    int n = static_cast<int>(c.size()) - 1;
    while (n > 0 && c[static_cast<std::size_t>(n)] == 0.0) --n;   // 去零首项
    if (n < 1) return false;
    const double lead = c[static_cast<std::size_t>(n)];
    if (lead == 0.0 || !std::isfinite(lead)) return false;

    roots.assign(static_cast<std::size_t>(n), std::complex<double>(1.0, 0.0));
    {
        std::complex<double> pw(1.0, 0.0);
        const std::complex<double> seed(0.4, 0.9);   // 经典种子: 互异且不共轭对称
        for (int i = 0; i < n; ++i) {
            roots[static_cast<std::size_t>(i)] = pw;
            pw *= seed;
        }
    }
    for (int it = 0; it < 300; ++it) {
        double mxd = 0.0;
        for (int i = 0; i < n; ++i) {
            std::complex<double> den(1.0, 0.0);
            for (int j = 0; j < n; ++j)
                if (j != i)
                    den *= (roots[static_cast<std::size_t>(i)] -
                            roots[static_cast<std::size_t>(j)]);
            if (std::abs(den) < 1e-300) {   // 迭代点重合: 推开重来
                roots[static_cast<std::size_t>(i)] +=
                    std::complex<double>(1e-4, 1e-4);
                mxd = 1.0;
                continue;
            }
            const std::complex<double> d =
                cpoly_eval(c, roots[static_cast<std::size_t>(i)]) / (lead * den);
            roots[static_cast<std::size_t>(i)] -= d;
            mxd = (std::max)(mxd, std::abs(d));
        }
        if (mxd < 1e-16 * (1.0 + std::abs(roots[0]))) break;
    }
    for (int it = 0; it < 60; ++it) {       // 单根二次收敛; 重根由复核兜底
        for (auto& z : roots) {
            const std::complex<double> d = cpoly_deriv_eval(c, z);
            if (std::abs(d) < 1e-300) continue;
            z -= cpoly_eval(c, z) / d;
        }
    }
    for (auto& z : roots)
        if (!std::isfinite(z.real()) || !std::isfinite(z.imag())) return false;
    return true;
}

// ── 可用的有理函数傅里叶变换(极点 + 留数, 已通过复核) ──────────────────────
struct RationalFT {
    bool ok = false;
    std::vector<std::complex<double>> poles;   // Q 的全部互异单根
    std::vector<std::complex<double>> res;     // Res_{z=p} f(z) = c₁
    double arc_coef = 0.0;   // c = lim_{z→∞} z·f(z): deg Q = deg P+1 时非零, 用于 ξ=0
    double check_residual = 0.0;               // 部分分式复核的实测最大相对残差
    int check_points = 0;
    double axis_gap = 0.0;                     // min_j |Im p_j|(离实轴距离)

    // F(ξ) = ∫f(x)e^{-2πiξx}dx, 留数闭式(ξ=0 时按需加回大弧的 Cauchy 主值修正)。
    std::complex<double> eval(double xi) const {
        std::complex<double> acc(0.0, 0.0);
        for (std::size_t j = 0; j < poles.size(); ++j) {
            const std::complex<double> p = poles[j];
            if (xi >= 0.0) {
                if (p.imag() >= 0.0) continue;   // 下半平面(ξ≥0 的收敛半平面)
            } else {
                if (p.imag() <= 0.0) continue;   // 上半平面(ξ<0)
            }
            acc += res[j] *
                   std::exp(std::complex<double>(0.0, -2.0 * kPi * xi) * p);
        }
        const double sgn = (xi >= 0.0) ? -1.0 : 1.0;
        std::complex<double> v = std::complex<double>(0.0, sgn * 2.0 * kPi) * acc;
        // ξ=0 时下半大弧贡献 -iπc, 主值要加回 +iπc(deg Q ≥ deg P+2 时 c=0)。
        if (xi == 0.0) v += std::complex<double>(0.0, kPi * arc_coef);
        return v;
    }
};

namespace rational_ft_impl {

// 复核用: 部分分式 Σ c_j/(x - p_j) 是否逐点重现 f(x)。
// 通过时把实测最大相对残差与取样点数回填给调用方(用于如实报告)。
inline bool verify(const RationalFT& r, const RCP<const Basic>& e,
                   const RCP<const Symbol>& x, double scale, double& worst_out,
                   int& points_out) {
    (void)scale;   // 判据本身是尺度无关的(用相对相消因子), 保留形参便于将来加尺度门限
    static const double cand[12] = {0.3721,  -1.4142, 1.6180,  -2.7183,
                                    3.1416,  -4.6692, 5.5772,  -6.2832,
                                    7.3891,  -8.5397, 9.8696,  -11.0};
    // 函数量级(判据的分母下限用)。
    double ftyp = 0.0;
    double fv[12];
    for (int i = 0; i < 12; ++i) {
        fv[i] = eval_double_expr(e, x, cand[i]);
        ftyp = (std::max)(ftyp, std::abs(fv[i]));
    }
    if (!(ftyp > 0.0)) return false;

    double worst = 0.0;
    int checked = 0;
    for (int i = 0; i < 12 && checked < 6; ++i) {
        const double t = cand[i];
        std::complex<double> sv(0.0, 0.0);
        double abs_terms = 0.0;
        for (std::size_t j = 0; j < r.poles.size(); ++j) {
            const std::complex<double> d = t - r.poles[j];
            if (std::abs(d) < 1e-300) { abs_terms = kInfD; break; }
            sv += r.res[j] / d;
            abs_terms += std::abs(r.res[j]) / std::abs(d);
        }
        // 相消太狠的取样点不算证据(避免拿舍入噪声当"复核通过")。
        const double denom = (std::max)(std::abs(fv[i]), 0.02 * ftyp);
        if (!std::isfinite(abs_terms) || abs_terms > 1e4 * denom) continue;
        worst = (std::max)(worst, std::abs(sv - fv[i]) / denom);
        ++checked;
    }
    if (checked < 3) return false;
    worst_out = worst;
    points_out = checked;
    return worst < 1e-9;
}

}  // namespace rational_ft_impl

inline RationalFT prepare_rational_ft_impl(const RCP<const Basic>& e,
                                           const RCP<const Symbol>& x) {
    RationalFT r;
    RCP<const Basic> num, den;
    if (!split_rational(e, x, num, den)) return r;

    std::vector<double> pc, qc;
    if (!poly_coeffs(num, x, pc)) return r;
    if (!poly_coeffs(den, x, qc)) return r;
    const int dp = static_cast<int>(pc.size()) - 1;
    const int dq = static_cast<int>(qc.size()) - 1;
    // deg Q < deg P + 1 ⇒ 积分发散; deg Q = deg P + 1 只条件收敛, ξ=0 需主值修正。
    if (dq < dp + 1) return r;
    const bool conditional = (dq == dp + 1);

    std::vector<std::complex<double>> roots;
    if (!poly_roots_complex(qc, roots)) return r;

    double scale = 1.0;
    for (const auto& z : roots) scale = (std::max)(scale, std::abs(z));

    // 极点必须离实轴足够远(否则积分本身发散/被极点邻域支配)。
    r.axis_gap = kInfD;
    for (const auto& z : roots) r.axis_gap = (std::min)(r.axis_gap, std::abs(z.imag()));
    if (!(r.axis_gap > 1e-9 * scale)) return r;
    // 只支持互异单极点(重极点需要 1/(z-p)^n 项, 本闭式不适用)。
    for (std::size_t i = 0; i < roots.size(); ++i)
        for (std::size_t j = i + 1; j < roots.size(); ++j)
            if (std::abs(roots[i] - roots[j]) < 1e-6 * scale) return r;

    r.poles = roots;
    r.res.reserve(roots.size());
    for (const auto& p : roots) {
        const std::complex<double> qd = cpoly_deriv_eval(qc, p);
        if (std::abs(qd) < 1e-300) return RationalFT();
        r.res.push_back(cpoly_eval(pc, p) / qd);   // c₁ = P(p)/Q'(p)
    }
    for (const auto& c : r.res) {
        if (!std::isfinite(c.real()) || !std::isfinite(c.imag())) return RationalFT();
    }

    if (conditional) {
        // 弧系数 c = lim z·f(z) = lead P / lead Q; 留数和定理 Σ_j c_j = c 必须成立,
        // 否则弧修正靠不住 ⇒ 拒绝。
        r.arc_coef = pc[static_cast<std::size_t>(dp)] / qc[static_cast<std::size_t>(dq)];
        std::complex<double> sres(0.0, 0.0);
        for (const auto& c : r.res) sres += c;
        if (!(std::abs(sres - r.arc_coef) <=
              1e-9 * (std::max)(1.0, std::abs(r.arc_coef))))
            return RationalFT();
    }

    if (!rational_ft_impl::verify(r, e, x, scale, r.check_residual,
                                  r.check_points))
        return RationalFT();
    r.ok = true;
    return r;
}

// 对外入口: 任何 SymEngine 异常都如实退化成"不适用"(ok=false)。
inline RationalFT prepare_rational_ft(const RCP<const Basic>& e,
                                      const RCP<const Symbol>& x) {
    try {
        return prepare_rational_ft_impl(e, x);
    } catch (...) {
        return RationalFT();
    }
}

}  // namespace mf::harmonic_analysis::detail
