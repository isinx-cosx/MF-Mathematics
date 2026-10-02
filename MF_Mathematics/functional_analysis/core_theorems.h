// core_theorems.h — 泛函分析核心定理:哈恩-巴拿赫、一致有界、开映射、闭图像。
#pragma once

#include <vector>

#include <Eigen/Dense>


namespace mf::functional_analysis {

// 哈恩-巴拿赫延拓:最小范数延拓(补零到全空间)。
std::vector<double> hahn_banach_extension(
    const std::vector<double>& a, long long subspace_dim, long long ambient_dim = -1);

// 一致有界原理数值演示。
struct UniformBoundednessResult {
    bool pointwise_bounded = false;
    bool uniformly_bounded = false;
    double sup_operator_norm = 0.0;
    std::vector<double> operator_norms;
};
UniformBoundednessResult uniform_boundedness(
    const std::vector<Eigen::MatrixXd>& operators,
    const std::vector<Eigen::VectorXd>* test_points = nullptr);

// 开映射:满射(行满秩)⇔ 开映射。
bool open_mapping(const Eigen::MatrixXd& A);

// 闭图像:有界(谱范数 < 1e10)⇔ 闭图像。
bool closed_graph(const Eigen::MatrixXd& A);

}  // namespace mf::functional_analysis
