// sequence_limit.h — 数列极限、收敛性判定、柯西准则。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::real_analysis {

// 数列极限 lim_{n→∞} a_n(数值检测)。发散返回 ±inf,振荡返回 NaN。
MF_API double sequence_limit(const std::string& expr,
                             const std::string& var = "n");

// 收敛性判定。
struct SequenceConvergenceResult {
    bool convergent = false;
    double limit_value = 0.0;
    std::string description;  // "收敛" / "发散（趋于 +∞）" / "发散（趋于 -∞）" / "发散（振荡或无界）"
};
MF_API SequenceConvergenceResult sequence_convergence(const std::string& expr,
                                                      const std::string& var = "n");

// 柯西准则:尾部项最大差异 < epsilon。
MF_API bool cauchy_criterion(const std::string& expr, double epsilon,
                             long long max_n, const std::string& var = "n");

// 数值列表的柯西准则。
MF_API bool cauchy_criterion_values(const std::vector<double>& values,
                                    double epsilon);

}  // namespace mf::real_analysis
