// set_systems.h — 集合系:σ-代数判定、最小 σ-代数生成、Borel σ-代数。
#pragma once

#include <string>
#include <vector>


namespace mf::measure_theory {

// 判定 collection 是否为 X 上的 σ-代数(空集/全集/补封闭/有限并封闭)。
struct SigmaAlgebraResult {
    bool is_sigma_algebra = false;
    long long collection_size = 0;
};
SigmaAlgebraResult is_sigma_algebra(
    const std::vector<std::vector<long long>>& collection,
    const std::vector<long long>& X);

// 生成包含生成元的最小 σ-代数(有限全集,反复补/并直至封闭)。
struct GeneratedSigmaAlgebra {
    long long count = 0;
    std::vector<std::vector<long long>> sets;
    long long iterations = 0;
};
GeneratedSigmaAlgebra generate_sigma_algebra(
    const std::vector<std::vector<long long>>& generators,
    const std::vector<long long>& X);

// 由离散点集的所有连续子段(开区间)生成 Borel σ-代数。
GeneratedSigmaAlgebra borel_sigma_algebra(
    const std::vector<long long>& elements);

}  // namespace mf::measure_theory
