// probability_api.cpp — probability 包 JSON 分发层。
//
// 注册 40 个 action:probability_space + random_variable + expectations +
// distributions + statistics + limits_theorems + hypothesis_test +
// nonparametric + anova + regression + time_series。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "probability_space.h"
#include "random_variable.h"
#include "expectations.h"
#include "distributions.h"
#include "statistics.h"
#include "limits_theorems.h"
#include "hypothesis_test.h"
#include "nonparametric.h"
#include "anova.h"
#include "regression.h"
#include "time_series.h"

#include <cstdint>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::probability;
using mf::api::make_handler;
using mf::api::get_int;
using mf::api::get_int_opt;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_bool_opt;
using mf::api::get_double_array;

// 二维 double 数组(分组数据)。
// 注意：这里**允许**各行长度不同（ANOVA / Kruskal-Wallis 的各组样本数本来就可以不等），
// 只拒绝空输入 —— 空数组传到下游统计函数里会变成非法下标访问。
std::vector<std::vector<double>> get_matrix(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少数组参数 ") + key);
    const Value& arr = args[key];
    if (arr.size() == 0)
        throw std::invalid_argument(std::string("数组参数 ") + key +
                                    " 不能为空（应为 [[1,2],[3,4]] 或各组数据的二维数组）");
    std::vector<std::vector<double>> out;
    for (std::size_t i = 0; i < arr.size(); ++i) {
        std::vector<double> row;
        for (std::size_t j = 0; j < arr.at(i).size(); ++j)
            row.push_back(arr.at(i).at(j).as_double());
        if (row.empty())
            throw std::invalid_argument(std::string("数组参数 ") + key + " 的第 " +
                                        std::to_string(i + 1) + " 组没有数据");
        out.push_back(std::move(row));
    }
    return out;
}

// 区间 [lo,hi]。
void get_range(const Value& args, double& lo, double& hi) {
    lo = get_double_opt(args, "a", 0.0);
    hi = get_double_opt(args, "b", 1.0);
    if (args.has("range") && args["range"].is_array() && args["range"].size() == 2) {
        lo = args["range"].at(0).as_double();
        hi = args["range"].at(1).as_double();
    }
}

// 从对象中取首个命中的键对应的 double。
double pick(const Value& obj, const std::vector<std::string>& keys,
            const std::string& err) {
    for (const auto& k : keys)
        if (obj.has(k)) return obj[k].as_double();
    throw std::invalid_argument(err);
}

Value to_darr(const std::vector<double>& v) {
    Value arr = Value::make_array();
    for (double x : v) arr.push_back(Value(x));
    return arr;
}

Value dist_to_json(const DistributionResult& r) {
    Value obj = Value::make_object();
    obj.set("name", Value(r.name));
    obj.set("mean", Value(r.mean));
    obj.set("variance", Value(r.variance));
    obj.set("std", Value(r.std));
    obj.set("pdf", Value(r.pdf));
    Value pk = Value::make_array(), pv = Value::make_array();
    for (long long k : r.pmf_keys) pk.push_back(Value(k));
    for (double v : r.pmf_values) pv.push_back(Value(v));
    obj.set("pmfKeys", pk);
    obj.set("pmfValues", pv);
    return obj;
}

Value hyp_to_json(const HypothesisResult& r) {
    Value obj = Value::make_object();
    obj.set("statistic", Value(r.statistic));
    obj.set("p_value", Value(r.p_value));
    obj.set("df", Value(r.df));
    obj.set("alpha", Value(r.alpha));
    obj.set("critical_value", Value(r.critical_value));
    obj.set("reject_H0", Value(r.reject_H0));
    obj.set("alternative", Value(r.alternative));
    return obj;
}

void register_all() {
    using mf::registry::register_function;

    // ── probability_space ───────────────────────────────────────────────────
    register_function("conditional_probability", make_handler([](const Value& args) {
        const std::string A = get_string(args, "A");
        const std::string B = get_string(args, "B");
        const Value& P = args["P"];
        const double p_ab = pick(P, {A + "_and_" + B, A + "∩" + B, "A_and_B", "A∩B"},
                                 "缺少交集概率 (A_and_B 或 A∩B)");
        double p_b;
        if (P.has(B)) p_b = P[B].as_double();
        else if (P.has("B")) p_b = P["B"].as_double();
        else throw std::invalid_argument("缺少 P(B) 的值");
        return Value(conditional_probability(p_ab, p_b));
    }));

    register_function("is_independent", make_handler([](const Value& args) {
        const std::string A = get_string(args, "A");
        const std::string B = get_string(args, "B");
        const Value& P = args["P"];
        double p_a;
        if (P.has(A)) p_a = P[A].as_double();
        else if (P.has("A")) p_a = P["A"].as_double();
        else throw std::invalid_argument("缺少 P(A) 的值");
        double p_b;
        if (P.has(B)) p_b = P[B].as_double();
        else if (P.has("B")) p_b = P["B"].as_double();
        else throw std::invalid_argument("缺少 P(B) 的值");
        const double p_ab = pick(P, {A + "_and_" + B, A + "∩" + B, "A_and_B", "A∩B"},
                                 "缺少交集概率");
        return Value(is_independent(p_a, p_b, p_ab));
    }));

    register_function("total_probability", make_handler([](const Value& args) {
        const Value& events = args["events"];
        const Value& P = args["P"];
        const std::string cond = get_string(args, "condition");
        std::vector<double> prob_events, cond_probs;
        for (const auto& ev : events.keys()) {
            prob_events.push_back(events[ev].as_double());
            double pc;
            if (P.has(cond + "|" + ev)) pc = P[cond + "|" + ev].as_double();
            else if (P.has(cond + "_given_" + ev)) pc = P[cond + "_given_" + ev].as_double();
            else throw std::invalid_argument("缺少条件概率 P(" + cond + "|" + ev + ")");
            cond_probs.push_back(pc);
        }
        return Value(total_probability(prob_events, cond_probs));
    }));

    register_function("bayes_theorem", make_handler([](const Value& args) {
        const Value& events = args["events"];
        const Value& P = args["P"];
        const std::string evi = get_string(args, "evidence");
        std::vector<std::string> names;
        std::vector<double> prob_events, cond_probs;
        for (const auto& ev : events.keys()) {
            names.push_back(ev);
            prob_events.push_back(events[ev].as_double());
            double pc;
            if (P.has(evi + "|" + ev)) pc = P[evi + "|" + ev].as_double();
            else if (P.has(evi + "_given_" + ev)) pc = P[evi + "_given_" + ev].as_double();
            else throw std::invalid_argument("缺少条件概率 P(" + evi + "|" + ev + ")");
            cond_probs.push_back(pc);
        }
        const auto post = bayes_posterior(prob_events, cond_probs);
        Value obj = Value::make_object();
        for (std::size_t i = 0; i < names.size(); ++i) obj.set(names[i], Value(post[i]));
        return obj;
    }));

    // ── random_variable ─────────────────────────────────────────────────────
    register_function("distribution_function", make_handler([](const Value& args) {
        const std::vector<double> data = get_double_array(args, "data");
        if (args.has("x")) return Value(distribution_function(data, get_double(args, "x")));
        const EmpiricalCdfResult r = distribution_function_full(data);
        Value obj = Value::make_object();
        obj.set("x", to_darr(r.x_values));
        obj.set("F", to_darr(r.f_values));
        return obj;
    }));

    register_function("pmf", make_handler([](const Value& args) {
        const PmfResult r = pmf_normalize(get_double_array(args, "probs"));
        Value obj = Value::make_object();
        obj.set("probabilities", to_darr(r.probabilities));
        obj.set("wasNormalized", Value(r.was_normalized));
        return obj;
    }));

    register_function("pdf", make_handler([](const Value& args) {
        return Value(pdf_expression(get_string(args, "expr"),
                                    get_string_opt(args, "var", "x")));
    }));

    register_function("expectation_rv", make_handler([](const Value& args) {
        const std::string g = get_string_opt(args, "expr", "x");
        if (args.has("pmf_data")) {
            const Value& pm = args["pmf_data"];
            return Value(expectation_discrete_g(
                get_double_array(pm, "values"), get_double_array(pm, "probs"), g));
        }
        double a, b;
        get_range(args, a, b);
        return Value(expectation_continuous(g, a, b));
    }));

    // ── expectations ────────────────────────────────────────────────────────
    register_function("prob_expectation", make_handler([](const Value& args) {
        if (args.has("data")) return Value(expectation_sample(get_double_array(args, "data")));
        if (args.has("pmf_data")) {
            const Value& pm = args["pmf_data"];
            return Value(expectation_pmf(get_double_array(pm, "values"),
                                         get_double_array(pm, "probs")));
        }
        double a, b;
        get_range(args, a, b);
        return Value(expectation_continuous(get_string(args, "expr"), a, b));
    }));

    register_function("variance", make_handler([](const Value& args) {
        if (args.has("data"))
            return Value(variance_sample(get_double_array(args, "data"),
                                         get_int_opt(args, "ddof", 1)));
        if (args.has("pmf_data")) {
            const Value& pm = args["pmf_data"];
            return Value(variance_pmf(get_double_array(pm, "values"),
                                      get_double_array(pm, "probs")));
        }
        double a, b;
        get_range(args, a, b);
        return Value(variance_continuous(get_string(args, "expr"), a, b));
    }));

    register_function("covariance", make_handler([](const Value& args) {
        if (args.has("joint")) {
            const Value& j = args["joint"];
            const Value& vals = j["values"];
            const std::vector<double> probs = get_double_array(j, "probs");
            std::vector<double> xv, yv;
            for (std::size_t i = 0; i < vals.size(); ++i) {
                xv.push_back(vals.at(i).at(0).as_double());
                yv.push_back(vals.at(i).at(1).as_double());
            }
            return Value(covariance_joint(xv, yv, probs));
        }
        return Value(covariance_sample(get_double_array(args, "X"),
                                       get_double_array(args, "Y")));
    }));

    register_function("correlation_coefficient", make_handler([](const Value& args) {
        if (args.has("joint")) {
            const Value& j = args["joint"];
            const Value& vals = j["values"];
            const std::vector<double> probs = get_double_array(j, "probs");
            std::vector<double> xv, yv;
            for (std::size_t i = 0; i < vals.size(); ++i) {
                xv.push_back(vals.at(i).at(0).as_double());
                yv.push_back(vals.at(i).at(1).as_double());
            }
            return Value(correlation_joint(xv, yv, probs));
        }
        return Value(correlation_sample(get_double_array(args, "X"),
                                        get_double_array(args, "Y")));
    }));

    // ── distributions ───────────────────────────────────────────────────────
    register_function("bernoulli", make_handler([](const Value& args) {
        return dist_to_json(bernoulli(get_double(args, "p")));
    }));
    register_function("binomial", make_handler([](const Value& args) {
        return dist_to_json(binomial(get_int(args, "n"), get_double(args, "p")));
    }));
    register_function("poisson", make_handler([](const Value& args) {
        return dist_to_json(poisson(get_double(args, "lambda")));
    }));
    register_function("uniform", make_handler([](const Value& args) {
        return dist_to_json(uniform_dist(get_double(args, "a"), get_double(args, "b")));
    }));
    register_function("exponential", make_handler([](const Value& args) {
        return dist_to_json(exponential_dist(get_double(args, "lambda")));
    }));
    register_function("normal", make_handler([](const Value& args) {
        return dist_to_json(normal_dist(get_double_opt(args, "mu", 0.0),
                                        get_double_opt(args, "sigma", 1.0)));
    }));

    // ── statistics ──────────────────────────────────────────────────────────
    register_function("sample_mean", make_handler([](const Value& args) {
        return Value(sample_mean(get_double_array(args, "data")));
    }));
    register_function("sample_variance", make_handler([](const Value& args) {
        return Value(sample_variance(get_double_array(args, "data"),
                                     get_int_opt(args, "ddof", 1)));
    }));
    register_function("moment_estimate", make_handler([](const Value& args) {
        const MomentEstimateResult r =
            moment_estimate(get_double_array(args, "data"), get_string(args, "dist"));
        Value obj = Value::make_object();
        obj.set("dist", Value(r.dist));
        obj.set("valid", Value(r.valid));
        if (r.dist == "normal") {
            obj.set("mu_hat", Value(r.mu_hat));
            obj.set("sigma_hat", Value(r.sigma_hat));
        } else if (r.dist == "exponential" || r.dist == "poisson") {
            obj.set("lambda_hat", Value(r.lambda_hat));
        } else if (r.dist == "uniform") {
            obj.set("a_hat", Value(r.a_hat));
            obj.set("b_hat", Value(r.b_hat));
        }
        return obj;
    }));
    register_function("mle", make_handler([](const Value& args) {
        const MleResult r = mle(get_double_array(args, "data"), get_string(args, "dist"));
        Value obj = Value::make_object();
        obj.set("dist", Value(r.dist));
        obj.set("valid", Value(r.valid));
        if (r.dist == "normal") {
            obj.set("mu_mle", Value(r.mu_mle));
            obj.set("sigma_mle", Value(r.sigma_mle));
        } else if (r.dist == "exponential" || r.dist == "poisson") {
            obj.set("lambda_mle", Value(r.lambda_mle));
        }
        return obj;
    }));
    register_function("confidence_interval", make_handler([](const Value& args) {
        const ConfidenceIntervalResult r = confidence_interval(
            get_double_array(args, "data"), get_double_opt(args, "confidence", 0.95));
        Value obj = Value::make_object();
        obj.set("lower", Value(r.lower));
        obj.set("upper", Value(r.upper));
        obj.set("mean", Value(r.mean));
        obj.set("margin", Value(r.margin));
        obj.set("confidence", Value(r.confidence));
        obj.set("n", Value(r.n));
        return obj;
    }));

    // ── limits_theorems ─────────────────────────────────────────────────────
    register_function("law_of_large_numbers", make_handler([](const Value& args) {
        const LlnResult r = law_of_large_numbers(
            get_double(args, "sample_mean"), get_double(args, "true_mean"),
            get_int(args, "n"));
        Value obj = Value::make_object();
        obj.set("deviation", Value(r.deviation));
        obj.set("threshold", Value(r.threshold));
        obj.set("converged", Value(r.converged));
        return obj;
    }));
    register_function("central_limit_theorem", make_handler([](const Value& args) {
        const CltResult r = central_limit_theorem(
            get_double_array(args, "sample"), get_double(args, "mu"),
            get_double(args, "sigma"), get_int(args, "n"));
        Value obj = Value::make_object();
        obj.set("sample_mean", Value(r.sample_mean));
        obj.set("Z", Value(r.Z));
        obj.set("p_value", Value(r.p_value));
        obj.set("standard_error", Value(r.standard_error));
        obj.set("approx_normal", Value(r.approx_normal));
        return obj;
    }));

    // ── hypothesis_test ─────────────────────────────────────────────────────
    register_function("z_test", make_handler([](const Value& args) {
        return hyp_to_json(z_test(
            get_double(args, "sample_mean"), get_double(args, "mu0"),
            get_double(args, "sigma"), get_int(args, "n"),
            get_double_opt(args, "alpha", 0.05),
            get_string_opt(args, "alternative", "two-sided")));
    }));
    register_function("t_test", make_handler([](const Value& args) {
        return hyp_to_json(t_test(
            get_double_array(args, "data"), get_double(args, "mu0"),
            get_double_opt(args, "alpha", 0.05),
            get_string_opt(args, "alternative", "two-sided")));
    }));
    register_function("chi_square_test", make_handler([](const Value& args) {
        const ChiSquareResult r = chi_square_test(
            get_double_array(args, "observed"), get_double_array(args, "expected"));
        Value obj = Value::make_object();
        obj.set("chi2", Value(r.chi2));
        obj.set("df", Value(r.df));
        obj.set("p_value", Value(r.p_value));
        obj.set("contributions", to_darr(r.contributions));
        obj.set("reject_H0", Value(r.reject_H0));
        return obj;
    }));
    register_function("p_value", make_handler([](const Value& args) {
        return Value(p_value(get_double(args, "test_statistic"),
                             get_string(args, "dist"), get_int_opt(args, "df", 1),
                             get_string_opt(args, "alternative", "two-sided")));
    }));

    // ── nonparametric ───────────────────────────────────────────────────────
    register_function("mann_whitney_u", make_handler([](const Value& args) {
        const NonparametricResult r = mann_whitney_u(
            get_double_array(args, "group1"), get_double_array(args, "group2"),
            get_string_opt(args, "alternative", "two-sided"),
            get_double_opt(args, "alpha", 0.05));
        Value obj = Value::make_object();
        obj.set("U_statistic", Value(r.statistic));
        obj.set("p_value", Value(r.p_value));
        obj.set("significant", Value(r.significant));
        obj.set("n1", Value(r.n1));
        obj.set("n2", Value(r.n2));
        obj.set("median1", Value(r.median1));
        obj.set("median2", Value(r.median2));
        return obj;
    }));
    register_function("kruskal_wallis", make_handler([](const Value& args) {
        const KruskalWallisResult r =
            kruskal_wallis(get_matrix(args, "groups"), get_double_opt(args, "alpha", 0.05));
        Value obj = Value::make_object();
        obj.set("H_statistic", Value(r.H));
        obj.set("p_value", Value(r.p_value));
        obj.set("significant", Value(r.significant));
        obj.set("group_medians", to_darr(r.group_medians));
        obj.set("mean_ranks", to_darr(r.mean_ranks));
        return obj;
    }));
    register_function("wilcoxon_signed_rank", make_handler([](const Value& args) {
        const NonparametricResult r = wilcoxon_signed_rank(
            get_double_array(args, "group1"), get_double_array(args, "group2"),
            get_double_opt(args, "mu", 0.0),
            get_string_opt(args, "alternative", "two-sided"),
            get_double_opt(args, "alpha", 0.05));
        Value obj = Value::make_object();
        obj.set("W_statistic", Value(r.statistic));
        obj.set("p_value", Value(r.p_value));
        obj.set("significant", Value(r.significant));
        obj.set("test_type", Value(r.test_type));
        obj.set("n", Value(r.n1));
        return obj;
    }));

    // ── anova ───────────────────────────────────────────────────────────────
    register_function("one_way_anova", make_handler([](const Value& args) {
        const AnovaResult r =
            one_way_anova(get_matrix(args, "groups"), get_double_opt(args, "alpha", 0.05));
        Value obj = Value::make_object();
        obj.set("F_statistic", Value(r.F));
        obj.set("p_value", Value(r.p_value));
        obj.set("significant", Value(r.significant));
        obj.set("ss_between", Value(r.ss_between));
        obj.set("ss_within", Value(r.ss_within));
        obj.set("ms_between", Value(r.ms_between));
        obj.set("ms_within", Value(r.ms_within));
        obj.set("df_between", Value(r.df_between));
        obj.set("df_within", Value(r.df_within));
        obj.set("group_means", to_darr(r.group_means));
        return obj;
    }));
    register_function("two_way_anova", make_handler([](const Value& args) {
        const TwoWayAnovaResult r =
            two_way_anova(get_matrix(args, "data"), get_double_opt(args, "alpha", 0.05));
        Value obj = Value::make_object();
        obj.set("valid", Value(r.valid));
        Value fa = Value::make_object(), fb = Value::make_object();
        fa.set("F", Value(r.F_A));
        fa.set("p", Value(r.p_A));
        fa.set("significant", Value(r.significant_A));
        fb.set("F", Value(r.F_B));
        fb.set("p", Value(r.p_B));
        fb.set("significant", Value(r.significant_B));
        obj.set("factor_A", fa);
        obj.set("factor_B", fb);
        return obj;
    }));

    // ── regression ──────────────────────────────────────────────────────────
    register_function("linear_regression", make_handler([](const Value& args) {
        const RegressionResult r = linear_regression(
            get_double_array(args, "x"), get_double_array(args, "y"));
        Value obj = Value::make_object();
        obj.set("slope", Value(r.slope));
        obj.set("intercept", Value(r.intercept));
        obj.set("r_squared", Value(r.r_squared));
        obj.set("n", Value(r.n));
        return obj;
    }));
    register_function("predict", make_handler([](const Value& args) {
        const double slope = get_double(args, "slope");
        const double intercept = get_double(args, "intercept");
        if (args.has("x") && args["x"].is_number())
            return Value(predict_linear(slope, intercept, args["x"].as_double()));
        return to_darr(predict_linear_many(slope, intercept, get_double_array(args, "x")));
    }));
    register_function("residuals", make_handler([](const Value& args) {
        const ResidualResult r = residuals_linear(
            get_double(args, "slope"), get_double(args, "intercept"),
            get_double_array(args, "x"), get_double_array(args, "y"));
        Value obj = Value::make_object();
        obj.set("residuals", to_darr(r.residuals));
        obj.set("SSE", Value(r.SSE));
        obj.set("MSE", Value(r.MSE));
        obj.set("n", Value(r.n));
        return obj;
    }));

    // ── time_series ─────────────────────────────────────────────────────────
    register_function("moving_average", make_handler([](const Value& args) {
        const MovingAverageResult r = moving_average(
            get_double_array(args, "data"), get_int_opt(args, "window", 3));
        Value obj = Value::make_object();
        obj.set("smoothed", to_darr(r.smoothed));
        obj.set("window", Value(r.window));
        obj.set("n", Value(r.n));
        return obj;
    }));
    register_function("exp_smoothing", make_handler([](const Value& args) {
        const ExpSmoothingResult r = exp_smoothing(
            get_double_array(args, "data"), get_double_opt(args, "alpha", 0.3));
        Value obj = Value::make_object();
        obj.set("smoothed", to_darr(r.smoothed));
        obj.set("forecast", Value(r.forecast));
        obj.set("alpha", Value(r.alpha));
        return obj;
    }));
    register_function("linear_trend", make_handler([](const Value& args) {
        const LinearTrendResult r = linear_trend(
            get_double_array(args, "data"), get_int_opt(args, "forecast_steps", 3));
        Value obj = Value::make_object();
        obj.set("slope", Value(r.slope));
        obj.set("intercept", Value(r.intercept));
        obj.set("r_squared", Value(r.r_squared));
        obj.set("forecasts", to_darr(r.forecasts));
        obj.set("trend", to_darr(r.trend));
        return obj;
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_probability_registrar;

}  // namespace
