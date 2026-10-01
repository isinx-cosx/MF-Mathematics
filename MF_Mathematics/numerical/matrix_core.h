#ifndef MATRIX_CORE_H
#define MATRIX_CORE_H

#include <cmath>
#include <cstdlib>
#include <utility>
#include <vector>

// ============================================================================
//  辅助函数（inline，仅本文件内部使用）
// ============================================================================

namespace {

inline double _dot(const std::vector<double>& a, const std::vector<double>& b) {
    double s = 0.0;
    for (size_t i = 0; i < a.size(); i++) s += a[i] * b[i];
    return s;
}

inline double _norm2(const std::vector<double>& v) {
    return std::sqrt(_dot(v, v));
}

inline void _matvec(const std::vector<std::vector<double>>& A,
                     const std::vector<double>& x,
                     std::vector<double>& out) {
    int n = (int)A.size();
    out.resize(n);
    for (int i = 0; i < n; i++) {
        double s = 0.0;
        for (int j = 0; j < n; j++) s += A[i][j] * x[j];
        out[i] = s;
    }
}

inline void _axpy(double a, const std::vector<double>& x,
                   std::vector<double>& y) {
    for (size_t i = 0; i < y.size(); i++) y[i] += a * x[i];
}

inline void _scale(double a, std::vector<double>& v) {
    for (size_t i = 0; i < v.size(); i++) v[i] *= a;
}

}  // anonymous namespace

// ============================================================================
//  LU 分解（Doolittle 算法）
//  A = L·U, L 主对角线全为 1
//  返回 (L, U)
// ============================================================================

inline std::pair<std::vector<std::vector<double>>,
                  std::vector<std::vector<double>>>
lu_decomposition(const std::vector<std::vector<double>>& A_in) {
    int n = (int)A_in.size();
    std::vector<std::vector<double>> L(n, std::vector<double>(n, 0.0));
    std::vector<std::vector<double>> U(n, std::vector<double>(n, 0.0));
    auto A = A_in;  // 拷贝，因为我们会修改

    for (int i = 0; i < n; i++) {
        // U 的第 i 行
        for (int j = i; j < n; j++) {
            double s = 0.0;
            for (int k = 0; k < i; k++) s += L[i][k] * U[k][j];
            U[i][j] = A[i][j] - s;
        }
        // 当前列主元检查（由 Python 端负责，这里假设已通过检查）
        L[i][i] = 1.0;
        // L 的第 i 列（i+1 行开始）
        for (int j = i + 1; j < n; j++) {
            double s = 0.0;
            for (int k = 0; k < i; k++) s += L[j][k] * U[k][i];
            L[j][i] = (A[j][i] - s) / U[i][i];
        }
    }
    return {L, U};
}

// ── LU 求解器（类 + RAII 版本）───────────────────────────
class LUSolver{
private:
    int _n;
    double* _L;
    double* _U;

public:
    LUSolver(const std::vector<std::vector<double>>& A) {
        _n = (int)A.size();
        _L = new double[_n * _n];
        _U = new double[_n * _n];

        // 清零
        for (int i = 0; i < _n * _n; i++) _L[i] = _U[i] = 0.0;

        // Doolittle LU 分解
        for (int i = 0; i < _n; i++) {
            for (int j = i; j < _n; j++) {
                double s = 0.0;
                for (int k = 0; k < i; k++)
                    s += _L[i * _n + k] * _U[k * _n + j];
                _U[i * _n + j] = A[i][j] - s;
            }
            _L[i * _n + i] = 1.0;
            for (int j = i + 1; j < _n; j++) {
                double s = 0.0;
                for (int k = 0; k < i; k++)
                    s += _L[j * _n + k] * _U[k * _n + i];
                _L[j * _n + i] = (A[j][i] - s) / _U[i * _n + i];
            }
        }
    }

    ~LUSolver() {
        delete[] _L;
        delete[] _U;
    }

    std::vector<double> solve(const std::vector<double>& b) const {
        std::vector<double> y(_n), x(_n);

        // 前代 L·y = b
        for (int i = 0; i < _n; i++) {
            double s = 0.0;
            for (int j = 0; j < i; j++)
                s += _L[i * _n + j] * y[j];
            y[i] = b[i] - s;
        }

        // 回代 U·x = y
        for (int i = _n - 1; i >= 0; i--) {
            double s = 0.0;
            for (int j = i + 1; j < _n; j++)
                s += _U[i * _n + j] * x[j];
            x[i] = (y[i] - s) / _U[i * _n + i];
        }
        return x;
    }
};

// ============================================================================
//  雅可比迭代法  Ax = b
//  收敛条件：A 严格对角占优
//  返回解向量；若未收敛则返回 max_iter 步后的结果
// ============================================================================

inline std::vector<double> jacobi_iteration(
    const std::vector<std::vector<double>>& A,
    const std::vector<double>& b,
    const std::vector<double>& x0,
    double tol,
    int max_iter,
    int& iterations)      // 输出：实际迭代次数
{
    int n = (int)A.size();
    std::vector<double> x = x0;
    std::vector<double> x_new(n);
    iterations = 0;

    for (int k = 0; k < max_iter; k++) {
        for (int i = 0; i < n; i++) {
            double s = 0.0;
            for (int j = 0; j < n; j++) {
                if (i != j) s += A[i][j] * x[j];
            }
            x_new[i] = (b[i] - s) / A[i][i];
        }
        // 计算变化量
        double diff = 0.0;
        for (int i = 0; i < n; i++) {
            double d = x_new[i] - x[i];
            diff += d * d;
        }
        x = x_new;
        iterations = k + 1;
        if (std::sqrt(diff) < tol) break;
    }
    return x;
}

// ============================================================================
//  高斯-赛德尔迭代法  Ax = b
//  每次用最新值更新（比雅可比收敛更快）
// ============================================================================

inline std::vector<double> gauss_seidel(
    const std::vector<std::vector<double>>& A,
    const std::vector<double>& b,
    const std::vector<double>& x0,
    double tol,
    int max_iter,
    int& iterations)
{
    int n = (int)A.size();
    std::vector<double> x = x0;
    iterations = 0;

    for (int k = 0; k < max_iter; k++) {
        std::vector<double> x_old = x;
        for (int i = 0; i < n; i++) {
            double s1 = 0.0;  // 已更新的分量
            for (int j = 0; j < i; j++) s1 += A[i][j] * x[j];
            double s2 = 0.0;  // 旧分量
            for (int j = i + 1; j < n; j++) s2 += A[i][j] * x_old[j];
            x[i] = (b[i] - s1 - s2) / A[i][i];
        }
        double diff = 0.0;
        for (int i = 0; i < n; i++) {
            double d = x[i] - x_old[i];
            diff += d * d;
        }
        iterations = k + 1;
        if (std::sqrt(diff) < tol) break;
    }
    return x;
}

// ============================================================================
//  共轭梯度法  Ax = b（A 需对称正定）
// ============================================================================

inline std::vector<double> conjugate_gradient(
    const std::vector<std::vector<double>>& A,
    const std::vector<double>& b,
    const std::vector<double>& x0,
    double tol,
    int max_iter,
    int& iterations)
{
    int n = (int)A.size();
    std::vector<double> x = x0;

    // r = b - A·x
    std::vector<double> Ax(n);
    _matvec(A, x, Ax);
    std::vector<double> r(n), p(n);
    for (int i = 0; i < n; i++) r[i] = b[i] - Ax[i];
    p = r;

    double rs_old = _dot(r, r);
    if (std::sqrt(rs_old) < 1e-15) {
        iterations = 0;
        return x;
    }

    iterations = 0;
    for (int k = 0; k < max_iter; k++) {
        _matvec(A, p, Ax);        // Ap = A·p
        double pAp = _dot(p, Ax);

        if (std::fabs(pAp) < 1e-15) break;

        double alpha = rs_old / pAp;
        // x = x + alpha·p
        for (int i = 0; i < n; i++) x[i] += alpha * p[i];
        // r = r - alpha·Ap
        for (int i = 0; i < n; i++) r[i] -= alpha * Ax[i];

        double rs_new = _dot(r, r);
        iterations = k + 1;
        if (std::sqrt(rs_new) < tol) break;

        double beta = rs_new / rs_old;
        // p = r + beta·p
        for (int i = 0; i < n; i++) p[i] = r[i] + beta * p[i];
        rs_old = rs_new;
    }
    return x;
}

// ============================================================================
//  幂法 — 求矩阵按模最大特征值及对应特征向量
// ============================================================================

inline std::pair<double, std::vector<double>>
power_method(const std::vector<std::vector<double>>& A,
              double tol,
              int max_iter,
              int& iterations)
{
    int n = (int)A.size();
    // 初始化随机向量
    std::vector<double> v(n);
    for (int i = 0; i < n; i++) v[i] = (double)std::rand() / RAND_MAX;
    double vn = _norm2(v);
    for (int i = 0; i < n; i++) v[i] /= vn;

    double lambda_old = 0.0, lambda_new = 0.0;
    iterations = 0;

    for (int k = 0; k < max_iter; k++) {
        // w = A·v
        std::vector<double> w(n);
        _matvec(A, v, w);
        // λ = v·w（瑞利商）
        lambda_new = _dot(v, w);
        // v = w / ||w||
        double wn = _norm2(w);
        for (int i = 0; i < n; i++) v[i] = w[i] / wn;

        iterations = k + 1;
        if (std::fabs(lambda_new - lambda_old) < tol) {
            lambda_old = lambda_new;
            break;
        }
        lambda_old = lambda_new;
    }
    return {lambda_old, v};
}

#endif
