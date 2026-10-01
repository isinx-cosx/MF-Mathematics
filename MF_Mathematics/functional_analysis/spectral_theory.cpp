#include "spectral_theory.h"

#include <algorithm>
#include <cmath>
#include <complex>
#include <stdexcept>
#include <vector>

namespace mf::functional_analysis {

namespace {

// Eigen 特征值 → 分类为实/复
void split_eigenvalues(const Eigen::MatrixXd& A, double tol,
                       std::vector<double>& real_evals,
                       std::vector<std::complex<double>>& complex_evals) {
    Eigen::EigenSolver<Eigen::MatrixXd> es(A);
    for (long long i = 0; i < A.rows(); ++i) {
        const std::complex<double> ev = es.eigenvalues()(i);
        if (std::abs(ev.imag()) < tol)
            real_evals.push_back(ev.real());
        else
            complex_evals.push_back(ev);
    }
    std::sort(real_evals.begin(), real_evals.end());
}

}  // namespace

SpectrumResult spectrum_approx(const Eigen::MatrixXd& A) {
    if (A.rows() != A.cols()) throw std::invalid_argument("谱仅对方阵定义");
    Eigen::EigenSolver<Eigen::MatrixXd> es(A);

    SpectrumResult res;
    double radius = 0.0;
    for (long long i = 0; i < A.rows(); ++i) {
        const std::complex<double> ev = es.eigenvalues()(i);
        radius = std::max(radius, std::abs(ev));
        if (std::abs(ev.imag()) < 1e-10)
            res.real_evals.push_back(ev.real());
        else
            res.complex_evals.push_back(ev);
    }
    std::sort(res.real_evals.begin(), res.real_evals.end());
    res.spectral_radius = radius;
    return res;
}

SpectrumClassifyResult spectrum_classify(const Eigen::MatrixXd& A, double tol) {
    if (A.rows() != A.cols()) throw std::invalid_argument("谱分类仅对方阵定义");
    std::vector<double> reals;
    std::vector<std::complex<double>> complex_evals;
    split_eigenvalues(A, tol, reals, complex_evals);

    // Python: point_spectrum = 实特征值(排序) + 复特征值对
    SpectrumClassifyResult res;
    for (double r : reals) res.point_spectrum.emplace_back(r, 0.0);
    for (const auto& c : complex_evals) res.point_spectrum.push_back(c);
    res.is_self_adjoint = A.isApprox(A.transpose(), tol);
    return res;
}

SpectralTheoremResult spectral_theorem(const Eigen::MatrixXd& A) {
    if (A.rows() != A.cols()) throw std::invalid_argument("谱定理仅适用于方阵");
    const bool symmetric = A.isApprox(A.transpose(), 1e-8);

    SpectralTheoremResult res;
    res.is_self_adjoint = symmetric;
    if (symmetric) {
        // 自伴:A = QΛQᵀ,Q 正交
        Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> es(A);
        const Eigen::MatrixXd Q = es.eigenvectors();
        const Eigen::VectorXd evals = es.eigenvalues();
        for (long long i = 0; i < A.rows(); ++i)
            res.eigenvalues.emplace_back(evals(i), 0.0);
        for (long long i = 0; i < A.cols(); ++i) {
            const Eigen::VectorXd col = Q.col(i);
            std::vector<std::complex<double>> vec;
            vec.reserve(static_cast<std::size_t>(col.size()));
            for (long long k = 0; k < col.size(); ++k)
                vec.emplace_back(col(k), 0.0);
            res.eigenvectors.push_back(std::move(vec));
        }
        const Eigen::MatrixXd recon = Q * evals.asDiagonal() * Q.transpose();
        res.reconstruction_error = (recon - A).cwiseAbs().maxCoeff();
    } else {
        // 非自伴：保留完整的复特征对。
        // 旧实现只取实部：±i 被说成 0、两列特征向量变成同一个（秩 1），
        // 却用**复数**去算重构误差、报出 0 —— 给错误结果盖了章。
        // 现在报出去的就是复特征对，误差也按同一份数据算，字段不再说谎。
        Eigen::EigenSolver<Eigen::MatrixXd> es(A);
        const Eigen::VectorXcd evals = es.eigenvalues();
        const Eigen::MatrixXcd Qc = es.eigenvectors();
        for (long long i = 0; i < A.cols(); ++i) {
            const std::complex<double> lam = evals(i);
            res.eigenvalues.push_back(lam);
            if (std::abs(lam.imag()) > 1e-10) res.has_complex = true;
            const Eigen::VectorXcd col = Qc.col(i);
            std::vector<std::complex<double>> vec;
            vec.reserve(static_cast<std::size_t>(col.size()));
            for (long long k = 0; k < col.size(); ++k)
                vec.push_back(std::complex<double>(col(k).real(), col(k).imag()));
            res.eigenvectors.push_back(std::move(vec));
        }
        const Eigen::MatrixXcd Lambda = evals.asDiagonal();
        const Eigen::MatrixXcd Qinv = Qc.inverse();
        const Eigen::MatrixXcd recon = Qc * Lambda * Qinv;
        res.reconstruction_error = (recon - A.cast<std::complex<double>>())
                                       .cwiseAbs().maxCoeff();
    }
    return res;
}

}  // namespace mf::functional_analysis
