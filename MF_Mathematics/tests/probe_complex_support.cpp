// 探针：SymEngine 的 eval_complex_double 到底支持哪些函数？
//
// 背景：复平面绘图要把 f(z) 在复网格上求值。原版（PyQt）用 sympy+lambdify+mpmath，
// 支持 zeta / gamma / erf 等特殊函数；新架构必须由 C++ 引擎算，所以先问清楚
// SymEngine 的复数值求值覆盖到哪里，再决定哪些要自己补实现。
//
// 编译（与 tests/test_limits 同样的依赖）：
//   g++ -std=c++17 -O2 probe_complex_support.cpp -o probe_complex_support.exe \
//       -I<MF_SYMENGINE_ROOT>/include -L<MF_SYMENGINE_ROOT>/lib \
//       -lsymengine -lflint -lgmp -lmpfr
#include <complex>
#include <cstdio>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/complex_double.h>
#include <symengine/eval_double.h>
#include <symengine/parser.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

using SymEngine::complex_double;
using SymEngine::eval_complex_double;
using SymEngine::parse;
using SymEngine::symbol;

struct Case {
    const char* expr;   // 用 z 的表达式
    std::complex<double> z;
    const char* want;   // 期望（人工算好的参考值）
};

int main() {
    const std::vector<Case> cases = {
        // ── 初等函数：复平面绘图的日常 ──
        {"z^2",              {1.0, 1.0},      "2i"},
        {"e^z",              {1.0, 0.0},      "e"},
        {"exp(z)",           {0.0, 3.141592653589793}, "-1"},
        {"sin(z)",           {0.0, 1.0},      "1.1752i"},
        {"cos(z)",           {0.0, 1.0},      "1.5431"},
        {"tan(z)",           {0.0, 1.0},      "0.7616i"},
        {"log(z)",           {-1.0, 0.0},     "i*pi"},
        {"sqrt(z)",          {-1.0, 0.0},     "i"},
        {"abs(z)",           {3.0, 4.0},      "5"},
        {"z^(-1)",           {0.0, 1.0},      "-i"},
        {"1/z",              {1.0, 1.0},      "0.5-0.5i"},
        {"sinh(z)",          {1.0, 0.0},      "1.1752"},
        {"cosh(z)",          {1.0, 0.0},      "1.5431"},
        {"asin(z)",          {0.5, 0.0},      "0.5236"},
        {"atan(z)",          {1.0, 0.0},      "0.7854"},
        // ── 原版明确支持的特殊函数 ──
        {"zeta(z)",          {2.0, 0.0},      "1.6449 (pi^2/6)"},
        {"gamma(z)",         {0.5, 0.0},      "1.7725 (sqrt(pi))"},
        {"erf(z)",           {1.0, 0.0},      "0.8427"},
        {"erfc(z)",          {1.0, 0.0},      "0.1573"},
        {"besselj(0,z)",     {1.0, 0.0},      "0.7652"},
        {"li(z)",            {2.0, 0.0},      "1.0452"},
        {"zeta(z)",          {0.5, 14.134725141735}, "复零点附近 ~0"},
        {"gamma(z)",         {0.0, 1.0},      "≈ -0.4980-0.1549i"},
    };

    const auto zs = symbol("z");
    int ok = 0, bad = 0;
    for (const auto& c : cases) {
        std::printf("%-16s z=%-24s 期望 %-24s ", c.expr,
                    (std::to_string(c.z.real()) + (c.z.imag() >= 0 ? "+" : "") +
                     std::to_string(c.z.imag()) + "i").c_str(), c.want);
        try {
            const auto e = parse(c.expr);
            const auto sub = e->subs({{zs, complex_double(c.z)}});
            const auto v = eval_complex_double(*sub);
            std::printf("→ 实部 %#.17g 虚部 %#.17g  [支持]\n", v.real(), v.imag());
            ++ok;
        } catch (const std::exception& ex) {
            std::printf("→ [不支持] %s\n", ex.what());
            ++bad;
        }
    }
    std::printf("\n支持 %d 项，不支持 %d 项\n", ok, bad);
    return 0;
}
