#include "modular_arithmetic.h"

#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <unordered_map>

#include "arithmetic_functions.h"
#include "core_algorithms.h"
#include "number_theory_internal.h"

namespace mf::number_theory {

namespace {

// 无符号版乘模,用于 M 可能接近 2^63 的 CRT 大数运算。
using u64 = unsigned long long;
inline u64 mul_mod_u64(u64 a, u64 b, u64 m) {
    a %= m;
    u64 r = 0;
    while (b) {
        if (b & 1) r = (r + a) % m;
        a = (a * 2) % m;
        b >>= 1;
    }
    return r;
}

// 无符号乘法,溢出返回 false
inline bool mul_u64(u64 a, u64 b, u64& out) {
    if (b != 0 && a > std::numeric_limits<u64>::max() / b) return false;
    out = a * b;
    return true;
}

// 把值归一到 [0, m) 的非负余数。
inline long long positive_mod(long long v, long long m) {
    long long r = v % m;
    return r < 0 ? r + m : r;
}

}  // namespace

long long crt(const std::vector<long long>& residues,
              const std::vector<long long>& moduli) {
    if (residues.size() != moduli.size())
        throw std::invalid_argument("余数个数与模数个数不一致");
    if (residues.empty())
        throw std::invalid_argument("至少需要一个同余方程");
    for (std::size_t i = 0; i < moduli.size(); ++i) {
        if (moduli[i] <= 0) throw std::invalid_argument("模数必须为正整数");
        for (std::size_t j = i + 1; j < moduli.size(); ++j) {
            if (gcd(moduli[i], moduli[j]) != 1)
                throw std::invalid_argument("模数两两不互素,CRT 无解");
        }
    }

    // 模数乘积 M 必须能放进 long long,否则结果 x < M 无法表示
    u64 M = 1;
    for (long long m : moduli) {
        u64 t;
        if (!mul_u64(M, static_cast<u64>(m), t) ||
            t > static_cast<u64>(std::numeric_limits<long long>::max())) {
            throw std::overflow_error("模数乘积超过 long long 范围,CRT 结果无法表示");
        }
        M = t;
    }

    u64 x = 0;
    for (std::size_t i = 0; i < residues.size(); ++i) {
        const u64 m = static_cast<u64>(moduli[i]);
        const u64 Mi = M / m;
        // Mi 模 m 的逆元(两两互素保证存在)
        long long inv =
            mod_inverse(static_cast<long long>(Mi % m), moduli[i]);
        long long r = positive_mod(residues[i], moduli[i]);
        u64 term = mul_mod_u64(mul_mod_u64(static_cast<u64>(r), Mi, M),
                               static_cast<u64>(inv), M);
        x = (x + term) % M;
    }
    return static_cast<long long>(x);
}

long long primitive_root(long long p) {
    if (p < 2) throw std::invalid_argument("模数必须 ≥2");
    if (p == 2) return 1;
    if (p == 4) return 3;

    // 原根存在的必要形式:2, 4, p^k, 2p^k(p 为奇素数)。照 Python 检查。
    long long temp = p;
    if (temp % 2 == 0) {
        temp /= 2;
        if (temp % 2 == 0)
            throw std::invalid_argument("模 p 不存在原根(含因子 2²)");
    }

    const long long phi = euler_phi(p);
    std::vector<long long> phi_factors;
    for (const auto& [q, e] : detail::factorize(phi)) {
        (void)e;
        phi_factors.push_back(q);
    }

    for (long long g = 2; g < p; ++g) {
        if (gcd(g, p) != 1) continue;
        bool is_primitive = true;
        for (long long q : phi_factors) {
            if (detail::pow_mod(g, phi / q, p) == 1) {
                is_primitive = false;
                break;
            }
        }
        if (is_primitive) return g;
    }
    throw std::invalid_argument("模 p 不存在原根或搜索失败");
}

long long discrete_log(long long g, long long h, long long p) {
    if (p <= 1) throw std::invalid_argument("模数必须 ≥2");
    const long long g_mod = positive_mod(g, p);
    const long long h_mod = positive_mod(h, p);
    if (g_mod == 0) throw std::invalid_argument("底数必须与模数互素");
    if (h_mod == 1) return 0;

    // m = ⌈√p⌉
    const long long m = static_cast<long long>(std::sqrt(static_cast<long double>(p))) + 1;

    // 大步小步(Baby-step Giant-step):g^(i*m) * g^j = h
    std::unordered_map<long long, long long> baby;
    long long cur = 1;
    for (long long j = 0; j < m; ++j) {
        if (!baby.count(cur)) baby[cur] = j;
        cur = detail::mul_mod(cur, g_mod, p);
    }

    // g^{-m} = (g^{-1})^m;g^{-1} = g^{p-2}(p 为素数,费马小定理)
    const long long g_inv = detail::pow_mod(g_mod, p - 2, p);
    const long long g_inv_m = detail::pow_mod(g_inv, m, p);

    long long gamma = h_mod;
    for (long long i = 0; i < m; ++i) {
        auto it = baby.find(gamma);
        if (it != baby.end()) {
            const long long x = i * m + it->second;
            if (detail::pow_mod(g_mod, x, p) == h_mod) return x;
        }
        gamma = detail::mul_mod(gamma, g_inv_m, p);
    }
    throw std::invalid_argument("未找到满足 g^x ≡ h (mod p) 的解");
}

}  // namespace mf::number_theory
