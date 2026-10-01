#include "set_systems.h"

#include <algorithm>

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
    std::vector<std::vector<long long>> sigma = {std::vector<long long>(),
                                                 Xs};
    for (const auto& s : generators) {
        const auto ns = sort_uniq(s);
        if (!contains_set(sigma, ns)) sigma.push_back(ns);
    }

    bool changed = true;
    long long iterations = 0;
    while (changed && iterations < 10) {
        changed = false;
        ++iterations;
        const auto snapshot = sigma;
        for (const auto& s : snapshot) {
            const auto comp = set_complement(s, Xs);
            if (!contains_set(sigma, comp)) {
                sigma.push_back(comp);
                changed = true;
            }
        }
        const auto snap2 = sigma;
        for (std::size_t i = 0; i < snap2.size(); ++i) {
            for (std::size_t j = i; j < snap2.size(); ++j) {
                const auto u = set_union(snap2[i], snap2[j]);
                if (!contains_set(sigma, u)) {
                    sigma.push_back(u);
                    changed = true;
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
