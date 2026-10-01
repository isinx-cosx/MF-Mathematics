#include "probability_space.h"

#include <cmath>
#include <stdexcept>

namespace mf::probability {

double conditional_probability(double p_ab, double p_b) {
    if (std::abs(p_b) < 1e-15)
        throw std::invalid_argument("P(B) = 0，条件概率无定义");
    return p_ab / p_b;
}

bool is_independent(double p_a, double p_b, double p_ab) {
    return std::abs(p_ab - p_a * p_b) < 1e-12;
}

double total_probability(const std::vector<double>& prob_events,
                         const std::vector<double>& cond_probs) {
    if (prob_events.size() != cond_probs.size())
        throw std::invalid_argument("事件数与条件概率数不匹配");
    double total = 0.0;
    for (std::size_t i = 0; i < prob_events.size(); ++i)
        total += cond_probs[i] * prob_events[i];
    return total;
}

std::vector<double> bayes_posterior(const std::vector<double>& prob_events,
                                    const std::vector<double>& cond_probs) {
    if (prob_events.size() != cond_probs.size())
        throw std::invalid_argument("事件数与条件概率数不匹配");
    double denom = 0.0;
    for (std::size_t i = 0; i < prob_events.size(); ++i)
        denom += cond_probs[i] * prob_events[i];
    if (std::abs(denom) < 1e-15)
        throw std::invalid_argument("全概率为 0，贝叶斯公式无定义");
    std::vector<double> posterior(prob_events.size());
    for (std::size_t i = 0; i < prob_events.size(); ++i)
        posterior[i] = cond_probs[i] * prob_events[i] / denom;
    return posterior;
}

}  // namespace mf::probability
