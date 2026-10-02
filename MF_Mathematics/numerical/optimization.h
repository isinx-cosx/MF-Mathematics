// optimization.h — 优化:梯度下降(符号导数)。
#pragma once

#include <string>
#include <vector>


namespace mf::numerical {

// 梯度下降求 f(x) 极小值。f 为表达式字符串,导数用符号微分求得。
struct GradientDescentResult {
    double x_min = 0.0;
    double f_min = 0.0;
    long long iterations = 0;
    std::vector<double> path;  // 前 10 个迭代点
};
GradientDescentResult gradient_descent(
    const std::string& f, double x0 = 1.0, double learning_rate = 0.1,
    long long max_iter = 1000, double tol = 1e-6);

}  // namespace mf::numerical
