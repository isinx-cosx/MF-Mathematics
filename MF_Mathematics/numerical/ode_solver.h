// ode_solver.h — 常微分方程初值问题:欧拉法、RK4、隐式欧拉、刚性检测、相图。
#pragma once

#include <string>
#include <vector>

#include "../mf_export.h"

namespace mf::numerical {

// ODE 数值解轨迹。t、y 等长,对应 Python 的 {"t": [...], "y": [...]}。
struct ODEResult {
    std::vector<double> t;
    std::vector<double> y;
};

// 前向欧拉 y' = f(t, y),f 为表达式字符串(变量 t, y)。
MF_API ODEResult euler_method(const std::string& f, double t0, double y0,
                              double t_end, double h = 0.1);

// 四阶龙格-库塔。
MF_API ODEResult rk4(const std::string& f, double t0, double y0, double t_end,
                     double h = 0.1);

// 隐式欧拉(牛顿迭代解隐含方程,与 Python 一致)。
MF_API ODEResult implicit_euler(const std::string& f, double t0, double y0,
                                double t_end, double h = 0.1);

// 刚性检测:比较小步长下显式/隐式欧拉结果,相对差异 > 0.1 判定刚性。
MF_API bool stiff_detector(const std::string& f, double t0, double y0,
                           double t_end);

// 相图:2D ODE 系统 dx/dt、dy/dt 的方向场与相轨迹数据。
struct PhasePortraitResult {
    struct Trajectory {
        std::vector<double> x;
        std::vector<double> y;
    };
    std::vector<std::vector<double>> X, Y;  // 网格坐标 (resolution × resolution)
    std::vector<std::vector<double>> U, V;  // 归一化方向场
    std::vector<Trajectory> trajectories;   // 相轨迹(种子 42)
};
MF_API PhasePortraitResult phase_portrait(
    const std::string& dx_dt, const std::string& dy_dt, double x_min,
    double x_max, double y_min, double y_max, long long n_trajectories = 5,
    long long resolution = 20);

}  // namespace mf::numerical
