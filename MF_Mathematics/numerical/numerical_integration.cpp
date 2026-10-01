#include "numerical_integration.h"

#include <algorithm>
#include <functional>
#include <stdexcept>
#include <string>

#include "expr_util.h"
#include "numerical_core.h"

namespace mf::numerical {

namespace {
// 现有 numerical_core.h 的算法接收裸函数指针 `double (*f)(double)`;
// 用 thread_local 包装表达式求值器,供内核复用核心算法(单线程分发安全)。
thread_local std::function<double(double)> g_unary;
double unary_adapter(double x) { return g_unary(x); }
}  // namespace

double trapezoidal_rule(const std::string& f, double a, double b, long long n) {
    if (n <= 0) throw std::invalid_argument("子区间数 n 必须为正数");
    g_unary = make_unary(f);
    return trapezoidal(unary_adapter, a, b, static_cast<int>(n));
}

double simpson_rule(const std::string& f, double a, double b, long long n) {
    if (n <= 0) throw std::invalid_argument("子区间数 n 必须为正数");
    bool flip = false;
    if (a > b) {
        flip = true;
        std::swap(a, b);
    }
    long long n_adj = n % 2 == 0 ? n : n + 1;
    g_unary = make_unary(f);
    double r = simpson(unary_adapter, a, b, static_cast<int>(n_adj));
    return flip ? -r : r;
}

double gauss_quadrature(const std::string& f, double a, double b, long long n) {
    if (n != 2 && n != 3 && n != 4)
        throw std::invalid_argument("高斯求积目前仅支持 n=2,3,4");
    g_unary = make_unary(f);
    return gauss_quad(unary_adapter, a, b, static_cast<int>(n));
}

double numerical_derivative(const std::string& f, double x, double h,
                            const std::string& method) {
    if (h == 0.0) throw std::invalid_argument("步长 h 必须非零");
    if (method != "forward" && method != "backward" && method != "central")
        throw std::invalid_argument("未知方法: " + method + ",可选 forward/backward/central");
    g_unary = make_unary(f);
    return derivative(unary_adapter, x, h, method);
}

double optimal_step(const std::string& f, double x, const std::string& method) {
    // 未知 method 必须报错,不能静默套用某一支差分公式(与 numerical_derivative 一致)。
    if (method != "forward" && method != "backward" && method != "central")
        throw std::invalid_argument("未知方法: " + method +
                                    ",可选 forward/backward/central");
    g_unary = make_unary(f);
    return ::optimal_step(unary_adapter, x, method);
}

}  // namespace mf::numerical
