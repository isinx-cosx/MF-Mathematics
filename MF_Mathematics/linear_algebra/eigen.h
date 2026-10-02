// eigen.h — 特征值与特征向量:特征值、特征向量、特征多项式、可对角化、对角化。
//
// 特征多项式 det(A-λI) 用 SymEngine 符号计算;其余用 Eigen 数值。
//
// ⚠ 复数特征值必须保留虚部。
//   旧实现写的是 es.eigenvalues()(i).real()，把一个复共轭对的虚部直接丢掉：
//   旋转矩阵 [[0,-1],[1,0]] 的真特征值是 ±i，却返回 [0, 0]；
//   [[4,1,2],[0,3,5],[1,0,6]] 的真特征值 7.0573、2.9714±1.1097i 返回成
//   7.0573、2.9714、2.9714 —— 虚部没了，还凭空多出一个"重根"。
//   eigenvectors 更糟：返回的 (λ, v) 连 Av = λv 都不满足。
//   原版 Python(linear_algebra/eigen.py 的 complex(v)、sympy 的 eigenvects())
//   是保留复数的，所以这是移植时引入的回归。

#pragma once

#include <complex>
#include <string>
#include <vector>

#include "la_internal.h"

namespace mf::linear_algebra {

// 特征值(含重数)。value 为复数，虚部为 0 时就是实特征值。
struct EigenvalueInfo {
    std::complex<double> value{0.0, 0.0};
    long long multiplicity = 1;
};
struct EigenvaluesResult {
    std::vector<std::complex<double>> values;  // 按出现顺序(含重数)
    std::vector<EigenvalueInfo> with_multiplicity;
    bool has_complex = false;  // 是否存在非实特征值
    std::string method;
    std::string note;
};
EigenvaluesResult eigenvalues(
    const std::vector<std::vector<double>>& matrix);

// 特征向量(与特征值配对)。特征向量同样可能是复向量。
struct Eigenpair {
    std::complex<double> eigenvalue{0.0, 0.0};
    std::vector<std::complex<double>> eigenvector;
    long long multiplicity = 1;
};
struct EigenvectorsResult {
    std::vector<Eigenpair> eigenpairs;
    bool has_complex = false;
    std::string method;
    std::string note;
};
EigenvectorsResult eigenvectors(
    const std::vector<std::vector<double>>& matrix);

// 特征多项式 det(A - λI)(SymEngine 符号计算)。
std::string characteristic_polynomial(
    const std::vector<std::vector<double>>& matrix);

// 可对角化(实数域上):无复特征值，且各特征值的几何重数之和 == 矩阵阶数。
bool is_diagonalizable(
    const std::vector<std::vector<double>>& matrix);

// 对角化 A = P·D·P⁻¹(实数域上)。
struct DiagonalizeResult {
    bool diagonalizable = false;
    Matrix P;
    Matrix D;
    std::string reason;  // 不可对角化时的说明
};
DiagonalizeResult diagonalize(
    const std::vector<std::vector<double>>& matrix);

}  // namespace mf::linear_algebra
