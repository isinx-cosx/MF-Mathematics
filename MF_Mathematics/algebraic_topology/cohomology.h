// cohomology.h — 上同调:上同调群(同调对偶)与庞加莱对偶验证。
#pragma once

#include <string>

#include "../mf_export.h"
#include "homology.h"

namespace mf::algebraic_topology {

// 上同调群 H^n:整系数下由万有系数定理给出
//   H^n(X;Z) ≅ Free(H_n) ⊕ Ext(H_{n-1},Z) ≅ Free(H_n) ⊕ Torsion(H_{n-1})
// 即自由部分秩 = β_n,挠部分 = H_{n-1} 的挠(H_{-1} = 0)。注意 H^n 一般 *不* 同构于 H_n:
// 例如 H¹(RP²;Z) = 0 而 H₁(RP²) = Z_2,H²(RP²;Z) = Z_2 而 H₂(RP²) = 0。
// 输入与 homology_group 相同:单纯复形或已知空间名。挠系数由 Smith 标准形精确给出
// (复形路径用 ∂_n 的 Smith 不变因子;空间查表路径用已知空间的精确挠)。
MF_API HomologyGroup cohomology_group(const Complex& c, long long n);
MF_API HomologyGroup cohomology_group(const std::string& space, long long n);

// 庞加莱对偶验证:H^k(M) 与 H_{n-k}(M) 的贝蒂数是否相等。
struct PoincareDuality {
    std::string manifold;
    long long dimension = 0;
    long long co_betti = 0;
    long long hom_betti = 0;
    bool duality_holds = false;
};
MF_API PoincareDuality poincare_duality(const std::string& manifold, long long k);

// 杯积概念结果:⌣ : H^p × H^q → H^{p+q}(概念性)。
struct CupProduct {
    std::string operation;
    std::string mapping;
};
MF_API CupProduct cup_product();

}  // namespace mf::algebraic_topology
