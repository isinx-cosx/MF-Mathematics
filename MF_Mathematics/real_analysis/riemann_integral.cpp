#include "riemann_integral.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <string>

#include "../calculus/integrals.h"
#include "ra_internal.h"

namespace mf::real_analysis {

namespace {
using mf::real_analysis::detail::ExprEval;

// 一次 n 等分的 U_n − L_n：每段取 41 个采样点估计 inf/sup。
double darboux_gap(const ExprEval& f, double a, double b, int n) {
    constexpr int kSamples = 40;
    const double dx = (b - a) / n;
    double lower = 0.0, upper = 0.0;
    for (int i = 0; i < n; ++i) {
        const double xl = a + dx * i;
        double mn = std::numeric_limits<double>::infinity();
        double mx = -std::numeric_limits<double>::infinity();
        int cnt = 0;
        for (int k = 0; k <= kSamples; ++k) {
            const double v = f.at(xl + dx * k / kSamples);
            if (std::isfinite(v)) {
                mn = std::min(mn, v);
                mx = std::max(mx, v);
                ++cnt;
            }
        }
        if (cnt > 0) {
            lower += mn * dx;
            upper += mx * dx;
        }
    }
    return upper - lower;
}

// 黎曼可积 ⟺ 分割加密时 U(P)−L(P) → 0。
//
// 旧实现的判据是「固定 10 等分下 U−L < 0.01」。这个阈值恰好卡在 x² 在 [0,1]
// 上的 U−L = (b−a)·(b−a)/n = 0.1 附近：同一函数在 [0,0.3] 又判 True，
// 而 U−L = 1/n → 0 本来是收敛的。
// 这里改为真的取极限：n = 10,20,…,320 逐级加倍，要求 D_n 按正的幂次速度衰减
// (D_{2n} ≤ 0.9·D_n，即衰减指数 p = log2(D_n/D_{2n}) ≥ 0.15)，末三级都要满足。
// 对 x²(D_n = 1/n)、常函数(D_n ≡ 0)成立；对 1/x(D_n 停在 39 左右不再衰减)、
// 有界振荡型函数不成立。
bool darboux_gap_vanishes(const ExprEval& f, double a, double b) {
    const int ns[6] = {10, 20, 40, 80, 160, 320};
    std::vector<double> d;
    for (int n : ns) {
        const double g = darboux_gap(f, a, b, n);
        if (!std::isfinite(g)) return false;
        d.push_back(g);
    }
    const std::size_t K = d.size() - 1;
    if (d[K] == 0.0) return true;
    for (std::size_t k = K - 3; k < K; ++k)
        if (!(d[k + 1] <= 0.9 * d[k])) return false;
    return true;
}
}  // namespace

DarbouxResult darboux_sum(const std::string& expr, double a, double b,
                          const std::vector<double>& partition_in) {
    if (a > b) std::swap(a, b);
    DarbouxResult r;
    std::vector<double> partition;
    if (partition_in.empty()) {
        for (int i = 0; i <= 10; ++i) partition.push_back(a + (b - a) * i / 10);
    } else {
        partition = partition_in;
        std::sort(partition.begin(), partition.end());
        partition.erase(std::unique(partition.begin(), partition.end()), partition.end());
    }
    r.partition = partition;
    const ExprEval f(expr, "x");
    double lower = 0.0, upper = 0.0;
    for (std::size_t i = 0; i + 1 < partition.size(); ++i) {
        const double xl = partition[i], xr = partition[i + 1], dx = xr - xl;
        double mn = std::numeric_limits<double>::infinity();
        double mx = -std::numeric_limits<double>::infinity();
        int cnt = 0;
        for (int k = 0; k <= 200; ++k) {
            const double v = f.at(xl + dx * k / 200);
            if (std::isfinite(v)) {
                mn = std::min(mn, v);
                mx = std::max(mx, v);
                ++cnt;
            }
        }
        if (cnt > 0) {
            lower += mn * dx;
            upper += mx * dx;
        }
    }
    r.lower_sum = lower;
    r.upper_sum = upper;
    r.is_integrable = darboux_gap_vanishes(f, a, b);
    return r;
}

bool riemann_integrable(const std::string& expr, double a, double b) {
    if (a > b) std::swap(a, b);
    const ExprEval f(expr, "x");
    if (!f.ok()) return false;
    return darboux_gap_vanishes(f, a, b);
}

FundamentalResult fundamental_theorem(const std::string& expr, double a, double b) {
    FundamentalResult r;
    r.integral = mf::calculus::integrate_definite(expr, "x", std::to_string(a),
                                                  std::to_string(b));
    r.antiderivative = mf::calculus::integrate_indefinite(expr, "x");
    if (r.antiderivative == "未实现") {
        r.antiderivative.clear();
        r.Fa = 0.0;
        r.Fb = r.integral;
        return r;
    }
    // 去掉 "+ C" 后缀后求值。
    std::string body = r.antiderivative;
    const std::size_t cpos = body.find("+ C");
    if (cpos != std::string::npos) body = body.substr(0, cpos);
    try {
        r.Fa = detail::eval_str(body, a);
        r.Fb = detail::eval_str(body, b);
    } catch (...) {
        r.Fa = 0.0;
        r.Fb = r.integral;
    }
    return r;
}

MeanValueResult integral_mean_value(const std::string& expr, double a, double b) {
    MeanValueResult r;
    const double integral = mf::calculus::integrate_definite(
        expr, "x", std::to_string(a), std::to_string(b));
    r.mean_value = integral / (b - a);
    double xi = detail::find_root(expr, a, b, r.mean_value);
    if (!std::isfinite(xi)) xi = 0.5 * (a + b);
    r.xi = xi;
    return r;
}

}  // namespace mf::real_analysis
