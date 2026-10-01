// distributions.cpp — 分布内核。

#include "distributions.h"

#include <cmath>
#include <complex>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/parser.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include "ha_internal.h"

namespace mf::harmonic_analysis {

using detail::eval_double_expr;

double delta_distribution(const std::string& phi, double x0) {
    const auto x = SymEngine::symbol("x");
    return eval_double_expr(SymEngine::parse(phi), x, x0);
}

std::string ft_delta() { return "1"; }

std::string ft_constant() { return "2*pi*delta(xi)"; }

TemperedResult tempered_distribution(const std::string& func, double x_hi) {
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(func);
    // 采样点 1, 10^{1/49}... 到 x_hi(对数网格)。
    std::vector<double> log_x, log_y;
    const double hi = std::max(x_hi, 10.0);
    for (int i = 0; i < 50; ++i) {
        const double t = std::pow(10.0, std::log10(hi) * i / 49.0);
        const double y = std::abs(eval_double_expr(e, x, t));
        if (!std::isfinite(y)) return {false, std::numeric_limits<double>::infinity()};
        if (y > 0) {
            log_x.push_back(std::log(t));
            log_y.push_back(std::log(y));
        }
    }
    TemperedResult r;
    if (log_x.size() < 3) {
        r.is_tempered = true;
        r.growth_order = 0.0;
        return r;
    }
    // 最小二乘线性拟合 slope。
    double sx = 0, sy = 0, sxy = 0, sxx = 0;
    const int m = static_cast<int>(log_x.size());
    for (int i = 0; i < m; ++i) {
        sx += log_x[i];
        sy += log_y[i];
        sxy += log_x[i] * log_y[i];
        sxx += log_x[i] * log_x[i];
    }
    const double denom = m * sxx - sx * sx;
    const double slope = std::abs(denom) > 1e-12 ? (m * sxy - sx * sy) / denom : 0.0;
    r.growth_order = slope;
    r.is_tempered = std::isfinite(slope);
    return r;
}

}  // namespace mf::harmonic_analysis
