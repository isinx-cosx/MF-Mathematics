// degree_fixedpoint.h — 映射度与不动点定理:映射度、布劳威尔不动点、毛球定理。
#pragma once

#include <string>

#include "../mf_export.h"

namespace mf::algebraic_topology {

// 映射度 deg(f) : Sⁿ → Sⁿ 的经典值(概念性,不依赖显式映射)。
struct MappingDegree {
    long long sphere_dim = 0;
    long long antipodal_degree = 0;  // deg(对径映射 A(x)=-x) = (-1)^{n+1}
    long long identity_degree = 1;   // deg(id) = 1
};
MF_API MappingDegree mapping_degree(long long sphere_dim);

// 布劳威尔不动点定理:任何 f : Dⁿ → Dⁿ 连续必有不动的(定理恒成立)。
struct BrouwerResult {
    long long dimension = 0;
    bool holds = true;
};
MF_API BrouwerResult brouwer_fixed_point_theorem(const std::string& space);

// 毛球定理:偶数维球面 S^{2n} 上不存在处处非零的连续切向量场。
struct HairyBall {
    long long sphere_dim = 0;
    bool nonzero_vector_field_exists = false;
    long long euler_characteristic = 0;  // χ(S^n) = 2 (n 偶) / 0 (n 奇)
};
MF_API HairyBall hairy_ball_theorem(long long sphere_dim);

}  // namespace mf::algebraic_topology
