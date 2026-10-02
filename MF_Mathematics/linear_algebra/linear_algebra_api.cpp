// linear_algebra_api.cpp — linear_algebra 包 JSON 分发层。
//
// 注册 32 个 action(vector_spaces + linear_transforms + inner_product +
// quadratic_forms + linear_systems + eigen)。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "vector_spaces.h"
#include "linear_transforms.h"
#include "inner_product.h"
#include "quadratic_forms.h"
#include "linear_systems.h"
#include "eigen.h"

#include <cstdint>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::linear_algebra;
using mf::api::make_handler;
using mf::api::get_double_array;
using mf::api::get_string_opt;

// 矩阵参数:嵌套数组 → vector<vector<double>>。
std::vector<std::vector<double>> get_matrix(const Value& args,
                                            const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少矩阵参数 ") + key);
    const Value& arr = args[key];
    std::vector<std::vector<double>> out;
    for (std::size_t i = 0; i < arr.size(); ++i) {
        const Value& row = arr.at(i);
        if (!row.is_array())
            throw std::invalid_argument(std::string("矩阵参数 ") + key +
                                        " 必须为二维数组");
        if (row.size() == 0)
            throw std::invalid_argument(std::string("矩阵参数 ") + key +
                                        " 的第 " + std::to_string(i + 1) +
                                        " 行为空（应为 [[1,2],[3,4]] 这种二维数组）");
        std::vector<double> r;
        for (std::size_t j = 0; j < row.size(); ++j)
            r.push_back(row.at(j).as_double());
        out.push_back(std::move(r));
    }
    if (out.empty())
        throw std::invalid_argument(std::string("矩阵参数 ") + key +
                                    " 不能为空（应为 [[1,2],[3,4]] 这种二维数组）");
    // 空矩阵/参差不齐的矩阵会一路传到 Eigen 里变成访问违规（实测整个宿主进程被杀），
    // 所以在入口就挡掉：矩阵必须是"每行等长且非空"。
    for (std::size_t i = 0; i < out.size(); ++i)
        if (out[i].size() != out[0].size())
            throw std::invalid_argument(std::string("矩阵参数 ") + key +
                                        " 各行长度不一致（第 " + std::to_string(i + 1) +
                                        " 行与第 1 行不同）");
    return out;
}

/**
 * 符号类矩阵动作的规模上限。
 *
 * 特征多项式 / 特征值 / 对角化走的是**符号**路线（SymEngine 行列式 + simplify），
 * 代价随阶数迅速增长：20×20 整数矩阵实测 >10 s 不返回（界面就是卡住），
 * 而 12 阶特征多项式已经是 12 次、系数巨大，人工也用不上。
 * 数值类动作（矩阵乘法、高斯消元、数值行列式）不走这里，不受此限。
 */
std::vector<std::vector<double>> get_matrix_symbolic(const Value& args, const char* key) {
    auto m = get_matrix(args, key);
    const std::size_t rows = m.size();
    const std::size_t cols = rows ? m[0].size() : 0;
    if (rows > 12 || cols > 12)
        throw std::invalid_argument(
            std::string("矩阵过大：") + std::to_string(rows) + "×" + std::to_string(cols) +
            "。本动作是符号计算（行列式/化简），上限 12×12；阶数更高请改用数值特征值。");
    return m;
}

// 向量参数:一维数组。
std::vector<double> get_vec(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key))
        throw std::invalid_argument(std::string("缺少向量参数 ") + key);
    return get_double_array(args, key);
}

// 可选向量参数(缺省为空 → 齐次)。
bool get_vec_opt(const Value& args, const char* key, std::vector<double>& out) {
    if (args.is_object() && args.has(key) && args[key].is_array()) {
        out = get_double_array(args, key);
        return true;
    }
    return false;
}

// 向量 → 列向量列表 [[x],[y],...]。
Value vector_to_value(const Vector& v) {
    Value arr = Value::make_array();
    for (Eigen::Index i = 0; i < v.size(); ++i) {
        Value col = Value::make_array();
        col.push_back(Value(v(i)));
        arr.push_back(std::move(col));
    }
    return arr;
}

// 向量列表 → 列向量列表的列表。
Value vecs_to_value(const std::vector<Vector>& vs) {
    Value arr = Value::make_array();
    for (const auto& v : vs) arr.push_back(vector_to_value(v));
    return arr;
}

// 复数 → JSON。虚部可忽略时给普通数字，否则给 {re, im}。
//
// 为什么不能只给实部：特征值/特征向量本身就是复数域的东西，
// 丢掉虚部会把 [[0,-1],[1,0]] 的 ±i 说成 0。给 {re, im} 保持了 JSON 数值语义
// （前端已有 complex_eval 在用同样的形状），且全实矩阵的输出与以前**完全一致**，
// 不影响既有界面。
Value complex_to_value(const std::complex<double>& z) {
    if (z.imag() == 0.0) return Value(z.real());
    Value obj = Value::make_object();
    obj.set("re", Value(z.real()));
    obj.set("im", Value(z.imag()));
    return obj;
}

// 复向量 → 列向量列表。
Value complex_vector_to_value(const std::vector<std::complex<double>>& v) {
    Value arr = Value::make_array();
    for (const auto& z : v) {
        Value col = Value::make_array();
        col.push_back(complex_to_value(z));
        arr.push_back(std::move(col));
    }
    return arr;
}

// 矩阵 → 嵌套列表。
Value matrix_to_value(const Matrix& M) {
    Value arr = Value::make_array();
    for (Eigen::Index i = 0; i < M.rows(); ++i) {
        Value row = Value::make_array();
        for (Eigen::Index j = 0; j < M.cols(); ++j)
            row.push_back(Value(M(i, j)));
        arr.push_back(std::move(row));
    }
    return arr;
}

void register_all() {
    using mf::registry::register_function;

    // ── vector_spaces ──────────────────────────────────────────────────────
    register_function("is_vector_space", make_handler([](const Value& args) {
        const VectorSpaceResult r = is_vector_space(get_matrix(args, "vectors"));
        Value obj = Value::make_object();
        obj.set("is_vector_space", Value(r.is_vector_space));
        obj.set("zero_vector", Value(r.zero_vector));
        obj.set("closed_under_addition", Value(r.closed_under_addition));
        obj.set("closed_under_scalar_multiplication",
                Value(r.closed_under_scalar_multiplication));
        return obj;
    }));
    register_function("linear_combination", make_handler([](const Value& args) {
        return vector_to_value(linear_combination(
            get_matrix(args, "vectors"), get_double_array(args, "coeffs")));
    }));
    register_function("is_linear_independent",
                      make_handler([](const Value& args) {
        return Value(is_linear_independent(get_matrix(args, "vectors")));
    }));
    register_function("basis", make_handler([](const Value& args) {
        const BasisResult r = basis(get_matrix(args, "vectors"));
        Value obj = Value::make_object();
        obj.set("basis", vecs_to_value(r.basis));
        obj.set("dimension", Value(r.dimension));
        return obj;
    }));
    register_function("dimension", make_handler([](const Value& args) {
        return Value(dimension(get_matrix(args, "vectors")));
    }));
    register_function("subspace_span", make_handler([](const Value& args) {
        const SpanResult r = subspace_span(get_matrix(args, "vectors"));
        Value obj = Value::make_object();
        obj.set("span_basis", vecs_to_value(r.span_basis));
        obj.set("dimension", Value(r.dimension));
        return obj;
    }));

    // ── linear_transforms ──────────────────────────────────────────────────
    register_function("linear_transform", make_handler([](const Value& args) {
        return vector_to_value(linear_transform(get_matrix(args, "matrix"),
                                                get_vec(args, "vector")));
    }));
    register_function("matrix_representation",
                      make_handler([](const Value& args) {
        const MatrixRepresentationResult r = matrix_representation(
            get_matrix(args, "transform"), get_matrix(args, "domain_basis"));
        Value obj = Value::make_object();
        obj.set("matrix", matrix_to_value(r.matrix));
        obj.set("is_standard_basis", Value(r.is_standard_basis));
        if (r.has_basis_matrix)
            obj.set("basis_matrix", matrix_to_value(r.basis_matrix));
        return obj;
    }));
    register_function("kernel", make_handler([](const Value& args) {
        const KernelResult r = kernel(get_matrix(args, "matrix"));
        Value obj = Value::make_object();
        obj.set("kernel_basis", vecs_to_value(r.kernel_basis));
        obj.set("nullity", Value(r.nullity));
        return obj;
    }));
    register_function("image", make_handler([](const Value& args) {
        const ImageResult r = image(get_matrix(args, "matrix"));
        Value obj = Value::make_object();
        obj.set("image_basis", vecs_to_value(r.image_basis));
        obj.set("rank", Value(r.rank));
        return obj;
    }));
    register_function("rank_nullity", make_handler([](const Value& args) {
        const RankNullityResult r = rank_nullity(get_matrix(args, "matrix"));
        Value obj = Value::make_object();
        obj.set("rank", Value(r.rank));
        obj.set("nullity", Value(r.nullity));
        obj.set("domain_dim", Value(r.domain_dim));
        obj.set("theorem_holds", Value(r.theorem_holds));
        return obj;
    }));

    // ── inner_product ──────────────────────────────────────────────────────
    register_function("dot", make_handler([](const Value& args) {
        return Value(dot(get_vec(args, "u"), get_vec(args, "v")));
    }));
    register_function("norm", make_handler([](const Value& args) {
        return Value(norm(get_vec(args, "vector")));
    }));
    register_function("angle", make_handler([](const Value& args) {
        const AngleResult r = angle(get_vec(args, "u"), get_vec(args, "v"));
        Value obj = Value::make_object();
        obj.set("radians", Value(r.radians));
        obj.set("degrees", Value(r.degrees));
        obj.set("cos_theta", Value(r.cos_theta));
        return obj;
    }));
    register_function("lin_is_orthogonal", make_handler([](const Value& args) {
        return Value(is_orthogonal(get_vec(args, "u"), get_vec(args, "v")));
    }));
    register_function("lin_gram_schmidt", make_handler([](const Value& args) {
        const auto basis = gram_schmidt(get_matrix(args, "vectors"));
        Value obj = Value::make_object();
        obj.set("orthonormal_basis", vecs_to_value(basis));
        obj.set("size", Value(static_cast<long long>(basis.size())));
        return obj;
    }));
    register_function("orthogonal_projection",
                      make_handler([](const Value& args) {
        return vector_to_value(orthogonal_projection(
            get_vec(args, "vector"), get_matrix(args, "basis")));
    }));

    // ── quadratic_forms ────────────────────────────────────────────────────
    register_function("quadratic_form", make_handler([](const Value& args) {
        return Value(quadratic_form(get_matrix(args, "matrix"),
                                    get_string_opt(args, "x", "")));
    }));
    register_function("standard_form", make_handler([](const Value& args) {
        const StandardFormResult r = standard_form(get_matrix(args, "matrix"));
        Value obj = Value::make_object();
        obj.set("standard_form", Value(r.standard_form));
        Value evs = Value::make_array();
        for (double e : r.eigenvalues) evs.push_back(Value(e));
        obj.set("eigenvalues", std::move(evs));
        obj.set("orthogonal_matrix", matrix_to_value(r.orthogonal_matrix));
        return obj;
    }));
    register_function("is_positive_definite",
                      make_handler([](const Value& args) {
        return Value(is_positive_definite(get_matrix(args, "matrix")));
    }));
    register_function("is_negative_definite",
                      make_handler([](const Value& args) {
        return Value(is_negative_definite(get_matrix(args, "matrix")));
    }));
    register_function("is_indefinite", make_handler([](const Value& args) {
        return Value(is_indefinite(get_matrix(args, "matrix")));
    }));

    // ── linear_systems ─────────────────────────────────────────────────────
    register_function("gaussian_elimination",
                      make_handler([](const Value& args) {
        std::vector<double> b;
        const bool has_b = get_vec_opt(args, "b", b);
        const GaussianResult r =
            gaussian_elimination(get_matrix(args, "matrix"), b, has_b);
        Value obj = Value::make_object();
        obj.set("type", Value(r.type));
        if (r.type == "unique")
            obj.set("solution", vector_to_value(r.solution));
        obj.set("rank", Value(r.rank));
        obj.set("free_vars", Value(r.free_vars));
        return obj;
    }));
    register_function("rank", make_handler([](const Value& args) {
        return Value(rank(get_matrix(args, "matrix")));
    }));
    register_function("lin_solve_linear_system",
                      make_handler([](const Value& args) {
        std::vector<double> b;
        const bool has_b = get_vec_opt(args, "b", b);
        const SolveResult r =
            solve_linear_system(get_matrix(args, "A"), b, has_b);
        Value obj = Value::make_object();
        obj.set("type", Value(r.type));
        obj.set("homogeneous", Value(r.homogeneous));
        if (r.type == "unique")
            obj.set("solution", vector_to_value(r.solution));
        if (r.type == "infinite")
            obj.set("homogeneous_basis", vecs_to_value(r.homogeneous_basis));
        return obj;
    }));
    register_function("nullspace", make_handler([](const Value& args) {
        const NullspaceResult r = nullspace(get_matrix(args, "A"));
        Value obj = Value::make_object();
        obj.set("basis", vecs_to_value(r.basis));
        obj.set("dimension", Value(r.dimension));
        return obj;
    }));
    register_function("matrix_inverse", make_handler([](const Value& args) {
        const InverseResult r = matrix_inverse(get_matrix(args, "matrix"));
        Value obj = Value::make_object();
        obj.set("det", Value(r.det));
        if (r.singular) {
            obj.set("inverse", Value());
            obj.set("singular", Value(true));
            return obj;
        }
        obj.set("condition_number", Value(r.condition_number));
        if (r.ill_conditioned) {
            obj.set("inverse", Value());
            obj.set("singular", Value(false));
            return obj;
        }
        obj.set("inverse", matrix_to_value(r.inverse));
        obj.set("singular", Value(false));
        return obj;
    }));

    // ── eigen ──────────────────────────────────────────────────────────────
    register_function("eigenvalues", make_handler([](const Value& args) {
        const EigenvaluesResult r = eigenvalues(get_matrix_symbolic(args, "matrix"));
        Value obj = Value::make_object();
        Value evs = Value::make_array();
        for (const auto& v : r.values) evs.push_back(complex_to_value(v));
        obj.set("eigenvalues", std::move(evs));
        Value wm = Value::make_array();
        for (const auto& info : r.with_multiplicity) {
            Value item = Value::make_object();
            item.set("value", complex_to_value(info.value));
            item.set("multiplicity", Value(info.multiplicity));
            wm.push_back(std::move(item));
        }
        obj.set("with_multiplicity", std::move(wm));
        // 显式标记，调用方不必逐个看是不是 {re,im}
        obj.set("hasComplex", Value(r.has_complex));
        obj.set("method", Value(r.method));
        if (!r.note.empty()) obj.set("note", Value(r.note));
        return obj;
    }));
    register_function("eigenvectors", make_handler([](const Value& args) {
        const EigenvectorsResult r = eigenvectors(get_matrix_symbolic(args, "matrix"));
        Value obj = Value::make_object();
        Value eps = Value::make_array();
        for (const auto& p : r.eigenpairs) {
            Value item = Value::make_object();
            item.set("eigenvalue", complex_to_value(p.eigenvalue));
            item.set("eigenvector", complex_vector_to_value(p.eigenvector));
            item.set("multiplicity", Value(p.multiplicity));
            eps.push_back(std::move(item));
        }
        obj.set("eigenpairs", std::move(eps));
        obj.set("hasComplex", Value(r.has_complex));
        obj.set("method", Value(r.method));
        if (!r.note.empty()) obj.set("note", Value(r.note));
        return obj;
    }));
    register_function("characteristic_polynomial",
                      make_handler([](const Value& args) {
        return Value(characteristic_polynomial(get_matrix_symbolic(args, "matrix")));
    }));
    register_function("is_diagonalizable", make_handler([](const Value& args) {
        return Value(is_diagonalizable(get_matrix_symbolic(args, "matrix")));
    }));
    register_function("diagonalize", make_handler([](const Value& args) {
        const DiagonalizeResult r = diagonalize(get_matrix_symbolic(args, "matrix"));
        Value obj = Value::make_object();
        obj.set("diagonalizable", Value(r.diagonalizable));
        if (r.diagonalizable) {
            obj.set("P", matrix_to_value(r.P));
            obj.set("D", matrix_to_value(r.D));
        } else {
            obj.set("reason", Value(r.reason));
        }
        return obj;
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_linear_algebra_registrar;

}  // namespace
