// matrix_numerical.h — 线性代数数值方法(基于 Eigen)。
//
// 涵盖 LU 分解、雅可比/高斯-赛德尔/共轭梯度迭代、幂法、QR 特征值。
// 矩阵用 Eigen::MatrixXd / VectorXd 表示。

#pragma once

#include <complex>
#include <utility>
#include <vector>

#include <Eigen/Dense>


namespace mf::numerical {

using Matrix = Eigen::MatrixXd;
using Vector = Eigen::VectorXd;

// LU 分解(Doolittle,L 为单位下三角,无选主元)。
// 主元接近零(矩阵奇异或需行交换)抛 std::invalid_argument。
std::pair<Matrix, Matrix> lu_decomposition(const Matrix& A);

// 雅可比迭代 Ax = b。对角含零抛异常。
Vector jacobi_iteration(const Matrix& A, const Vector& b, const Vector& x0,
                               double tol, int max_iter, int& iterations);

// 高斯-赛德尔迭代。
Vector gauss_seidel(const Matrix& A, const Vector& b, const Vector& x0,
                           double tol, int max_iter, int& iterations);

// 共轭梯度(A 需对称正定)。pᵀAp≈0 抛异常。
Vector conjugate_gradient(const Matrix& A, const Vector& b,
                                 const Vector& x0, double tol, int max_iter,
                                 int& iterations);

// 幂法求按模最大特征值及特征向量(确定性随机初始向量)。
struct PowerResult {
    double eigenvalue = 0.0;
    Vector eigenvector;
    int iterations = 0;
};
PowerResult power_method(const Matrix& A, double tol, int max_iter);

// QR 迭代(带 Householder QR)求全部特征值,返回复特征值(实部, 虚部)。
std::vector<std::complex<double>> qr_algorithm(const Matrix& A,
                                                      double tol, int max_iter);

}  // namespace mf::numerical
