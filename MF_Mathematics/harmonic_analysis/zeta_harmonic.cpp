// zeta_harmonic.cpp — 调和分析与数论内核。

#include "zeta_harmonic.h"

#include <cmath>
#include <complex>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/parser.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include "ha_internal.h"
#include "ha_numeric.h"
#include "ha_rational_ft.h"

namespace mf::harmonic_analysis {

using detail::eval_double_expr;
using detail::kPi;

namespace {

// 检测 f = e^{-a·x²}(高斯),返回 a;否则返回 false。
bool gaussian_param(const std::string& f, double& a) {
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(f);
    if (!SymEngine::is_a<SymEngine::Pow>(*e)) return false;
    const auto args = e->get_args();
    if (!SymEngine::eq(*args[0], *SymEngine::E)) return false;
    try {
        const auto c2 = SymEngine::coeff(*args[1], *x, *SymEngine::integer(2));
        const auto c1 = SymEngine::coeff(*args[1], *x, *SymEngine::integer(1));
        const auto c0 = SymEngine::coeff(*args[1], *x, *SymEngine::integer(0));
        const double a2 = SymEngine::eval_double(*c2);
        const double a1 = SymEngine::eval_double(*c1);
        const double a0 = SymEngine::eval_double(*c0);
        if (a1 != 0.0 || a0 != 0.0 || a2 >= 0.0) return false;
        a = -a2;
        return true;
    } catch (...) {
        return false;
    }
}

// 伯努利数 B_n(递归公式)。
double bernoulli(long long n) {
    std::vector<double> B(n + 1, 0.0);
    B[0] = 1.0;
    for (long long m = 1; m <= n; ++m) {
        double s = 0.0;
        for (long long k = 0; k < m; ++k) {
            // C(m, k)·B_k
            double c = 1.0;
            for (long long i = 0; i < k; ++i) c *= (m - i) / double(i + 1);
            s += c * B[k] / (m - k + 1);
        }
        B[m] = -s;
    }
    return B[n];
}

// 实 ζ(s): 任意实 s(s≠1) 用 Euler–Maclaurin, 非正整数用伯努利公式,
// 负非整数用函数方程。旧实现只覆盖 s>1 / s=0 / 负整数, 其余返回 NaN ——
// 于是 0<s<1(关键带)与 ζ(-0.5) 之类的调用会静默变成 null。
//
//   ζ(s) = Σ_{n=1}^{N-1} n^{-s} + N^{-s}/2 + N^{1-s}/(s-1)
//          + Σ_{k=1}^{M} B_{2k}/(2k)!·s(s+1)…(s+2k-2)·N^{-s-2k+1} + R
//
// N=16, M=12 时残项 <1e-15(实 s 全带内实测, 见 tests/accuracy 用例)。
double zeta_em(double s, int N, int M) {
    double sum = 0.0;
    for (int n = 1; n < N; ++n) sum += std::pow(static_cast<double>(n), -s);
    const double Nd = static_cast<double>(N);
    sum += 0.5 * std::pow(Nd, -s);
    sum += std::pow(Nd, 1.0 - s) / (s - 1.0);
    double rising = 1.0;  // s(s+1)…(s+2k-2)
    double fact = 1.0;    // (2k)!
    for (int k = 1; k <= M; ++k) {
        if (k == 1) rising = s;
        else rising *= (s + 2.0 * k - 3.0) * (s + 2.0 * k - 2.0);
        fact *= (2.0 * k - 1.0) * (2.0 * k);
        sum += bernoulli(2 * k) / fact * rising * std::pow(Nd, -s - 2.0 * k + 1.0);
    }
    return sum;
}

// 实 ζ(s)(s≠1)。
double zeta_real(double s) {
    if (s > 0.0) return zeta_em(s, 16, 12);
    if (s == 0.0) return -0.5;
    if (s < 0.0 && s == std::floor(s)) {
        const long long n = static_cast<long long>(-s);
        if (n > 0 && n % 2 == 0) return 0.0;  // ζ(-2k) = 0
        return -bernoulli(n + 1) / (n + 1);
    }
    // 负非整数: 函数方程 ζ(s) = 2^s π^{s-1} sin(πs/2) Γ(1-s) ζ(1-s)。
    return std::pow(2.0, s) * std::pow(kPi, s - 1.0) * std::sin(kPi * s / 2.0) *
           detail::gamma_fun(1.0 - s) * zeta_em(1.0 - s, 16, 12);
}

}  // namespace

PoissonResult poisson_summation(const std::string& f, double a, int n_terms) {
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(f);

    // 左边 Σ f(n·a)。
    double left = 0.0;
    for (int n = -n_terms; n <= n_terms; ++n)
        left += eval_double_expr(e, x, n * a);

    // 右边 (1/a)Σ F(k/a),F(ξ) = ∫f(x)e^{-2πixξ}dx(普通频率)。
    double gauss_a = 0.0;
    double right = 0.0;
    double unc = 0.0;      // 右和的误差上界
    int used = 0;          // 实际算出的项数
    bool reliable = true;
    const bool is_gauss = gaussian_param(f, gauss_a);
    // f 是有理函数时用留数闭式(ha_rational_ft.h): F(ξ) 逐项精确, 高频项不再欠采样。
    // 闭式只在"部分分式能逐点重现 f"的复核通过后才生效, 否则退回数值分支。
    detail::RationalFT rft;
    if (!is_gauss) rft = detail::prepare_rational_ft(e, x);
    if (is_gauss) {
        // f = e^{-a·x²} → F(ξ) = √(π/a)·e^{-π²ξ²/a}(闭式,避免高频混叠)。
        const double coef = std::sqrt(kPi / gauss_a);
        for (int k = -n_terms; k <= n_terms; ++k) {
            const double xi = k / a;
            right += coef * std::exp(-kPi * kPi * xi * xi / gauss_a);
        }
        right /= a;
        used = 2 * n_terms + 1;
    } else if (rft.ok) {
        // 解析分支: F(k/a) 由留数闭式给出(极点 p_j 与留数 c_j 已通过复核),
        // 于是 (1/a)Σ_k F(k/a) 的每一项都是真值, 误差只剩浮点求和舍入。
        std::complex<double> acc(0.0, 0.0);
        double abs_acc = 0.0;
        for (int k = -n_terms; k <= n_terms; ++k) {
            const std::complex<double> v = rft.eval(k / a);
            acc += v;
            abs_acc += std::abs(v);
        }
        right = acc.real() / a;
        unc = (2.0 * n_terms + 3.0) * 2.2204460492503131e-16 * abs_acc /
              std::abs(a);
        used = 2 * n_terms + 1;
    } else {
        // 数值分支: 逐项自适应积分(截断半径自适应 + 渐近尾校正)。
        // 大 |k| 时 ω=2πk/a 很大而 f 只有代数衰减, 变换的振荡积分会欠采样 ——
        // 这种项不再拿噪声当值加进去: 丢掉它, 用已解出项的几何衰减外推给出
        // 尾部上界(见 right_sum_error)。至少保证 k=0 与低阶项是真值。
        const double tol_sum = 1e-11 * std::max(1.0, std::abs(left));
        const double tol_term = tol_sum * 0.25;
        std::vector<double> mags;  // 已解析项的 |F(k/a)|/a
        int unresolved = 0;
        for (int k = 0; k <= n_terms; ++k) {
            const double xi = k / a;
            const double w = 2.0 * kPi * xi;
            const long long budget = (k <= 3) ? 4000000 : 300000;
            const detail::NumericFT q = detail::numeric_fourier_transform(
                e, x, w, 0.0, tol_term, budget);
            const double mult = (k == 0) ? 1.0 : 2.0;  // ±k 对称
            const double v = q.value.real() / a;
            if (q.reliable || std::abs(v) > 8.0 * q.error) {
                right += mult * v;
                unc += mult * q.error;
                mags.push_back(std::abs(v));
                used = k + 1;
                continue;
            }
            // 未解出: 该项不可信。
            ++unresolved;
            if (mags.size() >= 3) {
                const std::size_t m = mags.size();
                const double r1 = mags[m - 1] / mags[m - 2];
                const double r2 = mags[m - 2] / mags[m - 3];
                if (r1 > 0.0 && r1 <= 0.5 && r2 <= 0.5) {
                    // 尾部按几何级数界定(再留 2 倍安全系数)。
                    unc += 2.0 * mags[m - 1] * r1 / (1.0 - r1) / a;
                    break;
                }
            }
            unc += mult * std::max(q.error, std::abs(v));
            if (unresolved >= 3) {  // 无法界定: 不再逐项探测, 如实报告不可信
                reliable = false;
                break;
            }
        }
    }

    PoissonResult r;
    r.left_sum = left;
    r.right_sum = right;
    r.relative_difference =
        std::abs(left - right) / std::max(std::abs(left), 1e-12);
    r.consistent = r.relative_difference < 0.05;
    r.right_sum_error = unc;
    r.numeric_terms = used;
    r.right_sum_reliable = reliable;
    return r;
}

ThetaResult theta_function(double t, int n_terms) {
    if (t <= 0) throw std::invalid_argument("t 必须为正");
    double theta = 0.0;
    for (int n = -n_terms; n <= n_terms; ++n)
        theta += std::exp(-kPi * n * n * t);
    double recip = 0.0;
    for (int n = -n_terms; n <= n_terms; ++n)
        recip += std::exp(-kPi * n * n / t);
    ThetaResult r;
    r.theta_t = theta;
    r.theta_reciprocal = recip;
    r.modular_check = std::abs(theta - recip / std::sqrt(t)) / std::max(theta, 1e-12);
    return r;
}

FunctionalEquationResult functional_equation_demo(double s) {
    if (std::abs(s - 1.0) < 1e-10)
        throw std::invalid_argument("s 不能为 1(ζ 函数极点)");
    const double zs = zeta_real(s);
    const double z1s = zeta_real(1.0 - s);
    const double gs = detail::gamma_fun(s / 2.0);
    const double g1s = detail::gamma_fun((1.0 - s) / 2.0);
    const double left = std::pow(kPi, -s / 2.0) * gs * zs;
    const double right = std::pow(kPi, -(1.0 - s) / 2.0) * g1s * z1s;

    FunctionalEquationResult r;
    r.zeta_s = zs;
    r.zeta_1_minus_s = z1s;
    r.left_side = left;
    r.right_side = right;
    r.relative_difference =
        std::abs(left - right) / std::max(std::abs(left), 1e-30);
    return r;
}

}  // namespace mf::harmonic_analysis
