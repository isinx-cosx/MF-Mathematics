// interpolation_core.cpp — Python 胶水层
// 依赖：pybind11 + interpolation_core.h
// 将来换 C# 时，只需替换此文件
//
// 与 numerical_core.cpp 的关键区别：
//   本模块全部 4 个函数都是「纯数据 in → 纯数据 out」
//   （std::vector<double> → std::vector<double>），
//   不涉及 py::function 回调，因此 C++ 加速效果远优于 ODE 模块。

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "interpolation_core.h"

namespace py = pybind11;

PYBIND11_MODULE(interpolation_core, m) {
    m.doc() = "插值与逼近 — 纯 C++ 加速层";

    m.def("lagrange",      &lagrange,
          "拉格朗日插值\n\n"
          "Args: x (list[float]), y (list[float])\n"
          "Returns: 多项式系数（升幂排列 [c0, c1, ..., cn]）");

    m.def("newton",        &newton,
          "牛顿插值（差商形式）\n\n"
          "Args: x (list[float]), y (list[float])\n"
          "Returns: 差商系数表 [f[x0], f[x0,x1], f[x0,x1,x2], ...]");

    m.def("cubic_spline",  &cubic_spline,
          "三次样条插值（自然边界）\n\n"
          "Args: x (list[float]), y (list[float])\n"
          "Returns: 展开的样条系数 [a0,b0,c0,d0, a1,b1,c1,d1, ...]，"
          "共 (n-1)*4 个元素");

    m.def("least_squares", &least_squares,
          "最小二乘多项式拟合\n\n"
          "Args: x (list[float]), y (list[float]), degree (int)\n"
          "Returns: 多项式系数（升幂排列 [c0, c1, ..., cm]）");
}
