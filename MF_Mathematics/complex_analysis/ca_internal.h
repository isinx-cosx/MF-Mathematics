// ca_internal.h — complex_analysis 包共享辅助(仅头文件)。
//
// 提供:复值表达式求值、复辛普森、复伽马(Lanczos)、ζ 级数/η 延拓。

#pragma once

#include <cmath>
#include <complex>
#include <functional>
#include <stdexcept>
#include <string>

#include <symengine/basic.h>
#include <symengine/complex_double.h>
#include <symengine/derivative.h>
#include <symengine/eval_double.h>
#include <symengine/parser.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include <limits>

namespace mf::complex_analysis::detail {

inline constexpr double kPi = 3.14159265358979323846;
inline constexpr double kTwoPi = 6.283185307179586476925286766559;

// 表达式在复点 z 处的值(纯复表达式)。失败抛异常。
inline std::complex<double> eval_complex(const std::string& expr,
                                         std::complex<double> z) {
    const auto zs = SymEngine::symbol("z");
    const auto e = SymEngine::parse(expr);
    const auto sub = e->subs({{zs, SymEngine::complex_double(z)}});
    return SymEngine::eval_complex_double(*sub);
}

// 表达式求导后再在复点求值。
inline std::complex<double> eval_diff_complex(const std::string& expr,
                                              std::complex<double> z) {
    const auto zs = SymEngine::symbol("z");
    const auto d = SymEngine::diff(SymEngine::parse(expr), zs);
    const auto sub = d->subs({{zs, SymEngine::complex_double(z)}});
    return SymEngine::eval_complex_double(*sub);
}

// 复辛普森积分。
inline std::complex<double> simpson_c(
    const std::function<std::complex<double>(double)>& f, double a, double b,
    int n = 1000) {
    if (n % 2 != 0) ++n;
    const double h = (b - a) / n;
    std::complex<double> s = f(a) + f(b);
    for (int i = 1; i < n; ++i) {
        const double t = a + i * h;
        s += (i % 2 == 1) ? 4.0 * f(t) : 2.0 * f(t);
    }
    return s * (h / 3.0);
}

// 复伽马函数(Lanczos 近似,经反射公式延拓到全平面)。
inline std::complex<double> gamma_complex(std::complex<double> z) {
    const double g = 7.0;
    static const double c[9] = {
        0.99999999999980993, 676.5203681218851, -1259.1392167224028,
        771.32342877765313, -176.61502916214059, 12.507343278686905,
        -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7};
    // 非正整数处 Γ 有极点。
    if (z.imag() == 0.0 &&
        std::abs(z.real() - std::round(z.real())) < 1e-9 && z.real() <= 0.0)
        throw std::invalid_argument("Γ 在非正整数处有极点");
    if (z.real() < 0.5) {
        return kPi /
               (std::sin(kPi * z) * gamma_complex(1.0 - z));
    }
    z -= 1.0;
    std::complex<double> x = c[0];
    for (int i = 1; i < 9; ++i) x += c[i] / (z + (double)i);
    const std::complex<double> t = z + g + 0.5;
    const std::complex<double> result =
        std::sqrt(2.0 * kPi) * std::pow(t, z + 0.5) * std::exp(-t) * x;
    return result;
}

// ── ζ 函数数值计算 ──────────────────────────────────────────────────────────

// 级数定义(Re s > 1):ζ(s) = Σ 1/n^s。
inline std::complex<double> zeta_series(const std::complex<double>& s,
                                        long long n_terms) {
    std::complex<double> sum(0.0, 0.0);
    for (long long n = 1; n <= n_terms; ++n)
        sum += 1.0 / std::pow((double)n, s);
    return sum;
}

// Dirichlet η 延拓(Re s > 0):ζ(s) = η(s)/(1 - 2^{1-s})。
inline std::complex<double> zeta_eta(const std::complex<double>& s,
                                     long long n_terms) {
    // s = 1 是 ζ 的极点。
    if (std::abs(s.real() - 1.0) < 1e-9 && std::abs(s.imag()) < 1e-9)
        throw std::invalid_argument("ζ 在 s=1 处有极点");
    std::complex<double> eta(0.0, 0.0);
    for (long long n = 1; n <= n_terms; ++n) {
        const double sgn = (n % 2 == 1) ? 1.0 : -1.0;
        eta += sgn / std::pow((double)n, s);
    }
    const std::complex<double> factor = 1.0 - std::pow(2.0, 1.0 - s);
    if (std::abs(factor) < 1e-12) return zeta_series(s, n_terms);
    return eta / factor;
}

// 函数方程 ζ(s) = 2^s·π^{s-1}·sin(πs/2)·Γ(1-s)·ζ(1-s)。
// 用于把 Re s < 0 的求值化归到 Re(1-s) > 1 的 Euler–Maclaurin 快算。
// 必要性:直接对 Re s < 0 用 E-M 时 n^{-s} = n^{|Re s|} 会爆炸式增长
// (s = -100.5、N ≈ 88 时量级 10^{190}),与结果 O(1) 的相消让 double 完全失真。
inline std::complex<double> zeta_functional(
    const std::complex<double>& s, const std::complex<double>& zeta_1_minus_s) {
    const std::complex<double> factor =
        std::pow(std::complex<double>(2.0, 0.0), s) *
        std::pow(std::complex<double>(kPi, 0.0), s - 1.0);
    return factor * std::sin(kPi * s / 2.0) * gamma_complex(1.0 - s) *
           zeta_1_minus_s;
}

// B_{2k}/(2k)!·(2π)^{2k},k ≥ 1。
// k ≤ 10 用精确有理数表;k ≥ 11 用严格恒等式
//   B_{2k}/(2k)!·(2π)^{2k} = (-1)^{k+1}·2ζ(2k)
// (对一切 k ≥ 1 成立;2k ≥ 22 时 Σ_{n≤10} n^{-2k} 与 ζ(2k) 相差 < 1e-22,
//  即 10 项求和已达 double 精度)。
// 之所以把 (2π)^{2k} 并进系数,是为了在调用处用 ((2πN)^{-2})^k 的增量累乘,
// 避免 (2π)^{-2k} 自己先下溢成 0 而把整项错误归零。
inline double bernoulli_2pi_scale(long long k) {
    static const double B[22] = {1, -0.5, 1.0 / 6, 0, -1.0 / 30, 0, 1.0 / 42, 0,
                                 -1.0 / 30, 0, 5.0 / 66, 0, -691.0 / 2730, 0,
                                 7.0 / 6, 0, -3617.0 / 510, 0, 43867.0 / 798, 0,
                                 -174611.0 / 330, 0};
    if (k >= 1 && k <= 10) {
        double fact = 1.0;
        for (long long j = 2; j <= 2 * k; ++j) fact *= (double)j;
        return B[2 * k] / fact * std::pow(kTwoPi, 2.0 * (double)k);
    }
    double z = 0.0;
    for (int n = 1; n <= 10; ++n) z += std::pow((double)n, -2.0 * (double)k);
    return (k % 2 == 1) ? 2.0 * z : -2.0 * z;
}

// Euler–Maclaurin 求和:临界带 / 右半平面 ζ(s)。
//   ζ(s) = Σ_{n<N} n^{-s} + N^{1-s}/(s-1) + N^{-s}/2
//          + Σ_{k≥1} B_{2k}/(2k)!·(s)_{2k-1}·N^{-s-2k+1}
//
// **这是本条缺陷的根因**:渐近修正项按 (|s|/(2πN))^{2k} 收敛,只有当
// N ≳ |s|/(2π) 时才收敛。原先 N=12、M=10 写死,2πN ≈ 75,一旦 |Im s| 超过
// 这个量级级数就发散(实测 |Im s|=100 时偏差 3.8)。
// 现在按 |s| 自适应取 N(使 |s|/(2πN) ≈ 0.2),并在渐近级数的**最小项**处
// 截断(最优截断),这样从 |Im s|=0 到 200 以上都能保住 double 精度。
inline std::complex<double> zeta_euler_maclaurin(const std::complex<double>& s,
                                                 long long N = -1,
                                                 long long M = -1) {
    // 极点判据收紧到 1e-12：s 落在 (1±1e-9) 上时 E-M 本身仍算得对
    // (|base/(s-1)| ≈ 1e9，double 绰绰有余)，旧判据 1e-9 会把 ζ(1e-9) 这类
    // **合法**输入误报成极点。
    if (std::abs(s.real() - 1.0) < 1e-12 && std::abs(s.imag()) < 1e-12)
        throw std::invalid_argument("ζ 在 s=1 处有极点");
    if (N <= 0) {
        // |s|/(2πN) ≈ 0.2 ⇒ N ≈ 0.8|s|;下限 16 保证小 |s| 也有充足余量。
        N = (long long)std::ceil(0.8 * std::abs(s)) + 8;
        if (N < 16) N = 16;
        if (N > 4000000) N = 4000000;
    }
    std::complex<double> sum(0.0, 0.0);
    for (long long n = 1; n < N; ++n) sum += 1.0 / std::pow((double)n, s);
    const std::complex<double> base = std::pow((double)N, 1.0 - s);
    sum += base / (s - 1.0);
    sum += std::pow((double)N, -s) / 2.0;

    // 尾部(渐近级数)的求和:Wp 是 base·(2πN)^{-2k} 的增量累乘,
    // 与 bernoulli_2pi_scale(k) 相乘即得第 k 项。
    const double scale = std::max(1.0, std::abs(sum));
    const double tol = 1e-19 * scale;
    const double inv2piN2 = 1.0 / (kTwoPi * (double)N * kTwoPi * (double)N);
    std::complex<double> rising(1.0, 0.0);      // (s)_{2k-1} = s(s+1)…(s+2k-2)
    std::complex<double> Wp = base * inv2piN2;  // base·(2πN)^{-2}
    double prev = std::numeric_limits<double>::infinity();
    const long long kmax = (M > 0) ? M : 2000;
    for (long long k = 1; k <= kmax; ++k) {
        if (k == 1) {
            rising = s;
        } else {
            // (s)_{2k-3} → (s)_{2k-1},补上 (s+2k-3)(s+2k-2) 两个因子。
            rising *= (s + (double)(2 * k - 3));
            rising *= (s + (double)(2 * k - 2));
        }
        const std::complex<double> term = bernoulli_2pi_scale(k) * rising * Wp;
        const double a = std::abs(term);
        if (!(a == a) || a > std::numeric_limits<double>::max() / 16.0) break;
        if (k > 1 && a > prev) break;  // 已越过最小项 → 渐近级数开始发散,停
        sum += term;
        prev = a;
        if (a < tol) break;
        Wp *= inv2piN2;
    }
    return sum;
}

}  // namespace mf::complex_analysis::detail
