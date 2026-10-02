// probability_space.h — 条件概率、独立性、全概率公式、贝叶斯公式。
#pragma once

#include <vector>


namespace mf::probability {

// P(A|B) = P(A∩B) / P(B)。P(B) ≈ 0 时抛异常。
double conditional_probability(double p_ab, double p_b);

// 独立判定:|P(A∩B) - P(A)·P(B)| < 1e-12。
bool is_independent(double p_a, double p_b, double p_ab);

// 全概率公式 P(A) = Σ P(A|Bi)·P(Bi)。
double total_probability(const std::vector<double>& prob_events,
                                const std::vector<double>& cond_probs);

// 贝叶斯公式:后验 P(Bi|A) = P(A|Bi)·P(Bi) / Σ P(A|Bj)·P(Bj)。
std::vector<double> bayes_posterior(
    const std::vector<double>& prob_events,
    const std::vector<double>& cond_probs);

}  // namespace mf::probability
