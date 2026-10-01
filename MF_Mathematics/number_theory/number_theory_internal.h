// number_theory_internal.h — number_theory 包共享的内部数论辅助(仅头文件)。
//
// 仅供本包各 .cpp 内部使用,不构成公共 API。包含:
//   mul_mod     — 无溢出乘模(可移植,MSVC 无 __int128 也能用)
//   pow_mod     — 快速幂取模
//   factorize   — 试除法质因数分解,返回排序后的 [(质因数, 指数)]
//   is_prime_ll — 米勒-拉宾确定性素性测试(n < 2^64 全部正确)

#pragma once

#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

namespace mf::number_theory::detail {

// (a * b) % m,要求 0 <= a, b < m 且 m <= LLONG_MAX。避免中间积溢出。
inline long long mul_mod(long long a, long long b, long long m) {
#if defined(__SIZEOF_INT128__)
    return static_cast<long long>((static_cast<__int128>(a) * b) % m);
#else
    // 二进制长乘:每一步加法/倍乘都 < 2m,不溢出 unsigned long long。
    using u64 = unsigned long long;
    u64 aa = static_cast<u64>(a % m);
    u64 bb = static_cast<u64>(b % m);
    u64 mm = static_cast<u64>(m);
    u64 r = 0;
    while (bb) {
        if (bb & 1) r = (r + aa) % mm;
        aa = (aa * 2) % mm;
        bb >>= 1;
    }
    return static_cast<long long>(r);
#endif
}

// base^exp mod mod,exp >= 0,mod > 0。
inline long long pow_mod(long long base, long long exp, long long mod) {
    if (mod <= 0) throw std::invalid_argument("模数必须为正整数");
    if (mod == 1) return 0;
    base %= mod;
    if (base < 0) base += mod;
    long long r = 1;
    while (exp > 0) {
        if (exp & 1) r = mul_mod(r, base, mod);
        base = mul_mod(base, base, mod);
        exp >>= 1;
    }
    return r;
}

// 试除法质因数分解。n < 2 时返回空表。结果按质因数升序排列。
inline std::vector<std::pair<long long, long long>> factorize(long long n) {
    std::vector<std::pair<long long, long long>> factors;
    if (n < 2) return factors;
    long long temp = n;
    long long count = 0;
    while (temp % 2 == 0) {
        temp /= 2;
        ++count;
    }
    if (count) factors.emplace_back(2, count);
    for (long long d = 3; d <= temp / d; d += 2) {
        if (temp % d != 0) continue;
        count = 0;
        while (temp % d == 0) {
            temp /= d;
            ++count;
        }
        factors.emplace_back(d, count);
    }
    if (temp > 1) factors.emplace_back(temp, 1);
    return factors;
}

// 确定性米勒-拉宾:对任意 n < 2^64 判定正确(基底 2, 325, 9375, 28178,
// 450775, 9780504, 1795265022)。long long 上限约 9.2e18 < 2^64,全覆盖。
inline bool is_prime_ll(long long n) {
    if (n < 2) return false;
    if (n < 4) return true;
    if (n % 2 == 0) return false;
    long long d = n - 1;
    int s = 0;
    while ((d & 1) == 0) {
        d >>= 1;
        ++s;
    }
    static const long long bases[] = {2, 325, 9375, 28178, 450775,
                                      9780504, 1795265022};
    for (long long a : bases) {
        if (a % n == 0) continue;
        long long x = pow_mod(a, d, n);
        if (x == 1 || x == n - 1) continue;
        bool composite = true;
        for (int i = 0; i < s - 1; ++i) {
            x = mul_mod(x, x, n);
            if (x == n - 1) {
                composite = false;
                break;
            }
        }
        if (composite) return false;
    }
    return true;
}

}  // namespace mf::number_theory::detail
