// test_complex_grid.cpp — complex_grid（复网格求值）契约测试
//
// 为什么需要：complex_grid 是复变函数可视化五种模式（相位图 / HSV 域着色 /
// 3D 模长曲面 / 向量场 / 共形映射）**唯一的数据来源**，此前没有任何 C++ 测试，
// 于是契约（索引布局、null 语义、unsupported、点数上限）全靠前端碰运气。
//
// 本套件钉住六件事：
//   ① 初等函数数值正确（参考值来自 C++ 标准库 <complex> 的独立实现与数学事实）
//   ② 引擎自己补的 gamma / zeta / erf / erfc 数值正确
//      —— 其中 zeta(2) 专守刚修好的那个 bug（截断级数 1.644834 → Euler–Maclaurin 1.6449341）
//   ③ 极点 / 域外点给 null 并计入 nan——绝不返回一个看起来正常的错值
//   ④ 行优先索引 index = j*nx + i 与坐标一一对应（j 是 y、i 是 x，y0→y1 递增）
//   ⑤ 算不出来的函数必须报 unsupported，不能被当成数值结果
//   ⑥ 点数上限 400000；nx=1 / ny=1 时该维只取起点值
//
// 期望值全部来自数学事实或独立参考实现，**不来自「当前实现输出什么」**。
// 发现引擎算错一律如实报告（⑦ 节），本文件只测不改。
//
// 用法：test_complex_grid [--strict]
//   默认：引擎侧缺陷记 [KNOWN-BUG] 并在结尾汇总，不计入失败（回归门禁可先绿）；
//   --strict：把 [KNOWN-BUG] 计入失败，用于显式确认「这些缺陷还没修」。

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include "api.h"
#include "json.hpp"

namespace {

using mf::json::Value;
using zc = std::complex<double>;

int g_checks = 0;
int g_failures = 0;
int g_known_bugs = 0;
bool g_strict = false;  // --strict：已知引擎缺陷也计入失败

#define CHECK(cond, msg)                            \
    do {                                            \
        ++g_checks;                                 \
        if (!(cond)) {                              \
            ++g_failures;                           \
            std::printf("[FAIL] %s\n", (msg));      \
        }                                           \
    } while (0)

// 引擎侧已发现的缺陷：默认只记录（不把引擎的错误行为固化成期望值），
// --strict 时计入失败。记录它们是为了**如实报告**，不是为了合上眼睛。
#define CHECK_KNOWN(cond, msg)                      \
    do {                                            \
        ++g_checks;                                 \
        if (!(cond)) {                              \
            ++g_known_bugs;                         \
            std::printf("[KNOWN-BUG] %s\n", (msg)); \
            if (g_strict) ++g_failures;             \
        }                                           \
    } while (0)

const double kNaN = std::numeric_limits<double>::quiet_NaN();
const double kPi = std::acos(-1.0);

/** 相对误差比较：|a−b| ≤ tol·max(1,|b|)。注意 null（域外点）读出来是 NaN，任何数值比较都会失败。 */
bool near(double a, double b, double tol) {
    if (a != a || b != b) return false;
    return std::abs(a - b) <= tol * (std::max)(1.0, std::abs(b));
}

// ── 调用与解析 ──────────────────────────────────────────────────────────────

struct Grid {
    bool is_error = false;
    std::string error;  // isError=true 时的 value（错误文案）
    Value v;            // isError=false 时的 value（结果对象）
    std::string raw;    // 原始 JSON，便于报告里贴证据
};

std::string num(double v) {
    char b[40];
    std::snprintf(b, sizeof(b), "%.17g", v);
    return b;
}

/**
 * 调 complex_grid 并解析返回。
 *   ny < 0      → 不传 ny（走缺省，契约里缺省等于 nx）
 *   digits <= 0 → 不传 digits（走缺省 7 位有效数字）
 *   var != "z"  → 传 var 做变量改名
 */
Grid cgrid(const std::string& expr, double x0, double x1, double y0, double y1,
           long long nx, long long ny = -1, int digits = -1,
           const std::string& var = "z") {
    std::string args = "{\"expr\":\"" + expr + "\"";
    args += ",\"x0\":" + num(x0) + ",\"x1\":" + num(x1);
    args += ",\"y0\":" + num(y0) + ",\"y1\":" + num(y1);
    args += ",\"nx\":" + std::to_string(nx);
    if (ny >= 0) args += ",\"ny\":" + std::to_string(ny);
    if (digits > 0) args += ",\"digits\":" + std::to_string(digits);
    if (var != "z") args += ",\"var\":\"" + var + "\"";
    args += "}";

    Grid g;
    std::vector<char> buf(1 << 20);  // 1 MiB：本套件最大只到 9 个点
    const int n = math_call("complex_grid", args.c_str(), buf.data(),
                            static_cast<int>(buf.size()));
    if (n < 0) {
        g.is_error = true;
        g.error = "math_call 返回 -1（缓冲区不足或参数非法）";
        return g;
    }
    g.raw.assign(buf.data(), static_cast<std::size_t>(n));
    try {
        const Value root = Value::parse(g.raw);
        if (root["isError"].as_bool()) {
            g.is_error = true;
            g.error = root["value"].as_string();
        } else {
            g.v = root["value"];
        }
    } catch (const std::exception& e) {
        g.is_error = true;
        g.error = std::string("返回 JSON 解析失败：") + e.what();
    }
    return g;
}

/** 单点求值（nx=ny=1 是契约里的单点路径） */
Grid point(const std::string& expr, const zc& w, int digits = -1) {
    return cgrid(expr, w.real(), w.real(), w.imag(), w.imag(), 1, 1, digits);
}

// ── 读数与打印 ──────────────────────────────────────────────────────────────

/** re/im 的第 k 个分量；null（域外点）→ NaN */
double comp(const Grid& g, const char* which, std::size_t k) {
    const Value& a = g.v[which];
    return a.at(k).is_null() ? kNaN : a.at(k).as_double();
}
double re_at(const Grid& g, std::size_t k) { return comp(g, "re", k); }
double im_at(const Grid& g, std::size_t k) { return comp(g, "im", k); }

/** 分量文本：null 显示成 null，好与数值 0 区分开 */
std::string cell(const Grid& g, const char* which, std::size_t k) {
    if (g.v[which].at(k).is_null()) return "null";
    char b[40];
    std::snprintf(b, sizeof(b), "%.17g", g.v[which].at(k).as_double());
    return b;
}
std::string rc(const Grid& g, std::size_t k) {
    return "(" + cell(g, "re", k) + ", " + cell(g, "im", k) + ")";
}

std::size_t nulls(const Grid& g, const char* which) {
    const Value& a = g.v[which];
    std::size_t n = 0;
    for (std::size_t i = 0; i < a.size(); ++i)
        if (a.at(i).is_null()) ++n;
    return n;
}

// ── 通用断言 ────────────────────────────────────────────────────────────────

/** 结构检查：字段齐全、re/im 长度 = nx*ny、ok + nan = nx*ny、nx/ny 回显。返回结构是否可用。 */
bool check_shape(const Grid& g, long long nx, long long ny, const char* what) {
    char buf[512];
    if (g.is_error) {
        std::snprintf(buf, sizeof(buf), "%s：调用应成功，实得错误「%s」", what, g.error.c_str());
        CHECK(false, buf);
        return false;
    }
    const char* keys[] = {"re",    "im",   "nx",     "ny",       "ok",     "nan",
                          "x0",    "x1",   "y0",     "y1",       "maxMag", "minMag",
                          "unsupported"};
    bool complete = true;
    for (const char* k : keys)
        if (!g.v.has(k)) complete = false;
    std::snprintf(buf, sizeof(buf), "%s：应含字段 re/im/nx/ny/ok/nan/x0..y1/maxMag/minMag/unsupported（原始返回 %s）",
                  what, g.raw.c_str());
    CHECK(complete, buf);
    if (!complete) return false;

    const long long total = nx * ny;
    std::snprintf(buf, sizeof(buf), "%s：re/im 长度应各为 nx*ny=%lld，实得 %lld / %lld", what,
                  total, static_cast<long long>(g.v["re"].size()),
                  static_cast<long long>(g.v["im"].size()));
    const bool sized = static_cast<long long>(g.v["re"].size()) == total &&
                       static_cast<long long>(g.v["im"].size()) == total;
    CHECK(sized, buf);

    std::snprintf(buf, sizeof(buf), "%s：ok+nan 应等于 nx*ny=%lld，实得 ok=%lld nan=%lld", what,
                  total, static_cast<long long>(g.v["ok"].as_int()),
                  static_cast<long long>(g.v["nan"].as_int()));
    CHECK(static_cast<long long>(g.v["ok"].as_int()) +
              static_cast<long long>(g.v["nan"].as_int()) == total,
          buf);

    std::snprintf(buf, sizeof(buf), "%s：nx/ny 应回显 %lld/%lld，实得 %lld/%lld", what, nx, ny,
                  static_cast<long long>(g.v["nx"].as_int()),
                  static_cast<long long>(g.v["ny"].as_int()));
    CHECK(static_cast<long long>(g.v["nx"].as_int()) == nx &&
              static_cast<long long>(g.v["ny"].as_int()) == ny,
          buf);
    return sized;
}

/** 单点求值：第 0 个分量必须等于 want（复数两个分量都查）。 */
void expect_point(const Grid& g, const zc& want, double tol, const char* msg) {
    char buf[512];
    if (g.is_error) {
        std::snprintf(buf, sizeof(buf), "%s：调用应成功，实得错误「%s」", msg, g.error.c_str());
        CHECK(false, buf);
        return;
    }
    if (g.v["re"].size() == 0 || g.v["im"].size() == 0) {
        std::snprintf(buf, sizeof(buf), "%s：re/im 是空数组（原始返回 %s）", msg, g.raw.c_str());
        CHECK(false, buf);
        return;
    }
    std::snprintf(buf, sizeof(buf), "%s：期望 (%.17g, %.17g)，实得 %s", msg, want.real(),
                  want.imag(), rc(g, 0).c_str());
    std::printf("[值] %s：实得 %s，参考 %.17g%+.17gi\n", msg, rc(g, 0).c_str(), want.real(),
                want.imag());
    CHECK(near(re_at(g, 0), want.real(), tol) && near(im_at(g, 0), want.imag(), tol), buf);
}

/**
 * 实值特殊函数：硬断言 re 等于参考值；im 应为 0。
 *
 * 注意：digits ≥ 10 时引擎会把**精确 0** 分量写成 JSON null（⑦ 节），于是 im 的
 * 检查只能走 CHECK_KNOWN——既不能把引擎的缺陷固化成期望值，也不能假装没看见。
 * re 的精度断言不受该缺陷影响，是本套件的硬指标。
 */
void expect_real(const Grid& g, double want, double tol, const char* msg) {
    char buf[512];
    if (g.is_error) {
        std::snprintf(buf, sizeof(buf), "%s：调用应成功，实得错误「%s」", msg, g.error.c_str());
        CHECK(false, buf);
        return;
    }
    if (g.v["re"].size() == 0 || g.v["im"].size() == 0) {
        std::snprintf(buf, sizeof(buf), "%s：re/im 是空数组（原始返回 %s）", msg, g.raw.c_str());
        CHECK(false, buf);
        return;
    }
    std::snprintf(buf, sizeof(buf), "%s：期望 %.17g，实得 %s", msg, want, cell(g, "re", 0).c_str());
    if (re_at(g, 0) == re_at(g, 0))
        std::printf("[值] %s：实得 %s，参考 %.17g（绝对误差 %.3g）\n", msg, cell(g, "re", 0).c_str(),
                    want, std::abs(re_at(g, 0) - want));
    else
        std::printf("[值] %s：实得 %s（期望 %.17g）\n", msg, cell(g, "re", 0).c_str(), want);
    CHECK(near(re_at(g, 0), want, tol), buf);

    std::snprintf(buf, sizeof(buf),
                  "%s：实值函数的虚部应为 0，实得 %s（digits≥10 时精确 0 会被写成 null）", msg,
                  cell(g, "im", 0).c_str());
    CHECK_KNOWN(im_at(g, 0) == 0.0, buf);
}

// ── ① 初等函数 ──────────────────────────────────────────────────────────────
// 参考值来源逐条注明。可在复点精确取值的一律用复点（例如 exp/sin/cos/tan 取 1+i），
// 因为 C++ 标准库 <complex> 提供了独立实现，比手写常数更硬。
void test_elementary() {
    const int kHi = 17;  // 高精度：不截断有效数字（JSON 用最短往返表示，读回来是精确的）
    const zc w(1.0, 1.0);

    // z^2 @ z=2+3i = -5+12i —— 代数恒等式（来源：复数乘法定义）
    expect_point(point("z^2", zc(2.0, 3.0), kHi), zc(-5.0, 12.0), 1e-12, "z^2 @ 2+3i");

    // exp(z) @ 1+i —— 参考值 std::exp(complex)（C++ 标准库独立实现）
    expect_point(point("exp(z)", w, kHi), std::exp(w), 1e-12, "exp(z) @ 1+i");

    // e^z @ 1+i —— 原版（PyQt 版）写法之一：常数 e 直接参与幂运算，必须与 exp(z) 同值
    expect_point(point("e^z", w, kHi), std::exp(w), 1e-12, "e^z @ 1+i（原版写法）");

    // 三角 @ 1+i —— 参考值 std::sin/cos/tan(complex)
    expect_point(point("sin(z)", w, kHi), std::sin(w), 1e-12, "sin(z) @ 1+i");
    expect_point(point("cos(z)", w, kHi), std::cos(w), 1e-12, "cos(z) @ 1+i");
    expect_point(point("tan(z)", w, kHi), std::tan(w), 1e-12, "tan(z) @ 1+i");

    // log(-1) = iπ —— 数学事实（主值分支）。缺省 digits=7 的返回被截成 7 位有效数字，
    // 所以 π 的容差取 1e-6；实部必须**恰好** 0（这一条同时守着「0 分量」的语义）：
    // digits≥10 时实部会被写成 null，那是 ⑦ 节的引擎缺陷，所以这里故意用缺省 digits。
    {
        const Grid g = point("log(z)", zc(-1.0, 0.0));
        if (check_shape(g, 1, 1, "log(-1)")) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "log(-1)：虚部应为 π≈%.17g（7 位有效数字），实得 %s", kPi,
                          cell(g, "im", 0).c_str());
            CHECK(near(im_at(g, 0), kPi, 1e-6), buf);
            std::snprintf(buf, sizeof(buf), "log(-1)：实部应恰好 0，实得 %s", cell(g, "re", 0).c_str());
            CHECK(re_at(g, 0) == 0.0, buf);
        }
    }

    // sqrt(-1) = i —— 数学事实（主值）。实部只有浮点噪声，量级 ≤1e-15。
    {
        const Grid g = point("sqrt(z)", zc(-1.0, 0.0), kHi);
        expect_point(g, zc(0.0, 1.0), 1e-12, "sqrt(-1) = i");
        if (!g.is_error && g.v["re"].size() > 0) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "sqrt(-1)：实部应为 0（容差 1e-15），实得 %s",
                          cell(g, "re", 0).c_str());
            CHECK(std::abs(re_at(g, 0)) <= 1e-15, buf);
        }
    }

    // abs(3+4i) = 5 —— 数学事实。实值结果，虚部应为 0（缺省 digits，走的是没问题的路径）
    {
        const Grid g = point("abs(z)", zc(3.0, 4.0));
        if (check_shape(g, 1, 1, "abs(3+4i)")) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "abs(3+4i) 应为 5，实得 %s", cell(g, "re", 0).c_str());
            CHECK(re_at(g, 0) == 5.0, buf);
            std::snprintf(buf, sizeof(buf), "abs(3+4i) 的虚部应为 0，实得 %s", cell(g, "im", 0).c_str());
            CHECK(im_at(g, 0) == 0.0, buf);
        }
    }

    // 1/(1+i) = 0.5-0.5i —— 数学事实（分母有理化：1/(1+i) = (1-i)/2）
    expect_point(point("1/(1+z)", zc(0.0, 1.0), kHi), zc(0.5, -0.5), 1e-12, "1/(1+i) = 0.5-0.5i");

    // |z| @ 3+4i = 5 —— 原版（PyQt 版）写法之二：绝对值竖线。SymEngine 解析器认 |…|。
    {
        const Grid g = point("|z|", zc(3.0, 4.0));
        if (check_shape(g, 1, 1, "|z| @ 3+4i")) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "|z| @ 3+4i 应为 5（原版写法），实得 %s", cell(g, "re", 0).c_str());
            CHECK(re_at(g, 0) == 5.0, buf);
            std::snprintf(buf, sizeof(buf), "|z| 的虚部应为 0，实得 %s", cell(g, "im", 0).c_str());
            CHECK(im_at(g, 0) == 0.0, buf);
        }
    }
}

// ── ② 实值特殊函数（引擎自己补的实现）────────────────────────────────────────
// 全部用 digits=17，把「7 位有效数字截断」排除在精度判定之外。
// zeta(2) 这一条专守刚修的 bug：旧实现（截断级数 10000 项）给 1.644834，
// 尾巴误差约 1/N；Euler–Maclaurin 自带尾巴修正后应为 1.6449340668482262 量级。
void test_special_real() {
    const int kHi = 17;

    // zeta(2)：契约要求相对误差 < 1e-9。旧实现（截断级数 10000 项）给 1.644834，
    // 尾巴误差约 1/N≈1e-4；Euler–Maclaurin 自带尾巴修正后为 1.6449340668482262 量级，
    // 这一条就是为了不让那个 bug 回来。
    expect_real(point("zeta(2)", zc(2.0, 0.0), kHi), 1.6449340668482264, 1e-9, "zeta(2)");
    expect_real(point("zeta(3)", zc(3.0, 0.0), kHi), 1.2020569031595943, 1e-9, "zeta(3)");
    // ζ 的负整数走伯努利数路径（ζ(-1) = -B₂/2 = -1/12）
    expect_real(point("zeta(-1)", zc(-1.0, 0.0), kHi), -1.0 / 12.0, 1e-9, "zeta(-1)");
    expect_real(point("gamma(0.5)", zc(0.5, 0.0), kHi), std::sqrt(kPi), 1e-9, "gamma(0.5)");
    expect_real(point("erf(1)", zc(1.0, 0.0), kHi), 0.8427007929497149, 1e-9, "erf(1)");
    expect_real(point("erfc(1)", zc(1.0, 0.0), kHi), 0.15729920705028513, 1e-9, "erfc(1)");
    // 复合表达式：Γ(3)·ζ(3) = 2·1.2020569031595943…，走的是同一条递归求值路径
    expect_real(point("gamma(z)*zeta(z)", zc(3.0, 0.0), kHi), 2.4041138063191885, 1e-9,
                "gamma(z)*zeta(z) @ 3");
}

// ── ③ 复值特殊函数 ──────────────────────────────────────────────────────────
// 两个分量都不为 0，所以这里是全硬断言，不受 ⑦ 节缺陷影响。
void test_special_complex() {
    const int kHi = 17;
    expect_point(point("gamma(1+i)", zc(1.0, 1.0), kHi), zc(0.4980156681, -0.1549498283), 1e-9,
                 "gamma(1+i)");
    expect_point(point("gamma(i)", zc(0.0, 1.0), kHi), zc(-0.1549498283, -0.4980156681), 1e-9,
                 "gamma(i)（走反射公式）");
    expect_point(point("erf(1+i)", zc(1.0, 1.0), kHi), zc(1.3161512816, 0.1904534692), 1e-9,
                 "erf(1+i)（|z|≤4 的泰勒级数分支）");
}

// ── ④ 极点 / 域外点 → null 且计入 nan ───────────────────────────────────────
void test_domain_points() {
    // 1/z 在以 0 为中心的 3×3 网格上：(0,0) 是极点 → 该点 null，nan==1，ok==8。
    // 坐标映射：j=0 → y=-1，j=2 → y=1；i=0 → x=-1，i=2 → x=1。
    const char* what = "1/z @ 3×3（-1..1 × -1..1）";
    const Grid g = cgrid("1/z", -1, 1, -1, 1, 3, 3);
    if (check_shape(g, 3, 3, what)) {
        char buf[512];
        std::snprintf(buf, sizeof(buf), "%s：中心点 (0,0) 是极点，应为 null，实得 %s", what,
                      rc(g, 4).c_str());
        CHECK(comp(g, "re", 4) != comp(g, "re", 4) && comp(g, "im", 4) != comp(g, "im", 4), buf);

        std::snprintf(buf, sizeof(buf), "%s：nan 应为 1，实得 %lld", what,
                      static_cast<long long>(g.v["nan"].as_int()));
        CHECK(static_cast<long long>(g.v["nan"].as_int()) == 1, buf);

        std::snprintf(buf, sizeof(buf), "%s：ok 应为 8，实得 %lld", what,
                      static_cast<long long>(g.v["ok"].as_int()));
        CHECK(static_cast<long long>(g.v["ok"].as_int()) == 8, buf);

        std::snprintf(buf, sizeof(buf), "%s：re/im 里 null 的个数应等于 nan=1，实得 %lld / %lld", what,
                      static_cast<long long>(nulls(g, "re")),
                      static_cast<long long>(nulls(g, "im")));
        CHECK(nulls(g, "re") == 1 && nulls(g, "im") == 1, buf);

        // 其余 8 点：1/z 在 z=x+iy 处 = (x-iy)/(x²+y²)，逐点核对（同时也再验一遍索引布局）
        for (long long j = 0; j < 3; ++j) {
            for (long long i = 0; i < 3; ++i) {
                if (i == 1 && j == 1) continue;  // 极点
                const std::size_t k = static_cast<std::size_t>(j * 3 + i);
                const double x = -1.0 + i;  // i=0,1,2 → -1,0,1
                const double y = -1.0 + j;  // j=0,1,2 → -1,0,1
                const double d = x * x + y * y;
                std::snprintf(buf, sizeof(buf), "%s：index=%lld（z=%.17g%+.17gi）应为 (%.17g, %.17g)，实得 %s",
                              what, static_cast<long long>(k), x, y, x / d, -y / d, rc(g, k).c_str());
                CHECK(near(re_at(g, k), x / d, 1e-12) && near(im_at(g, k), -y / d, 1e-12), buf);
            }
        }
    }

    // 极点以外还有两类域外点：函数值非有限（溢出 / log(0)）。
    // exp(1000) 溢出成 +inf、log(0) 是 -inf，都必须给 null 并计入 nan——
    // 不能拿 inf 或一个巨大有限值冒充结果。
    {
        const char* w2 = "exp(1000)（溢出 → 非有限）";
        const Grid g2 = point("exp(z)", zc(1000.0, 0.0));
        if (check_shape(g2, 1, 1, w2)) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "%s：应为 null，实得 %s", w2, rc(g2, 0).c_str());
            CHECK(g2.v["nan"].as_int() == 1 && cell(g2, "re", 0) == "null" &&
                      cell(g2, "im", 0) == "null",
                  buf);
        }
        const char* w3 = "log(0)（-∞ → 非有限）";
        const Grid g3 = point("log(z)", zc(0.0, 0.0));
        if (check_shape(g3, 1, 1, w3)) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "%s：应为 null，实得 %s", w3, rc(g3, 0).c_str());
            CHECK(g3.v["nan"].as_int() == 1 && cell(g3, "re", 0) == "null" &&
                      cell(g3, "im", 0) == "null",
                  buf);
        }
        const char* w4 = "gamma(-3)（Γ 的非正整数极点）";
        const Grid g4 = point("gamma(z)", zc(-3.0, 0.0));
        if (check_shape(g4, 1, 1, w4)) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "%s：应为 null，实得 %s", w4, rc(g4, 0).c_str());
            CHECK(g4.v["nan"].as_int() == 1 && cell(g4, "re", 0) == "null" &&
                      cell(g4, "im", 0) == "null",
                  buf);
        }
    }
}

// ── ⑤ 索引与坐标的对应关系 ──────────────────────────────────────────────────
// 契约：行优先 index = j*nx + i；j 对应 y（y0→y1 递增），i 对应 x（x0→x1 递增）。
// 用**线性函数** z（和 2z+i）反推坐标是最好的验证方式——算错了坐标会立刻对不上。
void test_index_layout() {
    const char* what = "z @ 3×2（x:0..2，y:10..11）";
    {
        const Grid g = cgrid("z", 0, 2, 10, 11, 3, 2);
        if (check_shape(g, 3, 2, what)) {
            char buf[512];
            for (long long j = 0; j < 2; ++j) {
                for (long long i = 0; i < 3; ++i) {
                    const std::size_t k = static_cast<std::size_t>(j * 3 + i);
                    const double x = 0.0 + 2.0 * static_cast<double>(i) / 2.0;
                    const double y = 10.0 + 1.0 * static_cast<double>(j) / 1.0;
                    std::snprintf(buf, sizeof(buf),
                                  "%s：index=j*nx+i=%lld 对应 z=(%.17g, %.17g)，实得 %s",
                                  what, static_cast<long long>(k), x, y, rc(g, k).c_str());
                    CHECK(near(re_at(g, k), x, 1e-12) && near(im_at(g, k), y, 1e-12), buf);
                }
            }
        }
    }

    // 2*z+I：re=2x、im=2y+1——两个分量都被坐标各自动过，能同时抓住 x/y 轴搞反的情况
    const char* what2 = "2*z+I @ 3×2（x:0..2，y:10..11）";
    {
        const Grid g = cgrid("2*z+I", 0, 2, 10, 11, 3, 2);
        if (check_shape(g, 3, 2, what2)) {
            char buf[512];
            for (long long j = 0; j < 2; ++j) {
                for (long long i = 0; i < 3; ++i) {
                    const std::size_t k = static_cast<std::size_t>(j * 3 + i);
                    const double x = 2.0 * static_cast<double>(i);
                    const double y = 2.0 * (10.0 + static_cast<double>(j)) + 1.0;
                    std::snprintf(buf, sizeof(buf),
                                  "%s：index=%lld 应为 (%.17g, %.17g)，实得 %s",
                                  what2, static_cast<long long>(k), x, y, rc(g, k).c_str());
                    CHECK(near(re_at(g, k), x, 1e-12) && near(im_at(g, k), y, 1e-12), buf);
                }
            }
        }
    }

    // var 改名：表达式里的 t 会被改写成求值器认识的 z
    const char* what3 = "2*t+I（var=t）@ 3×2";
    {
        const Grid g = cgrid("2*t+I", 0, 2, 10, 11, 3, 2, -1, "t");
        if (check_shape(g, 3, 2, what3)) {
            char buf[512];
            for (long long j = 0; j < 2; ++j) {
                for (long long i = 0; i < 3; ++i) {
                    const std::size_t k = static_cast<std::size_t>(j * 3 + i);
                    const double x = 2.0 * static_cast<double>(i);
                    const double y = 2.0 * (10.0 + static_cast<double>(j)) + 1.0;
                    std::snprintf(buf, sizeof(buf), "%s：index=%lld 应为 (%.17g, %.17g)，实得 %s",
                                  what3, static_cast<long long>(k), x, y, rc(g, k).c_str());
                    CHECK(near(re_at(g, k), x, 1e-12) && near(im_at(g, k), y, 1e-12), buf);
                }
            }
        }
    }

    // ny 缺省 = nx（契约里的可选参数）
    const char* what4 = "z（不传 ny → ny=nx=3）";
    {
        const Grid g = cgrid("z", 0, 2, 10, 10, 3);
        if (check_shape(g, 3, 3, what4)) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "%s：y 固定 10 时 im 应全为 10，实得 %s", what4,
                          cell(g, "im", 0).c_str());
            bool all10 = true;
            for (std::size_t k = 0; k < 9; ++k)
                if (im_at(g, k) != 10.0) all10 = false;
            CHECK(all10, buf);
        }
    }

    // nx=1 / ny=1：该维只取**起点值**（不是中点、也不是终点）。
    // 故意让 x1/y1 远离 x0/y0，这样「只取起点」才真的可验证。
    {
        const char* w5 = "nx=1,ny=1 单点（x0=5,x1=99,y0=7,y1=99）";
        const Grid g = cgrid("z", 5, 99, 7, 99, 1, 1);
        if (check_shape(g, 1, 1, w5)) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "%s：应取起点 (5, 7)，实得 %s", w5, rc(g, 0).c_str());
            CHECK(near(re_at(g, 0), 5.0, 1e-15) && near(im_at(g, 0), 7.0, 1e-15), buf);
            std::snprintf(buf, sizeof(buf), "%s：x0..y1 应原样回显 5/99/7/99，实得 %.17g/%.17g/%.17g/%.17g", w5,
                          g.v["x0"].as_double(), g.v["x1"].as_double(), g.v["y0"].as_double(),
                          g.v["y1"].as_double());
            CHECK(g.v["x0"].as_double() == 5.0 && g.v["x1"].as_double() == 99.0 &&
                      g.v["y0"].as_double() == 7.0 && g.v["y1"].as_double() == 99.0,
                  buf);
        }
    }
    {
        const char* w6 = "nx=1（单列）";
        const Grid g = cgrid("z", 5, 99, 7, 99, 1, 3);
        if (check_shape(g, 1, 3, w6)) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "%s：x 应固定为起点 5、y 应为 7/53/99，实得 %s %s %s", w6,
                          rc(g, 0).c_str(), rc(g, 1).c_str(), rc(g, 2).c_str());
            CHECK(re_at(g, 0) == 5.0 && re_at(g, 1) == 5.0 && re_at(g, 2) == 5.0 &&
                      near(im_at(g, 0), 7.0, 1e-15) && near(im_at(g, 1), 53.0, 1e-15) &&
                      near(im_at(g, 2), 99.0, 1e-15),
                  buf);
        }
    }
    {
        const char* w7 = "ny=1（单行）";
        const Grid g = cgrid("z", 5, 99, 7, 99, 3, 1);
        if (check_shape(g, 3, 1, w7)) {
            char buf[512];
            std::snprintf(buf, sizeof(buf), "%s：y 应固定为起点 7、x 应为 5/52/99，实得 %s %s %s", w7,
                          rc(g, 0).c_str(), rc(g, 1).c_str(), rc(g, 2).c_str());
            CHECK(im_at(g, 0) == 7.0 && im_at(g, 1) == 7.0 && im_at(g, 2) == 7.0 &&
                      near(re_at(g, 0), 5.0, 1e-15) && near(re_at(g, 1), 52.0, 1e-15) &&
                      near(re_at(g, 2), 99.0, 1e-15),
                  buf);
        }
    }
}

// ── ⑥ unsupported 与参数错误 ────────────────────────────────────────────────
void test_unsupported_and_limits() {
    // lambertw：SymEngine 认这个名字（能解析），但复参数求值没实现 →
    // 必须报 unsupported，并给出 null（拿不到数值），**不能**当成 0 或其它假值。
    {
        const char* what = "lambertw(z)（能解析、算不出来）";
        const Grid g = point("lambertw(z)", zc(1.0, 0.0));
        if (check_shape(g, 1, 1, what)) {
            char buf[640];
            std::snprintf(buf, sizeof(buf), "%s：unsupported 应非空并指出函数名，实得「%s」（nan=%lld，re=%s）",
                          what, g.v["unsupported"].as_string().c_str(),
                          static_cast<long long>(g.v["nan"].as_int()), cell(g, "re", 0).c_str());
            const std::string u = g.v["unsupported"].as_string();
            CHECK(!u.empty() && u.find("lambertw") != std::string::npos, buf);
            std::snprintf(buf, sizeof(buf), "%s：算不出来时不得返回数值，应给 null 并计入 nan，实得 re=%s nan=%lld",
                          what, cell(g, "re", 0).c_str(),
                          static_cast<long long>(g.v["nan"].as_int()));
            CHECK(g.v["nan"].as_int() == 1 && cell(g, "re", 0) == "null" && cell(g, "im", 0) == "null",
                  buf);
        }
    }

    // polylog(2,z)：SymEngine 没有这个函数节点——多字母名被按单字母符号连乘解析
    // （所以报出来的其实是「未绑定的符号 l」）。结论一样：算不出来 → unsupported 非空。
    {
        const char* what = "polylog(2,z)";
        const Grid g = point("polylog(2,z)", zc(1.0, 0.0));
        if (check_shape(g, 1, 1, what)) {
            char buf[640];
            const std::string u = g.v["unsupported"].as_string();
            std::snprintf(buf, sizeof(buf), "%s：unsupported 应非空，实得「%s」", what, u.c_str());
            CHECK(!u.empty(), buf);
        }
    }

    // besselj(0,z)：连解析都过不去（多字母名 + 带逗号的括号组）→ 走的是**报错**这条路，
    // 与 unsupported 不是同一条路径。两者都必须让人一眼看出「这个表达式用不了」。
    {
        const Grid g = point("besselj(0,z)", zc(1.0, 0.0));
        char buf[640];
        std::snprintf(buf, sizeof(buf), "besselj(0,z)：应报错（解析失败），实得 isError=%d 返回 %s",
                      g.is_error ? 1 : 0, g.raw.substr(0, 200).c_str());
        CHECK(g.is_error, buf);
    }

    // 正常表达式的 unsupported 必须是空串——否则前端会把正常图当异常
    {
        const char* what = "正常表达式不得报 unsupported";
        const Grid g = point("sin(z)+zeta(z)", zc(1.0, 1.0), 7);
        if (check_shape(g, 1, 1, what)) {
            char buf[640];
            std::snprintf(buf, sizeof(buf), "%s，实得「%s」", what, g.v["unsupported"].as_string().c_str());
            CHECK(g.v["unsupported"].as_string().empty(), buf);
        }
    }

    // 点数上限 400000：701×701 = 491401 → 必须报错并说清原因，而不是悄悄降分辨率
    {
        const Grid g = cgrid("z", -1, 1, -1, 1, 701, 701);
        char buf[640];
        std::snprintf(buf, sizeof(buf), "701×701 应报错（上限 400000），实得 isError=%d 返回 %s",
                      g.is_error ? 1 : 0, g.raw.substr(0, 200).c_str());
        CHECK(g.is_error, buf);
        std::snprintf(buf, sizeof(buf), "701×701 的错误文案应说明上限 400000，实得「%s」", g.error.c_str());
        CHECK(g.error.find("400000") != std::string::npos, buf);
    }

    // nx/ny 必须为正整数
    {
        const Grid g = cgrid("z", 0, 1, 0, 1, 0, 2);
        char buf[640];
        std::snprintf(buf, sizeof(buf), "nx=0 应报错（必须为正整数），实得返回 %s", g.raw.substr(0, 200).c_str());
        CHECK(g.is_error && g.error.find("正整数") != std::string::npos, buf);
    }

    // 上限的另一侧：400×1001 = 400400，只超 400 个点也必须报错
    // （上限是「> 400000 才报错」，所以这一条与 701×701 互补：错一个点也算超）
    {
        const Grid g = cgrid("z", 0, 1, 0, 1, 400, 1001);
        char buf[640];
        std::snprintf(buf, sizeof(buf), "400×1001 = 400400 点应报错（上限 400000），实得 isError=%d 返回 %s",
                      g.is_error ? 1 : 0, g.raw.substr(0, 200).c_str());
        CHECK(g.is_error, buf);
    }
}

// ── ⑦ 已知引擎缺陷（只记录，不修；--strict 时计入失败）──────────────────────
//
// 根因在 plot_api.cpp 的 round_to：mag = 10^(digits-1-floor(log10(|v|+1e-300)))，当 v 恰好是 0 时
// floor(log10(1e-300)) = -300，于是 mag = 10^(digits+299)；digits ≥ 10 时幂超上 double 上限
// （1.8e308）变成 +inf，接着 round(0·inf)/inf = NaN，NaN 被 JSON 序列化成 null。
// 后果：digits ≥ 10 时**任何恰好为 0 的分量都会被当成「域外点」**，
// 而 nan 计数并不增加——前端于是无法区分「0」和「极点」，相位图/域着色会出现假空白。
// 缺省 digits=7 时 mag=1e306 仍有限，所以默认路径看不出问题。
void test_known_zero_component_defect() {
    // 边界：digits=9 正常（10^308 仍未溢出），digits=10 起坏掉
    {
        const Grid g9 = point("z", zc(0.0, 0.0), 9);
        char buf[640];
        std::snprintf(buf, sizeof(buf), "digits=9 时 z=0 的 re 应为 0，实得 %s", cell(g9, "re", 0).c_str());
        CHECK(g9.v["re"].size() > 0 && re_at(g9, 0) == 0.0 && im_at(g9, 0) == 0.0, buf);

        const Grid g10 = point("z", zc(0.0, 0.0), 10);
        std::snprintf(buf, sizeof(buf),
                      "digits=10 时 z=0 的 re/im 应为 0（0 是有限值，不是域外点），实得 re=%s im=%s，nan=%lld",
                      cell(g10, "re", 0).c_str(), cell(g10, "im", 0).c_str(),
                      static_cast<long long>(g10.v["nan"].as_int()));
        CHECK_KNOWN(re_at(g10, 0) == 0.0 && im_at(g10, 0) == 0.0, buf);
    }

    // 高精度实值特殊函数同样受害：zeta(2) 的虚部应为 0
    {
        const Grid g = point("zeta(2)", zc(2.0, 0.0), 17);
        char buf[640];
        std::snprintf(buf, sizeof(buf), "digits=17 时 zeta(2) 的虚部应为 0，实得 %s", cell(g, "im", 0).c_str());
        CHECK_KNOWN(im_at(g, 0) == 0.0, buf);
    }

    // 实部恰好为 0 的常见表达式：z^2 @ 1+i = 2i，log(-1) = iπ
    {
        const Grid g1 = point("z^2", zc(1.0, 1.0), 17);
        char buf[640];
        std::snprintf(buf, sizeof(buf), "digits=17 时 z^2 @ 1+i = 2i 的实部应为 0，实得 %s", cell(g1, "re", 0).c_str());
        CHECK_KNOWN(re_at(g1, 0) == 0.0, buf);

        const Grid g2 = point("log(z)", zc(-1.0, 0.0), 17);
        std::snprintf(buf, sizeof(buf), "digits=17 时 log(-1) = iπ 的实部应为 0，实得 %s", cell(g2, "re", 0).c_str());
        CHECK_KNOWN(re_at(g2, 0) == 0.0, buf);
    }

    // 最要紧的一条：null 的个数必须等于 nan，否则调用方无法区分「0」与「域外点」。
    // digits=17 下 1/z @ 3×3：re 里 null 有 3 个（z=i 与 z=-i 处 re=0，加中心极点），但 nan 只有 1。
    {
        const Grid g = cgrid("1/z", -1, 1, -1, 1, 3, 3, 17);
        char buf[640];
        std::snprintf(buf, sizeof(buf),
                      "digits=17 时 1/z @ 3×3 的 re 中 null 个数应等于 nan=%lld，实得 %lld（多出的是精确 0 被写成了 null）",
                      static_cast<long long>(g.v["nan"].as_int()),
                      static_cast<long long>(nulls(g, "re")));
        CHECK_KNOWN(nulls(g, "re") == static_cast<std::size_t>(g.v["nan"].as_int()), buf);
    }
}

}  // namespace

int main(int argc, char** argv) {
    for (int i = 1; i < argc; ++i)
        if (std::string(argv[i]) == "--strict") g_strict = true;

    std::system("chcp 65001 > nul");
    setvbuf(stdout, nullptr, _IONBF, 0);

    std::printf("===== complex_grid 契约测试 =====\n");
    std::printf("-- ① 初等函数数值 --\n");
    test_elementary();
    std::printf("-- ② 实值特殊函数（zeta / gamma / erf / erfc）--\n");
    test_special_real();
    std::printf("-- ③ 复值特殊函数 --\n");
    test_special_complex();
    std::printf("-- ④ 极点 / 域外点 → null 且计入 nan --\n");
    test_domain_points();
    std::printf("-- ⑤ 索引与坐标对应 --\n");
    test_index_layout();
    std::printf("-- ⑥ unsupported 与点数上限 --\n");
    test_unsupported_and_limits();
    std::printf("-- ⑦ 已知引擎缺陷（记录，不计入失败，除非 --strict）--\n");
    test_known_zero_component_defect();

    std::printf("\n%d 项检查，%d 项失败", g_checks, g_failures);
    if (g_known_bugs > 0) {
        std::printf("；另有 %d 项已知引擎缺陷（round_to 在 digits≥10 时把精确 0 写成 null）%s",
                    g_known_bugs, g_strict ? "，已计入失败" : "，默认不计入失败（--strict 可让它们生效）");
    }
    std::printf("\n");
    return g_failures == 0 ? 0 : 1;
}
