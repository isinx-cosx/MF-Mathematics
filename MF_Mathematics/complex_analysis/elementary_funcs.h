// elementary_funcs.h — 初等复函数:e^z、Log z、√z、Möbius 变换。
#pragma once

#include <complex>
#include <string>

#include "../mf_export.h"

namespace mf::complex_analysis {

// 复指数 e^z。
MF_API std::complex<double> exp_complex(std::complex<double> z);

// 复对数主值 Log z = ln|z| + i·Arg(z)(默认分支 (-π, π])。
MF_API std::complex<double> log_complex(std::complex<double> z,
                                        double branch_cut = -3.141592653589793);

// 复平方根主值 √z = exp(Log z / 2)。
MF_API std::complex<double> sqrt_complex(std::complex<double> z);

// Möbius 变换 f(z) = (a·z + b)/(c·z + d)。返回无穷或抛异常。
MF_API std::complex<double> mobius_transform(std::complex<double> z,
                                             std::complex<double> a,
                                             std::complex<double> b,
                                             std::complex<double> c,
                                             std::complex<double> d);

}  // namespace mf::complex_analysis
