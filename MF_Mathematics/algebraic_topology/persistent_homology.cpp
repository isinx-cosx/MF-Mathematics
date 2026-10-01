#include "persistent_homology.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <map>
#include <numeric>
#include <set>
#include <stdexcept>
#include <utility>
#include <vector>

namespace mf::algebraic_topology {

namespace {

double euclidean(const std::vector<double>& p, const std::vector<double>& q) {
    double s = 0.0;
    for (std::size_t k = 0; k < p.size(); ++k) {
        const double d = p[k] - q[k];
        s += d * d;
    }
    return std::sqrt(s);
}

// 过滤复形中的一个单形:进入时刻 = 该单形的直径(顶点间最大距离)。
struct FilteredSimplex {
    double value = 0.0;
    std::vector<long long> verts;  // 升序顶点索引
};

// 过滤顺序:先按进入时刻,再按维数(面先于余面),最后按顶点字典序 —— 保证
// 过滤相容(任何单形都不早于它的面进入),同值时结果确定。
bool filtration_less(const FilteredSimplex& a, const FilteredSimplex& b) {
    if (a.value != b.value) return a.value < b.value;
    if (a.verts.size() != b.verts.size()) return a.verts.size() < b.verts.size();
    return a.verts < b.verts;
}

// F2 向量(按位压缩)中最高位下标;全零返回 -1。
long long highest_bit(const std::vector<std::uint64_t>& bits) {
    for (long long w = static_cast<long long>(bits.size()) - 1; w >= 0; --w) {
        const std::uint64_t v = bits[static_cast<std::size_t>(w)];
        if (v == 0) continue;
        long long b = 63;
        while ((v & (1ULL << b)) == 0) --b;
        return w * 64 + b;
    }
    return -1;
}

// ── dim-1 持续同调(VR 过滤的正确语义)─────────────────────────────────────
//
//  · VR_t 含所有直径 ≤ t 的单形;单形 σ 的进入时刻就是它的直径;
//  · 1-圈类的出生:某条边 e 的两端点在「先于 e 进入的边」里已经连通时,e 关闭
//    一个独立回路 —— 这正是 ∂_1 的列消元中「化零列」(等价于 Kruskal/并查集);
//  · 1-圈类的死亡:某个 2-单形 σ 的边界在 F2 上把该回路变成边界。按标准
//    (Edelsbrunner–Letscher–Zomorodian)列消元,把 ∂_2 的列在「边索引」空间里
//    化简,化零列的 low = 生成边 k 时,该类在 σ 的进入时刻死亡;
//  · 到 max_scale 仍未死亡的 1-圈类记 death = max_scale(与 dim-0 的存活分量
//    约定一致,见 filtration() 的注释)。
//
// 注:只把直径 ≤ max_scale 的单形收进过滤,因此所有 birth/death ≤ max_scale。
//     dim-0 沿用「不过滤 max_scale 之外的边」的老约定(用例期望值按该约定写),
//     两者在 max_scale 覆盖全部边时完全一致。
std::vector<BirthDeathPair> dim1_pairs(const std::vector<std::vector<double>>& D,
                                       double max_scale, long long max_dim) {
    const long long n = static_cast<long long>(D.size());
    std::vector<BirthDeathPair> out;

    std::vector<FilteredSimplex> edges;
    for (long long i = 0; i < n; ++i)
        for (long long j = i + 1; j < n; ++j)
            if (D[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] <= max_scale)
                edges.push_back({D[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)],
                                 {i, j}});
    if (edges.empty()) return out;
    std::sort(edges.begin(), edges.end(), filtration_less);

    // ∂_1:并查集。两端点已连通的边 → 化零列 → 生成一个 1-圈类。
    std::vector<long long> parent(static_cast<std::size_t>(n));
    std::iota(parent.begin(), parent.end(), 0LL);
    auto find = [&parent](long long x) -> long long {
        long long r = x;
        while (parent[static_cast<std::size_t>(r)] != r)
            r = parent[static_cast<std::size_t>(r)];
        while (parent[static_cast<std::size_t>(x)] != x) {
            const long long nx = parent[static_cast<std::size_t>(x)];
            parent[static_cast<std::size_t>(x)] = r;
            x = nx;
        }
        return r;
    };
    std::vector<char> is_creator(edges.size(), 0);
    std::vector<double> birth(edges.size(), 0.0);
    for (std::size_t e = 0; e < edges.size(); ++e) {
        const long long i = edges[e].verts[0];
        const long long j = edges[e].verts[1];
        const long long ri = find(i);
        const long long rj = find(j);
        if (ri == rj) {
            is_creator[e] = 1;
            birth[e] = edges[e].value;
        } else {
            parent[static_cast<std::size_t>(rj)] = ri;
        }
    }

    std::map<long long, double> death_of;  // 生成边索引 → 死亡时刻
    if (max_dim >= 2) {
        std::map<std::pair<long long, long long>, long long> edge_index;
        for (std::size_t e = 0; e < edges.size(); ++e)
            edge_index[{edges[e].verts[0], edges[e].verts[1]}] =
                static_cast<long long>(e);

        std::vector<FilteredSimplex> triangles;
        for (long long i = 0; i < n; ++i)
            for (long long j = i + 1; j < n; ++j)
                for (long long k = j + 1; k < n; ++k) {
                    const std::size_t si = static_cast<std::size_t>(i);
                    const std::size_t sj = static_cast<std::size_t>(j);
                    const std::size_t sk = static_cast<std::size_t>(k);
                    const double v = std::max(
                        D[si][sj], std::max(D[sj][sk], D[si][sk]));
                    if (v <= max_scale) triangles.push_back({v, {i, j, k}});
                }
        std::sort(triangles.begin(), triangles.end(), filtration_less);

        const std::size_t words = (edges.size() + 63) / 64;
        std::map<long long, std::vector<std::uint64_t>> reduced;  // low → 化零列
        for (const FilteredSimplex& tri : triangles) {
            std::vector<std::uint64_t> R(words, 0);
            for (std::size_t a = 0; a < 3; ++a) {
                const long long u = tri.verts[a];
                const long long v = tri.verts[(a + 1) % 3];
                const auto it = edge_index.find({std::min(u, v), std::max(u, v)});
                if (it == edge_index.end()) continue;
                const long long e = it->second;
                R[static_cast<std::size_t>(e / 64)] ^= (1ULL << (e % 64));
            }
            long long low = highest_bit(R);
            while (low >= 0) {
                const auto it = reduced.find(low);
                if (it == reduced.end()) break;
                const std::vector<std::uint64_t>& col = it->second;
                for (std::size_t w = 0; w < words; ++w) R[w] ^= col[w];
                low = highest_bit(R);
            }
            if (low >= 0) {
                reduced[low] = R;
                death_of[low] = tri.value;
            }
            // low < 0:该 2-单形自己生成一个 2-类(本函数不报告 dim-2)。
        }
    }

    for (std::size_t e = 0; e < edges.size(); ++e) {
        if (!is_creator[e]) continue;
        const auto it = death_of.find(static_cast<long long>(e));
        double death = it == death_of.end() ? max_scale : it->second;
        // 浮点归一:VR 里"三角形直径"与"某条边长度"数学上可以相等,但前者取的是
        // max(D_ij,D_jk,D_ik) 的某个分量,可能与后者差 1 ulp;这种差不是真正的
        // 持续性,统一记成 0(birth == death),避免报出不存在的微小正持续性类。
        const double scale = max_scale > 0.0 ? max_scale : 1.0;
        if (!(death - birth[e] > 1e-12 * scale)) death = birth[e];
        out.push_back({birth[e], death});
    }
    std::sort(out.begin(), out.end(),
              [](const BirthDeathPair& a, const BirthDeathPair& b) {
                  if (a.birth != b.birth) return a.birth < b.birth;
                  return a.death < b.death;
              });
    return out;
}

}  // namespace

FiltrationResult filtration(const std::vector<std::vector<double>>& points,
                            double max_scale, long long max_dim) {
    const long long n = static_cast<long long>(points.size());
    if (n == 0) throw std::invalid_argument("点云不能为空");
    const long long ambient = static_cast<long long>(points[0].size());
    for (const auto& p : points)
        if (static_cast<long long>(p.size()) != ambient)
            throw std::invalid_argument("点云各点维度不一致");

    FiltrationResult res;
    res.n_points = n;
    res.ambient_dim = ambient;
    res.max_scale = max_scale;

    // 距离矩阵 + 全部边(按长度升序)。与 Python 一致,不过滤 max_scale 之外
    // 的边(0 维分量仍会在超出尺度时合并,死亡的 ε 可能 > max_scale)。
    std::vector<std::vector<double>> D(static_cast<std::size_t>(n),
                                       std::vector<double>(static_cast<std::size_t>(n), 0.0));
    struct Edge {
        double len;
        long long i, j;
    };
    std::vector<Edge> edges;
    edges.reserve(static_cast<std::size_t>(n) * (n - 1) / 2);
    for (long long i = 0; i < n; ++i)
        for (long long j = i + 1; j < n; ++j) {
            const double d = euclidean(points[static_cast<std::size_t>(i)],
                                       points[static_cast<std::size_t>(j)]);
            D[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] = d;
            D[static_cast<std::size_t>(j)][static_cast<std::size_t>(i)] = d;
            edges.push_back({d, i, j});
        }
    std::sort(edges.begin(), edges.end(),
              [](const Edge& a, const Edge& b) { return a.len < b.len; });

    // dim-0:并查集追踪连通分量。所有顶点出生 ε=0(与 Python 一致);
    // 边连接两个分量时,一个分量死亡于该边长;剩余分量死亡于 max_scale。
    // 注:Python 的出生追踪存在潜藏 bug(出生值写在非根节点),但因所有出生
    // 均为 0 而不显现;此处用等价的简化实现,输出与 Python 一致。
    std::vector<long long> parent(static_cast<std::size_t>(n));
    std::iota(parent.begin(), parent.end(), 0LL);
    auto find = [&parent](long long x) -> long long {
        long long r = x;
        while (parent[static_cast<std::size_t>(r)] != r)
            r = parent[static_cast<std::size_t>(r)];
        while (parent[static_cast<std::size_t>(x)] != x) {
            const long long nx = parent[static_cast<std::size_t>(x)];
            parent[static_cast<std::size_t>(x)] = r;
            x = nx;
        }
        return r;
    };

    for (const auto& e : edges) {
        const long long ri = find(e.i);
        const long long rj = find(e.j);
        if (ri != rj) {
            res.birth_death_0.push_back({0.0, e.len});
            parent[static_cast<std::size_t>(rj)] = ri;
        }
    }
    std::set<long long> roots;
    for (long long i = 0; i < n; ++i) roots.insert(find(i));
    for (long long root : roots) {
        (void)root;
        res.birth_death_0.push_back({0.0, max_scale});
    }

    // dim-1:按 VR 过滤语义算 birth/death(见 dim1_pairs 的注释)。
    res.birth_death_1 = dim1_pairs(D, max_scale, max_dim);

    return res;
}

PersistenceDiagramResult persistence_diagram(
    const std::vector<std::vector<double>>& points, long long dim,
    double max_scale, double significance_ratio) {
    const FiltrationResult fr = filtration(points, max_scale);

    PersistenceDiagramResult res;
    res.dimension = dim;

    const std::vector<BirthDeathPair>* src = nullptr;
    if (dim == 0) src = &fr.birth_death_0;
    if (dim == 1) src = &fr.birth_death_1;
    if (src != nullptr) {
        for (const BirthDeathPair& bd : *src)
            res.pairs.push_back({bd.birth, bd.death, bd.death - bd.birth});
    }
    std::sort(res.pairs.begin(), res.pairs.end(),
              [](const PersistencePair& a, const PersistencePair& b) {
                  return a.persistence > b.persistence;
              });
    res.num_pairs = static_cast<long long>(res.pairs.size());
    for (const PersistencePair& pr : res.pairs)
        if (pr.persistence > max_scale * significance_ratio) ++res.significant_pairs;
    return res;
}

BarcodeResult barcode_plot(const std::vector<std::vector<double>>& points,
                           long long dim, double max_scale) {
    const PersistenceDiagramResult pd = persistence_diagram(points, dim, max_scale);

    BarcodeResult res;
    res.dimension = dim;
    for (const PersistencePair& pr : pd.pairs) {
        // 零持续性类(birth == death,例如某 2-单形与关闭回路的边同时进入)
        // 画出来长度为零,不是一条条形码条目,故不进入 barcodes。
        if (!(pr.persistence > 0.0)) continue;
        res.barcodes.push_back({static_cast<long long>(res.barcodes.size()), pr.birth,
                                pr.death, pr.persistence, pr.persistence});
    }
    res.num_bars = static_cast<long long>(res.barcodes.size());
    return res;
}

}  // namespace mf::algebraic_topology
