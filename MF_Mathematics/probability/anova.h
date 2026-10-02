// anova.h — 单因素/双因素方差分析。
#pragma once

#include <vector>


namespace mf::probability {

// 单因素方差分析。
struct AnovaResult {
    double F = 0.0;
    double p_value = 0.0;
    bool significant = false;
    double alpha = 0.05;
    double ss_between = 0.0;
    double ss_within = 0.0;
    double ms_between = 0.0;
    double ms_within = 0.0;
    long long df_between = 0;
    long long df_within = 0;
    std::vector<double> group_means;
};
AnovaResult one_way_anova(const std::vector<std::vector<double>>& groups,
                                 double alpha);

// 双因素方差分析(无重复)。
struct TwoWayAnovaResult {
    double F_A = 0.0;
    double p_A = 0.0;
    bool significant_A = false;
    double F_B = 0.0;
    double p_B = 0.0;
    bool significant_B = false;
    double ss_row = 0.0;
    double ss_col = 0.0;
    double ss_error = 0.0;
    double ss_total = 0.0;
    bool valid = false;
};
TwoWayAnovaResult two_way_anova(const std::vector<std::vector<double>>& data,
                                       double alpha);

}  // namespace mf::probability
