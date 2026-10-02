// distributions.h — 经典分布族:伯努利/二项/泊松/均匀/指数/正态。
#pragma once

#include <string>
#include <vector>


namespace mf::probability {

struct DistributionResult {
    std::string name;
    double mean = 0.0;
    double variance = 0.0;
    double std = 0.0;
    std::string pdf;  // 密度/分布列描述
    std::vector<long long> pmf_keys;
    std::vector<double> pmf_values;
};

DistributionResult bernoulli(double p);
DistributionResult binomial(long long n, double p);
DistributionResult poisson(double lam);
DistributionResult uniform_dist(double a, double b);
DistributionResult exponential_dist(double lam);
DistributionResult normal_dist(double mu, double sigma);

}  // namespace mf::probability
