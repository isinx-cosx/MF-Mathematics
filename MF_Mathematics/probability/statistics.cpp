#include "statistics.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <limits>
#include <stdexcept>

#include "prob_internal.h"

namespace mf::probability {

double sample_mean(const std::vector<double>& data) {
    if (data.empty()) throw std::invalid_argument("样本为空");
    return detail::mean(data);
}

double sample_variance(const std::vector<double>& data, long long ddof) {
    if (data.size() <= (std::size_t)ddof)
        throw std::invalid_argument("样本量 n < 2 时无偏方差无定义 (ddof=1)");
    return detail::variance(data, ddof);
}

MomentEstimateResult moment_estimate(const std::vector<double>& data,
                                     const std::string& dist) {
    if (data.empty()) throw std::invalid_argument("样本为空");
    MomentEstimateResult r;
    std::string d = dist;
    std::transform(d.begin(), d.end(), d.begin(),
                   [](unsigned char c) { return (char)::tolower(c); });
    r.dist = d;
    const double m1 = detail::mean(data);
    double m2 = 0.0;
    for (double x : data) m2 += x * x;
    m2 /= (double)data.size();
    const double var_m = m2 - m1 * m1;

    if (d == "normal") {
        r.mu_hat = m1;
        r.sigma_hat = std::sqrt(std::max(0.0, var_m));
        r.valid = true;
    } else if (d == "exponential") {
        r.lambda_hat = m1 > 0 ? 1.0 / m1
                              : std::numeric_limits<double>::infinity();
        r.valid = true;
    } else if (d == "poisson") {
        r.lambda_hat = m1;
        r.valid = true;
    } else if (d == "uniform") {
        const double half = std::sqrt(3.0 * std::max(var_m, 0.0));
        r.a_hat = m1 - half;
        r.b_hat = m1 + half;
        r.valid = true;
    }
    return r;
}

MleResult mle(const std::vector<double>& data, const std::string& dist) {
    if (data.empty()) throw std::invalid_argument("样本为空");
    MleResult r;
    std::string d = dist;
    std::transform(d.begin(), d.end(), d.begin(),
                   [](unsigned char c) { return (char)::tolower(c); });
    r.dist = d;
    const double m1 = detail::mean(data);
    if (d == "normal") {
        r.mu_mle = m1;
        double s = 0.0;
        for (double x : data) {
            const double dd = x - m1;
            s += dd * dd;
        }
        r.sigma_mle = std::sqrt(s / (double)data.size());
        r.valid = true;
    } else if (d == "exponential") {
        r.lambda_mle = m1 > 0 ? 1.0 / m1
                              : std::numeric_limits<double>::infinity();
        r.valid = true;
    } else if (d == "poisson") {
        r.lambda_mle = m1;
        r.valid = true;
    }
    return r;
}

ConfidenceIntervalResult confidence_interval(const std::vector<double>& data,
                                             double confidence) {
    if (data.size() < 2) throw std::invalid_argument("样本量 n < 2");
    if (!(confidence > 0 && confidence < 1))
        throw std::invalid_argument("置信水平必须在 (0,1) 之间");
    ConfidenceIntervalResult r;
    r.n = (long long)data.size();
    r.confidence = confidence;
    r.mean = detail::mean(data);
    const double s = std::sqrt(detail::variance(data, 1));
    const double alpha = 1.0 - confidence;
    const double t_crit = detail::t_inv(1.0 - alpha / 2.0, (double)(r.n - 1));
    r.margin = t_crit * s / std::sqrt((double)r.n);
    r.lower = r.mean - r.margin;
    r.upper = r.mean + r.margin;
    return r;
}

}  // namespace mf::probability
