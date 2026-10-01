// test_complex_analysis.cpp — complex_analysis 包内核 + JSON 测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言。

#include <cmath>
#include <complex>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "api.h"
#include "json.hpp"
#include "complex_analysis/complex_integral.h"
#include "complex_analysis/complex_topology.h"
#include "complex_analysis/conformal.h"
#include "complex_analysis/holomorphic.h"
#include "complex_analysis/series.h"
#include "complex_analysis/elementary_funcs.h"
#include "complex_analysis/zeta.h"
#include "complex_analysis/residue.h"

namespace ca = mf::complex_analysis;

static const double kPi = 3.141592653589793;
static const std::complex<double> kI(0.0, 1.0);

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

// ── complex_integral ─────────────────────────────────────────────────────────

static void test_complex_integral() {
    // 柯西定理:f=1 沿单位圆 → 0。
    const ca::CauchyTheoremResult ct = ca::cauchy_theorem("1", {0, 0}, 1.0);
    CHECK(ct.zero, "柯西定理: ∮1 dz = 0");

    // ∫_{|z|=1} 1/z dz = 2πi。
    const std::complex<double> ci = ca::contour_integral_circle("1/z", {0, 0}, 1.0, 0.0, 2 * kPi, 2000);
    CHECK(std::abs(ci - 2.0 * kPi * kI) < 0.1, "∮ 1/z dz = 2πi");

    // 柯西积分公式:sin(z) 在 0 → 0。
    const ca::CauchyFormulaResult cf = ca::cauchy_integral_formula("sin(z)", {0, 0}, {0, 0}, 1.0);
    CHECK(cf.error < 0.01, "柯西积分公式: f(0)=0 误差 < 0.01");

    // 高阶导公式:z³ 在 0, n=2 → f''(0)=0。
    const ca::DerivativeFormulaResult df = ca::derivative_formula("z**3", {0, 0}, 2, {0, 0}, 1.0);
    CHECK(std::abs(df.symbolic) < 1e-10, "高阶导公式: f''(0)=0");
}

// ── complex_topology ─────────────────────────────────────────────────────────

static void test_complex_topology() {
    // 单位圆盘离散采样。
    std::vector<std::pair<double, double>> disk;
    for (int ri = 0; ri < 20; ++ri) {
        const double r = ri / 19.0 * 0.95;
        const int n_th = r <= 0 ? 1 : 30;
        for (int ti = 0; ti < n_th; ++ti) {
            const double th = 2 * kPi * ti / n_th;
            disk.emplace_back(r * std::cos(th), r * std::sin(th));
        }
    }
    CHECK(ca::is_open(disk, 0.0, 0.0, 0.05), "is_open: 原点为内点");
    CHECK(ca::is_connected(disk, 0.2), "is_connected: 圆盘连通");
    CHECK(ca::is_domain(disk, 0.03, 0.2), "is_domain: 圆盘是区域");

    // 两个分离的团不连通。
    std::vector<std::pair<double, double>> clusters;
    for (int i = 0; i < 10; ++i) clusters.emplace_back(i * 0.1, 0.0);
    for (int i = 0; i < 10; ++i) clusters.emplace_back(i * 0.1, 5.0);
    CHECK(!ca::is_connected(clusters, 0.2), "is_connected: 分离团不连通");
    CHECK(!ca::is_domain(clusters, 0.03, 0.2), "is_domain: 分离团不是区域");
}

// ── conformal ────────────────────────────────────────────────────────────────

static void test_conformal() {
    CHECK(ca::is_conformal("z**2", {1, 0}).is_conformal, "is_conformal(z², 1)");
    CHECK(!ca::is_conformal("z**2", {0, 0}).is_conformal, "is_conformal(z², 0) 临界点");
    CHECK(ca::is_conformal("exp(z)", {0, 0}).is_conformal, "is_conformal(e^z, 0)");

    const std::string rm = ca::riemann_mapping("upper_half_plane");
    CHECK(rm.find("Cayley") != std::string::npos, "riemann_mapping: Cayley 变换");

    const auto bc = ca::boundary_correspondence("(z - I)/(z + I)", "unit");
    CHECK(bc.size() == 16, "boundary_correspondence: 16 个采样点");
}

// ── holomorphic ──────────────────────────────────────────────────────────────

static void test_holomorphic() {
    CHECK(ca::is_holomorphic("sin(z)", {0.3, 0.2}), "is_holomorphic(sin(z))");
    CHECK(!ca::is_holomorphic("conjugate(z)", {0.3, 0.2}), "is_holomorphic(conj(z)) 非全纯");

    const ca::CauchyRiemannResult cr = ca::cauchy_riemann("x**2 - y**2", "2*x*y");
    CHECK(cr.both, "C-R: u=x²-y², v=2xy 满足");

    CHECK(ca::is_harmonic("x**2 - y**2"), "is_harmonic(x²-y²)");
    CHECK(!ca::is_harmonic("x**2 + y**2"), "is_harmonic(x²+y²) 非调和");
    CHECK(ca::is_harmonic("log(x**2 + y**2)"), "is_harmonic(log(x²+y²))");
}

// ── series ───────────────────────────────────────────────────────────────────

static void test_series() {
    const std::string ts = ca::taylor_series("sin(z)", {0, 0}, 5);
    CHECK(ts.find("z**3/6") != std::string::npos || ts.find("-z**3") != std::string::npos,
          "泰勒展开 sin(z): 含 z³/6 项");

    const std::string ls = ca::laurent_series("1/(z-1)", {1, 0}, 3);
    CHECK(!ls.empty(), "洛朗展开 1/(z-1) 非空");

    const ca::SingularityResult s1 = ca::singularity_classify("1/(z-1)", {1, 0});
    CHECK(s1.classification == "pole", "奇点分类: 1/(z-1) 极点");
    const ca::SingularityResult s2 = ca::singularity_classify("sin(z)/z", {0, 0});
    CHECK(s2.classification == "removable" || s2.classification == "regular",
          "奇点分类: sin(z)/z 可去");
    const ca::SingularityResult s3 = ca::singularity_classify("exp(1/z)", {0, 0});
    CHECK(s3.classification == "essential", "奇点分类: e^(1/z) 本性");

    CHECK(ca::pole_order("1/(z-1)**3", {1, 0}) == 3, "极点阶数: 1/(z-1)³ → 3");
}

// ── elementary_funcs ─────────────────────────────────────────────────────────

static void test_elementary_funcs() {
    const std::complex<double> e1 = ca::exp_complex(kI * kPi);
    CHECK(std::abs(e1.real() + 1.0) < 1e-10 && std::abs(e1.imag()) < 1e-10,
          "e^{iπ} = -1");

    const std::complex<double> l1 = ca::log_complex({-1.0, 0.0});
    CHECK(std::abs(l1.real()) < 1e-10 && std::abs(l1.imag() - kPi) < 1e-10,
          "Log(-1) = iπ");

    const std::complex<double> sq = ca::sqrt_complex({-1.0, 0.0});
    CHECK(std::abs(sq.real()) < 1e-10 && std::abs(sq.imag() - 1.0) < 1e-10,
          "√(-1) = i");

    const std::complex<double> m1 = ca::mobius_transform({2.0, 0}, {1, 0}, {0, 0}, {1, 0}, {-1, 0});
    CHECK(std::abs(m1 - 2.0) < 1e-10, "Möbius z/(z-1) at z=2 → 2");
    const std::complex<double> m2 = ca::mobius_transform({0, 1}, {0, 0}, {1, 0}, {1, 0}, {0, 0});
    CHECK(std::abs(m2 + kI) < 1e-10, "Möbius 1/z at z=i → -i");
}

// ── zeta ─────────────────────────────────────────────────────────────────────

static void test_zeta() {
    const std::complex<double> z2 = ca::zeta_series({2.0, 0}, 10000);
    CHECK(std::abs(z2.real() - kPi * kPi / 6) < 0.01, "ζ(2) ≈ π²/6");

    const std::complex<double> zm1 = ca::analytic_continuation_zeta({-1.0, 0});
    CHECK(std::abs(zm1.real() + 1.0 / 12.0) < 1e-6, "ζ(-1) = -1/12");
    const std::complex<double> z0 = ca::analytic_continuation_zeta({0.0, 0});
    CHECK(std::abs(z0.real() + 0.5) < 1e-6, "ζ(0) = -1/2");

    const ca::FunctionalEquationResult fe = ca::functional_equation_zeta({0.5, 0});
    CHECK(fe.verified, "ζ 函数方程在 s=0.5 成立");

    const auto zeros = ca::nontrivial_zeros(5);
    CHECK(zeros.size() == 5, "前 5 个非平凡零点");
}

// ── residue ──────────────────────────────────────────────────────────────────

static void test_residue() {
    const std::complex<double> r1 = ca::residue("1/(z**2+1)", {0, 1});
    CHECK(std::abs(r1 + 0.5 * kI) < 1e-6, "Res(1/(z²+1), i) = 1/(2i)");
    const std::complex<double> r2 = ca::residue("1/(z-1)", {1, 0});
    CHECK(std::abs(r2 - 1.0) < 1e-6, "Res(1/(z-1), 1) = 1");

    const std::complex<double> rt = ca::residue_theorem("1/(z**2+1)", {{0, 1}, {0, -1}});
    CHECK(std::abs(rt) < 1e-8, "留数定理: ∮ 1/(z²+1) = 0");

    const double ri = ca::real_integral("1/(1+x**2)",
                                        -std::numeric_limits<double>::infinity(),
                                        std::numeric_limits<double>::infinity());
    CHECK(std::abs(ri - kPi) < 0.1, "∫ dx/(1+x²) = π");

    CHECK(ca::argument_principle("z**2", {0, 0}, 1.0) == 2, "辐角原理: z² → Z-P=2");

    const ca::RoucheResult rc = ca::rouche_theorem("z**5", "z", {0, 0}, 1.5);
    CHECK(rc.condition_holds, "鲁歇定理: |z| < |z⁵| on |z|=1.5");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[8192];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("cauchy_theorem"), "function_exists(cauchy_theorem)");
    CHECK(function_exists("taylor_series"), "function_exists(taylor_series)");
    CHECK(function_exists("exp_complex"), "function_exists(exp_complex)");

    const std::string ct = call("cauchy_theorem", "{\"func\":\"1\",\"contour\":\"circle(0,1)\"}");
    CHECK(ct.find("\"zero\":true") != std::string::npos, "math_call cauchy_theorem → zero");

    const std::string zs = call("zeta_series", "{\"s\":2,\"n_terms\":10000}");
    const mf::json::Value zsv = mf::json::Value::parse(zs);
    CHECK(std::abs(zsv["value"].at(0).as_double() - kPi * kPi / 6) < 0.01,
          "math_call zeta_series(2) ≈ π²/6");

    const std::string ex = call("exp_complex", "{\"z\":[0,3.141592653589793]}");
    const mf::json::Value exv = mf::json::Value::parse(ex);
    CHECK(std::abs(exv["value"].at(0).as_double() + 1.0) < 1e-8,
          "math_call exp_complex(iπ) ≈ -1");

    const std::string po = call("pole_order", "{\"func\":\"1/(z-1)**3\",\"z0\":1}");
    CHECK(po.find("\"value\":3") != std::string::npos, "math_call pole_order → 3");
}

int main() {
    std::system("chcp 65001 > nul");
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("===== complex_analysis 内核测试 =====\n");
    test_complex_integral();
    test_complex_topology();
    test_conformal();
    test_holomorphic();
    test_series();
    test_elementary_funcs();
    test_zeta();
    test_residue();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
