// series.h — 数项级数:求和、比值/根值判别、幂级数、各种审敛法。
#pragma once

#include <string>
#include <vector>


namespace mf::calculus {

// 级数和(数值)。b < 0 表示无穷上限(部分和 + 尾项估计)。
double series_sum(const std::string& expr, const std::string& var,
                         long long a, long long b);

// 比值/根值判别:返回结论("绝对收敛"/"发散"/"判别法失效"/"待定")。
std::string series_convergence(const std::string& expr,
                                      const std::string& var);

// 幂级数展开(泰勒多项式)。
std::string power_series(const std::string& expr, const std::string& var,
                                double point, long long n);

// 收敛半径(比值法):∞ 返回 +inf。
double power_series_radius(const std::string& expr,
                                  const std::string& var);

// Leibniz 交错级数判别:"convergent"/"divergent"/"inconclusive"。
std::string leibniz_test(const std::string& expr, const std::string& var);

// 积分判别法:"convergent"/"divergent"/"inconclusive"。
std::string integral_test(const std::string& expr, const std::string& var);

// p-级数判别:估计 p = lim ln|a_n|/ln(1/n)。
std::string p_series_test(const std::string& expr, const std::string& var);

// 极限比较判别(与 p-级数比较)。
std::string limit_comparison_test(const std::string& expr,
                                         const std::string& var);
std::string direct_comparison_test(const std::string& expr,
                                          const std::string& var,
                                          const std::string& compare_expr = "");

// 分类审敛:先判交错 → p-级数 → 比值。
std::string classify_and_test(const std::string& expr,
                                     const std::string& var);

// ── 数列乘积与绝对收敛（对应视图里的"数列求积 / 无穷乘积 / 级数绝对收敛"）──
// 有限乘积 ∏_{k=a}^{b} a_k（b < a 时返回 1，符合空积约定）。
double product_sequence(const std::string& expr, const std::string& var,
                               long long a, long long b);

struct InfiniteProductResult {
    double value = 0.0;      // 部分积（发散时可能是 inf 或 0）
    bool converges = false;  // 通项是否趋于 1 且部分积趋于有限非零值
    std::string note;        // 中文说明（判定依据）
};
// 无穷乘积 ∏_{k=1}^{∞} a_k：收敛 ⟺ Σ ln a_k 收敛。实际用 part_n 的稳定性和
// |a_k - 1| 的衰减来判断，并把依据写进 note。
InfiniteProductResult infinite_product(const std::string& expr,
                                             const std::string& var);

// 绝对收敛判定：对 |a_n| 用比值法（与 series_convergence 同一套数值手段）。
std::string absolute_convergence(const std::string& expr,
                                        const std::string& var);

}  // namespace mf::calculus
