// lebesgue_integral.h — 勒贝格积分:简单函数、非负/一般函数、零测集无关性。
#pragma once

#include <string>
#include <utility>
#include <vector>


namespace mf::measure_theory {

// 简单函数积分 ∫φ dλ = Σ c_i · μ(E_i),μ(E_i) = |b_i - a_i|。
double integral_simple(
    const std::vector<double>& coefficients,
    const std::vector<std::pair<double, double>>& sets);

// 非负可测函数积分(连续函数勒贝格 = 黎曼)。函数非负否则抛异常。
struct NonnegIntegralResult {
    double integral = 0.0;
    double approximation = 0.0;  // 分层(simple function)逼近
};
NonnegIntegralResult integral_nonnegative(const std::string& expr,
                                                 double a, double b);

// 一般可测函数积分:正部减负部 ∫f = ∫f⁺ - ∫f⁻。
struct GeneralIntegralResult {
    double pos = 0.0;
    double neg = 0.0;
    double integral = 0.0;
};
GeneralIntegralResult integral_general(const std::string& expr, double a,
                                              double b);

// 零测集无关性:若 ∫f ≈ ∫g 则几乎处处相等函数积分一致;列出 f-g=0 的根。
struct ZeroSetResult {
    bool are_equal = false;
    std::vector<double> diff_points;
};
ZeroSetResult integral_zero_set_independent(const std::string& f,
                                                   const std::string& g,
                                                   double a, double b);

}  // namespace mf::measure_theory
