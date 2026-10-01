// SymEngine 0.14.0 验证 demo
// 编译: cmake -B build -DCMAKE_TOOLCHAIN_FILE=$env:USERPROFILE\vcpkg\scripts\buildsystems\vcpkg.cmake
//       cmake --build build --config Release
#include <iostream>

#include <symengine/constants.h>
#include <symengine/derivative.h>
#include <symengine/eval_double.h>
#include <symengine/expression.h>
#include <symengine/functions.h>
#include <symengine/pow.h>
#include <symengine/series.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>

using namespace SymEngine;

int main()
{
    auto x = symbol("x");

    // ===== 1. 构造表达式（RCP 风格，SymEngine 原生） =====
    auto expr = add(mul(sin(x), cos(x)), pow(x, integer(2)));
    std::cout << "expr            = " << *expr << "\n";

    // ===== 2. 符号求导 =====
    auto d = diff(expr, x);
    std::cout << "diff(expr,x)    = " << *d << "\n";

    // ===== 3. 展开 / 化简 =====
    auto e2 = expand(pow(add(x, integer(1)), integer(3)));
    std::cout << "expand((x+1)^3) = " << *e2 << "\n";
    auto e3 = simplify(
        div(add(pow(x, integer(2)), mul(integer(2), x)), add(x, integer(2))));
    std::cout << "simplify        = " << *e3 << "\n";

    // ===== 4. 代入 + 数值求值 =====
    map_basic_basic m;
    m[x] = integer(2);
    auto ev = expr->subs(m);
    std::cout << "subs(x=2)       = " << *ev << "  ≈ " << eval_double(*ev) << "\n";

    // ===== 5. 幂级数展开 =====
    auto s = series(sin(x), x, 8);
    std::cout << "series(sin x)   = " << *s->as_basic() << "\n";

    // ===== 6. 方程求解（返回解集 Set） =====
    auto sol = solve(add(pow(x, integer(2)), integer(-4)), x);
    std::cout << "solve(x^2-4)    = " << *sol << "\n";

    // ===== 7. Expression 风格（更接近 Python 写法） =====
    Expression e = Expression(mul(sin(x), cos(x))) + pow(x, integer(3));
    std::cout << "Expr style      = " << e << "\n";
    std::cout << "Expr diff       = " << e.diff(x) << "\n";

    // ===== 8. 特殊函数 =====
    std::cout << "zeta(2)         = " << *zeta(integer(2)) << "\n";
    std::cout << "gamma(5)        = " << *gamma(integer(5)) << "\n";
    std::cout << "pi^2/6 数值     = " << eval_double(*div(pow(pi, integer(2)), integer(6))) << "\n";

    return 0;
}
