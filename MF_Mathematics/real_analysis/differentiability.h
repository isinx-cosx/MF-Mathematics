// differentiability.h — 可微性:导数定义、可导性判断、泰勒多项式、拉格朗日余项、
// 罗尔定理、拉格朗日中值定理。
//
// 符号求导/求解基于 SymEngine;左右导数用数值差商估计。

#pragma once

#include <string>

#include "../mf_export.h"

namespace mf::real_analysis {

// 导数定义:f'(x₀) = lim_{h→0}[f(x₀+h)-f(x₀)]/h,结果与符号求导一致。
MF_API double derivative_definition(const std::string& expr,
                                    const std::string& var, double point);

// 判断函数在某点是否可导(左右导数差商比较)。
MF_API bool is_differentiable(const std::string& expr, const std::string& var,
                              double point);

// 泰勒多项式 T_n(x) = Σ_{k=0}^{n} f^(k)(a)/k! · (x-a)^k,返回化简后的字符串。
MF_API std::string taylor_polynomial(const std::string& expr,
                                     const std::string& var, double point,
                                     long long n);

// 拉格朗日余项 R_n(x) = f^(n+1)(ξ)/(n+1)! · (x-a)^(n+1)。
struct TaylorRemainderResult {
    std::string formula;         // 未代入 ξ 的余项公式
    bool has_xi = false;         // 是否提供了 ξ
    double remainder_factor = 0.0;  // f^(n+1)(ξ)/(n+1)! 的数值
};
MF_API TaylorRemainderResult taylor_remainder(const std::string& expr,
                                              const std::string& var,
                                              double point, long long n,
                                              bool has_xi, double xi);

// 罗尔定理:满足条件时返回 ξ ∈ (a,b) 使 f'(ξ)=0。
struct RolleResult {
    bool satisfies = false;  // f(a) = f(b) 是否成立
    double xi = 0.0;
};
MF_API RolleResult rolle_theorem(const std::string& expr,
                                 const std::string& var, double a, double b);

// 拉格朗日中值定理:返回 ξ 和割线斜率。
struct LagrangeResult {
    double xi = 0.0;
    double secant_slope = 0.0;
};
MF_API LagrangeResult lagrange_theorem(const std::string& expr,
                                       const std::string& var, double a,
                                       double b);

}  // namespace mf::real_analysis
