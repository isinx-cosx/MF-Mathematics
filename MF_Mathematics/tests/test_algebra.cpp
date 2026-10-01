// test_algebra.cpp — algebra 包(combinatorics + number_theory)内核 + JSON 测试。
//
// 期望值取自 Python 版各模块 self_test() 的断言。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <limits>
#include <string>
#include <vector>

#include "api.h"
#include "algebra/analytic_geometry.h"
#include "algebra/combinatorics.h"
#include "algebra/equation.h"
#include "algebra/function.h"
#include "algebra/number_theory.h"
#include "algebra/expression.h"
#include "algebra/inequality.h"
#include "algebra/sequences.h"

namespace alg = mf::algebra;

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

// ── 内核层:combinatorics ────────────────────────────────────────────────────

static void test_combinatorics() {
    CHECK_EQ(alg::addition_principle({3, 5, 2}), 10LL, "加法原理 3+5+2=10");
    CHECK_EQ(alg::multiplication_principle({3, 4, 2}), 24LL, "乘法原理 3×4×2=24");
    CHECK_EQ(alg::permutation(5, 3), 60LL, "A(5,3)=60");
    CHECK_EQ(alg::combination(5, 2), 10LL, "C(5,2)=10");
    CHECK_EQ(alg::combination(10, 3), 120LL, "C(10,3)=120");
    CHECK_EQ(alg::combination(0, 0), 1LL, "C(0,0)=1");

    CHECK(alg::comb_identities().size() == 8, "组合恒等式 8 条");

    CHECK(alg::binomial_expand("x", "y", 3) == "x^3 + 3·x^2·y + 3·x·y^2 + y^3",
          "(x+y)^3 展开");
    CHECK(alg::binomial_expand("x", "y", 2) == "x^2 + 2·x·y + y^2",
          "(x+y)^2 展开");

    const alg::BinomialTerm bt = alg::binomial_term("x", "y", 5, 2);
    CHECK_EQ(bt.coefficient, 10LL, "通项系数 C(5,2)=10");
    CHECK(bt.term == "10·x^3·y^2", "通项表达式 10·x^3·y^2");
    CHECK_EQ(bt.term_number, 3LL, "第 3 项");

    // 溢出防护
    bool threw = false;
    try {
        alg::permutation(100, 100);
    } catch (const std::exception&) {
        threw = true;
    }
    CHECK(threw, "permutation(100,100) 溢出 → 抛异常");
}

// ── 内核层:number_theory(数与运算)───────────────────────────────────────────

static void test_number_theory() {
    CHECK(alg::commutative_law(3, 5, "+").holds, "交换律 3+5");
    CHECK(alg::commutative_law(3, 5, "*").holds, "交换律 3×5");
    CHECK(alg::associative_law(2, 3, 4, "+").holds, "结合律 (2+3)+4");
    CHECK(alg::distributive_law(2, 3, 4).holds, "分配律 2×(3+4)");

    CHECK_EQ(alg::abs_value(-5), 5.0, "|−5|=5");
    CHECK_EQ(alg::distance_on_number_line(3, 8), 5.0, "|3−8|=5");

    CHECK(alg::ratio(3, 5).num == 3 && alg::ratio(3, 5).den == 5, "3:5=3:5");
    CHECK(alg::ratio(4, 6).num == 2 && alg::ratio(4, 6).den == 3, "4:6=2:3");
    CHECK(alg::ratio(0.5, 2).num == 1 && alg::ratio(0.5, 2).den == 4,
          "0.5:2=1:4");

    CHECK(near(alg::percentage(25, 200), 12.5, 1e-9), "25/200=12.5%");
    CHECK(near(alg::percentage_change(100, 120), 20.0, 1e-9), "100→120 +20%");

    const alg::ScientificNotation sn = alg::to_scientific_notation(12345);
    CHECK(near(sn.coefficient, 1.2345, 1e-9) && sn.exponent == 4,
          "12345 = 1.2345×10^4");
    CHECK(near(alg::significant_figures(3.14159, 3), 3.14, 1e-9),
          "3.14159 保留 3 位有效数字 = 3.14");
}

// ── 内核层:analytic_geometry ────────────────────────────────────────────────

static void test_analytic_geometry() {
    CHECK(near(alg::distance({0, 0}, {3, 4}), 5.0, 1e-9), "distance(0,0)-(3,4) == 5");
    const alg::Point mp = alg::midpoint({0, 0}, {4, 6});
    CHECK(near(mp.x, 2.0, 1e-9) && near(mp.y, 3.0, 1e-9), "midpoint == (2,3)");

    const alg::LineFromPoints lfp = alg::line_from_points({0, 0}, {1, 1});
    CHECK(near(lfp.slope, 1.0, 1e-9), "line_from_points slope == 1");
    const alg::LineFromPoints vert = alg::line_from_points({2, 0}, {2, 5});
    CHECK(vert.slope == std::numeric_limits<double>::infinity(),
          "垂直直线 slope == inf");

    const alg::LineSlopeIntercept lsi = alg::line_from_slope_intercept(2, 3);
    CHECK(lsi.slope_intercept == "y = 2.0x + 3.0", "斜截式 y = 2.0x + 3.0");
    CHECK(near(lsi.points[0].y, 3.0, 1e-9) && near(lsi.points[1].y, 5.0, 1e-9),
          "斜截式过 (0,3) 与 (1,5)");

    const alg::CircleStandard cs = alg::circle_standard({0, 0}, 5);
    CHECK(near(cs.radius, 5.0, 1e-9), "circle_standard r == 5");
    CHECK(near(cs.diameter, 10.0, 1e-9), "circle_standard 直径 10");
    CHECK(near(cs.area, 25.0 * 3.141592653589793, 1e-6), "circle_standard 面积 25π");

    const alg::CircleGeneral cg = alg::circle_general(-4, -6, 4);
    CHECK(!cg.is_imaginary, "circle_general 实圆");
    CHECK(near(cg.center.x, 2.0, 1e-9) && near(cg.center.y, 3.0, 1e-9),
          "circle_general 圆心 (2,3)");
    CHECK(near(cg.radius, 3.0, 1e-9), "circle_general r == 3");
    CHECK(alg::circle_general(0, 0, 1).is_imaginary, "circle_general r²<0 虚圆");

    const alg::LineGeneral lg = alg::line_general(1, 0, -2);
    CHECK(lg.slope == std::numeric_limits<double>::infinity(),
          "line_general B=0 垂直");
}

// ── 内核层:equation ──────────────────────────────────────────────────────────

static bool vec_contains(const std::vector<std::string>& v, const std::string& s) {
    for (const std::string& e : v)
        if (e == s) return true;
    return false;
}

static void test_equation() {
    // solve_linear
    CHECK_EQ(alg::solve_linear("2*x + 3 = 7", "x"), std::string("2"),
             "solve_linear 2x+3=7 → x=2");
    CHECK_EQ(alg::solve_linear("x + 1 = x", "x"), std::string("无解"),
             "solve_linear x+1=x → 无解");
    CHECK_EQ(alg::solve_linear("3*x = 9", "x"), std::string("3"),
             "solve_linear 3x=9 → x=3");

    // solve_linear_system
    const alg::LinearSystemResult sys =
        alg::solve_linear_system("x + y = 2", "x - y = 0", "x", "y");
    CHECK(sys.solvable && sys.x == "1" && sys.y == "1",
          "二元方程组 x+y=2, x-y=0 → x=1, y=1");
    CHECK(!alg::solve_linear_system("x + y = 1", "x + y = 2", "x", "y").solvable,
          "矛盾方程组 → 无解");

    // solve_quadratic
    const std::vector<std::string> rq = alg::solve_quadratic("x^2 - 4", "x");
    CHECK(vec_contains(rq, "2") && vec_contains(rq, "-2"), "solve_quadratic x²-4 → {2,-2}");
    CHECK(vec_contains(alg::solve_quadratic("x^2 - 5*x + 6", "x"), "3"),
          "solve_quadratic x²-5x+6 含 3");

    // discriminant
    const alg::DiscriminantResult d1 = alg::discriminant("x^2 - 4*x + 4", "x");
    CHECK(d1.delta == 0.0 && d1.nature == "有两个相等实根(重根)", "Δ(x²-4x+4)=0 重根");
    CHECK_EQ(alg::discriminant("x^2 - 4", "x").delta, 16.0, "Δ(x²-4)=16");
    CHECK_EQ(alg::discriminant("x^2 + 1", "x").nature, std::string("有一对共轭虚根"),
             "Δ(x²+1)<0 共轭虚根");
    bool threw = false;
    try {
        alg::discriminant("x + 1", "x");
    } catch (const std::exception&) {
        threw = true;
    }
    CHECK(threw, "discriminant 非二次式 → 抛异常");

    // vieta_theorem
    const alg::VietaResult vt = alg::vieta_theorem("x^2 - 5*x + 6", "x");
    CHECK(near(vt.sum_of_roots, 5.0, 1e-9) && near(vt.product_of_roots, 6.0, 1e-9),
          "韦达定理 x²-5x+6 → 和5 积6");

    // solve_fractional
    const alg::FractionalResult frac = alg::solve_fractional("1/x = 2", "x");
    CHECK(vec_contains(frac.valid, "1/2") && frac.extraneous.empty(),
          "分式方程 1/x=2 → 有效解 1/2");

    // solve_irrational
    const alg::FractionalResult irr = alg::solve_irrational("sqrt(x) = 2", "x");
    CHECK(vec_contains(irr.valid, "4"), "无理方程 sqrt(x)=2 → x=4");
    const alg::FractionalResult irr2 =
        alg::solve_irrational("sqrt(x+1) = x - 1", "x");
    CHECK(vec_contains(irr2.valid, "3"), "无理方程 sqrt(x+1)=x-1 → x=3");
}

// ── 内核层:function ──────────────────────────────────────────────────────────

static void test_function() {
    // domain
    CHECK_EQ(alg::domain("1/(x-2)", "x"), std::string("x ≠ 2"),
             "domain(1/(x-2)) → x ≠ 2");
    CHECK(alg::domain("sqrt(x-1)", "x").find("x ≥ 1") != std::string::npos,
          "domain(sqrt(x-1)) 含 x ≥ 1");
    CHECK_EQ(alg::domain("x^2 + 1", "x"), std::string("x ∈ R (全体实数)"),
             "domain(x²+1) → R");

    // correspondence_rule
    CHECK_EQ(alg::correspondence_rule("x^2 - 5*x + 6"), std::string("多项式函数"),
             "x²-5x+6 是多项式函数");
    CHECK_EQ(alg::correspondence_rule("1/x"), std::string("有理函数"),
             "1/x 是有理函数");
    CHECK_EQ(alg::correspondence_rule("sqrt(x-1)"), std::string("含根式函数"),
             "sqrt(x-1) 含根式");

    // 一次/反比例
    CHECK_EQ(alg::linear_function(2, 3), std::string("y = 2*x + 3"),
             "linear_function(2,3)");
    CHECK_EQ(alg::linear_function(1, 0), std::string("y = x"),
             "linear_function(1,0)");
    CHECK_EQ(alg::inverse_proportional(5), std::string("y = 5/x"),
             "inverse_proportional(5)");
    const alg::SlopeInterceptResult si = alg::slope_intercept(1, 0);
    CHECK(near(si.angle_degrees, 45.0, 0.01), "slope_intercept 倾斜角 45°");

    // 二次函数
    const alg::QuadraticResult qf = alg::quadratic_function(1, -4, 3);
    CHECK(near(qf.vertex_x, 2.0, 1e-9) && near(qf.vertex_y, -1.0, 1e-9),
          "二次函数顶点 (2,-1)");
    CHECK_EQ(qf.direction, std::string("向上"), "二次函数开口向上");
    const alg::ExtremaResult ex = alg::quadratic_extrema(1, -4, 3);
    CHECK(ex.type == "最小值" && near(ex.x, 2.0, 1e-9) && near(ex.value, -1.0, 1e-9),
          "二次函数最值 -1");
    CHECK_EQ(alg::quadratic_extrema(-1, 0, 0).type, std::string("最大值"),
             "开口向下 → 最大值");

    // 幂/指数/对数
    CHECK(alg::power_function("x", 2).expr == "x^2", "power_function(x,2) → x^2");
    const alg::PowerResult pw = alg::power_function("2", 3);
    CHECK(pw.numeric && near(pw.value, 8.0, 1e-9), "power_function(2,3) → 8");
    CHECK(near(alg::exponential_function(2, 3), 8.0, 1e-9), "2³ = 8");
    CHECK(near(alg::log_function(2, 8), 3.0, 1e-9), "log₂8 = 3");

    // 三角
    CHECK(near(alg::sine_cosine_tangent(30, "degrees").sin_val, 0.5, 1e-6),
          "sin 30° = 0.5");
    CHECK(alg::trig_basic_identities().size() == 14, "三角诱导公式 14 条");
    CHECK_EQ(alg::trig_periodicity("sin").period, std::string("2π"),
             "sin 周期 2π");
    CHECK_EQ(alg::trig_periodicity("tan").period, std::string("π"),
             "tan 周期 π");
    bool threw = false;
    try {
        alg::trig_periodicity("cot");
    } catch (const std::exception&) {
        threw = true;
    }
    CHECK(threw, "trig_periodicity 不支持 cot → 抛异常");
}

// ── 分发层测试(JSON + C ABI)────────────────────────────────────────────────

static std::string call(const char* name, const char* args) {
    char buf[4096];
    const int n = math_call(name, args, buf, sizeof(buf));
    if (n < 0) return "<math_call 失败>";
    return std::string(buf, buf + n);
}

static void test_dispatch() {
    CHECK(function_exists("combination"), "function_exists(combination)");
    CHECK(function_exists("binomial_expand"), "function_exists(binomial_expand)");

    CHECK(call("addition_principle", "{\"ways\":[3,5,2]}") ==
              "{\"isError\":false,\"value\":10}",
          "math_call addition_principle == 10");
    CHECK(call("permutation", "{\"n\":5,\"m\":3}") ==
              "{\"isError\":false,\"value\":60}",
          "math_call permutation(5,3) == 60");
    CHECK(call("combination", "{\"n\":5,\"m\":2}") ==
              "{\"isError\":false,\"value\":10}",
          "math_call combination(5,2) == 10");
    CHECK(call("binomial_expand", "{\"a\":\"x\",\"b\":\"y\",\"n\":3}") ==
              "{\"isError\":false,\"value\":\"x^3 + 3·x^2·y + 3·x·y^2 + y^3\"}",
          "math_call binomial_expand((x+y)^3)");
    CHECK(call("ratio", "{\"a\":0.5,\"b\":2}") ==
              "{\"isError\":false,\"value\":[1,4]}",
          "math_call ratio(0.5,2) == [1,4]");
    CHECK(call("to_scientific_notation", "{\"x\":12345}") ==
              "{\"isError\":false,\"value\":[1.2345,4]}",
          "math_call to_scientific_notation(12345)");
    CHECK(call("commutative_law", "{\"a\":3,\"b\":5,\"op\":\"+\"}") ==
              "{\"isError\":false,\"value\":{\"holds\":true,\"left\":8,\"right\":8}}",
          "math_call commutative_law(3,5,+)");
    CHECK(call("percentage", "{\"part\":25,\"total\":200}") ==
              "{\"isError\":false,\"value\":12.5}",
          "math_call percentage(25,200) == 12.5");
    CHECK(call("abs_value", "{\"x\":-5}") ==
              "{\"isError\":false,\"value\":5}",
          "math_call abs_value(-5) == 5");

    // 几何
    CHECK(call("distance", "{\"p1\":[0,0],\"p2\":[3,4]}") ==
              "{\"isError\":false,\"value\":5}",
          "math_call distance(0,0)-(3,4) == 5");
    CHECK(call("midpoint", "{\"p1\":[0,0],\"p2\":[4,6]}") ==
              "{\"isError\":false,\"value\":[2,3]}",
          "math_call midpoint == [2,3]");
    CHECK(call("line_from_slope_intercept", "{\"k\":2,\"b\":3}") ==
              "{\"isError\":false,\"value\":{\"general\":\"2.0x - y + 3.0 = 0\","
              "\"points\":[[0,3],[1,5]],\"slope\":2,"
              "\"slope_intercept\":\"y = 2.0x + 3.0\",\"y_intercept\":3}}",
          "math_call line_from_slope_intercept(2,3)");
    const std::string circle = call("circle_standard", "{\"center\":[0,0],\"r\":5}");
    CHECK(circle.find("\"isError\":false") != std::string::npos &&
              circle.find("\"radius\":5") != std::string::npos,
          "math_call circle_standard r=5");
    CHECK(call("circle_general", "{\"D\":-4,\"E\":-6,\"F\":4}").find("\"radius\":3") !=
              std::string::npos,
          "math_call circle_general(-4,-6,4) r=3");
    CHECK(call("circle_general", "{\"D\":0,\"E\":0,\"F\":1}") ==
              "{\"isError\":false,\"value\":\"表示一个虚圆（半径的平方为负数，无实数解）\"}",
          "math_call circle_general 虚圆");

    // 错误路径
    const std::string bad = call("ratio", "{\"a\":1,\"b\":0}");
    CHECK(bad.find("\"isError\":true") != std::string::npos, "ratio 分母为 0 → isError");
    const std::string overflow = call("permutation", "{\"n\":100,\"m\":100}");
    CHECK(overflow.find("\"isError\":true") != std::string::npos,
          "permutation 溢出 → isError");

    // ── equation ───────────────────────────────────────────────────────────
    CHECK(function_exists("solve_linear"), "function_exists(solve_linear)");
    CHECK(function_exists("solve_quadratic"), "function_exists(solve_quadratic)");
    CHECK(call("solve_linear", "{\"expr\":\"2*x + 3 = 7\",\"var\":\"x\"}") ==
              "{\"isError\":false,\"value\":\"2\"}",
          "math_call solve_linear(2x+3=7) → 2");
    CHECK(call("alg_solve_linear_system",
               "{\"eq1\":\"x + y = 2\",\"eq2\":\"x - y = 0\"}") ==
              "{\"isError\":false,\"value\":{\"x\":\"1\",\"y\":\"1\"}}",
          "math_call alg_solve_linear_system → {x:1,y:1}");
    const std::string quad =
        call("solve_quadratic", "{\"expr\":\"x^2 - 4\",\"var\":\"x\"}");
    CHECK(quad.find("\"2\"") != std::string::npos && quad.find("\"-2\"") != std::string::npos,
          "math_call solve_quadratic(x²-4) → [2,-2]");
    const std::string disc =
        call("discriminant", "{\"expr\":\"x^2 - 4*x + 4\",\"var\":\"x\"}");
    CHECK(disc.find("\"delta\":0") != std::string::npos, "math_call discriminant Δ=0");
    const std::string vieta =
        call("vieta_theorem", "{\"expr\":\"x^2 - 5*x + 6\",\"var\":\"x\"}");
    CHECK(vieta.find("\"sum_of_roots\":5") != std::string::npos &&
              vieta.find("\"product_of_roots\":6") != std::string::npos,
          "math_call vieta_theorem");
    const std::string frac =
        call("solve_fractional", "{\"expr\":\"1/x = 2\",\"var\":\"x\"}");
    CHECK(frac.find("\"valid_solutions\":[\"1/2\"]") != std::string::npos,
          "math_call solve_fractional(1/x=2)");
    const std::string irr =
        call("solve_irrational", "{\"expr\":\"sqrt(x) = 2\",\"var\":\"x\"}");
    CHECK(irr.find("\"valid_solutions\":[\"4\"]") != std::string::npos,
          "math_call solve_irrational(sqrt(x)=2) → 4");
    CHECK(call("discriminant", "{\"expr\":\"x + 1\",\"var\":\"x\"}").find(
              "\"isError\":true") != std::string::npos,
          "math_call discriminant 非二次 → isError");

    // ── function ───────────────────────────────────────────────────────────
    CHECK(function_exists("domain"), "function_exists(domain)");
    CHECK(function_exists("sine_cosine_tangent"),
          "function_exists(sine_cosine_tangent)");
    CHECK(call("domain", "{\"expr\":\"1/(x-2)\",\"var\":\"x\"}") ==
              "{\"isError\":false,\"value\":\"x ≠ 2\"}",
          "math_call domain(1/(x-2)) → x ≠ 2");
    CHECK(call("linear_function", "{\"k\":2,\"b\":3}") ==
              "{\"isError\":false,\"value\":\"y = 2*x + 3\"}",
          "math_call linear_function(2,3)");
    const std::string qf = call("quadratic_function", "{\"a\":1,\"b\":-4,\"c\":3}");
    CHECK(qf.find("\"vertex\":[2,-1]") != std::string::npos &&
              qf.find("\"direction\":\"向上\"") != std::string::npos,
          "math_call quadratic_function(1,-4,3)");
    CHECK(call("power_function", "{\"x\":\"2\",\"n\":3}") ==
              "{\"isError\":false,\"value\":8}",
          "math_call power_function(2,3) → 8");
    CHECK(call("power_function", "{\"x\":\"x\",\"n\":2}") ==
              "{\"isError\":false,\"value\":\"x^2\"}",
          "math_call power_function(x,2) → x^2");
    CHECK(call("log_function", "{\"base\":2,\"x\":8}") ==
              "{\"isError\":false,\"value\":3}",
          "math_call log_function(2,8) → 3");
    const std::string trig =
        call("sine_cosine_tangent", "{\"angle\":30,\"mode\":\"degrees\"}");
    CHECK(trig.find("\"sin\":0.5") != std::string::npos,
          "math_call sine_cosine_tangent(30°) sin=0.5");
    const std::string period = call("trig_periodicity", "{\"func\":\"sin\"}");
    CHECK(period.find("\"period\":\"2π\"") != std::string::npos,
          "math_call trig_periodicity(sin) → 2π");
}

// ── expression / inequality / sequences ──────────────────────────────────────

static void test_expression() {
    const std::string sp = alg::simplify_polynomial("x**2 + 2*x + 1");
    CHECK(sp.find("(x + 1)") != std::string::npos ||
              sp.find("x**2 + 2*x + 1") != std::string::npos,
          "化简 x²+2x+1");

    CHECK(alg::expand_expression("(x+1)*(x+2)").find("x**2") != std::string::npos,
          "展开 (x+1)(x+2) 含 x²");

    CHECK(alg::factor("x**2 - 1").find("(x - 1)") != std::string::npos,
          "分解 x²-1 = (x-1)(x+1)");
    CHECK(alg::factor_difference_squares("x**2 - 4").find("x") != std::string::npos,
          "平方差分解 x²-4");
    CHECK(alg::factor_perfect_square("x**2 + 2*x + 1").find("(x + 1)") !=
              std::string::npos,
          "完全平方分解");

    CHECK(alg::simplify_radical("sqrt(8)").find("2") != std::string::npos,
          "化简 sqrt(8) 含 2");

    const alg::LikeRadicalsResult lr = alg::like_radicals("sqrt(2)", "2*sqrt(2)");
    CHECK(lr.is_like, "sqrt(2) 与 2sqrt(2) 同类");

    CHECK(alg::radical_operations("sqrt(2)", "*", "sqrt(8)").find("4") !=
              std::string::npos,
          "sqrt(2)*sqrt(8) = 4");
}

static void test_inequality() {
    const auto props = alg::inequality_properties(2, 5, -3);
    CHECK(props.size() >= 4, "不等式性质演示 ≥4 条");

    CHECK(alg::solve_linear_inequality("2*x - 3 > 0").find("1.5") != std::string::npos,
          "2x-3>0 → x>1.5");

    CHECK(alg::solve_inequality_system({"x > 1", "x < 5"}).find("1") !=
              std::string::npos,
          "不等式组 (1,5)");

    CHECK(alg::solve_quadratic_inequality("x**2 - 4 > 0").find("2") !=
              std::string::npos,
          "x²-4>0 → 两侧");

    const alg::AmGmResult ag = alg::am_gm_inequality(4, 9);
    CHECK(near(ag.AM, 6.5, 1e-9) && near(ag.GM, 6.0, 1e-9), "AM=6.5, GM=6");
}

static void test_sequences() {
    CHECK(near(alg::sequence_term("n**2", 5), 25.0, 1e-12), "a_5 = 25 for n²");

    const auto ar = alg::arithmetic_sequence(1, 2, 5);
    CHECK(ar.size() == 5 && near(ar[0], 1.0, 1e-12) && near(ar[4], 9.0, 1e-12),
          "等差 [1,3,5,7,9]");
    CHECK(near(alg::arithmetic_sum(1, 2, 5), 25.0, 1e-12), "等差和 25");

    const auto ge = alg::geometric_sequence(2, 3, 4);
    CHECK(ge.size() == 4 && near(ge[0], 2.0, 1e-12) && near(ge[3], 54.0, 1e-12),
          "等比 [2,6,18,54]");
    CHECK(alg::geometric_sum(2, 3, 4) > 0, "等比和 > 0");

    const auto fib = alg::recurrence_sequence({1, 1}, "a[-1] + a[-2]", 10);
    CHECK(fib.size() == 10 && near(fib[0], 1.0, 1e-12) && near(fib[2], 2.0, 1e-12) &&
              near(fib[5], 8.0, 1e-12),
          "Fibonacci 递推 [1,1,2,3,5,8]");
}

int main() {
    std::system("chcp 65001 > nul");
    std::printf("===== algebra 内核测试 =====\n");
    test_combinatorics();
    test_number_theory();
    test_analytic_geometry();
    test_equation();
    test_function();
    test_expression();
    test_inequality();
    test_sequences();
    std::printf("===== 分发层测试(JSON) =====\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
