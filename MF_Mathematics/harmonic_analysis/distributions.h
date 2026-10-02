// distributions.h — 分布:δ 函数、δ/常数的傅里叶变换、缓增分布判断。
#pragma once

#include <string>


namespace mf::harmonic_analysis {

// δ 分布作用于测试函数:<δ_x0, φ> = φ(x0)。
double delta_distribution(const std::string& phi, double x0);

// F[δ] = 1(常函数)。
std::string ft_delta();

// F[1] = 2π·δ(ξ)(分布意义)。
std::string ft_constant();

// 缓增分布判断:采样 |f| 估计多项式增长阶。
struct TemperedResult {
    bool is_tempered = false;
    double growth_order = 0.0;
};
TemperedResult tempered_distribution(const std::string& func, double x_hi);

}  // namespace mf::harmonic_analysis
