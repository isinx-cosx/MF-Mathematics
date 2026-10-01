#include "homotopy.h"

#include <cctype>
#include <string>

#include "at_internal.h"

namespace mf::algebraic_topology {

namespace {

// 归一化空间名后缀是否全为数字("S3" → "3");空串或含非数字 → false。
bool all_digits(const std::string& s) {
    if (s.empty()) return false;
    for (char ch : s)
        if (!std::isdigit(static_cast<unsigned char>(ch))) return false;
    return true;
}

// 形如 S<k> / D<k> 的维数;不匹配返回 -1。
long long suffix_dim(const std::string& space, char prefix) {
    if (space.size() < 2 || space[0] != prefix) return -1;
    const std::string tail = space.substr(1);
    if (!all_digits(tail)) return -1;
    try {
        return std::stoll(tail);
    } catch (...) {
        return -1;  // 数字过长
    }
}

}  // namespace

std::string fundamental_group(const std::string& space_raw, long long n) {
    const std::string space = detail::normalize_space(space_raw);
    // S^k 的两种等价写法:字面拼写 S2/S3/…(与 homology_group / betti_numbers /
    // poincare_duality 的空间名约定一致)与 "SN" + 参数 n。π₁(S¹)=Z,π₁(S^k)=0(k≥2)。
    {
        const long long k = suffix_dim(space, 'S');
        if (k == 1) return "Z";
        if (k >= 2) return "0";
        if (k == 0) return "π₁(" + space_raw + ")";  // S⁰ 非道路连通,不给群
    }
    if (space == "SN") {
        // 与 Python 一致:n=1 → Z,n≥2 → 0;n=0(S⁰)落到占位符。
        if (n >= 2) return "0";
        if (n == 1) return "Z";
        return "π₁(" + space_raw + ")";
    }
    if (space == "T2") return "Z×Z";
    if (space == "RP2") return "Z_2";
    if (space == "K" || space == "KLEIN") return "<a,b | aba^{-1}b>";
    if (space == "FIG8") return "F_2";
    // 可缩空间:圆盘 D^k(与 brouwer_fixed_point_theorem 认得的 D1/D2/D3 同名约定)、
    // 单点、R^n(betti_numbers 表里的 POINT / RN)。π₁ = 0。
    if (suffix_dim(space, 'D') >= 1) return "0";
    if (space == "POINT" || space == "RN") return "0";
    if (space.rfind("WEDGE", 0) == 0) {
        // 优先从名字解析楔和个数:"WEDGE5"/"WEDGE_5" → F_5;
        // 无数字时回退 n 参数("WEDGEN" 等与 Python 行为一致)。
        std::string tail = space.substr(5);
        if (!tail.empty() && tail.front() == '_') tail.erase(tail.begin());
        if (!tail.empty()) {
            bool digits = true;
            for (char ch : tail)
                if (!std::isdigit(static_cast<unsigned char>(ch))) {
                    digits = false;
                    break;
                }
            if (digits) return "F_" + tail;
        }
        return "F_" + std::to_string(n);
    }
    return "π₁(" + space_raw + ")";
}

bool is_simply_connected(const std::string& space, long long n) {
    return fundamental_group(space, n) == "0";
}

PathHomotopy path_homotopy(const std::string& space) {
    return {space, fundamental_group(space, 1)};
}

}  // namespace mf::algebraic_topology
