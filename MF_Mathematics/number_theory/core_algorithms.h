// core_algorithms.h — 数论核心算法:欧几里得、扩展欧几里得、模逆元、快速幂取模。
#pragma once


namespace mf::number_theory {

// 最大公约数(欧几里得算法)。结果非负。
long long gcd(long long a, long long b);

// 扩展欧几里得:返回 (g, x, y) 满足 a*x + b*y = g = gcd(a, b)。
struct ExtendedGcd {
    long long g;
    long long x;
    long long y;
};
ExtendedGcd extended_gcd(long long a, long long b);

// a 模 m 的乘法逆元,要求 gcd(a, m) = 1,返回 [0, m) 内的唯一解;
// 逆元不存在时抛 std::invalid_argument。
long long mod_inverse(long long a, long long m);

// base^exp mod mod,exp >= 0,mod > 0。使用二进制快速幂。
long long mod_pow(long long base, long long exp, long long mod);

}  // namespace mf::number_theory
