// dual_spaces.h — 对偶空间与弱拓扑:对偶基、弱收敛、自反性。
#pragma once

#include <string>
#include <vector>

#include <Eigen/Dense>


namespace mf::functional_analysis {

// 对偶基 = B^{-T}(基矩阵不可逆抛 std::invalid_argument)。
Eigen::MatrixXd dual_space_basis(const Eigen::MatrixXd& basis);

// "R^n"/"l^p" → R³ 标准基的对偶基(单位阵)。
Eigen::MatrixXd dual_space_basis(const std::string& space);

// 弱收敛判断。functional 为 nullptr 时用标准坐标泛函;limit 为 nullptr 时用末项。
bool weak_convergence(const std::vector<std::vector<double>>& sequence,
                             const std::vector<double>* functional = nullptr,
                             const std::vector<double>* limit = nullptr,
                             double tol = 1e-3);

// 自反空间判断(查表 + 有限维自动自反)。
bool is_reflexive(const std::string& space, long long dimension = -1);

}  // namespace mf::functional_analysis
