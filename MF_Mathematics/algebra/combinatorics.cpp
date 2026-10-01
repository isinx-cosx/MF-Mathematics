#include "combinatorics.h"

#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace mf::algebra {

namespace {

// 有符号乘法,溢出返回 false。
bool mul_ll(long long a, long long b, long long& out) {
    const bool neg = (a < 0) ^ (b < 0);
    const unsigned long long ua =
        a < 0 ? ~static_cast<unsigned long long>(a + 1) + 1
              : static_cast<unsigned long long>(a);
    const unsigned long long ub =
        b < 0 ? ~static_cast<unsigned long long>(b + 1) + 1
              : static_cast<unsigned long long>(b);
    if (ub != 0 && ua > std::numeric_limits<unsigned long long>::max() / ub)
        return false;
    const unsigned long long p = ua * ub;
    if (p > static_cast<unsigned long long>(std::numeric_limits<long long>::max()))
        return false;
    out = neg ? -static_cast<long long>(p) : static_cast<long long>(p);
    return true;
}

}  // namespace

long long addition_principle(const std::vector<long long>& ways) {
    long long total = 0;
    for (long long w : ways) total += w;
    return total;
}

long long multiplication_principle(const std::vector<long long>& steps) {
    long long total = 1;
    for (long long s : steps) total *= s;
    return total;
}

long long permutation(long long n, long long m) {
    if (n < 0 || m < 0)
        throw std::invalid_argument("n 和 m 必须为非负整数");
    if (m > n) throw std::invalid_argument("m 不能大于 n");
    long long r = 1;
    for (long long i = 0; i < m; ++i) {
        long long t;
        if (!mul_ll(r, n - i, t))
            throw std::overflow_error("排列数超出 long long 范围");
        r = t;
    }
    return r;
}

long long combination(long long n, long long m) {
    if (n < 0 || m < 0)
        throw std::invalid_argument("n 和 m 必须为非负整数");
    if (m > n) throw std::invalid_argument("m 不能大于 n");
    if (m > n - m) m = n - m;
    // 乘法式 C(n,m) = Π (n-m+i)/i;每步先约分再乘,中间量不溢出。
    long long r = 1;
    for (long long i = 1; i <= m; ++i) {
        long long t = n - m + i;
        long long d = i;
        const long long g1 = std::gcd(t, d);
        t /= g1;
        d /= g1;
        const long long g2 = std::gcd(r, d);
        r /= g2;
        d /= g2;  // 数学上 d 必为 1(见注释于头文件对应推导)
        long long product;
        if (!mul_ll(r, t, product))
            throw std::overflow_error("组合数超出 long long 范围");
        r = product;
    }
    return r;
}

std::vector<std::string> comb_identities() {
    return {
        "C(n, 0) = C(n, n) = 1",
        "C(n, 1) = C(n, n-1) = n",
        "对称性: C(n, m) = C(n, n-m)",
        "递推公式: C(n, m) = C(n-1, m-1) + C(n-1, m)（帕斯卡恒等式）",
        "求和公式: Σ_{k=0}^n C(n, k) = 2^n",
        "交错和: Σ_{k=0}^n (-1)^k C(n, k) = 0 (n ≥ 1)",
        "范德蒙恒等式: Σ_{k=0}^r C(m, k)·C(n, r-k) = C(m+n, r)",
        "朱世杰恒等式: Σ_{k=m}^n C(k, m) = C(n+1, m+1)",
    };
}

std::string binomial_expand(const std::string& a, const std::string& b,
                            long long n) {
    if (n < 0) throw std::invalid_argument("n 必须为非负整数");

    const auto pow_str = [](const std::string& base, long long exp) {
        return base + "^" + std::to_string(exp);
    };

    std::vector<std::string> terms;
    terms.reserve(static_cast<std::size_t>(n) + 1);
    for (long long k = 0; k <= n; ++k) {
        const long long coeff = combination(n, k);
        std::string term;
        if (coeff == 1 && n - k == 0 && k == 0) {
            term = "1";
        } else if (coeff == 1) {
            if (n - k == 0)
                term = k > 1 ? pow_str(b, k) : b;
            else if (k == 0)
                term = (n - k > 1) ? pow_str(a, n - k) : a;
            else {
                const std::string ap = (n - k > 1) ? pow_str(a, n - k) : a;
                const std::string bp = k > 1 ? pow_str(b, k) : b;
                term = ap + "·" + bp;
            }
        } else {
            if (n - k == 0 && k == 0) {
                term = std::to_string(coeff);
            } else if (n - k == 0) {
                const std::string bp = k > 1 ? pow_str(b, k) : b;
                term = std::to_string(coeff) + "·" + bp;
            } else if (k == 0) {
                const std::string ap = (n - k > 1) ? pow_str(a, n - k) : a;
                term = std::to_string(coeff) + "·" + ap;
            } else {
                const std::string ap = (n - k > 1) ? pow_str(a, n - k) : a;
                const std::string bp = k > 1 ? pow_str(b, k) : b;
                term = std::to_string(coeff) + "·" + ap + "·" + bp;
            }
        }
        terms.push_back(std::move(term));
    }

    std::string out;
    for (std::size_t i = 0; i < terms.size(); ++i) {
        if (i) out += " + ";
        out += terms[i];
    }
    return out;
}

BinomialTerm binomial_term(const std::string& a, const std::string& b, long long n,
                           long long k) {
    if (n < 0) throw std::invalid_argument("n 必须为非负整数");
    if (k < 0 || k > n) throw std::invalid_argument("k 必须在 [0, n] 范围内");

    const long long coeff = combination(n, k);
    const auto pow_str = [](const std::string& base, long long exp) {
        return base + "^" + std::to_string(exp);
    };

    std::string a_part, b_part;
    if (n - k == 1) a_part = a;
    else if (n - k > 1) a_part = pow_str(a, n - k);
    if (k == 1) b_part = b;
    else if (k > 1) b_part = pow_str(b, k);

    std::string term_str;
    if (n - k == 0 && k == 0) {
        term_str = std::to_string(coeff);
    } else if (n - k == 0) {
        term_str = coeff > 1 ? std::to_string(coeff) + "·" + b_part : b_part;
    } else if (k == 0) {
        term_str = coeff > 1 ? std::to_string(coeff) + "·" + a_part : a_part;
    } else {
        std::vector<std::string> parts;
        if (coeff > 1) parts.push_back(std::to_string(coeff));
        parts.push_back(a_part);
        parts.push_back(b_part);
        for (std::size_t i = 0; i < parts.size(); ++i) {
            if (parts[i].empty()) continue;
            if (!term_str.empty()) term_str += "·";
            term_str += parts[i];
        }
    }
    return {term_str, coeff, k, k + 1};
}

}  // namespace mf::algebra
