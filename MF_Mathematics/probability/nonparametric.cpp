#include "nonparametric.h"

#include <algorithm>
#include <cmath>
#include <functional>
#include <stdexcept>

#include "prob_internal.h"

namespace mf::probability {

namespace {
using mf::probability::detail::mean;
using mf::probability::detail::median;
using mf::probability::detail::rank_average;

// 正态近似 p 值(含连续性校正)。
double mw_p_value(double u, double n1, double n2, const std::string& alternative) {
    const double mu = n1 * n2 / 2.0;
    const double sd = std::sqrt(n1 * n2 * (n1 + n2 + 1.0) / 12.0);
    if (sd < 1e-15) return 1.0;
    if (alternative == "two-sided") {
        const double z = std::abs(u - mu) / sd;
        return detail::two_sided_p(z);
    }
    // 上尾(greater)校正 -0.5,下尾(less)校正 +0.5。
    const double zc = (u - mu + (alternative == "greater" ? -0.5 : 0.5)) / sd;
    if (alternative == "greater") return 1.0 - detail::normal_cdf(zc);
    if (alternative == "less") return detail::normal_cdf(zc);
    throw std::invalid_argument("alternative 必须为 'two-sided'/'greater'/'less'");
}

// 是否有并列值(并列时精确枚举不适用,回退正态近似)。
bool has_ties(const std::vector<double>& v) {
    for (std::size_t i = 0; i < v.size(); ++i)
        for (std::size_t j = i + 1; j < v.size(); ++j)
            if (std::abs(v[i] - v[j]) < 1e-12) return true;
    return false;
}

// Wilcoxon 符号秩检验的精确 p 值:枚举 2^n 个符号组合,权重为平均秩(支持并列)。
double wilcoxon_exact_p(double w, const std::vector<double>& weights,
                        const std::string& alternative) {
    const long long n = (long long)weights.size();
    const long long total = 1LL << n;
    long long count_le = 0, count_ge = 0;
    for (long long mask = 0; mask < total; ++mask) {
        double wp = 0.0;
        for (long long i = 0; i < n; ++i)
            if (mask & (1LL << i)) wp += weights[(std::size_t)i];
        if (wp <= w + 1e-9) ++count_le;
        if (wp >= w - 1e-9) ++count_ge;
    }
    const double ple = (double)count_le / (double)total;
    const double pge = (double)count_ge / (double)total;
    if (alternative == "two-sided") return std::min(1.0, 2.0 * std::min(ple, pge));
    if (alternative == "greater") return pge;
    return ple;
}

// Mann-Whitney U 的精确 p 值:枚举 C(N,n1) 个组合的 U 分布(无并列时)。
double mw_exact_p(long long u, long long n1, long long n2,
                 const std::string& alternative) {
    const long long N = n1 + n2;
    std::vector<long long> comb((std::size_t)n1);
    long long count_le = 0, count_ge = 0, total = 0;
    std::function<void(long long, long long)> rec = [&](long long start, long long k) {
        if (k == n1) {
            ++total;
            long long rank_sum = 0;
            for (long long i = 0; i < n1; ++i) rank_sum += (comb[(std::size_t)i] + 1);
            const long long U = rank_sum - n1 * (n1 + 1) / 2;
            if (U <= u) ++count_le;
            if (U >= u) ++count_ge;
            return;
        }
        for (long long i = start; i < N - (n1 - k) + 1; ++i) {
            comb[(std::size_t)k] = i;
            rec(i + 1, k + 1);
        }
    };
    rec(0, 0);
    const double ple = (double)count_le / (double)total;
    const double pge = (double)count_ge / (double)total;
    if (alternative == "two-sided") return std::min(1.0, 2.0 * std::min(ple, pge));
    if (alternative == "greater") return pge;
    return ple;
}
}  // namespace

NonparametricResult mann_whitney_u(const std::vector<double>& group1,
                                   const std::vector<double>& group2,
                                   const std::string& alternative, double alpha) {
    if (group1.size() < 2 || group2.size() < 2)
        throw std::invalid_argument("每组至少需要 2 个数据点");
    NonparametricResult r;
    r.alpha = alpha;
    r.test_type = "Mann-Whitney";
    r.n1 = (long long)group1.size();
    r.n2 = (long long)group2.size();
    r.median1 = median(group1);
    r.median2 = median(group2);
    r.statistic = detail::mann_whitney_u(group1, group2);
    // 小样本且无并列:精确枚举(与大样本正态近似一致则用精确)。
    std::vector<double> all = group1;
    all.insert(all.end(), group2.begin(), group2.end());
    if (r.n1 + r.n2 <= 14 && !has_ties(all)) {
        r.p_value = mw_exact_p((long long)r.statistic, r.n1, r.n2, alternative);
    } else {
        r.p_value = mw_p_value(r.statistic, (double)r.n1, (double)r.n2, alternative);
    }
    r.significant = r.p_value < alpha;
    return r;
}

KruskalWallisResult kruskal_wallis(const std::vector<std::vector<double>>& groups,
                                   double alpha) {
    if (groups.size() < 3) throw std::invalid_argument("至少需要 3 组数据");
    for (std::size_t i = 0; i < groups.size(); ++i)
        if (groups[i].size() < 2) throw std::invalid_argument("每组至少 2 个数据点");
    KruskalWallisResult r;
    r.alpha = alpha;
    // 合并排名。
    std::vector<double> all;
    for (const auto& g : groups) all.insert(all.end(), g.begin(), g.end());
    const std::vector<double> ranks = rank_average(all);
    const double N = (double)all.size();
    std::size_t idx = 0;
    double h = 0.0;
    for (const auto& g : groups) {
        const double ni = (double)g.size();
        double ri = 0.0;
        for (std::size_t k = 0; k < g.size(); ++k) ri += ranks[idx++];
        h += ri * ri / ni;
        r.group_medians.push_back(median(g));
        r.mean_ranks.push_back(ri / ni);
    }
    r.H = 12.0 / (N * (N + 1.0)) * h - 3.0 * (N + 1.0);
    r.p_value = 1.0 - detail::chi2_cdf(std::max(0.0, r.H), (double)(groups.size() - 1));
    r.significant = r.p_value < alpha;
    return r;
}

NonparametricResult wilcoxon_signed_rank(const std::vector<double>& group1,
                                         const std::vector<double>& group2,
                                         double mu, const std::string& alternative,
                                         double alpha) {
    std::vector<double> diff;
    bool paired = false;
    if (!group2.empty()) {
        if (group1.size() != group2.size())
            throw std::invalid_argument("配对样本长度不一致");
        if (group1.size() < 3) throw std::invalid_argument("配对样本至少需要 3 对数据");
        paired = true;
        diff.resize(group1.size());
        for (std::size_t i = 0; i < group1.size(); ++i)
            diff[i] = group1[i] - group2[i];
    } else {
        if (group1.size() < 3) throw std::invalid_argument("样本至少需要 3 个数据点");
        diff.resize(group1.size());
        for (std::size_t i = 0; i < group1.size(); ++i) diff[i] = group1[i] - mu;
    }

    NonparametricResult r;
    r.alpha = alpha;
    r.test_type = paired ? "配对" : "单样本";
    r.n1 = (long long)diff.size();
    r.median1 = median(diff);

    long long n_zero = 0;
    for (double d : diff)
        if (std::abs(d) <= 1e-15) ++n_zero;
    const long long n_nonzero = r.n1 - n_zero;
    if (n_nonzero < 3) throw std::invalid_argument("非零差值不足,无法检验");

    const auto wp = detail::wilcoxon_ranks(diff);
    // 单侧用对应方向的秩和;双侧用较小者。
    double stat;
    if (alternative == "greater") stat = wp.first;       // W+
    else if (alternative == "less") stat = wp.second;    // W−
    else stat = std::min(wp.first, wp.second);           // W=min(W+,W−)
    r.statistic = stat;

    // 小样本:精确枚举 W+ 分布(权重=平均秩,支持并列;正态近似在小 n 误差大)。
    if (n_nonzero <= 15) {
        std::vector<double> abs_diff;
        for (double d : diff)
            if (std::abs(d) > 1e-15) abs_diff.push_back(std::abs(d));
        const std::vector<double> weights = detail::rank_average(abs_diff);
        r.p_value = wilcoxon_exact_p(stat, weights, alternative);
        r.significant = r.p_value < alpha;
        return r;
    }

    // 正态近似。
    const double n = (double)n_nonzero;
    const double m = n * (n + 1.0) / 4.0;
    const double sd = std::sqrt(n * (n + 1.0) * (2.0 * n + 1.0) / 24.0);
    if (sd < 1e-15) {
        r.p_value = 1.0;
    } else if (alternative == "two-sided") {
        const double z = std::abs(stat - m) / sd;
        r.p_value = detail::two_sided_p(z);
    } else if (alternative == "greater") {
        const double z = (stat - m - 0.5) / sd;  // 上尾连续性校正
        r.p_value = 1.0 - detail::normal_cdf(z);
    } else if (alternative == "less") {
        const double z = (stat - m + 0.5) / sd;  // 下尾连续性校正
        r.p_value = detail::normal_cdf(z);
    } else {
        throw std::invalid_argument("alternative 必须为 'two-sided'/'greater'/'less'");
    }
    r.significant = r.p_value < alpha;
    return r;
}

}  // namespace mf::probability
