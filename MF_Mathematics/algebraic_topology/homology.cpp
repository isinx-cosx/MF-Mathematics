#include "homology.h"

#include <algorithm>
#include <cctype>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>

namespace mf::algebraic_topology {

namespace {

// 单形是否升序(合法输入)
Simplex normalize_simplex(const Simplex& s) {
    Simplex v = s;
    std::sort(v.begin(), v.end());
    return v;
}

}  // namespace

SimplicialComplexResult build_simplicial_complex(
    const std::vector<Simplex>& simplices, bool maximal) {
    // 加入输入单形,若 maximal 则补全所有面直到封闭
    std::set<Simplex> all;
    for (const Simplex& s : simplices) all.insert(normalize_simplex(s));
    if (maximal) {
        std::vector<Simplex> queue(all.begin(), all.end());
        while (!queue.empty()) {
            const Simplex cur = queue.back();
            queue.pop_back();
            for (const Simplex& f : detail::faces(cur)) {
                if (all.insert(f).second) queue.push_back(f);
            }
        }
    }

    SimplicialComplexResult res;
    std::set<long long> vertices;
    for (const Simplex& s : all) {
        const long long dim = static_cast<long long>(s.size()) - 1;
        res.complex[dim].push_back(s);
        for (long long v : s) vertices.insert(v);
    }
    res.num_vertices = static_cast<long long>(vertices.size());
    res.num_simplices = static_cast<long long>(all.size());
    res.max_dimension = res.complex.empty() ? -1 : res.complex.rbegin()->first;
    return res;
}

HomologyGroup homology_group(const Complex& c, long long n) {
    const auto get = [&c](long long d) -> const std::vector<Simplex>& {
        static const std::vector<Simplex> empty;
        auto it = c.find(d);
        return it == c.end() ? empty : it->second;
    };

    // ∂_n : C_n → C_{n-1},∂_{n+1} : C_{n+1} → C_n
    const auto& cn = get(n);
    const auto& cn_1 = get(n - 1);
    const auto& cn_plus_1 = get(n + 1);

    const long long rank_bn = detail::integer_rank(detail::boundary_matrix(cn, cn_1));
    const long long rank_bn1 = detail::integer_rank(detail::boundary_matrix(cn_plus_1, cn));

    const long long dim_cn = static_cast<long long>(cn.size());
    const long long dim_ker = dim_cn - rank_bn;
    const long long betti = std::max<long long>(0, dim_ker - rank_bn1);

    // 挠系数:torsion(H_n) = torsion(coker ∂_{n+1}) = ∂_{n+1} 的 Smith 不变因子中 > 1 者
    // (0 → H_n → C_n/im ∂_{n+1} → im ∂_n → 0 且 im ∂_n 自由,可分裂)。用整数 SNF 精确算出。
    const std::vector<long long> torsion = detail::torsion_of_lower_homology(cn_plus_1, cn);
    return {betti, torsion, detail::format_group(betti, torsion)};
}

HomologyGroup homology_group(const std::string& space_raw, long long n) {
    using Entry = std::pair<long long, std::vector<long long>>;
    static const std::map<std::string, std::map<long long, Entry>> known = {
        {"S1", {{0, {1, {}}}, {1, {1, {}}}}},
        {"S2", {{0, {1, {}}}, {1, {0, {}}}, {2, {1, {}}}}},
        {"T2", {{0, {1, {}}}, {1, {2, {}}}, {2, {1, {}}}}},
        {"S3", {{0, {1, {}}}, {3, {1, {}}}}},
        {"RP2", {{0, {1, {}}}, {1, {0, {2}}}, {2, {0, {}}}}},
        {"K", {{0, {1, {}}}, {1, {1, {2}}}, {2, {0, {}}}}},
        {"FIG8", {{0, {1, {}}}, {1, {2, {}}}}},
    };
    // 与 fundamental_group 共用别名表（at_internal.h）：写 circle / torus 等英文名
    // 在同组各模式里必须得到一致行为，否则用户会以为是自己写错了。
    const std::string space = detail::canonical_space(detail::normalize_space(space_raw));
    auto space_it = known.find(space);
    if (space_it == known.end())
        throw std::invalid_argument("未知空间类型: " + space_raw);
    auto it = space_it->second.find(n);
    const Entry entry = (it == space_it->second.end()) ? Entry{0, {}} : it->second;
    const long long betti = entry.first;
    const std::vector<long long> torsion = entry.second;
    return {betti, torsion, detail::format_group(betti, torsion)};
}

std::vector<long long> betti_numbers(const Complex& c, long long max_dim) {
    if (c.empty()) return {};
    if (max_dim < 0) max_dim = c.rbegin()->first;
    std::vector<long long> betti;
    betti.reserve(static_cast<std::size_t>(max_dim) + 1);
    for (long long d = 0; d <= max_dim; ++d) betti.push_back(homology_group(c, d).betti);
    return betti;
}

std::vector<long long> betti_numbers(const std::string& space_raw) {
    static const std::map<std::string, std::vector<long long>> known = {
        {"S1", {1, 1}},
        {"S2", {1, 0, 1}},
        {"S3", {1, 0, 0, 1}},
        {"T2", {1, 2, 1}},
        {"RP2", {1, 0, 0}},
        {"K", {1, 1, 0}},
        {"FIG8", {1, 2}},
        {"POINT", {1}},
        {"RN", {1}},
    };
    // 与 fundamental_group 共用别名表（at_internal.h）：写 circle / torus 等英文名
    // 在同组各模式里必须得到一致行为，否则用户会以为是自己写错了。
    const std::string space = detail::canonical_space(detail::normalize_space(space_raw));
    auto it = known.find(space);
    if (it == known.end())
        throw std::invalid_argument("未知空间类型: " + space_raw);
    return it->second;
}

long long euler_characteristic(const Complex& c) {
    long long chi = 0;
    for (const auto& [dim, simplices] : c)
        chi += (dim % 2 == 0 ? 1 : -1) * static_cast<long long>(simplices.size());
    return chi;
}

long long euler_characteristic(const std::string& space_raw) {
    long long chi = 0;
    const std::vector<long long> betti = betti_numbers(space_raw);
    for (std::size_t k = 0; k < betti.size(); ++k)
        chi += (k % 2 == 0 ? 1 : -1) * betti[k];
    return chi;
}

BoundaryOperator boundary_operator(long long dimension) {
    // ∂_n[v₀,…,v_n] = Σ_{i=0}^{n} (-1)^i [v₀,…,v̂ᵢ,…,v_n]
    std::string formula = "∂_" + std::to_string(dimension) +
                          "[v₀,…,v_" + std::to_string(dimension) +
                          "] = Σ(-1)^i [v₀,…,v̂ᵢ,…,v_" + std::to_string(dimension) + "]";
    return {dimension, std::move(formula)};
}

}  // namespace mf::algebraic_topology
