// normed_spaces.h — 赋范空间与巴拿赫空间:ℓ^p 范数、巴拿赫判断、柯西列验证。
#pragma once

#include <string>
#include <vector>


namespace mf::functional_analysis {

// ℓ^p 范数。p 可为 +inf(上确界范数);p ≤ 0 抛 std::invalid_argument。
double lp_norm(const std::vector<double>& vector, double p);

// 巴拿赫空间判断(查表 + 有限维自动完备)。
bool is_banach(const std::string& space, long long dimension = -1);

// 序列是否柯西列(尾部范数差 < 1e-3)。norm ∈ {l1, l2, linf}。
struct CompletenessResult {
    bool is_cauchy = false;
    double tail_max_diff = 0.0;
    std::vector<double> all_diffs;
};
CompletenessResult space_completeness_check(
    const std::vector<std::vector<double>>& sequence,
    const std::string& norm = "l2");

}  // namespace mf::functional_analysis
