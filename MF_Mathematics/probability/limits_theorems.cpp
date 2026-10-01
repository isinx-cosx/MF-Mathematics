#include "limits_theorems.h"

#include <cmath>
#include <stdexcept>

#include "prob_internal.h"

namespace mf::probability {

LlnResult law_of_large_numbers(double sample_mean, double true_mean, long long n) {
    if (n <= 0) throw std::invalid_argument("样本量必须为正");
    LlnResult r;
    r.deviation = std::abs(sample_mean - true_mean);
    r.threshold = 3.0 / std::sqrt((double)n);
    r.converged = r.deviation < r.threshold;
    return r;
}

CltResult central_limit_theorem(const std::vector<double>& sample, double mu,
                                double sigma, long long n) {
    if (sample.empty()) throw std::invalid_argument("样本为空");
    if (std::abs(sigma) < 1e-15) throw std::invalid_argument("σ 不能为 0");
    if (n <= 0) throw std::invalid_argument("样本量必须为正");
    CltResult r;
    r.sample_mean = detail::mean(sample);
    r.standard_error = sigma / std::sqrt((double)n);
    r.Z = (r.sample_mean - mu) / r.standard_error;
    r.p_value = detail::two_sided_p(r.Z);
    r.approx_normal = n >= 30;
    return r;
}

}  // namespace mf::probability
