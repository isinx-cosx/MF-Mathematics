#include "inner_product_spaces.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "../parser_lib.h"

namespace mf::functional_analysis {

namespace {

// 解析函数表达式为可求值对象(替换 sympy lambdify)。
struct Fn {
    std::shared_ptr<const mf::expr::ExprNode> root;
    double operator()(double x) const { return mf::expr::eval(root.get(), x); }
};
Fn make_fn(const std::string& expr) { return {mf::expr::parse(expr)}; }

std::string norm_space(const std::string& s) {
    std::string out;
    for (char ch : s)
        out.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
    return out;
}

}  // namespace

double inner_product(const std::string& f, const std::string& g, double a, double b,
                     long long n_points) {
    // 复合辛普森要求偶数个区间 → 奇数个采样点。
    if (n_points % 2 == 0) n_points += 1;
    if (n_points < 3) n_points = 3;
    const Fn ff = make_fn(f);
    const Fn gg = make_fn(g);
    const double h = (b - a) / static_cast<double>(n_points - 1);
    // 复合辛普森:y[0]+y[n-1] + 4Σy[1::2] + 2Σy[2:-2:2]
    double sum = 0.0;
    for (long long i = 0; i < n_points; ++i) {
        const double x = a + i * h;
        const double y = ff(x) * gg(x);
        if (i == 0 || i == n_points - 1) {
            sum += y;
        } else if (i % 2 == 1) {
            sum += 4.0 * y;
        } else {
            sum += 2.0 * y;
        }
    }
    return sum * h / 3.0;
}

bool funct_is_orthogonal(const std::string& f, const std::string& g, double a,
                         double b, double tol) {
    return std::abs(inner_product(f, g, a, b)) < tol;
}

std::vector<std::vector<double>> funct_gram_schmidt(
    const std::vector<std::vector<double>>& vectors) {
    std::vector<std::vector<double>> orthonormal;
    for (std::size_t k = 0; k < vectors.size(); ++k) {
        std::vector<double> uk = vectors[k];
        for (std::size_t j = 0; j < k; ++j) {
            // proj = ⟨v_k, e_j⟩ · e_j
            const std::vector<double>& ej = orthonormal[j];
            double ip = 0.0;
            for (std::size_t i = 0; i < uk.size(); ++i) ip += vectors[k][i] * ej[i];
            for (std::size_t i = 0; i < uk.size(); ++i) uk[i] -= ip * ej[i];
        }
        double nrm = 0.0;
        for (double v : uk) nrm += v * v;
        nrm = std::sqrt(nrm);
        if (nrm < 1e-12)
            throw std::invalid_argument("第 " + std::to_string(k + 1) + " 个向量与之前的线性相关");
        for (double& v : uk) v /= nrm;
        orthonormal.push_back(std::move(uk));
    }
    return orthonormal;
}

bool is_hilbert(const std::string& space_raw, long long dimension) {
    const std::string space = norm_space(space_raw);
    if (space == "r^n" || space == "c^n" || space == "l^2" || space == "l^2(n)" ||
        space == "l^2(z)" || space == "l^2(r)" || space == "sobolev h^k" ||
        space == "hardy h^2") {
        return true;
    }
    if (space == "c[0,1] under l^2" || space == "l^p for p≠2") {
        return false;
    }
    if (dimension > 0) return true;  // 有限维自动完备
    return false;
}

}  // namespace mf::functional_analysis
