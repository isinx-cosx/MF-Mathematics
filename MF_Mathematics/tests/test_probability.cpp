// test_probability.cpp — probability 包内核 + JSON 测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "api.h"
#include "json.hpp"
#include "probability/anova.h"
#include "probability/distributions.h"
#include "probability/expectations.h"
#include "probability/hypothesis_test.h"
#include "probability/limits_theorems.h"
#include "probability/nonparametric.h"
#include "probability/probability_space.h"
#include "probability/random_variable.h"
#include "probability/regression.h"
#include "probability/statistics.h"
#include "probability/time_series.h"

namespace pr = mf::probability;

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

// ── probability_space ────────────────────────────────────────────────────────

static void test_probability_space() {
    CHECK(near(pr::conditional_probability(0.3, 0.5), 0.6, 0.01),
          "条件概率 P(A∩B)/P(B) = 0.3/0.5 = 0.6");
    CHECK(pr::is_independent(0.5, 0.4, 0.2), "独立: P(A∩B)=P(A)P(B)");
    CHECK(!pr::is_independent(0.5, 0.4, 0.1), "不独立: P(A∩B)≠P(A)P(B)");
    CHECK(near(pr::total_probability({0.6, 0.4}, {0.8, 0.3}), 0.6, 0.01),
          "全概率 = 0.6·0.8 + 0.4·0.3 = 0.6");
    const auto post = pr::bayes_posterior({0.6, 0.4}, {0.8, 0.3});
    CHECK(near(post[0], 0.8, 0.01) && near(post[1], 0.2, 0.01),
          "贝叶斯后验 P(B1|A)=0.8, P(B2|A)=0.2");
}

// ── random_variable ──────────────────────────────────────────────────────────

static void test_random_variable() {
    CHECK(near(pr::distribution_function({1, 3, 5, 7, 9}, 5), 0.6, 0.01),
          "经验分布 F(5) = 3/5 = 0.6");
    const pr::EmpiricalCdfResult cdf = pr::distribution_function_full({3, 1, 2});
    CHECK(cdf.x_values.size() == 3 && near(cdf.x_values[0], 1.0, 1e-12) &&
              near(cdf.f_values[2], 1.0, 1e-12),
          "完整经验分布排序 + 累计比例");

    const pr::PmfResult pm = pr::pmf_normalize({0.5, 0.5});
    CHECK(!pm.was_normalized && near(pm.probabilities[0], 0.5, 1e-12),
          "合法分布列不归一化");
    const pr::PmfResult pm2 = pr::pmf_normalize({1, 1});
    CHECK(pm2.was_normalized && near(pm2.probabilities[1], 0.5, 1e-12),
          "概率和≠1 时归一化");

    CHECK(pr::pdf_expression("exp(-x)") == "exp(-x)", "pdf 表达式验证");

    CHECK(near(pr::expectation_discrete_g({0, 1}, {0.5, 0.5}, "x"), 0.5, 0.01),
          "离散期望 E[X] = 0.5");
    CHECK(near(pr::expectation_continuous("x", 0, 1), 0.5, 0.01),
          "连续期望 ∫₀¹ x dx = 0.5");
}

// ── expectations ─────────────────────────────────────────────────────────────

static void test_expectations() {
    CHECK(near(pr::expectation_sample({1, 2, 3, 4, 5}), 3.0, 0.01), "样本均值 = 3");
    CHECK(near(pr::variance_sample({1, 2, 3, 4, 5}, 1), 2.5, 0.01),
          "样本方差 (ddof=1) = 2.5");
    CHECK(near(pr::variance_sample({1, 2, 3, 4, 5}, 0), 2.0, 0.01),
          "有偏方差 (ddof=0) = 2.0");
    CHECK(near(pr::expectation_pmf({0, 1}, {0.5, 0.5}), 0.5, 0.01), "离散期望 = 0.5");
    CHECK(near(pr::variance_pmf({0, 1}, {0.5, 0.5}), 0.25, 0.01), "离散方差 = 0.25");
    CHECK(near(pr::variance_continuous("1", 0, 1), 1.0 / 12.0, 0.01),
          "U(0,1) 方差 = 1/12");
    CHECK(pr::covariance_sample({1, 2, 3}, {2, 4, 6}) > 0, "协方差为正");
    CHECK(near(pr::correlation_sample({1, 2, 3}, {2, 4, 6}), 1.0, 0.01),
          "完全正相关 ρ = 1");
    CHECK(near(pr::correlation_sample({1, 2, 3}, {3, 2, 1}), -1.0, 0.01),
          "完全负相关 ρ = -1");
}

// ── distributions ────────────────────────────────────────────────────────────

static void test_distributions() {
    const pr::DistributionResult b1 = pr::bernoulli(0.3);
    CHECK(near(b1.mean, 0.3, 0.01) && near(b1.variance, 0.21, 0.01),
          "Bernoulli(0.3): E=0.3, Var=0.21");
    const pr::DistributionResult b2 = pr::binomial(10, 0.5);
    CHECK(near(b2.mean, 5.0, 0.01), "Binomial(10,0.5): E=5");
    const pr::DistributionResult p3 = pr::poisson(3.0);
    CHECK(near(p3.mean, 3.0, 0.01), "Poisson(3): E=3");
    const pr::DistributionResult u4 = pr::uniform_dist(0, 10);
    CHECK(near(u4.mean, 5.0, 0.01), "Uniform(0,10): E=5");
    const pr::DistributionResult e5 = pr::exponential_dist(2.0);
    CHECK(near(e5.mean, 0.5, 0.01), "Exp(2): E=0.5");
    const pr::DistributionResult n6 = pr::normal_dist(0, 1);
    CHECK(near(n6.mean, 0.0, 1e-12) && near(n6.variance, 1.0, 1e-12),
          "N(0,1): E=0, Var=1");
}

// ── statistics ───────────────────────────────────────────────────────────────

static void test_statistics() {
    CHECK(near(pr::sample_mean({1, 2, 3, 4, 5}), 3.0, 0.01), "样本均值 = 3");
    CHECK(near(pr::sample_variance({1, 2, 3, 4, 5}), 2.5, 0.01), "样本方差 = 2.5");

    const pr::MomentEstimateResult me = pr::moment_estimate({1, 2, 3, 4, 5}, "normal");
    CHECK(me.valid && near(me.mu_hat, 3.0, 0.01) && near(me.sigma_hat, std::sqrt(2.0), 0.01),
          "正态矩估计 μ̂=3, σ̂=√2");
    const pr::MomentEstimateResult mee = pr::moment_estimate({1, 2, 3}, "exponential");
    CHECK(mee.valid && near(mee.lambda_hat, 0.5, 0.01), "指数矩估计 λ̂=0.5");

    const pr::MleResult mle = pr::mle({1, 2, 3, 4, 5}, "normal");
    CHECK(mle.valid && near(mle.mu_mle, 3.0, 0.01), "正态 MLE μ̂=3");

    const pr::ConfidenceIntervalResult ci = pr::confidence_interval({1, 2, 3, 4, 5}, 0.95);
    CHECK(ci.lower < 3.0 && 3.0 < ci.upper, "95% 置信区间含样本均值");
    CHECK(ci.lower < ci.upper, "区间下界 < 上界");
}

// ── limits_theorems ──────────────────────────────────────────────────────────

static void test_limits_theorems() {
    const pr::LlnResult ll = pr::law_of_large_numbers(50.2, 50.0, 100);
    CHECK(ll.converged, "大数定律:偏差 0.2 < 阈值 0.3");
    const pr::LlnResult ll2 = pr::law_of_large_numbers(49.98, 50.0, 1000);
    CHECK(ll2.converged, "大数定律 (n=1000) 收敛");

    std::vector<double> sample(100, 50.0);
    sample[99] = 60.0;  // 样本均值 50.1
    const pr::CltResult clt = pr::central_limit_theorem(sample, 50.0, 10.0, 100);
    CHECK(clt.approx_normal && clt.p_value > 0.0 && clt.p_value <= 1.0,
          "中心极限定理:Z 与 p 值合理");
}

// ── hypothesis_test ──────────────────────────────────────────────────────────

static void test_hypothesis_test() {
    const pr::HypothesisResult z = pr::z_test(2.5, 3.0, 1.5, 100, 0.05, "two-sided");
    CHECK(near(z.statistic, -3.333, 0.01) && z.reject_H0, "Z 检验: Z=-3.33, 拒绝 H0");

    const pr::HypothesisResult t = pr::t_test({1, 2, 3, 4, 5}, 3.0, 0.05, "two-sided");
    CHECK(near(t.statistic, 0.0, 0.01) && !t.reject_H0, "t 检验: t=0, 不拒绝 H0");

    const pr::ChiSquareResult cs = pr::chi_square_test({50, 30, 20}, {40, 40, 20});
    CHECK(near(cs.chi2, 5.0, 0.01) && cs.df == 2, "卡方检验: χ²=5, df=2");

    CHECK(std::abs(pr::p_value(1.96, "normal", 1, "two-sided") - 0.05) < 0.01,
          "p 值: Z=1.96 → 0.05");
    CHECK(pr::p_value(3.0, "t", 4, "two-sided") < 0.05, "p 值: t(4)=3 显著");
}

// ── nonparametric ───────────────────────────────────────────────────────────

static void test_nonparametric() {
    const pr::NonparametricResult mw = pr::mann_whitney_u(
        {2, 3, 4, 5, 6}, {7, 8, 9, 10, 11}, "two-sided", 0.05);
    CHECK(near(mw.statistic, 0.0, 1e-9) && mw.significant,
          "Mann-Whitney U: 完全不重叠 → U=0, 显著");

    const pr::KruskalWallisResult kw =
        pr::kruskal_wallis({{2, 3, 4}, {5, 6, 7}, {8, 9, 10}}, 0.05);
    CHECK(kw.H > 0 && kw.p_value >= 0.0 && kw.p_value <= 1.0,
          "Kruskal-Wallis H 统计量合理");

    const pr::NonparametricResult w1 = pr::wilcoxon_signed_rank(
        {10, 12, 14, 15, 18}, {8, 9, 11, 13, 15}, 0.0, "two-sided", 0.05);
    CHECK(w1.test_type == "配对", "Wilcoxon 配对检验");

    const pr::NonparametricResult w2 = pr::wilcoxon_signed_rank(
        {1.5, 2.0, 2.5, 3.0, 3.5}, {}, 2.0, "two-sided", 0.05);
    CHECK(w2.test_type == "单样本", "Wilcoxon 单样本检验");
}

// ── anova ────────────────────────────────────────────────────────────────────

static void test_anova() {
    const pr::AnovaResult a1 =
        pr::one_way_anova({{2, 3, 4, 5}, {6, 7, 8, 9}, {1, 2, 2, 3}}, 0.05);
    CHECK(a1.F > 0 && a1.p_value >= 0.0 && a1.p_value <= 1.0,
          "单因素 ANOVA: F/p 合理");

    const pr::TwoWayAnovaResult a2 =
        pr::two_way_anova({{10, 12, 13}, {14, 15, 16}, {18, 20, 22}}, 0.05);
    CHECK(a2.valid && a2.F_A > 0 && a2.F_B > 0, "双因素 ANOVA 有效");
}

// ── regression ───────────────────────────────────────────────────────────────

static void test_regression() {
    const pr::RegressionResult r1 = pr::linear_regression({1, 2, 3}, {2, 4, 6});
    CHECK(near(r1.slope, 2.0, 0.01) && near(r1.intercept, 0.0, 0.01) &&
              near(r1.r_squared, 1.0, 0.01),
          "完美线性回归: y=2x, R²=1");
    CHECK(near(pr::predict_linear(2.0, 0.0, 4.0), 8.0, 0.01), "预测 x=4 → 8");
    const pr::ResidualResult res = pr::residuals_linear(2.0, 0.0, {1, 2, 3}, {2, 4, 6});
    CHECK(std::abs(res.SSE) < 0.01, "完美拟合残差 SSE≈0");

    const pr::RegressionResult r2 = pr::linear_regression({0, 1, 2, 3, 4}, {1, 3, 5, 7, 9});
    CHECK(near(r2.slope, 2.0, 0.01) && near(r2.intercept, 1.0, 0.01),
          "带截距回归: y=1+2x");
}

// ── time_series ──────────────────────────────────────────────────────────────

static void test_time_series() {
    const std::vector<double> data = {1, 2, 3, 4, 5, 6, 7};
    const pr::MovingAverageResult ma = pr::moving_average(data, 3);
    CHECK(ma.smoothed.size() == 5 && near(ma.smoothed[0], 2.0, 1e-9),
          "SMA(3): 长度 5, 首值 2");

    const pr::ExpSmoothingResult es = pr::exp_smoothing(data, 0.5);
    CHECK(std::abs(es.forecast - 7.0) < 2.0, "指数平滑预测接近 7");

    const pr::LinearTrendResult lt = pr::linear_trend(data, 2);
    CHECK(lt.r_squared > 0.9 && lt.forecasts.size() == 2, "线性趋势 R²>0.9");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[8192];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("z_test"), "function_exists(z_test)");
    CHECK(function_exists("linear_regression"), "function_exists(linear_regression)");
    CHECK(function_exists("confidence_interval"), "function_exists(confidence_interval)");

    const std::string df = call("distribution_function", "{\"data\":[1,3,5,7,9],\"x\":5}");
    CHECK(df.find("\"value\":0.6") != std::string::npos,
          "math_call distribution_function(F(5)) → 0.6");

    const std::string bn = call("binomial", "{\"n\":10,\"p\":0.5}");
    const mf::json::Value bnv = mf::json::Value::parse(bn);
    CHECK(near(bnv["value"]["mean"].as_double(), 5.0, 0.01),
          "math_call binomial(10,0.5) mean=5");

    const std::string ci = call("confidence_interval", "{\"data\":[1,2,3,4,5]}");
    const mf::json::Value civ = mf::json::Value::parse(ci);
    CHECK(civ["value"]["lower"].as_double() < 3.0 &&
              3.0 < civ["value"]["upper"].as_double(),
          "math_call confidence_interval 含均值");

    const std::string lr = call("linear_regression", "{\"x\":[1,2,3],\"y\":[2,4,6]}");
    const mf::json::Value lrv = mf::json::Value::parse(lr);
    CHECK(near(lrv["value"]["slope"].as_double(), 2.0, 0.01),
          "math_call linear_regression slope=2");

    const std::string ma = call("moving_average", "{\"data\":[1,2,3,4,5,6,7],\"window\":3}");
    const mf::json::Value mav = mf::json::Value::parse(ma);
    CHECK(mav["value"]["smoothed"].size() == 5, "math_call moving_average 长度 5");
}

int main() {
    std::system("chcp 65001 > nul");
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("===== probability 内核测试 =====\n");
    test_probability_space();
    test_random_variable();
    test_expectations();
    test_distributions();
    test_statistics();
    test_limits_theorems();
    test_hypothesis_test();
    test_nonparametric();
    test_anova();
    test_regression();
    test_time_series();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
