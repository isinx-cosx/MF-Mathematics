// harmonic_analysis_api.cpp — harmonic_analysis 包 JSON 分发层。
//
// 注册 22 个 action(fourier_series + fourier_transform + convolution +
// distributions + time_frequency + zeta_harmonic)。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "fourier_series.h"
#include "fourier_transform.h"
#include "convolution.h"
#include "distributions.h"
#include "time_frequency.h"
#include "zeta_harmonic.h"

#include <complex>
#include <cstdint>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::harmonic_analysis;
using mf::api::make_handler;
using mf::api::get_int;
using mf::api::get_int_opt;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_double_array;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_bool_opt;

// 一维数组参数。
std::vector<double> get_sig(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少数组参数 ") + key);
    return get_double_array(args, key);
}

Value to_arr(const std::vector<double>& v) {
    Value arr = Value::make_array();
    for (double x : v) arr.push_back(Value(x));
    return arr;
}

// 区间 [lo, hi],缺省 (0,1)。
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

// 傅里叶变换结果:数值 → [re, im];表达式 → 字符串。
//
// 数值分支只在**可信**时保持原来的 [re, im] 形状(向后兼容); 一旦数值积分
// 收敛不到容差, 就升级成对象并把实测误差/截断半径/告警一起给出 ——
// 慢衰减或高频函数欠采样时必须能被调用方看出来, 不能静默返回错值。
Value ft_result_value(const FourierTransformResult& r) {
    if (r.numeric) {
        Value arr = Value::make_array();
        arr.push_back(Value(r.value.real()));
        arr.push_back(Value(r.value.imag()));
        if (r.reliable) return arr;
        Value obj = Value::make_object();
        obj.set("value", std::move(arr));
        obj.set("reliable", Value(false));
        obj.set("estimated_error", Value(r.estimated_error));
        obj.set("truncation_radius", Value(r.truncation_radius));
        obj.set("tail_terms", Value(static_cast<double>(r.tail_terms)));
        obj.set("warning", Value(r.warning));
        return obj;
    }
    return Value(r.expression);
}

void register_all() {
    using mf::registry::register_function;

    // ── fourier_series ─────────────────────────────────────────────────────
    register_function("fourier_coeff", make_handler([](const Value& args) {
        const FourierCoeffResult r = fourier_coeff(
            get_string(args, "f"), get_int(args, "n"),
            get_double_opt(args, "period", 2.0 * 3.141592653589793),
            get_string_opt(args, "coeff_type", "cos"));
        Value obj = Value::make_object();
        obj.set("value", Value(r.value));
        obj.set("name", Value(r.name));
        return obj;
    }));
    register_function("fourier_series", make_handler([](const Value& args) {
        const FourierSeriesResult r = fourier_series(
            get_string(args, "f"), get_int(args, "n_terms"),
            get_double_opt(args, "period", 2.0 * 3.141592653589793));
        Value obj = Value::make_object();
        obj.set("expression", Value(r.expression));
        Value cs = Value::make_array();
        for (const auto& kv : r.coeffs) {
            Value item = Value::make_object();
            item.set("name", Value(kv.first));
            item.set("value", Value(kv.second));
            cs.push_back(std::move(item));
        }
        obj.set("coeffs", std::move(cs));
        return obj;
    }));
    register_function("complex_fourier_coeff", make_handler([](const Value& args) {
        const ComplexCoeffResult r = complex_fourier_coeff(
            get_string(args, "f"), get_int(args, "n"),
            get_double_opt(args, "period", 2.0 * 3.141592653589793));
        Value obj = Value::make_object();
        Value val = Value::make_array();
        val.push_back(Value(r.value.real()));
        val.push_back(Value(r.value.imag()));
        obj.set("value", std::move(val));
        return obj;
    }));
    register_function("orthogonality_check", make_handler([](const Value& args) {
        const OrthogonalityResult r = orthogonality_check(
            get_int(args, "n"), get_int(args, "m"),
            get_double_opt(args, "period", 2.0 * 3.141592653589793));
        Value obj = Value::make_object();
        obj.set("integral_re", Value(r.integral.real()));
        obj.set("integral_im", Value(r.integral.imag()));
        obj.set("orthogonal", Value(r.orthogonal));
        return obj;
    }));

    // ── fourier_transform ──────────────────────────────────────────────────
    register_function("fourier_transform", make_handler([](const Value& args) {
        const bool numeric =
            args.is_object() && args.has("xi") && !args["xi"].is_string();
        const double xi = numeric ? args["xi"].as_double() : 0.0;
        const FourierTransformResult r = fourier_transform(
            get_string(args, "f"), numeric, xi,
            get_bool_opt(args, "use_angular", true));
        return ft_result_value(r);
    }));
    register_function("inverse_fourier_transform",
                      make_handler([](const Value& args) {
        const bool numeric =
            args.is_object() && args.has("x") && !args["x"].is_string();
        const double xv = numeric ? args["x"].as_double() : 0.0;
        const FourierTransformResult r = inverse_fourier_transform(
            get_string(args, "F"), numeric, xv,
            get_bool_opt(args, "use_angular", true));
        return ft_result_value(r);
    }));
    register_function("plancherel_theorem", make_handler([](const Value& args) {
        double lo, hi;
        get_interval(args, lo, hi, -10.0, 10.0);
        const PlancherelResult r = plancherel_theorem(
            get_string(args, "f"), lo, hi, (int)get_int(args, "n_points"));
        Value obj = Value::make_object();
        obj.set("l2_time", Value(r.l2_time));
        obj.set("l2_freq", Value(r.l2_freq));
        obj.set("relative_difference", Value(r.relative_difference));
        obj.set("consistent", Value(r.consistent));
        return obj;
    }));
    register_function("ft_of_gaussian", make_handler([](const Value& args) {
        return Value(ft_of_gaussian(get_double(args, "a")));
    }));

    // ── convolution ────────────────────────────────────────────────────────
    register_function("convolution", make_handler([](const Value& args) {
        double lo, hi;
        get_interval(args, lo, hi, -10.0, 10.0);
        return Value(convolution(get_string(args, "f"), get_string(args, "g"),
                                 get_double_opt(args, "x_val", 0.0), lo, hi));
    }));
    register_function("convolution_theorem", make_handler([](const Value& args) {
        double lo, hi;
        get_interval(args, lo, hi, -10.0, 10.0);
        const ConvolutionTheoremResult r = convolution_theorem(
            get_string(args, "f"), get_string(args, "g"), lo, hi,
            (int)get_int(args, "n_points"));
        Value obj = Value::make_object();
        obj.set("max_absolute_error", Value(r.max_absolute_error));
        obj.set("max_relative_error", Value(r.max_relative_error));
        obj.set("consistent", Value(r.consistent));
        return obj;
    }));
    register_function("gaussian_blur", make_handler([](const Value& args) {
        return to_arr(gaussian_blur(get_sig(args, "signal"),
                                    get_double(args, "sigma")));
    }));
    register_function("low_pass_filter", make_handler([](const Value& args) {
        const LowPassResult r = low_pass_filter(
            get_sig(args, "signal"), get_double(args, "cutoff"),
            get_double_opt(args, "sample_rate", 1.0));
        Value obj = Value::make_object();
        obj.set("filtered", to_arr(r.filtered));
        obj.set("energy_ratio", Value(r.energy_ratio));
        return obj;
    }));

    // ── distributions ──────────────────────────────────────────────────────
    register_function("delta_distribution", make_handler([](const Value& args) {
        return Value(delta_distribution(get_string(args, "phi"),
                                        get_double_opt(args, "x0", 0.0)));
    }));
    register_function("ft_delta", make_handler([](const Value&) {
        return Value(ft_delta());
    }));
    register_function("ft_constant", make_handler([](const Value&) {
        return Value(ft_constant());
    }));
    register_function("tempered_distribution", make_handler([](const Value& args) {
        double lo, hi;
        get_interval(args, lo, hi, -100.0, 100.0);
        const TemperedResult r = tempered_distribution(get_string(args, "func"), hi);
        Value obj = Value::make_object();
        obj.set("is_tempered", Value(r.is_tempered));
        obj.set("growth_order", Value(r.growth_order));
        return obj;
    }));

    // ── time_frequency ─────────────────────────────────────────────────────
    register_function("uncertainty_principle", make_handler([](const Value& args) {
        double lo, hi;
        get_interval(args, lo, hi, -50.0, 50.0);
        const UncertaintyResult r = uncertainty_principle(
            get_string(args, "f"), lo, hi, (int)get_int(args, "n_points"));
        Value obj = Value::make_object();
        obj.set("delta_x", Value(r.delta_x));
        obj.set("delta_xi", Value(r.delta_xi));
        obj.set("product", Value(r.product));
        obj.set("lower_bound", Value(r.lower_bound));
        obj.set("satisfied", Value(r.satisfied));
        return obj;
    }));
    register_function("stft", make_handler([](const Value& args) {
        const StftResult r = stft(
            get_sig(args, "signal"), (int)get_int(args, "window_size"),
            (int)get_int_opt(args, "hop_size", 0),
            get_double_opt(args, "sample_rate", 1.0));
        Value obj = Value::make_object();
        Value sp = Value::make_array();
        for (const auto& row : r.spectrogram_magnitude) sp.push_back(to_arr(row));
        obj.set("spectrogram_magnitude", std::move(sp));
        obj.set("times", to_arr(r.times));
        obj.set("frequencies", to_arr(r.frequencies));
        return obj;
    }));
    register_function("wavelet_transform", make_handler([](const Value& args) {
        std::vector<double> scales;
        if (args.is_object() && args.has("scales"))
            scales = get_double_array(args, "scales");
        const WaveletResult r = wavelet_transform(
            get_sig(args, "signal"), get_string_opt(args, "wavelet_type", "mexican_hat"),
            scales);
        Value obj = Value::make_object();
        Value cs = Value::make_array();
        for (const auto& row : r.coefficients) {
            Value crow = Value::make_array();
            for (double c : row) crow.push_back(Value(std::abs(c)));
            cs.push_back(std::move(crow));
        }
        obj.set("coefficients_magnitude", std::move(cs));
        obj.set("scales", to_arr(r.scales));
        return obj;
    }));

    // ── zeta_harmonic ──────────────────────────────────────────────────────
    register_function("poisson_summation", make_handler([](const Value& args) {
        const PoissonResult r = poisson_summation(
            get_string(args, "f"), get_double_opt(args, "a", 1.0),
            (int)get_int_opt(args, "n_terms", 50));
        Value obj = Value::make_object();
        obj.set("left_sum", Value(r.left_sum));
        obj.set("right_sum", Value(r.right_sum));
        obj.set("relative_difference", Value(r.relative_difference));
        obj.set("consistent", Value(r.consistent));
        // 新增字段: 右和的误差上界与实际参与数值求和的项数(便于判断可信度)。
        obj.set("right_sum_error", Value(r.right_sum_error));
        obj.set("numeric_terms", Value(static_cast<double>(r.numeric_terms)));
        obj.set("right_sum_reliable", Value(r.right_sum_reliable));
        return obj;
    }));
    register_function("theta_function", make_handler([](const Value& args) {
        const ThetaResult r = theta_function(
            get_double(args, "t"), (int)get_int_opt(args, "n_terms", 100));
        Value obj = Value::make_object();
        obj.set("theta_t", Value(r.theta_t));
        obj.set("theta_reciprocal", Value(r.theta_reciprocal));
        obj.set("modular_check", Value(r.modular_check));
        return obj;
    }));
    register_function("functional_equation_demo",
                      make_handler([](const Value& args) {
        const FunctionalEquationResult r =
            functional_equation_demo(get_double_opt(args, "s", 2.0));
        Value obj = Value::make_object();
        obj.set("zeta_s", Value(r.zeta_s));
        obj.set("zeta_1_minus_s", Value(r.zeta_1_minus_s));
        obj.set("left_side", Value(r.left_side));
        obj.set("right_side", Value(r.right_side));
        obj.set("relative_difference", Value(r.relative_difference));
        return obj;
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_harmonic_analysis_registrar;

}  // namespace
