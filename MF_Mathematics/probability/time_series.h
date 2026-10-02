// time_series.h — 移动平均、指数平滑、线性趋势预测。
#pragma once

#include <vector>


namespace mf::probability {

// 简单移动平均(SMA):输出长度 n-window+1。
struct MovingAverageResult {
    std::vector<double> smoothed;
    long long window = 0;
    long long n = 0;
};
MovingAverageResult moving_average(const std::vector<double>& data,
                                          long long window);

// 指数平滑 s_t = α·y_t + (1-α)·s_{t-1}。
struct ExpSmoothingResult {
    std::vector<double> smoothed;
    double forecast = 0.0;
    double alpha = 0.3;
};
ExpSmoothingResult exp_smoothing(const std::vector<double>& data,
                                        double alpha);

// 线性趋势拟合与预测。
struct LinearTrendResult {
    double slope = 0.0;
    double intercept = 0.0;
    double r_squared = 0.0;
    std::vector<double> forecasts;
    std::vector<double> trend;
};
LinearTrendResult linear_trend(const std::vector<double>& data,
                                      long long forecast_steps);

}  // namespace mf::probability
