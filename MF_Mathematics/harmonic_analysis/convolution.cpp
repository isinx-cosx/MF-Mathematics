// convolution.cpp — 卷积内核。

#include "convolution.h"

#include <algorithm>
#include <cmath>
#include <complex>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/parser.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include "ha_internal.h"

namespace mf::harmonic_analysis {

using detail::eval_double_expr;
using detail::simpson;
using detail::simpson_c;
using detail::fft;

namespace {

using SymEngine::RCP;
using SymEngine::Basic;
using SymEngine::Symbol;

}  // namespace

double convolution(const std::string& f, const std::string& g, double x_val,
                   double t_lo, double t_hi) {
    const auto x = SymEngine::symbol("x");
    const auto t = SymEngine::symbol("t");
    // f(x) → f(t), g(x) → g(x_val - t),对 t 积分。
    const auto e_f = SymEngine::parse(f)->subs({{x, t}});
    const auto e_g = SymEngine::parse(g)->subs(
        {{x, SymEngine::sub(SymEngine::real_double(x_val), t)}});
    const auto integrand = SymEngine::mul(e_f, e_g);
    return simpson(detail::real_fv(integrand, t), t_lo, t_hi, 2000);
}

ConvolutionTheoremResult convolution_theorem(const std::string& f,
                                             const std::string& g, double x_lo,
                                             double x_hi, int n_points) {
    int n = 1;
    while (n < n_points) n <<= 1;
    const double dx = (x_hi - x_lo) / n;
    const auto x = SymEngine::symbol("x");
    const auto e_f = SymEngine::parse(f);
    const auto e_g = SymEngine::parse(g);

    std::vector<std::complex<double>> fs(n), gs(n);
    for (int i = 0; i < n; ++i) {
        const double t = x_lo + i * dx;
        fs[i] = eval_double_expr(e_f, x, t);
        gs[i] = eval_double_expr(e_g, x, t);
    }

    // 路径1:时域圆卷积 → FFT。DFT 恒等式 F[conv] = F[f]·F[g] 对圆卷积精确成立。
    std::vector<std::complex<double>> conv(n, 0.0);
    for (int j = 0; j < n; ++j) {
        std::complex<double> acc = 0.0;
        for (int k = 0; k < n; ++k)
            acc += fs[k] * gs[(j - k + n) % n];
        conv[j] = acc;
    }
    std::vector<std::complex<double>> F_conv = conv;
    detail::fft(F_conv, false);

    // 路径2:FFT → 频域乘积。
    std::vector<std::complex<double>> F_f = fs, F_g = gs;
    detail::fft(F_f, false);
    detail::fft(F_g, false);

    double max_err = 0.0;
    for (int i = 0; i < n; ++i) {
        const auto diff = F_conv[i] - F_f[i] * F_g[i];
        max_err = std::max(max_err, std::abs(diff));
    }
    double ref = 0.0;
    for (int i = 0; i < n; ++i) ref = std::max(ref, std::abs(F_conv[i]));

    ConvolutionTheoremResult r;
    r.max_absolute_error = max_err;
    r.max_relative_error = max_err / std::max(ref, 1e-12);
    r.consistent = r.max_relative_error < 0.01;
    return r;
}

std::vector<double> gaussian_blur(const std::vector<double>& signal, double sigma) {
    if (sigma <= 0) throw std::invalid_argument("sigma 必须为正");
    const int n = static_cast<int>(signal.size());
    const int kernel_size = static_cast<int>(2 * std::ceil(3 * sigma)) + 1;
    const int half = kernel_size / 2;
    std::vector<double> kernel(kernel_size);
    double ksum = 0.0;
    for (int i = -half; i <= half; ++i) {
        const double val = std::exp(-(i * i) / (2.0 * sigma * sigma));
        kernel[i + half] = val;
        ksum += val;
    }
    for (auto& v : kernel) v /= ksum;

    std::vector<double> out(n);
    for (int i = 0; i < n; ++i) {
        double acc = 0.0;
        for (int j = 0; j < kernel_size; ++j) {
            const int idx = i - half + j;
            if (idx >= 0 && idx < n) acc += signal[idx] * kernel[j];
        }
        out[i] = acc;
    }
    return out;
}

LowPassResult low_pass_filter(const std::vector<double>& signal, double cutoff,
                              double sample_rate) {
    if (cutoff <= 0) throw std::invalid_argument("cutoff 必须为正");
    const int n = static_cast<int>(signal.size());
    int sz = 1;
    while (sz < n) sz <<= 1;
    std::vector<std::complex<double>> data(sz, 0.0);
    for (int i = 0; i < n; ++i) data[i] = signal[i];
    detail::fft(data, false);

    // 频率网格。
    const double d = 1.0 / sample_rate;
    for (int j = 0; j < sz; ++j) {
        const double freq = (j < sz / 2 ? j : j - sz) / (sz * d);
        if (std::abs(freq) > cutoff) data[j] = 0.0;
    }
    detail::fft(data, true);

    LowPassResult r;
    r.filtered.resize(n);
    double e_orig = 0.0, e_filt = 0.0;
    for (int i = 0; i < n; ++i) {
        r.filtered[i] = std::real(data[i]);
        e_orig += signal[i] * signal[i];
        e_filt += r.filtered[i] * r.filtered[i];
    }
    r.energy_ratio = e_filt / std::max(e_orig, 1e-12);
    return r;
}

}  // namespace mf::harmonic_analysis
