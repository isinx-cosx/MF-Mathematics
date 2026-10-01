#include "probability_measure.h"

#include <cmath>
#include <stdexcept>

#include "mt_internal.h"

namespace mf::measure_theory {

namespace {
using mf::measure_theory::detail::kPi;
using mf::measure_theory::detail::eval_double_str;
using mf::measure_theory::detail::simpson;
}  // namespace

ProbabilitySpaceResult probability_space(const std::vector<long long>& omega) {
    ProbabilitySpaceResult r;
    r.omega = omega;
    const double p = omega.empty() ? 0.0 : 1.0 / (double)omega.size();
    for (std::size_t i = 0; i < omega.size(); ++i) r.probabilities.push_back(p);
    r.is_probability_space = std::abs(p * (double)omega.size() - 1.0) < 1e-10;
    return r;
}

RandomVariableResult random_variable(const std::string& rule,
                                     const std::vector<long long>& omega) {
    RandomVariableResult r;
    r.omega = omega;
    if (rule == "identity") {
        r.description = "X(ω) = ω（恒等映射）";
    } else if (rule == "square") {
        r.description = "X(ω) = ω²";
    } else {
        r.description = "X(ω) = " + rule;
    }
    for (long long w : omega) {
        if (rule == "identity")
            r.values.push_back((double)w);
        else if (rule == "square")
            r.values.push_back((double)(w * w));
        else
            r.values.push_back(eval_double_str(rule, (double)w));
    }
    return r;
}

double expectation_normal(const std::string& expr, double mu, double sigma) {
    if (sigma <= 0) throw std::invalid_argument("σ 必须为正");
    if (expr == "x" || expr == "identity" || expr.empty()) return mu;
    const auto pdf = [&](double t) {
        const double z = (t - mu) / sigma;
        return std::exp(-0.5 * z * z) / (sigma * std::sqrt(2.0 * kPi));
    };
    const auto integrand = [&](double t) { return eval_double_str(expr, t) * pdf(t); };
    return simpson(integrand, mu - 10.0 * sigma, mu + 10.0 * sigma, 4000);
}

double expectation_uniform(const std::string& expr, double a, double b) {
    if (b <= a) throw std::invalid_argument("需要 a < b");
    if (expr == "x" || expr == "identity" || expr.empty()) return 0.5 * (a + b);
    const auto integrand = [&](double t) {
        return eval_double_str(expr, t) / (b - a);
    };
    return simpson(integrand, a, b, 4000);
}

double expectation_discrete(const std::vector<double>& values,
                            const std::vector<double>& probs) {
    if (values.size() != probs.size())
        throw std::invalid_argument("取值与概率数量不匹配");
    double total = 0.0;
    for (std::size_t i = 0; i < values.size(); ++i) total += values[i] * probs[i];
    return total;
}

ConditionalExpectationResult conditional_expectation(
    const std::string& rule, const std::vector<long long>& omega,
    const std::vector<std::vector<long long>>& atoms) {
    ConditionalExpectationResult r;
    r.omega = omega;
    r.atoms = atoms;
    const double p = omega.empty() ? 0.0 : 1.0 / (double)omega.size();

    // X(ω) 取值表。
    auto xvals = [&](long long w) {
        if (rule == "identity") return (double)w;
        if (rule == "square") return (double)(w * w);
        return eval_double_str(rule, (double)w);
    };

    for (const auto& atom : atoms) {
        double weighted = 0.0;
        double total_prob = 0.0;
        for (long long w : atom) {
            weighted += xvals(w) * p;
            total_prob += p;
        }
        r.ce_per_atom.push_back(total_prob > 0 ? weighted / total_prob
                                               : std::numeric_limits<double>::quiet_NaN());
    }
    return r;
}

bool independence_check(const std::vector<long long>& A,
                        const std::vector<long long>& B,
                        const std::vector<long long>& omega,
                        const std::vector<double>& probs) {
    if (omega.size() != probs.size())
        throw std::invalid_argument("样本空间与概率数量不匹配");
    const auto has = [&](const std::vector<long long>& S, long long w) {
        return std::find(S.begin(), S.end(), w) != S.end();
    };
    double p_A = 0.0, p_B = 0.0, p_AB = 0.0;
    for (std::size_t i = 0; i < omega.size(); ++i) {
        const bool inA = has(A, omega[i]);
        const bool inB = has(B, omega[i]);
        if (inA) p_A += probs[i];
        if (inB) p_B += probs[i];
        if (inA && inB) p_AB += probs[i];
    }
    return std::abs(p_AB - p_A * p_B) < 1e-10;
}

}  // namespace mf::measure_theory
