// Eigen 5.0.1 验证 demo
#include <Eigen/Dense>
#include <iostream>

int main()
{
    // ===== 1. 基本矩阵运算 =====
    Eigen::MatrixXd A(2, 2);
    A << 4.0, 1.0, 2.0, 3.0;
    std::cout << "A =\n" << A << "\n\n";
    std::cout << "det(A)      = " << A.determinant() << "\n";
    std::cout << "rank(A)     = " << A.fullPivLu().rank() << "\n";
    std::cout << "A^-1 =\n" << A.inverse() << "\n";

    // ===== 2. 特征值/特征向量 =====
    Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> es(A);
    std::cout << "\neigenvalues  = " << es.eigenvalues().transpose() << "\n";
    std::cout << "eigenvectors =\n" << es.eigenvectors() << "\n";

    // ===== 3. QR 分解（线性回归用） =====
    Eigen::MatrixXd X(4, 2);
    X << 1.0, 1.0, 1.0, 2.0, 1.0, 3.0, 1.0, 4.0;
    Eigen::VectorXd y(4);
    y << 2.1, 3.9, 6.2, 7.8;
    Eigen::VectorXd coef = X.colPivHouseholderQr().solve(y);
    std::cout << "\nQR 最小二乘系数 = " << coef.transpose() << "\n";

    // ===== 4. SVD（矩阵数值秩/伪逆） =====
    Eigen::JacobiSVD<Eigen::MatrixXd> svd(A, Eigen::ComputeThinU | Eigen::ComputeThinV);
    std::cout << "SVD 奇异值    = " << svd.singularValues().transpose() << "\n";
    std::cout << "伪逆 =\n" << svd.solve(Eigen::MatrixXd::Identity(2, 2)) << "\n";

    return 0;
}
