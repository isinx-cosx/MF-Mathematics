// random_variable.h — 经验分布函数、分布列/密度、随机变量期望。
#pragma once

#include <string>
#include <utility>
#include <vector>

#include "../mf_export.h"

namespace mf::probability {

// 经验分布函数 F_n(x) = #{xi ≤ x}/n。
MF_API double distribution_function(const std::vector<double>& data, double x);

// 完整经验分布:排序后的样本与累计比例。
struct EmpiricalCdfResult {
    std::vector<double> x_values;
    std::vector<double> f_values;
};
MF_API EmpiricalCdfResult distribution_function_full(const std::vector<double>& data);

// 分布列归一化:概率非负;和 ≠ 1 时归一化。
struct PmfResult {
    std::vector<double> probabilities;
    bool was_normalized = false;
};
MF_API PmfResult pmf_normalize(const std::vector<double>& probs);

// 密度函数表达式(验证可解析,原样返回)。
MF_API std::string pdf_expression(const std::string& expr,
                                  const std::string& var = "x");

// 离散期望 E[g(X)] = Σ g(xi)·pi。g 为 "x" 时即恒等随机变量。
MF_API double expectation_discrete_g(const std::vector<double>& values,
                                     const std::vector<double>& probs,
                                     const std::string& g_expr);

// 连续期望 E[g(X)] = ∫ g(x) dx(expr 为被积函数)。
MF_API double expectation_continuous(const std::string& g_expr, double a,
                                     double b);

}  // namespace mf::probability
