#include "zeta.h"

#include <algorithm>
#include <cmath>
#include <complex>
#include <vector>

#include "ca_internal.h"

namespace mf::complex_analysis {

std::complex<double> zeta_series(const std::complex<double>& s,
                                 long long n_terms) {
    return detail::zeta_series(s, n_terms);
}

std::complex<double> analytic_continuation_zeta(const std::complex<double>& s) {
    // 整数 s ≤ 0:ζ(-n) = -B_{n+1}/(n+1)。
    if (std::abs(s.imag()) < 1e-12) {
        const double sr = s.real();
        if (std::abs(sr - std::round(sr)) < 1e-12 && std::round(sr) <= 0) {
            const long long n = (long long)(-std::round(sr));  // s = -n
            if (n == 0) return {-0.5, 0.0};
            // ⚠ n 由用户给的 s 直接决定，下面的递推是 O(n²) 且先按 n 分配：
            //   s = -1e9 时既申请巨大数组、又要跑 1e18 次乘加（实测卡死）。
            //   上限与 bernoulli_number 保持一致（500），超过明确报错。
            if (n > 500)
                throw std::invalid_argument(
                    "ζ 解析延拓：s = -" + std::to_string(n) +
                    " 超出可算范围（负整数点要求 |Re s| ≤ 500）。该点的值由伯努利数 B_{n+1} "
                    "给出，计算量随 |s| 平方增长，再大算不完。");
            // 伯努利数 B_0..B_{n+1}(B_1 = -1/2)。
            std::vector<double> B(n + 2, 0.0);
            B[0] = 1.0;
            for (long long m = 1; m <= n + 1; ++m) {
                double sum = 0.0;
                for (long long k = 0; k < m; ++k) {
                    // C(m+1, k)。
                    const long long km = std::min(k, m + 1 - k);
                    double c = 1.0;
                    for (long long i = 1; i <= km; ++i)
                        c = c * (m + 1 - km + i) / i;
                    sum += c * B[k];
                }
                B[m] = -sum / (double)(m + 1);
            }
            // ζ(-n) = -B_{n+1}/(n+1)。
            return {-B[n + 1] / (double)(n + 1), 0.0};
        }
    }
    // 注意：这里**不能**用截断级数 detail::zeta_series(s, 10000)。
    // 截断尾巴约 1/N，对 s=2 就是 1e-4 量级 —— ζ(2) 会算成 1.644834 而不是
    // 1.6449341（实测）。Euler–Maclaurin 自带尾巴修正。
    // E-M 按 |s| 自适应取 N，|s|/(2πN) ≈ 0.2，临界带/右半平面都准。
    if (s.real() >= 0.0) return detail::zeta_euler_maclaurin(s);
    // Re s < 0：E-M 求和里的 n^{-s} = n^{|Re s|} 会指数爆炸，与 O(1) 的结果
    // 相消后 double 精度全失（实测 s=-1-100i）。改走函数方程
    //   ζ(s) = 2^s·π^{s-1}·sin(πs/2)·Γ(1-s)·ζ(1-s)
    // 把求值化到 Re(1-s) > 1 的快算区（此处递归深度至多 1，不会自嵌套）。
    return detail::zeta_functional(
        s, detail::zeta_euler_maclaurin(std::complex<double>(1.0, 0.0) - s));
}

FunctionalEquationResult functional_equation_zeta(const std::complex<double>& s) {
    FunctionalEquationResult r;
    r.lhs = analytic_continuation_zeta(s);
    const std::complex<double> one_minus_s = 1.0 - s;
    const std::complex<double> factor =
        std::pow(std::complex<double>(2.0, 0.0), s) *
        std::pow(std::complex<double>(detail::kPi, 0.0), s - 1.0);
    const std::complex<double> sin_term =
        std::sin(detail::kPi * s / 2.0);
    const std::complex<double> gamma_term = detail::gamma_complex(one_minus_s);
    const std::complex<double> zeta_term = analytic_continuation_zeta(one_minus_s);
    r.rhs = factor * sin_term * gamma_term * zeta_term;
    r.error = std::abs(r.lhs - r.rhs);
    r.verified = r.error < 1e-10;
    return r;
}

std::vector<std::pair<double, double>> nontrivial_zeros(long long limit) {
    static const double imag_parts[20] = {
        14.134725, 21.022040, 25.010858, 30.424876, 32.935062,
        37.586178, 40.918719, 43.327073, 48.005151, 49.773832,
        52.970321, 56.446248, 59.347044, 60.831779, 65.112544,
        67.079811, 69.546402, 72.067158, 75.704691, 77.144840};
    if (limit > 20) limit = 20;
    std::vector<std::pair<double, double>> zeros;
    for (long long i = 0; i < limit; ++i)
        zeros.emplace_back(0.5, imag_parts[i]);
    return zeros;
}

}  // namespace mf::complex_analysis
