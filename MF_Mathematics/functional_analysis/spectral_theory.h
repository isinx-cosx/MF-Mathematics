// spectral_theory.h — 谱理论:谱近似、谱分类、谱定理验证。
#pragma once

#include <complex>
#include <vector>

#include <Eigen/Dense>

#include "../mf_export.h"

namespace mf::functional_analysis {

// 谱近似:全部特征值(虚部≈0 归入实特征值,其余为复特征值)+ 谱半径。
struct SpectrumResult {
    std::vector<double> real_evals;                  // 升序
    std::vector<std::complex<double>> complex_evals; // 虚部非零
    double spectral_radius = 0.0;
};
MF_API SpectrumResult spectrum_approx(const Eigen::MatrixXd& A);

// 谱分类:有限维矩阵的谱 = 点谱(特征值)。is_self_adjoint 判断自伴性。
struct SpectrumClassifyResult {
    std::vector<std::complex<double>> point_spectrum;
    bool is_self_adjoint = false;
};
MF_API SpectrumClassifyResult spectrum_classify(const Eigen::MatrixXd& A,
                                                double tol = 1e-6);

// 谱定理验证(实对称矩阵 A = QΛQᵀ;非对称给特征分解与重构误差)。
//
// 特征值/特征向量用复数 —— 与同文件的 SpectrumResult、SpectrumClassifyResult 一致。
// 旧实现把非自伴分支强制取 `.real()`，于是 [[0,-1],[1,0]] 的 ±i 被说成 0、两列
// 特征向量还变成同一个（秩 1），而 reconstruction_error 却用**复数**算、报 0 ——
// 等于给错误结果盖章背书。现在拆出来的就是复特征对，误差也按同一份数据算。
struct SpectralTheoremResult {
    std::vector<std::complex<double>> eigenvalues;
    std::vector<std::vector<std::complex<double>>> eigenvectors;
    bool is_self_adjoint = false;
    bool has_complex = false;  // 存在非实特征值（此时不是自伴算子的谱定理场景）
    double reconstruction_error = 0.0;
};
MF_API SpectralTheoremResult spectral_theorem(const Eigen::MatrixXd& A);

}  // namespace mf::functional_analysis
