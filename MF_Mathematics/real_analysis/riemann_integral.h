// riemann_integral.h — 达布和、可积判定、微积分基本定理、积分中值定理。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::real_analysis {

// 达布和:下和 L、上和 U(各子区间采样求 inf/sup)。
struct DarbouxResult {
    double lower_sum = 0.0;
    double upper_sum = 0.0;
    bool is_integrable = false;
    std::vector<double> partition;
};
MF_API DarbouxResult darboux_sum(const std::string& expr, double a, double b,
                                 const std::vector<double>& partition = {});

// 黎曼可积判定:U-L 随分割加密趋向 0。
MF_API bool riemann_integrable(const std::string& expr, double a, double b);

// 微积分基本定理:∫f dx = F(b) - F(a)。
struct FundamentalResult {
    double integral = 0.0;
    double Fb = 0.0;
    double Fa = 0.0;
    std::string antiderivative;
};
MF_API FundamentalResult fundamental_theorem(const std::string& expr, double a,
                                             double b);

// 积分中值定理:∃ξ ∈ [a,b] 使 f(ξ) = (1/(b-a))∫f dx。
struct MeanValueResult {
    double mean_value = 0.0;
    double xi = 0.0;
};
MF_API MeanValueResult integral_mean_value(const std::string& expr, double a,
                                           double b);

}  // namespace mf::real_analysis
