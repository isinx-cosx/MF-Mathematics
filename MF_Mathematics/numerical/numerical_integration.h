// numerical_integration.h — 数值积分与微分:梯形/辛普森/高斯求积/数值微分/最优步长。
#pragma once

#include <string>


namespace mf::numerical {

// 复合梯形法则 ∫_a^b f(x)dx。f 为表达式字符串(变量 x),n 为子区间数。
double trapezoidal_rule(const std::string& f, double a, double b,
                               long long n = 100);

// 复合辛普森法则(n 自动调整为偶数;a > b 时结果取负,与 Python 一致)。
double simpson_rule(const std::string& f, double a, double b,
                           long long n = 100);

// 高斯-勒让德求积,n ∈ {2, 3, 4}。
double gauss_quadrature(const std::string& f, double a, double b,
                               long long n = 3);

// 数值微分,method ∈ {forward, backward, central}。
double numerical_derivative(const std::string& f, double x,
                                   double h = 1e-6,
                                   const std::string& method = "central");

// 数值微分最优步长(平衡截断误差与舍入误差)。
double optimal_step(const std::string& f, double x,
                           const std::string& method = "central");

}  // namespace mf::numerical
