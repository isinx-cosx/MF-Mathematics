// inner_product_spaces.h — 内积空间与希尔伯特空间。
#pragma once

#include <string>
#include <vector>


namespace mf::functional_analysis {

// L²[a,b] 内积 ⟨f,g⟩ = ∫f·g dx(复合辛普森)。f、g 为表达式字符串。
double inner_product(const std::string& f, const std::string& g, double a,
                            double b, long long n_points = 1000);

// 正交性:|⟨f,g⟩| < tol。
bool funct_is_orthogonal(const std::string& f, const std::string& g,
                                double a, double b, double tol = 1e-6);

// 格拉姆-施密特正交化(标准点积)。线性相关抛 std::invalid_argument。
std::vector<std::vector<double>> funct_gram_schmidt(
    const std::vector<std::vector<double>>& vectors);

// 希尔伯特空间判断(查表 + 有限维自动完备)。
bool is_hilbert(const std::string& space, long long dimension = -1);

}  // namespace mf::functional_analysis
