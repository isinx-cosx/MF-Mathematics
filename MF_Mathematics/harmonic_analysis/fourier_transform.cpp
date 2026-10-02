// fourier_transform.cpp — 傅里叶变换内核。

#include "fourier_transform.h"

#include <charconv>
#include <cmath>
#include <complex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/functions.h>
#include <symengine/mul.h>
#include <symengine/parser.h>
#include <symengine/pow.h>
#include <symengine/real_double.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>
#include <symengine/visitor.h>

#include "ha_internal.h"
#include "ha_numeric.h"

namespace mf::harmonic_analysis {

using detail::real_fv;
using detail::eval_double_expr;
using detail::complex_exp_integral;
using detail::fft;
using detail::kPi;

namespace {

using SymEngine::RCP;
using SymEngine::Basic;
using SymEngine::Symbol;

// 检测 f = e^{-a·x²}(高斯),返回 a;否则返回 false。
bool gaussian_param(const std::string& f, double& a) {
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(f);
    if (!SymEngine::is_a<SymEngine::Pow>(*e)) return false;
    const auto args = e->get_args();
    if (!SymEngine::eq(*args[0], *SymEngine::E)) return false;
    const auto expo = args[1];
    // 指数 = -a·x²(无 x 一次项、无常数项)
    try {
        const auto c2 = SymEngine::coeff(*expo, *x, *SymEngine::integer(2));
        const auto c1 = SymEngine::coeff(*expo, *x, *SymEngine::integer(1));
        const auto c0 = SymEngine::coeff(*expo, *x, *SymEngine::integer(0));
        const double a2 = SymEngine::eval_double(*c2);
        const double a1 = SymEngine::eval_double(*c1);
        const double a0 = SymEngine::eval_double(*c0);
        if (a1 != 0.0 || a0 != 0.0 || a2 >= 0.0) return false;
        a = -a2;
        return true;
    } catch (...) {
        return false;
    }
}

std::string fmt(double v) {
    if (std::abs(v) < 1e-12) v = 0.0;
    char buf[32];
    const auto res = std::to_chars(buf, buf + sizeof(buf), v,
                                   std::chars_format::general);
    return std::string(buf, res.ptr);
}

// 数值分支的求值预算(被积函数求值次数上限)。LambdaRealDoubleVisitor 下每次
// 求值约 0.05 微秒, 400 万次 ≈ 0.2 秒, 足够覆盖慢衰减 + 高频的组合。
constexpr long long kEvalBudget = 4000000;

// 数值分支: 调 ha_numeric.h 的自适应积分, 并把实测误差如实带回去。
void fill_numeric(FourierTransformResult& r, const std::string& expr,
                  const char* var, double w, double scale_div) {
    const auto x = SymEngine::symbol(var);
    const auto e = SymEngine::parse(expr);
    const detail::NumericFT q =
        detail::numeric_fourier_transform(e, x, w, 1e-12, 0.0, kEvalBudget);
    r.numeric = true;
    r.value = q.value / scale_div;
    r.estimated_error = q.error / std::abs(scale_div);
    r.truncation_radius = q.radius;
    r.tail_terms = q.tail_terms;
    r.reliable = q.reliable;
    if (!q.reliable) {
        std::ostringstream oss;
        oss << "数值积分未能达到精度: 实测误差 " << fmt(q.error)
            << "(截断半径 " << fmt(q.radius) << ", 尾部级数 " << q.tail_terms
            << " 项); 结果不可信 —— 该被积函数在此频率下欠采样, "
               "请改用解析式或较小时延/频率";
        r.warning = oss.str();
    }
}

}  // namespace

FourierTransformResult fourier_transform(const std::string& f, bool numeric_xi,
                                         double xi, bool use_angular) {
    FourierTransformResult r;
    // 高斯符号公式:
    //   角频率(ω 约定):F(ω) = √(π/a)·e^{-ξ²/(4a)}
    //   普通频率(ξ 约定):F(ξ) = √(π/a)·e^{-π²ξ²/a}
    double a;
    if (gaussian_param(f, a)) {
        const double coef = std::sqrt(kPi / a);
        const double ex =
            a > 0 ? (use_angular ? -1.0 / (4.0 * a) : -kPi * kPi / a) : 0.0;
        r.numeric = false;
        if (numeric_xi) {
            r.numeric = true;
            r.value = std::complex<double>(coef * std::exp(ex * xi * xi), 0.0);
        } else {
            std::ostringstream oss;
            oss << "sqrt(pi/" << fmt(a) << ")*exp(" << fmt(ex) << "*xi^2)";
            r.expression = oss.str();
        }
        return r;
    }

    // 一般函数: 自适应数值积分 —— 截断半径由衰减尺度/频率共同决定, 尾部用
    // 分部积分的渐近级数补齐(见 ha_numeric.h), 实测误差随结果一并返回。
    const double w = use_angular ? xi : 2.0 * kPi * xi;
    fill_numeric(r, f, "x", w, 1.0);
    return r;
}

FourierTransformResult inverse_fourier_transform(const std::string& F,
                                                 bool numeric_x, double x,
                                                 bool use_angular) {
    FourierTransformResult r;
    // 逆变换 = ∫F(ξ)e^{+iξx}dξ(角频率约定再除 2π), 即角频率取 -x 的正变换。
    const double w = use_angular ? x : 2.0 * kPi * x;
    fill_numeric(r, F, "xi", -w, use_angular ? 2.0 * kPi : 1.0);
    (void)numeric_x;
    return r;
}

PlancherelResult plancherel_theorem(const std::string& f, double x_lo, double x_hi,
                                    int n_points) {
    // n_points 对齐到 2 的幂。旧写法是同款 int 左移循环，n_points 很大时会溢出成死循环。
    const long long n = detail::fft_grid_size(n_points);
    const double dx = (x_hi - x_lo) / (double)n;
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(f);
    std::vector<std::complex<double>> samples((std::size_t)n);
    double l2_time = 0.0;
    for (long long i = 0; i < n; ++i) {
        const double t = x_lo + (double)i * dx;
        const double v = eval_double_expr(e, x, t);
        samples[(std::size_t)i] = v;
        l2_time += v * v * dx;  // |f|² 梯形和(矩形近似)
    }
    l2_time = std::sqrt(l2_time);

    // FFT:频率形式 F(ξ) ≈ Σ f(x_k)e^{-iξ_j x_k}·dx。
    std::vector<std::complex<double>> work = samples;
    detail::fft(work, false);
    // 频率网格。
    double l2_freq = 0.0;
    for (long long j = 0; j < n; ++j) {
        const double dxi = 2.0 * kPi / ((double)n * dx);
        l2_freq += std::norm(work[(std::size_t)j]) * dx * dx * dxi / (2.0 * kPi);
    }
    l2_freq = std::sqrt(l2_freq);

    PlancherelResult r;
    r.l2_time = l2_time;
    r.l2_freq = l2_freq;
    r.relative_difference =
        std::abs(l2_time - l2_freq) / std::max(std::abs(l2_time), 1e-12);
    r.consistent = r.relative_difference < 0.05;
    return r;
}

std::string ft_of_gaussian(double a) {
    if (a <= 0) throw std::invalid_argument("参数 a 必须为正");
    const double ex = -1.0 / (4.0 * a);
    return "sqrt(pi/" + fmt(a) + ")*exp(" + fmt(ex) + "*xi^2)";
}

}  // namespace mf::harmonic_analysis
