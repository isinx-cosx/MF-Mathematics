#include "expectations.h"

#include <cmath>
#include <stdexcept>

#include "../calculus/integrals.h"
#include "prob_internal.h"

namespace mf::probability {

double expectation_sample(const std::vector<double>& data) {
    if (data.empty()) throw std::invalid_argument("样本为空");
    return detail::mean(data);
}

double expectation_pmf(const std::vector<double>& values,
                       const std::vector<double>& probs) {
    if (values.size() != probs.size())
        throw std::invalid_argument("取值与概率长度不匹配");
    double total = 0.0;
    for (std::size_t i = 0; i < values.size(); ++i)
        total += values[i] * probs[i];
    return total;
}

double expectation_continuous(const std::string& expr, double a, double b) {
    return mf::calculus::integrate_numeric(expr, "x", a, b);
}

double variance_sample(const std::vector<double>& data, long long ddof) {
    if (data.size() <= (std::size_t)ddof)
        throw std::invalid_argument("样本量不足，方差无定义");
    return detail::variance(data, ddof);
}

double variance_pmf(const std::vector<double>& values,
                    const std::vector<double>& probs) {
    if (values.size() != probs.size())
        throw std::invalid_argument("取值与概率长度不匹配");
    double e1 = 0.0, e2 = 0.0;
    for (std::size_t i = 0; i < values.size(); ++i) {
        e1 += values[i] * probs[i];
        e2 += values[i] * values[i] * probs[i];
    }
    return e2 - e1 * e1;
}

double variance_continuous(const std::string& expr, double a, double b) {
    const std::string e1 = "x*(" + expr + ")";
    const std::string e2 = "x**2*(" + expr + ")";
    const double m1 = mf::calculus::integrate_numeric(e1, "x", a, b);
    const double m2 = mf::calculus::integrate_numeric(e2, "x", a, b);
    return m2 - m1 * m1;
}

double covariance_sample(const std::vector<double>& x,
                         const std::vector<double>& y) {
    return detail::covariance(x, y);
}

double covariance_joint(const std::vector<double>& x_vals,
                        const std::vector<double>& y_vals,
                        const std::vector<double>& probs) {
    if (x_vals.size() != y_vals.size() || x_vals.size() != probs.size())
        throw std::invalid_argument("长度不匹配");
    double e_xy = 0.0, e_x = 0.0, e_y = 0.0;
    for (std::size_t i = 0; i < probs.size(); ++i) {
        e_xy += x_vals[i] * y_vals[i] * probs[i];
        e_x += x_vals[i] * probs[i];
        e_y += y_vals[i] * probs[i];
    }
    return e_xy - e_x * e_y;
}

double correlation_sample(const std::vector<double>& x,
                          const std::vector<double>& y) {
    const double c = detail::covariance(x, y);
    const double sx = std::sqrt(detail::variance(x, 1));
    const double sy = std::sqrt(detail::variance(y, 1));
    if (std::abs(sx * sy) < 1e-15)
        throw std::invalid_argument("标准差为零，相关系数无定义");
    return c / (sx * sy);
}

double correlation_joint(const std::vector<double>& x_vals,
                         const std::vector<double>& y_vals,
                         const std::vector<double>& probs) {
    const double cov = covariance_joint(x_vals, y_vals, probs);
    double ex = 0.0, ey = 0.0, ex2 = 0.0, ey2 = 0.0;
    for (std::size_t i = 0; i < probs.size(); ++i) {
        ex += x_vals[i] * probs[i];
        ey += y_vals[i] * probs[i];
        ex2 += x_vals[i] * x_vals[i] * probs[i];
        ey2 += y_vals[i] * y_vals[i] * probs[i];
    }
    const double sx = std::sqrt(ex2 - ex * ex);
    const double sy = std::sqrt(ey2 - ey * ey);
    if (std::abs(sx * sy) < 1e-15)
        throw std::invalid_argument("标准差为零，相关系数无定义");
    return cov / (sx * sy);
}

}  // namespace mf::probability
