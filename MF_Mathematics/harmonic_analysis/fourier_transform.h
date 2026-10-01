// fourier_transform.h — 傅里叶变换:变换、逆变换、普兰舍利、高斯变换。
#pragma once

#include <complex>
#include <string>

#include "../mf_export.h"

namespace mf::harmonic_analysis {

// 傅里叶变换。numeric_xi=true 时 xi 为数值,返回复值;否则返回表达式。
//
// reliable / estimated_error / truncation_radius 只对数值分支有意义: 数值积分
// (截断半径自适应 + 振荡分辨 + 渐近尾校正)会实测误差, 收敛不到容差时
// reliable=false 并给出 warning —— 分发层只在"不可信"时把这些字段暴露给调用方
// (可信时仍返回 [re, im], 保持向后兼容), 免得慢衰减/高频函数被静默算成错值。
struct FourierTransformResult {
    bool numeric = false;
    std::complex<double> value;
    std::string expression;
    bool reliable = true;
    double estimated_error = 0.0;
    double truncation_radius = 0.0;
    int tail_terms = 0;
    std::string warning;
};
MF_API FourierTransformResult fourier_transform(const std::string& f, bool numeric_xi,
                                                double xi, bool use_angular);

// 逆傅里叶变换。
MF_API FourierTransformResult inverse_fourier_transform(const std::string& F,
                                                        bool numeric_x, double x,
                                                        bool use_angular);

// 普兰舍利定理:比较时域与频域 L² 范数(FFT 数值)。
struct PlancherelResult {
    double l2_time = 0.0;
    double l2_freq = 0.0;
    double relative_difference = 0.0;
    bool consistent = false;
};
MF_API PlancherelResult plancherel_theorem(const std::string& f, double x_lo,
                                           double x_hi, int n_points);

// 高斯 e^{-ax²} 的傅里叶变换公式 √(π/a)·e^{-ξ²/(4a)}。
MF_API std::string ft_of_gaussian(double a);

}  // namespace mf::harmonic_analysis
