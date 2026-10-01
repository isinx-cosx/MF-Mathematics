// test_measure_theory.cpp — measure_theory 包内核 + JSON 测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "api.h"
#include "json.hpp"
#include "measure_theory/convergence_theorems.h"
#include "measure_theory/lebesgue_integral.h"
#include "measure_theory/measurable_functions.h"
#include "measure_theory/measure_construction.h"
#include "measure_theory/probability_measure.h"
#include "measure_theory/product_measure.h"
#include "measure_theory/set_systems.h"

namespace mt = mf::measure_theory;

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

// ── set_systems ──────────────────────────────────────────────────────────────

static void test_set_systems() {
    // 标准 σ-代数(幂集)。
    const mt::SigmaAlgebraResult r1 = mt::is_sigma_algebra(
        {{}, {1, 2, 3}, {1}, {2, 3}, {2}, {1, 3}, {3}, {1, 2}}, {1, 2, 3});
    CHECK(r1.is_sigma_algebra, "is_sigma_algebra 幂集 → 是 σ-代数");

    // 非 σ-代数:缺补集。
    const mt::SigmaAlgebraResult r2 =
        mt::is_sigma_algebra({{}, {1, 2, 3}, {1}}, {1, 2, 3});
    CHECK(!r2.is_sigma_algebra, "is_sigma_algebra {{},X,{1}} → 非 σ-代数");

    // generate_sigma_algebra([{1}], X={1,2}) → 4 个集合。
    const mt::GeneratedSigmaAlgebra g1 =
        mt::generate_sigma_algebra({{1}}, {1, 2});
    CHECK(g1.count == 4, "generate_sigma_algebra([{1}],{1,2}) → 4 个集合");

    // borel 离散 (0,2) → {0,1,2} 的幂集 → 8 个集合。
    const mt::GeneratedSigmaAlgebra b1 = mt::borel_sigma_algebra({0, 1, 2});
    CHECK(b1.count == 8, "borel_sigma_algebra((0,2)) → 8 个集合");
}

// ── measurable_functions ─────────────────────────────────────────────────────

static void test_measurable_functions() {
    const mt::MeasurableResult m1 = mt::is_measurable("x**2", -10, 10);
    CHECK(m1.is_measurable && m1.singularities.empty(), "x² 可测且无奇点");

    const mt::MeasurableResult m2 = mt::is_measurable("sin(x)", -10, 10);
    CHECK(m2.is_measurable, "sin(x) 可测");

    const mt::MeasurableResult m3 = mt::is_measurable("1/x", -1, 1);
    CHECK(!m3.singularities.empty(), "1/x 在 0 处有奇点");

    // 简单函数 φ = 1·1_[0,0.3] + 2·1_[0.3,0.6] + 3·1_[0.6,1]。
    const std::vector<std::pair<double, double>> sets = {
        {0, 0.3}, {0.3, 0.6}, {0.6, 1.0}};
    CHECK(near(mt::simple_function_eval({1, 2, 3}, sets, 0.15), 1.0, 1e-12),
          "简单函数 φ(0.15) = 1");
    CHECK(near(mt::simple_function_eval({1, 2, 3}, sets, 0.45), 2.0, 1e-12),
          "简单函数 φ(0.45) = 2");
    CHECK(near(mt::simple_function_eval({1, 2, 3}, sets, 0.8), 3.0, 1e-12),
          "简单函数 φ(0.8) = 3");

    // 阶梯逼近 x² on (0,1),n=4:dx=0.25。
    const mt::StepApproxResult sa = mt::step_function_approx("x**2", 4, 0, 1);
    CHECK(sa.values.size() == 4 && near(sa.dx, 0.25, 1e-12),
          "阶梯逼近 4 段,dx=0.25");
    CHECK(near(sa.integral, 0.21875, 1e-6), "阶梯逼近积分 = Σ f(left)·dx");
}

// ── measure_construction ─────────────────────────────────────────────────────

static void test_measure_construction() {
    CHECK(near(mt::lebesgue_measure(0, 1), 1.0, 1e-12), "λ([0,1]) = 1");

    const mt::MeasureSetResult q = mt::lebesgue_measure_set("Q");
    CHECK(!q.infinite && near(q.value, 0.0, 1e-12), "λ(Q) = 0");
    const mt::MeasureSetResult r = mt::lebesgue_measure_set("R");
    CHECK(r.infinite, "λ(R) = ∞");

    const mt::OuterMeasureResult om = mt::outer_measure(0, 1, 0.01);
    CHECK(near(om.measure, 1.0, 1e-12), "m*([0,1]) = 1");

    CHECK(mt::caratheodory_measurable(0, 1), "区间 Carathéodory 可测");

    const auto props = mt::measure_properties();
    CHECK(props.size() == 5, "测度性质共 5 条");
    bool all_verified = true;
    for (const auto& p : props) all_verified = all_verified && p.verified;
    CHECK(all_verified, "测度性质全部验证通过");
}

// ── lebesgue_integral ────────────────────────────────────────────────────────

static void test_lebesgue_integral() {
    const double si = mt::integral_simple(
        {1, 2}, {{0, 0.5}, {0.5, 1.0}});
    CHECK(near(si, 1.5, 1e-12), "∫φ dλ = 1·0.5 + 2·0.5 = 1.5");

    const mt::NonnegIntegralResult ni = mt::integral_nonnegative("x**2", 0, 1);
    CHECK(near(ni.integral, 1.0 / 3.0, 1e-3), "∫₀¹ x² dx ≈ 1/3");

    const mt::GeneralIntegralResult gi = mt::integral_general("x", -1, 1);
    CHECK(near(gi.integral, 0.0, 1e-3), "∫₋₁¹ x dx ≈ 0(正部=负部)");
    CHECK(near(gi.pos, 0.5, 1e-2), "正部 ∫ x⁺ dx = 1/2");

    const mt::ZeroSetResult zs =
        mt::integral_zero_set_independent("x**2", "x**2", 0, 1);
    CHECK(zs.are_equal, "零测集无关性:∫x² = ∫x²");
}

// ── convergence_theorems ─────────────────────────────────────────────────────

static void test_convergence_theorems() {
    const mt::MonotoneResult mono = mt::monotone_convergence(
        "1 - exp(-n*x)", "1", {1, 2, 5, 10, 50, 200}, 0, 2);
    CHECK(mono.converged, "单调收敛定理:lim ∫f_n = ∫f");

    const mt::FatouResult fatou =
        mt::fatou_lemma("x**(1/n)", {1, 2, 5, 10, 20}, 0, 1);
    CHECK(fatou.inequality_holds, "法图引理:∫liminf f_n ≤ liminf ∫f_n");

    const mt::DominatedResult dom = mt::dominated_convergence(
        "sin(n*x)/(n + x**2)", "0", "1/(1+x**2)", {1, 2, 5, 10, 50}, 0, 1);
    CHECK(dom.dominated, "控制收敛:|f_n| ≤ g");
    CHECK(dom.difference < 0.01, "控制收敛:DCT 交换成立");
}

// ── probability_measure ──────────────────────────────────────────────────────

static void test_probability_measure() {
    const mt::ProbabilitySpaceResult ps = mt::probability_space({1, 2, 3, 4, 5, 6});
    CHECK(ps.is_probability_space, "probability_space(dice):ΣP = 1");

    const mt::RandomVariableResult rv = mt::random_variable("identity", {1, 2, 3, 4, 5, 6});
    CHECK(rv.values.size() == 6 && near(rv.values[0], 1.0, 1e-12) &&
              near(rv.values[5], 6.0, 1e-12),
          "random_variable(identity) → [1..6]");

    const double e1 = mt::expectation_normal("x", 0.0, 1.0);
    CHECK(std::abs(e1) < 0.01, "E[x] 下 N(0,1) ≈ 0");

    const double e2 = mt::expectation_uniform("x", 0.0, 2.0);
    CHECK(near(e2, 1.0, 1e-9), "E[x] 下 U(0,2) = 1");

    const mt::ConditionalExpectationResult ce =
        mt::conditional_expectation("x", {1, 2, 3, 4, 5, 6},
                                    {{2, 4, 6}, {1, 3, 5}});
    CHECK(ce.ce_per_atom.size() == 2 &&
              near(ce.ce_per_atom[0], 4.0, 1e-9) &&
              near(ce.ce_per_atom[1], 3.0, 1e-9),
          "条件期望:偶原子=4,奇原子=3");

    CHECK(!mt::independence_check({1}, {2}, {1, 2, 3, 4, 5, 6},
                                  {1.0 / 6, 1.0 / 6, 1.0 / 6, 1.0 / 6, 1.0 / 6, 1.0 / 6}),
          "独立判定:单点事件 P(A∩B)=0 ≠ P(A)P(B)");
}

// ── product_measure ──────────────────────────────────────────────────────────

static void test_product_measure() {
    CHECK(near(mt::product_measure(1, 1, 0, 1, 0, 1), 1.0, 1e-12),
          "λ×λ([0,1]×[0,1]) = 1");
    CHECK(near(mt::product_measure(1, 1, 0, 2, 0, 3), 6.0, 1e-12),
          "λ×λ([0,2]×[0,3]) = 6");

    const mt::FubiniResult f1 = mt::fubini_theorem("x*y", 0, 1, 0, 1);
    CHECK(f1.fubini_holds && near(f1.xy_order, 0.25, 1e-3),
          "Fubini(x*y):两次序一致 ≈ 1/4");

    const mt::FubiniResult f2 = mt::fubini_theorem("x**2 + y**2", 0, 1, 0, 1);
    CHECK(f2.fubini_holds, "Fubini(x²+y²):成立");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[8192];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("is_sigma_algebra"), "function_exists(is_sigma_algebra)");
    CHECK(function_exists("lebesgue_measure"), "function_exists(lebesgue_measure)");
    CHECK(function_exists("fubini_theorem"), "function_exists(fubini_theorem)");
    CHECK(function_exists("meas_expectation"), "function_exists(meas_expectation)");

    const std::string sig = call("is_sigma_algebra",
        "{\"collection\":[[],[1,2,3],[1],[2,3],[2],[1,3],[3],[1,2]],\"X\":[1,2,3]}");
    CHECK(sig.find("\"isSigmaAlgebra\":true") != std::string::npos,
          "math_call is_sigma_algebra(幂集) → true");

    const std::string gen = call("generate_sigma_algebra",
                                 "{\"generators\":[[1]],\"X\":[1,2]}");
    CHECK(gen.find("\"count\":4") != std::string::npos,
          "math_call generate_sigma_algebra → count=4");

    const std::string lm = call("lebesgue_measure", "{\"E\":[0,1]}");
    CHECK(lm == "{\"isError\":false,\"value\":1}", "math_call lebesgue_measure([0,1]) → 1");

    const std::string lq = call("lebesgue_measure", "{\"E\":\"Q\"}");
    CHECK(lq.find("\"value\":0") != std::string::npos, "math_call lebesgue_measure(Q) → 0");

    const std::string nf = call("integral_nonnegative", "{\"f\":\"x**2\",\"range\":[0,1]}");
    const mf::json::Value nfv = mf::json::Value::parse(nf);
    CHECK(near(nfv["value"]["integral"].as_double(), 1.0 / 3.0, 1e-3),
          "math_call integral_nonnegative(x²) ≈ 1/3");

    const std::string ce = call("conditional_expectation",
        "{\"X\":\"x\",\"sub_sigma_algebra\":\"parity\",\"Omega\":\"finite:6\"}");
    const mf::json::Value cev = mf::json::Value::parse(ce);
    CHECK(cev["value"]["cePerAtom"].size() == 2 &&
              near(cev["value"]["cePerAtom"].at(0).as_double(), 4.0, 1e-9),
          "math_call conditional_expectation(parity) → 偶=4");

    const std::string fub = call("fubini_theorem",
                                 "{\"f\":\"x*y\",\"range\":[0,1,0,1]}");
    const mf::json::Value fubv = mf::json::Value::parse(fub);
    CHECK(fubv["value"]["fubiniHolds"].as_bool() &&
              near(fubv["value"]["xyOrder"].as_double(), 0.25, 1e-3),
          "math_call fubini_theorem(x*y) → 成立");
}

int main() {
    std::system("chcp 65001 > nul");
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("===== measure_theory 内核测试 =====\n");
    test_set_systems();
    test_measurable_functions();
    test_measure_construction();
    test_lebesgue_integral();
    test_convergence_theorems();
    test_probability_measure();
    test_product_measure();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
