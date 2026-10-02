// convergence_theorems.h — 积分极限定理:单调收敛、法图引理、控制收敛。
#pragma once

#include <string>
#include <vector>


namespace mf::measure_theory {

// 单调收敛定理验证:lim ∫ f_n = ∫ lim f_n(f_n ↑ f)。
struct MonotoneResult {
    std::vector<double> integral_values;
    double limit_of_integrals = 0.0;
    double integral_of_limit = 0.0;
    double difference = 0.0;
    bool converged = false;
};
MonotoneResult monotone_convergence(const std::string& fn_expr,
                                           const std::string& f_expr,
                                           const std::vector<long long>& n_values,
                                           double a, double b);

// 法图引理验证:∫(liminf f_n) ≤ liminf ∫ f_n(非负函数列)。
struct FatouResult {
    std::vector<double> integral_values;
    double integral_of_liminf = 0.0;
    double liminf_of_integrals = 0.0;
    bool inequality_holds = false;
};
FatouResult fatou_lemma(const std::string& fn_expr,
                               const std::vector<long long>& n_values,
                               double a, double b);

// 控制收敛定理验证:|f_n| ≤ g 可积时 lim ∫ f_n = ∫ lim f_n。
struct DominatedResult {
    bool dominated = false;
    std::vector<double> integral_values;
    double limit_of_integrals = 0.0;
    double integral_of_limit = 0.0;
    double g_integral = 0.0;
    double difference = 0.0;
};
DominatedResult dominated_convergence(const std::string& fn_expr,
                                             const std::string& f_expr,
                                             const std::string& g_expr,
                                             const std::vector<long long>& n_values,
                                             double a, double b);

}  // namespace mf::measure_theory
