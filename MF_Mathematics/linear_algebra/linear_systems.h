// linear_systems.h — 线性方程组:高斯消元、秩、解的结构、基础解系、矩阵求逆。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"
#include "la_internal.h"

namespace mf::linear_algebra {

// 高斯消元:增广矩阵行阶梯形 → 解的结构。
struct GaussianResult {
    std::string type;      // "unique" | "infinite" | "none"
    Vector solution;       // 唯一解时
    long long rank = 0;
    long long free_vars = 0;
};
MF_API GaussianResult gaussian_elimination(
    const std::vector<std::vector<double>>& matrix,
    const std::vector<double>& b, bool has_b);

// 矩阵秩。
MF_API long long rank(const std::vector<std::vector<double>>& matrix);

// 求解 Ax=b(唯一/无穷/无解)。
struct SolveResult {
    std::string type;      // "unique" | "infinite" | "none"
    bool homogeneous = false;
    Vector solution;       // 唯一解时
    std::vector<Vector> homogeneous_basis;  // 无穷多解时的通解基(零空间)
};
MF_API SolveResult solve_linear_system(const std::vector<std::vector<double>>& A,
                                       const std::vector<double>& b, bool has_b);

// 零空间基础解系。
struct NullspaceResult {
    std::vector<Vector> basis;
    long long dimension = 0;
};
MF_API NullspaceResult nullspace(const std::vector<std::vector<double>>& A);

// 矩阵求逆 + 行列式 + 条件数。
struct InverseResult {
    bool singular = false;
    bool ill_conditioned = false;
    Matrix inverse;
    double det = 0.0;
    double condition_number = 0.0;
};
MF_API InverseResult matrix_inverse(
    const std::vector<std::vector<double>>& matrix);

}  // namespace mf::linear_algebra
