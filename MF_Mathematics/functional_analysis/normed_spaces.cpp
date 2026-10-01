#include "normed_spaces.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace mf::functional_analysis {

namespace {

// 归一化空间名:仅小写(与 Python space.lower() 一致)。
std::string norm_space(const std::string& s) {
    std::string out;
    for (char ch : s)
        out.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
    return out;
}

double norm_l2(const std::vector<double>& v) {
    double s = 0.0;
    for (double x : v) s += x * x;
    return std::sqrt(s);
}
double norm_l1(const std::vector<double>& v) {
    double s = 0.0;
    for (double x : v) s += std::abs(x);
    return s;
}
double norm_linf(const std::vector<double>& v) {
    double m = 0.0;
    for (double x : v) m = std::max(m, std::abs(x));
    return m;
}

}  // namespace

double lp_norm(const std::vector<double>& vector, double p) {
    if (p == std::numeric_limits<double>::infinity()) {
        double m = 0.0;
        for (double x : vector) m = std::max(m, std::abs(x));
        return m;
    }
    if (p <= 0.0) throw std::invalid_argument("p 必须为正实数");
    double s = 0.0;
    for (double x : vector) s += std::pow(std::abs(x), p);
    return std::pow(s, 1.0 / p);
}

bool is_banach(const std::string& space_raw, long long dimension) {
    const std::string space = norm_space(space_raw);
    if (space == "r^n" || space == "c^n" || space == "l^p" ||
        space == "c[0,1]" || space == "c_0" || space == "l^∞") {
        return true;
    }
    if (space == "c[0,1] under l^1" || space == "polynomials under sup-norm") {
        return false;
    }
    if (dimension > 0) return true;  // 有限维自动完备
    return false;
}

CompletenessResult space_completeness_check(
    const std::vector<std::vector<double>>& sequence, const std::string& norm) {
    if (sequence.size() < 3)
        throw std::invalid_argument("序列长度至少为 3 才能判断收敛趋势");
    double (*norm_fn)(const std::vector<double>&) = nullptr;
    const std::string t = norm;
    if (t == "l1")
        norm_fn = norm_l1;
    else if (t == "l2" || t == "euclidean")
        norm_fn = norm_l2;
    else if (t == "linf" || t == "sup" || t == "infinity")
        norm_fn = norm_linf;
    else
        throw std::invalid_argument("未知范数类型: " + norm);

    CompletenessResult res;
    for (std::size_t i = 0; i + 1 < sequence.size(); ++i) {
        std::vector<double> diff;
        for (std::size_t k = 0; k < sequence[i].size(); ++k)
            diff.push_back(sequence[i + 1][k] - sequence[i][k]);
        res.all_diffs.push_back(norm_fn(diff));
    }

    // 尾部最大差异:后 5 项两两范数差
    const std::size_t tail_start = sequence.size() >= 5 ? sequence.size() - 5 : 0;
    double max_tail = 0.0;
    for (std::size_t i = tail_start; i < sequence.size(); ++i)
        for (std::size_t j = i + 1; j < sequence.size(); ++j) {
            std::vector<double> diff;
            for (std::size_t k = 0; k < sequence[i].size(); ++k)
                diff.push_back(sequence[j][k] - sequence[i][k]);
            max_tail = std::max(max_tail, norm_fn(diff));
        }
    res.tail_max_diff = max_tail;
    res.is_cauchy = max_tail < 1e-3;
    return res;
}

}  // namespace mf::functional_analysis
