#include "optimization.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

#include "../parser_lib.h"

namespace mf::numerical {

GradientDescentResult gradient_descent(const std::string& f, double x0,
                                       double learning_rate, long long max_iter,
                                       double tol) {
    if (learning_rate <= 0) throw std::invalid_argument("学习率必须为正数");
    // 符号微分求解析导数(与 Python 的 sympy.diff 对齐)
    auto root = mf::expr::parse(f);
    auto droot = mf::expr::differentiate(root.get());

    std::vector<double> path{x0};
    double xi = x0;
    for (long long i = 0; i < max_iter; ++i) {
        const double grad = mf::expr::eval(droot.get(), xi);
        const double xi_new = xi - learning_rate * grad;
        if (std::abs(xi_new - xi) < tol) {
            xi = xi_new;
            path.push_back(xi);
            break;
        }
        xi = xi_new;
        path.push_back(xi);
    }

    GradientDescentResult res;
    res.x_min = xi;
    res.f_min = mf::expr::eval(root.get(), xi);
    res.iterations = static_cast<long long>(path.size());
    const std::size_t keep = std::min<std::size_t>(10, path.size());
    res.path.assign(path.begin(), path.begin() + keep);
    return res;
}

}  // namespace mf::numerical
