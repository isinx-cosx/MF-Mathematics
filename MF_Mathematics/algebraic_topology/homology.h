// homology.h — 同调:单纯复形构建、同调群、贝蒂数、欧拉示性数。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"
#include "at_internal.h"

namespace mf::algebraic_topology {

// 单纯复形构建结果:复形本身 + 统计信息。
struct SimplicialComplexResult {
    Complex complex;
    long long num_vertices = 0;
    long long num_simplices = 0;
    long long max_dimension = 0;
};

// 从单形列表构建单纯复形。maximal=true 时自动补全所有面以保证封闭。
MF_API SimplicialComplexResult build_simplicial_complex(
    const std::vector<Simplex>& simplices, bool maximal = true);

// 第 n 个同调群:贝蒂数 β_n、挠系数与群记号。
// 挠系数两条路径都精确给出:空间查表路径取已知空间的精确值;复形路径由
// ∂_{n+1} 的 Smith 标准形不变因子(>1 者 = torsion(coker ∂_{n+1}) = torsion(H_n))算出。
struct HomologyGroup {
    long long betti = 0;
    std::vector<long long> torsion;
    std::string group;
};

// 从单纯复形计算 H_n(边界矩阵精确秩 + Smith 标准形挠系数)。
MF_API HomologyGroup homology_group(const Complex& c, long long n);

// 已知空间查表:S1/S2/T2/S3/RP2/K/fig8。未知空间抛 std::invalid_argument。
MF_API HomologyGroup homology_group(const std::string& space, long long n);

// 贝蒂数列表 [β0, β1, ...]。max_dim < 0 时自动取复形最高维。
MF_API std::vector<long long> betti_numbers(const Complex& c, long long max_dim = -1);

// 已知空间贝蒂数查表(含 point / R^n)。
MF_API std::vector<long long> betti_numbers(const std::string& space);

// 欧拉示性数:从复形按 χ = Σ (-1)^d c_d 计数,或从空间贝蒂数 Σ (-1)^k β_k。
MF_API long long euler_characteristic(const Complex& c);
MF_API long long euler_characteristic(const std::string& space);

// 边界算子概念结果:∂_n 的定义式(概念性,不依赖具体链)。
struct BoundaryOperator {
    long long dimension = 0;
    std::string formula;
};
MF_API BoundaryOperator boundary_operator(long long dimension);

}  // namespace mf::algebraic_topology
