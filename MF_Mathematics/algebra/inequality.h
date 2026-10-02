// inequality.h — 不等式性质、一元一次/二次/不等式组求解、均值不等式。
#pragma once

#include <string>
#include <vector>


namespace mf::algebra {

// 不等式基本性质演示:加减/乘除 c 时方向变化。
std::vector<std::string> inequality_properties(double a, double b,
                                                      double c);

// 一元一次不等式:返回解集区间字符串。
std::string solve_linear_inequality(const std::string& expr);

// 一元一次不等式组(取交集)。
std::string solve_inequality_system(
    const std::vector<std::string>& ineqs);

// 一元二次不等式。
std::string solve_quadratic_inequality(const std::string& expr);

// 均值不等式:AM = (a+b)/2, GM = √(ab)。
struct AmGmResult {
    double AM = 0.0;
    double GM = 0.0;
};
AmGmResult am_gm_inequality(double a, double b);

// 最值与均值关系:min ≤ GM ≤ AM ≤ max。
struct MaxMinResult {
    double min = 0.0;
    double max = 0.0;
    double GM = 0.0;
    double AM = 0.0;
};
MaxMinResult max_min_initial(double a, double b);

}  // namespace mf::algebra
