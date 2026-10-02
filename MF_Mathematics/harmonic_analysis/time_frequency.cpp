// time_frequency.cpp — 时频分析内核。

#include "time_frequency.h"

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
using detail::fft;
using detail::kPi;

namespace {

// 一维离散卷积(mode="same",实信号)。
std::vector<double> conv_same_d(const std::vector<double>& a,
                                const std::vector<double>& k) {
    const int n = static_cast<int>(a.size());
    const int kn = static_cast<int>(k.size());
    std::vector<double> out(n, 0.0);
    for (int i = 0; i < n; ++i) {
        double acc = 0.0;
        for (int j = 0; j < kn; ++j) {
            const int idx = i - (kn / 2) + j;
            if (idx >= 0 && idx < n) acc += a[idx] * k[j];
        }
        out[i] = acc;
    }
    return out;
}

}  // namespace

UncertaintyResult uncertainty_principle(const std::string& f, double x_lo,
                                        double x_hi, int n_points) {
    // 旧写法 `int n = 1; while (n < n_points) n <<= 1;` 在 n_points 很大时会
    // 有符号溢出 → 死循环（详见 ha_internal.h 的 fft_grid_size）。
    const long long n = detail::fft_grid_size(n_points);
    const double dx = (x_hi - x_lo) / (double)n;
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(f);

    std::vector<double> psi((std::size_t)n);
    double norm2 = 0.0;
    for (long long i = 0; i < n; ++i) {
        const double t = x_lo + (double)i * dx;
        const double v = std::abs(eval_double_expr(e, x, t));
        psi[(std::size_t)i] = v;
        norm2 += v * v * dx;
    }
    if (norm2 < 1e-15) throw std::runtime_error("函数范数过小,无法归一化");
    for (auto& v : psi) v /= std::sqrt(norm2);

    // Δx。
    double x_mean = 0.0, dx2 = 0.0;
    for (long long i = 0; i < n; ++i) {
        const double t = x_lo + (double)i * dx;
        x_mean += t * psi[(std::size_t)i] * psi[(std::size_t)i] * dx;
    }
    for (long long i = 0; i < n; ++i) {
        const double t = x_lo + (double)i * dx;
        dx2 += (t - x_mean) * (t - x_mean) * psi[(std::size_t)i] * psi[(std::size_t)i] * dx;
    }
    const double delta_x = std::sqrt(std::max(dx2, 0.0));

    // FFT → 频域。
    std::vector<std::complex<double>> work(n);
    for (int i = 0; i < n; ++i) work[i] = psi[i];
    detail::fft(work, false);
    const double dxi = 2.0 * kPi / (n * dx);
    double xi_norm = 0.0;
    for (int j = 0; j < n; ++j) xi_norm += std::norm(work[j]) * dxi;
    if (xi_norm < 1e-15) xi_norm = 1.0;
    double xi_mean = 0.0, dxi2 = 0.0;
    for (int j = 0; j < n; ++j) {
        const double xi_j = (j < n / 2 ? j : j - n) * dxi;
        const double pw = std::norm(work[j]) / xi_norm;
        xi_mean += xi_j * pw * dxi;
    }
    for (int j = 0; j < n; ++j) {
        const double xi_j = (j < n / 2 ? j : j - n) * dxi;
        const double pw = std::norm(work[j]) / xi_norm;
        dxi2 += (xi_j - xi_mean) * (xi_j - xi_mean) * pw * dxi;
    }
    // Δξ: 上面的网格 xi_j 是**角频率**(步长 dxi = 2π/(n·dx)), 而引擎公布的下界
    // 1/(4π) 是普通频率 ξ=ω/2π 下的海森堡界。两者必须同约定:
    //     Δξ = Δω/(2π)。
    // 旧实现写成 Δω/√(2π), 把 Δξ 放大 √(2π)=2.5066 倍, 于是
    // product = √(2π)·ΔxΔξ ≥ √(2π)/(4π) > lower_bound 恒成立 —— 判据完全没有
    // 判别力(exp(-x²) 之外的任何函数都会被判成 satisfied)。
    const double delta_xi = std::sqrt(std::max(dxi2, 0.0)) / (2.0 * kPi);

    UncertaintyResult r;
    r.delta_x = delta_x;
    r.delta_xi = delta_xi;
    r.product = delta_x * delta_xi;
    r.lower_bound = 1.0 / (4.0 * kPi);
    r.satisfied = r.product >= r.lower_bound - 1e-6;
    return r;
}

StftResult stft(const std::vector<double>& signal, int window_size, int hop_size,
                double sample_rate) {
    const int n = static_cast<int>(signal.size());
    // ⚠ window_size = 1 时必须先挡掉：汉宁窗要除以 (window_size-1)，
    //   而且 hop_size 缺省取 window_size/2 = 0，随后 `(n - window_size) / hop_size`
    //   是**整数除零** —— x86 会抛 #DE，MSVC 的 catch(...) 抓不到结构化异常，
    //   表现是整个宿主进程直接死掉（不是一次可恢复的调用失败）。
    if (window_size < 2)
        throw std::invalid_argument(
            "窗口长度至少为 2：汉宁窗需要 window_size-1 作分母，且缺省步长是 window_size/2。");
    if (hop_size <= 0) hop_size = window_size / 2;
    if (hop_size < 1) hop_size = 1;                 // 防御：任何路径都不允许步长为 0
    if (window_size > n)
        throw std::invalid_argument("信号太短:长度小于窗口");
    // 汉宁窗。
    std::vector<double> window(window_size);
    for (int i = 0; i < window_size; ++i)
        window[i] = 0.5 * (1.0 - std::cos(2.0 * kPi * i / (window_size - 1)));

    // FFT 为 radix-2:窗口零填充对齐到 2 的幂。
    long long fft_size = window_size;
    while ((fft_size & (fft_size - 1)) != 0) ++fft_size;
    if (fft_size > detail::kMaxFftPoints)
        throw std::invalid_argument("窗口长度过大：零填充到 2 的幂后超过上限。请减小窗口。");

    const int n_frames = 1 + (n - window_size) / hop_size;
    const int n_freq = static_cast<int>(fft_size) / 2 + 1;

    StftResult r;
    r.spectrogram_magnitude.assign(n_freq, std::vector<double>(n_frames, 0.0));
    for (int fr = 0; fr < n_frames; ++fr) {
        const int start = fr * hop_size;
        std::vector<std::complex<double>> seg((std::size_t)fft_size, {0.0, 0.0});
        for (int i = 0; i < window_size; ++i)
            seg[i] = signal[start + i] * window[i];
        detail::fft(seg, false);
        for (int k = 0; k < n_freq; ++k)
            r.spectrogram_magnitude[k][fr] = std::abs(seg[k]);
    }
    for (int fr = 0; fr < n_frames; ++fr)
        r.times.push_back(fr * hop_size / sample_rate);
    for (int k = 0; k < n_freq; ++k)
        r.frequencies.push_back(k * sample_rate / (double)fft_size);
    return r;
}

WaveletResult wavelet_transform(const std::vector<double>& signal,
                                const std::string& wavelet_type,
                                const std::vector<double>& scales) {
    const int n = static_cast<int>(signal.size());
    const std::vector<double> sc = scales.empty()
                                       ? std::vector<double>{1, 2, 4, 8, 16, 32}
                                       : scales;
    WaveletResult r;
    r.scales = sc;
    r.coefficients.assign(sc.size(), std::vector<double>(n, 0.0));
    for (std::size_t s = 0; s < sc.size(); ++s) {
        const double scale = sc[s];
        int half = static_cast<int>(4.0 * scale);
        if (half > n / 2) half = n / 2;
        if (half < 2) half = 2;
        std::vector<double> psi(2 * half + 1);
        double ps = 0.0;
        for (int i = -half; i <= half; ++i) {
            const double ts = i / scale;
            double val;
            if (wavelet_type == "mexican_hat") {
                val = (1.0 - ts * ts) * std::exp(-ts * ts / 2.0);
            } else if (wavelet_type == "morlet") {
                const double omega0 = 5.0;
                const std::complex<double> c =
                    std::pow(kPi, -0.25) *
                    std::exp(std::complex<double>(0, omega0 * ts)) *
                    std::exp(-ts * ts / 2.0);
                val = c.real();
            } else {
                throw std::invalid_argument("不支持的小波类型");
            }
            psi[i + half] = val;
            ps += val * val;
        }
        if (ps > 0) for (auto& v : psi) v /= std::sqrt(ps);
        r.coefficients[s] = conv_same_d(signal, psi);
    }
    return r;
}

}  // namespace mf::harmonic_analysis
