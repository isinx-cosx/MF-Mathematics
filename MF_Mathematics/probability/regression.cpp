#include "regression.h"

#include <cmath>
#include <stdexcept>

#include "prob_internal.h"

namespace mf::probability {

RegressionResult linear_regression(const std::vector<double>& x,
                                   const std::vector<double>& y) {
    if (x.size() != y.size()) throw std::invalid_argument("x 与 y 长度必须相同");
    if (x.size() < 2) throw std::invalid_argument("至少需要 2 个数据点");
    RegressionResult r;
    r.n = (long long)x.size();
    const double xm = detail::mean(x);
    const double ym = detail::mean(y);
    double sxy = 0.0, sxx = 0.0;
    for (std::size_t i = 0; i < x.size(); ++i) {
        const double dx = x[i] - xm;
        sxy += dx * (y[i] - ym);
        sxx += dx * dx;
    }
    if (std::abs(sxx) < 1e-15) throw std::invalid_argument("x 方差为零,无法拟合回归线");
    r.slope = sxy / sxx;
    r.intercept = ym - r.slope * xm;
    double ss_res = 0.0, ss_tot = 0.0;
    for (std::size_t i = 0; i < x.size(); ++i) {
        const double pred = r.intercept + r.slope * x[i];
        const double dr = y[i] - pred;
        const double dt = y[i] - ym;
        ss_res += dr * dr;
        ss_tot += dt * dt;
    }
    r.r_squared = ss_tot > 1e-15 ? 1.0 - ss_res / ss_tot : 1.0;
    return r;
}

double predict_linear(double slope, double intercept, double x) {
    return intercept + slope * x;
}

std::vector<double> predict_linear_many(double slope, double intercept,
                                        const std::vector<double>& x) {
    std::vector<double> out;
    out.reserve(x.size());
    for (double xi : x) out.push_back(intercept + slope * xi);
    return out;
}

ResidualResult residuals_linear(double slope, double intercept,
                                const std::vector<double>& x,
                                const std::vector<double>& y) {
    if (x.size() != y.size()) throw std::invalid_argument("x 与 y 长度必须相同");
    ResidualResult r;
    r.n = (long long)x.size();
    double sse = 0.0;
    for (std::size_t i = 0; i < x.size(); ++i) {
        const double e = y[i] - (intercept + slope * x[i]);
        r.residuals.push_back(e);
        sse += e * e;
    }
    r.SSE = sse;
    r.MSE = x.size() > 2 ? sse / (double)(x.size() - 2) : sse;
    return r;
}

}  // namespace mf::probability
