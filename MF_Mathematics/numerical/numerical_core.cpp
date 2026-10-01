// numerical_binding.cpp — Python 胶水层
// 依赖：pybind11 + numerical_core.h
// 将来换 C# 时，只需替换此文件

#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include <cmath>
#include <string>
namespace py = pybind11;

// ── 梯形法则 ─────────────────────────────────────────────
double trapezoidal(py::function f, double a, double b, int n) {
    double h = (b - a) / n;
    double s = 0.5 * (f(a).cast<double>() + f(b).cast<double>());
    for (int i = 1; i < n; i++)
        s += f(a + i * h).cast<double>();
    return s * h;
}

// ── 辛普森法则 ───────────────────────────────────────────
double simpson(py::function f, double a, double b, int n) {
    if (n % 2 != 0) n += 1;
    double h = (b - a) / n;
    double s = f(a).cast<double>() + f(b).cast<double>();
    for (int i = 1; i < n; i++) {
        double x = a + i * h;
        s += f(x).cast<double>() * (i % 2 == 0 ? 2.0 : 4.0);
    }
    return s * h / 3.0;
}

// ── 高斯求积 ─────────────────────────────────────────────
double gauss_quad(py::function f, double a, double b, int n) {
    static const double nodes[][4] = {
        {}, {},
        {-0.5773502692,  0.5773502692},
        {-0.7745966692,  0.0,           0.7745966692},
        {-0.8611363116, -0.3399810436,  0.3399810436,  0.8611363116}
    };
    static const double weights[][4] = {
        {}, {},
        {1.0, 1.0},
        {0.5555555556, 0.8888888889, 0.5555555556},
        {0.3478548451, 0.6521451549, 0.6521451549, 0.3478548451}
    };
    if (n < 2 || n > 4) return 0.0;
    double mid = (b + a) / 2.0, half = (b - a) / 2.0, s = 0.0;
    for (int i = 0; i < n; i++)
        s += weights[n][i] * f(mid + half * nodes[n][i]).cast<double>();
    return half * s;
}

// ── 数值微分 ─────────────────────────────────────────────
double derivative(py::function f, double x, double h,
                  const std::string& method) {
    if (method == "forward")
        return (f(x + h).cast<double>() - f(x).cast<double>()) / h;
    else if (method == "backward")
        return (f(x).cast<double>() - f(x - h).cast<double>()) / h;
    else
        return (f(x + h).cast<double>() - f(x - h).cast<double>()) / (2.0 * h);
}

// ── 最优步长 ─────────────────────────────────────────────
double optimal_step(py::function f, double x, const std::string& method) {
    double eps = 2.22e-16;
    double f_val = std::fabs(f(x).cast<double>()) + 1e-15;
    double h_opt = (method == "central")
        ? std::pow(eps, 1.0 / 3.0) * f_val
        : std::pow(eps, 1.0 / 2.0) * f_val;
    if (h_opt < 1e-12) h_opt = 1e-12;
    if (h_opt > 0.1)   h_opt = 0.1;
    return h_opt;
}

// ── 模块注册 ─────────────────────────────────────────────
PYBIND11_MODULE(numerical_core, m) {
    m.def("trapezoidal",  &trapezoidal,  "梯形法则");
    m.def("simpson",      &simpson,      "辛普森法则");
    m.def("gauss_quad",   &gauss_quad,   "高斯求积 (n=2,3,4)");
    m.def("derivative",   &derivative,   "数值微分");
    m.def("optimal_step", &optimal_step, "最优步长");
}
