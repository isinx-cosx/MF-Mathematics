// numerical_api.cpp — numerical 包 JSON 分发层(子批 1)。
//
// 注册 19 个 action:数值积分(5)+ ODE(5)+ 插值(4)+ 误差(4)+ 优化(1)。
// matrix_numerical(Eigen)的 6 个 action 稍后追加。

#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include "numerical_integration.h"
#include "ode_solver.h"
#include "interpolation.h"
#include "error_stability.h"
#include "optimization.h"
#include "matrix_numerical.h"

#include <Eigen/Dense>

#include <complex>
#include <cstdint>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using namespace mf::numerical;
using mf::api::make_handler;
using mf::api::get_int;
using mf::api::get_int_opt;
using mf::api::get_double;
using mf::api::get_double_opt;
using mf::api::get_string;
using mf::api::get_keyword;
using mf::api::get_string_opt;
using mf::api::get_double_array;
using mf::api::to_double_array;

Value ode_to_value(const ODEResult& r) {
    Value obj = Value::make_object();
    obj.set("t", to_double_array(r.t));
    obj.set("y", to_double_array(r.y));
    return obj;
}

// 二维网格 → JSON 数组的数组
Value to_matrix_value(const std::vector<std::vector<double>>& m) {
    Value arr = Value::make_array();
    for (const auto& row : m) arr.push_back(to_double_array(row));
    return arr;
}

// ── Eigen 矩阵/向量序列化与解析 ─────────────────────────────────────────────

Eigen::MatrixXd get_matrix(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw std::invalid_argument(std::string("缺少矩阵参数 ") + key);
    const Value& m = args[key];
    const long long rows = static_cast<long long>(m.size());
    // 空矩阵会让 Eigen 里的迭代器/下标直接越界（访问违规会把宿主进程一起带走），
    // 必须在入口挡掉并给出中文错误。
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

Eigen::VectorXd get_vector(const Value& args, const char* key) {
    const std::vector<double> vals = get_double_array(args, key);
    Eigen::VectorXd v(static_cast<long long>(vals.size()));
    for (std::size_t i = 0; i < vals.size(); ++i) v(i) = vals[i];
    return v;
}

// 迭代解法/特征值解法对维数的要求：A 方阵，b、x0 与 A 行数一致。
// 少了这道检查，维数不匹配会让 Eigen 越界访问，直接把宿主进程搞崩
// （实测 exit=0xC0000005：界面上连错误提示都出不来）。宁可这里先说清楚。
void require_square(const Eigen::MatrixXd& A) {
    if (A.rows() != A.cols())
        throw std::invalid_argument("矩阵必须为方阵（当前 " + std::to_string(A.rows()) +
                                    "×" + std::to_string(A.cols()) + "）");
}

void require_linear_system(const Eigen::MatrixXd& A, const Eigen::VectorXd& b,
                           const Eigen::VectorXd& x0) {
    require_square(A);
    if (b.size() != A.rows())
        throw std::invalid_argument("b 的长度必须等于 A 的行数（A 有 " +
                                    std::to_string(A.rows()) + " 行，b 有 " +
                                    std::to_string(b.size()) + " 个元素）");
    if (x0.size() != A.rows())
        throw std::invalid_argument("x0 的长度必须等于 A 的行数（A 有 " +
                                    std::to_string(A.rows()) + " 行，x0 有 " +
                                    std::to_string(x0.size()) + " 个元素）");
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

Value vector_to_value(const Eigen::VectorXd& v) {
    Value arr = Value::make_array();
    for (long long i = 0; i < v.size(); ++i) arr.push_back(Value(v(i)));
    return arr;
}

Value complex_array_to_value(const std::vector<std::complex<double>>& eigs) {
    Value arr = Value::make_array();
    for (const auto& e : eigs) {
        Value c = Value::make_array();
        c.push_back(Value(e.real()));
        c.push_back(Value(e.imag()));
        arr.push_back(std::move(c));
    }
    return arr;
}

void register_all() {
    using mf::registry::register_function;

    // ── 数值积分 ───────────────────────────────────────────────────────────
    register_function("trapezoidal_rule", make_handler([](const Value& args) {
        return Value(trapezoidal_rule(get_string(args, "f"), get_double(args, "a"),
                                      get_double(args, "b"), get_int_opt(args, "n", 100)));
    }));
    register_function("simpson_rule", make_handler([](const Value& args) {
        return Value(simpson_rule(get_string(args, "f"), get_double(args, "a"),
                                  get_double(args, "b"), get_int_opt(args, "n", 100)));
    }));
    register_function("gauss_quadrature", make_handler([](const Value& args) {
        return Value(gauss_quadrature(get_string(args, "f"), get_double(args, "a"),
                                      get_double(args, "b"), get_int_opt(args, "n", 3)));
    }));
    register_function("numerical_derivative", make_handler([](const Value& args) {
        return Value(numerical_derivative(get_string(args, "f"), get_double(args, "x"),
                                          get_double_opt(args, "h", 1e-6),
                                          get_string_opt(args, "method", "central")));
    }));
    register_function("optimal_step", make_handler([](const Value& args) {
        return Value(optimal_step(get_string(args, "f"), get_double(args, "x"),
                                  get_string_opt(args, "method", "central")));
    }));

    // ── ODE ────────────────────────────────────────────────────────────────
    register_function("euler_method", make_handler([](const Value& args) {
        return ode_to_value(euler_method(get_string(args, "f"), get_double(args, "t0"),
                                         get_double(args, "y0"), get_double(args, "t_end"),
                                         get_double_opt(args, "h", 0.1)));
    }));
    register_function("rk4", make_handler([](const Value& args) {
        return ode_to_value(rk4(get_string(args, "f"), get_double(args, "t0"),
                                get_double(args, "y0"), get_double(args, "t_end"),
                                get_double_opt(args, "h", 0.1)));
    }));
    register_function("implicit_euler", make_handler([](const Value& args) {
        return ode_to_value(implicit_euler(get_string(args, "f"), get_double(args, "t0"),
                                           get_double(args, "y0"), get_double(args, "t_end"),
                                           get_double_opt(args, "h", 0.1)));
    }));
    register_function("stiff_detector", make_handler([](const Value& args) {
        return Value(stiff_detector(get_string(args, "f"), get_double(args, "t0"),
                                    get_double(args, "y0"), get_double(args, "t_end")));
    }));
    register_function("phase_portrait", make_handler([](const Value& args) {
        const std::vector<double> xr = get_double_array(args, "x_range");
        const std::vector<double> yr = get_double_array(args, "y_range");
        if (xr.size() != 2 || yr.size() != 2)
            throw std::invalid_argument("x_range/y_range 须为 [min, max]");
        const PhasePortraitResult r = phase_portrait(
            get_string(args, "dx_dt"), get_string(args, "dy_dt"), xr[0], xr[1],
            yr[0], yr[1], get_int_opt(args, "n_trajectories", 5),
            get_int_opt(args, "resolution", 20));
        Value obj = Value::make_object();
        Value field = Value::make_object();
        field.set("X", to_matrix_value(r.X));
        field.set("Y", to_matrix_value(r.Y));
        field.set("U", to_matrix_value(r.U));
        field.set("V", to_matrix_value(r.V));
        obj.set("field", std::move(field));
        Value trajs = Value::make_array();
        for (const auto& tr : r.trajectories) {
            Value item = Value::make_object();
            item.set("x", to_double_array(tr.x));
            item.set("y", to_double_array(tr.y));
            trajs.push_back(std::move(item));
        }
        obj.set("trajectories", std::move(trajs));
        return obj;
    }));

    // ── 插值 ───────────────────────────────────────────────────────────────
    register_function("lagrange_interpolation", make_handler([](const Value& args) {
        return to_double_array(lagrange_interpolation(get_double_array(args, "x"),
                                                      get_double_array(args, "y")));
    }));
    register_function("newton_interpolation", make_handler([](const Value& args) {
        return to_double_array(newton_interpolation(get_double_array(args, "x"),
                                                    get_double_array(args, "y")));
    }));
    register_function("cubic_spline", make_handler([](const Value& args) {
        const auto segs = cubic_spline(get_double_array(args, "x"),
                                       get_double_array(args, "y"));
        Value arr = Value::make_array();
        for (const auto& s : segs) {
            Value row = Value::make_array();
            for (double v : s) row.push_back(Value(v));
            arr.push_back(std::move(row));
        }
        return arr;
    }));
    register_function("least_squares_fit", make_handler([](const Value& args) {
        const LeastSquaresResult r = least_squares_fit(
            get_double_array(args, "x"), get_double_array(args, "y"),
            get_int_opt(args, "degree", 2));
        Value obj = Value::make_object();
        obj.set("coeffs", to_double_array(r.coeffs));
        obj.set("r_squared", Value(r.r_squared));
        return obj;
    }));

    // ── 误差与稳定性 ───────────────────────────────────────────────────────
    register_function("condition_number", make_handler([](const Value& args) {
        return Value(condition_number(get_string(args, "f"), get_double(args, "x"),
                                      get_double_opt(args, "eps", 1e-8)));
    }));
    register_function("truncation_error", make_handler([](const Value& args) {
        // series 是**关键词**（exp/sin/cos/ln/geometric），不是表达式。
        // 用 get_string 会走隐式乘法归一化，把 "geometric" 变成 "g*e*o*m*e*t*r*i*c"，
        // 于是 error_stability.cpp 里的 geometric 分支永远不可达 ——
        // 用户看到的是「未知级数: g*e*o*m*e*t*r*i*c」，而头文件声明支持 geometric。
        return Value(truncation_error(get_keyword(args, "series"), get_double(args, "x"),
                                      get_int(args, "n"),
                                      get_double_opt(args, "true_value", 0.0)));
    }));
    register_function("rounding_error_estimate", make_handler([](const Value& args) {
        return Value(rounding_error_estimate(get_int_opt(args, "precision", 16)));
    }));
    register_function("is_stable", make_handler([](const Value& args) {
        return Value(is_stable(get_string(args, "f"), get_double(args, "x")));
    }));

    // ── 优化 ───────────────────────────────────────────────────────────────
    register_function("gradient_descent", make_handler([](const Value& args) {
        const GradientDescentResult r = gradient_descent(
            get_string(args, "f"), get_double_opt(args, "x0", 1.0),
            get_double_opt(args, "learning_rate", 0.1),
            get_int_opt(args, "max_iter", 1000), get_double_opt(args, "tol", 1e-6));
        Value obj = Value::make_object();
        obj.set("x_min", Value(r.x_min));
        obj.set("f_min", Value(r.f_min));
        obj.set("iterations", Value(r.iterations));
        obj.set("path", to_double_array(r.path));
        return obj;
    }));

    // ── matrix_numerical(Eigen)────────────────────────────────────────────
    register_function("lu_decomposition", make_handler([](const Value& args) {
        const auto [L, U] = lu_decomposition(get_matrix(args, "A"));
        Value obj = Value::make_object();
        obj.set("L", matrix_to_value(L));
        obj.set("U", matrix_to_value(U));
        return obj;
    }));
    register_function("jacobi_iteration", make_handler([](const Value& args) {
        const Eigen::MatrixXd A = get_matrix(args, "A");
        const Eigen::VectorXd b = get_vector(args, "b");
        const Eigen::VectorXd x0 = get_vector(args, "x0");
        require_linear_system(A, b, x0);
        int it = 0;
        return vector_to_value(jacobi_iteration(
            A, b, x0, get_double_opt(args, "tol", 1e-6),
            static_cast<int>(get_int_opt(args, "max_iter", 1000)), it));
    }));
    register_function("gauss_seidel", make_handler([](const Value& args) {
        const Eigen::MatrixXd A = get_matrix(args, "A");
        const Eigen::VectorXd b = get_vector(args, "b");
        const Eigen::VectorXd x0 = get_vector(args, "x0");
        require_linear_system(A, b, x0);
        int it = 0;
        return vector_to_value(gauss_seidel(
            A, b, x0, get_double_opt(args, "tol", 1e-6),
            static_cast<int>(get_int_opt(args, "max_iter", 1000)), it));
    }));
    register_function("conjugate_gradient", make_handler([](const Value& args) {
        const Eigen::MatrixXd A = get_matrix(args, "A");
        const Eigen::VectorXd b = get_vector(args, "b");
        const Eigen::VectorXd x0 = get_vector(args, "x0");
        require_linear_system(A, b, x0);
        int it = 0;
        return vector_to_value(conjugate_gradient(
            A, b, x0, get_double_opt(args, "tol", 1e-6),
            static_cast<int>(get_int_opt(args, "max_iter", 1000)), it));
    }));
    register_function("power_method", make_handler([](const Value& args) {
        const Eigen::MatrixXd A = get_matrix(args, "A");
        require_square(A);          // 幂法/Eigen 越界同样会崩宿主
        const PowerResult r = power_method(
            A, get_double_opt(args, "tol", 1e-8),
            static_cast<int>(get_int_opt(args, "max_iter", 1000)));
        Value obj = Value::make_object();
        obj.set("eigenvalue", Value(r.eigenvalue));
        obj.set("eigenvector", vector_to_value(r.eigenvector));
        obj.set("iterations", Value(r.iterations));
        return obj;
    }));
    register_function("qr_algorithm", make_handler([](const Value& args) {
        const Eigen::MatrixXd A = get_matrix(args, "A");
        require_square(A);
        return complex_array_to_value(qr_algorithm(
            A, get_double_opt(args, "tol", 1e-8),
            static_cast<int>(get_int_opt(args, "max_iter", 1000))));
    }));
}

struct Registrar {
    Registrar() { register_all(); }
};
const Registrar g_numerical_registrar;

}  // namespace
