#include "set_systems.h"

#include <algorithm>
#include <set>

#include "mt_internal.h"

namespace mf::measure_theory {

namespace {
using mf::measure_theory::detail::normalize_collection;
using mf::measure_theory::detail::sort_uniq;
using mf::measure_theory::detail::set_union;
using mf::measure_theory::detail::set_complement;
using mf::measure_theory::detail::contains_set;
}  // namespace

SigmaAlgebraResult is_sigma_algebra(
    const std::vector<std::vector<long long>>& collection,
    const std::vector<long long>& X) {
    const auto coll = normalize_collection(collection);
    const auto Xs = sort_uniq(X);
    const std::vector<long long> empty;

    if (!contains_set(coll, empty)) return {false, (long long)coll.size()};
    if (!contains_set(coll, Xs)) return {false, (long long)coll.size()};

    for (const auto& s : coll) {
        if (!contains_set(coll, set_complement(s, Xs)))
            return {false, (long long)coll.size()};
    }
    for (std::size_t i = 0; i < coll.size(); ++i) {
        for (std::size_t j = i; j < coll.size(); ++j) {
            if (!contains_set(coll, set_union(coll[i], coll[j])))
                return {false, (long long)coll.size()};
        }
    }
    return {true, (long long)coll.size()};
}

GeneratedSigmaAlgebra generate_sigma_algebra(
    const std::vector<std::vector<long long>>& generators,
    const std::vector<long long>& X) {
    const auto Xs = sort_uniq(X);
    std::vector<std::vector<long long>> sigma;
    /**
     * 成员判定用**索引**，不再线性扫描。
     *
     * 旧写法每次 `contains_set(sigma, x)` 都要与 |σ| 个集合逐个比较，而并集枚举
     * 本身是 O(|σ|²) → 整体 O(|σ|³)。12 个生成元时 |σ| 只有 4096，实测却要 **9.7 秒**
     * （纯浪费，算法没变聪明，只是查重方式差）。换成有序集合后整体降到
     * O(|σ|² log |σ|)，同样的输入在毫秒级完成。
     * 语义不变：集合以 sort_uniq 后的向量形式精确比较。
     */
    std::set<std::vector<long long>> seen;
    const auto add_set = [&](std::vector<long long> s) -> bool {
        if (!seen.insert(s).second) return false;      // 已存在
        sigma.push_back(std::move(s));
        return true;
    };
    add_set(std::vector<long long>());
    add_set(Xs);
    for (const auto& s : generators) add_set(sort_uniq(s));

    // ⚠ 规模会爆炸：|σ| 最坏可达 2^|X|，而下面每轮都要做 O(|σ|²) 的并集枚举。
    //   元素个数只多几个就会从"瞬间"变成"永远"。与其静默返回一个残缺的集合族
    //   （那会被当成"生成的 σ-代数"），不如明确拒绝。
    constexpr std::size_t kMaxSigmaSets = 20000;
    const auto too_big = [&]() {
        if (sigma.size() > kMaxSigmaSets)
            throw std::invalid_argument(
                "生成 σ-代数规模过大（已超过 " + std::to_string(kMaxSigmaSets) +
                " 个集合）：X 有 " + std::to_string(Xs.size()) +
                " 个元素时幂集规模是 2^" + std::to_string(Xs.size()) +
                "。请减少生成元或改用更小的样本空间。");
    };

    bool changed = true;
    long long iterations = 0;
    while (changed && iterations < 10) {
        changed = false;
        ++iterations;
        const auto snapshot = sigma;
        for (const auto& s : snapshot) {
            if (add_set(set_complement(s, Xs))) {
                changed = true;
                too_big();
            }
        }
        const auto snap2 = sigma;
        for (std::size_t i = 0; i < snap2.size(); ++i) {
            for (std::size_t j = i; j < snap2.size(); ++j) {
                if (add_set(set_union(snap2[i], snap2[j]))) {
                    changed = true;
                    too_big();
                }
            }
        }
    }

    // 按长度升序、字典序排序。
    std::sort(sigma.begin(), sigma.end(),
              [](const std::vector<long long>& a, const std::vector<long long>& b) {
                  if (a.size() != b.size()) return a.size() < b.size();
                  return a < b;
              });
    return {static_cast<long long>(sigma.size()), sigma, iterations};
}

GeneratedSigmaAlgebra borel_sigma_algebra(
    const std::vector<long long>& elements) {
    // ⚠ 先挡元素个数：本函数会生成 O(N²) 个开区间（每个最长 N 个元素），
    //   再交给 generate_sigma_algebra 做 O(|σ|²) 的扩张 —— 合起来是 O(N³) 内存量级。
    //   N=1e5 时第一步就要 push 1e10 个元素（用户输入 `{"space":[0,100000]}` 即触发）。
    if (elements.size() > 200)
        throw std::invalid_argument(
            "Borel σ-代数：元素个数 " + std::to_string(elements.size()) +
            " 过多（上限 200）。生成开区间是 O(N²)、再生成 σ-代数是 O(N³)，"
            "请改用更小的样本空间。");
    std::vector<std::vector<long long>> open_intervals;
    for (std::size_t i = 0; i < elements.size(); ++i) {
        for (std::size_t j = i + 1; j <= elements.size(); ++j) {
            open_intervals.emplace_back(elements.begin() + i,
                                        elements.begin() + j);
        }
    }
    return generate_sigma_algebra(open_intervals, elements);
}

}  // namespace mf::measure_theory
