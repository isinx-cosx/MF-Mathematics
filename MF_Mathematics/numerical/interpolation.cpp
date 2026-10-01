#include "interpolation.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <stdexcept>
#include <vector>

#include "interpolation_core.h"

namespace mf::numerical {

namespace {

void validate_points(const std::vector<double>& x, const std::vector<double>& y) {
    if (x.size() != y.size())
        throw std::invalid_argument("x_points 和 y_points 长度不一致");
    if (x.empty()) throw std::invalid_argument("插值点不能为空");
}

}  // namespace

std::vector<double> lagrange_interpolation(const std::vector<double>& x,
                                           const std::vector<double>& y) {
    validate_points(x, y);
    // 现有核心返回升幂系数 [c0,c1,...],Python 反转为降幂(高次到低次)
    std::vector<double> asc = ::lagrange(x, y);
    std::reverse(asc.begin(), asc.end());
    return asc;
}

std::vector<double> newton_interpolation(const std::vector<double>& x,
                                         const std::vector<double>& y) {
    validate_points(x, y);
    std::set<double> distinct(x.begin(), x.end());
    if (distinct.size() != x.size())
        throw std::invalid_argument("x 值中存在重复点,牛顿插值要求各点 x 坐标互不相同");
    return ::newton(x, y);
}

std::vector<std::vector<double>> cubic_spline(const std::vector<double>& x,
                                              const std::vector<double>& y) {
    validate_points(x, y);
    if (x.size() < 4)
        throw std::invalid_argument("三次样条至少需要 4 个点");
    for (std::size_t i = 1; i < x.size(); ++i)
        if (x[i] <= x[i - 1])
            throw std::invalid_argument("x 坐标必须严格递增");
    // 现有核心返回展开的 [a0,b0,c0,d0, a1,b1,c1,d1, ...],重排为每段一行
    const std::vector<double> flat = ::cubic_spline(x, y);
    const std::size_t seg = x.size() - 1;
    std::vector<std::vector<double>> coeffs(seg, std::vector<double>(4, 0.0));
    for (std::size_t i = 0; i < seg; ++i)
        for (std::size_t k = 0; k < 4; ++k)
            coeffs[i][k] = flat[i * 4 + k];
    return coeffs;
}

LeastSquaresResult least_squares_fit(const std::vector<double>& x,
                                     const std::vector<double>& y,
                                     long long degree) {
    validate_points(x, y);
    if (static_cast<long long>(x.size()) < degree + 1)
        throw std::invalid_argument("数据点不足,至少需要 " + std::to_string(degree + 1) + " 个点");
    std::vector<double> asc = ::least_squares(x, y, static_cast<int>(degree));
    std::reverse(asc.begin(), asc.end());

    // R² = 1 - SS_res/SS_tot
    double y_mean = 0.0;
    for (double v : y) y_mean += v;
    y_mean /= static_cast<double>(y.size());
    double ss_res = 0.0, ss_tot = 0.0;
    for (std::size_t i = 0; i < x.size(); ++i) {
        double y_pred = 0.0;
        for (std::size_t k = 0; k < asc.size(); ++k)
            y_pred += asc[k] * std::pow(x[i], static_cast<double>(asc.size() - 1 - k));
        const double dy = y[i] - y_pred;
        const double dy0 = y[i] - y_mean;
        ss_res += dy * dy;
        ss_tot += dy0 * dy0;
    }
    const double r_squared =
        ss_tot < 1e-15 ? std::numeric_limits<double>::quiet_NaN() : 1.0 - ss_res / ss_tot;
    return {std::move(asc), r_squared};
}

}  // namespace mf::numerical
