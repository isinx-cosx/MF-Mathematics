#include "real_numbers.h"

#include <algorithm>
#include <cmath>
#include <cctype>
#include <stdexcept>

namespace mf::real_analysis {

bool dedekind_cut(const std::vector<double>& A, const std::vector<double>& B) {
    if (A.empty() || B.empty()) return false;
    // 不相交。
    for (double a : A)
        for (double b : B)
            if (std::abs(a - b) < 1e-12) return false;
    // 所有 a < b。
    const double max_A = *std::max_element(A.begin(), A.end());
    const double min_B = *std::min_element(B.begin(), B.end());
    return max_A < min_B;
}

double supremum(const std::vector<double>& s, bool& has_value) {
    if (s.empty()) {
        has_value = false;
        return 0.0;
    }
    has_value = true;
    return *std::max_element(s.begin(), s.end());
}

// 解析 "{x | x < N}" / "{x | x <= N}" / "{x | x > N}"(无上界)。
double supremum_desc(const std::string& desc, bool& has_value) {
    // 提取数字。
    const std::size_t lt = desc.find('<');
    const std::size_t gt = desc.find('>');
    if (gt != std::string::npos && gt > desc.find('x')) {
        // x > N:无上界。
        has_value = false;
        return std::numeric_limits<double>::infinity();
    }
    if (lt != std::string::npos) {
        // 找到 < 或 <= 后的数字。
        std::size_t start = lt + 1;
        if (start < desc.size() && desc[start] == '=') ++start;
        while (start < desc.size() && (std::isspace((unsigned char)desc[start]) ||
                                       desc[start] == '}'))
            ++start;
        has_value = true;
        return std::stod(desc.substr(start));
    }
    has_value = false;
    return 0.0;
}

double infimum(const std::vector<double>& s, bool& has_value) {
    if (s.empty()) {
        has_value = false;
        return 0.0;
    }
    has_value = true;
    return *std::min_element(s.begin(), s.end());
}

double infimum_desc(const std::string& desc, bool& has_value) {
    const std::size_t gt = desc.find('>');
    const std::size_t lt = desc.find('<');
    if (lt != std::string::npos && lt > desc.find('x')) {
        // x < N:无下界。
        has_value = false;
        return -std::numeric_limits<double>::infinity();
    }
    if (gt != std::string::npos) {
        std::size_t start = gt + 1;
        if (start < desc.size() && desc[start] == '=') ++start;
        while (start < desc.size() && (std::isspace((unsigned char)desc[start]) ||
                                       desc[start] == '}'))
            ++start;
        has_value = true;
        return std::stod(desc.substr(start));
    }
    has_value = false;
    return 0.0;
}

long long archimedean_property(double x, double epsilon) {
    if (epsilon <= 0) throw std::invalid_argument("ε 必须为正数");
    return (long long)(std::abs(x) / epsilon) + 1;
}

}  // namespace mf::real_analysis
