// test_harmonic_analysis.cpp — harmonic_analysis 包内核 + JSON 测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "api.h"
#include "json.hpp"
#include "harmonic_analysis/convolution.h"
#include "harmonic_analysis/distributions.h"
#include "harmonic_analysis/fourier_series.h"
#include "harmonic_analysis/fourier_transform.h"
#include "harmonic_analysis/time_frequency.h"
#include "harmonic_analysis/zeta_harmonic.h"

namespace ha = mf::harmonic_analysis;

static const double kTwoPi = 2.0 * 3.141592653589793;

static int g_checks = 0;
static int g_failures = 0;

#define CHECK(cond, msg)                                     \
    do {                                                     \
        ++g_checks;                                          \
        if (!(cond)) {                                       \
            ++g_failures;                                    \
            std::printf("[FAIL] %s\n", msg);                 \
        }                                                    \
    } while (0)

static bool near(double a, double b, double tol) { return std::abs(a - b) <= tol; }

// ── fourier_series ───────────────────────────────────────────────────────────

static void test_fourier_series() {
    const ha::FourierCoeffResult a0 = ha::fourier_coeff("1", 0, kTwoPi, "cos");
    CHECK(near(a0.value, 1.0, 1e-6), "常数函数 a_0 = 1");

    const ha::FourierCoeffResult b1 = ha::fourier_coeff("sin(x)", 1, kTwoPi, "sin");
    CHECK(near(b1.value, 1.0, 1e-6), "sin(x) 的 b_1 = 1");

    const ha::FourierCoeffResult a1 = ha::fourier_coeff("cos(x)", 1, kTwoPi, "cos");
    CHECK(near(a1.value, 1.0, 1e-6), "cos(x) 的 a_1 = 1");

    const ha::FourierCoeffResult b0 = ha::fourier_coeff("sin(x)", 0, kTwoPi, "sin");
    CHECK(near(b0.value, 0.0, 1e-9), "b_0 ≡ 0");

    const ha::ComplexCoeffResult c1 =
        ha::complex_fourier_coeff("cos(x)", 1, kTwoPi);
    CHECK(near(c1.value.real(), 0.5, 1e-6) && near(c1.value.imag(), 0.0, 1e-6),
          "cos(x) 的复系数 c_1 = 1/2");

    const ha::OrthogonalityResult ort = ha::orthogonality_check(1, 2, kTwoPi);
    CHECK(near(std::abs(ort.integral), 0.0, 1e-6) && ort.orthogonal,
          "n≠m 正交,内积 ≈ 0");

    const ha::FourierSeriesResult fs = ha::fourier_series("sin(x)", 3, kTwoPi);
    CHECK(!fs.expression.empty(), "fourier_series 生成级数表达式");
    CHECK(fs.coeffs.size() >= 6, "fourier_series 系数 ≥ 6 个");
}

// ── fourier_transform ────────────────────────────────────────────────────────

static void test_fourier_transform() {
    const std::string g = ha::ft_of_gaussian(3.141592653589793);
    CHECK(!g.empty() && g.find("exp") != std::string::npos,
          "ft_of_gaussian 公式含 exp");

    const ha::FourierTransformResult ft =
        ha::fourier_transform("exp(-x**2)", true, 1.0, true);
    CHECK(ft.numeric && std::isfinite(ft.value.real()),
          "fourier_transform 数值点可算");

    const ha::FourierTransformResult fts =
        ha::fourier_transform("exp(-x**2)", false, 0.0, true);
    CHECK(!fts.numeric && fts.expression.find("exp") != std::string::npos,
          "fourier_transform 高斯 → 符号公式");

    const ha::PlancherelResult pl = ha::plancherel_theorem(
        "exp(-x**2/2)", -5.0, 5.0, 512);
    CHECK(pl.consistent, "普兰舍利定理:‖f‖₂ ≈ ‖F‖₂");
}

// ── convolution ──────────────────────────────────────────────────────────────

static void test_convolution() {
    const double conv = ha::convolution("exp(-x**2)", "exp(-x**2)", 0.0, -5.0, 5.0);
    CHECK(conv > 1e-3, "高斯自卷积在 0 处非零");

    const ha::ConvolutionTheoremResult ct =
        ha::convolution_theorem("exp(-x**2)", "exp(-x**2)", -5.0, 5.0, 256);
    CHECK(ct.consistent, "卷积定理成立(FFT)");

    const std::vector<double> blur =
        ha::gaussian_blur({1, 2, 3, 2, 1}, 0.5);
    CHECK(blur.size() == 5, "高斯模糊输出同长度");

    const ha::LowPassResult lp =
        ha::low_pass_filter({0, 1, 0, -1, 0, 1, 0, -1}, 0.2, 1.0);
    CHECK(lp.filtered.size() == 8, "低通滤波输出同长度");
}

// ── distributions ────────────────────────────────────────────────────────────

static void test_distributions() {
    CHECK(near(ha::delta_distribution("x**2 + 1", 3.0), 10.0, 1e-8),
          "δ 筛选性质:φ(3) = 10");
    CHECK(ha::ft_delta() == "1", "F[δ] = 1");
    CHECK(ha::ft_constant().find("delta") != std::string::npos, "F[1] 含 δ");

    const ha::TemperedResult t = ha::tempered_distribution("exp(-x**2)", 10.0);
    CHECK(t.is_tempered, "exp(-x²) 是缓增分布");
}

// ── time_frequency ───────────────────────────────────────────────────────────

static void test_time_frequency() {
    const ha::UncertaintyResult uc =
        ha::uncertainty_principle("exp(-x**2)", -20.0, 20.0, 2048);
    CHECK(uc.satisfied, "不确定性原理成立(高斯)");

    // chirp 信号。
    std::vector<double> chirp;
    for (int i = 0; i < 1000; ++i) {
        const double t = i * 10.0 / 999.0;
        chirp.push_back(std::sin(2 * 3.141592653589793 * (1 + t) * t));
    }
    const ha::StftResult st = ha::stft(chirp, 64, 32, 1.0);
    CHECK(st.spectrogram_magnitude.size() > 0 &&
              !st.spectrogram_magnitude[0].empty(),
          "STFT 时频谱图非空");

    const ha::WaveletResult wv =
        ha::wavelet_transform({0, 1, 0, -1, 0, 1, 0}, "mexican_hat", {});
    CHECK(wv.coefficients.size() == 6, "小波变换 6 个尺度");
}

// ── zeta_harmonic ───────────────────────────────────────────────────────────

static void test_zeta_harmonic() {
    const ha::PoissonResult ps =
        ha::poisson_summation("exp(-3.141592653589793*x**2)", 1.0, 30);
    CHECK(ps.consistent, "泊松求和公式成立");

    const ha::ThetaResult th = ha::theta_function(1.0, 100);
    CHECK(th.modular_check < 1e-6, "θ 函数模变换误差小");

    const ha::FunctionalEquationResult fe = ha::functional_equation_demo(2.0);
    CHECK(fe.relative_difference < 1e-3, "ζ 函数方程成立");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[8192];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("fourier_coeff"), "function_exists(fourier_coeff)");
    CHECK(function_exists("fourier_transform"), "function_exists(fourier_transform)");
    CHECK(function_exists("gaussian_blur"), "function_exists(gaussian_blur)");
    CHECK(function_exists("theta_function"), "function_exists(theta_function)");

    const std::string fc = call("fourier_coeff",
        "{\"f\":\"sin(x)\",\"n\":1,\"period\":6.283185307179586,\"coeff_type\":\"sin\"}");
    const mf::json::Value fcv = mf::json::Value::parse(fc);
    CHECK(near(fcv["value"]["value"].as_double(), 1.0, 1e-6),
          "math_call fourier_coeff(sin, b_1) ≈ 1");

    const std::string fg = call("ft_of_gaussian", "{\"a\":3.141592653589793}");
    CHECK(fg.find("\"isError\":false") != std::string::npos,
          "math_call ft_of_gaussian");

    const std::string d = call("delta_distribution", "{\"phi\":\"x**2 + 1\",\"x0\":3}");
    const mf::json::Value dv = mf::json::Value::parse(d);
    CHECK(near(dv["value"].as_double(), 10.0, 1e-8),
          "math_call delta_distribution ≈ 10");

    const std::string th = call("theta_function", "{\"t\":1,\"n_terms\":100}");
    CHECK(th.find("\"isError\":false") != std::string::npos,
          "math_call theta_function");
}

int main() {
    std::system("chcp 65001 > nul");
    std::printf("===== harmonic_analysis 内核测试 =====\n");
    test_fourier_series();
    test_fourier_transform();
    test_convolution();
    test_distributions();
    test_time_frequency();
    test_zeta_harmonic();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
