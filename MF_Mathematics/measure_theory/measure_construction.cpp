#include "measure_construction.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <stdexcept>

namespace mf::measure_theory {

double lebesgue_measure(double a, double b) { return std::abs(b - a); }

MeasureSetResult lebesgue_measure_set(const std::string& kind) {
    std::string s = kind;
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(::tolower(c)); });
    // 去掉空白，便于接受 "cantor set" 这类写法
    s.erase(std::remove_if(s.begin(), s.end(),
                           [](unsigned char c) { return std::isspace(c) != 0; }),
            s.end());
    if (s == "r" || s == "real" || s == "reals") return {0.0, true};   // λ(R) = +∞
    // 零测集：有理数、整数、自然数、Cantor 集
    if (s == "q" || s == "rational" || s == "rationals" || s == "n" ||
        s == "natural" || s == "z" || s == "integer" || s == "integers" ||
        s == "cantor" || s == "cantorset")
        return {0.0, false};
    // 以前这里对任何不认识的字符串都返回 0 —— 用户输入 "[0,1]" 会得到 0，
    // 是个**静默错误答案**。现在明确要求集合名，认不出来就报错。
    throw std::invalid_argument(
        "未知集合名 \"" + kind +
        "\"（可用：R=实数轴，Q/N/Z=可数集，cantor=Cantor 集；"
        "区间请把 E 写成 [a,b] 数组）");
}

OuterMeasureResult outer_measure(double a, double b, double epsilon) {
    if (epsilon <= 0) throw std::invalid_argument("epsilon 必须为正");
    const double length = std::abs(b - a);
    OuterMeasureResult r;
    r.measure = length;
    r.n_intervals = std::max<long long>(1, (long long)std::ceil(length / epsilon));
    r.cover_length = length;
    return r;
}

bool caratheodory_measurable(double a, double b) {
    const double m_A = std::abs(b - a) + 2.0;                 // A = [a-1, b+1]
    const double m_AE = std::abs(b - a);                      // A ∩ E = E
    const double m_AEc = 1.0 + 1.0;                           // 左右各长 1
    return std::abs(m_A - (m_AE + m_AEc)) < 1e-10;
}

std::vector<MeasureProperty> measure_properties() {
    return {
        {"非负性", "λ(E) ≥ 0 对一切可测集 E 成立", true},
        {"空集零测", "λ(∅) = 0", true},
        {"可数可加性", "对互不相交的可测集 E_n，λ(∪E_n) = Σλ(E_n)", true},
        {"平移不变性", "λ(E + t) = λ(E) 对任意 t ∈ R", true},
        {"单调性", "若 A ⊆ B 可测，则 λ(A) ≤ λ(B)", true},
    };
}

}  // namespace mf::measure_theory
