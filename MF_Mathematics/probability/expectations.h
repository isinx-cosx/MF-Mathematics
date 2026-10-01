// expectations.h — 期望、方差、协方差、相关系数。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::probability {

// 样本均值。
MF_API double expectation_sample(const std::vector<double>& data);

// 离散期望 E[X] = Σ xi·pi。
MF_API double expectation_pmf(const std::vector<double>& values,
                              const std::vector<double>& probs);

// 连续期望 ∫ expr dx(expr 为被积函数)。
MF_API double expectation_continuous(const std::string& expr, double a, double b);

// 样本方差(ddof=1 无偏 / 0 有偏)。
MF_API double variance_sample(const std::vector<double>& data, long long ddof = 1);

// 离散方差 Var = E[X²] - (E[X])²。
MF_API double variance_pmf(const std::vector<double>& values,
                           const std::vector<double>& probs);

// 连续方差(expr 为密度 f):Var = ∫x²f - (∫xf)²。
MF_API double variance_continuous(const std::string& expr, double a, double b);

// 样本协方差(ddof=1)。
MF_API double covariance_sample(const std::vector<double>& x,
                                const std::vector<double>& y);

// 联合分布协方差 Cov = E[XY] - E[X]E[Y]。
MF_API double covariance_joint(const std::vector<double>& x_vals,
                               const std::vector<double>& y_vals,
                               const std::vector<double>& probs);

// 样本相关系数 ρ = Cov/(σx·σy)。
MF_API double correlation_sample(const std::vector<double>& x,
                                 const std::vector<double>& y);

// 联合分布相关系数。
MF_API double correlation_joint(const std::vector<double>& x_vals,
                                const std::vector<double>& y_vals,
                                const std::vector<double>& probs);

}  // namespace mf::probability
