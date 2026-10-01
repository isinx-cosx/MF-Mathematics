#include "sequence_limit.h"

#include <algorithm>
#include <cmath>

#include "ra_internal.h"

namespace mf::real_analysis {

double sequence_limit(const std::string& expr, const std::string& var) {
    return detail::sequence_limit_value(expr, var);
}

SequenceConvergenceResult sequence_convergence(const std::string& expr,
                                               const std::string& var) {
    SequenceConvergenceResult r;
    const double lim = detail::sequence_limit_value(expr, var);
    if (std::isfinite(lim)) {
        r.convergent = true;
        r.limit_value = lim;
        r.description = "收敛";
    } else if (lim == std::numeric_limits<double>::infinity()) {
        r.description = "发散（趋于 +∞）";
    } else if (lim == -std::numeric_limits<double>::infinity()) {
        r.description = "发散（趋于 -∞）";
    } else {
        r.description = "发散（振荡或无界）";
    }
    return r;
}

bool cauchy_criterion_values(const std::vector<double>& values, double epsilon) {
    if (values.size() < 2) return false;
    const std::size_t tail = std::max<std::size_t>(1, values.size() / 2);
    double max_diff = 0.0;
    for (std::size_t i = tail; i < values.size(); ++i) {
        for (std::size_t j = i + 1; j < values.size(); ++j) {
            const double d = std::abs(values[i] - values[j]);
            if (d > max_diff) max_diff = d;
        }
    }
    return max_diff < epsilon;
}

bool cauchy_criterion(const std::string& expr, double epsilon, long long max_n,
                      const std::string& var) {
    if (max_n <= 1) return false;
    std::vector<double> values;
    for (long long i = 1; i <= max_n; ++i) {
        const double v = detail::eval_var(expr, var, (double)i);
        if (std::isfinite(v)) values.push_back(v);
    }
    return cauchy_criterion_values(values, epsilon);
}

}  // namespace mf::real_analysis
