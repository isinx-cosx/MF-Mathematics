#include "ode_solver.h"

#include <algorithm>
#include <cmath>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include "expr_util.h"

namespace mf::numerical {

namespace {

// Python: n_steps = max(1, ceil((t_end - t0) / h));h_actual = (t_end - t0) / n_steps。
long long step_count(double t0, double t_end, double h) {
    const double raw = (t_end - t0) / h;
    return std::max<long long>(1, static_cast<long long>(std::ceil(raw)));
}

}  // namespace

ODEResult euler_method(const std::string& f, double t0, double y0, double t_end,
                       double h) {
    if (h <= 0) throw std::invalid_argument("步长 h 必须为正数");
    const auto ff = make_binary(f);
    const long long n = step_count(t0, t_end, h);
    const double h_actual = (t_end - t0) / n;
    ODEResult res;
    res.t.reserve(static_cast<std::size_t>(n) + 1);
    res.y.reserve(static_cast<std::size_t>(n) + 1);
    res.t.push_back(t0);
    res.y.push_back(y0);
    for (long long i = 0; i < n; ++i) {
        const double tn = res.t[static_cast<std::size_t>(i)];
        const double yn = res.y[static_cast<std::size_t>(i)];
        res.t.push_back(t0 + (i + 1) * h_actual);
        res.y.push_back(yn + h_actual * ff(tn, yn));
    }
    return res;
}

ODEResult rk4(const std::string& f, double t0, double y0, double t_end,
              double h) {
    if (h <= 0) throw std::invalid_argument("步长 h 必须为正数");
    const auto ff = make_binary(f);
    const long long n = step_count(t0, t_end, h);
    const double h_actual = (t_end - t0) / n;
    ODEResult res;
    res.t.reserve(static_cast<std::size_t>(n) + 1);
    res.y.reserve(static_cast<std::size_t>(n) + 1);
    res.t.push_back(t0);
    res.y.push_back(y0);
    for (long long i = 0; i < n; ++i) {
        const double tn = res.t[static_cast<std::size_t>(i)];
        const double yn = res.y[static_cast<std::size_t>(i)];
        const double k1 = ff(tn, yn);
        const double k2 = ff(tn + h_actual / 2, yn + h_actual * k1 / 2);
        const double k3 = ff(tn + h_actual / 2, yn + h_actual * k2 / 2);
        const double k4 = ff(tn + h_actual, yn + h_actual * k3);
        res.t.push_back(t0 + (i + 1) * h_actual);
        res.y.push_back(yn + (h_actual / 6) * (k1 + 2 * k2 + 2 * k3 + k4));
    }
    return res;
}

ODEResult implicit_euler(const std::string& f, double t0, double y0,
                         double t_end, double h) {
    if (h <= 0) throw std::invalid_argument("步长 h 必须为正数");
    const auto ff = make_binary(f);
    const long long n = step_count(t0, t_end, h);
    const double h_actual = (t_end - t0) / n;
    ODEResult res;
    res.t.reserve(static_cast<std::size_t>(n) + 1);
    res.y.reserve(static_cast<std::size_t>(n) + 1);
    res.t.push_back(t0);
    res.y.push_back(y0);
    const double eps = 1e-8;
    for (long long i = 0; i < n; ++i) {
        const double tn1 = t0 + (i + 1) * h_actual;
        const double yn = res.y[static_cast<std::size_t>(i)];
        res.t.push_back(tn1);
        // 牛顿迭代解 y_next = yn + h·f(t_{n+1}, y_next)
        double y_next = yn;
        for (int it = 0; it < 20; ++it) {
            const double residual = y_next - yn - h_actual * ff(tn1, y_next);
            const double f_pert = ff(tn1, y_next + eps);
            const double jac = 1.0 - h_actual * (f_pert - ff(tn1, y_next)) / eps;
            if (std::abs(jac) < 1e-15) break;
            const double delta = residual / jac;
            if (std::abs(delta) > std::max(1.0, 10 * std::abs(y_next))) break;
            y_next = y_next - delta;
            if (std::abs(delta) < 1e-12) break;
        }
        res.y.push_back(y_next);
    }
    return res;
}

bool stiff_detector(const std::string& f, double t0, double y0, double t_end) {
    const double h = std::min(0.01, (t_end - t0) / 100);
    const ODEResult r_exp = euler_method(f, t0, y0, t0 + h * 5, h);
    const ODEResult r_imp = implicit_euler(f, t0, y0, t0 + h * 5, h);
    const double y_exp = r_exp.y.back();
    const double y_imp = r_imp.y.back();
    const double rel_diff =
        std::abs(y_exp - y_imp) / (std::abs(y_exp) + std::abs(y_imp) + 1e-15);
    return rel_diff > 0.1;
}

PhasePortraitResult phase_portrait(const std::string& dx_dt,
                                   const std::string& dy_dt, double x_min,
                                   double x_max, double y_min, double y_max,
                                   long long n_trajectories, long long resolution) {
    const auto f = make_xy(dx_dt);
    const auto g = make_xy(dy_dt);
    const long long res = resolution;

    // 方向场网格(X[i][j] = xs[j], Y[i][j] = ys[i],同 np.meshgrid)
    std::vector<std::vector<double>> X, Y, U, V;
    X.assign(static_cast<std::size_t>(res), std::vector<double>(static_cast<std::size_t>(res), 0.0));
    Y = X;
    U = X;
    V = X;
    for (long long i = 0; i < res; ++i) {
        const double yi = y_min + (y_max - y_min) * i / std::max<long long>(1, res - 1);
        for (long long j = 0; j < res; ++j) {
            const double xj = x_min + (x_max - x_min) * j / std::max<long long>(1, res - 1);
            X[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] = xj;
            Y[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] = yi;
            U[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] = f(xj, yi);
            V[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] = g(xj, yi);
        }
    }
    // 归一化:M = sqrt(U²+V²),M=0 处置 1
    for (long long i = 0; i < res; ++i) {
        for (long long j = 0; j < res; ++j) {
            double m = std::sqrt(U[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] *
                                 U[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] +
                                 V[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] *
                                 V[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)]);
            if (m == 0.0) m = 1.0;
            U[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] /= m;
            V[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] /= m;
        }
    }

    // 相轨迹:随机初始点(种子 42)欧拉步进
    std::mt19937 rng(42);
    std::uniform_real_distribution<double> dx(x_min, x_max), dy(y_min, y_max);
    PhasePortraitResult res_;
    res_.X = X;
    res_.Y = Y;
    res_.U = U;
    res_.V = V;
    const double dt = 0.05;
    for (long long tr = 0; tr < n_trajectories; ++tr) {
        PhasePortraitResult::Trajectory traj;
        double tx = dx(rng);
        double ty = dy(rng);
        traj.x.push_back(tx);
        traj.y.push_back(ty);
        for (int k = 0; k < 200; ++k) {
            const double step_dx = f(tx, ty);
            const double step_dy = g(tx, ty);
            const double nx = tx + step_dx * dt;
            const double ny = ty + step_dy * dt;
            if (nx < x_min || nx > x_max || ny < y_min || ny > y_max) break;
            tx = nx;
            ty = ny;
            traj.x.push_back(tx);
            traj.y.push_back(ty);
        }
        res_.trajectories.push_back(std::move(traj));
    }
    return res_;
}

}  // namespace mf::numerical
