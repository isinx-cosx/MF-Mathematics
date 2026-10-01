// limits_theorems.h — 大数定律与中心极限定理。
#pragma once

#include <vector>

#include "../mf_export.h"

namespace mf::probability {

// 大数定律:样本均值随 n 增大逼近总体均值。
struct LlnResult {
    double deviation = 0.0;
    double threshold = 0.0;
    bool converged = false;
};
MF_API LlnResult law_of_large_numbers(double sample_mean, double true_mean,
                                      long long n);

// 中心极限定理:标准化样本均值近似 N(0,1)。
struct CltResult {
    double sample_mean = 0.0;
    double Z = 0.0;
    double p_value = 0.0;
    double standard_error = 0.0;
    bool approx_normal = false;
};
MF_API CltResult central_limit_theorem(const std::vector<double>& sample,
                                       double mu, double sigma, long long n);

}  // namespace mf::probability
