// complex_topology.h — 复平面拓扑:开集、连通性、区域。
#pragma once

#include <string>
#include <utility>
#include <vector>

#include "../mf_export.h"

namespace mf::complex_analysis {

// 点是否为区域的内点:采样 ε-邻域 16 方向,检查是否都在区域内。
MF_API bool is_open(const std::vector<std::pair<double, double>>& region,
                    double x, double y, double epsilon = 1e-6);

// 连通性:距离 ≤ threshold 建邻接图 BFS。
MF_API bool is_connected(const std::vector<std::pair<double, double>>& region,
                         double threshold = 0.1);

// 区域 = 开集 + 连通。
MF_API bool is_domain(const std::vector<std::pair<double, double>>& region,
                      double epsilon = 1e-6, double threshold = 0.1);

// 命名区域解析:返回离散点集。
MF_API std::vector<std::pair<double, double>> resolve_region(
    const std::string& name);

}  // namespace mf::complex_analysis
