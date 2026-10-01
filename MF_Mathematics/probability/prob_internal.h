// prob_internal.h — probability 包共享辅助(仅头文件)。
//
// 提供:基础统计量、正态/t/χ²/F 分布的 CDF 与分位数(替代 scipy.stats)、
// 秩计算(Mann-Whitney / Wilcoxon)。

#pragma once

#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace mf::probability::detail {

inline constexpr double kPi = 3.14159265358979323846;

// ── 基础统计量 ──────────────────────────────────────────────────────────────

inline double mean(const std::vector<double>& v) {
    return std::accumulate(v.begin(), v.end(), 0.0) / (double)v.size();
}

// 方差:ddof=1 无偏,ddof=0 有偏。
inline double variance(const std::vector<double>& v, long long ddof = 1) {
    const std::size_t n = v.size();
    if (n <= (std::size_t)ddof) return 0.0;
    const double m = mean(v);
    double s = 0.0;
    for (double x : v) {
        const double d = x - m;
        s += d * d;
    }
    return s / (double)(n - ddof);
}

// 样本协方差(ddof=1)。
//
// ⚠ 长度不一致时必须报错，不能返回 0：返回 0 会被读成"这两个序列不相关"，
//   是结论性的错答（同模块的 covariance_joint 与 linear_regression 对同类
//   输入都是抛错，只有这里静默给 0）。
inline double covariance(const std::vector<double>& x,
                         const std::vector<double>& y) {
    const std::size_t n = x.size();
    if (n != y.size())
        throw std::invalid_argument(
            "两个序列长度必须一致（实得 " + std::to_string(n) + " 与 " +
            std::to_string(y.size()) + "）");
    if (n < 2) return 0.0;  // 少于 2 个点无法估样本协方差
    const double mx = mean(x), my = mean(y);
    double s = 0.0;
    for (std::size_t i = 0; i < n; ++i) s += (x[i] - mx) * (y[i] - my);
    return s / (double)(n - 1);
}

inline double median(std::vector<double> v) {
    if (v.empty()) return 0.0;
    std::sort(v.begin(), v.end());
    const std::size_t n = v.size();
    return (n % 2 == 1) ? v[n / 2]
                        : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

// ── 正态分布 ────────────────────────────────────────────────────────────────

inline double normal_pdf(double x) {
    return std::exp(-0.5 * x * x) / std::sqrt(2.0 * kPi);
}

inline double normal_cdf(double x) { return 0.5 * (1.0 + std::erf(x / std::sqrt(2.0))); }

// Φ^{-1}(p),Acklam 有理逼近 + 牛顿修正,精度 ~1e-9。
inline double normal_inv(double p) {
    if (p <= 0.0) return -std::numeric_limits<double>::infinity();
    if (p >= 1.0) return std::numeric_limits<double>::infinity();
    static const double a[6] = {-3.969683028665376e+01, 2.209460984245205e+02,
                                -2.759285104469687e+02, 1.383577518672690e+02,
                                -3.066479806614716e+01, 2.506628277459239e+00};
    static const double b[5] = {-5.447609879822406e+01, 1.615858368580409e+02,
                                -1.556989798598866e+02, 6.680131188771972e+01,
                                -1.328068155288572e+01};
    static const double c[6] = {-7.784894002430293e-03, -3.223964580411365e-01,
                                -2.400758277161838e+00, -2.549732539343734e+00,
                                4.374664141464968e+00, 2.938163982698783e+00};
    static const double d[4] = {7.784695709041462e-03, 3.224671290700398e-01,
                                2.445134137142996e+00, 3.754408661907416e+00};
    const double plow = 0.02425, phigh = 1.0 - 0.02425;
    double q, r, val;
    if (p < plow) {
        q = std::sqrt(-2.0 * std::log(p));
        val = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q +
               c[5]) /
              ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0);
    } else if (p <= phigh) {
        q = p - 0.5;
        r = q * q;
        val = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r +
               a[5]) *
              q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r +
                   1.0);
    } else {
        q = std::sqrt(-2.0 * std::log(1.0 - p));
        val = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q +
                c[5]) /
              ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0);
    }
    // 牛顿修正。
    val -= (normal_cdf(val) - p) / normal_pdf(val);
    val -= (normal_cdf(val) - p) / normal_pdf(val);
    return val;
}

// ── 不完全 beta / 不完全 gamma(正规化)──────────────────────────────────────

// 连分数 I_x(a,b)(Lentz)。
inline double betacf(double a, double b, double x) {
    const double tiny = 1e-300;
    const int maxit = 200;
    const double eps = 3e-14;
    const double qab = a + b, qap = a + 1.0, qam = a - 1.0;
    double c = 1.0;
    double d = 1.0 - qab * x / qap;
    if (std::abs(d) < tiny) d = tiny;
    d = 1.0 / d;
    double h = d;
    for (int m = 1; m <= maxit; ++m) {
        const double m2 = 2.0 * m;
        double aa = m * (b - m) * x / ((qam + m2) * (a + m2));
        d = 1.0 + aa * d;
        if (std::abs(d) < tiny) d = tiny;
        c = 1.0 + aa / c;
        if (std::abs(c) < tiny) c = tiny;
        d = 1.0 / d;
        h *= d * c;
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
        d = 1.0 + aa * d;
        if (std::abs(d) < tiny) d = tiny;
        c = 1.0 + aa / c;
        if (std::abs(c) < tiny) c = tiny;
        d = 1.0 / d;
        const double del = d * c;
        h *= del;
        if (std::abs(del - 1.0) < eps) break;
    }
    return h;
}

// 正规化不完全 beta 函数 I_x(a,b)。
inline double betai(double a, double b, double x) {
    if (x <= 0.0) return 0.0;
    if (x >= 1.0) return 1.0;
    const double bt =
        std::exp(std::lgamma(a + b) - std::lgamma(a) - std::lgamma(b) +
                 a * std::log(x) + b * std::log(1.0 - x));
    if (x < (a + 1.0) / (a + b + 2.0))
        return bt * betacf(a, b, x) / a;
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b;
}

// 正规化下不完全 gamma P(a,x)(级数,小 x)。
inline double gamma_pseries(double a, double x) {
    double ap = a;
    double sum = 1.0 / a;
    double del = sum;
    for (int n = 1; n <= 200; ++n) {
        ++ap;
        del *= x / ap;
        sum += del;
        if (std::abs(del) < std::abs(sum) * 3e-14) break;
    }
    return sum * std::exp(-x + a * std::log(x) - std::lgamma(a));
}

// 正规化上不完全 gamma Q(a,x)(连分数,大 x)。
inline double gamma_qcf(double a, double x) {
    const double tiny = 1e-300;
    const double eps = 3e-14;
    double b = x + 1.0 - a;
    double c = 1.0 / tiny;
    double d = 1.0 / b;
    double h = d;
    for (int i = 1; i <= 200; ++i) {
        const double an = -i * (i - a);
        b += 2.0;
        d = an * d + b;
        if (std::abs(d) < tiny) d = tiny;
        c = b + an / c;
        if (std::abs(c) < tiny) c = tiny;
        d = 1.0 / d;
        const double del = d * c;
        h *= del;
        if (std::abs(del - 1.0) < eps) break;
    }
    return std::exp(-x + a * std::log(x) - std::lgamma(a)) * h;
}

// 正规化下不完全 gamma P(a,x)。
inline double gamma_p(double a, double x) {
    if (x < a + 1.0) return gamma_pseries(a, x);
    return 1.0 - gamma_qcf(a, x);
}

// ── t / χ² / F 分布 ─────────────────────────────────────────────────────────

// t 分布密度。
inline double t_pdf(double t, double nu) {
    const double c =
        std::exp(std::lgamma((nu + 1.0) / 2.0) - std::lgamma(nu / 2.0)) /
        std::sqrt(nu * kPi);
    return c * std::pow(1.0 + t * t / nu, -(nu + 1.0) / 2.0);
}

inline double t_cdf(double t, double nu) {
    const double x = nu / (nu + t * t);
    if (t >= 0.0) return 1.0 - 0.5 * betai(nu / 2.0, 0.5, x);
    return 0.5 * betai(nu / 2.0, 0.5, x);
}

// t 分布分位数:牛顿迭代(初值取正态分位数)。
inline double t_inv(double p, double nu) {
    if (p <= 0.0) return -std::numeric_limits<double>::infinity();
    if (p >= 1.0) return std::numeric_limits<double>::infinity();
    double t = normal_inv(p);
    for (int i = 0; i < 80; ++i) {
        const double f = t_cdf(t, nu) - p;
        const double df = t_pdf(t, nu);
        if (std::abs(df) < 1e-300) break;
        const double step = f / df;
        t -= step;
        if (std::abs(step) < 1e-12 * (1.0 + std::abs(t))) break;
        if (std::abs(t) > 1e15) break;  // 发散保护(极端分位数可达 ~1e8 量级)
    }
    return t;
}

// χ² 分布 CDF:P(k/2, x/2)。
inline double chi2_cdf(double x, double k) {
    if (x <= 0.0) return 0.0;
    return gamma_p(k / 2.0, x / 2.0);
}

// F 分布 CDF:I_{d1·F/(d1·F+d2)}(d1/2, d2/2)。
inline double f_cdf(double F, double d1, double d2) {
    if (F <= 0.0) return 0.0;
    const double x = d1 * F / (d1 * F + d2);
    return betai(d1 / 2.0, d2 / 2.0, x);
}

// 双侧 p 值(标准正态)。
inline double two_sided_p(double z) { return 2.0 * (1.0 - normal_cdf(std::abs(z))); }

// ── 秩工具(非参数检验)──────────────────────────────────────────────────────

// 对数据(保留分组)计算平均秩(并列取平均)。
inline std::vector<double> rank_average(const std::vector<double>& v) {
    const std::size_t n = v.size();
    std::vector<std::pair<double, std::size_t>> ord;
    ord.reserve(n);
    for (std::size_t i = 0; i < n; ++i) ord.emplace_back(v[i], i);
    std::sort(ord.begin(), ord.end());
    std::vector<double> ranks(n);
    std::size_t i = 0;
    while (i < n) {
        std::size_t j = i;
        while (j + 1 < n && ord[j + 1].first == ord[i].first) ++j;
        const double avg = (double)(i + j + 2) / 2.0;
        for (std::size_t k = i; k <= j; ++k) ranks[ord[k].second] = avg;
        i = j + 1;
    }
    return ranks;
}

// Mann-Whitney U 统计量:对两组合并排名,取第一组秩和。
inline double mann_whitney_u(const std::vector<double>& g1,
                             const std::vector<double>& g2) {
    std::vector<double> all = g1;
    all.insert(all.end(), g2.begin(), g2.end());
    const std::vector<double> ranks = rank_average(all);
    const double n1 = (double)g1.size();
    double r1 = 0.0;
    for (std::size_t i = 0; i < g1.size(); ++i) r1 += ranks[i];
    return r1 - n1 * (n1 + 1.0) / 2.0;
}

// Wilcoxon 符号秩:返回 (W+, W-)(并列取平均秩,剔除零差)。
inline std::pair<double, double> wilcoxon_ranks(
    const std::vector<double>& diffs) {
    std::vector<double> nonzero;
    for (double d : diffs)
        if (std::abs(d) > 1e-15) nonzero.push_back(std::abs(d));
    const std::vector<double> ranks = rank_average(nonzero);
    double w_pos = 0.0, w_neg = 0.0;
    std::size_t idx = 0;
    for (double d : diffs) {
        if (std::abs(d) > 1e-15) {
            if (d > 0) w_pos += ranks[idx];
            else w_neg += ranks[idx];
            ++idx;
        }
    }
    return {w_pos, w_neg};
}

}  // namespace mf::probability::detail
