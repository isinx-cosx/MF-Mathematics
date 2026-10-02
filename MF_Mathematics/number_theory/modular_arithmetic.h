// modular_arithmetic.h — 模算术与同余:中国剩余定理、原根、离散对数。
#pragma once

#include <cstddef>
#include <vector>


namespace mf::number_theory {

// 中国剩余定理:解同余方程组 x ≡ residues[i] (mod moduli[i]),要求模数两两互素。
// 返回最小非负解 x。模数不互素或参数不一致时抛 std::invalid_argument。
long long crt(const std::vector<long long>& residues,
                     const std::vector<long long>& moduli);

// 求模 p 的最小原根 g(当 p = 2, 4, p^k, 2p^k 时存在原根)。
// p < 2 或无原根时抛 std::invalid_argument。
long long primitive_root(long long p);

// 离散对数:求满足 g^x ≡ h (mod p) 的最小非负解 x(大步小步法)。
// p 应为素数,g 应为模 p 的生成元。无解时抛 std::invalid_argument。
long long discrete_log(long long g, long long h, long long p);

}  // namespace mf::number_theory
