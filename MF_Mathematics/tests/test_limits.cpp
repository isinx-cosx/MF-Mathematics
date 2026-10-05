// test_limits.cpp — 极限契约测试（并入新实现前先铺的安全网）
//
// 背景：此前 C++ 测试里**没有任何 limit 断言**，所以极限行为改动无回归可依。
// 本套件把两件事钉住：
//   ① 确定形式必须直接给出正确值（旧实现曾把 1/x@∞ 算成 ∞、x/e^x@∞ 直接报错）
//   ② 不定式必须给对，或者**如实报"解不出"**——绝不能给一个看着像结果的错值
//
// 期望值全部来自数学事实，不来自"当前实现输出什么"。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <string>
#include <vector>

#include "api.h"
#include "json.hpp"
#include "calculus/limits.h"

namespace calc = mf::calculus;

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

static bool near(double a, double b, double tol = 1e-9) { return std::abs(a - b) <= tol * (std::max)(1.0, std::abs(b)); }

const double kInf = std::numeric_limits<double>::infinity();

/** 求极限；抛异常（= 该实现拒绝作答）时返回 NaN 并把原因写入 why。 */
static double lim(const std::string& expr, double point, const std::string& dir,
                  std::string* why = nullptr) {
    try {
        return calc::limit(expr, "x", point, dir);
    } catch (const std::exception& e) {
        if (why) *why = e.what();
        return std::numeric_limits<double>::quiet_NaN();
    }
}

/** 期望"有确定值" */
static void expect(const std::string& expr, double point, const std::string& dir, double want,
                   const char* msg) {
    const double got = lim(expr, point, dir);
    char buf[256];
    std::snprintf(buf, sizeof(buf), "%s（期望 %.6g，实得 %.6g）", msg, want, got);
    CHECK(std::isfinite(want) ? near(got, want, 1e-6) : got == want, buf);
}

/** 期望"如实拒绝"（不定式暂未实现 / 极限不存在）——重点是**不能给错值** */
static void expect_refuse(const std::string& expr, double point, const std::string& dir,
                          const char* msg) {
    std::string why;
    const double got = lim(expr, point, dir, &why);
    char buf[320];
    std::snprintf(buf, sizeof(buf), "%s（应拒绝，实得 %.6g，原因：%s）", msg, got, why.c_str());
    CHECK(std::isnan(got), buf);
    if (!std::isnan(got)) return;
    // 理由必须说人话，不能是空串或纯机器码
    CHECK(!why.empty() && why.find("Unknown token") == std::string::npos, "拒绝理由应可读");
}

// ── ① 确定形式：直接代入 ────────────────────────────────────────────────────
static void test_determinate() {
    expect("x^2", 2.0, "+", 4.0, "多项式在有限点");
    expect("sin(x)", 0.0, "+", 0.0, "三角在有限点");
    expect("(x^2-1)/(x-1)", 3.0, "+", 4.0, "有限/有限");
    expect("2/oo", kInf, "+", 0.0, "常数/∞（表达式内含 ∞ 字面量）");
    expect("exp(-x)", kInf, "+", 0.0, "指数衰减到 0");
    expect("x^2", kInf, "+", kInf, "幂发散（形式确定）");
    // 有界超越函数在 ∞：教科书事实（本批新增）。原先这三类都判成「函数在 ∞」不定式，
    // 而 ∞ 归约把 x 换成 1/t 后又回到同一句分类 → 连 lim atan(x) 都解不出，
    // 直接后果是 y=atan(x) 这类函数的水平渐近线全丢。
    expect("atan(x)", kInf, "+", std::acos(-1.0) / 2, "atan(x) → π/2（本批新增）");
    expect("atan(x)", -kInf, "-", -std::acos(-1.0) / 2, "atan(x) → −π/2（本批新增）");
    expect("tanh(x)", kInf, "+", 1.0, "tanh(x) → 1（本批新增）");
    expect("erf(x)", kInf, "+", 1.0, "erf(x) → 1（本批新增）");
    expect("exp(x)", kInf, "+", kInf, "指数发散（形式确定）");
    expect("log(x)", 0.0, "+", -kInf, "ln 在 0⁺ → −∞（确定）");
    expect("1/x", kInf, "+", 0.0, "有限/∞ → 0（旧实现给 ∞，属确定形式却算错）");
    expect("1/x^2", 0.0, "+", kInf, "0 处负偶次幂 → +∞（两侧同号）");
    expect("1/x", 0.0, "-", -kInf, "左极限 → −∞");
    expect("1/x^2", 0.0, "-", kInf, "双侧同号");

    // 方向词表：界面默认给的是 "right"/"left"（engineMapExtra.js 的 VAR_SPECS），
    // limits.h 的约定是 "+"/"-"，两套都必须认 —— 原实现只判 "-"，
    // 于是 "left" 被当成右极限（一个一直没人发现的老 bug）。
    expect("1/x", 0.0, "right", kInf, "direction=\"right\" → 右极限 +∞");
    expect("1/x", 0.0, "left", -kInf, "direction=\"left\" → 左极限 −∞");
    expect("1/x", 0.0, "+", kInf, "direction=\"+\" → 右极限");
    expect("1/x", 0.0, "-", -kInf, "direction=\"-\" → 左极限");
}

// ── ② 0/0、∞/∞：洛必达 ────────────────────────────────────────────────────
static void test_lhopital() {
    expect("sin(x)/x", 0.0, "+", 1.0, "经典 0/0");
    expect("(x^2-4)/(x-2)", 2.0, "+", 4.0, "可去间断点");
    expect("(1-cos(x))/x^2", 0.0, "+", 0.5, "0/0（两轮洛必达）");
    expect("log(1+x)/x", 0.0, "+", 1.0, "0/0");
    expect("(exp(x)-1)/x", 0.0, "+", 1.0, "0/0");
    expect("(2*x+1)/(x-1)", kInf, "+", 2.0, "∞/∞ 同阶 → 系数比（旧实现报错）");
    expect("(x^3+1)/(2*x^3-x)", kInf, "+", 0.5, "∞/∞ 同阶");
    expect("x/exp(x)", kInf, "+", 0.0, "∞/∞，指数压制幂（旧实现报错）");
    expect("log(x)/x", kInf, "+", 0.0, "∞/∞，对数慢于幂（旧实现报错）");
    expect("x^2/exp(x)", kInf, "+", 0.0, "同上");
}

// ── ③ ∞−∞、1^∞、0^0、0·∞ ──────────────────────────────────────────────────
static void test_indeterminate_forms() {
    expect("sqrt(x^2+x)-x", kInf, "+", 0.5, "∞−∞：共轭有理化（旧实现报错）");
    expect("x-log(x)", kInf, "+", kInf, "∞−∞：幂主导对数 → +∞");
    expect("x^2-x", kInf, "+", kInf, "∞−∞：同族但阶不同 → +∞");
    expect("(1+1/x)^x", kInf, "+", 2.718281828459045, "1^∞ → e（旧实现报错）");
    expect("(1+2/x)^(3*x)", kInf, "+", 403.4287934927351, "1^∞ 变体 → e^6");
    expect("(1+x)^(1/x)", 0.0, "+", 2.718281828459045, "1^∞ 在有限点 → e");
    expect("x^x", 0.0, "+", 1.0, "0^0 → 1");
    expect("x*log(x)", 0.0, "+", 0.0, "0·∞：x^p 压制 log → 0");
    expect("x^(1/log(x))", kInf, "+", 2.718281828459045, "∞^0 → e");
}

// ── ④ 诚实边界：解不出就说解不出，绝不给假值 ────────────────────────────────
static void test_honesty() {
    expect_refuse("sin(1/x)", 0.0, "+", "振荡无极限");
    expect_refuse("(-1)^x", kInf, "+", "无定义/振荡");
    expect_refuse("1/x", 0.0, "", "双侧不等（左 −∞、右 +∞）→ 不存在");
    expect_refuse("tan(x)", 1.5707963267948966, "+", "三角极点（旧实现给 1.6e16 这种假有限值）");
}

// ── ⑤ 经 JSON 分发层（UI 实际走的路）──────────────────────────────────────
static std::string call(const std::string& fn, const std::string& args) {
    std::vector<char> buf(1 << 16);
    const int n = math_call(fn.c_str(), args.c_str(), buf.data(), static_cast<int>(buf.size()));
    if (n < 0) return "{\"isError\":true,\"value\":\"call failed\"}";
    return std::string(buf.data(), static_cast<size_t>(n));
}

static void test_dispatch() {
    const std::string r1 = call("limit", "{\"expr\":\"1/x\",\"var\":\"x\",\"point\":\"oo\"}");
    CHECK(r1.find("\"isError\":false") != std::string::npos && r1.find("\"value\":0") != std::string::npos,
          "math_call limit(1/x, x→∞) → 0");
    const std::string r2 = call("limit", "{\"expr\":\"(2*x+1)/(x-1)\",\"var\":\"x\",\"point\":\"oo\"}");
    CHECK(r2.find("\"value\":2") != std::string::npos, "math_call limit((2x+1)/(x−1), x→∞) → 2");
    const std::string r3 = call("limit", "{\"expr\":\"sin(x)/x\",\"var\":\"x\",\"point\":0}");
    CHECK(r3.find("\"value\":1") != std::string::npos, "math_call limit(sin x/x, x→0) → 1");
    const std::string r4 = call("limit", "{\"expr\":\"sin(1/x)\",\"var\":\"x\",\"point\":0}");
    CHECK(r4.find("\"isError\":true") != std::string::npos, "math_call limit(sin(1/x), x→0) 应报错而不是给数");
}

int main() {
    std::system("chcp 65001 > nul");
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("===== 极限契约测试 =====\n");
    std::printf("-- 确定形式（直接代入）--\n");
    test_determinate();
    std::printf("-- 0/0、∞/∞（洛必达）--\n");
    test_lhopital();
    std::printf("-- 其它不定式 --\n");
    test_indeterminate_forms();
    std::printf("-- 诚实边界 --\n");
    test_honesty();
    std::printf("-- JSON 分发层 --\n");
    test_dispatch();

    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
