// measure_theory_api.cpp — measure_theory 包 JSON 分发层。
//
// 注册 24 个 action:set_systems + measurable_functions + measure_construction +
// lebesgue_integral + convergence_theorems + probability_measure + product_measure。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "set_systems.h"
#include "measurable_functions.h"
#include "measure_construction.h"
#include "lebesgue_integral.h"
#include "convergence_theorems.h"
#include "probability_measure.h"
#include "product_measure.h"

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::measure_theory;
using mf::api::make_handler;
using mf::api::get_int;
using mf::api::get_int_opt;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_keyword_opt;
using mf::api::get_bool_opt;

// 区间 [lo,hi] 参数(缺省 (0,1))。
void get_interval(const Value& args, double& lo, double& hi, double d_lo,
                  double d_hi) {
    lo = d_lo;
    hi = d_hi;
    if (args.is_object() && args.has("range") && args["range"].is_array() &&
        args["range"].size() == 2) {
        lo = args["range"].at(0).as_double();
        hi = args["range"].at(1).as_double();
    }
}

// 长整数一维数组参数。
std::vector<long long> get_ll_array(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少数组参数 ") + key);
    const Value& arr = args[key];
    std::vector<long long> out;
    for (std::size_t i = 0; i < arr.size(); ++i) out.push_back(arr.at(i).as_int());
    return out;
}

// 长整数二维数组参数(集合系)。
std::vector<std::vector<long long>> get_ll_matrix(const Value& args,
                                                  const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少数组参数 ") + key);
    const Value& arr = args[key];
    std::vector<std::vector<long long>> out;
    for (std::size_t i = 0; i < arr.size(); ++i) {
        std::vector<long long> row;
        for (std::size_t j = 0; j < arr.at(i).size(); ++j)
            row.push_back(arr.at(i).at(j).as_int());
        out.push_back(std::move(row));
    }
    return out;
}

// [a,b] 区间列表参数。
std::vector<std::pair<double, double>> get_pair_list(const Value& args,
                                                     const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少数组参数 ") + key);
    const Value& arr = args[key];
    std::vector<std::pair<double, double>> out;
    for (std::size_t i = 0; i < arr.size(); ++i) {
        if (arr.at(i).size() != 2)
            throw std::invalid_argument(std::string("参数 ") + key +
                                        " 第 " + std::to_string(i) + " 项不是区间");
        out.emplace_back(arr.at(i).at(0).as_double(),
                         arr.at(i).at(1).as_double());
    }
    return out;
}

std::vector<double> get_double_list(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少数组参数 ") + key);
    const Value& arr = args[key];
    std::vector<double> out;
    for (std::size_t i = 0; i < arr.size(); ++i)
        out.push_back(arr.at(i).as_double());
    return out;
}

Value to_ll_array(const std::vector<long long>& v) {
    Value arr = Value::make_array();
    for (long long x : v) arr.push_back(Value(x));
    return arr;
}

Value to_ll_matrix(const std::vector<std::vector<long long>>& m) {
    Value arr = Value::make_array();
    for (const auto& row : m) arr.push_back(to_ll_array(row));
    return arr;
}

Value to_double_array(const std::vector<double>& v) {
    Value arr = Value::make_array();
    for (double x : v) arr.push_back(Value(x));
    return arr;
}

// 解析样本空间:字符串 "dice"/"finite:n"/数组。
std::vector<long long> parse_omega(const Value& args, const char* key) {
    if (args.is_object() && args.has(key)) {
        const Value& v = args[key];
        if (v.is_array()) {
            std::vector<long long> out;
            for (std::size_t i = 0; i < v.size(); ++i)
                out.push_back(v.at(i).as_int());
            return out;
        }
        if (v.is_string()) {
            const std::string& s = v.as_string();
            if (s == "dice") {
                return {1, 2, 3, 4, 5, 6};
            }
            if (s == "coin") return {1, 2};
            if (s.rfind("finite:", 0) == 0) {
                const long long n = std::stoll(s.substr(7));
                std::vector<long long> out;
                for (long long i = 1; i <= n; ++i) out.push_back(i);
                return out;
            }
        }
    }
    return {1, 2, 3, 4, 5, 6};
}

// 解析 X 的取值规则:"x"/"identity" → 恒等;否则为表达式。
std::string x_rule(const Value& args) {
    std::string rule = get_string_opt(args, "X", "x");
    if (rule == "identity") rule = "x";
    return rule;
}

// 随机变量的取值(按 omega 对齐)。
std::vector<double> x_values(const std::string& rule,
                             const std::vector<long long>& omega) {
    RandomVariableResult rv = random_variable(rule, omega);
    return rv.values;
}

void register_all() {
    using mf::registry::register_function;

    // ── set_systems ─────────────────────────────────────────────────────────
    register_function("is_sigma_algebra", make_handler([](const Value& args) {
        const SigmaAlgebraResult r = is_sigma_algebra(
            get_ll_matrix(args, "collection"), get_ll_array(args, "X"));
        Value obj = Value::make_object();
        obj.set("isSigmaAlgebra", Value(r.is_sigma_algebra));
        obj.set("collectionSize", Value(r.collection_size));
        return obj;
    }));

    register_function("generate_sigma_algebra", make_handler([](const Value& args) {
        const GeneratedSigmaAlgebra r = generate_sigma_algebra(
            get_ll_matrix(args, "generators"), get_ll_array(args, "X"));
        Value obj = Value::make_object();
        obj.set("count", Value(r.count));
        obj.set("sets", to_ll_matrix(r.sets));
        obj.set("iterations", Value(r.iterations));
        return obj;
    }));

    register_function("borel_sigma_algebra", make_handler([](const Value& args) {
        if (args.is_object() && args.has("space") &&
            args["space"].is_string()) {
            const std::string s = args["space"].as_string();
            if (s == "R" || s == "real" || s == "实数") {
                Value obj = Value::make_object();
                obj.set("description",
                        Value("B(R) — 实数轴上的 Borel σ-代数"));
                obj.set("count", Value(0));
                return obj;
            }
        }
        std::vector<long long> elements;
        if (args.is_object() && args.has("space") &&
            args["space"].is_array()) {
            const Value& v = args["space"];
            if (v.size() == 2 && v.at(0).is_int() && v.at(1).is_int()) {
                for (long long i = v.at(0).as_int(); i <= v.at(1).as_int(); ++i)
                    elements.push_back(i);
            } else {
                for (std::size_t i = 0; i < v.size(); ++i)
                    elements.push_back(v.at(i).as_int());
            }
        } else {
            for (long long i = 0; i <= 4; ++i) elements.push_back(i);
        }
        const GeneratedSigmaAlgebra r = borel_sigma_algebra(elements);
        Value obj = Value::make_object();
        obj.set("count", Value(r.count));
        obj.set("sets", to_ll_matrix(r.sets));
        obj.set("iterations", Value(r.iterations));
        return obj;
    }));

    // ── measurable_functions ────────────────────────────────────────────────
    register_function("is_measurable", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b, -10.0, 10.0);
        const MeasurableResult r = is_measurable(get_string(args, "f"), a, b);
        Value obj = Value::make_object();
        obj.set("isMeasurable", Value(r.is_measurable));
        obj.set("singularities", to_double_array(r.singularities));
        return obj;
    }));

    register_function("simple_function", make_handler([](const Value& args) {
        const std::vector<double> coefs = get_double_list(args, "coefficients");
        const auto sets = get_pair_list(args, "sets");
        const double x = get_double_opt(args, "x", 0.0);
        Value obj = Value::make_object();
        obj.set("value", Value(simple_function_eval(coefs, sets, x)));
        obj.set("coefficients", mf::api::to_double_array(coefs));
        Value setsArr = Value::make_array();
        for (const auto& pr : sets) {
            Value it = Value::make_array();
            it.push_back(Value(pr.first));
            it.push_back(Value(pr.second));
            setsArr.push_back(it);
        }
        obj.set("sets", setsArr);
        return obj;
    }));

    register_function("step_function_approx", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b, 0.0, 1.0);
        const StepApproxResult r = step_function_approx(
            get_string(args, "f"), get_int(args, "n"), a, b);
        Value obj = Value::make_object();
        obj.set("values", to_double_array(r.values));
        obj.set("dx", Value(r.dx));
        obj.set("integral", Value(r.integral));
        return obj;
    }));

    // ── measure_construction ────────────────────────────────────────────────
    register_function("lebesgue_measure", make_handler([](const Value& args) {
        if (args.is_object() && args.has("E") && args["E"].is_string()) {
            const MeasureSetResult r = lebesgue_measure_set(args["E"].as_string());
            if (r.infinite) return Value("∞");
            return Value(r.value);
        }
        if (args.is_object() && args.has("E") && args["E"].is_array() &&
            args["E"].size() == 2) {
            return Value(lebesgue_measure(args["E"].at(0).as_double(),
                                          args["E"].at(1).as_double()));
        }
        throw std::invalid_argument("E 必须为 [a,b] 或集合名");
    }));

    register_function("outer_measure", make_handler([](const Value& args) {
        if (!args.is_object() || !args.has("E") || !args["E"].is_array() ||
            args["E"].size() != 2)
            throw std::invalid_argument("E 必须为 [a,b]");
        const OuterMeasureResult r = outer_measure(
            args["E"].at(0).as_double(), args["E"].at(1).as_double(),
            get_double_opt(args, "epsilon", 0.01));
        Value obj = Value::make_object();
        obj.set("measure", Value(r.measure));
        obj.set("nIntervals", Value(r.n_intervals));
        obj.set("coverLength", Value(r.cover_length));
        return obj;
    }));

    register_function("caratheodory_measurable", make_handler([](const Value& args) {
        if (!args.is_object() || !args.has("E") || !args["E"].is_array() ||
            args["E"].size() != 2)
            throw std::invalid_argument("E 必须为 [a,b]");
        return Value(caratheodory_measurable(args["E"].at(0).as_double(),
                                             args["E"].at(1).as_double()));
    }));

    register_function("measure_properties", make_handler([](const Value&) {
        const auto props = measure_properties();
        Value arr = Value::make_array();
        for (const auto& p : props) {
            Value obj = Value::make_object();
            obj.set("name", Value(p.name));
            obj.set("statement", Value(p.statement));
            obj.set("verified", Value(p.verified));
            arr.push_back(obj);
        }
        return arr;
    }));

    // ── lebesgue_integral ───────────────────────────────────────────────────
    register_function("integral_simple", make_handler([](const Value& args) {
        return Value(integral_simple(get_double_list(args, "coefficients"),
                                     get_pair_list(args, "sets")));
    }));

    register_function("integral_nonnegative", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b, 0.0, 1.0);
        const NonnegIntegralResult r =
            integral_nonnegative(get_string(args, "f"), a, b);
        Value obj = Value::make_object();
        obj.set("integral", Value(r.integral));
        obj.set("approximation", Value(r.approximation));
        return obj;
    }));

    register_function("integral_general", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b, -1.0, 1.0);
        const GeneralIntegralResult r =
            integral_general(get_string(args, "f"), a, b);
        Value obj = Value::make_object();
        obj.set("pos", Value(r.pos));
        obj.set("neg", Value(r.neg));
        obj.set("integral", Value(r.integral));
        return obj;
    }));

    register_function("integral_zero_set_independent", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b, 0.0, 1.0);
        const ZeroSetResult r = integral_zero_set_independent(
            get_string(args, "f"), get_string(args, "g"), a, b);
        Value obj = Value::make_object();
        obj.set("areEqual", Value(r.are_equal));
        obj.set("diffPoints", to_double_array(r.diff_points));
        return obj;
    }));

    // ── convergence_theorems ────────────────────────────────────────────────
    register_function("monotone_convergence", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b, 0.0, 1.0);
        const MonotoneResult r = monotone_convergence(
            get_string(args, "f_n"), get_string(args, "f"),
            get_ll_array(args, "n_values"), a, b);
        Value obj = Value::make_object();
        obj.set("integralValues", to_double_array(r.integral_values));
        obj.set("limitOfIntegrals", Value(r.limit_of_integrals));
        obj.set("integralOfLimit", Value(r.integral_of_limit));
        obj.set("difference", Value(r.difference));
        obj.set("converged", Value(r.converged));
        return obj;
    }));

    register_function("fatou_lemma", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b, 0.0, 1.0);
        const FatouResult r =
            fatou_lemma(get_string(args, "f_n"), get_ll_array(args, "n_values"), a, b);
        Value obj = Value::make_object();
        obj.set("integralValues", to_double_array(r.integral_values));
        obj.set("integralOfLiminf", Value(r.integral_of_liminf));
        obj.set("liminfOfIntegrals", Value(r.liminf_of_integrals));
        obj.set("inequalityHolds", Value(r.inequality_holds));
        return obj;
    }));

    register_function("dominated_convergence", make_handler([](const Value& args) {
        double a, b;
        get_interval(args, a, b, 0.0, 1.0);
        const DominatedResult r = dominated_convergence(
            get_string(args, "f_n"), get_string(args, "f"),
            get_string(args, "g"), get_ll_array(args, "n_values"), a, b);
        Value obj = Value::make_object();
        obj.set("dominated", Value(r.dominated));
        obj.set("integralValues", to_double_array(r.integral_values));
        obj.set("limitOfIntegrals", Value(r.limit_of_integrals));
        obj.set("integralOfLimit", Value(r.integral_of_limit));
        obj.set("gIntegral", Value(r.g_integral));
        obj.set("difference", Value(r.difference));
        return obj;
    }));

    // ── probability_measure ─────────────────────────────────────────────────
    register_function("probability_space", make_handler([](const Value& args) {
        const ProbabilitySpaceResult r = probability_space(parse_omega(args, "Omega"));
        Value obj = Value::make_object();
        obj.set("omega", to_ll_array(r.omega));
        obj.set("probabilities", to_double_array(r.probabilities));
        obj.set("isProbabilitySpace", Value(r.is_probability_space));
        return obj;
    }));

    register_function("random_variable", make_handler([](const Value& args) {
        // rule 是关键词（identity/square），不能用表达式归一化取值
        const std::string rule = get_keyword_opt(args, "rule", "identity");
        const RandomVariableResult r = random_variable(rule, parse_omega(args, "Omega"));
        Value obj = Value::make_object();
        obj.set("omega", to_ll_array(r.omega));
        obj.set("values", to_double_array(r.values));
        obj.set("description", Value(r.description));
        return obj;
    }));

    register_function("meas_expectation", make_handler([](const Value& args) {
        const std::string X = x_rule(args);
        const std::string P = get_string_opt(args, "P", "uniform");

        // 连续分布。
        if (P.rfind("normal", 0) == 0) {
            double mu = 0.0, sigma = 1.0;
            const std::size_t lp = P.find('(');
            if (lp != std::string::npos && P.find(')') != std::string::npos) {
                const std::string inner =
                    P.substr(lp + 1, P.find(')') - lp - 1);
                const std::size_t comma = inner.find(',');
                if (comma != std::string::npos) {
                    mu = std::stod(inner.substr(0, comma));
                    sigma = std::stod(inner.substr(comma + 1));
                }
            }
            return Value(expectation_normal(X, mu, sigma));
        }
        if (P.rfind("uniform", 0) == 0) {
            double a = 0.0, b = 1.0;
            const std::size_t lp = P.find('(');
            if (lp != std::string::npos && P.find(')') != std::string::npos) {
                const std::string inner =
                    P.substr(lp + 1, P.find(')') - lp - 1);
                const std::size_t comma = inner.find(',');
                if (comma != std::string::npos) {
                    a = std::stod(inner.substr(0, comma));
                    b = std::stod(inner.substr(comma + 1));
                }
            }
            return Value(expectation_uniform(X, a, b));
        }

        // 离散:Ω 上均匀。
        const std::vector<long long> omega = parse_omega(args, "Omega");
        const std::vector<double> xv = x_values(X, omega);
        std::vector<double> probs;
        const double p = omega.empty() ? 0.0 : 1.0 / (double)omega.size();
        for (std::size_t i = 0; i < omega.size(); ++i) probs.push_back(p);
        return Value(expectation_discrete(xv, probs));
    }));

    register_function("conditional_expectation", make_handler([](const Value& args) {
        const std::string X = x_rule(args);
        const std::vector<long long> omega = parse_omega(args, "Omega");
        std::vector<std::vector<long long>> atoms;
        if (args.is_object() && args.has("sub_sigma_algebra") &&
            args["sub_sigma_algebra"].is_string() &&
            args["sub_sigma_algebra"].as_string() == "parity") {
            std::vector<long long> even, odd;
            for (long long w : omega) {
                if (w % 2 == 0) even.push_back(w);
                else odd.push_back(w);
            }
            if (!even.empty()) atoms.push_back(even);
            if (!odd.empty()) atoms.push_back(odd);
        } else {
            atoms = get_ll_matrix(args, "sub_sigma_algebra");
        }
        const ConditionalExpectationResult r =
            conditional_expectation(X, omega, atoms);
        Value obj = Value::make_object();
        obj.set("omega", to_ll_array(r.omega));
        obj.set("atoms", to_ll_matrix(r.atoms));
        obj.set("cePerAtom", to_double_array(r.ce_per_atom));
        return obj;
    }));

    register_function("independence_check", make_handler([](const Value& args) {
        const std::vector<long long> omega = parse_omega(args, "Omega");
        std::vector<double> probs;
        const double p = omega.empty() ? 0.0 : 1.0 / (double)omega.size();
        for (std::size_t i = 0; i < omega.size(); ++i) probs.push_back(p);
        return Value(independence_check(get_ll_array(args, "A"),
                                        get_ll_array(args, "B"), omega, probs));
    }));

    // ── product_measure ─────────────────────────────────────────────────────
    register_function("product_measure", make_handler([](const Value& args) {
        const auto factor = [&](const char* key) {
            const Value& v = args[key];
            if (v.is_string() && v.as_string() == "lebesgue") return 1.0;
            return v.as_double();
        };
        if (!args.is_object() || !args.has("A") || !args["A"].is_array() ||
            args["A"].size() != 2 || !args.has("B") || !args["B"].is_array() ||
            args["B"].size() != 2)
            throw std::invalid_argument("A/B 必须为 [a,b]");
        return Value(product_measure(factor("mu"), factor("nu"),
                                     args["A"].at(0).as_double(),
                                     args["A"].at(1).as_double(),
                                     args["B"].at(0).as_double(),
                                     args["B"].at(1).as_double()));
    }));

    register_function("fubini_theorem", make_handler([](const Value& args) {
        if (!args.is_object() || !args.has("range") || !args["range"].is_array() ||
            args["range"].size() != 4)
            throw std::invalid_argument("range 需要 [xa,xb,ya,yb]");
        const FubiniResult r = fubini_theorem(
            get_string(args, "f"), args["range"].at(0).as_double(),
            args["range"].at(1).as_double(), args["range"].at(2).as_double(),
            args["range"].at(3).as_double());
        Value obj = Value::make_object();
        obj.set("xyOrder", Value(r.xy_order));
        obj.set("yxOrder", Value(r.yx_order));
        obj.set("difference", Value(r.difference));
        obj.set("fubiniHolds", Value(r.fubini_holds));
        // 定性结论的补充信息:迭代积分是否求得出来(观测) + 人读说明(含推断)。
        obj.set("iteratedIntegralsEvaluated", Value(r.iterated_integrals_evaluated));
        obj.set("note", Value(r.note));
        return obj;
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_measure_theory_registrar;

}  // namespace
