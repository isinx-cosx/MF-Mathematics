// extras.h — 补齐视图里"未接入引擎"的模式所缺的能力（第一批：容易且能给出确定答案的）
//
// 分成三块：
//   · 有限维线性代数：矩阵乘法、谱半径、共轭（转置）算子、自伴判定、紧算子说明、
//     Fredholm 二择一、Riesz 表示元
//   · 复数：共轭、模长、辐角、Dirichlet η
//   · 数列：部分乘积、无穷乘积、绝对收敛判定（声明在 calculus/series.h，实现在那里，
//     以便复用它的通项数值求值）
//
// 有限维是这些模式的前提：命题在有限维下的答案都是确定的（例如"有限维线性算子必紧"），
// 所以这里给出的都不是"近似结论"，而是该前提下正确的结论并附上理由。

#pragma once

#include <string>
#include <vector>


namespace mf::extras {

// ── 有限维线性代数 ────────────────────────────────────────────────────────

// 矩阵乘法；A 的列数必须等于 B 的行数（不满足抛 std::invalid_argument）。
std::vector<std::vector<double>> matrix_multiply(
    const std::vector<std::vector<double>>& A,
    const std::vector<std::vector<double>>& B);

// 谱半径 ρ(A) = max |λ|；要求 A 为方阵。
double spectral_radius(const std::vector<std::vector<double>>& A);

// 共轭（转置）算子：实矩阵即转置 Aᵀ。
std::vector<std::vector<double>> adjoint_operator(
    const std::vector<std::vector<double>>& A);

// 自伴（实对称）判定。
bool is_self_adjoint(const std::vector<std::vector<double>>& A, double tol = 1e-9);

// 紧算子：有限维下必有界且紧，返回理由（用于结果说明）。
std::string compact_operator_reason(
    const std::vector<std::vector<double>>& A);

// Fredholm 二择一：Ax=b 要么对任意 b 唯一可解，要么齐次共轭方程有非零解。
// 返回结论文本（含 rank 等依据）。has_b 为假时只做齐次部分。
std::string fredholm_alternative(
    const std::vector<std::vector<double>>& A,
    const std::vector<double>& b, bool has_b);

// Riesz 表示定理（有限维）：泛函 f(v) = <v, x> 由 x 自身表示，返回该表示元。
std::vector<double> riesz_representer(const std::vector<double>& x);

// ── 复数 ──────────────────────────────────────────────────────────────────

// 共轭（符号）：z̄。解析不了抛 std::invalid_argument。
std::string complex_conjugate(const std::string& expr);
// 模长 |z|。
double complex_modulus(const std::string& expr);
// 辐角 arg z（弧度，(-π, π]）。
double complex_argument(const std::string& expr);
// Dirichlet η 函数 η(s) = (1 - 2^{1-s}) ζ(s)。
double dirichlet_eta(double s);

}  // namespace mf::extras
