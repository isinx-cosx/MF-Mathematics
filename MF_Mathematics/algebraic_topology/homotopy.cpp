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

// 常见英文名 → 引擎规范名（输入已由 normalize_space 转成大写、去掉 '^' 与空白）。
//
// 为什么要有它：引擎只认 S1/T2/D2 这套（与 homology_group / betti_numbers /
// poincare_duality 的空间名约定一致），而"圆""环面""圆盘"最自然的写法就是
// circle / torus / disk。以前写 circle 会落到"未知空间"分支、**把占位串 π₁(circle)
// 当结果返回**（isError:false）—— 用户完全看不出这不是答案。
// 别名只在**同伦等价**意义下成立：莫比乌斯带 ≃ S¹（π₁ 相同），故映射到 S1。
std::string canonical_space(const std::string& s) {
    if (s == "CIRCLE") return "S1";
    if (s == "SPHERE") return "S2";
    if (s == "TORUS") return "T2";
    if (s == "DISK" || s == "DISC") return "D2";
    if (s == "BALL") return "D3";
    if (s == "FIGURE8" || s == "FIGUREEIGHT" || s == "ROSE") return "FIG8";
    if (s == "MOBIUS" || s == "MOEBIUS" || s == "MOBIUSBAND") return "S1";
    if (s == "PROJECTIVEPLANE" || s == "REALPROJECTIVEPLANE") return "RP2";
    if (s == "KLEINBOTTLE") return "K";
    return s;
}

}  // namespace

std::string fundamental_group(const std::string& space_raw, long long n) {
    // 先归一化（大写、去 '^' 与空白），再把 circle/torus/disk 这类英文名换成规范名。
    const std::string space = canonical_space(detail::normalize_space(space_raw));
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
    /* 未识别的空间名：**如实报错**，而不是把 π₁(<输入>) 这种占位串当结果返回。
     *
     * 以前这里 return "π₁(" + space_raw + ")"，且 isError:false —— 用户看到 "π₁(circle)"
     * 会以为这就是答案（而 circle 本该是 Z，现在由 canonical_space 别名表处理）。
     * 与引擎其它地方的纪律一致：**不知道就不猜**。
     * ⚠ S⁰ 那条分支（上面 suffix_dim == 0）**保留占位符**：S⁰ 非道路连通，本就没有
     *   基本群可言，那是"如实说明"而不是"不知道"，引擎测试也明确要求（对齐 Python）。 */
    throw std::invalid_argument(
        "不认识的拓扑空间「" + space_raw + "」。可用写法："
        "S1/S2/S3…（球面）、T2（环面）、RP2（实射影平面）、K 或 KLEIN（克莱因瓶）、"
        "FIG8（8 字空间）、D2/D3…（圆盘/球体）、POINT、RN、WEDGE5（5 个圆的楔和）；"
        "也接受英文名 circle / sphere / torus / disk / ball / figure8 / mobius。");
}

bool is_simply_connected(const std::string& space, long long n) {
    return fundamental_group(space, n) == "0";
}

PathHomotopy path_homotopy(const std::string& space) {
    return {space, fundamental_group(space, 1)};
}

}  // namespace mf::algebraic_topology
