// series.h — 复级数:泰勒展开、洛朗展开、奇点分类、极点阶数。
#pragma once

#include <complex>
#include <string>


namespace mf::complex_analysis {

// 泰勒展开多项式(字符串形式,阶数 n)。
std::string taylor_series(const std::string& func,
                                 std::complex<double> z0, long long n = 6);

// 洛朗展开(极点情形):主部 + 解析部。
std::string laurent_series(const std::string& func,
                                  std::complex<double> z0, long long n = 5);

// 奇点分类:"regular"/"removable"/"pole"/"essential"。
struct SingularityResult {
    std::string classification;
    long long pole_order = 0;
};
SingularityResult singularity_classify(const std::string& func,
                                              std::complex<double> z0);

// 极点阶数(非极点返回 0)。
long long pole_order(const std::string& func, std::complex<double> z0);

}  // namespace mf::complex_analysis
