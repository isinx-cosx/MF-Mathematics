#include "distributions.h"

#include <cmath>
#include <stdexcept>

#include "prob_internal.h"

namespace mf::probability {

namespace {
// 组合数 C(n,k)(迭代乘积,double)。
double comb(long long n, long long k) {
    if (k < 0 || k > n) return 0.0;
    k = std::min(k, n - k);
    double r = 1.0;
    for (long long i = 1; i <= k; ++i)
        r = r * (n - k + i) / i;
    return r;
}
}  // namespace

DistributionResult bernoulli(double p) {
    if (p < 0 || p > 1) throw std::invalid_argument("概率 p 必须在 [0,1] 之间");
    DistributionResult r;
    r.name = "Bernoulli(" + std::to_string(p) + ")";
    r.mean = p;
    r.variance = p * (1 - p);
    r.std = std::sqrt(r.variance);
    r.pdf = "P(X=1)=" + std::to_string(p) + ", P(X=0)=" + std::to_string(1 - p);
    r.pmf_keys = {0, 1};
    r.pmf_values = {1 - p, p};
    return r;
}

DistributionResult binomial(long long n, double p) {
    if (n <= 0) throw std::invalid_argument("n 必须为正整数");
    if (p < 0 || p > 1) throw std::invalid_argument("概率 p 必须在 [0,1] 之间");
    DistributionResult r;
    r.name = "Binomial(" + std::to_string(n) + ", " + std::to_string(p) + ")";
    r.mean = (double)n * p;
    r.variance = r.mean * (1 - p);
    r.std = std::sqrt(r.variance);
    r.pdf = "P(X=k) = C(" + std::to_string(n) + ",k)·p^k·(1-p)^(n-k)";
    const long long kmax = std::min(n + 1, 8LL);
    const double q = 1 - p;
    for (long long k = 0; k < kmax; ++k) {
        r.pmf_keys.push_back(k);
        r.pmf_values.push_back(comb(n, k) * std::pow(p, (double)k) * std::pow(q, (double)(n - k)));
    }
    return r;
}

DistributionResult poisson(double lam) {
    if (lam <= 0) throw std::invalid_argument("λ 必须 > 0");
    DistributionResult r;
    r.name = "Poisson(" + std::to_string(lam) + ")";
    r.mean = lam;
    r.variance = lam;
    r.std = std::sqrt(lam);
    if (lam > 700) {
        r.pdf = "exp(-λ) 下溢，建议使用正态近似 N(λ, λ)";
        return r;
    }
    r.pdf = "P(X=k) = λ^k·e^(-λ)/k!";
    double term = std::exp(-lam);
    for (long long k = 0; k < 8; ++k) {
        r.pmf_keys.push_back(k);
        r.pmf_values.push_back(term);
        term *= lam / (double)(k + 1);
    }
    return r;
}

DistributionResult uniform_dist(double a, double b) {
    if (b <= a) throw std::invalid_argument("必须 b > a");
    DistributionResult r;
    r.name = "Uniform(" + std::to_string(a) + ", " + std::to_string(b) + ")";
    r.mean = (a + b) / 2;
    r.variance = (b - a) * (b - a) / 12;
    r.std = std::sqrt(r.variance);
    r.pdf = "1/(" + std::to_string(b - a) + ") on [" + std::to_string(a) + ", " +
            std::to_string(b) + "]";
    return r;
}

DistributionResult exponential_dist(double lam) {
    if (lam <= 0) throw std::invalid_argument("λ 必须 > 0");
    DistributionResult r;
    r.name = "Exponential(" + std::to_string(lam) + ")";
    r.mean = 1 / lam;
    r.variance = 1 / (lam * lam);
    r.std = 1 / lam;
    r.pdf = std::to_string(lam) + "·e^(-" + std::to_string(lam) + "x), x ≥ 0";
    return r;
}

DistributionResult normal_dist(double mu, double sigma) {
    if (sigma <= 0) throw std::invalid_argument("σ 必须 > 0");
    DistributionResult r;
    r.name = "Normal(" + std::to_string(mu) + ", " + std::to_string(sigma) + "²)";
    r.mean = mu;
    r.variance = sigma * sigma;
    r.std = sigma;
    r.pdf = "(1/(√(2π)·" + std::to_string(sigma) +
            "))·exp(-(x-" + std::to_string(mu) + ")²/(2·" + std::to_string(sigma) +
            "²))";
    return r;
}

}  // namespace mf::probability
