#include "continued_fractions.h"

#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace mf::number_theory {

std::vector<long long> continued_fraction(double x, long long n_terms) {
    if (n_terms <= 0) throw std::invalid_argument("n_terms 必须为正整数");
    if (std::isnan(x) || std::isinf(x))
        throw std::invalid_argument("无法对 inf/nan 做连分数展开");

    std::vector<long long> coeffs;
    double remaining = x;
    double prev_remaining = 0.0;
    bool have_prev = false;
    for (long long i = 0; i < n_terms; ++i) {
        if (!std::isfinite(remaining) ||
            std::abs(remaining) >= 9.2233720368547758e18)
            throw std::invalid_argument("连分数系数超出 long long 范围");
        const long long a = static_cast<long long>(std::floor(remaining));
        coeffs.push_back(a);

        const double frac_part = remaining - static_cast<double>(a);
        if (std::abs(frac_part) < 1e-15) break;
        remaining = 1.0 / frac_part;

        if (std::abs(remaining) > 1e15) break;  // 溢出保护
        if (have_prev && std::abs(remaining - prev_remaining) < 1e-15) break;
        prev_remaining = remaining;
        have_prev = true;
    }
    return coeffs;
}

namespace {

/**
 * a*b + c 是否会溢出 long long（精确判断，含符号）。
 *
 * 旧实现用 `frac[n] > (MAX - p) / p2` 这种写法，有两个致命问题：
 *   · p2 可以为 0（首项 a0=0，例 [0;2]=1/2）→ **整数除零，直接崩进程**；
 *   · 对负数比较恒为假，负向溢出完全漏检（例 [-2;2]）。
 * 这里用无符号算术做精确判定，不依赖 long double 的精度。
 */
bool mul_add_overflows(long long a, long long b, long long c) {
    if (a == 0 || b == 0) return false;
    const bool neg = ((a < 0) != (b < 0));
    const unsigned long long ua =
        a < 0 ? 0ULL - static_cast<unsigned long long>(a)
              : static_cast<unsigned long long>(a);
    const unsigned long long ub =
        b < 0 ? 0ULL - static_cast<unsigned long long>(b)
              : static_cast<unsigned long long>(b);
    if (ua != 0 && ub > std::numeric_limits<unsigned long long>::max() / ua)
        return true;
    const unsigned long long prod = ua * ub;
    const unsigned long long pos_limit =
        static_cast<unsigned long long>(std::numeric_limits<long long>::max());
    const unsigned long long neg_limit = pos_limit + 1ULL;  // |LLONG_MIN|
    if (prod > (neg ? neg_limit : pos_limit)) return true;
    if (!neg) {
        if (c >= 0) return prod > pos_limit - static_cast<unsigned long long>(c);
        return false;  // prod + c 只会变小，或落到负区间内
    }
    if (c <= 0) {
        const unsigned long long uc =
            0ULL - static_cast<unsigned long long>(c);
        return uc > neg_limit || prod > neg_limit - uc;
    }
    return false;  // -prod + c，c > 0，结果落在 [-prod, c] 内
}

}  // namespace

std::vector<Convergent> convergents(const std::vector<long long>& frac) {
    if (frac.empty()) throw std::invalid_argument("连分数系数列表不能为空");

    std::vector<Convergent> convs;
    convs.reserve(frac.size());

    // 教科书递推：p_{-2}=0, p_{-1}=1；q_{-2}=1, q_{-1}=0；
    //   p_n = a_n·p_{n-1} + p_{n-2},  q_n = a_n·q_{n-1} + q_{n-2}。
    // n=0 时给 p_0 = a0·1 + 0 = a0、q_0 = a0·0 + 1 = 1，首项也就顺带处理了，
    // 不必再为 n==0 / n==1 写两套（旧实现的两套正是崩溃与漏检的来源）。
    long long p2 = 0, p1 = 1;
    long long q2 = 1, q1 = 0;
    for (std::size_t n = 0; n < frac.size(); ++n) {
        const long long a = frac[n];
        if (mul_add_overflows(a, p1, p2))
            throw std::overflow_error("连分数分子溢出（系数过大）");
        if (mul_add_overflows(a, q1, q2))
            throw std::overflow_error("连分数分母溢出（系数过大）");
        const long long p = a * p1 + p2;
        const long long q = a * q1 + q2;
        const double approx = q != 0
            ? static_cast<double>(p) / static_cast<double>(q)
            : std::numeric_limits<double>::infinity();
        convs.push_back({p, q, approx});
        p2 = p1; p1 = p;
        q2 = q1; q1 = q;
    }
    return convs;
}

RationalApprox best_rational_approximation(double x, long long max_denom) {
    if (max_denom < 1) throw std::invalid_argument("分母上限必须 ≥1");
    if (!std::isfinite(x) || std::abs(x) >= 9.2233720368547758e18)
        throw std::invalid_argument("|x| 超出 long long 可表示范围");
    if (x == 0.0) return {0, 1, 0.0};

    const long long sign = x >= 0 ? 1 : -1;
    const double x_abs = std::abs(x);

    long long p_minus_2 = 0, p_minus_1 = 1;  // p_{-2}=0, p_{-1}=1
    long long q_minus_2 = 1, q_minus_1 = 0;  // q_{-2}=1, q_{-1}=0

    long long best_p = 0, best_q = 1;
    double best_error = std::numeric_limits<double>::infinity();

    double remaining = x_abs;
    for (int iter = 0; iter < 100; ++iter) {  // 安全上限
        const long long a = static_cast<long long>(std::floor(remaining));
        const long long p = a * p_minus_1 + p_minus_2;
        const long long q = a * q_minus_1 + q_minus_2;

        if (q > max_denom) {
            // 半收敛子:取 t 使分母仍不超过 max_denom
            const long long t = (max_denom - q_minus_2) / q_minus_1;
            if (t > 0) {
                const long long sp = t * p_minus_1 + p_minus_2;
                const long long sq = t * q_minus_1 + q_minus_2;
                if (sq <= max_denom) {
                    const double err = std::abs(x_abs - static_cast<double>(sp) / sq);
                    if (err < best_error) {
                        best_p = sp;
                        best_q = sq;
                        best_error = err;
                    }
                }
            }
            break;
        }

        const double err = std::abs(x_abs - static_cast<double>(p) / q);
        if (err < best_error) {
            best_p = p;
            best_q = q;
            best_error = err;
        }

        p_minus_2 = p_minus_1;
        p_minus_1 = p;
        q_minus_2 = q_minus_1;
        q_minus_1 = q;

        const double frac_part = remaining - static_cast<double>(a);
        if (std::abs(frac_part) < 1e-15) break;
        remaining = 1.0 / frac_part;
    }

    const long long bp = best_p * sign;
    const double approx =
        best_q != 0 ? static_cast<double>(bp) / best_q
                    : std::numeric_limits<double>::infinity();
    return {bp, best_q, approx};
}

}  // namespace mf::number_theory
