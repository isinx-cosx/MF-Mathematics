// linear_operators.h — 线性算子:算子范数、有界性、线性泛函、核维数。
#pragma once

#include <string>
#include <vector>

#include <Eigen/Dense>

#include "../mf_export.h"

namespace mf::functional_analysis {

// 算子范数。p ∈ {"2"(谱范数), "1"(列和), "inf"(行和), "fro"(Frobenius)}。
MF_API double operator_norm(const Eigen::MatrixXd& A, const std::string& p = "2");

// 矩阵算子有界性:谱范数 < 1e10。
MF_API bool is_bounded(const Eigen::MatrixXd& A);

// 线性泛函值 f(x) = ⟨a, x⟩。维度不匹配抛 std::invalid_argument。
MF_API double linear_functional_eval(const std::vector<double>& func,
                                     const std::vector<double>& x);

// 核(零空间)维数 dim ker = n - rank,附右奇异向量基。
struct KernelResult {
    long long dim_ker = 0;
    std::vector<std::vector<double>> kernel_basis;
};
MF_API KernelResult kernel_dimension(const Eigen::MatrixXd& A, double tol = 1e-10);

}  // namespace mf::functional_analysis
