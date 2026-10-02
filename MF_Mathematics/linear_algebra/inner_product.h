// inner_product.h — 内积与正交:点积、范数、夹角、正交、格拉姆-施密特、正交投影。
#pragma once

#include <vector>

#include "la_internal.h"

namespace mf::linear_algebra {

// 点积 u·v。
double dot(const std::vector<double>& u, const std::vector<double>& v);

// 欧氏范数 ||v||。
double norm(const std::vector<double>& v);

// 夹角(弧度/角度/cosθ)。
struct AngleResult {
    double radians = 0.0;
    double degrees = 0.0;
    double cos_theta = 0.0;
};
AngleResult angle(const std::vector<double>& u,
                         const std::vector<double>& v);

// 是否正交(|u·v| < 1e-12)。
bool is_orthogonal(const std::vector<double>& u,
                          const std::vector<double>& v);

// 格拉姆-施密特正交化,返回标准正交基。
std::vector<Vector> gram_schmidt(
    const std::vector<std::vector<double>>& vectors);

// 向量在子空间(基张成)上的正交投影。
Vector orthogonal_projection(
    const std::vector<double>& vector,
    const std::vector<std::vector<double>>& basis);

}  // namespace mf::linear_algebra
