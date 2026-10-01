// numerical_integration.h — 数值积分与微分:梯形/辛普森/高斯求积/数值微分/最优步长。
#pragma once

#include <string>

#include "../mf_export.h"

namespace mf::numerical {

// 复合梯形法则 ∫_a^b f(x)dx。f 为表达式字符串(变量 x),n 为子区间数。
MF_API double trapezoidal_rule(const std::string& f, double a, double b,
                               long long n = 100);

// 复合辛普森法则(n 自动调整为偶数;a > b 时结果取负,与 Python 一致)。
MF_API double simpson_rule(const std::string& f, double a, double b,
                           long long n = 100);

// 高斯-勒让德求积,n ∈ {2, 3, 4}。
MF_API double gauss_quadrature(const std::string& f, double a, double b,
                               long long n = 3);

// 数值微分,method ∈ {forward, backward, central}。
MF_API double numerical_derivative(const std::string& f, double x,
                                   double h = 1e-6,
                                   const std::string& method = "central");

// 数值微分最优步长(平衡截断误差与舍入误差)。
MF_API double optimal_step(const std::string& f, double x,
                           const std::string& method = "central");

}  // namespace mf::numerical
