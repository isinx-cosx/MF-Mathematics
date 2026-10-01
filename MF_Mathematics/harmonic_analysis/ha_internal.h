// ha_internal.h — harmonic_analysis 包共享辅助(仅头文件)。
//
// 提供:表达式复数值求值、复/实辛普森、蝶形 FFT、伽马函数。
// 替换 Python 的 scipy/numpy 数值部分。

#pragma once

#include <algorithm>
#include <cmath>
#include <complex>
#include <functional>
#include <stdexcept>
#include <vector>

#include <symengine/basic.h>
#include <symengine/parser.h>
#include <symengine/symbol.h>
#include <symengine/subs.h>
#include <symengine/real_double.h>
#include <symengine/eval_double.h>

namespace mf::harmonic_analysis::detail {

inline constexpr double kPi = 3.14159265358979323846;

// 表达式在实数点 t 处的值(纯实数表达式)。
inline double eval_double_expr(
    const SymEngine::RCP<const SymEngine::Basic>& e,
    const SymEngine::RCP<const SymEngine::Symbol>& x, double t) {
    const auto sub = e->subs({{x, SymEngine::real_double(t)}});
    return SymEngine::eval_double(*sub);
}

// 实值回调。
inline std::function<double(double)> real_fv(
    const SymEngine::RCP<const SymEngine::Basic>& e,
    const SymEngine::RCP<const SymEngine::Symbol>& x) {
    return [e, x](double t) { return eval_double_expr(e, x, t); };
}

// 复辛普森(被积函数可为复值)。
inline std::complex<double> simpson_c(
    const std::function<std::complex<double>(double)>& f, double a, double b,
    int n = 1000) {
    if (n % 2 != 0) ++n;
    const double h = (b - a) / n;
    std::complex<double> s = f(a) + f(b);
    for (int i = 1; i < n; ++i) {
        const double x = a + i * h;
        s += (i % 2 == 1) ? 4.0 * f(x) : 2.0 * f(x);
    }
    return s * (h / 3.0);
}

// 实辛普森。
inline double simpson(const std::function<double(double)>& f, double a, double b,
                      int n = 1000) {
    if (n % 2 != 0) ++n;
    const double h = (b - a) / n;
    double s = f(a) + f(b);
    for (int i = 1; i < n; ++i) {
        const double x = a + i * h;
        s += (i % 2 == 1) ? 4.0 * f(x) : 2.0 * f(x);
    }
    return s * h / 3.0;
}

// 复积分 ∫_a^b f(x)·e^{-i·k·x} dx = ∫f·cos(kx) dx − i·∫f·sin(kx) dx。
// 拆实虚部,避免 eval_complex 在无 MPC 构建上的限制。
inline std::complex<double> complex_exp_integral(
    const SymEngine::RCP<const SymEngine::Basic>& e,
    const SymEngine::RCP<const SymEngine::Symbol>& x, double k, double a, double b,
    int n = 2000) {
    const auto cos_part = SymEngine::mul(
        e, SymEngine::cos(SymEngine::mul(SymEngine::real_double(k), x)));
    const auto sin_part = SymEngine::mul(
        e, SymEngine::sin(SymEngine::mul(SymEngine::real_double(k), x)));
    const double re = simpson(real_fv(cos_part, x), a, b, n);
    const double im = -simpson(real_fv(sin_part, x), a, b, n);
    return {re, im};
}

// 蝶形 FFT(原位,radix-2,N 须为 2 的幂;invert=true 为逆变换)。
inline void fft(std::vector<std::complex<double>>& a, bool invert) {
    const int n = static_cast<int>(a.size());
    for (int i = 1, j = 0; i < n; ++i) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) std::swap(a[i], a[j]);
    }
    for (int len = 2; len <= n; len <<= 1) {
        const double ang = 2.0 * kPi / len * (invert ? -1 : 1);
        const std::complex<double> wlen(std::cos(ang), std::sin(ang));
        for (int i = 0; i < n; i += len) {
            std::complex<double> w(1.0);
            for (int j = 0; j < len / 2; ++j) {
                const std::complex<double> u = a[i + j];
                const std::complex<double> v = a[i + j + len / 2] * w;
                a[i + j] = u + v;
                a[i + j + len / 2] = u - v;
                w *= wlen;
            }
        }
    }
    if (invert)
        for (auto& x : a) x /= static_cast<double>(n);
}

// 伽马函数(Lanczos 近似)。
inline double gamma_fun(double x) {
    static const double p[9] = {
        0.99999999999980993, 676.5203681218851,   -1259.1392167224028,
        771.32342877765313,  -176.61502916214059, 12.507343278686905,
        -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7};
    if (x <= 0.0 && std::abs(x - std::round(x)) < 1e-9)
        throw std::invalid_argument("Γ 在非正整数处有极点");
    if (x < 0.5)
        return kPi / (std::sin(kPi * x) * gamma_fun(1.0 - x));
    x -= 1.0;
    double a = p[0];
    const double t = x + 7.0 + 0.5;
    for (int i = 1; i < 9; ++i) a += p[i] / (x + i);
    return std::sqrt(2.0 * kPi) * std::pow(t, x + 0.5) * std::exp(-t) * a;
}

// 把一维数组元素取绝对值并转为嵌套列表(JSON 用)。
inline std::vector<std::vector<double>> abs2d(
    const std::vector<std::complex<double>>& v, int rows, int cols) {
    std::vector<std::vector<double>> out;
    for (int i = 0; i < rows; ++i) {
        std::vector<double> row;
        for (int j = 0; j < cols; ++j)
            row.push_back(std::abs(v[i * cols + j]));
        out.push_back(std::move(row));
    }
    return out;
}

}  // namespace mf::harmonic_analysis::detail
