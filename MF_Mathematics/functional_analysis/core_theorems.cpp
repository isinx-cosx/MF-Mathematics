#include "core_theorems.h"

#include <algorithm>
#include <cmath>
#include <random>
#include <stdexcept>
#include <vector>

#include "fa_internal.h"

namespace mf::functional_analysis {

std::vector<double> hahn_banach_extension(const std::vector<double>& a,
                                          long long subspace_dim,
                                          long long ambient_dim) {
    if (ambient_dim < 0)
        ambient_dim = std::max<long long>(static_cast<long long>(a.size()) + 1,
                                          subspace_dim + 1);
    std::vector<double> a_ext(static_cast<std::size_t>(ambient_dim), 0.0);
    const std::size_t copy_n = std::min(a.size(), a_ext.size());
    std::copy(a.begin(), a.begin() + static_cast<std::ptrdiff_t>(copy_n), a_ext.begin());
    return a_ext;
}

UniformBoundednessResult uniform_boundedness(
    const std::vector<Eigen::MatrixXd>& operators,
    const std::vector<Eigen::VectorXd>* test_points) {
    UniformBoundednessResult res;
    double sup = 0.0;
    for (const auto& A : operators) {
        const double nrm = detail::spectral_norm(A);
        res.operator_norms.push_back(nrm);
        sup = std::max(sup, nrm);
    }
    res.sup_operator_norm = sup;

    // 测试点:提供或随机生成 10 个单位向量(种子 42)
    std::vector<Eigen::VectorXd> pts;
    if (test_points != nullptr) {
        pts = *test_points;
    } else {
        const long long n_dim = operators.empty() ? 1 : operators[0].cols();
        std::mt19937 rng(42);
        std::normal_distribution<double> dist(0.0, 1.0);
        for (int k = 0; k < 10; ++k) {
            Eigen::VectorXd p(n_dim);
            for (long long i = 0; i < n_dim; ++i) p(i) = dist(rng);
            p.normalize();
            pts.push_back(p);
        }
    }

    double max_pointwise = 0.0;
    for (const auto& x : pts)
        for (const auto& A : operators)
            max_pointwise = std::max(max_pointwise, (A * x).norm());
    res.pointwise_bounded = max_pointwise < 1e6;
    res.uniformly_bounded = sup < 1e6;
    return res;
}

bool open_mapping(const Eigen::MatrixXd& A) {
    const long long rank = detail::matrix_rank_numpy(A);  // 与 np.linalg.matrix_rank 一致
    return rank == A.rows();  // 满射(行满秩)
}

bool closed_graph(const Eigen::MatrixXd& A) {
    return detail::spectral_norm(A) < 1e10;  // 有界 ⇒ 闭图像
}

}  // namespace mf::functional_analysis
