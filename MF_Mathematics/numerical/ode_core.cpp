#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include <cmath>
#include <string>
namespace py = pybind11;

inline double euler(py::function f, double t0, double y0, double t_end, double h){
    int n = std::max(1, static_cast<int>((t_end - t0) / h));
    double h_actual = (t_end - t0) / n;
    double t = t0;
    double y = y0;
    for (int _=0; _<n; _++) {
        y = y + h_actual * f(t, y).cast<double>();
        t = t+ h_actual;
    }
    return y;
}

inline double rk4(py::function f, double t0, double y0, double t_end, double h){
    int n = std::max(1, static_cast<int>((t_end - t0) / h));
    double h_actual = (t_end - t0)/ n;
    double t = t0;
    double y = y0;
    for (int _=0; _<n; _++){
        double k1 = f(t, y).cast<double>();
        double k2 = f(t + h_actual/2, y + h_actual * k1/2).cast<double>();
        double k3 = f(t + h_actual/2, y + h_actual * k2/2).cast<double>();
        double k4 = f(t + h_actual, y + h_actual * k3).cast<double>();
        y = y + h_actual/6 * (k1 + 2*k2 + 2*k3 + k4);
        t = t + h_actual;
    }
    return y;
}

inline double implicit_euler(py::function f, double t0, double y0, double t_end, double h){
    int n = std::max(1, static_cast<int>((t_end - t0) / h));
    double h_actual = (t_end - t0)/ n;
    double t = t0;
    double y = y0;
    for (int _=0; _<n; _++){
        double t_next = t + h_actual;
        double y_pred = y + h_actual * f(t, y).cast<double>();
        y = y + h_actual * f(t_next, y_pred).cast<double>();
        t = t_next;
    }
    return y;
}

PYBIND11_MODULE(ode_core, m) {
    m.def("euler",          &euler,          "欧拉方法");
    m.def("rk4",            &rk4,            "四阶龙格-库塔");
    m.def("implicit_euler", &implicit_euler, "隐式欧拉");
}