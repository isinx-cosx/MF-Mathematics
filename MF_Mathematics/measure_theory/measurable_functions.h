// measurable_functions.h — 可测函数:可测性判定、简单函数、阶梯逼近。
#pragma once

#include <string>
#include <utility>
#include <vector>

#include "../mf_export.h"

namespace mf::measure_theory {

// 函数在定义域内是否有奇点(连续函数 Borel 可测)。
struct MeasurableResult {
    bool is_measurable = true;
    std::vector<double> singularities;
};
MF_API MeasurableResult is_measurable(const std::string& expr, double a,
                                      double b);

// 简单函数 φ(x) = Σ c_i · 1_[a_i,b_i](x) 在点 x 处的值。
MF_API double simple_function_eval(
    const std::vector<double>& coefficients,
    const std::vector<std::pair<double, double>>& sets, double x);

// 阶梯函数逼近:等分 [a,b] 为 n 段,每段取左端点函数值。
struct StepApproxResult {
    std::vector<double> values;
    std::vector<std::pair<double, double>> intervals;
    double dx = 0.0;
    double integral = 0.0;  // Σ value_i · dx
};
MF_API StepApproxResult step_function_approx(const std::string& expr,
                                             long long n, double a, double b);

}  // namespace mf::measure_theory
