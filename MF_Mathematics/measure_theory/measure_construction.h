// measure_construction.h — 测度构造:外测度、Carathéodory 可测、勒贝格测度、测度性质。
#pragma once

#include <limits>
#include <string>
#include <vector>


namespace mf::measure_theory {

// 区间 [a, b] 的勒贝格测度 λ([a,b]) = |b-a|。
double lebesgue_measure(double a, double b);

// 特殊集合的勒贝格测度:"Q"/"N" → 0;"R" → +∞。
struct MeasureSetResult {
    double value = 0.0;
    bool infinite = false;
};
MeasureSetResult lebesgue_measure_set(const std::string& kind);

// 外测度 m*([a,b]) = b-a(下确界由覆盖逼近)。
struct OuterMeasureResult {
    double measure = 0.0;
    long long n_intervals = 0;
    double cover_length = 0.0;
};
OuterMeasureResult outer_measure(double a, double b, double epsilon);

// Carathéodory 可测判定:勒贝格外测度下区间总是可测。
bool caratheodory_measurable(double a, double b);

// 勒贝格测度的基本性质(非负/空集/可数可加/平移不变/单调)。
struct MeasureProperty {
    std::string name;
    std::string statement;
    bool verified = true;
};
std::vector<MeasureProperty> measure_properties();

}  // namespace mf::measure_theory
