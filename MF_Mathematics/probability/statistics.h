// statistics.h — 统计推断:样本均值/方差、矩估计、MLE、置信区间。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::probability {

MF_API double sample_mean(const std::vector<double>& data);

// ddof=1 无偏,ddof=0 有偏。
MF_API double sample_variance(const std::vector<double>& data, long long ddof = 1);

// 矩估计:分布 "normal"/"exponential"/"poisson"/"uniform"。
struct MomentEstimateResult {
    std::string dist;
    bool valid = false;
    double mu_hat = 0.0;      // normal
    double sigma_hat = 0.0;   // normal
    double lambda_hat = 0.0;  // exponential / poisson
    double a_hat = 0.0;       // uniform
    double b_hat = 0.0;       // uniform
};
MF_API MomentEstimateResult moment_estimate(const std::vector<double>& data,
                                            const std::string& dist);

// 最大似然估计(正态/指数/泊松)。
struct MleResult {
    std::string dist;
    bool valid = false;
    double mu_mle = 0.0;
    double sigma_mle = 0.0;
    double lambda_mle = 0.0;
};
MF_API MleResult mle(const std::vector<double>& data, const std::string& dist);

// 正态总体均值置信区间(σ 未知,t 分布)。
struct ConfidenceIntervalResult {
    double lower = 0.0;
    double upper = 0.0;
    double mean = 0.0;
    double margin = 0.0;
    double confidence = 0.95;
    long long n = 0;
};
MF_API ConfidenceIntervalResult confidence_interval(const std::vector<double>& data,
                                                    double confidence);

}  // namespace mf::probability
