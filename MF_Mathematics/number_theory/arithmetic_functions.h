// arithmetic_functions.h — 数论函数:欧拉 φ、除数函数 τ/σ、莫比乌斯 μ。
#pragma once

#include "../mf_export.h"

namespace mf::number_theory {

// 欧拉函数 φ(n):不超过 n 且与 n 互素的正整数个数。
// 要求 n >= 1,否则抛 std::invalid_argument。
MF_API long long euler_phi(long long n);

// 除数函数 τ(n):n 的正约数个数。
MF_API long long divisor_count(long long n);

// 除数和函数 σ(n):n 的所有正约数之和。
MF_API long long divisor_sum(long long n);

// 莫比乌斯函数 μ(n):μ(1)=1;无平方因子且恰有 k 个互异质因数时为 (-1)^k;
// 含平方因子时为 0。要求 n >= 1。
MF_API long long mobius(long long n);

// Mertens 函数 M(n) = Σ_{k=1}^{n} μ(k)。仅支持 n <= 10,000,000,
// 超出抛 std::domain_error。
MF_API long long mobius_prefix(long long n);

}  // namespace mf::number_theory
