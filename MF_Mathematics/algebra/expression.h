// expression.h — 代数式:化简、展开、因式分解、分式、根式运算。
#pragma once

#include <string>


namespace mf::algebra {

// 合并同类项/化简多项式(优先完全平方或二次因式)。
std::string simplify_polynomial(const std::string& expr);

// 去括号展开。
std::string expand_expression(const std::string& expr);

// 综合因式分解(二次可分解时用根式分解,否则展开)。
std::string factor(const std::string& expr);

// 提公因式(等价于 factor)。
std::string factor_common(const std::string& expr);

// 完全平方分解。
std::string factor_perfect_square(const std::string& expr);

// 平方差分解。
std::string factor_difference_squares(const std::string& expr);

// 十字相乘分解。
std::string factor_cross(const std::string& expr);

// 分组分解。
std::string factor_group(const std::string& expr);

// 约分。
std::string simplify_fraction(const std::string& expr);

// 通分:返回两个新分式与公分母。
struct CommonDenominatorResult {
    std::string new1;
    std::string new2;
    std::string den;
};
CommonDenominatorResult common_denominator(const std::string& e1,
                                                  const std::string& e2);

// 分式四则运算(op ∈ + - * /)。
std::string fraction_operations(const std::string& e1,
                                       const std::string& op,
                                       const std::string& e2);

// 分母有理化。
std::string rationalize_denominator(const std::string& expr);

// 化简根式(sqrt(8) → 2*sqrt(2))。
std::string simplify_radical(const std::string& expr);

// 同类根式判断。
struct LikeRadicalsResult {
    bool is_like = false;
    std::string radical1;
    std::string radical2;
};
LikeRadicalsResult like_radicals(const std::string& e1,
                                        const std::string& e2);

// 根式四则运算。
std::string radical_operations(const std::string& e1,
                                      const std::string& op,
                                      const std::string& e2);

}  // namespace mf::algebra
