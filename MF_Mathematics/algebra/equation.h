// equation.h — 方程:一元一次、二元一次方程组、一元二次、分式方程、无理方程。
//
// 符号求解基于 SymEngine。分式方程用 as_numer_denom 通分;无理方程在
// SymEngine solve 失败时回退到数值求根。

#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::algebra {

// 一元一次方程的解(单解 → 字符串;无解 → "无解")。
MF_API std::string solve_linear(const std::string& expr, const std::string& var);

// 二元一次方程组。solvable=false 表示无解或无穷多解。
struct LinearSystemResult {
    bool solvable = false;
    std::string x;  // var1 的解
    std::string y;  // var2 的解
};
MF_API LinearSystemResult solve_linear_system(const std::string& eq1,
                                              const std::string& eq2,
                                              const std::string& var1,
                                              const std::string& var2);

// 一元二次方程的解(字符串列表,可为空)。
MF_API std::vector<std::string> solve_quadratic(const std::string& expr,
                                                const std::string& var);

// 判别式 Δ = b² - 4ac 及根的性质。
struct DiscriminantResult {
    double delta = 0.0;
    std::string nature;  // 有两个不等实根 / 有两个相等实根(重根) / 有一对共轭虚根
};
MF_API DiscriminantResult discriminant(const std::string& expr,
                                       const std::string& var);

// 韦达定理:x₁+x₂=-b/a, x₁·x₂=c/a。
struct VietaResult {
    double sum_of_roots = 0.0;
    double product_of_roots = 0.0;
    std::vector<std::string> roots;
};
MF_API VietaResult vieta_theorem(const std::string& expr, const std::string& var);

// 分式方程:通分求解并检验增根。
struct FractionalResult {
    std::vector<std::string> valid;
    std::vector<std::string> extraneous;
};
MF_API FractionalResult solve_fractional(const std::string& expr,
                                         const std::string& var);

// 无理方程:求解并验根(符号失败时数值求根)。
MF_API FractionalResult solve_irrational(const std::string& expr,
                                         const std::string& var);

}  // namespace mf::algebra
