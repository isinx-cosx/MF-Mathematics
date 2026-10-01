// real_numbers.h — 戴德金分割、确界原理、阿基米德性质。
#pragma once

#include <limits>
#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::real_analysis {

// 戴德金分割判定:A/B 非空、不相交、∀a∈A,b∈B 有 a<b。
MF_API bool dedekind_cut(const std::vector<double>& A,
                         const std::vector<double>& B);

// 上确界:数值集合取最大值;描述字符串 "{x | x < N}" / "{x | x <= N}"。
// 无上界返回 +∞。
MF_API double supremum(const std::vector<double>& s, bool& has_value);
MF_API double supremum_desc(const std::string& desc, bool& has_value);

// 下确界:对称。
MF_API double infimum(const std::vector<double>& s, bool& has_value);
MF_API double infimum_desc(const std::string& desc, bool& has_value);

// 阿基米德性质:最小 n ∈ N 使 n·ε > x。
MF_API long long archimedean_property(double x, double epsilon);

}  // namespace mf::real_analysis
