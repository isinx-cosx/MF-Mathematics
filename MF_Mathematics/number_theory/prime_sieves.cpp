#include "prime_sieves.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

#include "number_theory_internal.h"

namespace mf::number_theory {

std::vector<long long> eratosthenes(long long n) {
    std::vector<long long> primes;
    if (n < 2) return primes;
    std::vector<bool> is_prime(static_cast<std::size_t>(n) + 1, true);
    is_prime[0] = is_prime[1] = false;
    for (long long i = 2; i <= n / i; ++i) {
        if (!is_prime[static_cast<std::size_t>(i)]) continue;
        for (long long j = i * i; j <= n; j += i)
            is_prime[static_cast<std::size_t>(j)] = false;
    }
    for (long long i = 2; i <= n; ++i)
        if (is_prime[static_cast<std::size_t>(i)]) primes.push_back(i);
    return primes;
}

std::vector<long long> segmented_sieve(long long n, long long segment_size) {
    std::vector<long long> primes;
    if (n < 2) return primes;
    if (segment_size < 1) segment_size = 1;

    // 第 1 步:筛出 ≤√n 的小素数。
    const long long limit =
        static_cast<long long>(std::sqrt(static_cast<long double>(n)));
    std::vector<long long> small = eratosthenes(limit);
    primes = small;

    // 第 2 步:分段筛 [low, high] 内的合数。
    long long low = std::max(limit + 1, 2LL);
    while (low <= n) {
        const long long high =
            (n - low < segment_size - 1) ? n : low + segment_size - 1;
        const long long len = high - low + 1;
        std::vector<bool> seg(static_cast<std::size_t>(len), true);
        for (long long p : small) {
            // 无符号计算,避免 low + p - 1 溢出。
            const unsigned long long ulow = static_cast<unsigned long long>(low);
            const unsigned long long ustart = std::max(
                static_cast<unsigned long long>(p) * p,
                ((ulow + static_cast<unsigned long long>(p - 1)) /
                 static_cast<unsigned long long>(p)) *
                    static_cast<unsigned long long>(p));
            if (ustart > static_cast<unsigned long long>(high)) continue;
            const long long start = static_cast<long long>(ustart);
            for (long long j = start; j <= high; j += p)
                seg[static_cast<std::size_t>(j - low)] = false;
        }
        for (long long i = 0; i < len; ++i)
            if (seg[static_cast<std::size_t>(i)]) primes.push_back(low + i);
        low = high + 1;
    }
    return primes;
}

bool is_prime(long long n) { return detail::is_prime_ll(n); }

std::vector<std::pair<long long, long long>> prime_factors(long long n) {
    if (n < 2) return {};
    return detail::factorize(n);
}

}  // namespace mf::number_theory
