// continued_fractions.h — 连分数:展开、渐近分数序列、最佳有理逼近。
#pragma once

#include <vector>

#include "../mf_export.h"

namespace mf::number_theory {

// 实数 x 的连分数展开,返回系数列表 [a0; a1, a2, ...](最多 n_terms 项)。
// x 为 inf/nan 或 n_terms <= 0 时抛 std::invalid_argument。
MF_API std::vector<long long> continued_fraction(double x,
                                                 long long n_terms = 20);

// 一个渐近分数 C_n = p_n / q_n 及其浮点近似值。
struct Convergent {
    long long p;
    long long q;
    double approx;
};

// 由连分数系数计算渐近分数序列。系数列表为空时抛 std::invalid_argument。
MF_API std::vector<Convergent> convergents(const std::vector<long long>& frac);

// 分母不超过 max_denom 时的最佳有理逼近 p/q。
struct RationalApprox {
    long long p;
    long long q;
    double approx;
};

MF_API RationalApprox best_rational_approximation(double x,
                                                  long long max_denom = 1000000);

}  // namespace mf::number_theory
