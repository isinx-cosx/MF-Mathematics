#include "random_variable.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>

#include "../calculus/integrals.h"

#include <symengine/basic.h>
#include <symengine/eval_double.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

namespace mf::probability {

double distribution_function(const std::vector<double>& data, double x) {
    if (data.empty()) throw std::invalid_argument("样本数据为空");
    long long count = 0;
    for (double d : data)
        if (d <= x) ++count;
    return (double)count / (double)data.size();
}

EmpiricalCdfResult distribution_function_full(const std::vector<double>& data) {
    if (data.empty()) throw std::invalid_argument("样本数据为空");
    EmpiricalCdfResult r;
    r.x_values = data;
    std::sort(r.x_values.begin(), r.x_values.end());
    const double n = (double)r.x_values.size();
    for (std::size_t i = 0; i < r.x_values.size(); ++i)
        r.f_values.push_back((double)(i + 1) / n);
    return r;
}

PmfResult pmf_normalize(const std::vector<double>& probs) {
    PmfResult r;
    double total = 0.0;
    for (double p : probs) {
        if (p < 0) throw std::invalid_argument("概率必须非负");
        total += p;
    }
    r.probabilities = probs;
    if (std::abs(total - 1.0) > 0.01) {
        for (double& p : r.probabilities) p /= total;
        r.was_normalized = true;
    }
    return r;
}

std::string pdf_expression(const std::string& expr, const std::string& var) {
    (void)var;
    SymEngine::parse(expr);  // 验证可解析。
    return expr;
}

double expectation_discrete_g(const std::vector<double>& values,
                              const std::vector<double>& probs,
                              const std::string& g_expr) {
    if (values.size() != probs.size())
        throw std::invalid_argument("取值与概率长度不匹配");
    if (g_expr == "x" || g_expr.empty()) {
        double total = 0.0;
        for (std::size_t i = 0; i < values.size(); ++i)
            total += values[i] * probs[i];
        return total;
    }
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(g_expr);
    double total = 0.0;
    for (std::size_t i = 0; i < values.size(); ++i) {
        const auto sub = e->subs({{x, SymEngine::real_double(values[i])}});
        total += SymEngine::eval_double(*sub) * probs[i];
    }
    return total;
}

}  // namespace mf::probability
