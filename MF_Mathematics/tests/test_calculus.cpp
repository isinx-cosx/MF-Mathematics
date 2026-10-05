// test_calculus.cpp — calculus(derivatives,基于 SymEngine)内核 + JSON 测试。
//
// 期望值取自 Python 版 derivatives self_test() 的断言。

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/derivative.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/symbol.h>

#include "api.h"
#include "json.hpp"
#include "calculus/derivatives.h"
#include "calculus/integrals.h"
#include "calculus/derivatives_app.h"
#include "calculus/integrals_app.h"
#include "calculus/series.h"

namespace calc = mf::calculus;

/**
 * 求导自证：d/dx(∫f dx) 必须回到 f —— 在若干点上数值一致即算通过。
 *
 * 为什么不比字符串：原函数的形式不唯一（∫tan x 写成 −ln cos x 还是 ln sec x 是同一个
 * 东西），比字符串只会误判。求导再数值比对，才是"这条积分规则对不对"的直接判据；
 * 规则写错会当场失败，而不是让用户拿到一个**错误的原函数**。
 */
static bool antideriv_self_checks_out(const std::string& f, const std::string& var,
                                      const std::vector<double>& pts) {
    std::string F = calc::integrate_indefinite(f, var);
    if (F == "未实现") return false;
    const std::string suffix = " + C";
    if (F.size() > suffix.size() &&
        F.compare(F.size() - suffix.size(), suffix.size(), suffix) == 0)
        F.erase(F.size() - suffix.size());
    const auto x = SymEngine::symbol(var);
    const auto D = SymEngine::diff(SymEngine::parse(F), x);
    const auto g = SymEngine::parse(f);
    for (double t : pts) {
        double a = 0.0, b = 0.0;
        try {
            a = SymEngine::eval_double(*D->subs({{x, SymEngine::real_double(t)}}));
            b = SymEngine::eval_double(*g->subs({{x, SymEngine::real_double(t)}}));
        } catch (...) {
            return false;
        }
        if (!std::isfinite(a) || !std::isfinite(b)) return false;
        const double den = (std::max)(1.0, std::abs(b));
        if (std::abs(a - b) / den > 1e-9) return false;
    }
    return true;
}

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

// ── 内核层测试 ──────────────────────────────────────────────────────────────

static void test_integrals_kernel() {
    // 不定积分(自研符号积分器)
    CHECK(calc::integrate_indefinite("sin(x)", "x").find("cos") != std::string::npos,
          "∫sin(x) = -cos(x) + C");
    CHECK(calc::integrate_indefinite("x**2", "x").find("x**3") != std::string::npos,
          "∫x² = x³/3 + C");
    CHECK(calc::integrate_indefinite("cos(x)", "x").find("sin") != std::string::npos,
          "∫cos(x) = sin(x) + C");
    CHECK(calc::integrate_indefinite("exp(x)", "x").find("exp") != std::string::npos,
          "∫eˣ = eˣ + C");
    CHECK(calc::integrate_indefinite("1/x", "x").find("log") != std::string::npos,
          "∫1/x = ln x + C");
    CHECK(calc::integrate_indefinite("2*x", "x").find("x**2") != std::string::npos,
          "∫2x = x² + C(线性性)");
    CHECK(calc::integrate_indefinite("x**2 + 1", "x").find("x**3") != std::string::npos,
          "∫(x²+1) = x³/3 + x + C");
    CHECK(calc::integrate_indefinite("sqrt(x)", "x").find("x**(3/2)") != std::string::npos,
          "∫√x = 2/3·x^(3/2)");
    // 分部积分:x·sin(x) = -x·cos(x) + sin(x)
    CHECK(calc::integrate_indefinite("x*sin(x)", "x").find("cos") != std::string::npos,
          "∫x·sin(x) 含 -x·cos(x)(分部积分)");
    // 无法积分 → 返回 "未实现"(不编造)。
    // 注意：∫tan(x) 原先也在这里断言"未实现"，本批已实现（见下面的求导自证），
    // 故改用真正非初等的 x^x 来守这条"不编造"的底线。
    CHECK(calc::integrate_indefinite("x**x", "x") == "未实现",
          "∫xˣ 未实现（非初等，如实拒绝）");

    // ── 本批新增的不定积分规则：逐条**求导自证** ────────────────────────────
    // 这些是教科书里最常遇到、而原先一律返回"未实现"的几条。
    CHECK(antideriv_self_checks_out("1/(1+x**2)", "x", {0.3, 0.7, -1.1}),
          "∫1/(1+x²) = atan x（求导自证）");
    CHECK(antideriv_self_checks_out("tan(x)", "x", {0.3, 0.7, -0.9}),
          "∫tan x = -ln cos x（求导自证）");
    CHECK(antideriv_self_checks_out("x/(1+x**2)", "x", {0.3, 0.7, -1.1}),
          "∫x/(1+x²) = ½ln(1+x²)（求导自证）");
    CHECK(antideriv_self_checks_out("1/(x*ln(x))", "x", {1.7, 2.5, 4.0}),
          "∫1/(x·ln x) = ln ln x（求导自证）");
    CHECK(antideriv_self_checks_out("tan(x)**2", "x", {0.3, 0.7, -0.9}),
          "∫tan²x = tan x − x（求导自证）");

    // ── 第二批：三角/反三角/指数×三角/幂×对数 ────────────────────────────
    // ∫cos³x 的第一版把 −sin³x/3 写成了 +sin³x/3，**就是这条自证**以
    // maxrel=0.635 当场抓出来的 —— 它存在的意义就在这里。
    CHECK(antideriv_self_checks_out("sec(x)", "x", {0.3, 0.7, -0.6}),
          "∫sec x = ln(sec x + tan x)（求导自证）");
    CHECK(antideriv_self_checks_out("x*ln(x)", "x", {0.5, 1.7, 3.0}),
          "∫x·ln x = ½x²ln x − ¼x²（求导自证）");
    CHECK(antideriv_self_checks_out("exp(x)*sin(x)", "x", {0.3, 0.7, -0.6}),
          "∫eˣ·sin x = eˣ(sin x − cos x)/2（求导自证）");
    CHECK(antideriv_self_checks_out("exp(x)*cos(x)", "x", {0.3, 0.7, -0.6}),
          "∫eˣ·cos x = eˣ(sin x + cos x)/2（求导自证）");
    CHECK(antideriv_self_checks_out("atan(x)", "x", {0.3, 0.7, -1.1}),
          "∫atan x = x·atan x − ½ln(1+x²)（求导自证）");
    CHECK(antideriv_self_checks_out("acos(x)", "x", {0.3, 0.7, -0.6}),
          "∫acos x = x·acos x − √(1−x²)（求导自证）");
    CHECK(antideriv_self_checks_out("sin(x)**3", "x", {0.3, 0.7, -0.6}),
          "∫sin³x = cos³x/3 − cos x（求导自证）");
    CHECK(antideriv_self_checks_out("cos(x)**3", "x", {0.3, 0.7, -0.6}),
          "∫cos³x = sin x − sin³x/3（求导自证，符号必须为负）");

    // ── 第三批：根式 / sec³ / 四次分式 / 分数幂×对数 ──────────────────────
    // 做完这批，26 个教科书积分里只剩**非初等**的那 5 条（x^x、sin x/x、
    // e^{-x²}、1/ln x、x²e^{-x²}）仍返回"未实现" —— 那拒绝是正确的。
    CHECK(antideriv_self_checks_out("sqrt(1-x**2)", "x", {0.3, 0.7, -0.6}),
          "∫√(1−x²) = (x√(1−x²) + asin x)/2（求导自证）");
    CHECK(antideriv_self_checks_out("sqrt(1+x**2)", "x", {0.3, 0.7, -0.6}),
          "∫√(1+x²) = (x√(1+x²) + asinh x)/2（求导自证）");
    CHECK(antideriv_self_checks_out("sec(x)**3", "x", {0.3, 0.7, -0.6}),
          "∫sec³x = ½(sec x·tan x + ln(sec x+tan x))（求导自证）");
    CHECK(antideriv_self_checks_out("1/(1+x**4)", "x", {0.3, 0.7, -0.6}),
          "∫1/(1+x⁴) 四次式闭式（求导自证）");
    CHECK(antideriv_self_checks_out("sqrt(x)*ln(x)", "x", {0.5, 1.7, 3.0}),
          "∫√x·ln x = (2/3)x^{3/2}ln x − (4/9)x^{3/2}（求导自证）");

    // 定积分(符号原函数 → 精确)
    CHECK(near(calc::integrate_definite("x**2", "x", "0", "1"), 1.0 / 3.0, 1e-9),
          "∫₀¹ x² = 1/3(符号精确)");
    CHECK(near(calc::integrate_definite("sin(x)", "x", "0", "pi"), 2.0, 1e-9),
          "∫₀^π sin(x) = 2(符号精确)");
    CHECK(near(calc::integrate_definite("cos(x)", "x", "0", "pi"), 0.0, 1e-9),
          "∫₀^π cos(x) = 0");

    // 二重积分(符号逐层)
    CHECK(near(calc::integrate_double("x*y", "x", "y", "0", "1", "0", "2"), 1.0, 1e-9),
          "∫∫x·y dy dx 矩形 = 1");
    CHECK(near(calc::integrate_double("x + y", "x", "y", "0", "1", "0", "1"), 1.0, 1e-9),
          "∫∫(x+y) 单位正方形 = 1");
    CHECK(near(calc::integrate_double("x*y", "x", "y", "0", "1", "0", "x"), 0.125, 1e-9),
          "∫∫x·y dy dx,y:0→x = 1/8(变上限)");

    // 三重积分(符号逐层)
    CHECK(near(calc::integrate_triple("x*y*z", "x", "y", "z",
                                      "0", "1", "0", "1", "0", "1"), 0.125, 1e-9),
          "∫∫∫x·y·z 单位立方体 = 1/8");
    CHECK(near(calc::integrate_triple("1", "x", "y", "z",
                                      "0", "1", "0", "1", "0", "x"), 0.5, 1e-9),
          "∫∫∫1 dz dy dx,z:0→x = 1/2(变上限)");

    // 幂降公式:∫sin²(x) = x/2 - sin(2x)/4,∫cos²(x) = x/2 + sin(2x)/4
    CHECK(calc::integrate_indefinite("sin(x)**2", "x").find("sin(2*x)") != std::string::npos &&
              calc::integrate_indefinite("sin(x)**2", "x").find("1/4") != std::string::npos,
          "∫sin²(x) 含 sin(2x)/4(幂降)");
    CHECK(calc::integrate_indefinite("cos(x)**2", "x").find("1/4") != std::string::npos,
          "∫cos²(x) 含 sin(2x)/4(幂降)");

    // 积化和差
    CHECK(calc::integrate_indefinite("sin(x)*cos(x)", "x").find("cos(2*x)") != std::string::npos,
          "∫sin(x)cos(x) 含 cos(2x)");
    CHECK(calc::integrate_indefinite("sin(x)*cos(2*x)", "x").find("cos(3*x)") != std::string::npos,
          "∫sin(x)cos(2x) 含 cos(3x)(积化和差)");
    CHECK(calc::integrate_indefinite("sin(x)*sin(2*x)", "x").find("sin(3*x)") != std::string::npos,
          "∫sin(x)sin(2x) 含 sin(3x)");
    CHECK(calc::integrate_indefinite("cos(x)*cos(2*x)", "x").find("sin(3*x)") != std::string::npos,
          "∫cos(x)cos(2x) 含 sin(3x)");

    // 符号反常积分
    CHECK(near(calc::improper_integral("x*exp(-x**2)", "x", "0", "oo"), 0.5, 1e-6),
          "∫₀^∞ x·e⁻ˣ² = 1/2(符号原函数)");

    // 复积分 ∫₀¹ e^{i2x} dx ≈ 0.4546 + 0.7081i
    const std::complex<double> cx = calc::integrate_complex("exp(I*2*x)", "x", "0", "1");
    CHECK(near(cx.real(), 0.4546487134, 1e-6) && near(cx.imag(), 0.7080734183, 1e-6),
          "∫₀¹ e^{i2x} ≈ 0.4546+0.7081i(复积分)");

    // 数值积分
    CHECK(near(calc::integrate_numeric("x**2", "x", 0, 1), 1.0 / 3.0, 1e-6),
          "Simpson ∫₀¹ x² ≈ 1/3");
    CHECK(near(calc::integrate_numeric("sin(x)", "x", 0, 3.141592653589793), 2.0, 1e-4),
          "Simpson ∫₀^π sin(x) ≈ 2");

    // 反常积分(数值截断)
    CHECK(near(calc::improper_integral("1/x**2", "x", "1", "oo"), 1.0, 1e-3),
          "∫₁^∞ 1/x² ≈ 1");
    CHECK(near(calc::improper_integral("exp(-x)", "x", "0", "oo"), 1.0, 1e-3),
          "∫₀^∞ e⁻ˣ ≈ 1");
    bool threw = false;
    try {
        calc::improper_integral("1/x", "x", "1", "oo");
    } catch (const std::exception&) {
        threw = true;
    }
    CHECK(threw, "∫₁^∞ 1/x 发散 → 抛异常");
    threw = false;
    try {
        calc::integrate_definite("sin(x)", "x", "0", "oo");
    } catch (const std::exception&) {
        threw = true;
    }
    CHECK(threw, "定积分遇到无穷边界 → 抛异常提示用 improper_integral");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static void test_kernel() {
    // diff
    const std::string d1 = calc::diff("x**3", "x");
    CHECK(d1.find("3") != std::string::npos && d1.find("x") != std::string::npos,
          "d(x^3) 含 3 和 x");
    const std::string d2 = calc::diff("x**3", "x", 2);
    CHECK(d2.find("6") != std::string::npos, "d²(x^3) 含 6");
    const std::string dsin = calc::diff("sin(x)", "x");
    CHECK(dsin.find("cos") != std::string::npos, "d(sin x) = cos x");

    // diff_at
    CHECK(near(calc::diff_at("x**3", "x", 2.0), 12.0, 1e-9), "f'(2)=12 for x³");
    CHECK(near(calc::diff_at("x**2", "x", 3.0, 2), 2.0, 1e-9), "f''(3)=2 for x²");

    // implicit_diff:x²+y²=1 → dy/dx = -x/y
    const std::string id = calc::implicit_diff("x**2 + y**2 - 1", "x", "y");
    CHECK(id.find("x") != std::string::npos && id.find("y") != std::string::npos &&
              id.find("-") != std::string::npos,
          "隐函数 x²+y²=1 → dy/dx 含 -x/y");
    CHECK(calc::implicit_diff("x", "x", "y") == "无法求解", "F_y=0 → 无法求解");

    // parametric_diff:x=t², y=t³ → dy/dx = 3t/2
    const std::string pd = calc::parametric_diff("t**2", "t**3", "t");
    CHECK(pd.find("t") != std::string::npos, "参数方程求导含 t");
    CHECK(calc::parametric_diff("2", "t", "t") == "无穷大（切线垂直）",
          "dx/dt=0 → 切线垂直");

    // differential
    CHECK(near(calc::differential("x**2", "x", 3.0, 0.1), 0.6, 1e-9),
          "dy = f'(3)·0.1 = 0.6");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[4096];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

// ── derivatives_app / integrals_app / series ─────────────────────────────────

static void test_derivatives_app() {
    const auto rolle = calc::calc_rolle_theorem("x*(x-1)", "x", 0, 1);
    CHECK(rolle.size() == 1 && near(rolle[0], 0.5, 1e-9),
          "罗尔定理 x(x-1) on [0,1] → ξ=0.5");

    CHECK(near(calc::calc_lagrange_theorem("x**2", "x", 0, 1), 0.5, 1e-9),
          "拉格朗日中值定理 x² → ξ=0.5");

    CHECK(near(calc::lhopital("sin(x)/x", "x", 0), 1.0, 1e-3),
          "洛必达 sin(x)/x → 1");

    const auto mono = calc::monotonicity("x**2", "x");
    CHECK(mono.size() >= 2, "单调性 x² 至少两个区间");

    const calc::LocalExtremaResult le = calc::local_extrema("x**3 - 3*x", "x");
    CHECK(le.maxima_x.size() == 1 && near(le.maxima_x[0], -1.0, 1e-6) &&
              le.minima_x.size() == 1 && near(le.minima_x[0], 1.0, 1e-6),
          "局部极值 x³-3x: 极大 x=-1, 极小 x=1");

    const calc::GlobalExtremaResult ge = calc::global_extrema("x**2", "x", -1, 2);
    CHECK(near(ge.max, 4.0, 1e-9) && near(ge.min, 0.0, 1e-9),
          "全局最值 x² on [-1,2]: max=4, min=0");

    const std::string t = calc::taylor("sin(x)", "x", 0, 3);
    CHECK(t.find("x") != std::string::npos, "泰勒展开 sin(x) 含 x");
}

static void test_integrals_app() {
    const double kPi = 3.141592653589793;
    const double ab = calc::area_between("sin(x)", "cos(x)", "x", 0, kPi / 4);
    CHECK(near(ab, std::sqrt(2.0) - 1.0, 0.01), "面积 sin vs cos ≈ √2-1");

    CHECK(near(calc::volume_disk("x", "x", 0, 1), kPi / 3, 0.01),
          "圆盘法体积 x on [0,1] = π/3");

    CHECK(near(calc::volume_shell("x", "x", 0, 1), 2 * kPi / 3, 0.01),
          "壳法体积 x on [0,1] = 2π/3");

    CHECK(near(calc::arc_length("x", "x", 0, 1), std::sqrt(2.0), 0.01),
          "弧长 y=x on [0,1] = √2");
}

static void test_series() {
    CHECK(near(calc::series_sum("1/n**2", "n", 1, -1), 1.644934, 1e-3),
          "Σ 1/n² = π²/6");
    const std::string sc = calc::series_convergence("1/n**2", "n");
    CHECK(!sc.empty(), "级数收敛性判别非空");
    const std::string ps = calc::power_series("sin(x)", "x", 0, 5);
    CHECK(ps.find("x") != std::string::npos, "幂级数 sin(x) 含 x");
    CHECK(calc::power_series_radius("1/factorial(n)", "n") ==
              std::numeric_limits<double>::infinity(),
          "收敛半径 1/n! = ∞");
    CHECK(calc::leibniz_test("(-1)**n/n", "n") == "convergent",
          "Leibniz: (-1)^n/n 收敛");
    CHECK(calc::integral_test("1/n**2", "n") == "convergent", "积分判别 1/n² 收敛");
    CHECK(calc::p_series_test("1/n**2", "n") == "convergent", "p-级数 1/n² 收敛");
    CHECK(calc::limit_comparison_test("1/(n**2+1)", "n") == "convergent",
          "极限比较 1/(n²+1) 收敛");
    CHECK(calc::classify_and_test("(-1)**n/n", "n") == "convergent",
          "分类审敛 (-1)^n/n 收敛");
    CHECK(calc::classify_and_test("1/n", "n") == "divergent",
          "分类审敛 1/n 发散");
}

static void test_dispatch() {
    CHECK(function_exists("diff"), "function_exists(diff)");
    CHECK(function_exists("diff_at"), "function_exists(diff_at)");

    CHECK(call("diff", "{\"expr\":\"x**3\",\"var\":\"x\"}").find("3") != std::string::npos,
          "math_call diff(x³) 含 3");
    CHECK(call("diff_at", "{\"expr\":\"x**3\",\"var\":\"x\",\"point\":2}") ==
              "{\"isError\":false,\"value\":12}",
          "math_call diff_at(x³,2) = 12");
    const std::string id = call("implicit_diff",
                                "{\"eq\":\"x**2 + y**2 - 1\",\"var\":\"x\",\"dep_var\":\"y\"}");
    CHECK(id.find("\"isError\":false") != std::string::npos, "math_call implicit_diff");
    const mf::json::Value diffv = mf::json::Value::parse(
        call("differential", "{\"expr\":\"x**2\",\"var\":\"x\",\"point\":3,\"dx\":0.1}"));
    CHECK(near(diffv["value"].as_double(), 0.6, 1e-9), "math_call differential ≈ 0.6");

    const std::string bad = call("diff", "{\"expr\":\"x**3\",\"order\":0}");
    CHECK(bad.find("\"isError\":true") != std::string::npos, "diff order=0 → isError");

    // ── integrals ──────────────────────────────────────────────────────────
    CHECK(function_exists("integrate"), "function_exists(integrate)");
    CHECK(function_exists("integrate_numeric"), "function_exists(integrate_numeric)");
    CHECK(function_exists("improper_integral"), "function_exists(improper_integral)");
    CHECK(call("integrate", "{\"expr\":\"sin(x)\",\"var\":\"x\"}").find("cos") !=
              std::string::npos,
          "math_call integrate(sin(x)) 含 cos");
    const std::string def =
        call("integrate", "{\"expr\":\"x**2\",\"var\":\"x\",\"a\":0,\"b\":1}");
    CHECK(def.find("\"isError\":false") != std::string::npos,
          "math_call integrate(x²,0,1)");
    const std::string num =
        call("integrate_numeric", "{\"expr\":\"x**2\",\"var\":\"x\",\"a\":0,\"b\":1}");
    const mf::json::Value numv = mf::json::Value::parse(num);
    CHECK(near(numv["value"].as_double(), 1.0 / 3.0, 1e-4),
          "math_call integrate_numeric(x²,0,1) ≈ 1/3");
    const std::string improper = call("improper_integral",
                                      "{\"expr\":\"1/x**2\",\"var\":\"x\",\"a\":1,\"b\":\"oo\"}");
    const mf::json::Value impv = mf::json::Value::parse(improper);
    CHECK(near(impv["value"].as_double(), 1.0, 1e-3),
          "math_call improper_integral(1/x²,1,oo) ≈ 1");
    const std::string oo_bad =
        call("integrate", "{\"expr\":\"sin(x)\",\"var\":\"x\",\"a\":0,\"b\":\"oo\"}");
    CHECK(oo_bad.find("\"isError\":true") != std::string::npos,
          "math_call integrate 无穷边界 → isError");

    // 二重/三重积分
    CHECK(function_exists("integrate_double"), "function_exists(integrate_double)");
    CHECK(function_exists("integrate_triple"), "function_exists(integrate_triple)");
    const std::string dbl = call("integrate_double",
        "{\"expr\":\"x*y\",\"x\":\"x\",\"y\":\"y\",\"xa\":0,\"xb\":1,\"ya\":0,\"yb\":2}");
    const mf::json::Value dblv = mf::json::Value::parse(dbl);
    CHECK(near(dblv["value"].as_double(), 1.0, 1e-9),
          "math_call integrate_double(x·y) ≈ 1");
    const std::string trp = call("integrate_triple",
        "{\"expr\":\"x*y*z\",\"x\":\"x\",\"y\":\"y\",\"z\":\"z\","
        "\"xa\":0,\"xb\":1,\"ya\":0,\"yb\":1,\"za\":0,\"zb\":1}");
    const mf::json::Value trpv = mf::json::Value::parse(trp);
    CHECK(near(trpv["value"].as_double(), 0.125, 1e-9),
          "math_call integrate_triple(x·y·z) ≈ 0.125");

    // 不定重积分：**缺边界**即逐次求原函数（与单变量 integrate 同一套约定）。
    // 钉住两件事：① 结果是对的原函数；② "常数"写成 A(x)+B(y) 而不是含糊的 "+ C"
    // —— 对 y 积分时 x 是常数，那层的积分常数是 x 的任意函数，加 "+ C" 是错的。
    const std::string dbi = call("integrate_double",
        "{\"expr\":\"x*y\",\"x\":\"x\",\"y\":\"y\"}");
    CHECK(dbi.find("\"isError\":false") != std::string::npos &&
              dbi.find("x**2*y**2") != std::string::npos &&
              dbi.find("A(x)") != std::string::npos &&
              dbi.find("B(y)") != std::string::npos,
          "integrate_double 缺边界 → 不定重积分 (1/4)x²y² + A(x) + B(y)");
    // 缺边界不能再静默按 [0,1] 算出一个看着正常的数
    CHECK(dbi.find("0.25") == std::string::npos,
          "integrate_double 缺边界不再静默按 [0,1] 求值");
    const std::string tbi = call("integrate_triple",
        "{\"expr\":\"x*y*z\",\"x\":\"x\",\"y\":\"y\",\"z\":\"z\"}");
    CHECK(tbi.find("\"isError\":false") != std::string::npos &&
              tbi.find("x**2*y**2*z**2") != std::string::npos &&
              tbi.find("A(x,y)") != std::string::npos &&
              tbi.find("C(y,z)") != std::string::npos,
          "integrate_triple 缺边界 → 不定三重积分含 A(x,y)+B(x,z)+C(y,z)");
    // 符号积分做不到时必须如实说，不许编
    const std::string dbr = call("integrate_double",
        "{\"expr\":\"sin(x*y)\",\"x\":\"x\",\"y\":\"y\"}");
    CHECK(dbr.find("未实现") != std::string::npos,
          "integrate_double 无法符号积分 → 未实现（不编造）");

    CHECK(function_exists("integrate_complex"), "function_exists(integrate_complex)");
    const std::string cpx = call("integrate_complex",
        "{\"expr\":\"exp(I*2*x)\",\"var\":\"x\",\"a\":0,\"b\":1}");
    const mf::json::Value cpxv = mf::json::Value::parse(cpx);
    CHECK(near(cpxv["value"].at(0).as_double(), 0.4546487134, 1e-6) &&
              near(cpxv["value"].at(1).as_double(), 0.7080734183, 1e-6),
          "math_call integrate_complex(e^{i2x}) ≈ [0.4546, 0.7081]");
}

int main() {
    std::system("chcp 65001 > nul");
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("===== calculus 内核测试 =====\n");
    test_kernel();
    test_integrals_kernel();
    test_derivatives_app();
    test_integrals_app();
    test_series();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
