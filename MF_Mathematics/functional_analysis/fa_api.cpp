// fa_api.cpp — functional_analysis 包 JSON 分发层。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "core_theorems.h"
#include "dual_spaces.h"
#include "inner_product_spaces.h"
#include "linear_operators.h"
#include "normed_spaces.h"
#include "spectral_theory.h"

#include <complex>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::functional_analysis;
using mf::api::make_handler;
using mf::api::get_int;
using mf::api::get_int_opt;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_string;
using mf::api::get_double_array;
using mf::api::get_string_opt;
using mf::api::to_double_array;
using mf::api::get_int_bounded;
using mf::api::get_int_opt_bounded;

// ── 矩阵/复数序列化与解析 ──────────────────────────────────────────────────

Eigen::MatrixXd get_matrix(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少矩阵参数 ") + key);
    const Value& m = args[key];
    const long long rows = static_cast<long long>(m.size());
    // 空矩阵必须当场拒绝：0×0 传进 Eigen 会直接访问违规（实测 exit=0xC0000005，
    // 整个宿主进程被带走，连错误弹窗都出不来）。宁可在这里给一句中文错误。
    if (rows == 0)
        throw std::invalid_argument(std::string("矩阵参数 ") + key +
                                    " 不能为空（应为 [[1,2],[3,4]] 这种二维数组）");
    const long long cols = static_cast<long long>(m.at(0).size());
    if (cols == 0)
        throw std::invalid_argument(std::string("矩阵参数 ") + key +
                                    " 的行不能为空（应为 [[1,2],[3,4]] 这种二维数组）");
    Eigen::MatrixXd A(rows, cols);
    for (long long i = 0; i < rows; ++i) {
        if (static_cast<long long>(m.at(static_cast<std::size_t>(i)).size()) != cols)
            throw std::invalid_argument(std::string("矩阵参数 ") + key +
                                        " 各行长度不一致（第 " + std::to_string(i + 1) +
                                        " 行与其他行不同）");
        for (long long j = 0; j < cols; ++j)
            A(i, j) = m.at(static_cast<std::size_t>(i)).at(static_cast<std::size_t>(j)).as_double();
    }
    return A;
}

Value matrix_to_value(const Eigen::MatrixXd& A) {
    Value arr = Value::make_array();
    for (long long i = 0; i < A.rows(); ++i) {
        Value row = Value::make_array();
        for (long long j = 0; j < A.cols(); ++j) row.push_back(Value(A(i, j)));
        arr.push_back(std::move(row));
    }
    return arr;
}

// 复数:虚部≈0 输出实数,否则 [实部, 虚部]
Value complex_value(std::complex<double> c) {
    if (std::abs(c.imag()) < 1e-10) return Value(c.real());
    Value arr = Value::make_array();
    arr.push_back(Value(c.real()));
    arr.push_back(Value(c.imag()));
    return arr;
}
Value complex_array_to_value(const std::vector<std::complex<double>>& v) {
    Value arr = Value::make_array();
    for (const auto& c : v) arr.push_back(complex_value(c));
    return arr;
}

// 范数阶数:数字或 "inf"/"fro" 字符串
double get_p_number(const Value& args) {
    if (!args.has("p")) return 2.0;
    const Value& v = args["p"];
    if (v.is_string()) {
        const std::string s = v.as_string();
        if (s == "inf" || s == "infinity") return std::numeric_limits<double>::infinity();
        return std::stod(s);
    }
    return v.as_double();
}

std::string get_p_string(const Value& args) {
    if (!args.has("p")) return "2";
    const Value& v = args["p"];
    if (v.is_string()) return v.as_string();
    return std::to_string(v.as_int());
}

void register_all() {
    using mf::registry::register_function;

    // ── normed_spaces ──────────────────────────────────────────────────────
    register_function("lp_norm", make_handler([](const Value& args) {
        return Value(lp_norm(get_double_array(args, "vector"), get_p_number(args)));
    }));
    register_function("is_banach", make_handler([](const Value& args) {
        return Value(is_banach(get_string(args, "space"), get_int_opt(args, "dimension", -1)));
    }));
    register_function("space_completeness_check",
                      make_handler([](const Value& args) {
        std::vector<std::vector<double>> sequence;
        for (std::size_t i = 0; i < args["sequence"].size(); ++i) {
            const Value& row = args["sequence"].at(i);
            std::vector<double> r;
            for (std::size_t k = 0; k < row.size(); ++k) r.push_back(row.at(k).as_double());
            sequence.push_back(std::move(r));
        }
        const CompletenessResult r =
            space_completeness_check(sequence, get_string_opt(args, "norm", "l2"));
        Value obj = Value::make_object();
        obj.set("is_cauchy", Value(r.is_cauchy));
        obj.set("tail_max_diff", Value(r.tail_max_diff));
        obj.set("all_diffs", to_double_array(r.all_diffs));
        return obj;
    }));

    // ── dual_spaces ────────────────────────────────────────────────────────
    register_function("dual_space_basis", make_handler([](const Value& args) {
        if (args.has("space"))
            return matrix_to_value(dual_space_basis(get_string(args, "space")));
        return matrix_to_value(dual_space_basis(get_matrix(args, "basis")));
    }));
    register_function("weak_convergence", make_handler([](const Value& args) {
        std::vector<std::vector<double>> seq;
        for (std::size_t i = 0; i < args["sequence"].size(); ++i) {
            const Value& row = args["sequence"].at(i);
            std::vector<double> r;
            for (std::size_t k = 0; k < row.size(); ++k) r.push_back(row.at(k).as_double());
            seq.push_back(std::move(r));
        }
        std::vector<double> functional, limit;
        const std::vector<double>* fp = nullptr;
        const std::vector<double>* lp = nullptr;
        if (args.has("functional")) {
            functional = get_double_array(args, "functional");
            fp = &functional;
        }
        if (args.has("limit")) {
            limit = get_double_array(args, "limit");
            lp = &limit;
        }
        return Value(weak_convergence(seq, fp, lp, get_double_opt(args, "tol", 1e-3)));
    }));
    register_function("is_reflexive", make_handler([](const Value& args) {
        return Value(is_reflexive(get_string(args, "space"), get_int_opt(args, "dimension", -1)));
    }));

    // ── linear_operators ───────────────────────────────────────────────────
    register_function("operator_norm", make_handler([](const Value& args) {
        return Value(operator_norm(get_matrix(args, "A"), get_p_string(args)));
    }));
    register_function("is_bounded", make_handler([](const Value& args) {
        return Value(is_bounded(get_matrix(args, "A")));
    }));
    register_function("linear_functional_eval", make_handler([](const Value& args) {
        return Value(linear_functional_eval(get_double_array(args, "func"),
                                            get_double_array(args, "x")));
    }));
    register_function("kernel_dimension", make_handler([](const Value& args) {
        const KernelResult r = kernel_dimension(get_matrix(args, "A"),
                                                get_double_opt(args, "tol", 1e-10));
        Value obj = Value::make_object();
        obj.set("dim_ker", Value(r.dim_ker));
        Value basis = Value::make_array();
        for (const auto& b : r.kernel_basis) basis.push_back(to_double_array(b));
        obj.set("kernel_basis", std::move(basis));
        return obj;
    }));

    // ── spectral_theory ────────────────────────────────────────────────────
    register_function("spectrum_approx", make_handler([](const Value& args) {
        const SpectrumResult r = spectrum_approx(get_matrix(args, "A"));
        Value arr = Value::make_array();
        for (double x : r.real_evals) arr.push_back(Value(x));
        for (const auto& c : r.complex_evals) arr.push_back(complex_value(c));
        return arr;
    }));
    register_function("spectrum_classify", make_handler([](const Value& args) {
        const SpectrumClassifyResult r =
            spectrum_classify(get_matrix(args, "A"), get_double_opt(args, "tol", 1e-6));
        Value obj = Value::make_object();
        obj.set("point_spectrum", complex_array_to_value(r.point_spectrum));
        obj.set("is_self_adjoint", Value(r.is_self_adjoint));
        return obj;
    }));
    register_function("spectral_theorem", make_handler([](const Value& args) {
        const SpectralTheoremResult r = spectral_theorem(get_matrix(args, "A"));
        Value obj = Value::make_object();
        obj.set("eigenvalues", complex_array_to_value(r.eigenvalues));
        Value evs = Value::make_array();
        for (const auto& v : r.eigenvectors) evs.push_back(complex_array_to_value(v));
        obj.set("eigenvectors", std::move(evs));
        obj.set("is_self_adjoint", Value(r.is_self_adjoint));
        obj.set("hasComplex", Value(r.has_complex));
        obj.set("reconstruction_error", Value(r.reconstruction_error));
        if (!r.is_self_adjoint && r.has_complex)
            obj.set("note", Value("非自伴算子，特征值为复数；"
                                  "谱定理（A = QΛQᵀ，Q 正交）只对自伴算子成立，"
                                  "这里的重构误差按复特征分解 A = QΛQ⁻¹ 计算。"));
        return obj;
    }));

    // ── core_theorems ──────────────────────────────────────────────────────
    register_function("hahn_banach_extension", make_handler([](const Value& args) {
        return to_double_array(hahn_banach_extension(
            get_double_array(args, "a"), get_int(args, "subspace_dim"),
            get_int_opt(args, "ambient_dim", -1)));
    }));
    register_function("uniform_boundedness", make_handler([](const Value& args) {
        std::vector<Eigen::MatrixXd> ops;
        for (std::size_t i = 0; i < args["operators"].size(); ++i) {
            // 每个算子是一个二维数组
            Value op_args = Value::make_object();
            op_args.set("A", args["operators"].at(i));
            ops.push_back(get_matrix(op_args, "A"));
        }
        std::vector<Eigen::VectorXd> test_pts;
        const std::vector<Eigen::VectorXd>* tp = nullptr;
        if (args.has("test_points")) {
            for (std::size_t i = 0; i < args["test_points"].size(); ++i) {
                const Value& row = args["test_points"].at(i);
                Eigen::VectorXd v(row.size());
                for (std::size_t k = 0; k < row.size(); ++k) v(k) = row.at(k).as_double();
                test_pts.push_back(v);
            }
            tp = &test_pts;
        }
        const UniformBoundednessResult r = uniform_boundedness(ops, tp);
        Value obj = Value::make_object();
        obj.set("pointwise_bounded", Value(r.pointwise_bounded));
        obj.set("uniformly_bounded", Value(r.uniformly_bounded));
        obj.set("sup_operator_norm", Value(r.sup_operator_norm));
        obj.set("operator_norms", to_double_array(r.operator_norms));
        return obj;
    }));
    register_function("open_mapping", make_handler([](const Value& args) {
        return Value(open_mapping(get_matrix(args, "A")));
    }));
    register_function("closed_graph", make_handler([](const Value& args) {
        return Value(closed_graph(get_matrix(args, "A")));
    }));

    // ── inner_product_spaces ───────────────────────────────────────────────
    register_function("inner_product", make_handler([](const Value& args) {
        const std::vector<double> dom = get_double_array(args, "domain");
        if (dom.size() != 2) throw std::invalid_argument("domain 须为 [a, b]");
        return Value(inner_product(get_string(args, "f"), get_string(args, "g"),
                                   dom[0], dom[1], get_int_opt_bounded(args, "n_points", 1000, -9223372036854775807, 1000000, "采样点数")));
    }));
    register_function("funct_is_orthogonal", make_handler([](const Value& args) {
        const std::vector<double> dom = get_double_array(args, "domain");
        if (dom.size() != 2) throw std::invalid_argument("domain 须为 [a, b]");
        return Value(funct_is_orthogonal(get_string(args, "f"), get_string(args, "g"),
                                         dom[0], dom[1], get_double_opt(args, "tol", 1e-6)));
    }));
    register_function("funct_gram_schmidt", make_handler([](const Value& args) {
        std::vector<std::vector<double>> vecs;
        for (std::size_t i = 0; i < args["vectors"].size(); ++i) {
            const Value& row = args["vectors"].at(i);
            std::vector<double> v;
            for (std::size_t k = 0; k < row.size(); ++k) v.push_back(row.at(k).as_double());
            vecs.push_back(std::move(v));
        }
        const auto basis = funct_gram_schmidt(vecs);
        Value arr = Value::make_array();
        for (const auto& b : basis) arr.push_back(to_double_array(b));
        return arr;
    }));
    register_function("is_hilbert", make_handler([](const Value& args) {
        return Value(is_hilbert(get_string(args, "space"), get_int_opt(args, "dimension", -1)));
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_fa_registrar;

}  // namespace
