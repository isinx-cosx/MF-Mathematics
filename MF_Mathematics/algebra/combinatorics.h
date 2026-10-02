// combinatorics.h — 计数与二项式:加法/乘法原理、排列组合、二项式定理。
#pragma once

#include <string>
#include <vector>


namespace mf::algebra {

// 加法原理:各类方法数之和。空列表返回 0。
long long addition_principle(const std::vector<long long>& ways);

// 乘法原理:各步骤方法数之积。空列表返回 1。
long long multiplication_principle(const std::vector<long long>& steps);

// 排列数 A(n,m) = n!/(n-m)!。要求 n,m ≥ 0 且 m ≤ n;
// 结果超出 long long 抛 std::overflow_error。
long long permutation(long long n, long long m);

// 组合数 C(n,m) = n!/(m!(n-m)!)。
long long combination(long long n, long long m);

// 常用组合恒等式(常量列表)。
std::vector<std::string> comb_identities();

// 二项式定理展开 (a+b)^n,返回展开式字符串。a、b 为已字符串化的项。
std::string binomial_expand(const std::string& a, const std::string& b,
                                   long long n);

// 二项式通项 T_{k+1} = C(n,k)·a^(n-k)·b^k(0-based 的 k)。
struct BinomialTerm {
    std::string term;
    long long coefficient;
    long long k;
    long long term_number;
};
BinomialTerm binomial_term(const std::string& a, const std::string& b,
                                  long long n, long long k);

}  // namespace mf::algebra
