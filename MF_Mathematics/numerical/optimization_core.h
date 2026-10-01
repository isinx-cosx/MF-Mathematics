#ifndef OPTIMIZATION_CORE_H
#define OPTIMIZATION_CORE_H

#include <cmath>
#include <vector>

// ============================================================================
//  梯度下降 — 纯 C++ 实现（函数指针版本，为 C# 准备）
//
//  与 ODE 模块的关键区别：
//    梯度下降每次迭代仅 1 次函数调用，max_iter 通常 ≤ 10000
//    ODE 每步多次回调 × 百万步 → 回调开销致命
//    梯度下降 10000 次 × 200ns = 2ms → 回调开销可接受
// ============================================================================

struct GradientDescentResult {
    double x_min;
    double f_min;
    int    iterations;
    std::vector<double> path;  // 前 10 个迭代点的 x 值
};

inline GradientDescentResult gradient_descent_core(
    double (*f)(double),        // 目标函数
    double (*df)(double),       // 导函数（nullptr → 中心差分近似）
    double x0,
    double learning_rate,
    int    max_iter,
    double tol)
{
    GradientDescentResult res;
    res.iterations = 0;
    res.path.clear();

    double xi = x0;
    const double h_fd = 1e-6;  // 有限差分步长

    // 记录初始点
    res.path.push_back(xi);

    for (int i = 0; i < max_iter; i++) {
        double grad;
        if (df != nullptr) {
            grad = df(xi);
        } else {
            grad = (f(xi + h_fd) - f(xi - h_fd)) / (2.0 * h_fd);
        }

        double xi_new = xi - learning_rate * grad;

        if (std::fabs(xi_new - xi) < tol) {
            xi = xi_new;
            res.iterations = i + 1;
            break;
        }
        xi = xi_new;
        res.iterations = i + 1;

        // 只保留前 10 个轨迹点（避免返回过大数组）
        if ((int)res.path.size() < 10) {
            res.path.push_back(xi);
        }
    }

    res.x_min = xi;
    res.f_min = f(xi);
    return res;
}

#endif
