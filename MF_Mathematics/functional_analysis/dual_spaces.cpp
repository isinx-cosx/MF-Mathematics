#include "dual_spaces.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

namespace mf::functional_analysis {

namespace {

std::string norm_space(const std::string& s) {
    std::string out;
    for (char ch : s)
        out.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
    return out;
}

}  // namespace

Eigen::MatrixXd dual_space_basis(const Eigen::MatrixXd& basis) {
    Eigen::FullPivLU<Eigen::MatrixXd> lu(basis);
    if (!lu.isInvertible())
        throw std::invalid_argument("基矩阵不可逆,无法计算对偶基");
    return lu.inverse().transpose();
}

Eigen::MatrixXd dual_space_basis(const std::string& space) {
    (void)space;
    return Eigen::MatrixXd::Identity(3, 3);  // R^n/l^p 默认 R³ 标准基
}

bool weak_convergence(const std::vector<std::vector<double>>& sequence,
                      const std::vector<double>* functional,
                      const std::vector<double>* limit, double tol) {
    const long long n = static_cast<long long>(sequence.size());
    if (n < 3) throw std::invalid_argument("序列长度至少为 3");
    const long long dim = static_cast<long long>(sequence[0].size());

    const std::vector<double> limit_vec =
        limit != nullptr ? *limit : sequence[static_cast<std::size_t>(n - 1)];
    if (static_cast<long long>(limit_vec.size()) != dim)
        throw std::invalid_argument("limit 维度与序列不匹配");

    // 测试泛函:Riesz 表示向量
    std::vector<std::vector<double>> functionals;
    if (functional != nullptr) {
        if ((long long)functional->size() != dim)
            throw std::invalid_argument("泛函维度与序列维度不匹配");
        functionals.push_back(*functional);
    } else {
        const long long k = std::min<long long>(dim, 3);
        for (long long i = 0; i < k; ++i) {
            std::vector<double> e(dim, 0.0);
            e[static_cast<std::size_t>(i)] = 1.0;
            functionals.push_back(std::move(e));
        }
    }

    bool all_converge = true;
    const long long tail = std::min<long long>(5, n);
    for (const auto& f : functionals) {
        std::vector<double> f_values;
        for (const auto& s : sequence) {
            double v = 0.0;
            for (long long k = 0; k < dim; ++k) v += f[static_cast<std::size_t>(k)] * s[static_cast<std::size_t>(k)];
            f_values.push_back(v);
        }
        double f_limit = 0.0;
        for (long long k = 0; k < dim; ++k) f_limit += f[static_cast<std::size_t>(k)] * limit_vec[static_cast<std::size_t>(k)];
        double max_dev = 0.0;
        for (long long i = n - tail; i < n; ++i)
            max_dev = std::max(max_dev, std::abs(f_values[static_cast<std::size_t>(i)] - f_limit));
        if (max_dev >= tol) all_converge = false;
    }
    return all_converge;
}

bool is_reflexive(const std::string& space_raw, long long dimension) {
    const std::string space = norm_space(space_raw);
    if (space == "r^n" || space == "c^n" || space == "l^p (1<p<∞)" ||
        space == "l^p" || space == "l^2" || space == "sobolev w^{k,p} (1<p<∞)") {
        return true;
    }
    if (space == "l^1" || space == "l^∞" || space == "c[0,1]" || space == "c_0") {
        return false;
    }
    if (dimension > 0) return true;  // 有限维自动自反
    return false;
}

}  // namespace mf::functional_analysis
