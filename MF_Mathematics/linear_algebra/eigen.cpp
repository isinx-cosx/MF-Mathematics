// eigen.cpp — 特征值内核:特征多项式用 SymEngine,其余 Eigen 数值。

#include "eigen.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>

#include <Eigen/Dense>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/matrix.h>
#include <symengine/printers.h>
#include <symengine/simplify.h>
#include <symengine/symbol.h>

namespace mf::linear_algebra {

using detail::to_matrix;
using detail::rref_rank;

namespace {

void require_square(const Matrix& A) {
    if (A.rows() != A.cols())
        throw std::invalid_argument("矩阵必须是方阵");
}

// 复数的「有效数字」规整，与实数的 round_sig 一致。
std::complex<double> round_sig_c(const std::complex<double>& z, int sig = 9) {
    return {detail::round_sig(z.real(), sig), detail::round_sig(z.imag(), sig)};
}

// 虚部是否可忽略（相对量级判断，避免把 1e-17 的数值噪声显示成虚数）。
bool negligible_imag(const std::complex<double>& z) {
    return std::abs(z.imag()) <= 1e-10 * std::max(1.0, std::abs(z.real()));
}

// 数值特征值。**保留虚部** —— Eigen 的 EigenSolver 本来就返回复数。
std::vector<std::complex<double>> numeric_eigenvalues(const Matrix& A) {
    Eigen::EigenSolver<Matrix> es(A);
    std::vector<std::complex<double>> out;
    out.reserve(static_cast<std::size_t>(A.rows()));
    for (Eigen::Index i = 0; i < A.rows(); ++i) {
        const auto ev = es.eigenvalues()(i);
        std::complex<double> z(ev.real(), ev.imag());
        if (negligible_imag(z)) z = {z.real(), 0.0};
        out.push_back(round_sig_c(z));
    }
    return out;
}

// 按容差聚类求重数。复平面上比距离 —— 共轭对 a±bi 是两个不同的特征值，
// 不会再被当成"重根 2"（旧实现只看实部，正是这个错误来源）。
std::vector<EigenvalueInfo> multiplicity_of(
    const std::vector<std::complex<double>>& vals, double tol = 1e-9) {
    std::vector<std::complex<double>> sorted = vals;
    std::sort(sorted.begin(), sorted.end(),
              [](const std::complex<double>& a, const std::complex<double>& b) {
                  return a.real() != b.real() ? a.real() < b.real()
                                              : a.imag() < b.imag();
              });
    std::vector<EigenvalueInfo> out;
    for (const auto& v : sorted) {
        if (out.empty() || std::abs(v - out.back().value) > tol) {
            EigenvalueInfo info;
            info.value = v;
            info.multiplicity = 1;
            out.push_back(info);
        } else {
            ++out.back().multiplicity;
        }
    }
    return out;
}

bool any_complex(const std::vector<std::complex<double>>& vals) {
    for (const auto& v : vals)
        if (std::abs(v.imag()) > 1e-10) return true;
    return false;
}

// 复特征值的可读形式，用于说明文字（如 "2.971365+1.109746i"）。
std::string fmt_complex(const std::complex<double>& z) {
    if (negligible_imag(z)) return detail::fmt_num(z.real());
    const std::string re = detail::fmt_num(z.real());
    const std::string im = detail::fmt_num(std::abs(z.imag()));
    return re + (z.imag() >= 0 ? "+" : "-") + im + "i";
}

}  // namespace

EigenvaluesResult eigenvalues(
    const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    EigenvaluesResult r;
    r.values = numeric_eigenvalues(A);
    r.has_complex = any_complex(r.values);
    r.with_multiplicity = multiplicity_of(r.values);
    r.method = "数值(Eigen)";
    if (r.has_complex)
        r.note = "存在复特征值（以 {re, im} 给出虚部），并非实特征值";
    if (A.rows() >= 5) {
        if (!r.note.empty()) r.note += "；";
        r.note += "矩阵维度 ≥5,使用数值方法";
    }
    return r;
}

EigenvectorsResult eigenvectors(
    const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    Eigen::EigenSolver<Matrix> es(A);

    EigenvectorsResult r;
    r.method = "数值(Eigen)";
    for (Eigen::Index i = 0; i < A.rows(); ++i) {
        const auto raw = es.eigenvalues()(i);
        std::complex<double> lam(raw.real(), raw.imag());
        if (negligible_imag(lam)) lam = {lam.real(), 0.0};
        if (std::abs(lam.imag()) > 1e-10) r.has_complex = true;

        Eigenpair p;
        p.eigenvalue = round_sig_c(lam);
        p.multiplicity = 1;
        Eigen::VectorXcd v(static_cast<Eigen::Index>(A.rows()));
        for (Eigen::Index k = 0; k < A.rows(); ++k)
            v(k) = es.eigenvectors()(k, i);
        const double nrm = v.norm();
        if (nrm > 1e-15) v /= nrm;
        p.eigenvector.reserve(static_cast<std::size_t>(A.rows()));
        for (Eigen::Index k = 0; k < A.rows(); ++k) {
            std::complex<double> c(v(k).real(), v(k).imag());
            if (negligible_imag(c)) c = {c.real(), 0.0};
            p.eigenvector.push_back(round_sig_c(c));
        }
        r.eigenpairs.push_back(std::move(p));
    }
    if (r.has_complex) r.note = "存在复特征值，对应的特征向量也是复向量";
    if (A.rows() >= 5) {
        if (!r.note.empty()) r.note += "；";
        r.note += "矩阵维度 ≥5,使用数值方法";
    }
    return r;
}

std::string characteristic_polynomial(
    const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    const auto lam = SymEngine::symbol("λ");
    SymEngine::DenseMatrix M(static_cast<unsigned>(A.rows()),
                             static_cast<unsigned>(A.cols()));
    for (long long i = 0; i < A.rows(); ++i)
        for (long long j = 0; j < A.cols(); ++j) {
            if (i == j)
                M.set(static_cast<unsigned>(i), static_cast<unsigned>(j),
                      SymEngine::sub(SymEngine::real_double(A(i, j)), lam));
            else
                M.set(static_cast<unsigned>(i), static_cast<unsigned>(j),
                      SymEngine::real_double(A(i, j)));
        }
    const auto poly = SymEngine::simplify(M.det());
    return SymEngine::str(*poly);
}

bool is_diagonalizable(const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    const long long n = A.rows();
    const auto vals = numeric_eigenvalues(A);
    // 有复特征值 → 在实数域上不可对角化。
    // 旧实现拿"实部"去构造 A - aI 再算零空间，复共轭对的实部根本不是特征值，
    // 于是几何重数恒为 0、结论恒为 false，理由却写成"几何重数之和 < 代数重数"，
    // 属于用错误的推理得出（碰巧）可用的结论。这里改成如实判断。
    if (any_complex(vals)) return false;
    const auto groups = multiplicity_of(vals);
    long long geom_sum = 0;
    for (const auto& g : groups) {
        const Matrix shifted = A - g.value.real() * Matrix::Identity(n, n);
        geom_sum += n - rref_rank(shifted);
    }
    return geom_sum == n;
}

DiagonalizeResult diagonalize(const std::vector<std::vector<double>>& matrix) {
    const Matrix A = to_matrix(matrix);
    require_square(A);
    const long long n = A.rows();

    const auto vals = numeric_eigenvalues(A);
    if (any_complex(vals)) {
        DiagonalizeResult r;
        r.reason = "存在复特征值（如 λ = " + fmt_complex(vals.front()) +
                   "），在实数域上不可对角化；"
                   "在复数域上它可能有复特征向量，本函数只在实数域上给 P、D。";
        return r;
    }

    if (!is_diagonalizable(matrix)) {
        DiagonalizeResult r;
        r.reason = "不可对角化(几何重数之和 < 代数重数)";
        return r;
    }

    Eigen::EigenSolver<Matrix> es(A);
    DiagonalizeResult r;
    r.diagonalizable = true;
    r.P = es.eigenvectors().real();
    r.D = es.eigenvalues().real().asDiagonal();
    // 归一化 P 的列。
    for (Eigen::Index i = 0; i < n; ++i) {
        const double nrm = r.P.col(i).norm();
        if (nrm > 1e-15) r.P.col(i) /= nrm;
    }
    return r;
}

}  // namespace mf::linear_algebra
