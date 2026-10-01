// at_internal.h — algebraic_topology 包内部辅助(仅头文件)。
//
// 提供单纯复形的数据结构与基础运算:
//   Simplex  — 单形,顶点索引升序
//   Complex  — 复形,维数 → 单形列表
//   faces / boundary_matrix / integer_rank
//
// 边界矩阵 B_k : C_k → C_{k-1} 的元素为 {−1, 0, +1}(定向符号)。
// 贝蒂数由整数矩阵的精确秩给出(分式无关高斯消元)。

#pragma once

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <limits>
#include <map>
#include <numeric>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace mf::algebraic_topology {

using Simplex = std::vector<long long>;                    // 升序顶点索引
using Complex = std::map<long long, std::vector<Simplex>>; // dim → 单形列表

namespace detail {

// 归一化空间名:大写、去掉 '^' 与空白("S^2" / "s2" / "T 2" → "S2")。
inline std::string normalize_space(const std::string& space) {
    std::string out;
    for (char ch : space) {
        if (ch == '^' || std::isspace(static_cast<unsigned char>(ch))) continue;
        out.push_back(static_cast<char>(std::toupper(static_cast<unsigned char>(ch))));
    }
    return out;
}

// ── 溢出检测算术(整数秩消元用)──────────────────────────────────────────

// 有符号乘法,溢出返回 false。
inline bool mul_ll(long long a, long long b, long long& out) {
    const bool neg = (a < 0) ^ (b < 0);
    // |a| = -(a+1)+1(避免 a == LLONG_MIN 时 a+1 的语义,正确求绝对值)。
    const unsigned long long ua =
        a < 0 ? static_cast<unsigned long long>(-(a + 1)) + 1
              : static_cast<unsigned long long>(a);
    const unsigned long long ub =
        b < 0 ? static_cast<unsigned long long>(-(b + 1)) + 1
              : static_cast<unsigned long long>(b);
    if (ub != 0 && ua > std::numeric_limits<unsigned long long>::max() / ub)
        return false;
    const unsigned long long p = ua * ub;
    // 正结果最大 2^63-1;负结果最大 2^63(LLONG_MIN 可表示)。
    const unsigned long long limit =
        neg ? 0x8000000000000000ULL
            : static_cast<unsigned long long>(
                  std::numeric_limits<long long>::max());
    if (p > limit) return false;
    if (neg) {
        out = (p == 0x8000000000000000ULL)
                  ? std::numeric_limits<long long>::min()
                  : -static_cast<long long>(p);
    } else {
        out = static_cast<long long>(p);
    }
    return true;
}

// 有符号减法,溢出返回 false。
inline bool sub_ll(long long a, long long b, long long& out) {
    if (b > 0 && a < std::numeric_limits<long long>::min() + b) return false;
    if (b < 0 && a > std::numeric_limits<long long>::max() + b) return false;
    out = a - b;
    return true;
}

// 单形的所有 (dim-1) 维面:依次去掉一个顶点,其余顶点排序。
// 0/1-单形(顶点)没有面,返回空。
inline std::vector<Simplex> faces(const Simplex& s) {
    std::vector<Simplex> out;
    if (s.size() <= 1) return out;
    out.reserve(s.size());
    for (std::size_t i = 0; i < s.size(); ++i) {
        Simplex f = s;
        f.erase(f.begin() + static_cast<std::ptrdiff_t>(i));
        std::sort(f.begin(), f.end());
        out.push_back(std::move(f));
    }
    return out;
}

// 边界矩阵 B[面索引][单形索引]:第 j 个 k-单形的第 i 个面记符号 (-1)^i。
// 定向符号与顶点顺序相关,内部统一按升序归一化,不依赖调用方已排序。
inline std::vector<std::vector<long long>> boundary_matrix(
    const std::vector<Simplex>& dim_k, const std::vector<Simplex>& dim_km1) {
    const long long m = static_cast<long long>(dim_km1.size());
    const long long n = static_cast<long long>(dim_k.size());
    std::vector<std::vector<long long>> B(m, std::vector<long long>(n, 0));
    std::map<Simplex, long long> face_index;
    for (long long i = 0; i < m; ++i) {
        Simplex key = dim_km1[static_cast<std::size_t>(i)];
        std::sort(key.begin(), key.end());
        face_index[std::move(key)] = i;
    }
    for (long long j = 0; j < n; ++j) {
        Simplex sigma = dim_k[static_cast<std::size_t>(j)];
        std::sort(sigma.begin(), sigma.end());
        const std::vector<Simplex> fs = faces(sigma);
        for (std::size_t i = 0; i < fs.size(); ++i) {
            auto it = face_index.find(fs[i]);
            if (it != face_index.end())
                B[it->second][static_cast<std::size_t>(j)] = (i % 2 == 0) ? 1 : -1;
        }
    }
    return B;
}

// 整数矩阵的秩(有理数域上)。分式无关消元:行 i := 主元×行 i − 系数×主元行,
// 再按行内 gcd 归一化控制中间量增长。对 ±1 边界矩阵稳定精确;
// 中间量溢出(非 ±1 大元素矩阵)时抛 std::overflow_error,不静默算错。
inline long long integer_rank(std::vector<std::vector<long long>> A) {
    if (A.empty() || A[0].empty()) return 0;
    const long long rows = static_cast<long long>(A.size());
    const long long cols = static_cast<long long>(A[0].size());
    long long rank = 0;
    for (long long c = 0; c < cols && rank < rows; ++c) {
        long long p = -1;
        for (long long i = rank; i < rows; ++i)
            if (A[static_cast<std::size_t>(i)][static_cast<std::size_t>(c)] != 0) {
                p = i;
                break;
            }
        if (p == -1) continue;
        std::swap(A[static_cast<std::size_t>(rank)], A[static_cast<std::size_t>(p)]);
        const long long piv = A[static_cast<std::size_t>(rank)][static_cast<std::size_t>(c)];
        for (long long i = rank + 1; i < rows; ++i) {
            auto& row = A[static_cast<std::size_t>(i)];
            if (row[static_cast<std::size_t>(c)] == 0) continue;
            const long long q = row[static_cast<std::size_t>(c)];
            const auto& pr = A[static_cast<std::size_t>(rank)];
            for (long long j = c; j < cols; ++j) {
                long long t1, t2, diff;
                if (!mul_ll(row[static_cast<std::size_t>(j)], piv, t1) ||
                    !mul_ll(q, pr[static_cast<std::size_t>(j)], t2) ||
                    !sub_ll(t1, t2, diff)) {
                    throw std::overflow_error("整数秩计算中间量溢出,矩阵元素过大");
                }
                row[static_cast<std::size_t>(j)] = diff;
            }
            long long g = 0;
            for (long long j = c; j < cols; ++j)
                g = std::gcd(g, row[static_cast<std::size_t>(j)]);
            if (g != 0)
                for (long long j = c; j < cols; ++j)
                    row[static_cast<std::size_t>(j)] /= g;
        }
        ++rank;
    }
    return rank;
}

// 整数矩阵的 Smith 标准形不变因子(全部对角元,正数升序,含 1)。
// 纯整数行/列初等变换;中间量溢出或步数超界抛 std::overflow_error,不静默算错。
// 用途:对边界矩阵 ∂_k : C_k → C_{k-1},不变因子中 > 1 的那些正好是
//       torsion(coker ∂_k) 的循环因子,而 torsion(H_{k-1}) = torsion(coker ∂_k)
//       (因为 0 → H_{k-1} → C_{k-1}/im ∂_k → im ∂_{k-1} → 0 且 im ∂_{k-1} 自由,可分裂)。
//       这是从复形直接算出挠系数、并在此基础上做万有系数定理所必需的。
inline std::vector<long long> smith_invariants(std::vector<std::vector<long long>> A) {
    const long long m = static_cast<long long>(A.size());
    const long long n = m > 0 ? static_cast<long long>(A[0].size()) : 0;
    std::vector<long long> factors;
    if (m == 0 || n == 0) return factors;

    auto row_sub = [&A, n](long long i, long long j, long long q) {
        for (long long c = 0; c < n; ++c) {
            long long t1 = 0, d = 0;
            if (!mul_ll(q, A[static_cast<std::size_t>(j)][static_cast<std::size_t>(c)], t1) ||
                !sub_ll(A[static_cast<std::size_t>(i)][static_cast<std::size_t>(c)], t1, d))
                throw std::overflow_error("Smith 标准形中间量溢出,矩阵元素过大");
            A[static_cast<std::size_t>(i)][static_cast<std::size_t>(c)] = d;
        }
    };
    auto col_sub = [&A, m](long long i, long long j, long long q) {
        for (long long r = 0; r < m; ++r) {
            long long t1 = 0, d = 0;
            if (!mul_ll(q, A[static_cast<std::size_t>(r)][static_cast<std::size_t>(j)], t1) ||
                !sub_ll(A[static_cast<std::size_t>(r)][static_cast<std::size_t>(i)], t1, d))
                throw std::overflow_error("Smith 标准形中间量溢出,矩阵元素过大");
            A[static_cast<std::size_t>(r)][static_cast<std::size_t>(i)] = d;
        }
    };
    auto row_add = [&A, n](long long i, long long j) {
        for (long long c = 0; c < n; ++c) {
            const long long a = A[static_cast<std::size_t>(i)][static_cast<std::size_t>(c)];
            const long long b = A[static_cast<std::size_t>(j)][static_cast<std::size_t>(c)];
            if ((b > 0 && a > std::numeric_limits<long long>::max() - b) ||
                (b < 0 && a < std::numeric_limits<long long>::min() - b))
                throw std::overflow_error("Smith 标准形中间量溢出,矩阵元素过大");
            A[static_cast<std::size_t>(i)][static_cast<std::size_t>(c)] = a + b;
        }
    };
    auto row_negate = [&A, n](long long i) {
        for (long long c = 0; c < n; ++c)
            A[static_cast<std::size_t>(i)][static_cast<std::size_t>(c)] =
                -A[static_cast<std::size_t>(i)][static_cast<std::size_t>(c)];
    };

    long long guard = 256 * (m + n) * (m + n) + 1024;
    long long t = 0;
    while (t < m && t < n) {
        if (--guard < 0) throw std::overflow_error("Smith 标准形未在预期步数内收敛");
        // 1. 取子矩阵中任一个非零元作主元
        long long pi = -1, pj = -1;
        for (long long i = t; i < m && pi < 0; ++i)
            for (long long j = t; j < n; ++j)
                if (A[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] != 0) {
                    pi = i;
                    pj = j;
                    break;
                }
        if (pi < 0) break;  // 余下全零:秩 = t
        std::swap(A[static_cast<std::size_t>(t)], A[static_cast<std::size_t>(pi)]);
        for (long long i = 0; i < m; ++i)
            std::swap(A[static_cast<std::size_t>(i)][static_cast<std::size_t>(t)],
                      A[static_cast<std::size_t>(i)][static_cast<std::size_t>(pj)]);

        // 2. 反复消去第 t 行/列。每轮把余数换回主元位置,|主元| 严格下降 → 终止。
        for (;;) {
            if (--guard < 0) throw std::overflow_error("Smith 标准形未在预期步数内收敛");
            bool again = false;
            const long long piv = A[static_cast<std::size_t>(t)][static_cast<std::size_t>(t)];
            for (long long i = t + 1; i < m; ++i) {
                if (A[static_cast<std::size_t>(i)][static_cast<std::size_t>(t)] == 0) continue;
                row_sub(i, t, A[static_cast<std::size_t>(i)][static_cast<std::size_t>(t)] / piv);
                if (A[static_cast<std::size_t>(i)][static_cast<std::size_t>(t)] != 0) {
                    std::swap(A[static_cast<std::size_t>(t)], A[static_cast<std::size_t>(i)]);
                    again = true;
                    break;
                }
            }
            if (again) continue;
            const long long piv2 = A[static_cast<std::size_t>(t)][static_cast<std::size_t>(t)];
            for (long long j = t + 1; j < n; ++j) {
                if (A[static_cast<std::size_t>(t)][static_cast<std::size_t>(j)] == 0) continue;
                col_sub(j, t, A[static_cast<std::size_t>(t)][static_cast<std::size_t>(j)] / piv2);
                if (A[static_cast<std::size_t>(t)][static_cast<std::size_t>(j)] != 0) {
                    for (long long r = 0; r < m; ++r)
                        std::swap(A[static_cast<std::size_t>(r)][static_cast<std::size_t>(t)],
                                  A[static_cast<std::size_t>(r)][static_cast<std::size_t>(j)]);
                    again = true;
                    break;
                }
            }
            if (again) continue;
            break;
        }

        // 3. 整除性:主元必须整除余下子矩阵的全部元素,否则把"坏行"加到主元行后重做。
        long long bad_row = -1;
        for (long long i = t + 1; i < m && bad_row < 0; ++i)
            for (long long j = t + 1; j < n; ++j)
                if (A[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] %
                        A[static_cast<std::size_t>(t)][static_cast<std::size_t>(t)] !=
                    0) {
                    bad_row = i;
                    break;
                }
        if (bad_row >= 0) {
            row_add(t, bad_row);
            continue;  // 不推进 t,重新消元
        }

        if (A[static_cast<std::size_t>(t)][static_cast<std::size_t>(t)] < 0) row_negate(t);
        factors.push_back(A[static_cast<std::size_t>(t)][static_cast<std::size_t>(t)]);
        ++t;
    }
    std::sort(factors.begin(), factors.end());
    return factors;
}

// ∂_k : C_k → C_{k-1} 的 Smith 不变因子中 > 1 者 = torsion(H_{k-1})。
// 空矩阵(任一维没有单形)返回空列表。
inline std::vector<long long> torsion_of_lower_homology(
    const std::vector<Simplex>& dim_k, const std::vector<Simplex>& dim_km1) {
    std::vector<long long> tors;
    for (long long d : smith_invariants(boundary_matrix(dim_k, dim_km1)))
        if (d > 1) tors.push_back(d);
    return tors;
}

// 格式化同调群:如 "Z" / "Z^2 ⊕ Z_2" / "0"。标准数学记法,与 Python 表的
// "Z⊕Z" 等拼写等价但统一为 ^ 记法。
inline std::string format_group(long long betti, const std::vector<long long>& torsion) {
    std::vector<std::string> parts;
    if (betti > 0)
        parts.push_back(betti == 1 ? "Z" : "Z^" + std::to_string(betti));
    for (long long t : torsion)
        if (t > 1) parts.push_back("Z_" + std::to_string(t));
    if (parts.empty()) return "0";
    std::string out = parts[0];
    for (std::size_t i = 1; i < parts.size(); ++i) out += " ⊕ " + parts[i];
    return out;
}

}  // namespace detail
}  // namespace mf::algebraic_topology
