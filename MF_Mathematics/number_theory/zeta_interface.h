// zeta_interface.h — ζ 函数接口:欧拉乘积、Dirichlet 级数、L 函数、伯努利数。
#pragma once

#include <cstddef>
#include <vector>


namespace mf::number_theory {

// 欧拉乘积公式部分逼近:∏_{p≤P} (1 - p^{-s})^{-1} → ζ(s)(Re(s) > 1 时)。
double euler_product(double s, long long prime_limit = 100);

// ζ(s) 的 Dirichlet 级数部分和:Σ_{n=1}^{N} n^{-s}。
double zeta_dirichlet_series(double s, long long n_terms = 10000);

// Dirichlet L 函数 L(s, χ) 的部分和:Σ χ(n) n^{-s}。
// chi 为 nullptr 时使用默认模 4 特征 χ₋₄:χ(偶)=0,χ(n≡1 mod 4)=1,χ(n≡3 mod 4)=-1;
// 否则 chi 长度为 conductor,χ(n) = chi[n % conductor]。
double dirichlet_l_function(double s,
                                   const std::vector<long long>* chi = nullptr,
                                   long long n_terms = 1000,
                                   long long conductor = 4);

// 精确有理数(已约分,分母 > 0)。若无法以 long long 表示则降级为浮点。
struct BernoulliResult {
    bool is_approx;   // true = 精确分子分母超出 long long,降级为浮点近似
    long long num;    // is_approx == false 时有效
    long long den;    // is_approx == false 时有效
    double approx;    // is_approx == true 时有效
};

// 第 n 个伯努利数 B_n。精确优先,溢出时降级为浮点近似并置 is_approx。
BernoulliResult bernoulli_number(long long n);

// ζ(-n) = -B_{n+1} / (n+1)(精确分数,溢出时降级为浮点近似)。
BernoulliResult zeta_negative(long long n);

}  // namespace mf::number_theory
