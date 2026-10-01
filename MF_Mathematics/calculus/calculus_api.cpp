// calculus_api.cpp — calculus 包 JSON 分发层(derivatives 模块)。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "derivatives.h"
#include "integrals.h"
#include "derivatives_app.h"
#include "integrals_app.h"
#include "series.h"
#include "limits.h"

#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::calculus;
using mf::api::make_handler;
using mf::api::get_int_opt;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_equation;
using mf::api::get_string_or_number;

// 趋近点:数字或字符串 "oo"/"+oo"/"-oo"(handler 存储为 std::function,只能引用自由函数)。
double point_of(const Value& args) {
    const std::string pstr = get_string_or_number(args, "point");
    if (pstr == "oo" || pstr == "+oo" || pstr == "inf")
        return std::numeric_limits<double>::infinity();
    if (pstr == "-oo" || pstr == "-inf")
        return -std::numeric_limits<double>::infinity();
    return std::stod(pstr);
}

void register_all() {
    using mf::registry::register_function;

    register_function("diff", make_handler([](const Value& args) {
        return Value(diff(get_string(args, "expr"), get_string_opt(args, "var", "x"),
                          get_int_opt(args, "order", 1)));
    }));
    // 在某点求导。**含参数时返回符号结果**（f=a*x^2 在 x=2 处是 4*a，不是一个报错），
    // 不含参数时仍然返回数值——因此这里按"结果文本能否整体解析为数字"来决定 JSON 类型。
    register_function("diff_at", make_handler([](const Value& args) {
        const std::string s = diff_at_str(get_string(args, "expr"),
                                          get_string_opt(args, "var", "x"),
                                          get_double(args, "point"),
                                          get_int_opt(args, "order", 1));
        // 必须整串都能解析才算数值：stod("4*a") 会只看前一位，绝不能当 4 用
        std::size_t used = 0;
        try {
            const double v = std::stod(s, &used);
            if (used == s.size() && std::isfinite(v)) return Value(v);
        } catch (...) { /* 不是纯数字，走符号分支 */ }
        return Value(s);
    }));
    register_function("implicit_diff", make_handler([](const Value& args) {
        // 隐函数求导的输入天然是方程：F(x,y)=0。允许写 x^2+y^2=1 或 x^2+y^2-1。
        return Value(implicit_diff(get_equation(args, "eq"),
                                   get_string_opt(args, "var", "x"),
                                   get_string_opt(args, "dep_var", "y")));
    }));
    register_function("parametric_diff", make_handler([](const Value& args) {
        return Value(parametric_diff(get_string(args, "x_expr"),
                                     get_string(args, "y_expr"),
                                     get_string_opt(args, "t", "t")));
    }));
    register_function("differential", make_handler([](const Value& args) {
        return Value(differential(get_string(args, "expr"),
                                  get_string_opt(args, "var", "x"),
                                  get_double_opt(args, "point", 0.0),
                                  get_double_opt(args, "dx", 0.01)));
    }));

    // ── integrals ──────────────────────────────────────────────────────────
    // 边界 a/b 可为数字或字符串("pi"/"oo"/"inf")。
    const auto bound = [](const Value& args, const char* key,
                          const char* def) {
        if (args.is_object() && args.has(key))
            return get_string_or_number(args, key);
        return std::string(def);
    };
    register_function("integrate", make_handler([bound](const Value& args) {
        if (args.is_object() && args.has("a") && args.has("b"))
            return Value(integrate_definite(
                get_string(args, "expr"), get_string_opt(args, "var", "x"),
                bound(args, "a", "0"), bound(args, "b", "1")));
        return Value(integrate_indefinite(get_string(args, "expr"),
                                          get_string_opt(args, "var", "x")));
    }));
    register_function("integrate_numeric", make_handler([](const Value& args) {
        return Value(integrate_numeric(
            get_string(args, "expr"), get_string_opt(args, "var", "x"),
            get_double_opt(args, "a", 0.0), get_double_opt(args, "b", 1.0)));
    }));
    register_function("improper_integral",
                      make_handler([bound](const Value& args) {
        return Value(improper_integral(
            get_string(args, "expr"), get_string_opt(args, "var", "x"),
            bound(args, "a", "0"), bound(args, "b", "oo")));
    }));
    register_function("integrate_double",
                      make_handler([bound](const Value& args) {
        return Value(integrate_double(
            get_string(args, "expr"), get_string_opt(args, "x", "x"),
            get_string_opt(args, "y", "y"), bound(args, "xa", "0"),
            bound(args, "xb", "1"), bound(args, "ya", "0"),
            bound(args, "yb", "1")));
    }));
    register_function("integrate_triple",
                      make_handler([bound](const Value& args) {
        return Value(integrate_triple(
            get_string(args, "expr"), get_string_opt(args, "x", "x"),
            get_string_opt(args, "y", "y"), get_string_opt(args, "z", "z"),
            bound(args, "xa", "0"), bound(args, "xb", "1"),
            bound(args, "ya", "0"), bound(args, "yb", "1"),
            bound(args, "za", "0"), bound(args, "zb", "1")));
    }));
    register_function("integrate_complex",
                      make_handler([bound](const Value& args) {
        const std::complex<double> c = integrate_complex(
            get_string(args, "expr"), get_string_opt(args, "var", "x"),
            bound(args, "a", "0"), bound(args, "b", "1"));
        Value arr = Value::make_array();
        arr.push_back(Value(c.real()));
        arr.push_back(Value(c.imag()));
        return arr;
    }));

    // ── derivatives_app ─────────────────────────────────────────────────────
    register_function("calc_rolle_theorem", make_handler([](const Value& args) {
        const auto roots = calc_rolle_theorem(
            get_string(args, "expr"), get_string_opt(args, "var", "x"),
            get_double_opt(args, "a", 0.0), get_double_opt(args, "b", 1.0));
        Value arr = Value::make_array();
        for (double r : roots) arr.push_back(Value(r));
        return arr;
    }));
    register_function("calc_lagrange_theorem", make_handler([](const Value& args) {
        return Value(calc_lagrange_theorem(
            get_string(args, "expr"), get_string_opt(args, "var", "x"),
            get_double_opt(args, "a", 0.0), get_double_opt(args, "b", 1.0)));
    }));
    register_function("lhopital", make_handler([](const Value& args) {
        return Value(lhopital(get_string(args, "expr"),
                              get_string_opt(args, "var", "x"),
                              get_double_opt(args, "point", 0.0)));
    }));
    register_function("limit", make_handler([](const Value& args) {
        const double r = limit(get_string(args, "expr"),
                               get_string_opt(args, "var", "x"), point_of(args),
                               get_string_opt(args, "direction", ""));
        // 发散 → ±∞:用字符串 "oo"/"-oo" 表达(与 Python sympy 一致)。
        if (std::isinf(r)) return Value(std::string(r > 0 ? "oo" : "-oo"));
        return Value(r);
    }));
    register_function("calc_is_continuous", make_handler([](const Value& args) {
        return Value(is_continuous_at(get_string(args, "expr"),
                                      get_string_opt(args, "var", "x"),
                                      point_of(args)));
    }));
    register_function("calc_discontinuity_classify",
                      make_handler([](const Value& args) {
        return Value(classify_discontinuity(get_string(args, "expr"),
                                            get_string_opt(args, "var", "x"),
                                            point_of(args)));
    }));
    register_function("monotonicity", make_handler([](const Value& args) {
        const auto iv = monotonicity(get_string(args, "expr"),
                                     get_string_opt(args, "var", "x"));
        Value arr = Value::make_array();
        for (const auto& s : iv) arr.push_back(Value(s));
        return arr;
    }));
    register_function("local_extrema", make_handler([](const Value& args) {
        const LocalExtremaResult r = local_extrema(
            get_string(args, "expr"), get_string_opt(args, "var", "x"));
        Value obj = Value::make_object();
        Value mx = Value::make_array(), mn = Value::make_array();
        for (std::size_t i = 0; i < r.maxima_x.size(); ++i) {
            Value pt = Value::make_array();
            pt.push_back(Value(r.maxima_x[i]));
            pt.push_back(Value(r.maxima_val[i]));
            mx.push_back(pt);
        }
        for (std::size_t i = 0; i < r.minima_x.size(); ++i) {
            Value pt = Value::make_array();
            pt.push_back(Value(r.minima_x[i]));
            pt.push_back(Value(r.minima_val[i]));
            mn.push_back(pt);
        }
        obj.set("maxima", mx);
        obj.set("minima", mn);
        return obj;
    }));
    register_function("global_extrema", make_handler([](const Value& args) {
        const GlobalExtremaResult r = global_extrema(
            get_string(args, "expr"), get_string_opt(args, "var", "x"),
            get_double_opt(args, "a", 0.0), get_double_opt(args, "b", 1.0));
        Value obj = Value::make_object();
        obj.set("max", Value(r.max));
        obj.set("max_point", Value(r.max_point));
        obj.set("min", Value(r.min));
        obj.set("min_point", Value(r.min_point));
        return obj;
    }));
    register_function("taylor", make_handler([](const Value& args) {
        return Value(taylor(get_string(args, "expr"),
                            get_string_opt(args, "var", "x"),
                            get_double_opt(args, "point", 0.0),
                            get_int_opt(args, "order", 3)));
    }));

    // ── integrals_app ───────────────────────────────────────────────────────
    register_function("area_between", make_handler([](const Value& args) {
        return Value(area_between(get_string(args, "expr1"),
                                  get_string(args, "expr2"),
                                  get_string_opt(args, "var", "x"),
                                  get_double_opt(args, "a", 0.0),
                                  get_double_opt(args, "b", 1.0)));
    }));
    register_function("volume_disk", make_handler([](const Value& args) {
        return Value(volume_disk(get_string(args, "expr"),
                                 get_string_opt(args, "var", "x"),
                                 get_double_opt(args, "a", 0.0),
                                 get_double_opt(args, "b", 1.0)));
    }));
    register_function("volume_shell", make_handler([](const Value& args) {
        return Value(volume_shell(get_string(args, "expr"),
                                  get_string_opt(args, "var", "x"),
                                  get_double_opt(args, "a", 0.0),
                                  get_double_opt(args, "b", 1.0)));
    }));
    register_function("arc_length", make_handler([](const Value& args) {
        return Value(arc_length(get_string(args, "expr"),
                                get_string_opt(args, "var", "x"),
                                get_double_opt(args, "a", 0.0),
                                get_double_opt(args, "b", 1.0)));
    }));

    // ── series ──────────────────────────────────────────────────────────────
    register_function("series_sum", make_handler([](const Value& args) {
        bool infinite = true;
        long long b = -1;
        if (args.is_object() && args.has("b")) {
            const Value& bv = args["b"];
            if (bv.is_string()) {
                const std::string bs = bv.as_string();
                if (bs != "oo" && bs != "inf") {
                    b = std::stoll(bs);
                    infinite = false;
                }
            } else {
                b = bv.as_int();
                infinite = false;
            }
        }
        return Value(series_sum(get_string(args, "expr"),
                                get_string_opt(args, "var", "n"),
                                get_int_opt(args, "a", 1),
                                infinite ? -1 : b));
    }));
    register_function("series_convergence", make_handler([](const Value& args) {
        return Value(series_convergence(get_string(args, "expr"),
                                        get_string_opt(args, "var", "n")));
    }));
    register_function("power_series", make_handler([](const Value& args) {
        return Value(power_series(get_string(args, "expr"),
                                  get_string_opt(args, "var", "x"),
                                  get_double_opt(args, "point", 0.0),
                                  get_int_opt(args, "n", 5)));
    }));
    register_function("power_series_radius", make_handler([](const Value& args) {
        const double R = power_series_radius(get_string(args, "expr"),
                                             get_string_opt(args, "var", "n"));
        // R = ∞ 是合法且常见的答案（如 Σ xⁿ/n!）：JSON 没有 inf 字面量，
        // 直接 Value(inf) 会被序列化成 null，与"算不出"无法区分。
        // 与同模块的 limit 保持一致，用字符串 "oo" 表达。
        if (std::isinf(R)) return Value(std::string(R > 0 ? "oo" : "-oo"));
        return Value(R);
    }));
    register_function("leibniz_test", make_handler([](const Value& args) {
        return Value(leibniz_test(get_string(args, "expr"),
                                  get_string_opt(args, "var", "n")));
    }));
    register_function("integral_test", make_handler([](const Value& args) {
        return Value(integral_test(get_string(args, "expr"),
                                   get_string_opt(args, "var", "n")));
    }));
    register_function("p_series_test", make_handler([](const Value& args) {
        return Value(p_series_test(get_string(args, "expr"),
                                   get_string_opt(args, "var", "n")));
    }));
    register_function("limit_comparison_test", make_handler([](const Value& args) {
        return Value(limit_comparison_test(get_string(args, "expr"),
                                           get_string_opt(args, "var", "n")));
    }));
    register_function("direct_comparison_test", make_handler([](const Value& args) {
        return Value(direct_comparison_test(get_string(args, "expr"),
                                            get_string_opt(args, "var", "n"),
                                            get_string_opt(args, "compare_expr", "")));
    }));
    register_function("classify_and_test", make_handler([](const Value& args) {
        return Value(classify_and_test(get_string(args, "expr"),
                                       get_string_opt(args, "var", "n")));
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_calculus_registrar;

}  // namespace
