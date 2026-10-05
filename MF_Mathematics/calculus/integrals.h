// integrals.h — 积分:自研符号积分 + 数值辛普森 + 反常积分。
//
// 符号原函数:多项式规则 ∫xⁿ、积分表(sin/cos/eˣ/1/x/ln)、线性性、分部积分(简单)。
// 无法积分时 integrate_indefinite 返回 "未实现"(不编造结果);定积分符号失败回退数值。

#pragma once

#include <complex>
#include <string>


namespace mf::calculus {

// 不定积分:返回 "原函数 + C"。无法符号积分时返回 "未实现"。
std::string integrate_indefinite(const std::string& expr,
                                        const std::string& var);

// 定积分:优先符号原函数 F(b)-F(a)(精确),失败回退数值辛普森。
// a/b 可为数字或 "pi"/"π"。无穷边界抛异常,请用 improper_integral。
double integrate_definite(const std::string& expr, const std::string& var,
                                 const std::string& a, const std::string& b);

// 数值积分(辛普森,1000 子区间)。a/b 须为数字。
double integrate_numeric(const std::string& expr, const std::string& var,
                                double a, double b);

// 反常积分(数值):无穷端按数量级分段(每 10 倍一段)求和并判断收敛。
// 发散抛 std::invalid_argument。
double improper_integral(const std::string& expr, const std::string& var,
                                const std::string& a, const std::string& b);

// 不定二重积分 ∫∫ f(x,y) dy dx:内层对 y、外层对 x 逐次求原函数,
// 返回 "H(x,y) + A(x) + B(y)"。无法符号积分时返回 "未实现"。
// ⚠ 与单变量不同,这里的积分常数是**任意函数**(见 .cpp 里的说明),不要加 "+ C"。
std::string integrate_double_indefinite(const std::string& expr,
                                               const std::string& x,
                                               const std::string& y);

// 不定三重积分 ∫∫∫ f(x,y,z) dz dy dx,返回 "K + A(x,y) + B(x,z) + C(y,z)"。
// 无法符号积分时返回 "未实现"。
std::string integrate_triple_indefinite(const std::string& expr,
                                               const std::string& x,
                                               const std::string& y,
                                               const std::string& z);

// 二重积分 ∫∫ f(x,y) dy dx,区域 [xa,xb]×[ya,yb]。
// 边界可为数字或含外层变量的表达式(如 "2*x")。符号积分器失败回退数值。
double integrate_double(const std::string& expr, const std::string& x,
                               const std::string& y, const std::string& xa,
                               const std::string& xb, const std::string& ya,
                               const std::string& yb);

// 三重积分 ∫∫∫ f(x,y,z) dz dy dx,区域 [xa,xb]×[ya,yb]×[za,zb]。
double integrate_triple(const std::string& expr, const std::string& x,
                               const std::string& y, const std::string& z,
                               const std::string& xa, const std::string& xb,
                               const std::string& ya, const std::string& yb,
                               const std::string& za, const std::string& zb);

// 复定积分 ∫_a^b f(x) dx(符号原函数),返回复数。适用于 e^{iωx} 等(如 Fourier)。
std::complex<double> integrate_complex(const std::string& expr,
                                              const std::string& var,
                                              const std::string& a,
                                              const std::string& b);

}  // namespace mf::calculus
