#include "elementary_funcs.h"

#include <cmath>
#include <stdexcept>

namespace mf::complex_analysis {

std::complex<double> exp_complex(std::complex<double> z) {
    const double e = std::exp(z.real());
    return e * std::complex<double>(std::cos(z.imag()), std::sin(z.imag()));
}

std::complex<double> log_complex(std::complex<double> z, double branch_cut) {
    if (z == std::complex<double>(0.0, 0.0))
        throw std::invalid_argument("log(0) 无定义");
    const double r = std::abs(z);
    double theta = std::atan2(z.imag(), z.real());
    while (theta <= branch_cut) theta += 2.0 * 3.141592653589793;
    while (theta > branch_cut + 2.0 * 3.141592653589793) theta -= 2.0 * 3.141592653589793;
    return {std::log(r), theta};
}

std::complex<double> sqrt_complex(std::complex<double> z) {
    // 用标准库的主支复数开方，而不是 exp(log(z)/2)：
    //   · exp(log(z)/2) 在 z = 0 处要经过 log(0)，会直接报"log(0) 无定义"，
    //     可 0 明明是主支平方根的合法输入（√0 = 0，与 mpmath/cmath/numpy 一致）；
    //   · std::sqrt 的割线取在负实轴，正是主支约定，且精度优于 log→exp 两步。
    return std::sqrt(z);
}

std::complex<double> mobius_transform(std::complex<double> z, std::complex<double> a,
                                      std::complex<double> b, std::complex<double> c,
                                      std::complex<double> d) {
    if (std::abs(a * d - b * c) < 1e-15)
        throw std::invalid_argument("ad - bc ≈ 0，不是 Möbius 变换");
    const std::complex<double> denom = c * z + d;
    if (std::abs(denom) < 1e-15)
        throw std::invalid_argument("分母为零，映射到无穷远点");
    return (a * z + b) / denom;
}

}  // namespace mf::complex_analysis
