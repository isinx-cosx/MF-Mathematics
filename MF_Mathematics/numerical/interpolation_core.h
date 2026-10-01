#ifndef INTERPOLATION_CORE_H
#define INTERPOLATION_CORE_H

#include <cmath>
#include <string>
#include <vector>

inline std::vector<double> polymul(const std::vector<double>& a, const std::vector<double>& b) {
    if (a.empty() || b.empty()) return {};
    std::vector<double> res(a.size() + b.size() - 1, 0.0);
    for (size_t i = 0; i < a.size(); ++i) {
        for (size_t j = 0; j < b.size(); ++j) {
            res[i + j] += a[i] * b[j];
        }
    }
    return res;
}

inline std::vector<double> lagrange(const std::vector<double>& x, const std::vector<double>& y) {
    int n = (int)x.size();
    std::vector<double> coeffs(n, 0.0);   // 最终系数

    for (int i = 0; i < n; ++i) {
        // 构造基多项式 Li(x) = ∏_{j≠i} (x - xj) / (xi - xj)
        std::vector<double> basis = {1.0};   // 初始化为常数 1
        double denom = 1.0;
        for (int j = 0; j < n; ++j) {
            if (i == j) continue;
            // 乘以 (x - xj)
            basis = polymul(basis, {1.0, -x[j]});
            denom *= (x[i] - x[j]);
        }
        // 除以分母（常数缩放）
        for (auto& c : basis) {
            c /= denom;
        }
        // 累加到最终系数：coeffs += yi * basis
        for (int k = 0; k < (int)basis.size(); ++k) {
            coeffs[k] += y[i] * basis[k];
        }
    }
    return coeffs;
}

inline std::vector<double> newton(const std::vector<double>& x, const std::vector<double>& y) {
    int n = (int)x.size();
    std::vector<double> div_diff = y;
    for (int j = 1; j < n; j++){
        for (int i = n - 1; i >= j; i--){
            div_diff[i] = (div_diff[i] - div_diff[i-1]) / (x[i] - x[i-j]);
        }
    }
    return div_diff;
}

// 三次样条系数 [a,b,c,d] × (n-1) 展开成一维数组 [a0,b0,c0,d0, a1,b1,c1,d1, ...]
//
// ⚠ 旧实现有内存越界（已修）：
//     `lo(seg-1), up(seg-1)` 把上下次对角带分配成 n-2 个元素，却按**行号**写
//     `up[i] = h[i]`（i 最大到 n-2）→ `up[n-2]` 越界写 1 个 double，并把堆写坏；
//     随后的 Thomas 前代循环 `for i=1..n-1` 又多跑一轮，读 `lo[n-2]`／`up[n-2]`
//     两个越界位置。表现是同一输入重复调用结果不一致（读到未初始化内存），
//     点数稍多（5、7）时直接堆损坏崩进程（0xC0000374）。
//     现在三条带都按 n 分配、按行号索引，带外的元素恒为 0，Thomas 递推不再有
//     下标的错位，也不需要靠 `seg-1` 这种容易算错的尺寸。
inline std::vector<double> cubic_spline(const std::vector<double>& x, const std::vector<double>& y) {
    const int n = (int)x.size();
    if (n != (int)y.size()) throw std::invalid_argument("x 与 y 长度必须相同");
    if (n < 2) throw std::invalid_argument("三次样条至少需要 2 个结点");
    for (int i = 0; i + 1 < n; ++i)
        if (!(x[i + 1] > x[i]))
            throw std::invalid_argument("结点必须严格递增（x[1] < x[2] < …）");
    const int seg = n - 1;

    std::vector<double> h(seg);
    for (int i = 0; i < seg; i++) h[i] = x[i + 1] - x[i];

    // 自然边界条件 M₀ = M_{n-1} = 0，内点方程
    //   h_{i-1}·M_{i-1} + 2(h_{i-1}+h_i)·M_i + h_i·M_{i+1} = 6·(Δ_i − Δ_{i-1})
    // 三条带统一按 n 个元素分配、以下标 i 作行号（带外为 0）。
    std::vector<double> lo(n, 0.0), di(n, 0.0), up(n, 0.0), rhs(n, 0.0);
    di[0] = 1.0;
    di[n - 1] = 1.0;
    for (int i = 1; i <= n - 2; i++) {
        lo[i] = h[i - 1];
        di[i] = 2.0 * (h[i - 1] + h[i]);
        up[i] = h[i];
        rhs[i] = 6.0 * ((y[i + 1] - y[i]) / h[i] - (y[i] - y[i - 1]) / h[i - 1]);
    }

    // Thomas 前代
    for (int i = 1; i <= n - 1; i++) {
        const double w = lo[i] / di[i - 1];
        di[i] -= w * up[i - 1];
        rhs[i] -= w * rhs[i - 1];
    }
    std::vector<double> M(n, 0.0);
    M[n - 1] = rhs[n - 1] / di[n - 1];
    for (int i = n - 2; i >= 0; i--)
        M[i] = (rhs[i] - up[i] * M[i + 1]) / di[i];

    // 系数: [a,b,c,d] per segment
    std::vector<double> coeffs((size_t)seg * 4);
    for (int i = 0; i < seg; i++) {
        coeffs[i * 4 + 0] = y[i];
        coeffs[i * 4 + 1] = (y[i + 1] - y[i]) / h[i] - h[i] * (2 * M[i] + M[i + 1]) / 6;
        coeffs[i * 4 + 2] = M[i] / 2;
        coeffs[i * 4 + 3] = (M[i + 1] - M[i]) / (6 * h[i]);
    }
    return coeffs;
}

inline std::vector<double> least_squares(const std::vector<double>& x,
                                          const std::vector<double>& y,
                                          int degree) {
    int n = (int)x.size(), m = degree + 1;
    std::vector<double> ATA(m * m, 0.0), ATy(m, 0.0);

    for (int i = 0; i < m; i++) {
        for (int j = 0; j < m; j++) {
            double s = 0;
            for (int k = 0; k < n; k++) s += std::pow(x[k], i + j);
            ATA[i*m+j] = s;
        }
        double s = 0;
        for (int k = 0; k < n; k++) s += y[k] * std::pow(x[k], i);
        ATy[i] = s;
    }
    // 高斯消元
    for (int col = 0; col < m; col++) {
        int best = col;
        for (int r = col+1; r < m; r++)
            if (std::fabs(ATA[r*m+col]) > std::fabs(ATA[best*m+col])) best = r;
        for (int j = 0; j < m; j++) std::swap(ATA[col*m+j], ATA[best*m+j]);
        std::swap(ATy[col], ATy[best]);
        double piv = ATA[col*m+col];
        if (std::fabs(piv) < 1e-15) continue;
        for (int r = col+1; r < m; r++) {
            double f = ATA[r*m+col] / piv;
            for (int j = col; j < m; j++) ATA[r*m+j] -= f * ATA[col*m+j];
            ATy[r] -= f * ATy[col];
        }
    }
    std::vector<double> coeffs(m, 0.0);
    for (int i = m-1; i >= 0; i--) {
        double s = ATy[i];
        for (int j = i+1; j < m; j++) s -= ATA[i*m+j] * coeffs[j];
        coeffs[i] = (std::fabs(ATA[i*m+i]) > 1e-15) ? s / ATA[i*m+i] : 0;
    }
    return coeffs;
}

#endif