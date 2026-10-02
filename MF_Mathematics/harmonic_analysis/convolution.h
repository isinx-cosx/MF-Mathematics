// convolution.h — 卷积:卷积值、卷积定理、高斯模糊、低通滤波。
#pragma once

#include <string>
#include <vector>


namespace mf::harmonic_analysis {

// 卷积 (f*g)(x) = ∫ f(t)·g(x-t) dt(数值截断)。
double convolution(const std::string& f, const std::string& g, double x_val,
                          double t_lo, double t_hi);

// 卷积定理:F[f*g] ≈ F[f]·F[g](FFT 数值验证)。
struct ConvolutionTheoremResult {
    double max_absolute_error = 0.0;
    double max_relative_error = 0.0;
    bool consistent = false;
};
ConvolutionTheoremResult convolution_theorem(const std::string& f,
                                                    const std::string& g,
                                                    double x_lo, double x_hi,
                                                    int n_points);

// 高斯模糊(高斯核离散卷积)。
std::vector<double> gaussian_blur(const std::vector<double>& signal,
                                         double sigma);

// 低通滤波(FFT 截断高频)。
struct LowPassResult {
    std::vector<double> filtered;
    double energy_ratio = 0.0;
};
LowPassResult low_pass_filter(const std::vector<double>& signal,
                                     double cutoff, double sample_rate);

}  // namespace mf::harmonic_analysis
