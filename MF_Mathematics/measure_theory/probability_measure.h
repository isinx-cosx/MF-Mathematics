// probability_measure.h — 概率测度论:概率空间、随机变量、期望、条件期望、独立性。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::measure_theory {

// 概率空间 (Ω, P):均匀测度。
struct ProbabilitySpaceResult {
    std::vector<long long> omega;
    std::vector<double> probabilities;
    bool is_probability_space = false;
};
MF_API ProbabilitySpaceResult probability_space(
    const std::vector<long long>& omega);

// 随机变量 X:Ω → R,按规则("identity"/"square"/表达式)取值。
struct RandomVariableResult {
    std::vector<long long> omega;
    std::vector<double> values;
    std::string description;
};
MF_API RandomVariableResult random_variable(const std::string& rule,
                                            const std::vector<long long>& omega);

// 连续期望:正态 N(μ,σ²) 下 E[X(ω)] = ∫ x·φ dx。"x" → μ。
MF_API double expectation_normal(const std::string& expr, double mu,
                                 double sigma);

// 连续期望:均匀 U(a,b) 下 E[X] = ∫ x/(b-a) dx。"x" → (a+b)/2。
MF_API double expectation_uniform(const std::string& expr, double a, double b);

// 离散期望:E[X] = Σ v_i · p_i。
MF_API double expectation_discrete(const std::vector<double>& values,
                                   const std::vector<double>& probs);

// 条件期望 E[X|G]:在子 σ-代数每个原子上取加权平均(均匀测度)。
struct ConditionalExpectationResult {
    std::vector<long long> omega;
    std::vector<std::vector<long long>> atoms;
    std::vector<double> ce_per_atom;
};
MF_API ConditionalExpectationResult conditional_expectation(
    const std::string& rule, const std::vector<long long>& omega,
    const std::vector<std::vector<long long>>& atoms);

// 事件独立性:P(A∩B) == P(A)·P(B)。
MF_API bool independence_check(const std::vector<long long>& A,
                               const std::vector<long long>& B,
                               const std::vector<long long>& omega,
                               const std::vector<double>& probs);

}  // namespace mf::measure_theory
