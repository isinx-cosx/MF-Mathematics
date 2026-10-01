#include "degree_fixedpoint.h"

#include <string>

#include "at_internal.h"

namespace mf::algebraic_topology {

MappingDegree mapping_degree(long long sphere_dim) {
    // deg(对径映射) = (-1)^{n+1}
    const bool positive = (sphere_dim + 1) % 2 == 0;
    return {sphere_dim, positive ? 1 : -1, 1};
}

BrouwerResult brouwer_fixed_point_theorem(const std::string& space_raw) {
    // 维数查表:D1/D2/D3,未知默认 2(与 Python 一致)
    const std::string space = detail::normalize_space(space_raw);
    long long dim = 2;
    if (space == "D1") dim = 1;
    if (space == "D3") dim = 3;
    return {dim, true};
}

HairyBall hairy_ball_theorem(long long sphere_dim) {
    const bool even = sphere_dim % 2 == 0;
    return {sphere_dim, !even, even ? 2 : 0};
}

}  // namespace mf::algebraic_topology
