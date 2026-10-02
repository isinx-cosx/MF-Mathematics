// product_measure.h — 乘积测度与 Fubini 定理。
#pragma once

#include <string>


namespace mf::measure_theory {

// 乘积测度 (μ×ν)([a,b]×[c,d]) = μ_factor·(b-a)·ν_factor·(d-c)。
// "lebesgue" 测度因子为 1;数值因子直接相乘。
double product_measure(double mu_factor, double nu_factor, double ax,
                              double bx, double ay, double by);

// Fubini 定理验证:两种积分次序 ∫∫f dy dx 与 ∫∫f dx dy 应一致。
struct FubiniResult {
    double xy_order = 0.0;  // 先 x 后 y
    double yx_order = 0.0;  // 先 y 后 x
    double difference = 0.0;
    bool fubini_holds = false;
    // 观测事实(不含推断):两个迭代积分是否都求出了有限值。
    // 被积函数在区域上无界时积分层会拒绝求值(见 calculus/integrals.cpp 的有界性检查),
    // 此时本字段为 false,而 fubini_holds 按定性结论取 false:
    //   f 不绝对可积 ⇒ Fubini 定理「f 绝对可积」的前提不满足 ⇒ 定理不适用、
    //   两个迭代积分不必相等。这正是 (x-y)/(x+y)^3 这类教科书反例的情形。
    // 不直接叫 absolutelyIntegrable:单侧"求不出值"只能说明积分层无法求值,
    // 不足以对任意 f 断言"不绝对可积"(无界但可积的函数同样会走到这里),
    // 故把推断留给 note 说明,机器可读的字段只报告观测到的事实。
    bool iterated_integrals_evaluated = true;
    // 定性说明:观测到什么、由此得出什么结论(含积分层给出的原始理由,可直接展示给用户)。
    std::string note;
};
FubiniResult fubini_theorem(const std::string& expr, double xa, double xb,
                                   double ya, double yb);

}  // namespace mf::measure_theory
