// nonparametric.h — 非参数检验:Mann-Whitney U、Kruskal-Wallis、Wilcoxon 符号秩。
#pragma once

#include <string>
#include <vector>


namespace mf::probability {

struct NonparametricResult {
    double statistic = 0.0;    // U / H / W
    double p_value = 0.0;
    bool significant = false;
    double alpha = 0.05;
    std::string test_type;     // "Mann-Whitney"/"Kruskal-Wallis"/"配对"/"单样本"
    long long n1 = 0;
    long long n2 = 0;
    double median1 = 0.0;
    double median2 = 0.0;
};

// Mann-Whitney U 检验(两独立样本)。
NonparametricResult mann_whitney_u(const std::vector<double>& group1,
                                          const std::vector<double>& group2,
                                          const std::string& alternative,
                                          double alpha);

// Kruskal-Wallis H 检验(≥3 组独立样本)。
struct KruskalWallisResult {
    double H = 0.0;
    double p_value = 0.0;
    bool significant = false;
    double alpha = 0.05;
    std::vector<double> group_medians;
    std::vector<double> mean_ranks;
};
KruskalWallisResult kruskal_wallis(
    const std::vector<std::vector<double>>& groups, double alpha);

// Wilcoxon 符号秩检验(配对或单样本)。
NonparametricResult wilcoxon_signed_rank(
    const std::vector<double>& group1, const std::vector<double>& group2,
    double mu, const std::string& alternative, double alpha);

}  // namespace mf::probability
