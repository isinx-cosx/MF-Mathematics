// holomorphic.h — 全纯函数:C-R 方程、调和函数。
#pragma once

#include <complex>
#include <string>

#include "../mf_export.h"

namespace mf::complex_analysis {

// 在一点检查全纯(数值 C-R 方程)。
MF_API bool is_holomorphic(const std::string& func, std::complex<double> z);

// 显式验证 C-R 方程组:u_x = v_y 且 u_y = -v_x。
struct CauchyRiemannResult {
    bool cr1 = false;  // u_x = v_y
    bool cr2 = false;  // u_y = -v_x
    bool both = false;
    std::string u_x;
    std::string u_y;
    std::string v_x;
    std::string v_y;
};
MF_API CauchyRiemannResult cauchy_riemann(const std::string& u,
                                          const std::string& v);

// 调和函数判定:Δu = u_xx + u_yy = 0。
MF_API bool is_harmonic(const std::string& func);

}  // namespace mf::complex_analysis
