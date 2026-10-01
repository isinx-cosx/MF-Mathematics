// fa_internal.h — functional_analysis 包内部辅助(仅头文件)。
//
// 提供基于 Eigen 的谱范数、数值秩计算,替换 Python 的 scipy.linalg 调用。

#pragma once

#include <algorithm>
#include <cmath>

#include <Eigen/Dense>

namespace mf::functional_analysis::detail {

// 谱范数 = 最大奇异值(替换 linalg.norm(A, ord=2) / svdvals()[0])。
inline double spectral_norm(const Eigen::MatrixXd& A) {
    Eigen::JacobiSVD<Eigen::MatrixXd> svd(A);
    const auto& s = svd.singularValues();
    return s.size() > 0 ? s(0) : 0.0;
}

// 数值秩:奇异值 > tol·max(s₀, 1) 的个数。
// 对应 linear_operators.kernel_dimension 的手写计数逻辑(Python: tol*max(s[0],1))。
inline long long matrix_rank(const Eigen::MatrixXd& A, double tol = 1e-10) {
    Eigen::JacobiSVD<Eigen::MatrixXd> svd(A);
    const auto& s = svd.singularValues();
    if (s.size() == 0) return 0;
    const double threshold = tol * std::max(s(0), 1.0);
    long long rank = 0;
    for (long long i = 0; i < static_cast<long long>(s.size()); ++i)
        if (s(i) > threshold) ++rank;
    return rank;
}

// 等价 np.linalg.matrix_rank(A)(默认 tol=None):
//   阈值 = s₀·max(M,N)·eps,eps 为 double 机器精度 2.22e-16。
// 对应 core_theorems.open_mapping 使用的 numpy 内置秩。
inline long long matrix_rank_numpy(const Eigen::MatrixXd& A) {
    Eigen::JacobiSVD<Eigen::MatrixXd> svd(A);
    const auto& s = svd.singularValues();
    if (s.size() == 0) return 0;
    const double eps = 2.220446049250313e-16;
    const double threshold = s(0) * static_cast<double>(std::max(A.rows(), A.cols())) * eps;
    long long rank = 0;
    for (long long i = 0; i < static_cast<long long>(s.size()); ++i)
        if (s(i) > threshold) ++rank;
    return rank;
}

}  // namespace mf::functional_analysis::detail
