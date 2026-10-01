#include "arithmetic_functions.h"
#include "number_theory_internal.h"

#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

namespace mf::number_theory {

long long euler_phi(long long n) {
    if (n <= 0) throw std::invalid_argument("n 必须为正整数");
    // φ(n) = n ∏_{p|n} (1 - 1/p),p 跑遍 n 的互异质因数。
    long long result = n;
    long long temp = n;
    for (long long p = 2; p <= temp / p; p += (p == 2 ? 1 : 2)) {
        if (temp % p != 0) continue;
        while (temp % p == 0) temp /= p;
        result -= result / p;
    }
    if (temp > 1) result -= result / temp;
    return result;
}

long long divisor_count(long long n) {
    if (n <= 0) throw std::invalid_argument("n 必须为正整数");
    // τ(n) = ∏ (a_i + 1),其中 n = ∏ p_i^{a_i}。
    long long count = 1;
    for (const auto& [p, e] : detail::factorize(n)) {
        count *= (e + 1);
    }
    return count;
}

long long divisor_sum(long long n) {
    if (n <= 0) throw std::invalid_argument("n 必须为正整数");
    // σ(n) = ∏ (1 + p + p² + ... + p^e),增量计算防溢出。
    long long sum = 1;
    for (const auto& [p, e] : detail::factorize(n)) {
        long long term = 1;
        long long acc = 1;
        for (long long i = 0; i < e; ++i) {
            if (term > std::numeric_limits<long long>::max() / p)
                throw std::overflow_error("σ(n) 计算溢出");
            term *= p;
            if (acc > std::numeric_limits<long long>::max() - term)
                throw std::overflow_error("σ(n) 计算溢出");
            acc += term;
        }
        if (sum > std::numeric_limits<long long>::max() / acc)
            throw std::overflow_error("σ(n) 计算溢出");
        sum *= acc;
    }
    return sum;
}

long long mobius(long long n) {
    if (n <= 0) throw std::invalid_argument("n 必须为正整数");
    if (n == 1) return 1;
    long long temp = n;
    long long prime_count = 0;
    for (long long d = 2; d <= temp / d; d += (d == 2 ? 1 : 2)) {
        if (temp % d != 0) continue;
        temp /= d;
        if (temp % d == 0) return 0;  // 含平方因子
        ++prime_count;
    }
    if (temp > 1) ++prime_count;
    return (prime_count % 2 == 0) ? 1 : -1;
}

long long mobius_prefix(long long n) {
    if (n <= 0) throw std::invalid_argument("n 必须为正整数");
    if (n > 10'000'000)
        throw std::domain_error("n 过大,Mertens 函数仅支持 n ≤ 10,000,000");
    // 线性筛求 μ(1..n) 并累加。
    std::vector<std::int32_t> mu(n + 1, 0);
    std::vector<std::int32_t> primes;
    primes.reserve(static_cast<std::size_t>(n / 10));
    std::vector<bool> composite(n + 1, false);
    mu[1] = 1;
    long long sum = 1;  // μ(1)
    for (long long i = 2; i <= n; ++i) {
        if (!composite[static_cast<std::size_t>(i)]) {
            primes.push_back(static_cast<std::int32_t>(i));
            mu[static_cast<std::size_t>(i)] = -1;
        }
        for (std::int32_t p : primes) {
            long long v = i * static_cast<long long>(p);
            if (v > n) break;
            composite[static_cast<std::size_t>(v)] = true;
            if (i % p == 0) {
                mu[static_cast<std::size_t>(v)] = 0;
                break;
            }
            mu[static_cast<std::size_t>(v)] = -mu[static_cast<std::size_t>(i)];
        }
        sum += mu[static_cast<std::size_t>(i)];
    }
    return sum;
}

}  // namespace mf::number_theory
