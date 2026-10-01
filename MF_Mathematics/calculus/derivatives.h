// derivatives.h — 导数(基于 SymEngine 符号计算):求导、某点导数值、隐函数、参数方程、微分。
#pragma once

#include <string>

#include "../mf_export.h"

namespace mf::calculus {

// 求导(支持高阶),返回导数表达式字符串。order ≥ 1。
MF_API std::string diff(const std::string& expr, const std::string& var = "x",
                        long long order = 1);

// 在某点求导数值。
MF_API double diff_at(const std::string& expr, const std::string& var,
                      double point, long long order = 1);

// 在某点求导，**含参数时给符号结果**（如 a*x^2 在 x=2 处 → "4*a"）。
// 不含参数时给数值文本（%.17g）。调用方据返回值决定是数字还是字符串。
MF_API std::string diff_at_str(const std::string& expr, const std::string& var,
                          double point, long long order = 1);

// 隐函数求导 dy/dx = -F_x/F_y。F_y = 0 时返回 "无法求解"。
MF_API std::string implicit_diff(const std::string& eq, const std::string& var,
                                 const std::string& dep_var);

// 参数方程求导 dy/dx = (dy/dt)/(dx/dt)。dx/dt = 0 时返回 "无穷大（切线垂直）"。
MF_API std::string parametric_diff(const std::string& x_expr,
                                   const std::string& y_expr,
                                   const std::string& t = "t");

// 微分 dy = f'(point)·dx。
MF_API double differential(const std::string& expr, const std::string& var,
                           double point, double dx);

}  // namespace mf::calculus
