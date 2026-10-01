// time_frequency.h — 时频分析:不确定性原理、STFT、小波变换。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::harmonic_analysis {

// 海森堡不确定性原理:Δx·Δξ ≥ 1/(4π)(FFT 数值)。
struct UncertaintyResult {
    double delta_x = 0.0;
    double delta_xi = 0.0;
    double product = 0.0;
    double lower_bound = 0.0;
    bool satisfied = false;
};
MF_API UncertaintyResult uncertainty_principle(const std::string& f, double x_lo,
                                               double x_hi, int n_points);

// 短时傅里叶变换(STFT)时频谱图。
struct StftResult {
    std::vector<std::vector<double>> spectrogram_magnitude;  // n_freq × n_frames
    std::vector<double> times;
    std::vector<double> frequencies;
};
MF_API StftResult stft(const std::vector<double>& signal, int window_size,
                       int hop_size, double sample_rate);

// 连续小波变换(mexican_hat / morlet)。
struct WaveletResult {
    std::vector<std::vector<double>> coefficients;  // n_scales × n
    std::vector<double> scales;
};
MF_API WaveletResult wavelet_transform(const std::vector<double>& signal,
                                       const std::string& wavelet_type,
                                       const std::vector<double>& scales);

}  // namespace mf::harmonic_analysis
