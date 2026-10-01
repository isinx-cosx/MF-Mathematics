// fourier_series.h — 傅里叶级数:三角/复指数系数、级数逼近、正交性。
#pragma once

#include <complex>
#include <string>
#include <utility>
#include <vector>

#include "../mf_export.h"

namespace mf::harmonic_analysis {

// 傅里叶三角系数:a_n = (2/T)∫f·cos(2πnx/T), b_n = (2/T)∫f·sin(...), a_0 = (1/T)∫f。
struct FourierCoeffResult {
    double value = 0.0;
    std::string name;  // a_0 / a_n / b_n
};
MF_API FourierCoeffResult fourier_coeff(const std::string& f, long long n,
                                        double period,
                                        const std::string& coeff_type);

// 前 n 项傅里叶级数逼近 f ≈ a_0 + Σ(a_k cos + b_k sin)。
struct FourierSeriesResult {
    std::string expression;
    std::vector<std::pair<std::string, std::string>> coeffs;  // (name, value)
};
MF_API FourierSeriesResult fourier_series(const std::string& f, long long n_terms,
                                          double period);

// 复傅里叶系数 c_n = (1/T)∫_0^T f(x) e^{-2πinx/T} dx。
struct ComplexCoeffResult {
    std::complex<double> value;
    std::string expression;
};
MF_API ComplexCoeffResult complex_fourier_coeff(const std::string& f, long long n,
                                                double period);

// 正交性:∫_0^T e^{inωx}·e^{-imωx} dx = T(n=m) 或 0(n≠m),ω=2π/T。
struct OrthogonalityResult {
    std::complex<double> integral;
    bool orthogonal = false;
};
MF_API OrthogonalityResult orthogonality_check(long long n, long long m,
                                               double period);

}  // namespace mf::harmonic_analysis
