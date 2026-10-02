// zeta.h — 黎曼 ζ 函数:级数、解析延拓、函数方程、非平凡零点。
#pragma once

#include <complex>
#include <utility>
#include <vector>


namespace mf::complex_analysis {

// ζ(s) 级数(Re s > 1)。
std::complex<double> zeta_series(const std::complex<double>& s,
                                        long long n_terms = 1000);

// ζ(s) 解析延拓:整数 ≤ 0 用伯努利数,Re s > 0 用 η 级数。
std::complex<double> analytic_continuation_zeta(
    const std::complex<double>& s);

// 函数方程验证:ζ(s) 与 2^s π^{s-1} sin(πs/2) Γ(1-s) ζ(1-s)。
struct FunctionalEquationResult {
    std::complex<double> lhs{0.0, 0.0};
    std::complex<double> rhs{0.0, 0.0};
    double error = 0.0;
    bool verified = false;
};
FunctionalEquationResult functional_equation_zeta(
    const std::complex<double>& s);

// 前 limit 个非平凡零点(虚部已知表)。
std::vector<std::pair<double, double>> nontrivial_zeros(long long limit = 10);

}  // namespace mf::complex_analysis
