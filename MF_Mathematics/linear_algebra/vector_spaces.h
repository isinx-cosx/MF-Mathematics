// vector_spaces.h — 向量空间:线性组合、线性相关/无关、基与维数、子空间。
#pragma once

#include <vector>

#include "../mf_export.h"
#include "la_internal.h"

namespace mf::linear_algebra {

// 验证向量集合是否构成向量空间(标准运算):零向量 + 加法/标量乘法封闭。
struct VectorSpaceResult {
    bool is_vector_space = false;
    bool zero_vector = false;
    bool closed_under_addition = false;
    bool closed_under_scalar_multiplication = false;
};
MF_API VectorSpaceResult is_vector_space(
    const std::vector<std::vector<double>>& vectors);

// 线性组合 Σ cᵢ·vᵢ,返回列向量。
MF_API Vector linear_combination(const std::vector<std::vector<double>>& vectors,
                                 const std::vector<double>& coeffs);

// 秩 == 向量个数 → 线性无关。
MF_API bool is_linear_independent(
    const std::vector<std::vector<double>>& vectors);

// 一组基(极大线性无关组)。
struct BasisResult {
    std::vector<Vector> basis;
    long long dimension = 0;
};
MF_API BasisResult basis(const std::vector<std::vector<double>>& vectors);

// 张成子空间的维数 = 矩阵秩。
MF_API long long dimension(const std::vector<std::vector<double>>& vectors);

// span(S) 的基与维数。
struct SpanResult {
    std::vector<Vector> span_basis;
    long long dimension = 0;
};
MF_API SpanResult subspace_span(const std::vector<std::vector<double>>& vectors);

}  // namespace mf::linear_algebra
