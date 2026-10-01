// sequences.h — 数列:通项求值、等差/等比、求和、递推。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::algebra {

// 通项公式求第 n 项。
MF_API double sequence_term(const std::string& formula, long long n);

// 等差数列前 n 项。
MF_API std::vector<double> arithmetic_sequence(double a1, double d, long long n);

// 等差数列前 n 项和 S_n = n(2a₁ + (n-1)d)/2。
MF_API double arithmetic_sum(double a1, double d, long long n);

// 等差数列求和公式(证明结论)。
MF_API std::string arithmetic_proof();

// 等比数列前 n 项。
MF_API std::vector<double> geometric_sequence(double a1, double q, long long n);

// 等比数列前 n 项和。
MF_API double geometric_sum(double a1, double q, long long n);

// 等比数列求和公式。
MF_API std::string geometric_proof();

// 递推数列:初始值 + 递推规则(引用 a[-1], a[-2] 等)。
//
// rule 收**未归一化**的原始规则串：`a[-k]` 是引擎自定义语法，先做输入归一化会把
// 标识符 `a` 与 `[` 之间补上隐式乘号（a*[-1]），使记号失配。归一化在函数内部、
// 代入数值之后进行。
MF_API std::vector<double> recurrence_sequence(
    const std::vector<double>& initial, const std::string& rule, long long n);

}  // namespace mf::algebra
