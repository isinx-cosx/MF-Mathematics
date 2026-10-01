// function.h — 函数:三要素、一次/反比例/二次函数、幂/指数/对数函数、三角函数初步。
//
// domain 用 SymEngine 提取分母零点与偶次根式约束;其余为数值/静态分析。

#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::algebra {

// 求定义域:返回描述字符串,如 "x ≠ 2" / "x ≥ 1" / "x ∈ R (全体实数)"。
MF_API std::string domain(const std::string& expr, const std::string& var);

// 值域估算(数值采样 + 临界点),返回 "[min, max]" 形式。
MF_API std::string range_estimate(const std::string& expr,
                                  const std::string& var);

// 函数类型分类:多项式函数 / 有理函数 / 含根式函数 / 对数函数 / 指数函数 / 代数表达式。
MF_API std::string correspondence_rule(const std::string& expr);

// 一次函数表达式字符串,如 "y = 2*x + 3"。
MF_API std::string linear_function(double k, double b);

// 斜率与截距的几何意义。
struct SlopeInterceptResult {
    double slope = 0.0;
    double intercept = 0.0;
    double angle_degrees = 0.0;
    std::string x_intercept;  // -b/k,垂直/不存在时为 "不存在"
};
MF_API SlopeInterceptResult slope_intercept(double k, double b);

// 反比例函数 y = k/x 描述字符串。
MF_API std::string inverse_proportional(double k);

// 二次函数 y = ax² + bx + c 分析。
struct QuadraticResult {
    double vertex_x = 0.0;
    double vertex_y = 0.0;
    std::string axis;        // "x = ..."
    std::string direction;   // 向上 / 向下
    double y_intercept = 0.0;
    std::string x_intercepts;  // 与 x 轴交点描述
};
MF_API QuadraticResult quadratic_function(double a, double b, double c);

// 二次函数最值。
struct ExtremaResult {
    std::string type;  // 最小值 / 最大值
    double x = 0.0;
    double value = 0.0;
};
MF_API ExtremaResult quadratic_extrema(double a, double b, double c);

// 幂函数:base 为数字时求值,为符号名时返回表达式字符串。
struct PowerResult {
    bool numeric = false;
    double value = 0.0;
    std::string expr;
};
MF_API PowerResult power_function(const std::string& base, double n);

// 指数函数值。
MF_API double exponential_function(double base, double x);

// 对数函数值。
MF_API double log_function(double base, double x);

// 三角函数值(mode: degrees / radians)。
struct TrigResult {
    double sin_val = 0.0;
    double cos_val = 0.0;
    double tan_val = 0.0;
};
MF_API TrigResult sine_cosine_tangent(double angle, const std::string& mode);

// 三角函数诱导公式列表。
MF_API std::vector<std::string> trig_basic_identities();

// 三角函数周期性。
struct PeriodicityResult {
    std::string period;
    std::string frequency;
    std::string description;
};
MF_API PeriodicityResult trig_periodicity(const std::string& func);

}  // namespace mf::algebra
