// test_numerical.cpp — numerical 包(积分/ODE/插值/误差/优化)内核 + JSON 测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <string>
#include <vector>

#include "api.h"
#include "json.hpp"
#include "parser_lib.h"
#include "numerical/error_stability.h"
#include "numerical/interpolation.h"
#include "numerical/matrix_numerical.h"
#include "numerical/numerical_integration.h"
#include "numerical/ode_solver.h"
#include "numerical/optimization.h"

namespace num = mf::numerical;

static int g_checks = 0;
static int g_failures = 0;

#define CHECK(cond, msg)                                     \
    do {                                                     \
        ++g_checks;                                          \
        if (!(cond)) {                                       \
            ++g_failures;                                    \
            std::printf("[FAIL] %s\n", msg);                 \
        }                                                    \
    } while (0)

#define CHECK_EQ(a, b, msg) CHECK((a) == (b), msg)

static bool near(double a, double b, double tol) { return std::abs(a - b) <= tol; }

// 多项式求值(系数高次到低次)
static double polyval(const std::vector<double>& c, double x) {
    double s = 0.0;
    for (std::size_t k = 0; k < c.size(); ++k)
        s += c[k] * std::pow(x, static_cast<double>(c.size() - 1 - k));
    return s;
}

// ── 内核层:数值积分 ─────────────────────────────────────────────────────────

static void test_integration() {
    const double kPi = 3.14159265358979323846;
    CHECK(near(num::trapezoidal_rule("sin(x)", 0, kPi, 100), 2.0, 0.001),
          "梯形积分 sin(x) ≈ 2");
    CHECK(near(num::simpson_rule("sin(x)", 0, kPi, 100), 2.0, 0.0001),
          "辛普森积分 sin(x) ≈ 2");
    CHECK(near(num::gauss_quadrature("x**2", 0, 1, 3), 1.0 / 3.0, 0.0001),
          "高斯求积 x² 0→1 = 1/3");
    CHECK(near(num::numerical_derivative("x**3", 2.0, 1e-6, "central"), 12.0, 0.001),
          "中心差分 (x³)'@2 = 12");
    CHECK(num::optimal_step("x**2", 1.0, "central") > 0, "最优步长 > 0");
}

// ── 内核层:ODE ──────────────────────────────────────────────────────────────

static void test_ode() {
    const double e = std::exp(1.0);
    CHECK(near(num::euler_method("y", 0, 1, 1, 0.1).y.back(), e, 0.5),
          "欧拉法 y'=y, y(1) ≈ e");
    CHECK(near(num::rk4("y", 0, 1, 1, 0.1).y.back(), e, 0.001),
          "RK4 y'=y, y(1) ≈ e");
    CHECK(near(num::implicit_euler("y", 0, 1, 1, 0.1).y.back(), e, 0.5),
          "隐式欧拉 y'=y, y(1) ≈ e");
    CHECK(!num::stiff_detector("y", 0, 1, 1), "y'=y 非刚性");

    // 相图:系统 dx/dt=-y, dy/dt=x 应产生闭合轨迹数据
    const num::PhasePortraitResult pp =
        num::phase_portrait("-y", "x", -2, 2, -2, 2, 3, 10);
    CHECK(pp.X.size() == 10 && pp.X[0].size() == 10, "相图网格 10×10");
    CHECK(pp.trajectories.size() == 3, "相图 3 条轨迹");
}

// ── 内核层:插值 ─────────────────────────────────────────────────────────────

static void test_interpolation() {
    const std::vector<double> lag = num::lagrange_interpolation({0, 1, 2}, {0, 1, 0});
    CHECK(near(polyval(lag, 1), 1.0, 1e-10), "拉格朗日 P(1) = 1");

    const std::vector<double> newton = num::newton_interpolation({0, 1, 2}, {0, 1, 4});
    // 牛顿形式:P(x) = c0 + c1(x-x0) + c2(x-x0)(x-x1)
    const double nx = newton[0] + newton[1] * (2 - 0) + newton[2] * (2 - 0) * (2 - 1);
    CHECK(near(nx, 4.0, 1e-10), "牛顿插值 P(2) = 4");

    const auto spline = num::cubic_spline({0, 1, 2, 3}, {0, 1, 0, 1});
    CHECK(spline.size() == 3 && spline[0].size() == 4, "三次样条 3 段 × 4 系数");
    // 段 0 在 x=1(dx=1) 处应过点 (1,1)
    const double s1 = spline[0][0] + spline[0][1] * 1.0 + spline[0][2] * 1.0 +
                      spline[0][3] * 1.0;
    CHECK(near(s1, 1.0, 1e-10), "三次样条 S(1) = 1");

    // 近线性数据的最小二乘拟合,degree=1,R² 应接近 1
    const std::vector<double> xs = {0, 1, 2, 3, 4, 5, 6, 7};
    const std::vector<double> ys = {1.1, 2.9, 5.2, 7.1, 9.3, 10.9, 12.8, 15.1};
    const num::LeastSquaresResult ls = num::least_squares_fit(xs, ys, 1);
    CHECK(ls.r_squared > 0.99, "最小二乘 R² > 0.99");
}

// ── 内核层:误差与优化 ───────────────────────────────────────────────────────

static void test_error_optimization() {
    CHECK(near(num::condition_number("1/x", 1e-3), 1.0, 0.01),
          "条件数(1/x) = 1");
    CHECK(num::condition_number("1/(x-1)", 1.001) > 100,
          "条件数(1/(x-1)) 病态 > 100");
    CHECK(num::truncation_error("exp", 1.0, 5, std::exp(1.0)) < 0.01,
          "exp 截断误差 < 0.01");
    CHECK(near(num::rounding_error_estimate(16), 1e-16, 1e-30),
          "舍入误差界 10^-16");
    CHECK(num::is_stable("x+1", 1000), "x+1 稳定");

    const num::GradientDescentResult g1 = num::gradient_descent("x**2", 3.0, 0.1);
    CHECK(std::abs(g1.x_min) < 0.01, "min(x²) x_min ≈ 0");
    const num::GradientDescentResult g2 =
        num::gradient_descent("(x-2)**2 + 1", 0.0, 0.1);
    CHECK(std::abs(g2.x_min - 2.0) < 0.01, "min((x-2)²+1) x_min ≈ 2");
}

// ── 内核层:矩阵数值(Eigen)──────────────────────────────────────────────────

static void test_matrix() {
    Eigen::MatrixXd A(2, 2);
    A << 4, 3, 6, 3;
    const auto [L, U] = num::lu_decomposition(A);
    CHECK((L * U - A).cwiseAbs().maxCoeff() < 1e-10, "LU 分解重构 A");

    Eigen::MatrixXd Aj(2, 2);
    Aj << 4, 1, 2, 5;
    Eigen::VectorXd b(2);
    b << 1, 1;
    const Eigen::VectorXd x0 = Eigen::VectorXd::Zero(2);
    int it = 0;
    const Eigen::VectorXd xj = num::jacobi_iteration(Aj, b, x0, 1e-6, 100, it);
    CHECK((xj - Eigen::Vector2d(2.0 / 9, 1.0 / 9)).norm() < 0.01, "雅可比解 ≈ (2/9, 1/9)");
    const Eigen::VectorXd xg = num::gauss_seidel(Aj, b, x0, 1e-6, 100, it);
    CHECK((xg - Eigen::Vector2d(2.0 / 9, 1.0 / 9)).norm() < 0.01, "高斯赛德尔解");

    Eigen::MatrixXd Ac(2, 2);
    Ac << 4, 0, 0, 2;
    Eigen::VectorXd bc(2);
    bc << 1, 1;
    const Eigen::VectorXd xc = num::conjugate_gradient(Ac, bc, x0, 1e-6, 100, it);
    CHECK(std::abs(xc(0) - 0.25) < 0.01 && std::abs(xc(1) - 0.5) < 0.01,
          "共轭梯度解 ≈ (0.25, 0.5)");

    Eigen::MatrixXd Ap(2, 2);
    Ap << 2, 1, 1, 2;
    const num::PowerResult pm = num::power_method(Ap, 1e-8, 1000);
    CHECK(std::abs(pm.eigenvalue - 3.0) < 0.01, "幂法 λ ≈ 3");

    Eigen::MatrixXd Aq(2, 2);
    Aq << 4, 1, 2, 3;
    const std::vector<std::complex<double>> eigs = num::qr_algorithm(Aq, 1e-8, 1000);
    CHECK(eigs.size() == 2, "QR 2 个特征值");
    const bool has5 = std::abs(eigs[0].real() - 5) < 0.1 || std::abs(eigs[1].real() - 5) < 0.1;
    CHECK(has5, "QR 含特征值 5");
}

// ── 内核层:符号微分边缘情况 ────────────────────────────────────────────────

static void test_differentiate() {
    // 表达式形式的常数指数:x^(2+0) → 不引入 log,在 x<0 也能求值
    auto d1 = mf::expr::differentiate(mf::expr::parse("x**(2+0)").get());
    CHECK(near(mf::expr::eval(d1.get(), -1.0), -2.0, 1e-9),
          "d(x^(2+0)) 在 x=-1 = -2(常量指数分支)");
    // 变量指数:x^x → x^x·(ln(x)+1)
    auto d2 = mf::expr::differentiate(mf::expr::parse("x**x").get());
    CHECK(near(mf::expr::eval(d2.get(), 2.0), 6.7725887222, 1e-6),
          "d(x^x)@2 ≈ 6.7726(一般法则)");
    // 嵌套幂:(x^x)^x → 在 x=2 求值 ≈ 76.36
    auto d3 = mf::expr::differentiate(mf::expr::parse("(x**x)**x").get());
    CHECK(near(mf::expr::eval(d3.get(), 2.0), 76.36, 0.1),
          "d((x^x)^x)@2 ≈ 76.36(嵌套幂)");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[8192];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

// 解析 math_call 输出,取 value 的浮点值
static double call_value_double(const char* name, const char* args) {
    const mf::json::Value v = mf::json::Value::parse(call(name, args));
    return v["value"].as_double();
}

static void test_dispatch() {
    CHECK(function_exists("trapezoidal_rule"), "function_exists(trapezoidal_rule)");
    CHECK(function_exists("gradient_descent"), "function_exists(gradient_descent)");

    CHECK(near(call_value_double("trapezoidal_rule",
                                 "{\"f\":\"sin(x)\",\"a\":0,\"b\":3.141592653589793,\"n\":100}"),
               2.0, 0.001),
          "math_call trapezoidal_rule ≈ 2");
    CHECK(near(call_value_double("simpson_rule",
                                 "{\"f\":\"sin(x)\",\"a\":0,\"b\":3.141592653589793,\"n\":100}"),
               2.0, 0.0001),
          "math_call simpson_rule ≈ 2");
    CHECK(near(call_value_double("gauss_quadrature", "{\"f\":\"x**2\",\"a\":0,\"b\":1,\"n\":3}"),
               1.0 / 3.0, 0.0001),
          "math_call gauss_quadrature = 1/3");
    CHECK(near(call_value_double("numerical_derivative", "{\"f\":\"x**3\",\"x\":2}"),
               12.0, 0.001),
          "math_call numerical_derivative x³ = 12");
    {
        const mf::json::Value v = mf::json::Value::parse(
            call("rk4", "{\"f\":\"y\",\"t0\":0,\"y0\":1,\"t_end\":1,\"h\":0.1}"));
        const mf::json::Value& yarr = v["value"]["y"];
        CHECK(near(yarr.at(yarr.size() - 1).as_double(), std::exp(1.0), 0.001),
              "math_call rk4 y'=y ≈ e");
    }
    CHECK(near(call_value_double("condition_number", "{\"f\":\"1/x\",\"x\":0.001}"),
               1.0, 0.01),
          "math_call condition_number(1/x) = 1");

    // 插值/优化/结构结果
    const std::string lag = call("lagrange_interpolation", "{\"x\":[0,1,2],\"y\":[0,1,0]}");
    CHECK(lag.find("\"isError\":false") != std::string::npos, "math_call lagrange");
    const std::string gd = call("gradient_descent", "{\"f\":\"x**2\",\"x0\":3,\"learning_rate\":0.1}");
    CHECK(gd.find("\"isError\":false") != std::string::npos &&
              gd.find("\"x_min\"") != std::string::npos,
          "math_call gradient_descent x²");

    // 错误路径
    const std::string bad = call("gauss_quadrature", "{\"f\":\"x\",\"a\":0,\"b\":1,\"n\":5}");
    CHECK(bad.find("\"isError\":true") != std::string::npos, "gauss n=5 → isError");

    // 矩阵数值
    {
        const mf::json::Value v = mf::json::Value::parse(
            call("power_method", "{\"A\":[[2,1],[1,2]]}"));
        CHECK(near(v["value"]["eigenvalue"].as_double(), 3.0, 0.01),
              "math_call power_method λ ≈ 3");
    }
    const std::string qr = call("qr_algorithm", "{\"A\":[[4,1],[2,3]]}");
    CHECK(qr.find("\"isError\":false") != std::string::npos, "math_call qr_algorithm");
    const std::string lu = call("lu_decomposition", "{\"A\":[[4,3],[6,3]]}");
    CHECK(lu.find("\"isError\":false") != std::string::npos &&
              lu.find("\"L\"") != std::string::npos,
          "math_call lu_decomposition");
}

int main() {
    std::system("chcp 65001 > nul");
    std::printf("===== numerical 内核测试 =====\n");
    test_integration();
    test_ode();
    test_interpolation();
    test_error_optimization();
    test_matrix();
    test_differentiate();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
