// at_api.cpp — algebraic_topology 包(homology/cohomology)JSON 分发层。
//
// 注册 6 个 action:simplicial_complex / homology_group / betti_numbers /
// euler_characteristic / cohomology_group / poincare_duality。
//
// 复形类参数用 JSON 对象 {dim: [单形...]} 表达,如:
//   {"complex": {"2": [[0,1,2],[0,1,3]], "1": [[0,1],...], "0": [[0],[1],...]}}
// 也可用已知空间名:{"space": "T2", "n": 1}

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "cohomology.h"
#include "degree_fixedpoint.h"
#include "homology.h"
#include "homotopy.h"
#include "persistent_homology.h"

#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using mf::api::make_handler;
using mf::api::to_int_array;
using mf::api::get_int;
using mf::api::get_int_opt;
using mf::api::get_double_opt;
using mf::api::get_bool_opt;
using mf::api::get_string;
using mf::api::get_int_bounded;
using mf::api::get_int_opt_bounded;
using namespace mf::algebraic_topology;

// ── 单形/复形的 JSON 解析与序列化 ─────────────────────────────────────────

Simplex parse_simplex(const Value& v) {
    if (!v.is_array()) throw std::invalid_argument("单形必须为顶点索引数组");
    Simplex s;
    for (std::size_t i = 0; i < v.size(); ++i) s.push_back(v.at(i).as_int());
    return s;
}

std::vector<Simplex> parse_simplices(const Value& v) {
    if (!v.is_array()) throw std::invalid_argument("simplices 必须为数组");
    std::vector<Simplex> out;
    for (std::size_t i = 0; i < v.size(); ++i) out.push_back(parse_simplex(v.at(i)));
    return out;
}

Complex parse_complex(const Value& v) {
    if (!v.is_object())
        throw std::invalid_argument("complex 必须为 {dim: [单形...]} 对象");
    Complex c;
    for (const std::string& key : v.keys()) {
        long long dim = 0;
        try {
            dim = std::stoll(key);
        } catch (...) {
            throw std::invalid_argument("复形维数键必须为整数: " + key);
        }
        const Value& arr = v[key];
        if (!arr.is_array()) throw std::invalid_argument("复形每维必须是单形数组");
        for (std::size_t i = 0; i < arr.size(); ++i) c[dim].push_back(parse_simplex(arr.at(i)));
    }
    return c;
}

Value complex_to_value(const Complex& c) {
    Value obj = Value::make_object();
    for (const auto& [dim, simps] : c) {
        Value arr = Value::make_array();
        for (const Simplex& s : simps) {
            Value sv = Value::make_array();
            for (long long v : s) sv.push_back(Value(v));
            arr.push_back(std::move(sv));
        }
        obj.set(std::to_string(dim), std::move(arr));
    }
    return obj;
}

Value homology_group_to_value(const HomologyGroup& hg) {
    Value obj = Value::make_object();
    obj.set("betti", Value(hg.betti));
    obj.set("torsion", to_int_array(hg.torsion));
    obj.set("group", Value(hg.group));
    return obj;
}

// 点云解析:数组的数组(多维点),或标量数组(视为 1 维点,同 Python reshape)。
std::vector<std::vector<double>> get_point_cloud(const Value& args,
                                                 const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少点云参数 ") + key);
    const Value& pc = args[key];
    std::vector<std::vector<double>> points;
    for (std::size_t i = 0; i < pc.size(); ++i) {
        const Value& p = pc.at(i);
        if (p.is_array()) {
            std::vector<double> pt;
            for (std::size_t k = 0; k < p.size(); ++k)
                pt.push_back(p.at(k).as_double());
            points.push_back(std::move(pt));
        } else {
            points.push_back({p.as_double()});
        }
    }
    return points;
}

// 支持 {"space": ...} 或 {"complex": ...} 二选一
Complex or_space(const Value& args) {
    if (args.has("complex")) return parse_complex(args["complex"]);
    throw std::invalid_argument("需要 complex 参数(复形对象)");
}

void register_all() {
    using mf::registry::register_function;

    register_function("simplicial_complex", make_handler([](const Value& args) {
        const std::vector<Simplex> simplices = parse_simplices(args["simplices"]);
        const bool maximal = get_bool_opt(args, "maximal", true);
        const SimplicialComplexResult res = build_simplicial_complex(simplices, maximal);
        Value obj = Value::make_object();
        obj.set("complex", complex_to_value(res.complex));
        obj.set("num_vertices", Value(res.num_vertices));
        obj.set("num_simplices", Value(res.num_simplices));
        obj.set("max_dimension", Value(res.max_dimension));
        return obj;
    }));

    register_function("homology_group", make_handler([](const Value& args) {
        const long long n = get_int_bounded(args, "n", -9223372036854775807, 100, "维数 n");
        if (args.has("space"))
            return homology_group_to_value(homology_group(args["space"].as_string(), n));
        return homology_group_to_value(homology_group(or_space(args), n));
    }));

    register_function("cohomology_group", make_handler([](const Value& args) {
        const long long n = get_int_bounded(args, "n", -9223372036854775807, 100, "维数 n");
        if (args.has("space"))
            return homology_group_to_value(cohomology_group(args["space"].as_string(), n));
        return homology_group_to_value(cohomology_group(or_space(args), n));
    }));

    register_function("betti_numbers", make_handler([](const Value& args) {
        const long long max_dim = get_int_opt_bounded(args, "max_dim", -1, -9223372036854775807, 20, "最大维数");
        if (args.has("space")) {
            std::vector<long long> b = betti_numbers(args["space"].as_string());
            if (max_dim >= 0 && static_cast<std::size_t>(max_dim) + 1 < b.size())
                b.resize(static_cast<std::size_t>(max_dim) + 1);
            return to_int_array(b);
        }
        return to_int_array(betti_numbers(or_space(args), max_dim));
    }));

    register_function("euler_characteristic", make_handler([](const Value& args) {
        if (args.has("space"))
            return Value(euler_characteristic(args["space"].as_string()));
        return Value(euler_characteristic(or_space(args)));
    }));

    register_function("poincare_duality", make_handler([](const Value& args) {
        const std::string manifold = get_string(args, "manifold");
        const long long k = get_int_opt(args, "k", 0);
        const PoincareDuality pd = poincare_duality(manifold, k);
        Value obj = Value::make_object();
        obj.set("manifold", Value(pd.manifold));
        obj.set("dimension", Value(pd.dimension));
        obj.set("co_betti", Value(pd.co_betti));
        obj.set("hom_betti", Value(pd.hom_betti));
        obj.set("duality_holds", Value(pd.duality_holds));
        return obj;
    }));

    // ── homotopy / degree_fixedpoint / 概念函数 ───────────────────────────
    register_function("fundamental_group", make_handler([](const Value& args) {
        return Value(fundamental_group(get_string(args, "space"),
                                       get_int_opt(args, "n", 1)));
    }));
    register_function("is_simply_connected", make_handler([](const Value& args) {
        return Value(is_simply_connected(get_string(args, "space"),
                                         get_int_opt(args, "n", 1)));
    }));
    register_function("path_homotopy", make_handler([](const Value& args) {
        const PathHomotopy ph = path_homotopy(get_string(args, "space"));
        Value obj = Value::make_object();
        obj.set("space", Value(ph.space));
        obj.set("fundamental_group", Value(ph.fundamental_group));
        return obj;
    }));
    register_function("mapping_degree", make_handler([](const Value& args) {
        const MappingDegree md = mapping_degree(get_int_bounded(args, "sphere_dim", -9223372036854775807, 1000, "球面维数"));
        Value obj = Value::make_object();
        obj.set("sphere_dim", Value(md.sphere_dim));
        obj.set("antipodal_degree", Value(md.antipodal_degree));
        obj.set("identity_degree", Value(md.identity_degree));
        return obj;
    }));
    register_function("brouwer_fixed_point_theorem",
                      make_handler([](const Value& args) {
        const BrouwerResult b =
            brouwer_fixed_point_theorem(get_string(args, "space"));
        Value obj = Value::make_object();
        obj.set("dimension", Value(b.dimension));
        obj.set("holds", Value(b.holds));
        return obj;
    }));
    register_function("hairy_ball_theorem", make_handler([](const Value& args) {
        const HairyBall hb = hairy_ball_theorem(get_int_bounded(args, "sphere_dim", -9223372036854775807, 100, "球面维数"));
        Value obj = Value::make_object();
        obj.set("sphere_dim", Value(hb.sphere_dim));
        obj.set("nonzero_vector_field_exists", Value(hb.nonzero_vector_field_exists));
        obj.set("euler_characteristic", Value(hb.euler_characteristic));
        return obj;
    }));
    register_function("boundary_operator", make_handler([](const Value& args) {
        const BoundaryOperator bo = boundary_operator(get_int_bounded(args, "dimension", -9223372036854775807, 1000, "维数"));
        Value obj = Value::make_object();
        obj.set("dimension", Value(bo.dimension));
        obj.set("formula", Value(bo.formula));
        return obj;
    }));
    register_function("cup_product", make_handler([](const Value&) {
        const CupProduct cp = cup_product();
        Value obj = Value::make_object();
        obj.set("operation", Value(cp.operation));
        obj.set("mapping", Value(cp.mapping));
        return obj;
    }));

    // ── persistent_homology ────────────────────────────────────────────────
    register_function("filtration", make_handler([](const Value& args) {
        const auto points = get_point_cloud(args, "point_cloud");
        const double ms = get_double_opt(args, "max_scale", 1.0);
        const long long md = get_int_opt_bounded(args, "max_dim", 2, -9223372036854775807, 20, "最大维数");
        const FiltrationResult fr = filtration(points, ms, md);
        Value obj = Value::make_object();
        obj.set("n_points", Value(fr.n_points));
        obj.set("ambient_dim", Value(fr.ambient_dim));
        obj.set("max_scale", Value(fr.max_scale));
        Value bd = Value::make_object();
        for (long long d = 0; d <= 1; ++d) {
            const std::vector<BirthDeathPair>& src =
                d == 0 ? fr.birth_death_0 : fr.birth_death_1;
            Value arr = Value::make_array();
            for (const BirthDeathPair& bdp : src) {
                Value pair = Value::make_array();
                pair.push_back(Value(bdp.birth));
                pair.push_back(Value(bdp.death));
                arr.push_back(std::move(pair));
            }
            bd.set(std::to_string(d), std::move(arr));
        }
        obj.set("birth_death", std::move(bd));
        return obj;
    }));

    register_function("persistence_diagram", make_handler([](const Value& args) {
        const auto points = get_point_cloud(args, "point_cloud");
        const long long dim = get_int_opt(args, "dim", 0);
        const double ms = get_double_opt(args, "max_scale", 1.0);
        const double sig = get_double_opt(args, "significance", 0.1);
        const PersistenceDiagramResult pd =
            persistence_diagram(points, dim, ms, sig);
        Value obj = Value::make_object();
        obj.set("dimension", Value(pd.dimension));
        obj.set("num_pairs", Value(pd.num_pairs));
        obj.set("significant_pairs", Value(pd.significant_pairs));
        Value pairs = Value::make_array();
        for (const PersistencePair& pr : pd.pairs) {
            Value p = Value::make_object();
            p.set("birth", Value(pr.birth));
            p.set("death", Value(pr.death));
            p.set("persistence", Value(pr.persistence));
            pairs.push_back(std::move(p));
        }
        obj.set("pairs", std::move(pairs));
        return obj;
    }));

    register_function("barcode_plot", make_handler([](const Value& args) {
        const auto points = get_point_cloud(args, "point_cloud");
        const long long dim = get_int_opt(args, "dim", 0);
        const double ms = get_double_opt(args, "max_scale", 1.0);
        const BarcodeResult br = barcode_plot(points, dim, ms);
        Value obj = Value::make_object();
        obj.set("dimension", Value(br.dimension));
        obj.set("num_bars", Value(br.num_bars));
        Value bars = Value::make_array();
        for (const Barcode& b : br.barcodes) {
            Value item = Value::make_object();
            item.set("id", Value(b.id));
            item.set("birth", Value(b.birth));
            item.set("death", Value(b.death));
            item.set("persistence", Value(b.persistence));
            item.set("bar_length", Value(b.bar_length));
            bars.push_back(std::move(item));
        }
        obj.set("barcodes", std::move(bars));
        return obj;
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_at_registrar;

}  // namespace
