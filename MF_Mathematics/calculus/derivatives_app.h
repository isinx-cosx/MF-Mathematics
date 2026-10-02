// derivatives_app.h — 导数应用:罗尔/拉格朗日定理、洛必达、单调性、极值、最值、泰勒。
#pragma once

#include <string>
#include <vector>


namespace mf::calculus {

// 罗尔定理:满足 f'(ξ)=0 的 ξ(在 (a,b) 内)。f(a)≠f(b) 返回空。
std::vector<double> calc_rolle_theorem(const std::string& expr,
                                              const std::string& var, double a,
                                              double b);

// 拉格朗日中值定理:f'(ξ) = 割线斜率。未找到返回 NaN。
double calc_lagrange_theorem(const std::string& expr,
                                    const std::string& var, double a, double b);

// 洛必达法则求 0/0 或 ∞/∞ 型极限。
double lhopital(const std::string& expr, const std::string& var,
                       double point);

// 单调性:各区间描述 "(-∞,x1): 单调递增" 等。
std::vector<std::string> monotonicity(const std::string& expr,
                                             const std::string& var);

// 局部极值:二阶导数检验。
struct LocalExtremaResult {
    std::vector<double> maxima_x;
    std::vector<double> maxima_val;
    std::vector<double> minima_x;
    std::vector<double> minima_val;
};
LocalExtremaResult local_extrema(const std::string& expr,
                                        const std::string& var);

// 全局最值(闭区间端点 + 驻点)。
struct GlobalExtremaResult {
    double max = 0.0;
    double max_point = 0.0;
    double min = 0.0;
    double min_point = 0.0;
};
GlobalExtremaResult global_extrema(const std::string& expr,
                                          const std::string& var, double a,
                                          double b);

// 泰勒展开多项式。
std::string taylor(const std::string& expr, const std::string& var,
                          double point, long long order);

}  // namespace mf::calculus
