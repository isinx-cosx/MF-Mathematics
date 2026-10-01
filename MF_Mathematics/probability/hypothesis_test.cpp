#include "hypothesis_test.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <limits>
#include <stdexcept>

#include "prob_internal.h"

namespace mf::probability {

HypothesisResult z_test(double sample_mean, double mu0, double sigma, long long n,
                        double alpha, const std::string& alternative) {
    if (sigma <= 0) throw std::invalid_argument("σ 必须 > 0");
    if (n <= 0) throw std::invalid_argument("n 必须 > 0");
    HypothesisResult r;
    r.alpha = alpha;
    r.alternative = alternative;
    const double se = sigma / std::sqrt((double)n);
    r.statistic = (sample_mean - mu0) / se;
    if (alternative == "two-sided") {
        r.p_value = detail::two_sided_p(r.statistic);
        r.critical_value = detail::normal_inv(1.0 - alpha / 2.0);
    } else if (alternative == "greater") {
        r.p_value = 1.0 - detail::normal_cdf(r.statistic);
        r.critical_value = detail::normal_inv(1.0 - alpha);
    } else if (alternative == "less") {
        r.p_value = detail::normal_cdf(r.statistic);
        r.critical_value = detail::normal_inv(alpha);
    } else {
        throw std::invalid_argument("alternative 必须为 'two-sided'/'greater'/'less'");
    }
    r.reject_H0 = r.p_value < alpha;
    return r;
}

HypothesisResult t_test(const std::vector<double>& data, double mu0, double alpha,
                        const std::string& alternative) {
    if (data.size() < 2) throw std::invalid_argument("样本量 n < 2");
    HypothesisResult r;
    r.alpha = alpha;
    r.alternative = alternative;
    r.df = (long long)data.size() - 1;
    const double mean_val = detail::mean(data);
    const double s = std::sqrt(detail::variance(data, 1));
    const double se = s / std::sqrt((double)data.size());
    if (se < 1e-15) {
        // 零方差样本:t 无定义。均值恰为 mu0 → 无法拒绝;否则 → 显著。
        r.statistic = std::abs(mean_val - mu0) > 1e-15
                          ? std::numeric_limits<double>::infinity()
                          : 0.0;
        r.p_value = std::isfinite(r.statistic) ? 1.0 : 0.0;
        r.critical_value = detail::t_inv(1.0 - alpha / 2.0, (double)r.df);
        r.reject_H0 = r.p_value < alpha;
        return r;
    }
    r.statistic = (mean_val - mu0) / se;
    if (alternative == "two-sided") {
        r.p_value = 2.0 * (1.0 - detail::t_cdf(std::abs(r.statistic), (double)r.df));
        r.critical_value = detail::t_inv(1.0 - alpha / 2.0, (double)r.df);
    } else if (alternative == "greater") {
        r.p_value = 1.0 - detail::t_cdf(r.statistic, (double)r.df);
        r.critical_value = detail::t_inv(1.0 - alpha, (double)r.df);
    } else if (alternative == "less") {
        r.p_value = detail::t_cdf(r.statistic, (double)r.df);
        r.critical_value = detail::t_inv(alpha, (double)r.df);
    } else {
        throw std::invalid_argument("alternative 必须为 'two-sided'/'greater'/'less'");
    }
    r.reject_H0 = r.p_value < alpha;
    return r;
}

ChiSquareResult chi_square_test(const std::vector<double>& observed,
                                const std::vector<double>& expected) {
    if (observed.size() != expected.size())
        throw std::invalid_argument("观测与期望频数长度必须相同");
    ChiSquareResult r;
    r.df = (long long)observed.size() - 1;
    if (r.df < 1) throw std::invalid_argument("自由度 df < 1");
    for (double e : expected)
        if (e <= 0) throw std::invalid_argument("期望频数必须全部 > 0");
    for (std::size_t i = 0; i < observed.size(); ++i) {
        const double diff = observed[i] - expected[i];
        const double c = diff * diff / expected[i];
        r.chi2 += c;
        r.contributions.push_back(c);
    }
    r.p_value = 1.0 - detail::chi2_cdf(r.chi2, (double)r.df);
    r.reject_H0 = r.p_value < 0.05;
    return r;
}

double p_value(double test_statistic, const std::string& dist, long long df,
               const std::string& alternative) {
    std::string d = dist;
    std::transform(d.begin(), d.end(), d.begin(),
                   [](unsigned char c) { return (char)::tolower(c); });
    if (d == "normal") {
        if (alternative == "two-sided") return detail::two_sided_p(test_statistic);
        if (alternative == "greater") return 1.0 - detail::normal_cdf(test_statistic);
        if (alternative == "less") return detail::normal_cdf(test_statistic);
        throw std::invalid_argument("alternative 无效");
    }
    if (d == "t") {
        if (alternative == "two-sided")
            return 2.0 * (1.0 - detail::t_cdf(std::abs(test_statistic), (double)df));
        if (alternative == "greater")
            return 1.0 - detail::t_cdf(test_statistic, (double)df);
        if (alternative == "less") return detail::t_cdf(test_statistic, (double)df);
        throw std::invalid_argument("alternative 无效");
    }
    if (d == "chi2") return 1.0 - detail::chi2_cdf(test_statistic, (double)df);
    throw std::invalid_argument("dist 必须为 'normal'/'t'/'chi2'");
}

}  // namespace mf::probability
