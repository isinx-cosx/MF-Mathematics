// number_theory.h — 数与运算(algebra 包):运算律、绝对值、比例百分比、科学记数法。
#pragma once

#include <string>

#include "../mf_export.h"

namespace mf::algebra {

// 运算律验证结果:左式、右式、是否成立(容差 1e-12)。
struct LawResult {
    double left;
    double right;
    bool holds;
};

// 交换律 a op b == b op a,op ∈ {'+', '*'};其他 op 抛 std::invalid_argument。
MF_API LawResult commutative_law(double a, double b, const std::string& op);
// 结合律 (a op b) op c == a op (b op c)。
MF_API LawResult associative_law(double a, double b, double c,
                                 const std::string& op);
// 分配律 a*(b+c) == a*b + a*c。
MF_API LawResult distributive_law(double a, double b, double c);

MF_API double abs_value(double x);
MF_API double distance_on_number_line(double a, double b);

// 化简比例 a:b 为最简整数比。整数输入精确;浮点输入经连分数有理化。
struct Ratio {
    long long num;
    long long den;
};
MF_API Ratio ratio(double a, double b);

// 部分占整体的百分比(四舍五入到 4 位小数)。total == 0 抛异常。
MF_API double percentage(double part, double total);

// 新旧值变化率 %(四舍五入到 4 位小数)。old == 0 抛异常。
MF_API double percentage_change(double old_value, double new_value);

// 科学记数法:x = coefficient × 10^exponent,coefficient ∈ [1, 10)。
struct ScientificNotation {
    double coefficient;
    long long exponent;
};
MF_API ScientificNotation to_scientific_notation(double x);

// 保留 n 位有效数字。
MF_API double significant_figures(double x, long long n);

}  // namespace mf::algebra
