#include "number_theory.h"

#include <cmath>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>

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

struct Frac {
    long long num;
    long long den;  // > 0
};

// 浮点 → 有理近似(连分数,分母 ≤ max_denom),等价 Python Fraction.limit_denominator。
Frac to_fraction(double x, long long max_denom) {
    if (std::isnan(x) || std::isinf(x))
        throw std::invalid_argument("无法转为分数");
    if (x == 0.0) return {0, 1};
    const long long sign = x < 0 ? -1 : 1;
    double v = std::abs(x);
    long long p0 = 0, q0 = 1, p1 = 1, q1 = 0;
    while (true) {
        const long long a = static_cast<long long>(std::floor(v));
        const long long p2 = a * p1 + p0;
        const long long q2 = a * q1 + q0;
        if (q2 > max_denom) break;
        p0 = p1;
        q0 = q1;
        p1 = p2;
        q1 = q2;
        const double frac = v - static_cast<double>(a);
        if (std::abs(frac) < 1e-15) break;
        v = 1.0 / frac;
        if (v > 1e15) break;
    }
    return {sign * p1, q1};
}

}  // namespace

LawResult commutative_law(double a, double b, const std::string& op) {
    if (op != "+" && op != "*")
        throw std::invalid_argument("不支持的运算符 '" + op + "',仅支持 '+' 和 '*'");
    double left, right;
    if (op == "+") {
        left = a + b;
        right = b + a;
    } else {
        left = a * b;
        right = b * a;
    }
    return {left, right, std::abs(left - right) < 1e-12};
}

LawResult associative_law(double a, double b, double c, const std::string& op) {
    if (op != "+" && op != "*")
        throw std::invalid_argument("不支持的运算符 '" + op + "',仅支持 '+' 和 '*'");
    double left, right;
    if (op == "+") {
        left = (a + b) + c;
        right = a + (b + c);
    } else {
        left = (a * b) * c;
        right = a * (b * c);
    }
    return {left, right, std::abs(left - right) < 1e-12};
}

LawResult distributive_law(double a, double b, double c) {
    const double left = a * (b + c);
    const double right = a * b + a * c;
    return {left, right, std::abs(left - right) < 1e-12};
}

double abs_value(double x) { return std::abs(x); }

double distance_on_number_line(double a, double b) { return std::abs(a - b); }

Ratio ratio(double a, double b) {
    if (b == 0.0) throw std::invalid_argument("分母不能为零");
    const Frac fa = to_fraction(a, 1000000);
    const Frac fb = to_fraction(b, 1000000);
    // a:b = fa/fb = (fa.num·fb.den) : (fa.den·fb.num)
    long long num, den;
    if (!mul_ll(fa.num, fb.den, num) || !mul_ll(fa.den, fb.num, den))
        throw std::overflow_error("比例化简超出 long long 范围");
    if (den < 0) {
        num = -num;
        den = -den;
    }
    if (den == 0) throw std::invalid_argument("分母不能为零");
    const long long g = std::gcd(num, den);
    if (g != 0) {
        num /= g;
        den /= g;
    }
    return {num, den};
}

double percentage(double part, double total) {
    if (total == 0.0) throw std::invalid_argument("总量不能为零");
    const double pct = (part / total) * 100.0;
    return std::round(pct * 1e4) / 1e4;
}

double percentage_change(double old_value, double new_value) {
    if (old_value == 0.0) throw std::invalid_argument("旧值不能为零,无法计算变化率");
    const double change = ((new_value - old_value) / std::abs(old_value)) * 100.0;
    return std::round(change * 1e4) / 1e4;
}

ScientificNotation to_scientific_notation(double x) {
    if (x == 0.0) return {0.0, 0};
    long long exponent =
        static_cast<long long>(std::floor(std::log10(std::abs(x))));
    double coefficient = x / std::pow(10.0, static_cast<double>(exponent));
    // 用绝对值判断：x = -500 时 coefficient = -5，若按 `coefficient < 1.0` 判断
    // 会误以为不在 [1,10) 再乘一次 10，得到 [-50, 1]（规范形式应为 [-5, 2]）。
    if (std::abs(coefficient) < 1.0) {
        coefficient *= 10.0;
        --exponent;
    }
    return {std::round(coefficient * 1e10) / 1e10, exponent};
}

double significant_figures(double x, long long n) {
    if (n <= 0) throw std::invalid_argument("有效数字位数必须为正整数");
    if (x == 0.0) return 0.0;
    const long long exponent =
        static_cast<long long>(std::floor(std::log10(std::abs(x))));
    const double factor =
        std::pow(10.0, static_cast<double>(n - 1 - exponent));
    return std::round(x * factor) / factor;
}

}  // namespace mf::algebra
