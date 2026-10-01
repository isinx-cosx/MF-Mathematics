// numerical_core.h — 纯 C++ 数值计算
// 零依赖：不依赖 pybind11、Python、Qt，C# 可直接 P/Invoke

#ifndef NUMERICAL_CORE_H
#define NUMERICAL_CORE_H

#include <algorithm>
#include <cmath>
#include <functional>
#include <string>

// 标准双精度机器 eps = 2^-52（数值微分的舍入误差量级以此为准）。
inline constexpr double kMachineEps = 2.220446049250313e-16;

// ── 梯形法则 ─────────────────────────────────────────────
inline double trapezoidal(double (*f)(double), double a, double b, int n) {
    double h = (b - a) / n;
    double s = 0.5 * (f(a) + f(b));
    for (int i = 1; i < n; i++) {
        s += f(a + i * h);
    }
    return s * h;
}

// ── 辛普森法则 ───────────────────────────────────────────
inline double simpson(double (*f)(double), double a, double b, int n) {
    if (n % 2 != 0) n += 1;
    double h = (b - a) / n;
    double s = f(a) + f(b);
    for (int i = 1; i < n; i++) {
        double x = a + i * h;
        s += f(x) * (i % 2 == 0 ? 2.0 : 4.0);
    }
    return s * h / 3.0;
}

// ── 高斯求积 (n=2,3,4) ───────────────────────────────────
inline double gauss_quad(double (*f)(double), double a, double b, int n) {
    static const double nodes[][4] = {
        {}, {},
        {-0.5773502692, 0.5773502692},
        {-0.7745966692, 0.0, 0.7745966692},
        {-0.8611363116, -0.3399810436, 0.3399810436, 0.8611363116}
    };
    static const double weights[][4] = {
        {}, {},
        {1.0, 1.0},
        {0.5555555556, 0.8888888889, 0.5555555556},
        {0.3478548451, 0.6521451549, 0.6521451549, 0.3478548451}
    };
    if (n < 2 || n > 4) return 0.0;

    double mid = (b + a) / 2.0;
    double half = (b - a) / 2.0;
    double s = 0.0;
    for (int i = 0; i < n; i++) {
        s += weights[n][i] * f(mid + half * nodes[n][i]);
    }
    return half * s;
}

// ── 数值微分 ──────────────────────────────────────────────
inline double derivative(double (*f)(double), double x, double h,
                         const std::string& method) {
    if (method == "forward")
        return (f(x + h) - f(x)) / h;
    else if (method == "backward")
        return (f(x) - f(x - h)) / h;
    else
        return (f(x + h) - f(x - h)) / (2.0 * h);
}

// ── 高阶导数幅值的有限差分探针 ────────────────────────────
//
// 中心差分 (f(x+h)-f(x-h))/(2h) 的误差由两部分构成：
//   舍入误差 ~ eps·|f(x)|/h ，截断误差 ~ h²·|f'''(x)|/6 。
// 两者相加对 h 求极小得 h* = (3·eps·|f(x)|/|f'''(x)|)^(1/3)；
// 单侧差分 (f(x+h)-f(x))/h 的截断误差 ~ h·|f''(x)|/2，故
//   h* = (2·eps·|f(x)|/|f''(x)|)^(1/2) 。
// 关键点：h* 只取决于「|f(x)| 与高阶导数幅值的**比值**」，与 f 的绝对量级无关。
// 例如 f = e^x 时 |f'''| = |f|，比值恒为 1，h* ≈ 8.73e-6 与 x 无关；
// 旧实现写成 h = eps^(1/3)·|f(x)|，在 x=10 处被 e^10 ≈ 2.2e4 放大到 0.133 后
// 又截断到 0.1，比真最优步长大 1.1e4 倍。
//
// 这里用中心差分探针在一串量级的步长上估计 |f^{(k)}(x)|（k ∈ {2,3}）并取中位数：
// 大探针受截断误差影响、小探针受舍入误差影响，中位数对两端都稳健；只需要量级正确
// （h* 是它的立方/平方根，量级误差被大幅压缩）。分辨不出该导数的探针会被舍入水位
// 过滤掉（否则 x²、线性函数这类 f^{(k)}≡0 的函数会把差分噪声当成导数，h* 被噪声
// 顶到上限），全部被过滤时返回 0，由调用方退到尺度默认值。
inline double derivative_magnitude(const std::function<double(double)>& f,
                                   double x, int order) {
    if (order != 2 && order != 3) return 0.0;
    // 探针步长阶梯（绝对量级，跨 6 个数量级），下限是 x 的浮点分辨率：
    // δ ≲ eps·|x| 时 x±δ 在双精度下已无法区分。
    const double dmin = 100.0 * kMachineEps * std::max(1.0, std::fabs(x));
    const double ladder[6] = {1e-1, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6};
    double est[6];
    int n = 0;
    for (int k = 0; k < 6; ++k) {
        const double h = std::max(ladder[k], dmin);
        double num, den, noise;
        if (order == 3) {
            const double a1 = f(x + 2 * h), a2 = f(x + h);
            const double a3 = f(x - h), a4 = f(x - 2 * h);
            if (!(std::isfinite(a1) && std::isfinite(a2) && std::isfinite(a3) &&
                  std::isfinite(a4)))
                continue;
            den = 2.0 * h * h * h;
            num = a1 - 2.0 * a2 + 2.0 * a3 - a4;
            noise = 4.0 * kMachineEps *
                    (std::fabs(a1) + 2.0 * std::fabs(a2) + 2.0 * std::fabs(a3) +
                     std::fabs(a4));
        } else {
            const double a1 = f(x + h), a0 = f(x), a3 = f(x - h);
            if (!(std::isfinite(a1) && std::isfinite(a0) && std::isfinite(a3)))
                continue;
            den = h * h;
            num = a1 - 2.0 * a0 + a3;
            noise = 4.0 * kMachineEps *
                    (std::fabs(a1) + 2.0 * std::fabs(a0) + std::fabs(a3));
        }
        const double mag = std::fabs(num) / den;
        if (!std::isfinite(mag) || mag <= noise / den) continue;  // 该探针分辨不出
        est[n++] = mag;
    }
    if (n == 0) return 0.0;
    std::sort(est, est + n);
    return est[n / 2];
}

// ── 最优步长 ──────────────────────────────────────────────
//
// method 的合法性由 API 层校验(numerical_integration.cpp)；此处把 central 之外的
// 方法一律按单侧差分处理。
inline double optimal_step_impl(const std::function<double(double)>& f, double x,
                                const std::string& method) {
    const bool central = (method == "central");
    const double scale = std::max(1.0, std::fabs(x));
    const double f_val = std::fabs(f(x));
    const double fallback = central ? std::pow(kMachineEps, 1.0 / 3.0) * scale
                                    : std::pow(kMachineEps, 1.0 / 2.0) * scale;

    double h_opt = fallback;
    if (std::isfinite(f_val) && f_val > 0.0) {
        const double d = derivative_magnitude(f, x, central ? 3 : 2);
        if (std::isfinite(d) && d > 0.0) {
            // 高阶导数不消失：h* 由 |f| 与该导数之比决定（与 f 的绝对量级无关）。
            h_opt = central ? std::pow(3.0 * kMachineEps * f_val / d, 1.0 / 3.0)
                            : std::pow(2.0 * kMachineEps * f_val / d, 1.0 / 2.0);
        }
        // 高阶导数数值上为 0（如 x²）：截断误差项消失，无法据此定 h*，
        // 退回到按 x 的尺度给出默认步长。
    }
    if (!std::isfinite(h_opt) || h_opt < 1e-12) h_opt = 1e-12;
    if (h_opt > 0.1) h_opt = 0.1;
    return h_opt;
}

// 兼容既有裸函数指针接口的薄包装。
inline double optimal_step(double (*f)(double), double x,
                           const std::string& method) {
    return optimal_step_impl([f](double t) { return f(t); }, x, method);
}

#endif
