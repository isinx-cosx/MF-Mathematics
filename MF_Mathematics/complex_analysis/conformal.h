// conformal.h — 共形映射:共形判定、黎曼映射定理、边界对应。
#pragma once

#include <complex>
#include <string>
#include <utility>
#include <vector>


namespace mf::complex_analysis {

// 共形判定:f'(z) ≠ 0。
struct ConformalResult {
    bool is_conformal = false;
    std::complex<double> derivative{0.0, 0.0};
};
ConformalResult is_conformal(const std::string& func,
                                    std::complex<double> z);

// 黎曼映射定理:预定义区域的共形映射描述。
std::string riemann_mapping(const std::string& region);

// 边界对应:采样边界点并映射。
struct BoundarySample {
    std::complex<double> z{0.0, 0.0};
    std::complex<double> w{0.0, 0.0};
};
std::vector<BoundarySample> boundary_correspondence(
    const std::string& func, const std::string& region);

}  // namespace mf::complex_analysis
