// residue.h — 留数、留数定理、实积分、辐角原理、鲁歇定理。
#pragma once

#include <complex>
#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::complex_analysis {

// 留数(极点公式)。
MF_API std::complex<double> residue(const std::string& func,
                                    std::complex<double> z0);

// 留数定理:∮ f dz = 2πi Σ Res(内部奇点)。
MF_API std::complex<double> residue_theorem(const std::string& func,
                                            const std::vector<std::complex<double>>& singularities);

// 实积分:全实轴有理函数用上半平面围道积分;有限区间数值积分。
MF_API double real_integral(const std::string& func, double a, double b);

// 辐角原理:Z - P = 1/(2πi) ∮ f'/f dz(数值)。
MF_API long long argument_principle(const std::string& func,
                                    std::complex<double> center, double radius);

// 鲁歇定理:若 |g| < |f| 在 γ 上,则 f 与 f+g 零点数相同。
struct RoucheResult {
    bool condition_holds = false;
    double max_ratio = 0.0;
    long long zeros_f = 0;
    long long zeros_fg = 0;
};
MF_API RoucheResult rouche_theorem(const std::string& f, const std::string& g,
                                   std::complex<double> center, double radius);

}  // namespace mf::complex_analysis
