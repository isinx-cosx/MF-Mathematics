#include "cohomology.h"

#include <map>
#include <stdexcept>
#include <string>

#include "at_internal.h"
#include "homology.h"

namespace mf::algebraic_topology {

namespace {

// 万有系数定理(Z 系数,有限生成复形):
//   H^n(X;Z) ≅ Free(H_n) ⊕ Ext(H_{n-1},Z) ≅ Free(H_n) ⊕ Torsion(H_{n-1})
// 即:自由部分取自 H_n(秩 = β_n),挠部分取自 H_{n-1} 的挠
// (Ext(A,Z) ≅ Torsion(A) 对有限生成交换群成立)。n = 0 时 H_{-1} = 0。
HomologyGroup uct(long long betti_n, const std::vector<long long>& torsion_nm1) {
    return {betti_n, torsion_nm1, detail::format_group(betti_n, torsion_nm1)};
}

}  // namespace

HomologyGroup cohomology_group(const Complex& c, long long n) {
    // 复形路径:自由部分取 H_n 的秩;挠部分取 H_{n-1} 的挠 —— 后者由
    // at_internal.h 的 Smith 标准形从 ∂_n 直接算出(不再是空列表),
    // 所以这里得到的是真正的 H^n,而不是 H_n。
    const HomologyGroup hn = homology_group(c, n);
    const HomologyGroup hnm1 = homology_group(c, n - 1);
    return uct(hn.betti, hnm1.torsion);
}

HomologyGroup cohomology_group(const std::string& space, long long n) {
    const HomologyGroup hn = homology_group(space, n);
    const HomologyGroup hnm1 = homology_group(space, n - 1);
    return uct(hn.betti, hnm1.torsion);
}

PoincareDuality poincare_duality(const std::string& manifold_raw, long long k) {
    static const std::map<std::string, long long> dims = {
        {"S1", 1}, {"S2", 2}, {"S3", 3},
        {"T2", 2}, {"RP2", 2}, {"K", 2},
    };
    const std::string manifold = detail::normalize_space(manifold_raw);
    auto it = dims.find(manifold);
    if (it == dims.end())
        throw std::invalid_argument("未知流形: " + manifold_raw);
    const long long n = it->second;

    const long long co_betti = cohomology_group(manifold, k).betti;
    const long long hom_betti = homology_group(manifold, n - k).betti;
    return {manifold_raw, n, co_betti, hom_betti, co_betti == hom_betti};
}

CupProduct cup_product() { return {"cup_product", "H^p × H^q → H^{p+q}"}; }

}  // namespace mf::algebraic_topology
