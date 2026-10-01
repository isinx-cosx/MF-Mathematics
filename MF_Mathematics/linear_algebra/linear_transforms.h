// linear_transforms.h — 线性变换:矩阵表示、核与像、秩-零化度定理。
#pragma once

#include <vector>

#include "../mf_export.h"
#include "la_internal.h"

namespace mf::linear_algebra {

// 线性变换 T(v) = A·v。
MF_API Vector linear_transform(const std::vector<std::vector<double>>& matrix,
                               const std::vector<double>& vector);

// 线性变换在给定基下的矩阵表示。标准基 → 原矩阵;否则 T' = B⁻¹·T·B。
struct MatrixRepresentationResult {
    Matrix matrix;
    bool is_standard_basis = false;
    bool has_basis_matrix = false;  // 非标准基时给出基矩阵
    Matrix basis_matrix;
};
MF_API MatrixRepresentationResult matrix_representation(
    const std::vector<std::vector<double>>& transform,
    const std::vector<std::vector<double>>& domain_basis);

// 核(零空间)。
struct KernelResult {
    std::vector<Vector> kernel_basis;
    long long nullity = 0;
};
MF_API KernelResult kernel(const std::vector<std::vector<double>>& matrix);

// 像(列空间)。
struct ImageResult {
    std::vector<Vector> image_basis;
    long long rank = 0;
};
MF_API ImageResult image(const std::vector<std::vector<double>>& matrix);

// 秩-零化度定理:rank + nullity = dim(V)。
struct RankNullityResult {
    long long rank = 0;
    long long nullity = 0;
    long long domain_dim = 0;
    bool theorem_holds = false;
};
MF_API RankNullityResult rank_nullity(
    const std::vector<std::vector<double>>& matrix);

}  // namespace mf::linear_algebra
