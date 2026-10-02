// real_analysis_api.cpp — real_analysis 包 JSON 分发层(differentiability 模块)。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "differentiability.h"
#include "sequence_limit.h"
#include "real_numbers.h"
#include "riemann_integral.h"
#include "function_limit.h"
#include "function_series.h"

#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::real_analysis;
using mf::api::make_handler;
using mf::api::get_int_opt;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_double_array;
using mf::api::get_int_bounded;
using mf::api::get_int_opt_bounded;

// 区间参数 [a, b],缺省 (0, 1)。
void get_interval(const Value& args, double& a, double& b) {
    if (args.is_object() && args.has("interval") && args["interval"].is_array() &&
        args["interval"].size() == 2) {
        a = args["interval"].at(0).as_double();
        b = args["interval"].at(1).as_double();
        return;
    }
    a = 0.0;
    b = 1.0;
}

void register_all() {
    using mf::registry::register_function;

    register_function("derivative_definition", make_handler([](const Value& args) {
        return Value(derivative_definition(get_string(args, "expr"),
                                           get_string_opt(args, "var", "x"),
                                           get_double_opt(args, "point", 0.0)));
    }));
    register_function("is_differentiable", make_handler([](const Value& args) {
        return Value(is_differentiable(get_string(args, "expr"),
                                       get_string_opt(args, "var", "x"),
                                       get_double_opt(args, "point", 0.0)));
    }));
    register_function("taylor_polynomial", make_handler([](const Value& args) {
        return Value(taylor_polynomial(get_string(args, "expr"),
                                       get_string_opt(args, "var", "x"),
                                       get_double_opt(args, "point", 0.0),
                                       get_int_opt_bounded(args, "n", 3, -9223372036854775807, 100, "项数")));
    }));
    register_function("taylor_remainder", make_handler([](const Value& args) {
        const bool has_xi = args.is_object() && args.has("xi");
        const TaylorRemainderResult r = taylor_remainder(
            get_string(args, "expr"), get_string_opt(args, "var", "x"),
            get_double_opt(args, "point", 0.0), get_int_opt_bounded(args, "n", 3, -9223372036854775807, 100, "项数"),
            has_xi, get_double_opt(args, "xi", 0.0));
        if (!r.has_xi) return Value(r.formula);
        Value obj = Value::make_object();
        obj.set("formula", Value(r.formula));
        obj.set("xi", Value(get_double_opt(args, "xi", 0.0)));
        obj.set("remainder_factor", Value(r.remainder_factor));
        return obj;
    }));
    register_function("real_rolle_theorem", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const RolleResult r = rolle_theorem(get_string(args, "expr"),
                                            get_string_opt(args, "var", "x"), a, b);
        if (!r.satisfies) return Value();
        return Value(r.xi);
    }));
    register_function("real_lagrange_theorem", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const LagrangeResult r = lagrange_theorem(get_string(args, "expr"),
                                                  get_string_opt(args, "var", "x"),
                                                  a, b);
        Value obj = Value::make_object();
        obj.set("xi", Value(r.xi));
        obj.set("secant_slope", Value(r.secant_slope));
        return obj;
    }));

    // ── sequence_limit ──────────────────────────────────────────────────────
    register_function("sequence_limit", make_handler([](const Value& args) {
        return Value(sequence_limit(get_string(args, "expr"),
                                    get_string_opt(args, "var", "n")));
    }));
    register_function("sequence_convergence", make_handler([](const Value& args) {
        const SequenceConvergenceResult r = sequence_convergence(
            get_string(args, "expr"), get_string_opt(args, "var", "n"));
        Value obj = Value::make_object();
        obj.set("convergent", Value(r.convergent));
        obj.set("description", Value(r.description));
        obj.set("limit", Value(r.limit_value));
        return obj;
    }));
    register_function("cauchy_criterion", make_handler([](const Value& args) {
        return Value(cauchy_criterion(get_string(args, "seq"),
                                      get_double_opt(args, "epsilon", 0.001),
                                      get_int_opt_bounded(args, "max_n", 1000, -9223372036854775807, 100000, "最大项数"),
                                      get_string_opt(args, "var", "n")));
    }));

    // ── real_numbers ────────────────────────────────────────────────────────
    register_function("dedekind_cut", make_handler([](const Value& args) {
        return Value(dedekind_cut(get_double_array(args, "setA"),
                                  get_double_array(args, "setB")));
    }));
    register_function("supremum", make_handler([](const Value& args) {
        bool has = false;
        double v;
        if (args.is_object() && args.has("set") && args["set"].is_array())
            v = supremum(get_double_array(args, "set"), has);
        else if (args.is_object() && args.has("set") && args["set"].is_string())
            v = supremum_desc(args["set"].as_string(), has);
        else
            throw std::invalid_argument("set 必须为数组或描述字符串");
        if (!has) {
            if (v == std::numeric_limits<double>::infinity()) return Value("∞");
            return Value();
        }
        return Value(v);
    }));
    register_function("infimum", make_handler([](const Value& args) {
        bool has = false;
        double v;
        if (args.is_object() && args.has("set") && args["set"].is_array())
            v = infimum(get_double_array(args, "set"), has);
        else if (args.is_object() && args.has("set") && args["set"].is_string())
            v = infimum_desc(args["set"].as_string(), has);
        else
            throw std::invalid_argument("set 必须为数组或描述字符串");
        if (!has) {
            if (v == -std::numeric_limits<double>::infinity()) return Value("-∞");
            return Value();
        }
        return Value(v);
    }));
    register_function("archimedean_property", make_handler([](const Value& args) {
        return Value(archimedean_property(get_double(args, "x"),
                                          get_double_opt(args, "epsilon", 1.0)));
    }));

    // ── riemann_integral ────────────────────────────────────────────────────
    register_function("darboux_sum", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const DarbouxResult r = darboux_sum(get_string(args, "expr"), a, b);
        Value obj = Value::make_object();
        obj.set("lower_sum", Value(r.lower_sum));
        obj.set("upper_sum", Value(r.upper_sum));
        obj.set("is_integrable", Value(r.is_integrable));
        return obj;
    }));
    register_function("riemann_integrable", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        return Value(riemann_integrable(get_string(args, "expr"), a, b));
    }));
    register_function("fundamental_theorem", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const FundamentalResult r = fundamental_theorem(get_string(args, "expr"), a, b);
        Value obj = Value::make_object();
        obj.set("integral", Value(r.integral));
        obj.set("Fb", Value(r.Fb));
        obj.set("Fa", Value(r.Fa));
        obj.set("antiderivative", Value(r.antiderivative));
        return obj;
    }));
    register_function("integral_mean_value", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const MeanValueResult r = integral_mean_value(get_string(args, "expr"), a, b);
        Value obj = Value::make_object();
        obj.set("mean_value", Value(r.mean_value));
        obj.set("xi", Value(r.xi));
        return obj;
    }));

    // ── function_limit ──────────────────────────────────────────────────────
    register_function("limit_epsilon_delta", make_handler([](const Value& args) {
        const EpsDeltaResult r = limit_epsilon_delta(
            get_string(args, "expr"), get_double_opt(args, "point", 0.0),
            get_double_opt(args, "epsilon", 0.01));
        Value obj = Value::make_object();
        obj.set("L", Value(r.L));
        obj.set("delta", Value(r.delta));
        return obj;
    }));
    register_function("real_is_continuous", make_handler([](const Value& args) {
        return Value(real_is_continuous(get_string(args, "expr"),
                                        get_double_opt(args, "point", 0.0)));
    }));
    register_function("uniform_continuity", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        return Value(uniform_continuity(get_string(args, "expr"), a, b));
    }));
    register_function("real_discontinuity_classify", make_handler([](const Value& args) {
        return Value(real_discontinuity_classify(get_string(args, "expr"),
                                                 get_double_opt(args, "point", 0.0)));
    }));
    register_function("extreme_value", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const ExtremeValueResult r = extreme_value(get_string(args, "expr"), a, b);
        Value obj = Value::make_object();
        obj.set("max", Value(r.max));
        obj.set("min", Value(r.min));
        obj.set("max_point", Value(r.max_point));
        obj.set("min_point", Value(r.min_point));
        return obj;
    }));
    register_function("intermediate_value", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const double xi = intermediate_value(get_string(args, "expr"), a, b,
                                             get_double_opt(args, "value", 0.0));
        if (!std::isfinite(xi)) return Value();
        return Value(xi);
    }));

    // ── function_series ─────────────────────────────────────────────────────
    register_function("pointwise_convergence", make_handler([](const Value& args) {
        return Value(pointwise_convergence(get_string(args, "seq_expr"),
                                           get_double_opt(args, "point", 0.5)));
    }));
    register_function("uniform_convergence", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const UniformConvergenceResult r =
            uniform_convergence(get_string(args, "seq_expr"), a, b);
        Value obj = Value::make_object();
        obj.set("convergence_type", Value(r.convergence_type));
        obj.set("limit_function", Value(r.limit_function_value));
        return obj;
    }));
    register_function("weierstrass_m_test", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const WeierstrassResult r = weierstrass_m_test(get_string(args, "seq_expr"), a, b);
        Value obj = Value::make_object();
        obj.set("passes", Value(r.passes));
        return obj;
    }));
    register_function("termwise_integration", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b);
        const TermwiseIntegralResult r = termwise_integration(
            get_string(args, "seq_expr"), a, b, get_int_opt_bounded(args, "n_terms", 10, -9223372036854775807, 200, "逐项积分项数"));
        Value obj = Value::make_object();
        obj.set("termwise_sum", Value(r.termwise_sum));
        obj.set("direct_integral", Value(r.direct_integral));
        return obj;
    }));
    register_function("termwise_differentiation", make_handler([](const Value& args) {
        const TermwiseDiffResult r = termwise_differentiation(
            get_string(args, "seq_expr"), get_int_opt_bounded(args, "n_terms", 5, -9223372036854775807, 200, "逐项微分项数"));
        Value obj = Value::make_object();
        obj.set("derivative_series", Value(r.derivative_series));
        obj.set("verified", Value(r.verified));
        return obj;
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_real_analysis_registrar;

}  // namespace
