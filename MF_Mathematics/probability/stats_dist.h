// stats_dist.h — 统计分布数值工具(仅头文件,内部使用)。
//
// 供 confidence_interval 等需要分位数/累计分布的函数使用。目前包含:
//   betainc     — 正则化不完全贝塔函数 I_x(a, b)
//   t_quantile  — 学生 t 分布分位数(逆 CDF),精度 ~1e-12
//
// t 分布分位数用"对 t-CDF 二分求根"实现,不引入外部数值库。t-CDF 由
// 正则化不完全贝塔表出:F(t;ν) = 1 - ½·I_{ν/(ν+t²)}(ν/2, ½),t ≥ 0。

#pragma once

#include <cmath>
#include <stdexcept>

namespace mf::probability::detail {

// ── 正则化不完全贝塔 I_x(a,b) ──────────────────────────────────────────────

inline double betacf(double a, double b, double x) {
    const int kMaxIt = 200;
    const double kEps = 3e-14;
    const double kFpmin = 1e-300;

    const double qab = a + b;
    const double qap = a + 1.0;
    const double qam = a - 1.0;
    double c = 1.0;
    double d = 1.0 - qab * x / qap;
    if (std::abs(d) < kFpmin) d = kFpmin;
    d = 1.0 / d;
    double h = d;

    for (int m = 1; m <= kMaxIt; ++m) {
        const int m2 = 2 * m;
        double aa = m * (b - m) * x / ((qam + m2) * (a + m2));
        d = 1.0 + aa * d;
        if (std::abs(d) < kFpmin) d = kFpmin;
        c = 1.0 + aa / c;
        if (std::abs(c) < kFpmin) c = kFpmin;
        d = 1.0 / d;
        h *= d * c;

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
        d = 1.0 + aa * d;
        if (std::abs(d) < kFpmin) d = kFpmin;
        c = 1.0 + aa / c;
        if (std::abs(c) < kFpmin) c = kFpmin;
        d = 1.0 / d;
        const double del = d * c;
        h *= del;
        if (std::abs(del - 1.0) < kEps) break;
    }
    return h;
}

inline double betainc(double a, double b, double x) {
    if (x <= 0.0) return 0.0;
    if (x >= 1.0) return 1.0;
    const double bt =
        std::exp(std::lgamma(a + b) - std::lgamma(a) - std::lgamma(b) +
                 a * std::log(x) + b * std::log1p(-x));
    if (x < (a + 1.0) / (a + b + 2.0))
        return bt * betacf(a, b, x) / a;
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b;
}

// ── 学生 t 分布 ─────────────────────────────────────────────────────────────

// 学生 t 分布累计分布函数 F(t;ν),任意实数 t。
inline double t_cdf(double t, double df) {
    const double x = df / (df + t * t);
    // F(t) = 1 - ½·I_x(ν/2, ½),t ≥ 0;由对称性扩展到 t < 0。
    return t >= 0 ? 1.0 - 0.5 * betainc(df / 2.0, 0.5, x)
                  : 0.5 * betainc(df / 2.0, 0.5, x);
}

// 学生 t 分布分位数(逆 CDF):F^{-1}(p;ν)。p ∈ (0,1),ν ≥ 1。
// 返回精度 ~1e-12(二分求根,最大迭代次数内收敛)。
inline double t_quantile(double p, long long df) {
    if (!(p > 0.0 && p < 1.0))
        throw std::invalid_argument("分位数概率必须在 (0,1) 之间");
    if (df < 1) throw std::invalid_argument("t 分布自由度必须 ≥1");
    if (p == 0.5) return 0.0;

    // 求 t ≥ 0 使 F(t) = max(p, 1-p),再按 p 是否 > 0.5 定符号
    const double target = p > 0.5 ? p : 1.0 - p;
    double lo = 0.0, hi = 1.0;
    const int kMaxIt = 200;
    while (t_cdf(hi, df) < target) {
        hi *= 2.0;
        if (hi > 1e15) throw std::runtime_error("t 分布分位数计算未收敛");
    }
    for (int i = 0; i < kMaxIt; ++i) {
        const double mid = 0.5 * (lo + hi);
        if (t_cdf(mid, df) < target)
            lo = mid;
        else
            hi = mid;
    }
    const double t = 0.5 * (lo + hi);
    return p > 0.5 ? t : -t;
}

}  // namespace mf::probability::detail
