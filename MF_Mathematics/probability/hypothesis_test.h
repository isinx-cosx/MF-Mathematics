// hypothesis_test.h — Z 检验、t 检验、卡方检验、p 值计算。
#pragma once

#include <string>
#include <vector>


namespace mf::probability {

struct HypothesisResult {
    double statistic = 0.0;    // Z / t / χ²
    double p_value = 0.0;
    long long df = 0;
    double alpha = 0.05;
    double critical_value = 0.0;
    bool reject_H0 = false;
    std::string alternative;
};

// 单样本 Z 检验(总体方差已知)。
HypothesisResult z_test(double sample_mean, double mu0, double sigma,
                               long long n, double alpha,
                               const std::string& alternative);

// 单样本 t 检验(总体方差未知)。
HypothesisResult t_test(const std::vector<double>& data, double mu0,
                               double alpha,
                               const std::string& alternative);

// 卡方拟合优度检验 χ² = Σ(Oi-Ei)²/Ei。
struct ChiSquareResult {
    double chi2 = 0.0;
    long long df = 0;
    double p_value = 0.0;
    std::vector<double> contributions;
    bool reject_H0 = false;
};
ChiSquareResult chi_square_test(const std::vector<double>& observed,
                                       const std::vector<double>& expected);

// p 值计算:分布 "normal"/"t"/"chi2"。
double p_value(double test_statistic, const std::string& dist, long long df,
                      const std::string& alternative);

}  // namespace mf::probability
