// homotopy.h — 同伦与基本群:π₁、单连通性、路径同伦。
#pragma once

#include <string>


namespace mf::algebraic_topology {

// 基本群 π₁(space) 的群字符串。
//   支持:S1 → Z;S<k>(k≥2,含字面拼写 S2/S3/… 与 "SN"+n 两种写法) → 0;
//        T2 → Z×Z;RP2 → Z_2;K → <a,b|aba⁻¹b>;fig8 → F_2;
//        wedge 形如 wedge_5 → F_5(从名字解析个数,无数字回退 n);
//        可缩空间 D<k>(k≥1)/point/R^n → 0。
//   未知空间返回占位符 "π₁(<space>)",与 Python 行为一致。
std::string fundamental_group(const std::string& space, long long n = 1);

// 单连通判定:π₁ 平凡(群字符串为 "0")。
bool is_simply_connected(const std::string& space, long long n = 1);

// 路径同伦概念结果:路径同伦等价于在基本群中代表同一元素。
struct PathHomotopy {
    std::string space;
    std::string fundamental_group;
};
PathHomotopy path_homotopy(const std::string& space);

}  // namespace mf::algebraic_topology
