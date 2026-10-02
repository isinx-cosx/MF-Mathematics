// algebra_api.cpp — algebra 包(combinatorics + number_theory)JSON 分发层。
//
// 注册 17 个 action。analytic_geometry 的函数稍后追加到本文件。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "combinatorics.h"
#include "number_theory.h"
#include "analytic_geometry.h"
#include "equation.h"
#include "function.h"
#include "expression.h"
#include "inequality.h"
#include "sequences.h"

#include <cmath>
#include <cstdint>
#include <limits>
#include <charconv>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::algebra;
using mf::api::make_handler;
using mf::api::get_int;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_keyword;
using mf::api::get_string_or_number;
using mf::api::get_int_array;
using mf::api::get_int_bounded;
using mf::api::get_int_opt_bounded;

// 点参数:[x, y]
Point get_point(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array() ||
        args[key].size() != 2)
        throw std::invalid_argument(std::string("缺少点参数 ") + key + "(须为 [x, y])");
    return {args[key].at(0).as_double(), args[key].at(1).as_double()};
}

Value point_to_value(Point p) {
    Value arr = Value::make_array();
    arr.push_back(Value(p.x));
    arr.push_back(Value(p.y));
    return arr;
}

// 数字 → 文本（与 analytic_geometry 里的 fmt 同风格：整数值补 ".0"）
std::string fmt_num(double d) {
    char buf[40];
    const auto res = std::to_chars(buf, buf + sizeof(buf), d, std::chars_format::general);
    std::string s(buf, res.ptr);
    if (s.find('.') == std::string::npos && s.find('e') == std::string::npos &&
        s.find('E') == std::string::npos)
        s += ".0";
    return s;
}

// 运算律结果 → JSON 对象
Value law_to_value(const LawResult& r) {
    Value obj = Value::make_object();
    obj.set("left", Value(r.left));
    obj.set("right", Value(r.right));
    obj.set("holds", Value(r.holds));
    return obj;
}

void register_all() {
    using mf::registry::register_function;

    // ── combinatorics ──────────────────────────────────────────────────────
    register_function("addition_principle", make_handler([](const Value& args) {
        return Value(addition_principle(get_int_array(args, "ways")));
    }));
    register_function("multiplication_principle",
                      make_handler([](const Value& args) {
        return Value(multiplication_principle(get_int_array(args, "steps")));
    }));
    register_function("permutation", make_handler([](const Value& args) {
        return Value(permutation(get_int_bounded(args, "n", -9223372036854775807, 1000000, "n"), get_int(args, "m")));
    }));
    register_function("combination", make_handler([](const Value& args) {
        return Value(combination(get_int_bounded(args, "n", -9223372036854775807, 1000000, "n"), get_int(args, "m")));
    }));
    register_function("comb_identities", make_handler([](const Value&) {
        const std::vector<std::string> ids = comb_identities();
        Value arr = Value::make_array();
        for (const std::string& s : ids) arr.push_back(Value(s));
        return arr;
    }));
    register_function("binomial_expand", make_handler([](const Value& args) {
        return Value(binomial_expand(get_string_or_number(args, "a"),
                                     get_string_or_number(args, "b"),
                                     get_int_bounded(args, "n", -9223372036854775807, 1000, "二项式指数 n")));
    }));
    register_function("binomial_term", make_handler([](const Value& args) {
        const BinomialTerm bt = binomial_term(
            get_string_or_number(args, "a"), get_string_or_number(args, "b"),
            get_int_bounded(args, "n", -9223372036854775807, 1000, "二项式指数 n"), get_int(args, "k"));
        Value obj = Value::make_object();
        obj.set("term", Value(bt.term));
        obj.set("coefficient", Value(bt.coefficient));
        obj.set("k", Value(bt.k));
        obj.set("term_number", Value(bt.term_number));
        return obj;
    }));

    // ── number_theory(数与运算)────────────────────────────────────────────
    register_function("commutative_law", make_handler([](const Value& args) {
        return law_to_value(commutative_law(
            get_double(args, "a"), get_double(args, "b"), get_string(args, "op")));
    }));
    register_function("associative_law", make_handler([](const Value& args) {
        return law_to_value(associative_law(
            get_double(args, "a"), get_double(args, "b"), get_double(args, "c"),
            get_string(args, "op")));
    }));
    register_function("distributive_law", make_handler([](const Value& args) {
        return law_to_value(distributive_law(
            get_double(args, "a"), get_double(args, "b"), get_double(args, "c")));
    }));
    register_function("abs_value", make_handler([](const Value& args) {
        return Value(abs_value(get_double(args, "x")));
    }));
    register_function("distance_on_number_line",
                      make_handler([](const Value& args) {
        return Value(distance_on_number_line(get_double(args, "a"),
                                             get_double(args, "b")));
    }));
    register_function("ratio", make_handler([](const Value& args) {
        const Ratio r = ratio(get_double(args, "a"), get_double(args, "b"));
        Value arr = Value::make_array();
        arr.push_back(Value(r.num));
        arr.push_back(Value(r.den));
        return arr;
    }));
    register_function("percentage", make_handler([](const Value& args) {
        return Value(percentage(get_double(args, "part"),
                                get_double(args, "total")));
    }));
    register_function("percentage_change", make_handler([](const Value& args) {
        return Value(percentage_change(get_double(args, "old"),
                                       get_double(args, "new")));
    }));
    register_function("to_scientific_notation",
                      make_handler([](const Value& args) {
        const ScientificNotation sn = to_scientific_notation(get_double(args, "x"));
        Value arr = Value::make_array();
        arr.push_back(Value(sn.coefficient));
        arr.push_back(Value(sn.exponent));
        return arr;
    }));
    register_function("significant_figures", make_handler([](const Value& args) {
        return Value(significant_figures(get_double(args, "x"),
                                         get_int(args, "n")));
    }));

    // ── analytic_geometry ──────────────────────────────────────────────────
    register_function("distance", make_handler([](const Value& args) {
        return Value(distance(get_point(args, "p1"), get_point(args, "p2")));
    }));
    register_function("midpoint", make_handler([](const Value& args) {
        return point_to_value(midpoint(get_point(args, "p1"), get_point(args, "p2")));
    }));
    register_function("line_from_points", make_handler([](const Value& args) {
        const LineFromPoints r =
            line_from_points(get_point(args, "p1"), get_point(args, "p2"));
        Value obj = Value::make_object();
        obj.set("two_point", Value(r.two_point));
        obj.set("point_slope", Value(r.point_slope));
        obj.set("slope_intercept", Value(r.slope_intercept));
        obj.set("general", Value(r.general));
        obj.set("slope", Value(r.slope));
        return obj;
    }));
    register_function("line_from_slope_intercept",
                      make_handler([](const Value& args) {
        const LineSlopeIntercept r = line_from_slope_intercept(
            get_double(args, "k"), get_double(args, "b"));
        Value obj = Value::make_object();
        obj.set("slope_intercept", Value(r.slope_intercept));
        obj.set("general", Value(r.general));
        Value pts = Value::make_array();
        pts.push_back(point_to_value(r.points[0]));
        pts.push_back(point_to_value(r.points[1]));
        obj.set("points", std::move(pts));
        obj.set("slope", Value(r.slope));
        obj.set("y_intercept", Value(r.y_intercept));
        return obj;
    }));
    register_function("line_from_point_slope", make_handler([](const Value& args) {
        const LinePointSlope r = line_from_point_slope(
            get_point(args, "p"), get_double(args, "k"));
        Value obj = Value::make_object();
        obj.set("point_slope", Value(r.point_slope));
        obj.set("slope_intercept", Value(r.slope_intercept));
        obj.set("general", Value(r.general));
        obj.set("slope", Value(r.slope));
        obj.set("point", point_to_value(r.point));
        return obj;
    }));
    register_function("line_from_intercepts", make_handler([](const Value& args) {
        const LineIntercepts r =
            line_from_intercepts(get_double(args, "a"), get_double(args, "b"));
        Value obj = Value::make_object();
        obj.set("intercept_form", Value(r.intercept_form));
        obj.set("slope_intercept", Value(r.slope_intercept));
        obj.set("general", Value(r.general));
        obj.set("x_intercept", Value(r.x_intercept));
        obj.set("y_intercept", Value(r.y_intercept));
        obj.set("slope", Value(r.slope));
        return obj;
    }));
    register_function("line_general", make_handler([](const Value& args) {
        const LineGeneral r = line_general(get_double(args, "A"),
                                           get_double(args, "B"),
                                           get_double(args, "C"));
        Value obj = Value::make_object();
        obj.set("general", Value(r.general));
        obj.set("slope", Value(r.slope));
        obj.set("slope_intercept", Value(r.slope_intercept));
        obj.set("has_x_intercept", Value(r.has_x_intercept));
        obj.set("x_intercept", Value(r.x_intercept));
        obj.set("has_y_intercept", Value(r.has_y_intercept));
        obj.set("y_intercept", Value(r.y_intercept));
        return obj;
    }));
    register_function("circle_standard", make_handler([](const Value& args) {
        const CircleStandard r =
            circle_standard(get_point(args, "center"), get_double(args, "r"));
        Value obj = Value::make_object();
        obj.set("standard", Value(r.standard));
        obj.set("general", Value(r.general));
        obj.set("center", point_to_value(r.center));
        obj.set("radius", Value(r.radius));
        obj.set("diameter", Value(r.diameter));
        obj.set("circumference", Value(r.circumference));
        obj.set("area", Value(r.area));
        return obj;
    }));
    register_function("circle_general", make_handler([](const Value& args) {
        const CircleGeneral r = circle_general(get_double(args, "D"),
                                               get_double(args, "E"),
                                               get_double(args, "F"));
        if (r.is_imaginary)
            return Value(std::string("表示一个虚圆（半径的平方为负数，无实数解）"));
        Value obj = Value::make_object();
        obj.set("center", point_to_value(r.center));
        obj.set("radius", Value(r.radius));
        obj.set("r_squared", Value(r.r_squared));
        obj.set("standard", Value(r.standard));
        obj.set("general", Value(r.general));
        return obj;
    }));

    // ── 圆锥曲线（中心/顶点在原点）─────────────────────────────────────────
    register_function("ellipse_standard", make_handler([](const Value& args) {
        const EllipseInfo r = ellipse_standard(get_double(args, "a"), get_double(args, "b"));
        Value obj = Value::make_object();
        obj.set("standard", Value(r.standard));
        obj.set("general", Value(r.general));
        obj.set("a", Value(r.a));
        obj.set("b", Value(r.b));
        obj.set("c", Value(r.c));
        obj.set("eccentricity", Value(r.eccentricity));
        obj.set("axis", Value(std::string(r.is_vertical ? "长轴沿 y 轴" : "长轴沿 x 轴")));
        obj.set("focus1", Value(std::string("(" + fmt_num(r.focus1_x) + ", " + fmt_num(r.focus1_y) + ")")));
        obj.set("focus2", Value(std::string("(" + fmt_num(r.focus2_x) + ", " + fmt_num(r.focus2_y) + ")")));
        obj.set("directrix", Value(r.directrix));
        obj.set("area", Value(r.area));
        return obj;
    }));
    register_function("hyperbola_standard", make_handler([](const Value& args) {
        const HyperbolaInfo r = hyperbola_standard(get_double(args, "a"), get_double(args, "b"));
        Value obj = Value::make_object();
        obj.set("standard", Value(r.standard));
        obj.set("general", Value(r.general));
        obj.set("a", Value(r.a));
        obj.set("b", Value(r.b));
        obj.set("c", Value(r.c));
        obj.set("eccentricity", Value(r.eccentricity));
        obj.set("focus1", Value(std::string("(" + fmt_num(r.focus1_x) + ", " + fmt_num(r.focus1_y) + ")")));
        obj.set("focus2", Value(std::string("(" + fmt_num(r.focus2_x) + ", " + fmt_num(r.focus2_y) + ")")));
        obj.set("asymptote1", Value(r.asymptote1));
        obj.set("asymptote2", Value(r.asymptote2));
        obj.set("directrix", Value(r.directrix));
        return obj;
    }));
    register_function("parabola_standard", make_handler([](const Value& args) {
        const ParabolaInfo r =
            parabola_standard(get_double(args, "p"), get_string_opt(args, "axis", "x"));
        Value obj = Value::make_object();
        obj.set("standard", Value(r.standard));
        obj.set("general", Value(r.general));
        obj.set("p", Value(r.p));
        obj.set("axis", Value(r.axis));
        obj.set("opening", Value(r.opening));
        obj.set("focus", Value(std::string("(" + fmt_num(r.focus_x) + ", " + fmt_num(r.focus_y) + ")")));
        obj.set("directrix", Value(r.directrix));
        obj.set("latus_rectum", Value(r.latus_rectum));
        return obj;
    }));

    // ── equation(方程)──────────────────────────────────────────────────────
    register_function("solve_linear", make_handler([](const Value& args) {
        return Value(solve_linear(get_string(args, "expr"),
                                  get_string_opt(args, "var", "x")));
    }));
    register_function("alg_solve_linear_system", make_handler([](const Value& args) {
        const LinearSystemResult r = solve_linear_system(
            get_string(args, "eq1"), get_string(args, "eq2"),
            get_string_opt(args, "var1", "x"), get_string_opt(args, "var2", "y"));
        if (!r.solvable) return Value(std::string("无解或无穷多解"));
        Value obj = Value::make_object();
        obj.set(get_string_opt(args, "var1", "x"), Value(r.x));
        obj.set(get_string_opt(args, "var2", "y"), Value(r.y));
        return obj;
    }));
    register_function("solve_quadratic", make_handler([](const Value& args) {
        const std::vector<std::string> roots =
            solve_quadratic(get_string(args, "expr"),
                            get_string_opt(args, "var", "x"));
        Value arr = Value::make_array();
        for (const std::string& s : roots) arr.push_back(Value(s));
        return arr;
    }));
    register_function("discriminant", make_handler([](const Value& args) {
        const DiscriminantResult r = discriminant(
            get_string(args, "expr"), get_string_opt(args, "var", "x"));
        Value obj = Value::make_object();
        obj.set("delta", Value(r.delta));
        obj.set("nature", Value(r.nature));
        return obj;
    }));
    register_function("vieta_theorem", make_handler([](const Value& args) {
        const VietaResult r = vieta_theorem(
            get_string(args, "expr"), get_string_opt(args, "var", "x"));
        Value obj = Value::make_object();
        obj.set("sum_of_roots", Value(r.sum_of_roots));
        obj.set("product_of_roots", Value(r.product_of_roots));
        Value arr = Value::make_array();
        for (const std::string& s : r.roots) arr.push_back(Value(s));
        obj.set("roots", std::move(arr));
        return obj;
    }));
    register_function("solve_fractional", make_handler([](const Value& args) {
        const FractionalResult r = solve_fractional(
            get_string(args, "expr"), get_string_opt(args, "var", "x"));
        Value obj = Value::make_object();
        Value v = Value::make_array();
        for (const std::string& s : r.valid) v.push_back(Value(s));
        obj.set("valid_solutions", std::move(v));
        v = Value::make_array();
        for (const std::string& s : r.extraneous) v.push_back(Value(s));
        obj.set("extraneous_solutions", std::move(v));
        return obj;
    }));
    register_function("solve_irrational", make_handler([](const Value& args) {
        const FractionalResult r = solve_irrational(
            get_string(args, "expr"), get_string_opt(args, "var", "x"));
        Value obj = Value::make_object();
        Value v = Value::make_array();
        for (const std::string& s : r.valid) v.push_back(Value(s));
        obj.set("valid_solutions", std::move(v));
        v = Value::make_array();
        for (const std::string& s : r.extraneous) v.push_back(Value(s));
        obj.set("extraneous_solutions", std::move(v));
        return obj;
    }));

    // ── function(函数)──────────────────────────────────────────────────────
    register_function("domain", make_handler([](const Value& args) {
        return Value(domain(get_string(args, "expr"),
                            get_string_opt(args, "var", "x")));
    }));
    register_function("range_estimate", make_handler([](const Value& args) {
        return Value(range_estimate(get_string(args, "expr"),
                                    get_string_opt(args, "var", "x")));
    }));
    register_function("correspondence_rule", make_handler([](const Value& args) {
        return Value(correspondence_rule(get_string(args, "expr")));
    }));
    register_function("linear_function", make_handler([](const Value& args) {
        return Value(linear_function(get_double(args, "k"),
                                     get_double_opt(args, "b", 0.0)));
    }));
    register_function("slope_intercept", make_handler([](const Value& args) {
        const SlopeInterceptResult r = slope_intercept(get_double(args, "k"),
                                                       get_double(args, "b"));
        Value obj = Value::make_object();
        obj.set("slope", Value(r.slope));
        obj.set("intercept", Value(r.intercept));
        obj.set("angle_degrees", Value(r.angle_degrees));
        obj.set("x_intercept", Value(r.x_intercept));
        return obj;
    }));
    register_function("inverse_proportional", make_handler([](const Value& args) {
        return Value(inverse_proportional(get_double(args, "k")));
    }));
    register_function("quadratic_function", make_handler([](const Value& args) {
        const QuadraticResult r = quadratic_function(
            get_double(args, "a"), get_double(args, "b"), get_double(args, "c"));
        Value obj = Value::make_object();
        Value vtx = Value::make_array();
        vtx.push_back(Value(r.vertex_x));
        vtx.push_back(Value(r.vertex_y));
        obj.set("vertex", std::move(vtx));
        obj.set("axis_of_symmetry", Value(r.axis));
        obj.set("direction", Value(r.direction));
        obj.set("y_intercept", Value(r.y_intercept));
        obj.set("x_intercepts", Value(r.x_intercepts));
        return obj;
    }));
    register_function("quadratic_extrema", make_handler([](const Value& args) {
        const ExtremaResult r = quadratic_extrema(
            get_double(args, "a"), get_double(args, "b"), get_double(args, "c"));
        Value obj = Value::make_object();
        obj.set("type", Value(r.type));
        obj.set("x", Value(r.x));
        obj.set("value", Value(r.value));
        return obj;
    }));
    register_function("power_function", make_handler([](const Value& args) {
        const PowerResult r = power_function(
            get_string_or_number(args, "x"), get_double(args, "n"));
        if (r.numeric) return Value(r.value);
        return Value(r.expr);
    }));
    register_function("exponential_function", make_handler([](const Value& args) {
        return Value(exponential_function(get_double(args, "base"),
                                          get_double(args, "x")));
    }));
    register_function("log_function", make_handler([](const Value& args) {
        return Value(log_function(get_double(args, "base"),
                                  get_double(args, "x")));
    }));
    register_function("sine_cosine_tangent", make_handler([](const Value& args) {
        const TrigResult r = sine_cosine_tangent(
            get_double(args, "angle"), get_string_opt(args, "mode", "degrees"));
        Value obj = Value::make_object();
        obj.set("sin", Value(r.sin_val));
        obj.set("cos", Value(r.cos_val));
        obj.set("tan", Value(r.tan_val));
        return obj;
    }));
    register_function("trig_basic_identities", make_handler([](const Value&) {
        Value arr = Value::make_array();
        for (const std::string& s : trig_basic_identities())
            arr.push_back(Value(s));
        return arr;
    }));
    register_function("trig_periodicity", make_handler([](const Value& args) {
        const PeriodicityResult r = trig_periodicity(get_string(args, "func"));
        Value obj = Value::make_object();
        obj.set("period", Value(r.period));
        obj.set("frequency", Value(r.frequency));
        obj.set("description", Value(r.description));
        return obj;
    }));

    // ── expression ──────────────────────────────────────────────────────────
    register_function("simplify_polynomial", make_handler([](const Value& args) {
        return Value(simplify_polynomial(get_string(args, "expr")));
    }));
    register_function("expand_expression", make_handler([](const Value& args) {
        return Value(expand_expression(get_string(args, "expr")));
    }));
    register_function("factor", make_handler([](const Value& args) {
        return Value(factor(get_string(args, "expr")));
    }));
    register_function("factor_common", make_handler([](const Value& args) {
        return Value(factor_common(get_string(args, "expr")));
    }));
    register_function("factor_perfect_square", make_handler([](const Value& args) {
        return Value(factor_perfect_square(get_string(args, "expr")));
    }));
    register_function("factor_difference_squares", make_handler([](const Value& args) {
        return Value(factor_difference_squares(get_string(args, "expr")));
    }));
    register_function("factor_cross", make_handler([](const Value& args) {
        return Value(factor_cross(get_string(args, "expr")));
    }));
    register_function("factor_group", make_handler([](const Value& args) {
        return Value(factor_group(get_string(args, "expr")));
    }));
    register_function("simplify_fraction", make_handler([](const Value& args) {
        return Value(simplify_fraction(get_string(args, "expr")));
    }));
    register_function("common_denominator", make_handler([](const Value& args) {
        const CommonDenominatorResult r = common_denominator(
            get_string(args, "expr1"), get_string(args, "expr2"));
        Value obj = Value::make_object();
        obj.set("new1", Value(r.new1));
        obj.set("new2", Value(r.new2));
        obj.set("den", Value(r.den));
        return obj;
    }));
    register_function("fraction_operations", make_handler([](const Value& args) {
        return Value(fraction_operations(get_string(args, "expr1"),
                                         get_string(args, "op"),
                                         get_string(args, "expr2")));
    }));
    register_function("rationalize_denominator", make_handler([](const Value& args) {
        return Value(rationalize_denominator(get_string(args, "expr")));
    }));
    register_function("simplify_radical", make_handler([](const Value& args) {
        return Value(simplify_radical(get_string(args, "expr")));
    }));
    register_function("like_radicals", make_handler([](const Value& args) {
        const LikeRadicalsResult r =
            like_radicals(get_string(args, "expr1"), get_string(args, "expr2"));
        Value obj = Value::make_object();
        obj.set("is_like", Value(r.is_like));
        obj.set("radical1", Value(r.radical1));
        obj.set("radical2", Value(r.radical2));
        return obj;
    }));
    register_function("radical_operations", make_handler([](const Value& args) {
        return Value(radical_operations(get_string(args, "expr1"),
                                        get_string(args, "op"),
                                        get_string(args, "expr2")));
    }));

    // ── inequality ──────────────────────────────────────────────────────────
    register_function("inequality_properties", make_handler([](const Value& args) {
        const auto props = inequality_properties(
            get_double(args, "a"), get_double(args, "b"), get_double(args, "c"));
        Value arr = Value::make_array();
        for (const auto& s : props) arr.push_back(Value(s));
        return arr;
    }));
    register_function("solve_linear_inequality", make_handler([](const Value& args) {
        return Value(solve_linear_inequality(get_string(args, "expr")));
    }));
    register_function("solve_inequality_system", make_handler([](const Value& args) {
        const Value& arr = args["ineqs"];
        std::vector<std::string> ineqs;
        for (std::size_t i = 0; i < arr.size(); ++i)
            ineqs.push_back(arr.at(i).as_string());
        return Value(solve_inequality_system(ineqs));
    }));
    register_function("solve_quadratic_inequality", make_handler([](const Value& args) {
        return Value(solve_quadratic_inequality(get_string(args, "expr")));
    }));
    register_function("am_gm_inequality", make_handler([](const Value& args) {
        const AmGmResult r = am_gm_inequality(get_double(args, "a"),
                                              get_double(args, "b"));
        Value obj = Value::make_object();
        obj.set("AM", Value(r.AM));
        obj.set("GM", Value(r.GM));
        return obj;
    }));
    register_function("max_min_initial", make_handler([](const Value& args) {
        const MaxMinResult r = max_min_initial(get_double(args, "a"),
                                               get_double(args, "b"));
        Value obj = Value::make_object();
        obj.set("min", Value(r.min));
        obj.set("max", Value(r.max));
        obj.set("GM", Value(r.GM));
        obj.set("AM", Value(r.AM));
        return obj;
    }));

    // ── sequences ───────────────────────────────────────────────────────────
    register_function("sequence_term", make_handler([](const Value& args) {
        return Value(sequence_term(get_string(args, "formula"),
                                   get_int(args, "n")));
    }));
    register_function("arithmetic_sequence", make_handler([](const Value& args) {
        const auto terms = arithmetic_sequence(
            get_double(args, "a1"), get_double(args, "d"), get_int_bounded(args, "n", -9223372036854775807, 100000, "项数"));
        Value arr = Value::make_array();
        for (double t : terms) arr.push_back(Value(t));
        return arr;
    }));
    register_function("arithmetic_sum", make_handler([](const Value& args) {
        return Value(arithmetic_sum(get_double(args, "a1"), get_double(args, "d"),
                                    get_int(args, "n")));
    }));
    register_function("arithmetic_proof", make_handler([](const Value&) {
        return Value(arithmetic_proof());
    }));
    register_function("geometric_sequence", make_handler([](const Value& args) {
        const auto terms = geometric_sequence(
            get_double(args, "a1"), get_double(args, "q"), get_int_bounded(args, "n", -9223372036854775807, 100000, "项数"));
        Value arr = Value::make_array();
        for (double t : terms) arr.push_back(Value(t));
        return arr;
    }));
    register_function("geometric_sum", make_handler([](const Value& args) {
        return Value(geometric_sum(get_double(args, "a1"), get_double(args, "q"),
                                   get_int_bounded(args, "n", -9223372036854775807, 100000, "项数")));
    }));
    register_function("geometric_proof", make_handler([](const Value&) {
        return Value(geometric_proof());
    }));
    register_function("recurrence_sequence", make_handler([](const Value& args) {
        std::vector<double> initial;
        const Value& iv = args["initial"];
        for (std::size_t i = 0; i < iv.size(); ++i)
            initial.push_back(iv.at(i).as_double());
        // rule 用 get_keyword 取**原始串**：`a[-1]` 是引擎自定义语法，表达式归一化
        // 会在 `a` 与 `[` 之间补乘号把它毁掉（a[-1] → a*[-1]）。归一化交给
        // recurrence_sequence 内部、在代入数值之后做。
        const auto terms = recurrence_sequence(
            initial, get_keyword(args, "rule"), get_int_bounded(args, "n", -9223372036854775807, 100000, "项数"));
        Value arr = Value::make_array();
        for (double t : terms) arr.push_back(Value(t));
        return arr;
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_algebra_registrar;

}  // namespace
