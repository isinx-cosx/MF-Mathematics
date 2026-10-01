// persistent_homology.h — 持续同调:Vietoris-Rips 过滤、持续同调图、条形码数据。
#pragma once

#include <vector>

#include "../mf_export.h"

namespace mf::algebraic_topology {

// 一个拓扑特征的出生-死亡对。
struct BirthDeathPair {
    double birth = 0.0;
    double death = 0.0;
};

// Vietoris-Rips 过滤复形结果:点云统计 + 各维 birth-death 对。
// dim-0:连通分量的出生-死亡(顶点出生 ε=0,合并时死亡;存活分量死亡记 max_scale,
//        且 0 维不过滤 max_scale 之外的边 —— 与 Python 一致的旧约定);
// dim-1:VR 过滤的正确语义 —— 单形进入时刻 = 其直径,只收直径 ≤ max_scale 的单形,
//        1-圈类在某 2-单形使其变成边界时死亡(死亡值 = 该 2-单形的直径),到
//        max_scale 仍未死亡者记 death = max_scale。同一过滤尺度上既出生又死亡的类
//        以 (b, b) 形式保留(标准列消元的输出),用 death − birth = 0 识别。
struct FiltrationResult {
    long long n_points = 0;
    long long ambient_dim = 0;
    double max_scale = 0.0;
    std::vector<BirthDeathPair> birth_death_0;
    std::vector<BirthDeathPair> birth_death_1;
};
MF_API FiltrationResult filtration(const std::vector<std::vector<double>>& points,
                                   double max_scale = 1.0,
                                   long long max_dim = 2);

// 持续同调图:第 dim 维的 (birth, death, persistence) 对,按 persistence 降序。
struct PersistencePair {
    double birth = 0.0;
    double death = 0.0;
    double persistence = 0.0;
};
struct PersistenceDiagramResult {
    long long dimension = 0;
    std::vector<PersistencePair> pairs;
    long long num_pairs = 0;
    // 显著对个数:persistence > max_scale × significance_ratio。
    // significance_ratio 为启发式阈值(默认 0.1,与 Python 对齐),可调用方覆盖。
    long long significant_pairs = 0;
};
MF_API PersistenceDiagramResult persistence_diagram(
    const std::vector<std::vector<double>>& points, long long dim = 0,
    double max_scale = 1.0, double significance_ratio = 0.1);

// 条形码数据:每个特征一条 {id, birth, death, persistence, bar_length}。
// 只输出长度 > 0 的条(零持续性类没有可视长度,不进 barcodes);id 从 0 连续编号。
struct Barcode {
    long long id = 0;
    double birth = 0.0;
    double death = 0.0;
    double persistence = 0.0;
    double bar_length = 0.0;
};
struct BarcodeResult {
    long long dimension = 0;
    long long num_bars = 0;
    std::vector<Barcode> barcodes;
};
MF_API BarcodeResult barcode_plot(const std::vector<std::vector<double>>& points,
                                  long long dim = 0, double max_scale = 1.0);

}  // namespace mf::algebraic_topology
