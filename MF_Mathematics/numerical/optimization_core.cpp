// optimization_core.cpp — Python 胶水层
// 依赖：pybind11 + optimization_core.h
// 单函数模块，py::function 回调 × 少迭代次数 → 回调开销可接受

#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include <pybind11/stl.h>
#include <cmath>
#include <vector>

namespace py = pybind11;

// ── 梯度下降核心 ──────────────────────────────────────────
//   与 optimization_core.h 的纯 C++ 版本算法一致，
//   但直接使用 py::function 避免函数指针转换的开销

inline std::tuple<double, double, int, std::vector<double>>
_gradient_descent(py::function f, py::object df,
                  double x0, double lr, int max_iter, double tol)
{
    double xi = x0;
    double h_fd = 1e-6;
    int iterations = 0;
    std::vector<double> path;
    path.push_back(xi);

    bool has_df = !df.is_none();

    for (int i = 0; i < max_iter; i++) {
        double grad;
        if (has_df) {
            grad = df(xi).cast<double>();
        } else {
            grad = (f(xi + h_fd).cast<double>() - f(xi - h_fd).cast<double>())
                   / (2.0 * h_fd);
        }

        double xi_new = xi - lr * grad;

        if (std::fabs(xi_new - xi) < tol) {
            xi = xi_new;
            iterations = i + 1;
            break;
        }
        xi = xi_new;
        iterations = i + 1;

        // 只保留前 10 个轨迹点
        if ((int)path.size() < 10) {
            path.push_back(xi);
        }
    }

    double f_min = f(xi).cast<double>();
    return {xi, f_min, iterations, path};
}

// ── 模块注册 ─────────────────────────────────────────────

PYBIND11_MODULE(optimization_core, m) {
    m.doc() = "梯度下降优化 — C++ 迭代循环加速";

    m.def("gradient_descent", &_gradient_descent,
          py::arg("f"),
          py::arg("df") = py::none(),
          py::arg("x0") = 1.0,
          py::arg("learning_rate") = 0.1,
          py::arg("max_iter") = 1000,
          py::arg("tol") = 1e-6,
          "梯度下降法求函数极小值\n\n"
          "Args:\n"
          "  f: 目标函数 f(x) → float\n"
          "  df: 导函数 f'(x) → float（None 则用中心差分）\n"
          "  x0: 初始点\n"
          "  learning_rate: 学习率\n"
          "  max_iter: 最大迭代次数\n"
          "  tol: 收敛容差\n\n"
          "Returns: (x_min, f_min, iterations, path)\n"
          "  path: 前 10 个迭代点的 x 值");
}
