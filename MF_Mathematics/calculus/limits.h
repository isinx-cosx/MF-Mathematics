#pragma once

#include <string>

#include <symengine/basic.h>
#include <symengine/symbol.h>

// 本文件曾把 limit / spl / expand_transcendental 声明在**全局命名空间**，
// 而同文件的 is_continuous_at / classify_discontinuity 在 mf::calculus ——
// 同一个头文件两种作用域。现统一收进 mf::calculus。
namespace mf::calculus {

// 计算 f/g 形式(或可化为 f/g)的极限:直接代值 → 0/0 洛必达 → 发散返回 ±inf。
// direction:"" 双侧,"+" 右极限,"-" 左极限(影响发散符号)。
double limit(const std::string& expr, const std::string& var, double point,
                    const std::string& direction = "");

// 分类派发:按表达式最外层形式(f/g、f-g、f*g、f^g、单值)调用对应极限函数。
double spl(const std::string& expr, const std::string& var, double point);

// 输入 SymEngine 表达式,把其中超越函数(sin/cos/tan/log/e^u)展开成泰勒多项式,
// 多项式与四则结构保持原样,返回展开后的表达式。
SymEngine::RCP<const SymEngine::Basic>
expand_transcendental(const SymEngine::RCP<const SymEngine::Basic>& expr,
                      const SymEngine::RCP<const SymEngine::Symbol>& var,
                      double point, long long order = 20);

// 判断函数在某点是否连续:f(point) 有定义、双侧极限存在且等于 f(point)。
bool is_continuous_at(const std::string& expr, const std::string& var,
                             double point);

// 间断点分类:无穷 / 振荡 / 可去 / 跳跃。
std::string classify_discontinuity(const std::string& expr,
                                          const std::string& var,
                                          double point);

}  // namespace mf::calculus