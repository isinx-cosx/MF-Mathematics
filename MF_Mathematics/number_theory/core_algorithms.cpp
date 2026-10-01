#include "core_algorithms.h"
#include "number_theory_internal.h"

#include <cstdint>
#include <numeric>
#include <stdexcept>

namespace mf::number_theory {

long long gcd(long long a, long long b) { return std::gcd(a, b); }

ExtendedGcd extended_gcd(long long a, long long b) {
    // 迭代版扩展欧几里得,保持贝祖系数整数不变式。
    long long old_r = a, r = b;
    long long old_s = 1, s = 0;
    long long old_t = 0, t = 1;
    while (r != 0) {
        long long q = old_r / r;
        long long nr = old_r - q * r;
        long long ns = old_s - q * s;
        long long nt = old_t - q * t;
        old_r = r;
        r = nr;
        old_s = s;
        s = ns;
        old_t = t;
        t = nt;
    }
    long long g = old_r, x = old_s, y = old_t;
    if (g < 0) {  // 对齐 Python 语义:gcd 非负
        g = -g;
        x = -x;
        y = -y;
    }
    return {g, x, y};
}

long long mod_inverse(long long a, long long m) {
    if (m <= 0) throw std::invalid_argument("模数 m 必须为正整数");
    ExtendedGcd eg = extended_gcd(a, m);
    if (eg.g != 1)
        throw std::invalid_argument("gcd(a, m) ≠ 1,逆元不存在(需互素)");
    long long inv = eg.x % m;
    if (inv < 0) inv += m;
    return inv;
}

long long mod_pow(long long base, long long exp, long long mod) {
    if (mod <= 0) throw std::invalid_argument("模数 mod 必须为正整数");
    if (exp < 0) throw std::invalid_argument("指数 exp 必须为非负整数");
    return detail::pow_mod(base, exp, mod);
}

}  // namespace mf::number_theory
