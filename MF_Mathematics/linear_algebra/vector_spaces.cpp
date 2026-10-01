// vector_spaces.cpp — 向量空间内核(基于 Eigen)。

#include "vector_spaces.h"

#include <cmath>
#include <stdexcept>

namespace mf::linear_algebra {

using detail::to_matrix;
using detail::to_vector;
using detail::hstack;
using detail::vec_in_set;
using detail::rref_with_pivots;
using detail::rref_rank;

namespace {

// 向量列表 → Eigen 向量列表。
std::vector<Vector> to_vectors(const std::vector<std::vector<double>>& rows) {
    std::vector<Vector> out;
    for (const auto& r : rows) out.push_back(to_vector(r));
    return out;
}

// 向量是否为零向量。
bool is_zero_vec(const Vector& v, double tol = 1e-12) {
    return v.norm() <= tol;
}

}  // namespace

VectorSpaceResult is_vector_space(
    const std::vector<std::vector<double>>& vectors) {
    VectorSpaceResult r;
    if (vectors.empty()) return r;
    const auto vecs = to_vectors(vectors);
    const Eigen::Index n = vecs[0].size();

    // 维数一致性。
    for (const auto& v : vecs)
        if (v.size() != n) return r;

    // 零向量。
    for (const auto& v : vecs)
        if (is_zero_vec(v)) r.zero_vector = true;

    // 加法封闭。
    r.closed_under_addition = true;
    for (std::size_t i = 0; i < vecs.size() && r.closed_under_addition; ++i)
        for (std::size_t j = i; j < vecs.size(); ++j)
            if (!vec_in_set(vecs, vecs[i] + vecs[j])) {
                r.closed_under_addition = false;
                break;
            }

    // 标量乘法封闭(抽样标量 -1, 2, 0.5)。
    r.closed_under_scalar_multiplication = true;
    const double scalars[] = {-1.0, 2.0, 0.5};
    for (const auto& v : vecs) {
        for (double c : scalars) {
            if (!vec_in_set(vecs, c * v)) {
                r.closed_under_scalar_multiplication = false;
                break;
            }
        }
        if (!r.closed_under_scalar_multiplication) break;
    }

    r.is_vector_space =
        r.zero_vector && r.closed_under_addition &&
        r.closed_under_scalar_multiplication;
    return r;
}

Vector linear_combination(const std::vector<std::vector<double>>& vectors,
                          const std::vector<double>& coeffs) {
    if (vectors.empty()) throw std::invalid_argument("向量列表不能为空");
    if (vectors.size() != coeffs.size())
        throw std::invalid_argument("向量的数量与系数的数量不匹配");
    const auto vecs = to_vectors(vectors);
    Vector result = Vector::Zero(vecs[0].size());
    for (std::size_t i = 0; i < vecs.size(); ++i) result += coeffs[i] * vecs[i];
    return result;
}

bool is_linear_independent(const std::vector<std::vector<double>>& vectors) {
    if (vectors.empty()) return true;
    const auto vecs = to_vectors(vectors);
    const Matrix M = hstack(vecs);
    return rref_rank(M) == static_cast<long long>(vecs.size());
}

BasisResult basis(const std::vector<std::vector<double>>& vectors) {
    BasisResult r;
    if (vectors.empty()) return r;
    const auto vecs = to_vectors(vectors);
    const auto rr = rref_with_pivots(hstack(vecs));
    for (long long p : rr.pivots) r.basis.push_back(vecs[p]);
    r.dimension = static_cast<long long>(rr.pivots.size());
    return r;
}

long long dimension(const std::vector<std::vector<double>>& vectors) {
    if (vectors.empty()) return 0;
    const auto vecs = to_vectors(vectors);
    return rref_rank(hstack(vecs));
}

SpanResult subspace_span(const std::vector<std::vector<double>>& vectors) {
    SpanResult r;
    if (vectors.empty()) return r;
    const auto vecs = to_vectors(vectors);
    const auto rr = rref_with_pivots(hstack(vecs));
    for (long long p : rr.pivots) r.span_basis.push_back(vecs[p]);
    r.dimension = static_cast<long long>(rr.pivots.size());
    return r;
}

}  // namespace mf::linear_algebra
