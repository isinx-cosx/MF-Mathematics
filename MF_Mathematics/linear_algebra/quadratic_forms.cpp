// quadratic_forms.cpp — 二次型与正定性内核(基于 Eigen)。

#include "quadratic_forms.h"

#include <cmath>
#include <sstream>
#include <stdexcept>
#include <string>

#include <Eigen/Dense>

namespace mf::linear_algebra {

using detail::to_matrix;
using detail::fmt_num;

namespace {

// 二次项系数格式化:c·sym(c=1 → "sym", c=-1 → "-sym")。
std::string coeff_term(double c, const std::string& sym) {
    if (std::abs(c) < 1e-12) return "";
    if (c == 1.0) return sym;
    if (c == -1.0) return "-" + sym;
    return fmt_num(c) + "*" + sym;
}

void require_square(const Matrix& A) {
    if (A.rows() != A.cols())
        throw std::invalid_argument("矩阵必须是方阵");
}

void require_symmetric(const Matrix& A) {
    if ((A - A.transpose()).norm() > 1e-9)
        throw std::invalid_argument("矩阵必须是对称矩阵");
}

}  // namespace

std::string quadratic_form(const std::vector<std::vector<double>>& matrix,
                           const std::string& x) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    const long long n = A.rows();

    std::vector<std::string> names;
    if (x.empty()) {
        for (long long i = 0; i < n; ++i) names.push_back("x" + std::to_string(i));
    } else {
        std::stringstream ss(x);
        std::string item;
        while (std::getline(ss, item, ',')) {
            // 去空白;空段视为错误。
            const auto b = item.find_first_not_of(" \t");
            const auto e = item.find_last_not_of(" \t");
            if (b == std::string::npos || e == std::string::npos)
                throw std::invalid_argument("变量名列表含空段");
            names.push_back(item.substr(b, e - b + 1));
        }
    }
    if (static_cast<long long>(names.size()) != n)
        throw std::invalid_argument("变量个数与矩阵阶数不匹配");

    std::vector<std::string> terms;
    for (long long i = 0; i < n; ++i) {
        const std::string d = coeff_term(A(i, i), names[i] + "**2");
        if (!d.empty()) terms.push_back(d);
        for (long long j = i + 1; j < n; ++j) {
            const std::string o =
                coeff_term(2.0 * A(i, j), names[i] + "*" + names[j]);
            if (!o.empty()) terms.push_back(o);
        }
    }
    if (terms.empty()) return "0";
    std::string out;
    for (std::size_t i = 0; i < terms.size(); ++i) {
        if (i) out += " + ";
        out += terms[i];
    }
    return out;
}

StandardFormResult standard_form(
    const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    require_symmetric(A);

    Eigen::SelfAdjointEigenSolver<Matrix> es(A);
    const auto evals = es.eigenvalues();
    const Matrix Q = es.eigenvectors();

    StandardFormResult r;
    for (Eigen::Index i = 0; i < evals.size(); ++i)
        r.eigenvalues.push_back(evals(i));
    std::vector<std::string> terms;
    for (Eigen::Index i = 0; i < evals.size(); ++i)
        terms.push_back(fmt_num(evals(i)) + "*y" + std::to_string(i + 1) + "^2");
    std::string out;
    for (std::size_t i = 0; i < terms.size(); ++i) {
        if (i) out += " + ";
        out += terms[i];
    }
    r.standard_form = out;
    r.orthogonal_matrix = Q;
    return r;
}

bool is_positive_definite(const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    require_symmetric(A);
    for (Eigen::Index k = 1; k <= A.rows(); ++k) {
        const double d = A.topLeftCorner(k, k).determinant();
        if (d <= 0.0) return false;
    }
    return true;
}

bool is_negative_definite(const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    require_symmetric(A);
    for (Eigen::Index k = 1; k <= A.rows(); ++k) {
        const double d = A.topLeftCorner(k, k).determinant();
        if (k % 2 == 1) {
            if (d >= 0.0) return false;
        } else {
            if (d <= 0.0) return false;
        }
    }
    return true;
}

bool is_indefinite(const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    // 二次型 xᵀAx 只由 A 的**对称部分**决定（反对称部分贡献恒为 0），
    // 所以这里先取对称部分再做定性判定 —— 对任意输入这个提法都有意义：
    //   · A = [[0,-1],[1,0]]（反对称）→ 对称部分为 0 → 二次型 ≡ 0 → 不定 = false；
    //   · A = [[0,2],[-1,0]] → 对称部分 [[0,0.5],[0.5,0]]，特征值 ±0.5 → 不定 = true。
    // 旧实现既不做这一步、又用一般 EigenSolver 取**实部**，于是把后者判成 false。
    // 注意：is_positive_definite / is_negative_definite 仍按教科书惯例要求矩阵对称，
    // 与此处的宽松处理不同 —— 那对函数是按"矩阵定性"提问，这里是按"二次型定性"提问。
    const Matrix S = 0.5 * (A + A.transpose());
    Eigen::SelfAdjointEigenSolver<Matrix> es(S);
    if (es.info() != Eigen::Success)
        throw std::runtime_error("特征值求解未收敛");
    bool has_pos = false, has_neg = false;
    const double scale = std::max(1.0, S.norm());
    for (Eigen::Index i = 0; i < S.rows(); ++i) {
        const double lambda = es.eigenvalues()(i);
        if (lambda > 1e-12 * scale) has_pos = true;
        else if (lambda < -1e-12 * scale) has_neg = true;
    }
    return has_pos && has_neg;
}

}  // namespace mf::linear_algebra
