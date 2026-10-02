// complex_analysis_api.cpp — complex_analysis 包 JSON 分发层。
//
// 注册 30 个 action:complex_integral + complex_topology + conformal +
// holomorphic + series + elementary_funcs + zeta + residue。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "complex_integral.h"
#include "complex_topology.h"
#include "conformal.h"
#include "holomorphic.h"
#include "series.h"
#include "elementary_funcs.h"
#include "zeta.h"
#include "residue.h"

#include <complex>
#include <cstdint>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::complex_analysis;
using mf::api::make_handler;
using mf::api::get_int;
using mf::api::get_int_opt;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_int_bounded;
using mf::api::get_int_opt_bounded;

// 复数 [re, im]。
Value c2v(std::complex<double> c) {
    Value arr = Value::make_array();
    arr.push_back(Value(c.real()));
    arr.push_back(Value(c.imag()));
    return arr;
}

// 解析复数:数字 / [re, im] / "a±bi"。
std::complex<double> parse_complex(const Value& v) {
    if (v.is_number()) return {v.as_double(), 0.0};
    if (v.is_array() && v.size() >= 2)
        return {v.at(0).as_double(), v.at(1).as_double()};
    if (v.is_string()) {
        std::string s = v.as_string();
        bool has_i = false;
        for (char& c : s)
            if (c == 'i' || c == 'I') {
                c = 'i';
                has_i = true;
            }
        if (!has_i) return {std::stod(s), 0.0};
        // a ± bi 形式。
        std::string re_s, im_s;
        char sign = '+';
        std::size_t idx = 0;
        while (idx < s.size() && s[idx] != '+' && s[idx] != '-') ++idx;
        re_s = s.substr(0, idx);
        if (idx < s.size()) sign = s[idx++];
        im_s = s.substr(idx);
        if (im_s == "i") im_s = "1";
        else if (im_s == "-i") im_s = "-1";
        else if (im_s.size() > 1 && im_s.back() == 'i') im_s.pop_back();
        double re = re_s.empty() ? 0.0 : std::stod(re_s);
        double im = im_s.empty() ? 1.0 : std::stod(im_s);
        if (sign == '-') im = -im;
        return {re, im};
    }
    throw std::invalid_argument("无法解析为复数");
}

// 圆规格 "circle(center, r)"。
void parse_circle(const std::string& spec, std::complex<double>& center,
                  double& radius) {
    const std::size_t lp = spec.find('(');
    if (spec.rfind("circle", 0) != 0 || lp == std::string::npos ||
        spec.back() != ')')
        throw std::invalid_argument("无法解析 contour: " + spec);
    std::string inner = spec.substr(lp + 1, spec.size() - lp - 2);
    const std::size_t comma = inner.rfind(',');
    if (comma == std::string::npos) throw std::invalid_argument("circle 需要两个参数");
    center = parse_complex(Value(inner.substr(0, comma)));
    radius = std::stod(inner.substr(comma + 1));
}

// 区域:字符串命名 → 解析判定;点集 → 离散判定。
bool resolve_region_args(const Value& args,
                         std::vector<std::pair<double, double>>& pts,
                         bool& named, std::string& name) {
    named = false;
    if (args.is_object() && args.has("region")) {
        const Value& r = args["region"];
        if (r.is_string()) {
            named = true;
            name = r.as_string();
            return true;
        }
        if (r.is_array()) {
            for (std::size_t i = 0; i < r.size(); ++i)
                pts.emplace_back(r.at(i).at(0).as_double(),
                                 r.at(i).at(1).as_double());
            return false;
        }
    }
    throw std::invalid_argument("缺少区域参数");
}

void register_all() {
    using mf::registry::register_function;

    // ── complex_integral ────────────────────────────────────────────────────
    register_function("contour_integral", make_handler([](const Value& args) {
        std::complex<double> center;
        double radius, a, b;
        if (args.is_object() && args.has("gamma") && args["gamma"].is_string()) {
            parse_circle(args["gamma"].as_string(), center, radius);
        } else {
            throw std::invalid_argument("gamma 必须为 circle(center, r)");
        }
        if (args.is_object() && args.has("t_range")) {
            const Value& tr = args["t_range"];
            a = tr.at(0).as_double();
            b = tr.at(1).as_double();
        } else {
            a = 0.0;
            b = 6.283185307179586;
        }
        return c2v(contour_integral_circle(get_string(args, "func"), center, radius,
                                           a, b, get_int_opt_bounded(args, "n_points", 1000, -9223372036854775807, 10000, "围道点数")));
    }));

    register_function("cauchy_theorem", make_handler([](const Value& args) {
        std::complex<double> center;
        double radius;
        parse_circle(get_string(args, "contour"), center, radius);
        const CauchyTheoremResult r = cauchy_theorem(get_string(args, "func"), center, radius);
        Value obj = Value::make_object();
        obj.set("integral", c2v(r.integral));
        obj.set("zero", Value(r.zero));
        return obj;
    }));

    register_function("cauchy_integral_formula", make_handler([](const Value& args) {
        std::complex<double> center;
        double radius;
        parse_circle(get_string(args, "contour"), center, radius);
        const CauchyFormulaResult r = cauchy_integral_formula(
            get_string(args, "func"), parse_complex(args["a"]), center, radius,
            get_int_opt_bounded(args, "n_points", 1000, -9223372036854775807, 10000, "围道点数"));
        Value obj = Value::make_object();
        obj.set("cauchy_formula", c2v(r.cauchy_formula));
        obj.set("direct_f_a", c2v(r.direct_f_a));
        obj.set("error", Value(r.error));
        return obj;
    }));

    register_function("derivative_formula", make_handler([](const Value& args) {
        std::complex<double> center;
        double radius;
        parse_circle(get_string(args, "contour"), center, radius);
        const DerivativeFormulaResult r = derivative_formula(
            get_string(args, "func"), parse_complex(args["a"]),
            get_int_bounded(args, "n", -9223372036854775807, 100, "阶数"), center, radius,
            get_int_opt_bounded(args, "n_points", 1000, -9223372036854775807, 10000, "围道点数"));
        Value obj = Value::make_object();
        obj.set("derivative", c2v(r.derivative));
        obj.set("symbolic", c2v(r.symbolic));
        return obj;
    }));

    // ── complex_topology ────────────────────────────────────────────────────
    register_function("is_open", make_handler([](const Value& args) {
        std::vector<std::pair<double, double>> pts;
        bool named;
        std::string name;
        resolve_region_args(args, pts, named, name);
        const std::complex<double> p = parse_complex(args["point"]);
        const double eps = get_double_opt(args, "epsilon", 1e-6);
        if (named) {
            if (name == "unit_disk")
                return Value(p.real() * p.real() + p.imag() * p.imag() < 1.0);
            if (name == "separated_disks") {
                const double d1 = (p.real() + 1.5) * (p.real() + 1.5) + p.imag() * p.imag();
                const double d2 = (p.real() - 1.5) * (p.real() - 1.5) + p.imag() * p.imag();
                return Value(d1 < 0.25 || d2 < 0.25);
            }
            throw std::invalid_argument("未知区域名称: " + name);
        }
        return Value(is_open(pts, p.real(), p.imag(), eps));
    }));

    register_function("is_connected", make_handler([](const Value& args) {
        std::vector<std::pair<double, double>> pts;
        bool named;
        std::string name;
        resolve_region_args(args, pts, named, name);
        const double th = get_double_opt(args, "connect_threshold", 0.1);
        if (named) {
            if (name == "unit_disk") return Value(true);
            if (name == "separated_disks") return Value(false);
            throw std::invalid_argument("未知区域名称: " + name);
        }
        return Value(is_connected(pts, th));
    }));

    register_function("is_domain", make_handler([](const Value& args) {
        std::vector<std::pair<double, double>> pts;
        bool named;
        std::string name;
        resolve_region_args(args, pts, named, name);
        const double eps = get_double_opt(args, "epsilon", 1e-6);
        const double th = get_double_opt(args, "connect_threshold", 0.1);
        if (named) {
            if (name == "unit_disk") return Value(true);
            if (name == "separated_disks") return Value(false);
            throw std::invalid_argument("未知区域名称: " + name);
        }
        return Value(is_domain(pts, eps, th));
    }));

    // ── conformal ───────────────────────────────────────────────────────────
    register_function("is_conformal", make_handler([](const Value& args) {
        const ConformalResult r =
            is_conformal(get_string(args, "func"), parse_complex(args["z"]));
        Value obj = Value::make_object();
        obj.set("isConformal", Value(r.is_conformal));
        obj.set("derivative", c2v(r.derivative));
        return obj;
    }));

    register_function("riemann_mapping", make_handler([](const Value& args) {
        return Value(riemann_mapping(get_string(args, "region")));
    }));

    register_function("boundary_correspondence", make_handler([](const Value& args) {
        const auto samples = boundary_correspondence(
            get_string(args, "func"), get_string_opt(args, "region", "unit"));
        Value arr = Value::make_array();
        for (const auto& s : samples) {
            Value pt = Value::make_array();
            pt.push_back(c2v(s.z));
            pt.push_back(c2v(s.w));
            arr.push_back(pt);
        }
        return arr;
    }));

    // ── holomorphic ─────────────────────────────────────────────────────────
    register_function("is_holomorphic", make_handler([](const Value& args) {
        return Value(is_holomorphic(get_string(args, "func"), parse_complex(args["z"])));
    }));

    register_function("cauchy_riemann", make_handler([](const Value& args) {
        const CauchyRiemannResult r =
            cauchy_riemann(get_string(args, "u"), get_string(args, "v"));
        Value obj = Value::make_object();
        obj.set("cr1", Value(r.cr1));
        obj.set("cr2", Value(r.cr2));
        obj.set("both", Value(r.both));
        obj.set("u_x", Value(r.u_x));
        obj.set("v_y", Value(r.v_y));
        obj.set("u_y", Value(r.u_y));
        obj.set("v_x", Value(r.v_x));
        return obj;
    }));

    register_function("is_harmonic", make_handler([](const Value& args) {
        return Value(is_harmonic(get_string(args, "func")));
    }));

    // ── series ──────────────────────────────────────────────────────────────
    register_function("taylor_series", make_handler([](const Value& args) {
        return Value(taylor_series(get_string(args, "func"),
                                   parse_complex(args["z0"]),
                                   get_int_opt_bounded(args, "n", 6, -9223372036854775807, 200, "级数项数")));
    }));

    register_function("laurent_series", make_handler([](const Value& args) {
        return Value(laurent_series(get_string(args, "func"),
                                    parse_complex(args["z0"]),
                                    get_int_opt_bounded(args, "n", 5, -9223372036854775807, 200, "级数项数")));
    }));

    register_function("singularity_classify", make_handler([](const Value& args) {
        const SingularityResult r =
            singularity_classify(get_string(args, "func"), parse_complex(args["z0"]));
        Value obj = Value::make_object();
        obj.set("classification", Value(r.classification));
        obj.set("pole_order", Value(r.pole_order));
        return obj;
    }));

    register_function("pole_order", make_handler([](const Value& args) {
        return Value(pole_order(get_string(args, "func"), parse_complex(args["z0"])));
    }));

    // ── elementary_funcs ────────────────────────────────────────────────────
    register_function("exp_complex", make_handler([](const Value& args) {
        return c2v(exp_complex(parse_complex(args["z"])));
    }));
    register_function("log_complex", make_handler([](const Value& args) {
        return c2v(log_complex(parse_complex(args["z"]),
                               get_double_opt(args, "branch_cut", -3.141592653589793)));
    }));
    register_function("sqrt_complex", make_handler([](const Value& args) {
        return c2v(sqrt_complex(parse_complex(args["z"])));
    }));
    register_function("mobius_transform", make_handler([](const Value& args) {
        return c2v(mobius_transform(parse_complex(args["z"]), parse_complex(args["a"]),
                                    parse_complex(args["b"]), parse_complex(args["c"]),
                                    parse_complex(args["d"])));
    }));

    // ── zeta ────────────────────────────────────────────────────────────────
    register_function("zeta_series", make_handler([](const Value& args) {
        return c2v(zeta_series(parse_complex(args["s"]),
                               get_int_opt_bounded(args, "n_terms", 1000, -9223372036854775807, 1000000, "级数项数")));
    }));
    register_function("analytic_continuation_zeta", make_handler([](const Value& args) {
        return c2v(analytic_continuation_zeta(parse_complex(args["s"])));
    }));
    register_function("functional_equation_zeta", make_handler([](const Value& args) {
        const FunctionalEquationResult r = functional_equation_zeta(parse_complex(args["s"]));
        Value obj = Value::make_object();
        obj.set("lhs", c2v(r.lhs));
        obj.set("rhs", c2v(r.rhs));
        obj.set("error", Value(r.error));
        obj.set("verified", Value(r.verified));
        return obj;
    }));
    register_function("nontrivial_zeros", make_handler([](const Value& args) {
        const auto zeros = nontrivial_zeros(get_int_opt(args, "limit", 10));
        Value arr = Value::make_array();
        for (const auto& z : zeros) {
            Value pt = Value::make_array();
            pt.push_back(Value(z.first));
            pt.push_back(Value(z.second));
            arr.push_back(pt);
        }
        return arr;
    }));

    // ── residue ─────────────────────────────────────────────────────────────
    register_function("residue", make_handler([](const Value& args) {
        return c2v(residue(get_string(args, "func"), parse_complex(args["z0"])));
    }));

    register_function("residue_theorem", make_handler([](const Value& args) {
        const Value& sing = args["singularities"];
        std::vector<std::complex<double>> ss;
        for (std::size_t i = 0; i < sing.size(); ++i)
            ss.push_back(parse_complex(sing.at(i)));
        return c2v(residue_theorem(get_string(args, "func"), ss));
    }));

    register_function("real_integral", make_handler([](const Value& args) {
        const double a = get_double_opt(args, "a",
                                        -std::numeric_limits<double>::infinity());
        const double b = get_double_opt(args, "b",
                                        std::numeric_limits<double>::infinity());
        return Value(real_integral(get_string(args, "func"), a, b));
    }));

    register_function("argument_principle", make_handler([](const Value& args) {
        std::complex<double> center;
        double radius;
        parse_circle(get_string(args, "contour"), center, radius);
        return Value(argument_principle(get_string(args, "func"), center, radius));
    }));

    register_function("rouche_theorem", make_handler([](const Value& args) {
        std::complex<double> center;
        double radius;
        parse_circle(get_string(args, "contour"), center, radius);
        const RoucheResult r =
            rouche_theorem(get_string(args, "f"), get_string(args, "g"), center, radius);
        Value obj = Value::make_object();
        obj.set("condition_holds", Value(r.condition_holds));
        obj.set("max_ratio", Value(r.max_ratio));
        obj.set("zeros_f", Value(r.zeros_f));
        obj.set("zeros_fg", Value(r.zeros_fg));
        return obj;
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_complex_analysis_registrar;

}  // namespace
