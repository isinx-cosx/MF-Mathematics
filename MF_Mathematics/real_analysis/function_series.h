// function_series.h — 函数序列/级数:逐点/一致收敛、M 判别、逐项积分/求导。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::real_analysis {

// 逐点收敛:固定 x,lim_{n→∞} f_n(x)。发散返回 ±inf/NaN。
MF_API double pointwise_convergence(const std::string& seq_expr, double point);

// 一致收敛:sup|f_n - f| → 0。
struct UniformConvergenceResult {
    bool is_uniform = false;
    std::string convergence_type;  // "一致收敛" / "逐点收敛（非一致）"
    double limit_function_value = 0.0;
    std::vector<double> sup_diffs;
};
MF_API UniformConvergenceResult uniform_convergence(const std::string& seq_expr,
                                                   double a, double b);

// Weierstrass M 判别法:sup|f_n| 支配级数收敛。
struct WeierstrassResult {
    bool passes = false;
    std::vector<double> M_values;
};
MF_API WeierstrassResult weierstrass_m_test(const std::string& seq_expr, double a,
                                            double b);

// 逐项积分:Σ∫f_n dx 与 ∫(Σf_n) dx。
struct TermwiseIntegralResult {
    double termwise_sum = 0.0;
    double direct_integral = 0.0;
};
MF_API TermwiseIntegralResult termwise_integration(const std::string& seq_expr,
                                                   double a, double b,
                                                   long long n_terms);

// 逐项求导:Σ d/dx f_n 与 d/dx(Σf_n)。
struct TermwiseDiffResult {
    std::string derivative_series;
    bool verified = false;
};
MF_API TermwiseDiffResult termwise_differentiation(const std::string& seq_expr,
                                                   long long n_terms);

}  // namespace mf::real_analysis
