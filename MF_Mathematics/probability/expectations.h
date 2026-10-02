// expectations.h — 期望、方差、协方差、相关系数。
#pragma once

#include <string>
#include <vector>


namespace mf::probability {

// 样本均值。
double expectation_sample(const std::vector<double>& data);

// 离散期望 E[X] = Σ xi·pi。
double expectation_pmf(const std::vector<double>& values,
                              const std::vector<double>& probs);

// 连续期望 ∫ expr dx(expr 为被积函数)。
double expectation_continuous(const std::string& expr, double a, double b);

// 样本方差(ddof=1 无偏 / 0 有偏)。
double variance_sample(const std::vector<double>& data, long long ddof = 1);

// 离散方差 Var = E[X²] - (E[X])²。
double variance_pmf(const std::vector<double>& values,
                           const std::vector<double>& probs);

// 连续方差(expr 为密度 f):Var = ∫x²f - (∫xf)²。
double variance_continuous(const std::string& expr, double a, double b);

// 样本协方差(ddof=1)。
double covariance_sample(const std::vector<double>& x,
                                const std::vector<double>& y);

// 联合分布协方差 Cov = E[XY] - E[X]E[Y]。
double covariance_joint(const std::vector<double>& x_vals,
                               const std::vector<double>& y_vals,
                               const std::vector<double>& probs);

// 样本相关系数 ρ = Cov/(σx·σy)。
double correlation_sample(const std::vector<double>& x,
                                 const std::vector<double>& y);

// 联合分布相关系数。
double correlation_joint(const std::vector<double>& x_vals,
                                const std::vector<double>& y_vals,
                                const std::vector<double>& probs);

}  // namespace mf::probability
