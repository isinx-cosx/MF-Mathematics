#include "zeta_interface.h"

#include <cmath>
#include <cstdint>
#include <limits>
#include <numeric>
#include <stdexcept>

#include "prime_sieves.h"

namespace mf::number_theory {

double euler_product(double s, long long prime_limit) {
    if (prime_limit < 2)
        throw std::invalid_argument("素数上限必须 ≥2");
    const std::vector<long long> primes = eratosthenes(prime_limit);
    double product = 1.0;
    for (long long p : primes)
        product *= 1.0 / (1.0 - std::pow(static_cast<double>(p), -s));
    return product;
}

double zeta_dirichlet_series(double s, long long n_terms) {
    if (n_terms < 1) throw std::invalid_argument("项数必须 ≥1");
    double sum = 0.0;
    for (long long n = 1; n <= n_terms; ++n)
        sum += std::pow(static_cast<double>(n), -s);
    return sum;
}

double dirichlet_l_function(double s, const std::vector<long long>* chi,
                            long long n_terms, long long conductor) {
    if (n_terms < 1) throw std::invalid_argument("项数必须 ≥1");
    if (conductor < 1) throw std::invalid_argument("导子必须 ≥1");
    if (chi != nullptr && static_cast<long long>(chi->size()) != conductor)
        throw std::invalid_argument("chi 长度与 conductor 不匹配");

    double sum = 0.0;
    for (long long n = 1; n <= n_terms; ++n) {
        long long cn;
        if (chi == nullptr) {
            if (n % 2 == 0)
                cn = 0;
            else
                cn = (n % 4 == 1) ? 1 : -1;
        } else {
            cn = (*chi)[static_cast<std::size_t>(n % conductor)];
        }
        if (cn != 0) sum += static_cast<double>(cn) * std::pow(static_cast<double>(n), -s);
    }
    return sum;
}

// ── 精确有理数(带溢出降级)───────────────────────────────────────────────

namespace {

using u64 = unsigned long long;

// 有符号绝对值(安全处理 LLONG_MIN 不会出现于此实现)
inline u64 mag(long long v) {
    if (v < 0) {
        // -(v+1)+1 避免 LLONG_MIN 取负溢出
        return static_cast<u64>(-(v + 1)) + 1;
    }
    return static_cast<u64>(v);
}

inline bool mul_u64(u64 a, u64 b, u64& out) {
    if (b != 0 && a > std::numeric_limits<u64>::max() / b) return false;
    out = a * b;
    return true;
}

inline bool add_u64(u64 a, u64 b, u64& out) {
    if (a > std::numeric_limits<u64>::max() - b) return false;
    out = a + b;
    return true;
}

// 有符号乘法,溢出返回 false
inline bool mul_ll(long long a, long long b, long long& out) {
    const bool neg = (a < 0) ^ (b < 0);
    u64 p;
    if (!mul_u64(mag(a), mag(b), p)) return false;
    if (p > static_cast<u64>(std::numeric_limits<long long>::max())) return false;
    out = neg ? -static_cast<long long>(p) : static_cast<long long>(p);
    return true;
}

// 有符号加法,溢出返回 false
inline bool add_ll(long long a, long long b, long long& out) {
    if ((b > 0 && a > std::numeric_limits<long long>::max() - b) ||
        (b < 0 && a < std::numeric_limits<long long>::min() - b)) {
        return false;
    }
    out = a + b;
    return true;
}

struct Rat {
    bool exact;
    long long num;  // exact 时有效,可为负
    long long den;  // exact 时有效,> 0
    double approx;  // !exact 时有效
};

// 构造已约分有理数;num 溢出不可能(由调用方保证),den 必须 > 0
Rat make_rat(long long num, long long den) {
    if (den < 0) {
        num = -num;
        den = -den;
    }
    const long long g = std::gcd(num, den);
    num /= g;
    den /= g;
    return {true, num, den, static_cast<double>(num) / den};
}

Rat rat_add(const Rat& a, const Rat& b) {
    if (!a.exact || !b.exact)
        return {false, 0, 0, a.approx + b.approx};
    // 通分到最小公分母:g = gcd(d1,d2), num = n1*d2/g + n2*d1/g, den = d1*(d2/g)
    const long long g = std::gcd(a.den, b.den);
    const long long d1r = a.den / g;
    const long long d2r = b.den / g;
    long long t1, t2, num, den;
    if (!mul_ll(a.num, d2r, t1) || !mul_ll(b.num, d1r, t2) ||
        !add_ll(t1, t2, num) || !mul_ll(d1r, b.den, den))
        return {false, 0, 0, a.approx + b.approx};
    return make_rat(num, den);
}

Rat rat_mul(const Rat& a, const Rat& b) {
    if (!a.exact || !b.exact)
        return {false, 0, 0, a.approx * b.approx};
    bool neg = (a.num < 0) ^ (b.num < 0);
    u64 an = mag(a.num), ad = a.den, bn = mag(b.num), bd = b.den;
    const u64 g1 = std::gcd(an, bd);
    an /= g1;
    bd /= g1;
    const u64 g2 = std::gcd(bn, ad);
    bn /= g2;
    ad /= g2;
    u64 nn, dd;
    if (!mul_u64(an, bn, nn) || !mul_u64(ad, bd, dd))
        return {false, 0, 0, a.approx * b.approx};
    if (nn > static_cast<u64>(std::numeric_limits<long long>::max()) ||
        dd > static_cast<u64>(std::numeric_limits<long long>::max()))
        return {false, 0, 0, a.approx * b.approx};
    long long num = neg ? -static_cast<long long>(nn) : static_cast<long long>(nn);
    return make_rat(num, static_cast<long long>(dd));
}

Rat rat_div_int(const Rat& a, long long n) {
    if (!a.exact) return {false, 0, 0, a.approx / static_cast<double>(n)};
    return rat_mul(a, make_rat(1, n));
}

// 二项式系数 C(n, k),用连乘分数计算以控制中间量
Rat binom(long long n, long long k) {
    if (k < 0 || k > n) return make_rat(0, 1);
    if (k == 0 || k == n) return make_rat(1, 1);
    k = k < n - k ? k : n - k;
    Rat r = make_rat(1, 1);
    for (long long i = 1; i <= k; ++i) {
        Rat term = make_rat(n - k + i, i);
        r = rat_mul(r, term);
    }
    return r;
}

}  // namespace

BernoulliResult bernoulli_number(long long n) {
    if (n < 0) throw std::invalid_argument("n 必须为非负整数");
    if (n == 0) return {false, 1, 1, 1.0};
    if (n == 1) return {false, -1, 2, -0.5};

    // 递推:Σ_{k=0}^{n} C(n+1, k) B_k = 0 ⇒ B_n = -1/(n+1) Σ_{k=0}^{n-1} C(n+1,k) B_k
    std::vector<Rat> B(static_cast<std::size_t>(n) + 1);
    B[0] = make_rat(1, 1);
    B[1] = make_rat(-1, 2);
    for (long long m = 2; m <= n; ++m) {
        if (m % 2 == 1) {
            B[static_cast<std::size_t>(m)] = make_rat(0, 1);
            continue;
        }
        Rat sum = make_rat(0, 1);
        for (long long k = 0; k < m; ++k)
            sum = rat_add(sum, rat_mul(binom(m + 1, k), B[static_cast<std::size_t>(k)]));
        B[static_cast<std::size_t>(m)] = rat_div_int(sum, -(m + 1));  // B_m = -S/(m+1)
    }

    const Rat& r = B[static_cast<std::size_t>(n)];
    if (r.exact) return {false, r.num, r.den, r.approx};
    // ── 精确有理数路径溢出后的降级 ──
    //
    // **不能**直接返回上面那套递推在 double 下的 approx：该递推在 double 下数值
    // 极不稳定（中间项被二项式系数放大到 ~1e81），实测 B_100 会算成 +9.12e82，
    // 而真值是 −2.838e78 —— 符号都反了，相差 3 万倍。
    //
    // 改用渐近公式（对 |B_{2m}| 的著名展开的首项，m 越大越精确）：
    //     B_{2m} = (-1)^{m+1} · 2·(2m)!·ζ(2m) / (2π)^{2m}
    // 该式对 B_100 给出 2.82e78，与 mpmath 的 2.838e78 一致。
    // 在 log 空间求值，避免 (2m)!/(2π)^{2m} 的中间量溢出。
    if (n % 2 == 1) return {false, 0, 1, 0.0};  // 奇 n>1 恒为 0（保险）
    {
        const long long m = n / 2;
        // ζ(2m)：2m 较大时它极其接近 1（ζ(100) − 1 ≈ 8e-31），
        // 直接用引擎自己的 Dirichlet 级数取到 double 能表达的精度。
        double zeta_val = 1.0;
        try {
            zeta_val = zeta_dirichlet_series(static_cast<double>(n), 10000);
        } catch (const std::exception&) {
            zeta_val = 1.0;
        }
        if (!(zeta_val > 0.0)) zeta_val = 1.0;
        const double log_abs =
            std::log(2.0) + std::lgamma(static_cast<double>(n) + 1.0) -
            static_cast<double>(n) * std::log(2.0 * 3.14159265358979323846) +
            std::log(zeta_val);
        const double mag = std::exp(log_abs);
        if (!std::isfinite(mag)) return {true, 0, 0, r.approx};  // 实在算不出，退回
        // 符号是 (-1)^{m+1}：m 为奇数 → +1，m 为偶数 → −1。
        // 校验：m=1 → B₂ = +1/6 ✓；m=2 → B₄ = −1/30 ✓；m=30 → B₆₀ = −2.13999e34 ✓。
        const double sign = (m % 2 == 1) ? 1.0 : -1.0;
        return {true, 0, 0, sign * mag};
    }
}

BernoulliResult zeta_negative(long long n) {
    if (n < 0) throw std::invalid_argument("n 必须为非负整数");
    if (n == 0) return {false, -1, 2, -0.5};  // ζ(0) = -1/2

    // ζ(-n) = -B_{n+1} / (n+1)
    const BernoulliResult b = bernoulli_number(n + 1);
    if (!b.is_approx) {
        // 精确路径:分子取负,分母乘 (n+1),溢出则降级
        u64 num = mag(-b.num), den;
        if (!mul_u64(b.den, static_cast<u64>(n + 1), den) ||
            num > static_cast<u64>(std::numeric_limits<long long>::max()) ||
            den > static_cast<u64>(std::numeric_limits<long long>::max())) {
            return {true, 0, 0, -b.approx / static_cast<double>(n + 1)};
        }
        const Rat r = make_rat(-b.num, b.den * (n + 1));
        if (r.exact) return {false, r.num, r.den, r.approx};
        return {true, 0, 0, r.approx};
    }
    return {true, 0, 0, -b.approx / static_cast<double>(n + 1)};
}

}  // namespace mf::number_theory
