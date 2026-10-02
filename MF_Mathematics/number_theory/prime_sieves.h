// prime_sieves.h — 素数分布与筛法:埃拉托斯特尼筛、分段筛、素性测试、质因数分解。
#pragma once

#include <utility>
#include <vector>


namespace mf::number_theory {

// 埃拉托斯特尼筛法:返回所有不超过 n 的素数(升序)。n < 2 时返回空表。
std::vector<long long> eratosthenes(long long n);

// 分段筛法:高效生成不超过 n 的全部素数。segment_size 控制每段内存(默认 100000)。
std::vector<long long> segmented_sieve(long long n,
                                              long long segment_size = 100000);

// 米勒-拉宾确定性素性测试:n < 2^64 全部正确判定。
bool is_prime(long long n);

// 质因数分解:返回 [(质因数, 指数), ...],按质因数升序。n < 2 时返回空表。
std::vector<std::pair<long long, long long>> prime_factors(long long n);

}  // namespace mf::number_theory
