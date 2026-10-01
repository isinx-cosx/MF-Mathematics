#include "matrix_numerical.h"

#include <cmath>
#include <complex>
#include <stdexcept>
#include <utility>
#include <vector>

namespace mf::numerical {

std::pair<Matrix, Matrix> lu_decomposition(const Matrix& A) {
    if (A.rows() != A.cols()) throw std::invalid_argument("矩阵必须为方阵");
    const long long n = A.rows();
    Matrix L = Matrix::Zero(n, n), U = Matrix::Zero(n, n);
    for (long long i = 0; i < n; ++i) {
        for (long long j = i; j < n; ++j) {
            double s = 0.0;
            for (long long k = 0; k < i; ++k) s += L(i, k) * U(k, j);
            U(i, j) = A(i, j) - s;
        }
        if (std::abs(U(i, i)) < 1e-14)
            throw std::invalid_argument("矩阵奇异或需要行交换: 主元接近零");
        L(i, i) = 1.0;
        for (long long j = i + 1; j < n; ++j) {
            double s = 0.0;
            for (long long k = 0; k < i; ++k) s += L(j, k) * U(k, i);
            L(j, i) = (A(j, i) - s) / U(i, i);
        }
    }
    return {L, U};
}

Vector jacobi_iteration(const Matrix& A, const Vector& b, const Vector& x0,
                        double tol, int max_iter, int& iterations) {
    const long long n = A.rows();
    const Vector diag = A.diagonal();
    for (long long i = 0; i < n; ++i)
        if (std::abs(diag(i)) < 1e-15)
            throw std::invalid_argument("对角元素含零,无法直接使用雅可比迭代");
    Vector x = x0, x_new(n);
    iterations = 0;
    for (int k = 0; k < max_iter; ++k) {
        for (long long i = 0; i < n; ++i) {
            double s = 0.0;
            for (long long j = 0; j < n; ++j)
                if (i != j) s += A(i, j) * x(j);
            x_new(i) = (b(i) - s) / A(i, i);
        }
        const double diff = (x_new - x).norm();
        x = x_new;
        iterations = k + 1;
        if (diff < tol) break;
    }
    return x;
}

Vector gauss_seidel(const Matrix& A, const Vector& b, const Vector& x0,
                    double tol, int max_iter, int& iterations) {
    const long long n = A.rows();
    Vector x = x0;
    iterations = 0;
    for (int k = 0; k < max_iter; ++k) {
        const Vector x_old = x;
        for (long long i = 0; i < n; ++i) {
            if (std::abs(A(i, i)) < 1e-15)
                throw std::invalid_argument("对角元素为零");
            double s1 = 0.0, s2 = 0.0;
            for (long long j = 0; j < i; ++j) s1 += A(i, j) * x(j);
            for (long long j = i + 1; j < n; ++j) s2 += A(i, j) * x_old(j);
            x(i) = (b(i) - s1 - s2) / A(i, i);
        }
        iterations = k + 1;
        if ((x - x_old).norm() < tol) break;
    }
    return x;
}

Vector conjugate_gradient(const Matrix& A, const Vector& b, const Vector& x0,
                          double tol, int max_iter, int& iterations) {
    Vector x = x0;
    Vector r = b - A * x;
    Vector p = r;
    double rs_old = r.squaredNorm();
    if (std::sqrt(rs_old) < 1e-15) {
        iterations = 0;
        return x;
    }
    iterations = 0;
    for (int k = 0; k < max_iter; ++k) {
        const Vector Ap = A * p;
        const double pAp = p.dot(Ap);
        if (std::abs(pAp) < 1e-15)
            throw std::invalid_argument("pᵀAp 接近零,矩阵可能非正定或不满足收敛条件");
        const double alpha = rs_old / pAp;
        x += alpha * p;
        r -= alpha * Ap;
        const double rs_new = r.squaredNorm();
        iterations = k + 1;
        if (std::sqrt(rs_new) < tol) break;
        p = r + (rs_new / rs_old) * p;
        rs_old = rs_new;
    }
    return x;
}

PowerResult power_method(const Matrix& A, double tol, int max_iter) {
    if (A.rows() != A.cols()) throw std::invalid_argument("矩阵必须为方阵");
    Vector v = Vector::Random(A.rows());  // 确定性伪随机初始向量
    v.normalize();
    double lambda_old = 0.0, lambda_new = 0.0;
    int iterations = 0;
    for (int k = 0; k < max_iter; ++k) {
        const Vector w = A * v;
        lambda_new = v.dot(w);  // 瑞利商
        v = w.normalized();
        iterations = k + 1;
        if (std::abs(lambda_new - lambda_old) < tol) {
            lambda_old = lambda_new;
            break;
        }
        lambda_old = lambda_new;
    }
    return {lambda_old, v, iterations};
}

std::vector<std::complex<double>> qr_algorithm(const Matrix& A, double tol,
                                               int max_iter) {
    if (A.rows() != A.cols()) throw std::invalid_argument("矩阵必须为方阵");
    const long long n = A.rows();
    Matrix H = A;
    for (int k = 0; k < max_iter; ++k) {
        // H = R·Q(一次 QR 迭代)
        const Eigen::HouseholderQR<Matrix> qr(H);
        const Matrix R = qr.matrixQR().template triangularView<Eigen::Upper>();
        H = R * qr.householderQ();
        double off = 0.0;
        for (long long i = 0; i < n; ++i)
            for (long long j = 0; j < n; ++j)
                if (i != j) off = std::max(off, std::abs(H(i, j)));
        if (off < tol) break;
    }
    // 提取特征值:对角元 + 2×2 块(共轭复根)
    std::vector<std::complex<double>> eigs;
    long long i = 0;
    while (i < n) {
        if (i < n - 1 && std::abs(H(i + 1, i)) > tol) {
            const double a = H(i, i), b = H(i, i + 1);
            const double c = H(i + 1, i), d = H(i + 1, i + 1);
            const double tr = a + d;
            const double det = a * d - b * c;
            const double disc = tr * tr - 4 * det;
            if (disc < 0) {
                const double re = tr / 2;
                const double im = std::sqrt(-disc) / 2;
                eigs.push_back({re, im});
                eigs.push_back({re, -im});
            } else {
                eigs.push_back({(tr + std::sqrt(disc)) / 2, 0.0});
                eigs.push_back({(tr - std::sqrt(disc)) / 2, 0.0});
            }
            i += 2;
        } else {
            eigs.push_back({H(i, i), 0.0});
            i += 1;
        }
    }
    return eigs;
}

}  // namespace mf::numerical
