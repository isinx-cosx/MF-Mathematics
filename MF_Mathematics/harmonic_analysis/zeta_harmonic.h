// zeta_harmonic.h — 调和分析与数论:泊松求和、θ 函数、ζ 函数方程。
#pragma once

#include <string>

#include "../mf_export.h"

namespace mf::harmonic_analysis {

// 泊松求和公式验证:Σf(na) ≈ (1/a)ΣF(k/a)。
//
// 右和的 F(ξ) 有两条路:
//   * f 是有理函数(如 1/(1+x²)): 用留数闭式(见 ha_rational_ft.h)精确逐项求值,
//     误差只剩浮点求和舍入 —— 高频项不再欠采样, right_sum_error ≈ 1e-16 量级;
//   * 否则: 逐项自适应数值积分。大 |k| 项的变换在慢衰减函数下可能根本解不出来 ——
//     这时不再把欠采样的噪声当值加进去, 而是丢掉并用已解出项的几何衰减外推给出
//     误差上界 right_sum_error; right_sum_reliable=false 表示存在无法界定的项
//     (那才是真的不可信)。
struct PoissonResult {
    double left_sum = 0.0;
    double right_sum = 0.0;
    double relative_difference = 0.0;
    bool consistent = false;
    double right_sum_error = 0.0;
    int numeric_terms = 0;
    bool right_sum_reliable = true;
};
MF_API PoissonResult poisson_summation(const std::string& f, double a, int n_terms);

// 雅可比 θ 函数 θ(t) = Σ e^{-πn²t} + 模变换验证。
struct ThetaResult {
    double theta_t = 0.0;
    double theta_reciprocal = 0.0;
    double modular_check = 0.0;
};
MF_API ThetaResult theta_function(double t, int n_terms);

// ζ 函数方程:π^{-s/2}Γ(s/2)ζ(s) = π^{-(1-s)/2}Γ((1-s)/2)ζ(1-s)。
struct FunctionalEquationResult {
    double zeta_s = 0.0;
    double zeta_1_minus_s = 0.0;
    double left_side = 0.0;
    double right_side = 0.0;
    double relative_difference = 0.0;
};
MF_API FunctionalEquationResult functional_equation_demo(double s);

}  // namespace mf::harmonic_analysis
