// interpolation.h — 插值与逼近:拉格朗日/牛顿/三次样条/最小二乘拟合。
#pragma once

#include <vector>


namespace mf::numerical {

// 拉格朗日插值多项式系数(高次到低次,与 Python np.polyval 顺序一致)。
std::vector<double> lagrange_interpolation(
    const std::vector<double>& x, const std::vector<double>& y);

// 牛顿插值差商表系数。
std::vector<double> newton_interpolation(
    const std::vector<double>& x, const std::vector<double>& y);

// 三次样条(自然边界),返回 n-1 段每段系数 [a, b, c, d](a+b·dx+c·dx²+d·dx³)。
std::vector<std::vector<double>> cubic_spline(
    const std::vector<double>& x, const std::vector<double>& y);

// 最小二乘多项式拟合(degree 次),返回高次到低次系数 + 决定系数 R²。
struct LeastSquaresResult {
    std::vector<double> coeffs;
    double r_squared = 0.0;  // 所有 y 相同(R² 无定义)时为 NaN
};
LeastSquaresResult least_squares_fit(
    const std::vector<double>& x, const std::vector<double>& y,
    long long degree = 2);

}  // namespace mf::numerical
