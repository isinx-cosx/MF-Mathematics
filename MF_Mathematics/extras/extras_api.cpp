// extras_api.cpp — 把 extras 模块与"数列乘积/绝对收敛"注册进引擎。
//
// 单独一个注册文件的原因：这批函数是被"视图里未接入引擎的模式"逼出来的补齐件，
// 集中在一处便于看出"为了哪些模式补了什么"，也不去改动已经很大的各模块 API 文件。

#include "extras.h"
#include "analysis.h"

#include "../calculus/series.h"
#include "../registry.hpp"
#include "../api_helpers.h"
#include "../json.hpp"

#include <cmath>
#include <complex>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::extras;
using mf::api::make_handler;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_int_opt;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_double_array;
using mf::api::to_double_array;
using mf::api::get_int_bounded;
using mf::api::get_int_opt_bounded;

// 二维数组参数 → vector<vector<double>>（空/非数值一律报错，不留给 Eigen 崩）
std::vector<std::vector<double>> get_matrix(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少矩阵参数 ") + key);
    const Value& m = args[key];
    if (m.size() == 0)
        throw std::invalid_argument(std::string("矩阵参数 ") + key +
                                    " 不能为空（应为 [[1,2],[3,4]] 这种二维数组）");
    std::vector<std::vector<double>> out;
    for (std::size_t i = 0; i < m.size(); ++i) {
        const Value& row = m.at(i);
        if (!row.is_array())
            throw std::invalid_argument(std::string("矩阵参数 ") + key + " 必须为二维数组");
        std::vector<double> r;
        for (std::size_t j = 0; j < row.size(); ++j) r.push_back(row.at(j).as_double());
        if (r.empty())
            throw std::invalid_argument(std::string("矩阵参数 ") + key + " 的第 " +
                                        std::to_string(i + 1) + " 行为空");
        out.push_back(std::move(r));
    }
    return out;
}

Value matrix_to_value(const std::vector<std::vector<double>>& M) {
    Value arr = Value::make_array();
    for (const auto& row : M) arr.push_back(to_double_array(row));
    return arr;
}

void register_all() {
    using mf::registry::register_function;

    /* ── 有限维线性代数 ─────────────────────────────────────────────────── */
    register_function("matrix_multiply", make_handler([](const Value& args) {
        return matrix_to_value(matrix_multiply(get_matrix(args, "A"), get_matrix(args, "B")));
    }));

    register_function("spectral_radius", make_handler([](const Value& args) {
        return Value(spectral_radius(get_matrix(args, "A")));
    }));

    register_function("adjoint_operator", make_handler([](const Value& args) {
        return matrix_to_value(adjoint_operator(get_matrix(args, "A")));
    }));

    register_function("is_self_adjoint", make_handler([](const Value& args) {
        const auto A = get_matrix(args, "A");
        Value obj = Value::make_object();
        obj.set("is_self_adjoint", Value(is_self_adjoint(A)));
        obj.set("note", Value(std::string(
            "实矩阵自伴 ⟺ 对称（A = Aᵀ）；复数情形要求 A = A*（共轭转置）。")));
        return obj;
    }));

    register_function("is_compact_operator", make_handler([](const Value& args) {
        Value obj = Value::make_object();
        obj.set("is_compact", Value(true));
        obj.set("reason", Value(compact_operator_reason(get_matrix(args, "A"))));
        return obj;
    }));

    register_function("fredholm_alternative", make_handler([](const Value& args) {
        const auto A = get_matrix(args, "A");
        std::vector<double> b;
        const bool has_b = args.is_object() && args.has("b") && args["b"].is_array() &&
                           args["b"].size() > 0;
        if (has_b) b = get_double_array(args, "b");
        return Value(fredholm_alternative(A, b, has_b));
    }));

    register_function("riesz_representation", make_handler([](const Value& args) {
        const std::vector<double> x = get_double_array(args, "x");
        Value obj = Value::make_object();
        obj.set("representer", to_double_array(riesz_representer(x)));
        obj.set("note", Value(std::string(
            "有限维 Hilbert 空间中每个连续线性泛函 f 都有唯一表示元 y 使 f(v) = ⟨v, y⟩；"
            "对 f(v) = ⟨v, x⟩ 而言表示元就是 x 本身。")));
        return obj;
    }));

    /* ── 复数 ───────────────────────────────────────────────────────────── */
    register_function("complex_conjugate", make_handler([](const Value& args) {
        return Value(complex_conjugate(get_string(args, "expr")));
    }));

    register_function("complex_modulus", make_handler([](const Value& args) {
        return Value(complex_modulus(get_string(args, "expr")));
    }));

    register_function("complex_argument", make_handler([](const Value& args) {
        const double rad = complex_argument(get_string(args, "expr"));
        Value obj = Value::make_object();
        obj.set("radians", Value(rad));
        obj.set("degrees", Value(rad * 180.0 / 3.14159265358979323846));
        return obj;
    }));

    register_function("dirichlet_eta", make_handler([](const Value& args) {
        return Value(dirichlet_eta(get_double(args, "s")));
    }));

    /* ── 数列乘积与绝对收敛（实现在 calculus/series.cpp，复用其通项求值）──── */
    register_function("product_sequence", make_handler([](const Value& args) {
        return Value(mf::calculus::product_sequence(
            get_string(args, "expr"), get_string_opt(args, "var", "n"),
            get_int_opt(args, "a", 1), get_int_opt_bounded(args, "b", 10, -9223372036854775807, 1000000, "上界")));
    }));

    register_function("infinite_product", make_handler([](const Value& args) {
        const auto r = mf::calculus::infinite_product(
            get_string(args, "expr"), get_string_opt(args, "var", "n"));
        Value obj = Value::make_object();
        obj.set("value", Value(r.value));
        obj.set("converges", Value(r.converges));
        obj.set("note", Value(r.note));
        return obj;
    }));

    register_function("absolute_convergence", make_handler([](const Value& args) {
        return Value(mf::calculus::absolute_convergence(
            get_string(args, "expr"), get_string_opt(args, "var", "n")));
    }));
    /* ── 曲线分析 / 微分方程 / 偏微分方程 / 复分析（analysis.cpp）──────── */
    register_function("calc_concavity", make_handler([](const Value& args) {
        const auto r = concavity(get_string(args, "expr"), get_string_opt(args, "var", "x"),
                                get_double_opt(args, "a", -2.0), get_double_opt(args, "b", 2.0));
        Value obj = Value::make_object();
        obj.set("conclusion", Value(r.conclusion));
        Value segs = Value::make_array();
        for (const auto& s : r.segments) segs.push_back(Value(s));
        obj.set("segments", segs);
        obj.set("interval", Value("[" + std::to_string(r.a) + ", " + std::to_string(r.b) + "]"));
        return obj;
    }));

    register_function("calc_inflection", make_handler([](const Value& args) {
        const auto r = inflection_points(get_string(args, "expr"), get_string_opt(args, "var", "x"),
                                        get_double_opt(args, "a", -5.0), get_double_opt(args, "b", 5.0));
        Value arr = Value::make_array();
        for (const auto& p : r.points) {
            Value obj = Value::make_object();
            obj.set("x", Value(p.x));
            obj.set("y", Value(p.y));
            arr.push_back(obj);
        }
        Value out = Value::make_object();
        out.set("points", arr);
        out.set("note", Value(r.note));
        return out;
    }));

    register_function("calc_asymptotes", make_handler([](const Value& args) {
        const auto r = asymptotes(get_string(args, "expr"), get_string_opt(args, "var", "x"));
        Value obj = Value::make_object();
        const auto put = [&](const char* key, const std::vector<std::string>& v) {
            Value arr = Value::make_array();
            for (const auto& s : v) arr.push_back(Value(s));
            obj.set(key, arr);
        };
        put("vertical", r.vertical);
        put("horizontal", r.horizontal);
        put("oblique", r.oblique);
        obj.set("note", Value(r.note));
        return obj;
    }));

    register_function("calc_curvature", make_handler([](const Value& args) {
        const auto r = curvature(get_string(args, "expr"), get_string_opt(args, "var", "x"),
                                 get_double_opt(args, "point", 0.0));
        Value obj = Value::make_object();
        obj.set("x", Value(r.x));
        obj.set("y", Value(r.y));
        obj.set("dy", Value(r.dy));
        obj.set("d2y", Value(r.d2y));
        obj.set("curvature", Value(r.curvature));
        obj.set("radius", Value(r.radius));
        obj.set("is_straight", Value(r.is_straight));
        return obj;
    }));

    register_function("calc_cauchy_mvt", make_handler([](const Value& args) {
        const auto r = cauchy_mvt(get_string(args, "expr"), get_string(args, "g_expr"),
                                  get_string_opt(args, "var", "x"),
                                  get_double_opt(args, "a", 0.0), get_double_opt(args, "b", 1.0));
        Value obj = Value::make_object();
        obj.set("found", Value(r.found));
        obj.set("c", Value(r.c));
        obj.set("lhs", Value(r.lhs));
        obj.set("rhs", Value(r.rhs));
        obj.set("note", Value(r.note));
        return obj;
    }));

    register_function("ode_first_order", make_handler([](const Value& args) {
        const auto r = ode_first_order(get_string(args, "f"), get_string_opt(args, "var", "x"),
                                       get_string_opt(args, "yvar", "y"));
        Value obj = Value::make_object();
        obj.set("kind", Value(r.kind));
        obj.set("solution", Value(r.solution));
        obj.set("note", Value(r.note));
        return obj;
    }));

    register_function("ode_constant_coefficients", make_handler([](const Value& args) {
        const auto r = ode_constant_coefficients(get_double_array(args, "coeffs"));
        Value obj = Value::make_object();
        obj.set("characteristic", Value(r.characteristic));
        Value roots = Value::make_array();
        for (const auto& s : r.roots) roots.push_back(Value(s));
        obj.set("roots", roots);
        obj.set("solution", Value(r.solution));
        return obj;
    }));

    register_function("ode_linear_system", make_handler([](const Value& args) {
        const auto r = ode_linear_system(get_matrix(args, "A"));
        Value obj = Value::make_object();
        obj.set("eigenvalues", Value(r.eigenvalues));
        obj.set("solution", Value(r.solution));
        obj.set("note", Value(r.note));
        return obj;
    }));

    register_function("classify_second_order_pde", make_handler([](const Value& args) {
        const auto r = classify_second_order_pde(get_double(args, "A"), get_double(args, "B"),
                                                 get_double(args, "C"));
        Value obj = Value::make_object();
        obj.set("type", Value(r.type));
        obj.set("discriminant", Value(r.discriminant));
        obj.set("canonical", Value(r.canonical));
        obj.set("note", Value(r.note));
        return obj;
    }));

    register_function("first_order_linear_pde", make_handler([](const Value& args) {
        const auto r = first_order_linear_pde(get_double(args, "a"), get_double(args, "b"),
                                              get_double_opt(args, "c", 0.0));
        Value obj = Value::make_object();
        obj.set("characteristics", Value(r.characteristics));
        obj.set("solution", Value(r.solution));
        obj.set("note", Value(r.note));
        return obj;
    }));

    register_function("zeros_and_poles", make_handler([](const Value& args) {
        const std::string func = get_string(args, "func");
        std::complex<double> center(0.0, 0.0);
        if (args.is_object() && args.has("center") && args["center"].is_array() &&
            args["center"].size() == 2)
            center = {args["center"].at(0).as_double(), args["center"].at(1).as_double()};
        const double radius = get_double_opt(args, "radius", 2.0);
        const auto r = zeros_and_poles(func, center, radius);
        const auto pts = [](const std::vector<std::pair<double, double>>& v) {
            Value arr = Value::make_array();
            for (const auto& p : v) {
                Value pt = Value::make_array();
                pt.push_back(Value(p.first));
                pt.push_back(Value(p.second));
                arr.push_back(pt);
            }
            return arr;
        };
        Value obj = Value::make_object();
        obj.set("zeros", pts(r.zeros));
        obj.set("poles", pts(r.poles));
        obj.set("note", Value(r.note));
        return obj;
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_extras_registrar;

}  // namespace
