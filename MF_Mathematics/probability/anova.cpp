#include "anova.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

#include "prob_internal.h"

namespace mf::probability {

namespace {
using mf::probability::detail::mean;
}  // namespace

AnovaResult one_way_anova(const std::vector<std::vector<double>>& groups,
                          double alpha) {
    if (groups.size() < 2) throw std::invalid_argument("至少需要 2 组数据");
    for (const auto& g : groups)
        if (g.size() < 2) throw std::invalid_argument("每组至少 2 个数据点");
    AnovaResult r;
    r.alpha = alpha;
    r.df_between = (long long)groups.size() - 1;

    double grand_sum = 0.0;
    long long total_n = 0;
    std::vector<double> means;
    for (const auto& g : groups) {
        means.push_back(mean(g));
        for (double x : g) grand_sum += x;
        total_n += (long long)g.size();
    }
    r.df_within = total_n - (long long)groups.size();
    r.group_means = means;
    const double grand = grand_sum / (double)total_n;

    double ss_b = 0.0, ss_w = 0.0;
    for (std::size_t i = 0; i < groups.size(); ++i) {
        const double dm = means[i] - grand;
        ss_b += (double)groups[i].size() * dm * dm;
        for (double x : groups[i]) {
            const double dd = x - means[i];
            ss_w += dd * dd;
        }
    }
    r.ss_between = ss_b;
    r.ss_within = ss_w;
    r.ms_between = r.df_between > 0 ? ss_b / (double)r.df_between : 0.0;
    r.ms_within = r.df_within > 0 ? ss_w / (double)r.df_within : 0.0;
    if (r.ms_within < 1e-15) {
        // 组内方差为 0(全同组):F 无定义。若组间有差异 → 显著。
        r.F = r.ms_between > 1e-15
                  ? std::numeric_limits<double>::infinity()
                  : 0.0;
        r.p_value = std::isfinite(r.F) ? 1.0 : 0.0;
        r.significant = r.p_value < alpha;
        return r;
    }
    r.F = r.ms_between / r.ms_within;
    r.p_value = 1.0 - detail::f_cdf(r.F, (double)r.df_between, (double)r.df_within);
    r.significant = r.p_value < alpha;
    return r;
}

TwoWayAnovaResult two_way_anova(const std::vector<std::vector<double>>& data,
                                double alpha) {
    const std::size_t rows = data.size();
    if (rows < 2) throw std::invalid_argument("因素 A 至少需要 2 个水平");
    const std::size_t cols = data[0].size();
    for (const auto& row : data)
        if (row.size() != cols) throw std::invalid_argument("矩阵不是矩形");
    if (cols < 2) throw std::invalid_argument("因素 B 至少需要 2 个水平");

    TwoWayAnovaResult r;
    // 计算总均值与平方和。
    double grand_sum = 0.0, ss_total = 0.0;
    std::vector<double> row_means(rows, 0.0), col_means(cols, 0.0);
    for (std::size_t i = 0; i < rows; ++i)
        for (std::size_t j = 0; j < cols; ++j)
            grand_sum += data[i][j];
    const double grand = grand_sum / (double)(rows * cols);

    for (std::size_t i = 0; i < rows; ++i) {
        double s = 0.0;
        for (std::size_t j = 0; j < cols; ++j) {
            s += data[i][j];
            const double dd = data[i][j] - grand;
            ss_total += dd * dd;
        }
        row_means[i] = s / (double)cols;
    }
    for (std::size_t j = 0; j < cols; ++j) {
        double s = 0.0;
        for (std::size_t i = 0; i < rows; ++i) s += data[i][j];
        col_means[j] = s / (double)rows;
    }

    double ss_row = 0.0, ss_col = 0.0;
    for (std::size_t i = 0; i < rows; ++i) {
        const double dd = row_means[i] - grand;
        ss_row += (double)cols * dd * dd;
    }
    for (std::size_t j = 0; j < cols; ++j) {
        const double dd = col_means[j] - grand;
        ss_col += (double)rows * dd * dd;
    }
    r.ss_total = ss_total;
    r.ss_row = ss_row;
    r.ss_col = ss_col;
    r.ss_error = ss_total - ss_row - ss_col;

    const long long df_row = (long long)rows - 1;
    const long long df_col = (long long)cols - 1;
    const long long df_error = df_row * df_col;
    if (r.ss_error <= 1e-12 * std::max(ss_total, 1.0) || df_error < 1) {
        r.valid = false;  // 完美可加,残差为 0,F 无定义。
        return r;
    }
    const double ms_error = r.ss_error / (double)df_error;
    const double ms_row = r.ss_row / (double)df_row;
    const double ms_col = r.ss_col / (double)df_col;
    r.F_A = ms_row / ms_error;
    r.F_B = ms_col / ms_error;
    r.p_A = 1.0 - detail::f_cdf(r.F_A, (double)df_row, (double)df_error);
    r.p_B = 1.0 - detail::f_cdf(r.F_B, (double)df_col, (double)df_error);
    r.significant_A = r.p_A < alpha;
    r.significant_B = r.p_B < alpha;
    r.valid = true;
    return r;
}

}  // namespace mf::probability
