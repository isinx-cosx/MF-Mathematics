// linear_systems.cpp — 线性方程组内核(基于 Eigen)。

#include "linear_systems.h"

#include <cmath>
#include <limits>
#include <stdexcept>

#include <Eigen/Dense>

namespace mf::linear_algebra {

using detail::to_matrix;
using detail::to_vector;
using detail::rref_with_pivots;
using detail::rref_rank;
using detail::nullspace_basis;

namespace {

// 增广矩阵 [A|b] 行阶梯形 → 解结构。
GaussianResult gaussian_from_aug(const Matrix& A, const Vector& b) {
    const long long m = A.rows(), n = A.cols();
    Matrix aug(m, n + 1);
    aug.leftCols(n) = A;
    aug.col(n) = b;
    const auto rr = rref_with_pivots(aug);
    const Matrix& R = rr.rref;

    GaussianResult r;
    // A 部分的秩(主元列 < n)。
    long long rank_a = 0;
    for (long long p : rr.pivots)
        if (p < n) ++rank_a;
    r.rank = rank_a;
    r.free_vars = n - rank_a;

    // 矛盾行:系数全零但常数非零。
    for (long long i = 0; i < m; ++i) {
        bool coeff_zero = true;
        for (long long j = 0; j < n; ++j)
            if (std::abs(R(i, j)) > 1e-9) {
                coeff_zero = false;
                break;
            }
        if (coeff_zero && std::abs(R(i, n)) > 1e-9) {
            r.type = "none";
            return r;
        }
    }

    if (rank_a == n) {
        // 唯一解:R 的右端前 n 个分量。
        r.type = "unique";
        r.solution = R.col(n).head(n);
    } else {
        r.type = "infinite";
    }
    return r;
}

}  // namespace

GaussianResult gaussian_elimination(
    const std::vector<std::vector<double>>& matrix,
    const std::vector<double>& b, bool has_b) {
    const Matrix A = to_matrix(matrix);
    if (has_b) {
        const Vector bv = to_vector(b);
        if (bv.size() != A.rows())
            throw std::invalid_argument("常数向量长度与矩阵行数不一致");
        return gaussian_from_aug(A, bv);
    }
    return gaussian_from_aug(A, Vector::Zero(A.rows()));
}

long long rank(const std::vector<std::vector<double>>& matrix) {
    return rref_rank(to_matrix(matrix));
}

SolveResult solve_linear_system(const std::vector<std::vector<double>>& A_in,
                                const std::vector<double>& b, bool has_b) {
    const Matrix A = to_matrix(A_in);
    const Vector bv = has_b ? to_vector(b) : Vector::Zero(A.rows());
    if (bv.size() != A.rows())
        throw std::invalid_argument("常数向量长度与矩阵行数不一致");

    const bool homogeneous = has_b ? bv.norm() <= 1e-12 : true;
    const GaussianResult g = gaussian_from_aug(A, bv);

    SolveResult r;
    r.type = g.type;
    r.homogeneous = homogeneous;
    r.solution = g.solution;
    if (g.type == "infinite") r.homogeneous_basis = nullspace_basis(A);
    return r;
}

NullspaceResult nullspace(const std::vector<std::vector<double>>& A_in) {
    NullspaceResult r;
    const Matrix A = to_matrix(A_in);
    r.basis = nullspace_basis(A);
    r.dimension = static_cast<long long>(r.basis.size());
    return r;
}

InverseResult matrix_inverse(
    const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    if (A.rows() != A.cols())
        throw std::invalid_argument("矩阵必须为方阵");

    InverseResult r;
    r.det = A.determinant();
    if (std::abs(r.det) < 1e-12) {
        r.singular = true;
        return r;
    }

    // 条件数 = 最大/最小奇异值。
    Eigen::JacobiSVD<Matrix> svd(A);
    const auto& s = svd.singularValues();
    if (s.size() > 0 && s(s.size() - 1) > 0)
        r.condition_number = s(0) / s(s.size() - 1);
    else
        r.condition_number = std::numeric_limits<double>::infinity();
    if (r.condition_number > 1e10) {
        r.ill_conditioned = true;
        return r;
    }

    r.inverse = Eigen::FullPivLU<Matrix>(A).inverse();
    return r;
}

}  // namespace mf::linear_algebra
