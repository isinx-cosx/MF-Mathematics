#include "time_series.h"

#include <cmath>
#include <stdexcept>

#include "prob_internal.h"

namespace mf::probability {

MovingAverageResult moving_average(const std::vector<double>& data,
                                   long long window) {
    if (window <= 0) throw std::invalid_argument("窗口必须为正");
    if ((long long)data.size() < window)
        throw std::invalid_argument("数据长度必须 ≥ 窗口");
    MovingAverageResult r;
    r.window = window;
    r.n = (long long)data.size();
    for (long long i = 0; i + window <= (long long)data.size(); ++i) {
        double s = 0.0;
        for (long long k = 0; k < window; ++k) s += data[i + k];
        r.smoothed.push_back(s / (double)window);
    }
    return r;
}

ExpSmoothingResult exp_smoothing(const std::vector<double>& data, double alpha) {
    if (!(alpha > 0 && alpha < 1)) throw std::invalid_argument("alpha 必须在 (0,1) 之间");
    if (data.empty()) throw std::invalid_argument("序列为空");
    ExpSmoothingResult r;
    r.alpha = alpha;
    double s = data[0];
    r.smoothed.push_back(s);
    for (std::size_t i = 1; i < data.size(); ++i) {
        s = alpha * data[i] + (1 - alpha) * s;
        r.smoothed.push_back(s);
    }
    r.forecast = s;
    return r;
}

LinearTrendResult linear_trend(const std::vector<double>& data,
                               long long forecast_steps) {
    if (data.size() < 2) throw std::invalid_argument("至少需要 2 个数据点");
    if (forecast_steps < 0) throw std::invalid_argument("预测步数不能为负");
    LinearTrendResult r;
    const long long n = (long long)data.size();
    // 最小二乘:t = 0..n-1。
    const double tm = (double)(n - 1) / 2.0;
    const double ym = detail::mean(data);
    double stt = 0.0, sty = 0.0;
    for (long long i = 0; i < n; ++i) {
        const double dt = (double)i - tm;
        stt += dt * dt;
        sty += dt * (data[i] - ym);
    }
    r.slope = stt > 1e-15 ? sty / stt : 0.0;
    r.intercept = ym - r.slope * tm;
    double ss_res = 0.0, ss_tot = 0.0;
    for (long long i = 0; i < n; ++i) {
        const double fit = r.intercept + r.slope * (double)i;
        r.trend.push_back(fit);
        const double dr = data[i] - fit;
        const double dt = data[i] - ym;
        ss_res += dr * dr;
        ss_tot += dt * dt;
    }
    r.r_squared = ss_tot > 1e-15 ? 1.0 - ss_res / ss_tot : 1.0;
    // 拟合用的是 t = 0..n-1，所以下一个时刻是 t = n，第 k 步是 t = n-1+k。
    // 旧写法 (n + k) 整体多外推一步：data=[1,3,5,7,9]（slope=2、trend 末点 9）
    // 下一步必然是 11，却给 13。注意 Python 原库 time_series.py:112 有同一行，
    // 属于被一并移植过来的原始缺陷 —— 这里按数学修正，不跟着原版错。
    for (long long k = 1; k <= forecast_steps; ++k)
        r.forecasts.push_back(r.intercept + r.slope * (double)(n - 1 + k));
    return r;
}

}  // namespace mf::probability
