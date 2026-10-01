// probe_bugs.cpp — 边界情况对抗探针(临时,验证潜在 bug)。
#include <cmath>
#include <cstdio>
#include <limits>
#include <string>

#include "json.hpp"
#include "number_theory/number_theory_internal.h"
#include "number_theory/arithmetic_functions.h"
#include "probability/prob_internal.h"
#include "probability/hypothesis_test.h"
#include "probability/statistics.h"
#include "probability/nonparametric.h"
#include "algebra/sequences.h"
#include "algebra/expression.h"
#include "algebra/inequality.h"
#include "calculus/series.h"
#include "calculus/integrals.h"
#include "calculus/derivatives_app.h"
#include "algebraic_topology/at_internal.h"
#include "algebraic_topology/homology.h"
#include "complex_analysis/residue.h"
#include "complex_analysis/zeta.h"
#include "complex_analysis/ca_internal.h"

namespace nt = mf::number_theory::detail;
namespace ntf = mf::number_theory;
namespace pd = mf::probability::detail;
namespace pr = mf::probability;
namespace al = mf::algebra;
namespace ca = mf::calculus;

static int verify_fixes();

int main() {
    int bad = 0;
    bad += verify_fixes();

    // 1. json:inf/NaN 往返。
    {
        mf::json::Value v = mf::json::Value(std::numeric_limits<double>::infinity());
        std::string s = v.to_string();
        printf("inf -> '%s'\n", s.c_str());
        mf::json::Value v2 = mf::json::Value(std::numeric_limits<double>::quiet_NaN());
        printf("nan -> '%s'\n", v2.to_string().c_str());
        // 2^63 = 9.223372036854775808e18,float 恰好是 2^63。
        mf::json::Value big = mf::json::Value(9223372036854775808.0);
        printf("big double 2^63 -> '%s'\n", big.to_string().c_str());
        try {
            printf("big.as_int() = %lld\n", big.as_int());
        } catch (const std::exception& e) {
            printf("big.as_int() threw: %s\n", e.what());
        }
    }

    // 2. mul_mod 在 LLONG_MAX 附近。
    {
        const long long m = 9223372036854775806LL;
        printf("mul_mod(10^18, 10^18, m) = %lld\n", nt::mul_mod(1000000000000000000LL, 1000000000000000000LL, m));
        printf("mul_mod(m-1, m-1, m) = %lld\n", nt::mul_mod(m - 1, m - 1, m));
    }

    // 3. t_inv 极端分位数。
    {
        printf("t_inv(0.975, 4) = %.6f (期望 2.776)\n", pd::t_inv(0.975, 4));
        printf("t_inv(0.975, 1) = %.6f (期望 12.706)\n", pd::t_inv(0.975, 1));
        printf("normal_inv(0.9999999999) = %.6f\n", pd::normal_inv(0.9999999999));
    }

    // 4. 概率:小样本 t 检验 df 边界。
    {
        // p_value t, df=1(柯西尾)应有限。
        printf("p_value(t=3, df=1) = %.6f\n", pr::p_value(3.0, "t", 1, "two-sided"));
        // CDF 校验。
        printf("t_cdf(0,10) = %.9f (期望 0.5)\n", pd::t_cdf(0.0, 10));
        printf("t_cdf(1,1) = %.9f (期望 0.75)\n", pd::t_cdf(1.0, 1));
        printf("normal_cdf(0) = %.9f (期望 0.5)\n", pd::normal_cdf(0.0));
        printf("normal_cdf(1.96) = %.9f (期望 0.975002)\n", pd::normal_cdf(1.96));
        printf("chi2_cdf(5,2) = %.9f (期望 0.917915)\n", pd::chi2_cdf(5.0, 2));
        printf("gamma_complex(0.5) = %.9f (期望 1.772454)\n", pd::gamma_p(0.5, 0.5));
    }

    // 5. 递推:初始值短但规则引用 a[-3]。
    {
        try {
            auto fib = al::recurrence_sequence({1, 1}, "a[-1] + a[-2]", 10);
            printf("fib10 = [");
            for (double f : fib) printf("%.0f,", f);
            printf("]\n");
        } catch (const std::exception& e) {
            printf("recurrence threw: %s\n", e.what());
            ++bad;
        }
    }

    // 6. 因式分解负数根。
    {
        printf("factor(x^2-4) = '%s'\n", al::factor("x**2 - 4").c_str());
        printf("factor(2x^2-2) = '%s'\n", al::factor("2*x**2 - 2").c_str());
        printf("factor(x^2+2x+1) = '%s'\n", al::factor("x**2 + 2*x + 1").c_str());
    }

    // 7. 不等式:负系数。
    {
        printf("solve(2x-3>0) = '%s'\n", al::solve_linear_inequality("2*x - 3 > 0").c_str());
        printf("solve(1-x>0) = '%s'\n", al::solve_linear_inequality("1 - x > 0").c_str());
        printf("solve(-x^2+4>0) = '%s'\n", al::solve_quadratic_inequality("-x**2 + 4 > 0").c_str());
    }

    // 8. 级数审敛。
    {
        printf("p_series(1/sqrt(n)) = '%s' (期望 divergent)\n", ca::p_series_test("1/n**(0.5)", "n").c_str());
        printf("leibniz((-1)^n/n) = '%s'\n", ca::leibniz_test("(-1)**n/n", "n").c_str());
    }

    printf("probe done, bad=%d\n", bad);
    return bad;
}

// 修复验证段。
static int verify_fixes() {
    int bad = 0;
    // residue 正则点 → 0。
    {
        auto r = mf::complex_analysis::residue("z", {1, 0});
        printf("[fix] residue(z,1) = %.4g%+.4gi (期望 0)\n", r.real(), r.imag());
        if (std::abs(r) > 1e-9) ++bad;
    }
    // divisor_sum(2^62) = 2^63-1。
    {
        try {
            long long s = ntf::divisor_sum(4611686018427387904LL);
            printf("[fix] σ(2^62) = %lld (期望 9223372036854775807)\n", s);
            if (s != 9223372036854775807LL) ++bad;
        } catch (const std::exception& e) {
            printf("[fix] σ(2^62) threw: %s\n", e.what());
            ++bad;
        }
    }
    // mul_ll(-1, 7) = -7。
    {
        long long out;
        bool ok = mf::algebraic_topology::detail::mul_ll(-1, 7, out);
        printf("[fix] mul_ll(-1,7) = %lld ok=%d (期望 -7)\n", out, (int)ok);
        if (!ok || out != -7) ++bad;
    }
    // t_test 零方差。
    {
        auto r = pr::t_test({5, 5, 5, 5}, 5.0, 0.05, "two-sided");
        printf("[fix] t_test 全同 p=%.4f (期望 1)\n", r.p_value);
        if (!(r.p_value == 1.0)) ++bad;
    }
    // factor 线性式。
    {
        printf("[fix] factor(2x+1) = '%s' (期望 2*x + 1)\n", al::factor("2*x + 1").c_str());
        printf("[fix] factor(x^3) = '%s' (期望 x**3)\n", al::factor("x**3").c_str());
    }
    // 二次不等式重根。
    {
        printf("[fix] x²-2x+1>0 = '%s' (期望两侧)\n",
               al::solve_quadratic_inequality("x**2 - 2*x + 1 > 0").c_str());
    }
    // 慢衰减反常积分。
    {
        try {
            double v = mf::calculus::improper_integral("1/x**1.5", "x", "1", "oo");
            printf("[fix] ∫1/x^1.5 = %.4f (期望 2)\n", v);
            if (std::abs(v - 2.0) > 0.01) ++bad;
        } catch (const std::exception& e) {
            printf("[fix] ∫1/x^1.5 threw: %s\n", e.what());
            ++bad;
        }
    }
    // 同斜率不同相位三角积分。
    {
        auto s = mf::calculus::integrate_indefinite("sin(2*x)*cos(2*x + 1)", "x");
        printf("[fix] ∫sin(2x)cos(2x+1) = '%s'\n", s.c_str());
    }
    // 级数比值。
    {
        printf("[fix] series_convergence(1/n) = '%s' (期望 判别法失效)\n",
               ca::series_convergence("1/n", "n").c_str());
    }
    // gamma 负整数 → 抛异常。
    {
        try {
            (void)mf::complex_analysis::detail::gamma_complex({-1.0, 0});
            printf("[fix] gamma(-1) 未抛异常! (期望抛)\n");
            ++bad;
        } catch (const std::exception&) {
            printf("[fix] gamma(-1) 正确抛出\n");
        }
    }
    // zeta s=1 → 抛异常。
    {
        try {
            (void)mf::complex_analysis::analytic_continuation_zeta({1.0, 0});
            printf("[fix] ζ(1) 未抛异常! (期望抛)\n");
            ++bad;
        } catch (const std::exception&) {
            printf("[fix] ζ(1) 正确抛出\n");
        }
    }
    // Wilcoxon 单侧方向。
    {
        auto r = pr::wilcoxon_signed_rank({10, 12, 14, 15, 18}, {8, 9, 11, 13, 15},
                                          0.0, "greater", 0.05);
        printf("[fix] wilcoxon greater p=%.4f (期望显著<0.05)\n", r.p_value);
        if (!(r.p_value < 0.05)) ++bad;
    }
    // mul_ll 反例:复形贝蒂数。
    {
        using mf::algebraic_topology::Simplex;
        auto res = mf::algebraic_topology::build_simplicial_complex(
            {Simplex{0, 1, 2}, Simplex{2, 3}, Simplex{1, 2}, Simplex{0, 4},
             Simplex{2, 4}, Simplex{0, 1}, Simplex{0, 3}});
        auto b = mf::algebraic_topology::betti_numbers(res.complex);
        printf("[fix] betti = [");
        for (auto x : b) printf("%lld,", x);
        printf("] (期望 [1,2,0]:χ=5-7+1=-1,β1=3-1=2)\n");
        if (b.size() < 3 || b[0] != 1 || b[1] != 2 || b[2] != 0) ++bad;
    }
    return bad;
}
