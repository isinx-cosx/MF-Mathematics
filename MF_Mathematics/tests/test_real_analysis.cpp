// test_real_analysis.cpp — real_analysis 包(differentiability,基于 SymEngine)内核 + JSON 测试。
//
// 期望值取自 Python 版 differentiability self_test() 的断言。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>

#include "api.h"
#include "json.hpp"
#include "real_analysis/differentiability.h"
#include "real_analysis/sequence_limit.h"
#include "real_analysis/real_numbers.h"
#include "real_analysis/riemann_integral.h"
#include "real_analysis/function_limit.h"
#include "real_analysis/function_series.h"

namespace ra = mf::real_analysis;

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

#define CHECK_EQ(a, b, msg) CHECK((a) == (b), msg)

static bool near(double a, double b, double tol) { return std::abs(a - b) <= tol; }

// ── 内核层测试 ──────────────────────────────────────────────────────────────

static void test_kernel() {
    // derivative_definition:f'(x²)=2x, f'(0)=0
    CHECK(near(ra::derivative_definition("x**2", "x", 0), 0.0, 1e-6),
          "导数定义 f'(0) of x² = 0");
    CHECK(near(ra::derivative_definition("x**2", "x", 3), 6.0, 1e-6),
          "导数定义 f'(3) of x² = 6");

    // is_differentiable
    CHECK(ra::is_differentiable("sin(x)", "x", 0), "sin(x) 在 0 可导");
    CHECK(!ra::is_differentiable("Abs(x)", "x", 0), "|x| 在 0 不可导");
    CHECK(ra::is_differentiable("x**2", "x", 2), "x² 在 2 可导");

    // taylor_polynomial
    const std::string tp = ra::taylor_polynomial("sin(x)", "x", 0, 3);
    CHECK(tp.find("x") != std::string::npos && tp.find("-") != std::string::npos,
          "泰勒多项式 sin(x) n=3 含 x 与负项");

    // taylor_remainder
    const ra::TaylorRemainderResult tr =
        ra::taylor_remainder("sin(x)", "x", 0, 3, false, 0.0);
    CHECK(!tr.formula.empty() && !tr.has_xi, "拉格朗日余项公式(未代 ξ)");
    const ra::TaylorRemainderResult tr2 =
        ra::taylor_remainder("sin(x)", "x", 0, 3, true, 0.5);
    CHECK(tr2.has_xi && std::isfinite(tr2.remainder_factor),
          "拉格朗日余项(代 ξ=0.5)");

    // rolle_theorem
    const ra::RolleResult rolle = ra::rolle_theorem("x**2 - 1", "x", -1, 1);
    CHECK(rolle.satisfies && near(rolle.xi, 0.0, 1e-9),
          "罗尔定理 x²-1 on [-1,1] → ξ=0");
    CHECK(!ra::rolle_theorem("x**2", "x", 0, 1).satisfies,
          "罗尔定理 f(a)≠f(b) → 不满足");

    // lagrange_theorem
    const ra::LagrangeResult lag = ra::lagrange_theorem("x**2", "x", 0, 2);
    CHECK(near(lag.xi, 1.0, 1e-9) && near(lag.secant_slope, 2.0, 1e-9),
          "拉格朗日中值定理 x² on [0,2] → ξ=1, 斜率 2");
}

// ── 数列极限 / 实数系 / 黎曼积分 / 函数极限 / 函数级数 ──────────────────────

static void test_sequence_limit() {
    CHECK(near(ra::sequence_limit("1/n"), 0.0, 1e-3), "lim 1/n = 0");
    CHECK(near(ra::sequence_limit("(n+1)/n"), 1.0, 1e-3), "lim (n+1)/n = 1");
    const ra::SequenceConvergenceResult c1 = ra::sequence_convergence("1/n");
    CHECK(c1.convergent, "1/n 收敛");
    const ra::SequenceConvergenceResult c2 = ra::sequence_convergence("n");
    CHECK(!c2.convergent && c2.description.find("+∞") != std::string::npos,
          "n 发散到 +∞");
    CHECK(ra::cauchy_criterion("1/n", 0.01, 500), "1/n 满足柯西准则");
    CHECK(!ra::cauchy_criterion("(-1)**n", 0.01, 500), "(-1)^n 不满足柯西准则");
}

static void test_real_numbers() {
    bool has = false;
    CHECK(near(ra::supremum_desc("{x | x < 2}", has), 2.0, 1e-12) && has,
          "sup {x|x<2} = 2");
    CHECK(near(ra::infimum_desc("{x | x > 1}", has), 1.0, 1e-12) && has,
          "inf {x|x>1} = 1");
    CHECK(near(ra::supremum({1, 3, 5, 2, 4}, has), 5.0, 1e-12), "sup = 5");
    CHECK(ra::archimedean_property(100.0, 1.0) == 101, "阿基米德性质 n=101");
    CHECK(ra::dedekind_cut({1, 2, 3}, {4, 5, 6}), "戴德金分割 [1,2,3]/[4,5,6]");
    CHECK(!ra::dedekind_cut({1, 2, 4}, {3, 4, 5}), "重叠分割无效");
}

static void test_riemann_integral() {
    const ra::DarbouxResult db = ra::darboux_sum("x**2", 0, 1);
    CHECK(db.lower_sum > 0 && db.upper_sum > db.lower_sum, "达布和 L>0, U>L");
    CHECK(ra::riemann_integrable("x**2", 0, 1), "x² 可积");
    CHECK(!ra::riemann_integrable("1/x", 0, 1), "1/x on [0,1] 不可积");

    const ra::FundamentalResult ft = ra::fundamental_theorem("x**2", 0, 1);
    CHECK(near(ft.integral, 1.0 / 3.0, 0.01), "微积分基本定理 ∫x² = 1/3");

    const ra::MeanValueResult mv = ra::integral_mean_value("x**2", 0, 1);
    CHECK(near(mv.mean_value, 1.0 / 3.0, 0.01), "积分中值 mean = 1/3");
    CHECK(near(mv.xi, 1.0 / std::sqrt(3.0), 0.01), "ξ = 1/√3");
}

static void test_function_limit() {
    const ra::EpsDeltaResult ed = ra::limit_epsilon_delta("x**2", 0, 0.01);
    CHECK(near(ed.L, 0.0, 1e-4), "ε-δ: lim x² = 0");

    CHECK(ra::real_is_continuous("sin(x)", 0), "sin(x) 在 0 连续");
    CHECK(!ra::real_is_continuous("1/(x-1)", 1), "1/(x-1) 在 1 不连续");

    const std::string dc = ra::real_discontinuity_classify("1/(x-1)", 1);
    CHECK(dc.find("无穷") != std::string::npos, "1/(x-1) 无穷间断点");

    const ra::ExtremeValueResult ev = ra::extreme_value("x**2", 0, 1);
    CHECK(near(ev.max, 1.0, 1e-9) && near(ev.min, 0.0, 1e-9),
          "最值定理: max=1, min=0");

    CHECK(near(ra::intermediate_value("x**3", -1, 1, 0), 0.0, 1e-6),
          "介值定理: ξ=0");

    CHECK(ra::uniform_continuity("x**2", 0, 1), "x² 在 [0,1] 一致连续");
}

static void test_function_series() {
    CHECK(near(ra::pointwise_convergence("x**n", 0.5), 0.0, 1e-3),
          "逐点收敛 x^n at 0.5 → 0");
    CHECK(near(ra::pointwise_convergence("x**n", 1.0), 1.0, 1e-3),
          "逐点收敛 x^n at 1 → 1");

    const ra::UniformConvergenceResult u1 = ra::uniform_convergence("x**n", 0, 0.5);
    CHECK(u1.is_uniform, "x^n on [0,0.5] 一致收敛");
    const ra::UniformConvergenceResult u2 = ra::uniform_convergence("x**n", 0, 1);
    CHECK(!u2.is_uniform, "x^n on [0,1] 非一致收敛");

    const ra::WeierstrassResult w = ra::weierstrass_m_test("x**n/n**2", 0, 1);
    CHECK(w.passes, "Weierstrass M: Σ x^n/n² 一致收敛");

    const ra::TermwiseIntegralResult ti = ra::termwise_integration("x**n/n**2", 0, 1, 5);
    CHECK(ti.termwise_sum > 0 && near(ti.termwise_sum, ti.direct_integral, 0.01),
          "逐项积分与直接积分一致");

    const ra::TermwiseDiffResult td = ra::termwise_differentiation("x**n/n**2", 3);
    CHECK(td.verified && !td.derivative_series.empty(), "逐项求导验证通过");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[4096];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("derivative_definition"),
          "function_exists(derivative_definition)");
    CHECK(function_exists("taylor_polynomial"), "function_exists(taylor_polynomial)");

    CHECK(call("derivative_definition",
               "{\"expr\":\"x**2\",\"var\":\"x\",\"point\":0}") ==
              "{\"isError\":false,\"value\":0}",
          "math_call derivative_definition(x²,0) → 0");
    CHECK(call("is_differentiable",
               "{\"expr\":\"Abs(x)\",\"var\":\"x\",\"point\":0}") ==
              "{\"isError\":false,\"value\":false}",
          "math_call is_differentiable(|x|,0) → false");
    const std::string tp = call("taylor_polynomial",
                                "{\"expr\":\"sin(x)\",\"var\":\"x\",\"point\":0,\"n\":3}");
    CHECK(tp.find("\"isError\":false") != std::string::npos &&
              tp.find("x") != std::string::npos,
          "math_call taylor_polynomial(sin(x),0,3)");
    const std::string rem =
        call("taylor_remainder", "{\"expr\":\"sin(x)\",\"var\":\"x\",\"point\":0,\"n\":3}");
    CHECK(rem.find("\"isError\":false") != std::string::npos,
          "math_call taylor_remainder");
    CHECK(call("real_rolle_theorem",
               "{\"expr\":\"x**2 - 1\",\"var\":\"x\",\"interval\":[-1,1]}") ==
              "{\"isError\":false,\"value\":0}",
          "math_call real_rolle_theorem(x²-1,[-1,1]) → 0");
    const std::string no_rolle = call(
        "real_rolle_theorem", "{\"expr\":\"x**2\",\"var\":\"x\",\"interval\":[0,1]}");
    CHECK(no_rolle.find("\"value\":null") != std::string::npos,
          "math_call real_rolle_theorem 不满足 → null");
    const std::string lag = call(
        "real_lagrange_theorem", "{\"expr\":\"x**2\",\"var\":\"x\",\"interval\":[0,2]}");
    CHECK(lag.find("\"xi\":1") != std::string::npos &&
              lag.find("\"secant_slope\":2") != std::string::npos,
          "math_call real_lagrange_theorem(x²,[0,2]) → ξ=1, slope=2");
}

int main() {
    std::system("chcp 65001 > nul");
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("===== real_analysis 内核测试 =====\n");
    test_kernel();
    test_sequence_limit();
    test_real_numbers();
    test_riemann_integral();
    test_function_limit();
    test_function_series();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
