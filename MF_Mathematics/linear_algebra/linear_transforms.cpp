// linear_transforms.cpp — 线性变换内核(基于 Eigen)。

#include "linear_transforms.h"

#include <cmath>
#include <stdexcept>

namespace mf::linear_algebra {

using detail::to_matrix;
using detail::to_vector;
using detail::hstack;
using detail::rref_with_pivots;
using detail::rref_rank;
using detail::nullspace_basis;

Vector linear_transform(const std::vector<std::vector<double>>& matrix,
                        const std::vector<double>& vector) {
    const Matrix A = to_matrix(matrix);
    const Vector v = to_vector(vector);
    if (A.cols() != v.size())
        throw std::invalid_argument("矩阵列数与向量维数不匹配");
    return A * v;
}

MatrixRepresentationResult matrix_representation(
    const std::vector<std::vector<double>>& transform,
    const std::vector<std::vector<double>>& domain_basis) {
    MatrixRepresentationResult r;
    const Matrix T = to_matrix(transform);
    const auto basis_vecs = [&] {
        std::vector<Vector> out;
        for (const auto& b : domain_basis) out.push_back(to_vector(b));
        return out;
    }();

    // 标准基判断:基向量 == 单位向量。
    const Eigen::Index n = T.cols();
    bool standard = true;
    for (Eigen::Index i = 0; i < static_cast<Eigen::Index>(basis_vecs.size()); ++i) {
        Vector expected = Vector::Zero(n);
        if (i < n) expected(i) = 1.0;
        if (basis_vecs[i].size() != n || (basis_vecs[i] - expected).norm() > 1e-9) {
            standard = false;
            break;
        }
    }

    if (standard) {
        r.matrix = T;
        r.is_standard_basis = true;
        return r;
    }

    // 非标准基:T' = B⁻¹·T·B。
    const Matrix B = hstack(basis_vecs);
    if (B.rows() != B.cols())
        throw std::invalid_argument("基矩阵必须为方阵");
    const Eigen::FullPivLU<Matrix> lu(B);
    if (!lu.isInvertible())
        throw std::invalid_argument("基矩阵不可逆");
    r.matrix = lu.inverse() * T * B;
    r.is_standard_basis = false;
    r.has_basis_matrix = true;
    r.basis_matrix = B;
    return r;
}

KernelResult kernel(const std::vector<std::vector<double>>& matrix) {
    KernelResult r;
    const Matrix A = to_matrix(matrix);
    r.kernel_basis = nullspace_basis(A);
    r.nullity = static_cast<long long>(r.kernel_basis.size());
    return r;
}

ImageResult image(const std::vector<std::vector<double>>& matrix) {
    ImageResult r;
    const Matrix A = to_matrix(matrix);
    const auto rr = rref_with_pivots(A);
    for (long long p : rr.pivots) r.image_basis.push_back(A.col(p));
    r.rank = static_cast<long long>(rr.pivots.size());
    return r;
}

RankNullityResult rank_nullity(const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    RankNullityResult r;
    r.rank = rref_rank(A);
    r.nullity = static_cast<long long>(nullspace_basis(A).size());
    r.domain_dim = A.cols();
    r.theorem_holds = r.rank + r.nullity == r.domain_dim;
    return r;
}

}  // namespace mf::linear_algebra
