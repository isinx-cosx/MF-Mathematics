// analysis.h — 补齐最后一批"未接入引擎"的模式：
//   曲线分析（凹凸性、拐点、渐近线、曲率、曲率半径）
//   中值定理（Cauchy 中值定理）
//   微分方程（一阶 ODE、高阶常系数 ODE、线性 ODE 组）
//   偏微分方程（一阶线性 PDE、二阶 PDE 分类）
//   复分析（零点与极点）
//
// 设计原则（对应"不允许占位/静默失败"）：
//   · 能给出**确定结论**的就给结论（二阶 PDE 的分类、曲率、Cauchy 中值定理都是确定的）；
//   · 只能数值求解的（拐点、渐近线、零点/极点）就明确标注是数值结果与扫描区间；
//   · 方法不适用时返回**为什么不适用**，而不是返回一个看着像答案的东西。

#pragma once

#include <complex>
#include <string>
#include <utility>
#include <vector>


namespace mf::extras {

// ── 区间/采样约定：任何数值扫描都必须把区间一并返回，避免"结果依赖隐藏参数" ──

struct IntervalFinding {
    double x = 0.0;
    double y = 0.0;
};

// 凹凸性：在 [a,b] 上按 f'' 的符号分段，返回每段的凹凸性与依据。
struct ConcavityResult {
    std::string conclusion;                  // 中文结论
    std::vector<std::string> segments;       // 每段："(a, b) 上 f''>0，曲线凹（下凸）"
    double a = 0.0, b = 0.0;
};
ConcavityResult concavity(const std::string& expr, const std::string& var,
                                 double a, double b);

// 拐点：f'' 变号处（数值求根 + 变号确认），含函数值。
struct InflectionResult {
    std::vector<IntervalFinding> points;
    double a = 0.0, b = 0.0;
    std::string note;
};
InflectionResult inflection_points(const std::string& expr,
                                          const std::string& var, double a, double b);

// 渐近线：垂直（f→∞ 的点）、水平（x→±∞ 的极限）、斜渐近线 y=kx+b。
struct AsymptoteResult {
    std::vector<std::string> vertical;
    std::vector<std::string> horizontal;
    std::vector<std::string> oblique;
    std::string note;
};
AsymptoteResult asymptotes(const std::string& expr, const std::string& var);

// 曲率 κ = |y''| / (1 + y'^2)^{3/2}；曲率半径 R = 1/κ（κ=0 时 R=∞）。
struct CurvatureResult {
    double x = 0.0, y = 0.0;
    double dy = 0.0, d2y = 0.0;
    double curvature = 0.0;
    double radius = 0.0;         // 无穷大时 is_straight 置真
    bool is_straight = false;
};
CurvatureResult curvature(const std::string& expr, const std::string& var,
                                double x0);

// Cauchy 中值定理：在 (a,b) 内找 c 使 f'(c)(g(b)-g(a)) = g'(c)(f(b)-f(a))。
struct CauchyMvtResult {
    bool found = false;
    double c = 0.0;
    double lhs = 0.0, rhs = 0.0;    // 两侧的值（用于核对）
    std::string note;
};
CauchyMvtResult cauchy_mvt(const std::string& f, const std::string& g,
                                  const std::string& var, double a, double b);

// ── 微分方程 ──
// 一阶 ODE y' = f(x, y)：识别 直接积分 / 可分离 / 一阶线性 三类并给出通解。
struct OdeResult {
    std::string kind;        // direct / separable / linear
    std::string solution;    // 通解（含积分常数 C）
    std::string note;        // 步骤或适用范围说明
};
OdeResult ode_first_order(const std::string& f, const std::string& xvar,
                                 const std::string& yvar);

// 常系数线性齐次 ODE：a_n y^(n) + ... + a_1 y' + a_0 y = 0（n ≤ 4），
// 由特征方程根给出通解（实根/共轭复根/重根分别处理）。
struct HigherOdeResult {
    std::string characteristic;   // 特征方程
    std::vector<std::string> roots;
    std::string solution;
};
HigherOdeResult ode_constant_coefficients(const std::vector<double>& coeffs);

// 线性 ODE 组 y' = A y：由 A 的特征值/特征向量给出通解。
struct OdeSystemResult {
    std::string eigenvalues;
    std::string solution;
    std::string note;
};
OdeSystemResult ode_linear_system(const std::vector<std::vector<double>>& A);

// 二阶 PDE 分类：A u_xx + 2B u_xy + C u_yy + ... ＝ 椭圆的/抛物的/双曲线型，
// 并给出判别式与化简所用的特征变量。
struct PdeClassResult {
    std::string type;            // 椭圆型 / 抛物型 / 双曲线型
    double discriminant = 0.0;   // B² - AC
    std::string canonical;       // 特征变量（化简到标准形的变换）
    std::string note;
};
PdeClassResult classify_second_order_pde(double A, double B, double C);

// 一阶线性 PDE：a u_x + b u_y = 0（常系数）→ 特征线 bx - ay = C，通解 u = F(bx - ay)。
struct FirstOrderPdeResult {
    std::string characteristics;
    std::string solution;
    std::string note;
};
FirstOrderPdeResult first_order_linear_pde(double a, double b, double c);

// ── 复分析 ──
struct ZeroPoleResult {
    std::vector<std::pair<double, double>> zeros;
    std::vector<std::pair<double, double>> poles;
    std::string note;
};
// 在 |z - center| ≤ radius 内数值定位零点与极点：
// 零点 = |f| 的局部极小（且接近 0），极点 = 1/|f| 的局部极小（且 |f| 很大）。
ZeroPoleResult zeros_and_poles(const std::string& func,
                                      std::complex<double> center, double radius);

}  // namespace mf::extras
