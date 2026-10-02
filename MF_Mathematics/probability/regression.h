// regression.h — 一元线性回归、预测、残差分析。
#pragma once

#include <string>
#include <vector>


namespace mf::probability {

struct RegressionResult {
    double slope = 0.0;
    double intercept = 0.0;
    double r_squared = 0.0;
    long long n = 0;
};
RegressionResult linear_regression(const std::vector<double>& x,
                                          const std::vector<double>& y);

// 线性预测 ŷ = β₀ + β₁·x。
double predict_linear(double slope, double intercept, double x);

// 批量预测。
std::vector<double> predict_linear_many(double slope, double intercept,
                                               const std::vector<double>& x);

// 残差分析。
struct ResidualResult {
    std::vector<double> residuals;
    double SSE = 0.0;
    double MSE = 0.0;
    long long n = 0;
};
ResidualResult residuals_linear(double slope, double intercept,
                                       const std::vector<double>& x,
                                       const std::vector<double>& y);

}  // namespace mf::probability
