#include "extras.h"

#include "../special_numeric.h"

#include <algorithm>
#include <cmath>
#include <complex>
#include <limits>
#include <sstream>
#include <stdexcept>

#include <Eigen/Dense>
#include <Eigen/Eigenvalues>

#include <symengine/basic.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/parser.h>
#include <symengine/visitor.h>   // SymEngine::str()

namespace mf::extras {

namespace {

Eigen::MatrixXd to_eigen(const std::vector<std::vector<double>>& A,
                         const char* what) {
    if (A.empty() || A[0].empty())
        throw std::invalid_argument(std::string(what) + "不能为空");
    const std::size_t cols = A[0].size();
    for (std::size_t i = 0; i < A.size(); ++i)
        if (A[i].size() != cols)
            throw std::invalid_argument(std::string(what) + "各行长度不一致");
    Eigen::MatrixXd M(static_cast<long long>(A.size()),
                      static_cast<long long>(cols));
    for (std::size_t i = 0; i < A.size(); ++i)
        for (std::size_t j = 0; j < cols; ++j) M(i, j) = A[i][j];
    return M;
}

std::vector<std::vector<double>> from_eigen(const Eigen::MatrixXd& M) {
    std::vector<std::vector<double>> out(static_cast<std::size_t>(M.rows()));
    for (long long i = 0; i < M.rows(); ++i) {
        out[static_cast<std::size_t>(i)].resize(static_cast<std::size_t>(M.cols()));
        for (long long j = 0; j < M.cols(); ++j) out[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] = M(i, j);
    }
    return out;
}

std::complex<double> eval_z(const std::string& expr) {
    SymEngine::RCP<const SymEngine::Basic> e;
    try {
        e = SymEngine::parse(expr);
    } catch (const std::exception& ex) {
        throw std::invalid_argument(std::string("复数表达式解析失败：") + ex.what());
    }
    try {
        return SymEngine::eval_complex_double(*e);
    } catch (const std::exception& ex) {
        throw std::invalid_argument(std::string("复数求值失败：") + ex.what());
    }
}

}  // namespace

/* ── 有限维线性代数 ─────────────────────────────────────────────────────── */

std::vector<std::vector<double>> matrix_multiply(
    const std::vector<std::vector<double>>& A,
    const std::vector<std::vector<double>>& B) {
    const Eigen::MatrixXd MA = to_eigen(A, "矩阵 A");
    const Eigen::MatrixXd MB = to_eigen(B, "矩阵 B");
    if (MA.cols() != MB.rows())
        throw std::invalid_argument("A 的列数（" + std::to_string(MA.cols()) +
                                    "）必须等于 B 的行数（" + std::to_string(MB.rows()) + "）");
    return from_eigen(MA * MB);
}

double spectral_radius(const std::vector<std::vector<double>>& A) {
    const Eigen::MatrixXd M = to_eigen(A, "矩阵 A");
    if (M.rows() != M.cols())
        throw std::invalid_argument("谱半径要求方阵（当前 " + std::to_string(M.rows()) +
                                    "×" + std::to_string(M.cols()) + "）");
    Eigen::EigenSolver<Eigen::MatrixXd> es(M, /*computeEigenvectors=*/false);
    double rho = 0.0;
    for (long long i = 0; i < es.eigenvalues().size(); ++i)
        rho = std::max(rho, std::abs(es.eigenvalues()(i)));
    return rho;
}

std::vector<std::vector<double>> adjoint_operator(
    const std::vector<std::vector<double>>& A) {
    return from_eigen(to_eigen(A, "矩阵 A").transpose());
}

bool is_self_adjoint(const std::vector<std::vector<double>>& A, double tol) {
    const Eigen::MatrixXd M = to_eigen(A, "矩阵 A");
    if (M.rows() != M.cols())
        throw std::invalid_argument("自伴（实对称）只对方阵有意义（当前 " +
                                    std::to_string(M.rows()) + "×" +
                                    std::to_string(M.cols()) + "）");
    return (M - M.transpose()).cwiseAbs().maxCoeff() <= tol;
}

std::string compact_operator_reason(const std::vector<std::vector<double>>& A) {
    const Eigen::MatrixXd M = to_eigen(A, "矩阵 A");
    // 有限维空间里"有界 ⟺ 紧"：单位球是有界闭集，因而紧；线性算子把紧集映成紧集。
    std::ostringstream os;
    os << "有限维空间（这里是 R^" << M.rows() << "）中的线性算子都是有界算子，"
       << "而有限维赋范空间的闭单位球是紧集，有界算子把紧集映成紧集，"
       << "所以该算子必为紧算子 —— 结论不依赖于算子本身，只依赖于空间是有限维的。";
    return os.str();
}

std::string fredholm_alternative(const std::vector<std::vector<double>>& A,
                                 const std::vector<double>& b, bool has_b) {
    const Eigen::MatrixXd M = to_eigen(A, "矩阵 A");
    Eigen::FullPivLU<Eigen::MatrixXd> lu(M);
    const long long r = lu.rank();
    const long long n = M.cols();
    std::ostringstream os;
    os << "rank(A) = " << r << "，未知数个数 n = " << n << "。";
    if (r == n) {
        os << "r = n，齐次共轭方程 Aᵀy=0 只有零解，"
           << "因此对任意 b 方程 Ax=b 都有唯一解（二择一的前一支成立）。";
        return os.str();
    }
    os << "r < n，齐次共轭方程 Aᵀy=0 有非零解（dim ker Aᵀ = " << (M.rows() - r) << "），"
       << "此时 Ax=b 可解当且仅当 b 与 ker Aᵀ 正交。（二择一的后一支成立）";
    if (has_b) {
        if (b.size() != static_cast<std::size_t>(M.rows()))
            throw std::invalid_argument("b 的长度必须等于 A 的行数");
        Eigen::VectorXd bv(static_cast<long long>(b.size()));
        for (std::size_t i = 0; i < b.size(); ++i) bv(static_cast<long long>(i)) = b[i];
        // 增广矩阵的秩与原矩阵相同 ⟺ b 落在列空间里（可解）
        Eigen::MatrixXd aug(M.rows(), M.cols() + 1);
        aug << M, bv;
        Eigen::FullPivLU<Eigen::MatrixXd> lu_aug(aug);
        os << " 本次 b 的判定：增广矩阵 rank = " << lu_aug.rank()
           << (lu_aug.rank() == r ? " = rank(A)，b 在列空间中，方程有解。"
                                  : " > rank(A)，b 不在列空间中，方程无解。");
    }
    return os.str();
}

std::vector<double> riesz_representer(const std::vector<double>& x) {
    if (x.empty()) throw std::invalid_argument("向量不能为空");
    // 有限维 Hilbert 空间：每个连续线性泛函 f 都有唯一表示元 y，使 f(v) = <v, y>。
    // 对 f(v) = <v, x> 而言，表示元就是 x 自己（唯一性由内积正定性给出）。
    return x;
}

/* ── 复数 ───────────────────────────────────────────────────────────────── */

std::string complex_conjugate(const std::string& expr) {
    SymEngine::RCP<const SymEngine::Basic> e;
    try {
        e = SymEngine::parse(expr);
    } catch (const std::exception& ex) {
        throw std::invalid_argument(std::string("复数表达式解析失败：") + ex.what());
    }
    const auto c = SymEngine::conjugate(e);
    return SymEngine::str(*SymEngine::expand(c));
}

double complex_modulus(const std::string& expr) {
    return std::abs(eval_z(expr));
}

double complex_argument(const std::string& expr) {
    return std::arg(eval_z(expr));
}

double dirichlet_eta(double s) {
    // η(s) = (1 - 2^{1-s}) ζ(s)；s=1 处 2^{0}=1 使因子为零，而 ζ(1) 发散，
    // 这里是可去奇点（η(1)=ln2），按极限补上。
    if (std::abs(s - 1.0) < 1e-12) return std::log(2.0);
    const double z = mf::num::zeta_real(s);
    return (1.0 - std::pow(2.0, 1.0 - s)) * z;
}

}  // namespace mf::extras
