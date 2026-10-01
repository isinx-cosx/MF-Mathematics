// matrix_core.cpp — Python 胶水层
// 依赖：pybind11 + matrix_core.h
// 全部 5 个函数都是纯数据运算，无 py::function 回调 → 加速效果显著

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "matrix_core.h"

namespace py = pybind11;

// ── 薄封装：将 int& iterations 转为返回值的一部分 ────────────

inline std::pair<std::vector<double>, int>
_jacobi(const std::vector<std::vector<double>>& A,
        const std::vector<double>& b,
        const std::vector<double>& x0,
        double tol, int max_iter) {
    int iters;
    auto sol = jacobi_iteration(A, b, x0, tol, max_iter, iters);
    return {sol, iters};
}

inline std::pair<std::vector<double>, int>
_gs(const std::vector<std::vector<double>>& A,
    const std::vector<double>& b,
    const std::vector<double>& x0,
    double tol, int max_iter) {
    int iters;
    auto sol = gauss_seidel(A, b, x0, tol, max_iter, iters);
    return {sol, iters};
}

inline std::pair<std::vector<double>, int>
_cg(const std::vector<std::vector<double>>& A,
    const std::vector<double>& b,
    const std::vector<double>& x0,
    double tol, int max_iter) {
    int iters;
    auto sol = conjugate_gradient(A, b, x0, tol, max_iter, iters);
    return {sol, iters};
}

inline std::tuple<double, std::vector<double>, int>
_pm(const std::vector<std::vector<double>>& A,
    double tol, int max_iter) {
    int iters;
    auto [lambda, vec] = power_method(A, tol, max_iter, iters);
    return {lambda, vec, iters};
}

// ── 模块注册 ─────────────────────────────────────────────────

PYBIND11_MODULE(matrix_core, m) {
    m.doc() = "矩阵数值方法 — 纯 C++ 加速层（零回调依赖）";

    m.def("lu_decomposition", &lu_decomposition,
          "LU 分解（Doolittle）\n"
          "Args: A (list[list[float]])\n"
          "Returns: (L, U) 元组，L 为单位下三角");

    m.def("jacobi_iteration", &_jacobi,
          "雅可比迭代法求解 Ax = b\n"
          "Args: A, b, x0, tol, max_iter\n"
          "Returns: (x_solution, iterations)");

    m.def("gauss_seidel", &_gs,
          "高斯-赛德尔迭代法求解 Ax = b\n"
          "Args: A, b, x0, tol, max_iter\n"
          "Returns: (x_solution, iterations)");

    m.def("conjugate_gradient", &_cg,
          "共轭梯度法求解 Ax = b（A 对称正定）\n"
          "Args: A, b, x0, tol, max_iter\n"
          "Returns: (x_solution, iterations)");

    m.def("power_method", &_pm,
          "幂法求按模最大特征值\n"
          "Args: A, tol, max_iter\n"
          "Returns: (eigenvalue, eigenvector, iterations)");
}
