// la_internal.h — linear_algebra 包内部辅助(仅头文件)。
//
// 提供基于 Eigen 的矩阵构造、Gauss-Jordan 行阶梯形(含主元列)、
// 秩、零空间基等,替换 Python 的 sympy.Matrix 操作。

#pragma once

#include <charconv>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

#include <Eigen/Dense>

namespace mf::linear_algebra {

using Matrix = Eigen::MatrixXd;
using Vector = Eigen::VectorXd;

namespace detail {

inline Matrix to_matrix(const std::vector<std::vector<double>>& rows) {
    if (rows.empty()) throw std::invalid_argument("矩阵不能为空");
    const Eigen::Index m = static_cast<Eigen::Index>(rows.size());
    const Eigen::Index n = static_cast<Eigen::Index>(rows[0].size());
    Matrix A(m, n);
    for (Eigen::Index i = 0; i < m; ++i) {
        if (static_cast<Eigen::Index>(rows[i].size()) != n)
            throw std::invalid_argument("矩阵各行长度不一致");
        for (Eigen::Index j = 0; j < n; ++j) A(i, j) = rows[i][j];
    }
    return A;
}

inline Vector to_vector(const std::vector<double>& v) {
    Vector x(static_cast<Eigen::Index>(v.size()));
    for (Eigen::Index i = 0; i < x.size(); ++i) x(i) = v[i];
    return x;
}

inline std::vector<std::vector<double>> matrix_to_list(const Matrix& M) {
    std::vector<std::vector<double>> out;
    for (Eigen::Index i = 0; i < M.rows(); ++i) {
        std::vector<double> row;
        for (Eigen::Index j = 0; j < M.cols(); ++j) row.push_back(M(i, j));
        out.push_back(std::move(row));
    }
    return out;
}

// 向量 → 列向量列表 [[x],[y],...],与 Python 的 sp.Matrix.tolist() 一致。
inline std::vector<std::vector<double>> vector_to_col_list(const Vector& v) {
    std::vector<std::vector<double>> out;
    for (Eigen::Index i = 0; i < v.size(); ++i) out.push_back({v(i)});
    return out;
}

// 按列拼接向量列表为矩阵。
inline Matrix hstack(const std::vector<Vector>& vecs) {
    if (vecs.empty()) return Matrix();
    const Eigen::Index rows = vecs[0].size();
    Matrix M(rows, static_cast<Eigen::Index>(vecs.size()));
    for (Eigen::Index j = 0; j < static_cast<Eigen::Index>(vecs.size()); ++j)
        M.col(j) = vecs[j];
    return M;
}

// 向量是否近似在集合内(容差内)。
inline bool vec_in_set(const std::vector<Vector>& set, const Vector& s,
                       double tol = 1e-9) {
    for (const auto& w : set)
        if ((w - s).norm() <= tol) return true;
    return false;
}

// Gauss-Jordan 行阶梯形(部分主元 + 容差),返回主元列(0-based)。
struct RrefResult {
    Matrix rref;
    std::vector<long long> pivots;
};
inline RrefResult rref_with_pivots(const Matrix& M, double tol = 1e-9) {
    Matrix A = M;
    const long long m = A.rows(), n = A.cols();
    long long r = 0;
    std::vector<long long> pivots;
    for (long long c = 0; c < n && r < m; ++c) {
        long long pivot = r;
        double best = std::abs(A(r, c));
        for (long long i = r + 1; i < m; ++i)
            if (std::abs(A(i, c)) > best) {
                best = std::abs(A(i, c));
                pivot = i;
            }
        if (best <= tol) continue;
        if (pivot != r) A.row(r).swap(A.row(pivot));
        A.row(r) /= A(r, c);
        for (long long i = 0; i < m; ++i)
            if (i != r && std::abs(A(i, c)) > tol)
                A.row(i) -= A(i, c) * A.row(r);
        pivots.push_back(c);
        ++r;
    }
    return {A, pivots};
}

inline long long rref_rank(const Matrix& M) {
    return static_cast<long long>(rref_with_pivots(M).pivots.size());
}

// 零空间基(由行阶梯形解齐次方程组 Ax=0)。
inline std::vector<Vector> nullspace_basis(const Matrix& A) {
    const auto rr = rref_with_pivots(A);
    const long long n = A.cols();
    std::vector<bool> pivot_col(n, false);
    for (long long p : rr.pivots) pivot_col[p] = true;
    std::vector<Vector> basis;
    for (long long j = 0; j < n; ++j) {
        if (pivot_col[j]) continue;
        Vector v = Vector::Zero(n);
        v(j) = 1.0;
        long long row = 0;
        for (long long p : rr.pivots) {
            double s = 0.0;
            for (long long f = 0; f < n; ++f)
                if (!pivot_col[f]) s += rr.rref(row, f) * v(f);
            v(p) = -s;
            ++row;
        }
        basis.push_back(v);
    }
    return basis;
}

// 数字格式化(整数值去小数点)。
inline std::string fmt_num(double v) {
    if (std::abs(v) < 1e-12) v = 0.0;
    char buf[32];
    const auto res = std::to_chars(buf, buf + sizeof(buf), v,
                                   std::chars_format::general);
    return std::string(buf, res.ptr);
}

// 四舍五入到 sig 位有效数字(清除浮点尾噪,如 2.9999999999999996 → 3)。
inline double round_sig(double v, int sig = 9) {
    if (v == 0.0 || !std::isfinite(v)) return v;
    const double scale =
        std::pow(10.0, sig - 1 - std::floor(std::log10(std::abs(v))));
    return std::round(v * scale) / scale;
}

}  // namespace detail

}  // namespace mf::linear_algebra
