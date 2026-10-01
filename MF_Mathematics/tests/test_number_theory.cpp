// test_number_theory.cpp — number_theory 内核 + JSON 分发层测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言。运行:
//   ctest --test-dir build -R number_theory

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <string>
#include <vector>

#include "api.h"
#include "number_theory/arithmetic_functions.h"
#include "number_theory/continued_fractions.h"
#include "number_theory/core_algorithms.h"
#include "number_theory/modular_arithmetic.h"
#include "number_theory/prime_sieves.h"
#include "number_theory/zeta_interface.h"

namespace nt = mf::number_theory;

// MSVC 默认不定义 M_PI,统一用局部常量 kPi
static const double kPi = 3.14159265358979323846;

static int g_checks = 0;
static int g_failures = 0;

#define CHECK(cond, msg)                                     \
    do {                                                     \
        ++g_checks;                                          \
        if (!(cond)) {                                       \
            ++g_failures;                                    \
            std::printf("[FAIL] %s\n", msg);                 \
        }                                                    \
    } while (0)

#define CHECK_EQ(a, b, msg) CHECK((a) == (b), msg)

static bool near(double a, double b, double tol) {
    return std::abs(a - b) <= tol;
}

// ── 内核层测试 ──────────────────────────────────────────────────────────────

static void test_arithmetic_functions() {
    CHECK_EQ(nt::euler_phi(10), 4LL, "euler_phi(10) == 4");
    CHECK_EQ(nt::euler_phi(1), 1LL, "euler_phi(1) == 1");
    CHECK_EQ(nt::divisor_count(12), 6LL, "divisor_count(12) == 6");
    CHECK_EQ(nt::divisor_sum(12), 28LL, "divisor_sum(12) == 28");
    CHECK_EQ(nt::mobius(6), 1LL, "mobius(6) == 1");
    CHECK_EQ(nt::mobius(12), 0LL, "mobius(12) == 0");
    CHECK_EQ(nt::mobius(30), -1LL, "mobius(30) == -1");
    CHECK_EQ(nt::mobius_prefix(10), -1LL, "mobius_prefix(10) == -1");
}

static void test_core_algorithms() {
    CHECK_EQ(nt::gcd(48, 18), 6LL, "gcd(48, 18) == 6");
    CHECK_EQ(nt::gcd(0, 7), 7LL, "gcd(0, 7) == 7");
    nt::ExtendedGcd eg = nt::extended_gcd(48, 18);
    CHECK(eg.g == 6 && eg.x == -1 && eg.y == 3,
          "extended_gcd(48,18) == (6, -1, 3)");
    CHECK_EQ(nt::mod_inverse(3, 7), 5LL, "mod_inverse(3, 7) == 5");
    CHECK_EQ(nt::mod_pow(2, 10, 1000), 24LL, "mod_pow(2, 10, 1000) == 24");
}

static void test_modular_arithmetic() {
    CHECK_EQ(nt::crt({2, 3, 2}, {3, 5, 7}), 23LL, "crt([2,3,2],[3,5,7]) == 23");
    CHECK_EQ(nt::primitive_root(7), 3LL, "primitive_root(7) == 3");
    long long x = nt::discrete_log(3, 2, 7);
    CHECK(nt::mod_pow(3, x, 7) == 2 && x >= 0,
          "discrete_log(3,2,7) 满足 3^x ≡ 2 (mod 7)");

    // 模数乘积超过 long long 时应抛异常,而非静默回绕成负数
    bool threw = false;
    try {
        nt::crt({0, 0}, {4294967291LL, 4294967293LL});
    } catch (const std::exception&) {
        threw = true;
    }
    CHECK(threw, "crt 模数乘积超范围 → 抛异常");
}

static void test_prime_sieves() {
    const std::vector<long long> expect20 = {2, 3, 5, 7, 11, 13, 17, 19};
    CHECK(nt::eratosthenes(20) == expect20, "eratosthenes(20) == 前 8 个素数");
    CHECK_EQ(static_cast<long long>(nt::segmented_sieve(100).size()), 25LL,
             "segmented_sieve(100) 有 25 个素数");
    CHECK(nt::is_prime(17), "is_prime(17) == true");
    CHECK(!nt::is_prime(100), "is_prime(100) == false");
    CHECK(nt::is_prime(2147483647LL), "is_prime(2^31-1) == true (M31)");

    const std::vector<std::pair<long long, long long>> expect84 = {
        {2, 2}, {3, 1}, {7, 1}};
    CHECK(nt::prime_factors(84) == expect84, "prime_factors(84) == [(2,2),(3,1),(7,1)]");
    const std::vector<std::pair<long long, long long>> expect97 = {{97, 1}};
    CHECK(nt::prime_factors(97) == expect97, "prime_factors(97) == [(97,1)]");
}

static void test_continued_fractions() {
    const std::vector<long long> coeffs =
        nt::continued_fraction(kPi, 6);
    CHECK(coeffs.size() >= 5 &&
              coeffs[0] == 3 && coeffs[1] == 7 && coeffs[2] == 15 &&
              coeffs[3] == 1 && coeffs[4] == 292,
          "continued_fraction(π,6) 前 5 项为 [3,7,15,1,292]");

    const std::vector<nt::Convergent> convs = nt::convergents({3, 7, 15, 1});
    CHECK(convs.size() == 4, "convergents([3,7,15,1]) 有 4 项");
    CHECK(convs[0].p == 3 && convs[0].q == 1, "C0 = 3/1");
    CHECK(convs[1].p == 22 && convs[1].q == 7, "C1 = 22/7");
    CHECK(convs[3].p == 355 && convs[3].q == 113, "C3 = 355/113");

    const nt::RationalApprox best = nt::best_rational_approximation(kPi, 1000);
    CHECK(best.p == 355 && best.q == 113, "best_rational_approximation(π,1000) == 355/113");
}

static void test_zeta_interface() {
    const double zeta2 = kPi * kPi / 6.0;
    CHECK(near(nt::euler_product(2.0, 100), zeta2, 0.05),
          "euler_product(2,100) ≈ π²/6");
    CHECK(near(nt::zeta_dirichlet_series(2.0, 10000), zeta2, 0.01),
          "zeta_dirichlet_series(2,10000) ≈ π²/6");
    CHECK(near(nt::dirichlet_l_function(1.0, nullptr, 10000, 4), kPi / 4.0, 0.01),
          "dirichlet_l_function(1,10000) ≈ π/4");

    nt::BernoulliResult b2 = nt::bernoulli_number(2);
    CHECK(!b2.is_approx && b2.num == 1 && b2.den == 6, "B2 = 1/6 (精确)");
    nt::BernoulliResult b4 = nt::bernoulli_number(4);
    CHECK(!b4.is_approx && b4.num == -1 && b4.den == 30, "B4 = -1/30 (精确)");
    nt::BernoulliResult b_odd = nt::bernoulli_number(7);
    CHECK(!b_odd.is_approx && b_odd.num == 0 && b_odd.den == 1, "B7 = 0 (奇数)");

    nt::BernoulliResult z1 = nt::zeta_negative(1);
    CHECK(!z1.is_approx && z1.num == -1 && z1.den == 12, "ζ(-1) = -1/12 (精确)");
    nt::BernoulliResult z3 = nt::zeta_negative(3);
    CHECK(!z3.is_approx && z3.num == 1 && z3.den == 120, "ζ(-3) = 1/120 (精确)");

    // 精确优先:较大的 n 溢出后应降级为浮点并标记
    nt::BernoulliResult b36 = nt::bernoulli_number(36);
    CHECK(b36.is_approx, "B36 溢出 long long → is_approx 标记");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[4096];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("euler_phi"), "function_exists(\"euler_phi\")");
    CHECK(!function_exists("no_such_fn"), "!function_exists(\"no_such_fn\")");

    CHECK(call("euler_phi", "{\"n\":10}") == "{\"isError\":false,\"value\":4}",
          "math_call euler_phi(10) == 4");
    CHECK(call("divisor_count", "{\"n\":12}") == "{\"isError\":false,\"value\":6}",
          "math_call divisor_count(12) == 6");
    CHECK(call("extended_gcd", "{\"a\":48,\"b\":18}") ==
              "{\"isError\":false,\"value\":[6,-1,3]}",
          "math_call extended_gcd(48,18) == [6,-1,3]");
    CHECK(call("crt", "{\"residues\":[2,3,2],\"moduli\":[3,5,7]}") ==
              "{\"isError\":false,\"value\":23}",
          "math_call crt == 23");
    CHECK(call("prime_factors", "{\"n\":84}") ==
              "{\"isError\":false,\"value\":[[2,2],[3,1],[7,1]]}",
          "math_call prime_factors(84) == [[2,2],[3,1],[7,1]]");
    CHECK(call("is_prime", "{\"n\":17}") ==
              "{\"isError\":false,\"value\":true}",
          "math_call is_prime(17) == true");
    CHECK(call("eratosthenes", "{\"n\":10}") ==
              "{\"isError\":false,\"value\":[2,3,5,7]}",
          "math_call eratosthenes(10) == [2,3,5,7]");
    CHECK(call("bernoulli_number", "{\"n\":2}") ==
              "{\"isError\":false,\"value\":[1,6]}",
          "math_call bernoulli_number(2) == [1,6]");
    CHECK(call("zeta_negative", "{\"n\":3}") ==
              "{\"isError\":false,\"value\":[1,120]}",
          "math_call zeta_negative(3) == [1,120]");

    // 错误路径
    const std::string err = call("euler_phi", "{\"n\":-1}");
    CHECK(err.find("\"isError\":true") != std::string::npos,
          "euler_phi(-1) → isError");
    const std::string missing = call("euler_phi", "{}");
    CHECK(missing.find("\"isError\":true") != std::string::npos,
          "euler_phi 缺参数 → isError");
    const std::string unknown = call("no_such_fn", "{}");
    CHECK(unknown.find("\"isError\":true") != std::string::npos,
          "未知函数 → isError");
}

int main() {
    system("chcp 65001 > nul");
    std::printf("===== number_theory 内核测试 =====\n");
    test_arithmetic_functions();
    test_core_algorithms();
    test_modular_arithmetic();
    test_prime_sieves();
    test_continued_fractions();
    test_zeta_interface();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
