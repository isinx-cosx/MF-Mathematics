#include "complex_topology.h"

#include <cmath>
#include <queue>
#include <stdexcept>
#include <string>

#include "ca_internal.h"

namespace mf::complex_analysis {

namespace {
using mf::complex_analysis::detail::kPi;

bool point_in_region(const std::vector<std::pair<double, double>>& region,
                     double x, double y, double tol) {
    for (const auto& p : region) {
        const double dx = p.first - x, dy = p.second - y;
        if (dx * dx + dy * dy <= tol * tol) return true;
    }
    return false;
}
}  // namespace

bool is_open(const std::vector<std::pair<double, double>>& region, double x,
             double y, double epsilon) {
    if (region.empty()) return false;
    const int N = 16;
    for (int i = 0; i < N; ++i) {
        const double a = 2.0 * kPi * i / N;
        const double sx = x + epsilon * std::cos(a);
        const double sy = y + epsilon * std::sin(a);
        if (!point_in_region(region, sx, sy, 2.0 * epsilon)) return false;
    }
    return true;
}

bool is_connected(const std::vector<std::pair<double, double>>& region,
                  double threshold) {
    const std::size_t n = region.size();
    if (n <= 1) return true;
    std::vector<std::vector<std::size_t>> adj(n);
    for (std::size_t i = 0; i < n; ++i) {
        for (std::size_t j = i + 1; j < n; ++j) {
            const double dx = region[i].first - region[j].first;
            const double dy = region[i].second - region[j].second;
            if (dx * dx + dy * dy <= threshold * threshold) {
                adj[i].push_back(j);
                adj[j].push_back(i);
            }
        }
    }
    std::vector<bool> visited(n, false);
    std::queue<std::size_t> q;
    q.push(0);
    visited[0] = true;
    while (!q.empty()) {
        const std::size_t u = q.front();
        q.pop();
        for (std::size_t v : adj[u]) {
            if (!visited[v]) {
                visited[v] = true;
                q.push(v);
            }
        }
    }
    for (bool v : visited)
        if (!v) return false;
    return true;
}

bool is_domain(const std::vector<std::pair<double, double>>& region,
               double epsilon, double threshold) {
    if (region.empty()) return false;
    // 采样前 50 个点检查开性。
    const std::size_t limit = region.size() < 50 ? region.size() : 50;
    for (std::size_t i = 0; i < limit; ++i)
        if (!is_open(region, region[i].first, region[i].second, epsilon))
            return false;
    return is_connected(region, threshold);
}

std::vector<std::pair<double, double>> resolve_region(const std::string& name) {
    std::vector<std::pair<double, double>> pts;
    if (name == "unit_disk") {
        for (int ri = 0; ri < 20; ++ri) {
            const double r = ri / 19.0;
            const int n_theta = (r <= 0) ? 1 : std::max(8, (int)(40 * r));
            for (int ti = 0; ti < n_theta; ++ti) {
                const double th = 2.0 * kPi * ti / n_theta;
                pts.emplace_back(r * std::cos(th), r * std::sin(th));
            }
        }
    } else if (name == "separated_disks") {
        for (double cx : {-1.5, 1.5}) {
            for (int ri = 0; ri < 10; ++ri) {
                const double r = ri / 9.0 * 0.5;
                const int n_theta = (r <= 0) ? 1 : std::max(4, (int)(20 * r));
                for (int ti = 0; ti < n_theta; ++ti) {
                    const double th = 2.0 * kPi * ti / n_theta;
                    pts.emplace_back(cx + r * std::cos(th), r * std::sin(th));
                }
            }
        }
    } else {
        throw std::invalid_argument("未知区域名称: " + name);
    }
    return pts;
}

}  // namespace mf::complex_analysis
