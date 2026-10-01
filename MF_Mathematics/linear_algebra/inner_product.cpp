// inner_product.cpp — 内积与正交内核(基于 Eigen)。

#include "inner_product.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace mf::linear_algebra {

using detail::to_vector;

namespace {

Vector to_v(const std::vector<double>& v) { return to_vector(v); }

}  // namespace

double dot(const std::vector<double>& u, const std::vector<double>& v) {
    const Vector U = to_v(u), V = to_v(v);
    if (U.size() != V.size())
        throw std::invalid_argument("向量维数不一致");
    return U.dot(V);
}

double norm(const std::vector<double>& v) { return to_v(v).norm(); }

AngleResult angle(const std::vector<double>& u, const std::vector<double>& v) {
    const Vector U = to_v(u), V = to_v(v);
    if (U.size() != V.size())
        throw std::invalid_argument("向量维数不一致");
    const double nu = U.norm(), nv = V.norm();
    if (nu < 1e-15 || nv < 1e-15)
        throw std::invalid_argument("零向量无法计算夹角");
    const double dotv = U.dot(V);
    const double cos_theta = std::clamp(dotv / (nu * nv), -1.0, 1.0);
    AngleResult r;
    r.cos_theta = cos_theta;
    r.radians = std::acos(cos_theta);
    r.degrees = r.radians * 180.0 / std::acos(-1.0);
    return r;
}

bool is_orthogonal(const std::vector<double>& u,
                   const std::vector<double>& v) {
    return std::abs(dot(u, v)) < 1e-12;
}

std::vector<Vector> gram_schmidt(
    const std::vector<std::vector<double>>& vectors) {
    std::vector<Vector> orthonormal;
    for (const auto& row : vectors) {
        Vector w = to_v(row);
        for (const auto& u : orthonormal) w -= w.dot(u) * u;
        const double wn = w.norm();
        if (wn > 1e-15) orthonormal.push_back(w / wn);
    }
    return orthonormal;
}

Vector orthogonal_projection(const std::vector<double>& vector,
                             const std::vector<std::vector<double>>& basis) {
    const Vector v = to_v(vector);
    if (basis.empty()) return v;
    // 基先正交化,再投影 proj = Σ (v·eᵢ) eᵢ。
    const auto ortho = gram_schmidt(basis);
    Vector proj = Vector::Zero(v.size());
    for (const auto& e : ortho) proj += v.dot(e) * e;
    return proj;
}

}  // namespace mf::linear_algebra
