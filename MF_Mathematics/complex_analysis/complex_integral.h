// complex_integral.h — 复曲线积分、柯西定理、柯西积分公式、高阶导公式。
#pragma once

#include <complex>
#include <string>


namespace mf::complex_analysis {

// 复曲线积分 ∫_γ f(z) dz,γ(t) = center + r·e^{it},t ∈ [a,b]。
std::complex<double> contour_integral_circle(
    const std::string& func, std::complex<double> center, double radius,
    double a, double b, long long n_points = 1000);

// 柯西定理验证:闭合曲线积分为零。
struct CauchyTheoremResult {
    std::complex<double> integral{0.0, 0.0};
    bool zero = false;
};
CauchyTheoremResult cauchy_theorem(const std::string& func,
                                          std::complex<double> center,
                                          double radius);

// 柯西积分公式 f(a) = 1/(2πi) ∮ f(z)/(z-a) dz。
struct CauchyFormulaResult {
    std::complex<double> cauchy_formula{0.0, 0.0};
    std::complex<double> direct_f_a{0.0, 0.0};
    double error = 0.0;
};
CauchyFormulaResult cauchy_integral_formula(
    const std::string& func, std::complex<double> a,
    std::complex<double> center, double radius, long long n_points = 1000);

// 高阶导公式 f^{(n)}(a) = n!/(2πi) ∮ f(z)/(z-a)^{n+1} dz。
struct DerivativeFormulaResult {
    std::complex<double> derivative{0.0, 0.0};
    std::complex<double> symbolic{0.0, 0.0};
};
DerivativeFormulaResult derivative_formula(
    const std::string& func, std::complex<double> a, long long n,
    std::complex<double> center, double radius, long long n_points = 1000);

}  // namespace mf::complex_analysis
