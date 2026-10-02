// function_limit.h — ε-δ、连续性、一致连续、间断点分类、最值、介值。
#pragma once

#include <string>


namespace mf::real_analysis {

// ε-δ 演示:极限 L 与估算 δ。
struct EpsDeltaResult {
    double L = 0.0;
    double delta = 0.0;
};
EpsDeltaResult limit_epsilon_delta(const std::string& expr, double point,
                                          double epsilon);

// 在某点的连续性。
bool real_is_continuous(const std::string& expr, double point);

// 区间上的一致连续性(无奇点即一致连续)。
bool uniform_continuity(const std::string& expr, double a, double b);

// 间断点分类:"连续（非间断点）"/"可去间断点"/"无穷间断点"/"跳跃间断点"/"振荡间断点"。
std::string real_discontinuity_classify(const std::string& expr,
                                               double point);

// 最值定理:闭区间上的最值(端点 + 驻点)。
struct ExtremeValueResult {
    double max = 0.0;
    double min = 0.0;
    double max_point = 0.0;
    double min_point = 0.0;
};
ExtremeValueResult extreme_value(const std::string& expr, double a, double b);

// 介值定理:∃ξ ∈ (a,b) 使 f(ξ)=c。不满足条件返回 NaN。
double intermediate_value(const std::string& expr, double a, double b,
                                 double value);

}  // namespace mf::real_analysis
