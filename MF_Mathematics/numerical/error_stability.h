// error_stability.h — 误差与稳定性:条件数、截断误差、舍入误差、稳定性判断。
#pragma once

#include <string>


namespace mf::numerical {

// 函数 f 在 x 处的条件数 |x·f'(x)/f(x)|(数值微分)。f(x)≈0 时返回 +inf。
double condition_number(const std::string& f, double x,
                               double eps = 1e-8);

// 级数截断误差。series 为级数名:exp / sin / cos / ln / geometric。
// true_value 非零时返回 |近似-真值|,否则用第 n+1 项差估计。
double truncation_error(const std::string& series, double x, long long n,
                               double true_value = 0.0);

// 舍入误差界:10^(-precision)(机器精度量级)。
double rounding_error_estimate(long long precision = 16);

// 算法稳定性:对输入施加 1e-8 相对扰动,结果相对差异 < 1e-4 视为稳定。
bool is_stable(const std::string& f, double x);

}  // namespace mf::numerical
