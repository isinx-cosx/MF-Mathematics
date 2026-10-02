#include "series.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <sstream>
#include <string>

#include <symengine/basic.h>
#include <symengine/derivative.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/simplify.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

namespace mf::calculus {

namespace {
using SymEngine::RCP;
using SymEngine::Basic;

// 阶乘(数值,上溢为 inf)。
double fact_double(long long n) {
    if (n < 0) return std::numeric_limits<double>::quiet_NaN();
    double f = 1.0;
    for (long long i = 2; i <= n; ++i) {
        f *= (double)i;
        if (!std::isfinite(f)) return std::numeric_limits<double>::infinity();
    }
    return f;
}

// 通项 a_n 的求值器：**解析一次**，之后每次只做整数代换 + 求值。
//
// ⚠ 历史上这里是 `eval_n(expr, var, n)`，每次都重新 parse。单次调用无所谓，但凡是
// "对 n 扫一遍"的判别法都必须用本类：旧实现里 integral_test 做了 **100 万次** 求值，
// 时间几乎全花在重复解析上（1/n² 这种最简单的式子要 1 秒，复杂式子 3–10 秒，
// 用户看到的就是"点了没反应"）。
class SeriesEvaluator {
public:
    SeriesEvaluator(const std::string& expr, const std::string& var)
        : var_(SymEngine::symbol(var)) {
        std::string e = expr;
        // factorial(var) → 数值占位：SymEngine 解析器不支持 factorial(n)，
        // 这个预处理是**每个 n 都要做的**字符串替换，所以只在构造时判断一次，
        // 之后每次求值直接把占位符换成当前 n 的阶乘值。
        const std::string token = "factorial(" + var + ")";
        has_factorial_ = e.find(token) != std::string::npos;
        if (has_factorial_) {
            std::size_t pos = 0;
            while ((pos = e.find(token, pos)) != std::string::npos) {
                e.replace(pos, token.size(), kFactPlaceholder);
                pos += std::string(kFactPlaceholder).size();
            }
        }
        try {
            body_ = SymEngine::parse(e);
            ok_ = true;
        } catch (...) {
            ok_ = false;
        }
    }

    bool ok() const { return ok_; }

    double at(double n) const {
        if (!ok_) return std::numeric_limits<double>::quiet_NaN();
        try {
            SymEngine::RCP<const Basic> target = body_;
            if (has_factorial_) {
                std::string s = SymEngine::str(*body_);
                const std::string repl = std::to_string(fact_double((long long)std::round(n)));
                std::size_t pos = 0;
                while ((pos = s.find(kFactPlaceholder, pos)) != std::string::npos) {
                    s.replace(pos, std::string(kFactPlaceholder).size(), repl);
                    pos += repl.size();
                }
                target = SymEngine::parse(s);
            }
            // 整数代换,避免 (-1)^n 的实数指数求值问题。
            SymEngine::RCP<const Basic> pt;
            if (std::abs(n - std::round(n)) < 1e-12)
                pt = SymEngine::integer((long long)std::round(n));
            else
                pt = SymEngine::real_double(n);
            return SymEngine::eval_double(*target->subs({{var_, pt}}));
        } catch (...) {
            return std::numeric_limits<double>::quiet_NaN();
        }
    }

private:
    static constexpr const char* kFactPlaceholder = "__mf_factorial__";
    SymEngine::RCP<const SymEngine::Symbol> var_;
    SymEngine::RCP<const Basic> body_;
    bool has_factorial_ = false;
    bool ok_ = false;
};

// 通项 a_n 在整数 n 处的值。异常返回 NaN。
// 单次调用走这条路（内部构造一次求值器）；循环里请直接用 SeriesEvaluator。
double eval_n(const std::string& expr, const std::string& var, double n) {
    return SeriesEvaluator(expr, var).at(n);
}

// 估计 p:ln|a_n|/ln(1/n) 在大 n 处。
double estimate_p(const std::string& expr, const std::string& var) {
    const double a1 = std::abs(eval_n(expr, var, 1e6));
    const double a2 = std::abs(eval_n(expr, var, 1e8));
    if (a1 <= 0 || a2 <= 0 || !std::isfinite(a1) || !std::isfinite(a2))
        return std::numeric_limits<double>::quiet_NaN();
    return std::log(a1 / a2) / std::log(1e8 / 1e6);
}

/**
 * 用柯西凝聚估指数：b_k = 2^k·a(2^k)，对 b_k ~ C·k^(-P) 取对数斜率
 *     P = ln(b_k / b_{2k}) / ln 2
 *
 * 为什么比直接对 a_n 估 p 好：**对数因子会被吸收成常数**。
 *   a_n = 1/(n·ln n) → b_k = 2^k/(2^k·ln 2^k) = 1/(k·ln2)，P 精确 = 1 ⇒ 发散 ✓
 *   而旧的直接估计法把 ln(1e8)/ln(1e6) 的比值算进去，得到 p ≈ 1.0625 > 1，
 *   把一个**发散**的级数判成了绝对收敛。
 * 对纯幂级数两者一致（1/n² → P=2 ✓），对几何级数 P 极大 ⇒ 收敛 ✓。
 */
double estimate_p_condensed(const std::string& expr, const std::string& var) {
    const auto b = [&](long long k) -> double {
        const double n = std::pow(2.0, static_cast<double>(k));
        const double a = std::abs(eval_n(expr, var, n));
        if (!std::isfinite(a) || a <= 0.0) return std::numeric_limits<double>::quiet_NaN();
        return n * a;
    };
    for (long long k : {24LL, 20LL, 16LL, 12LL, 8LL, 5LL}) {
        const double b1 = b(k), b2 = b(2 * k);
        if (std::isfinite(b1) && std::isfinite(b2) && b1 > 0.0 && b2 > 0.0) {
            const double P = std::log(b1 / b2) / std::log(2.0);
            if (std::isfinite(P)) return P;
        }
    }
    return std::numeric_limits<double>::quiet_NaN();
}

// 符号比值 |a_{n+1}/a_n| 在 n 处的值(避免阶乘下溢)。
double ratio_at(const std::string& expr, const std::string& var, long long n) {
    // factorial:数值比值(SymEngine 解析器不支持 factorial)。
    if (expr.find("factorial(") != std::string::npos) {
        const double an = std::abs(eval_n(expr, var, (double)n));
        const double an1 = std::abs(eval_n(expr, var, (double)(n + 1)));
        if (std::isfinite(an) && std::isfinite(an1) && an > 1e-300)
            return an1 / an;
        return std::numeric_limits<double>::quiet_NaN();
    }
    const auto ns = SymEngine::symbol(var);
    const auto e = SymEngine::parse(expr);
    const auto e_next = e->subs({{ns, SymEngine::add(ns, SymEngine::integer(1))}});
    const auto ratio = SymEngine::simplify(SymEngine::abs(SymEngine::div(e_next, e)));
    const auto sub = ratio->subs({{ns, SymEngine::integer(n)}});
    return SymEngine::eval_double(*sub);
}

// 交错级数检测:符号交替且 |a_n| 递减。
bool is_alternating(const std::string& expr, const std::string& var) {
    std::vector<double> signs;
    for (long long n = 1; n <= 20; ++n) {
        const double v = eval_n(expr, var, (double)n);
        if (!std::isfinite(v)) return false;
        signs.push_back(v > 0 ? 1.0 : -1.0);
    }
    for (std::size_t i = 1; i < signs.size(); ++i)
        if (signs[i] == signs[i - 1]) return false;
    // |a_n| 递减。
    double prev = std::abs(eval_n(expr, var, 1.0));
    for (long long n = 2; n <= 20; ++n) {
        const double cur = std::abs(eval_n(expr, var, (double)n));
        if (cur > prev * (1 + 1e-9)) return false;
        prev = cur;
    }
    return true;
}

// 泰勒系数(符号)。
std::string coeff_at(const std::string& expr, const std::string& var,
                     double point, long long k) {
    const auto xs = SymEngine::symbol(var);
    auto d = SymEngine::parse(expr);
    for (long long i = 0; i < k; ++i) d = SymEngine::diff(d, xs);
    if (k > 0) d = SymEngine::div(d, SymEngine::factorial((unsigned long)k));
    RCP<const Basic> pt;
    if (std::abs(point - std::round(point)) < 1e-12)
        pt = SymEngine::integer((long long)std::round(point));
    else
        pt = SymEngine::real_double(point);
    return SymEngine::str(*SymEngine::simplify(d->subs({{xs, pt}})));
}
}  // namespace

double series_sum(const std::string& expr, const std::string& var, long long a,
                  long long b) {
    if (b >= 0) {
        double s = 0.0;
        for (long long n = a; n <= b; ++n) {
            const double v = eval_n(expr, var, (double)n);
            if (std::isfinite(v)) s += v;
        }
        return s;
    }
    // 无穷上限:部分和 + 尾项估计。
    //
    // 旧实现把 n 一直加到 **1000000**（again：100 万次求值），只为把尾项压到足够小。
    // 实际上尾项可以用通项自身的衰减规律解析估出来，2000 项 + 尾项修正即可达到
    // 1e-7 量级（π²/6 这种标准值误差远小于 1e-3 的用例容差）：
    //   · 几何衰减（r = a(N+1)/a(N) < 0.999）→ 尾 = a_N·r/(1-r)；
    //   · 幂型衰减 a_n ~ C·n^-p → 先用 a(N) 与 a(2N) 估出 p = log2(a_N/a_2N)，
    //     尾 ≈ a_N·N/(p-1)（∫_N^∞）+ a_N/2（Euler–Maclaurin 一阶项）。
    // p ≤ 1（发散）或估不出来时不再硬撑，直接返回部分和——这一点在注释里写清，
    // 免得下游把"发散的级数"当成"算出来的和"。
    const long long N = 2000;
    SeriesEvaluator ev(expr, var);
    double s = 0.0;
    for (long long n = a; n <= N; ++n) {
        const double v = ev.at((double)n);
        if (std::isfinite(v)) s += v;
    }
    const double aN = std::abs(ev.at((double)N));
    const double aN1 = std::abs(ev.at((double)(N + 1)));
    if (!std::isfinite(aN) || aN <= 0.0) return s;
    if (std::isfinite(aN1)) {
        const double r = aN1 / aN;
        if (r < 0.999) return s + aN * r / (1.0 - r);   // 几何尾
    }
    const double a2N = std::abs(ev.at((double)(2 * N)));
    if (std::isfinite(a2N) && a2N > 0.0) {
        const double p = std::log(aN / a2N) / std::log(2.0);
        if (std::isfinite(p) && p > 1.0 + 1e-9)
            return s + aN * (double)N / (p - 1.0) + aN * 0.5;
    }
    return s;
}

std::string series_convergence(const std::string& expr,
                               const std::string& var) {
    // 比值判别:r = lim |a_{n+1}/a_n|。r→1 时比值法失效(如 p-级数)。
    double r = std::numeric_limits<double>::quiet_NaN();
    try {
        r = ratio_at(expr, var, 100000);
    } catch (...) {
    }
    if (!std::isfinite(r)) {
        // 大 n 溢出(如阶乘):回退到小 n。
        try {
            r = ratio_at(expr, var, 100);
        } catch (...) {
        }
    }
    if (!std::isfinite(r)) return "极限不存在";
    if (r < 0.9995) return "绝对收敛";
    if (r > 1.0005) return "发散";
    return "判别法失效";
}

std::string power_series(const std::string& expr, const std::string& var,
                         double point, long long n) {
    const bool zero_center = std::abs(point) < 1e-12;
    std::string out;
    for (long long k = 0; k <= n; ++k) {
        const std::string c = coeff_at(expr, var, point, k);
        if (c == "0") continue;
        std::string term;
        if (k == 0) {
            term = c;
        } else {
            std::string pw;
            if (zero_center) {
                pw = (k == 1) ? var : var + "**" + std::to_string(k);
            } else {
                const std::string base = "(" + var + " - " + std::to_string(point) + ")";
                pw = (k == 1) ? base : base + "**" + std::to_string(k);
            }
            if (c == "1") term = pw;
            else if (c == "-1") term = "-" + pw;
            else {
                const std::size_t pos = c.find('/');
                if (pos != std::string::npos) {
                    const std::string num = c.substr(0, pos), den = c.substr(pos + 1);
                    if (num == "1") term = pw + "/" + den;
                    else if (num == "-1") term = "-" + pw + "/" + den;
                    else term = pw + "*" + num + "/" + den;
                } else {
                    term = pw + "*" + c;
                }
            }
        }
        if (!out.empty()) out += " + ";
        out += term;
    }
    return out;
}

double power_series_radius(const std::string& expr, const std::string& var) {
    const auto a_abs = [&](long long n) {
        return std::abs(eval_n(expr, var, static_cast<double>(n)));
    };
    const auto ratio_at = [&](long long n) {
        const double an = a_abs(n);
        const double an1 = a_abs(n + 1);
        if (std::isfinite(an) && std::isfinite(an1) && an > 0 && an1 > 0)
            return an1 / an;
        return std::numeric_limits<double>::quiet_NaN();
    };
    const double r10 = ratio_at(10);
    const double r20 = ratio_at(20);
    const double r40 = ratio_at(40);
    if (!(std::isfinite(r10) && std::isfinite(r20) && std::isfinite(r40)))
        return std::numeric_limits<double>::quiet_NaN();
    // 比值逐段减半 → 极限 0 → 半径 ∞（阶乘型）。
    if (r20 < 0.6 * r10 && r40 < 0.6 * r20 && r40 < 0.5)
        return std::numeric_limits<double>::infinity();

    // ── 结构化解法（不再是"取某个 n 的比值"或多项式外推）──
    //
    // 覆盖 a_n = qⁿ·n^(-p) 这一大类（幂型、几何型、两者相乘）：此时
    //     r_n = a_{n+1}/a_n = q·(1 + 1/n)^(-p)
    // 未知量两个（q、p），恰好可以两步解出、不必外推：
    //     t = r_n / r_{2n} = ((1+1/(2n)) / (1+1/n))^p
    //     ⇒ p = ln t / ln((1+1/(2n))/(1+1/n))        （q 被约掉，与 q 无关）
    //     ⇒ q = r_n·(1 + 1/n)^p
    // 半径 R = 1/q。已用精确有理数离线验证：这一族上相对误差 0～2e-16，
    // 而"取 1/r40"会给 1/n² 算出 1.0506（偏 5%）—— 旧实现的系统性高估来源。
    //
    // ⚠ 关键的取样点选择：必须在 a_n **量级正常**的 n 上取样。
    //   a_n = 1/(3ⁿ·n) 在 n=640 时约 1e-311，已进入次正规区，比值只剩两三位
    //   有效数字；若在那里做高阶外推会彻底崩坏（实测给 3.075，真值 3）。
    //   所以从大往小挑第一个 a_n、a_{n+1} 都 ≥1e-250 的 n。
    const auto usable = [&](long long n) {
        const double an = a_abs(n);
        const double an1 = a_abs(n + 1);
        return std::isfinite(an) && std::isfinite(an1) &&
               an > 1e-250 && an1 > 1e-250;
    };
    long long n_best = 0;
    for (long long n : {5120LL, 2560LL, 1280LL, 640LL, 320LL, 160LL, 80LL, 40LL}) {
        // n 和 2n 都必须量级正常：反解要用到 r_n/r_{2n}，
        // 只要 2n 处 a 已经溢出/下溢，这一步就白做（实测 1/(n·2ⁿ) 在 n=640 时
        // 2n=1280 的 2^1280 溢出 → 直接退回旧分支、又给出 2.05）。
        if (usable(n) && usable(2 * n)) {
            n_best = n;
            break;
        }
    }
    const auto solve_q = [&](long long n, bool& ok) -> double {
        ok = false;
        const double rn = ratio_at(n);
        const double r2n = ratio_at(2 * n);
        if (!std::isfinite(rn) || !std::isfinite(r2n) || rn <= 0.0 || r2n <= 0.0)
            return 0.0;
        const double t = rn / r2n;
        const double den = std::log((1.0 + 1.0 / (2.0 * n)) / (1.0 + 1.0 / n));
        if (t <= 0.0 || std::abs(den) < 1e-300) return 0.0;
        const double p = std::log(t) / den;
        const double q = rn * std::pow(1.0 + 1.0 / n, p);
        if (!std::isfinite(q)) return 0.0;
        ok = true;
        return q;
    };
    if (n_best > 0) {
        bool ok_a = false, ok_b = false;
        const double q_a = solve_q(n_best, ok_a);
        const double n_b = n_best / 2 >= 40 ? n_best / 2 : n_best;
        const double q_b = (n_b == n_best) ? q_a : solve_q(static_cast<long long>(n_b), ok_b);
        if (ok_a && q_a > 1e-300) {
            // 两个不同 n 上解出的 q 一致才采用（一致性检查，防止模型不适用时误用）
            if (ok_b && std::abs(q_a - q_b) / q_a < 1e-6) return 1.0 / q_a;
            if (!ok_b) return 1.0 / q_a;
        }
        if (ok_a && q_a <= 1e-300)
            return std::numeric_limits<double>::infinity();
    }
    return 1.0 / r40;
}

std::string leibniz_test(const std::string& expr, const std::string& var) {
    if (!is_alternating(expr, var)) return "inconclusive";
    // 莱布尼茨判别法：|a_n| 单调递减 **且** 趋于 0。
    //
    // ⚠ 旧实现只看 |a_{10^6}| < 1e-3 这一个绝对阈值：(-1)^n/√n 在 10^6 处
    //   恰为 1e-3，「不小于」于是被判 divergent，而它明明收敛。
    //   "趋于 0" 是极限命题，不能用固定阈值代替。
    //
    // 这里用**每十倍衰减比** r = |a(10^5)| / |a(10^6)|：
    //   · 幂型 a_n ~ n^-p → r = 10^p > 1（p=0.5 时 r=3.16）；
    //   · 对数型 1/ln n  → r = ln(10^6)/ln(10^5) ≈ 1.20 > 1，仍能判出；
    //   · 极限非零（如 0.5 + 1/n、常数 1）→ r ≈ 1，正确判为发散。
    // 门槛取 1.05，留出对数型的余量。
    //
    // ⚠ 不调用符号 limit 来精确判 a_n → 0：实测
    //   limit("1/n^0.5", n, ∞) 会让引擎**栈溢出**（0xC0000005，进程直接死），
    //   而这类分数次幂正是本判别法最常见的输入。已把该崩溃记为待修缺陷。
    // 已知局限：衰减极慢的项（如 n^-0.01，r≈1.023）会被判 divergent；
    // 数值方法无法可靠区分"极慢趋零"与"趋于正的常数"，故不假装能判。
    const double a5 = std::abs(eval_n(expr, var, 1e5));
    const double a6 = std::abs(eval_n(expr, var, 1e6));
    const double a3 = std::abs(eval_n(expr, var, 1e3));
    if (!std::isfinite(a5) || !std::isfinite(a6)) return "convergent";
    const bool non_increasing = (a5 <= a3 * (1.0 + 1e-12)) &&
                                (a6 <= a5 * (1.0 + 1e-12));
    if (!non_increasing) return "divergent";
    const bool decays = (a6 < 1e-8) || (a5 > 0.0 && a5 > 1.05 * a6);
    return decays ? "convergent" : "divergent";
}

std::string integral_test(const std::string& expr, const std::string& var) {
    // 积分判别法：a_n 单调递减时 Σa_n 与 ∫a(x)dx 同敛散。
    //
    // 旧实现把"部分和有界"直接当成**逐项累加 100 万次**来做（n=1..1e5 再 1e5+1..1e6），
    // 于是这个纯判别动作白烧掉 1e6 次表达式求值：最简单的情形 1 秒，稍复杂 3–10 秒，
    // 严重时直接把界面卡住。判敛散根本不需要精确部分和——只需要**尾部是否还在累积**。
    //
    // 现在：在 [1e5, 1e6] 上按**几何节点**做梯形积分（65 个点，跨两个数量级），
    // 阈值与原实现一致（尾部量级 < 0.1 视为收敛）。为了不被震荡项相消骗过，
    // 同时用 |a| 的同一个积分做量级检查（对应旧实现的 |s1| > 1e8 判发散）。
    constexpr int kSteps = 64;
    const double lo = 1e5, hi = 1e6;
    const double log_lo = std::log(lo), log_hi = std::log(hi);
    const double dx = (log_hi - log_lo) / kSteps;

    SeriesEvaluator ev(expr, var);
    if (!ev.ok()) return "inconclusive";

    double tail = 0.0, magnitude = 0.0;
    double prev_x = lo, prev_f = ev.at(lo), prev_abs = std::abs(prev_f);
    for (int i = 1; i <= kSteps; ++i) {
        const double x = std::exp(log_lo + i * dx);
        const double f = ev.at(x);
        const double af = std::abs(f);
        const double df = std::isfinite(f) ? f : 0.0;
        const double da = std::isfinite(af) ? af : 0.0;
        // 梯形（对数坐标下 d(ln x) 的积分 = ∫a dx）
        tail += 0.5 * (prev_f + df) * (x - prev_x);
        magnitude += 0.5 * (prev_abs + da) * (x - prev_x);
        prev_x = x; prev_f = df; prev_abs = da;
    }
    if (!std::isfinite(magnitude)) return "divergent";
    if (magnitude > 1e8) return "divergent";         // 尾部还在爆量级 → 发散
    if (!std::isfinite(tail)) return "divergent";
    if (tail < 0.1) return "convergent";             // 尾积分可忽略 → 收敛
    return "divergent";
}

std::string p_series_test(const std::string& expr, const std::string& var) {
    const double p = estimate_p(expr, var);
    if (!std::isfinite(p)) return "inconclusive";
    return p > 1 ? "convergent" : "divergent";
}

std::string limit_comparison_test(const std::string& expr,
                                  const std::string& var) {
    const double p = estimate_p(expr, var);
    if (!std::isfinite(p)) return "inconclusive";
    // 与 p-级数比较:极限 a_n·n^p 有限。
    const double an = std::abs(eval_n(expr, var, 1e6));
    const double scaled = std::isfinite(an) ? an * std::pow(1e6, p) : 0.0;
    if (!std::isfinite(scaled)) return "inconclusive";
    return p > 1 ? "convergent" : "divergent";
}

// 直接比较判别法:与已知敛散的比较级数 b_n 比较。
//   a_n ≤ b_n 且 ∑b_n 收敛 → 收敛;a_n ≥ b_n 且 ∑b_n 发散 → 发散。
// compare_expr 为空时自动生成(含 exp → 几何 (1/2)^n,否则 1/n²)。
std::string direct_comparison_test(const std::string& expr,
                                   const std::string& var,
                                   const std::string& compare_expr) {
    std::string b = compare_expr;
    if (b.empty()) {
        if (expr.find("exp(") != std::string::npos)
            b = "(1/2)**" + var;
        else
            b = "1/" + var + "**2";
    }
    // 大 n 处 a_n 与 b_n 的大小关系(+1:a>b,-1:a<b,0:相等/无法判定)。
    int sign = 0;
    for (const double n : {1e6, 1e5, 1e4, 1e3}) {
        const double av = eval_n(expr, var, n);
        const double bv = eval_n(b, var, n);
        // 一方溢出为 ±inf:主导项直接定符号。
        if (std::isinf(av) && std::isfinite(bv)) { sign = av > 0 ? 1 : -1; break; }
        if (std::isinf(bv) && std::isfinite(av)) { sign = av > bv ? 1 : -1; break; }
        if (std::isfinite(av) && std::isfinite(bv) && std::abs(av - bv) > 1e-15) {
            sign = (av > bv) ? 1 : -1;
            break;
        }
    }
    // 比较级数已知敛散性:+1 收敛,-1 发散,0 未知。
    int known = 0;
    const double b3 = std::abs(eval_n(b, var, 1e3));
    const double b6 = std::abs(eval_n(b, var, 1e6));
    if (std::isfinite(b6) && b6 > 1e-300) {
        const double c = b6 * 1e12;  // 1/n² 型
        if (std::isfinite(c) && std::abs(c - 1.0) < 1e-2) known = 1;
        if (known == 0) {
            const double c2 = b6 * 1e6;  // 1/n 型
            if (std::isfinite(c2) && std::abs(c2 - 1.0) < 1e-2) known = -1;
        }
        if (known == 0 && std::isfinite(b3) &&
            std::abs(b6 - b3) < 1e-6 * std::max(1.0, std::abs(b3)))
            known = -1;  // 常数型
    } else if (std::isfinite(b6) && std::isfinite(b3) && b3 > 0.0) {
        const double r = eval_n(b, var, 200) / eval_n(b, var, 100);  // 几何比 < 1
        if (std::isfinite(r) && std::abs(r) < 0.99) known = 1;
    }
    if (sign <= 0) return known > 0 ? "convergent" : "inconclusive";
    return known < 0 ? "divergent" : "inconclusive";
}

std::string classify_and_test(const std::string& expr, const std::string& var) {
    if (is_alternating(expr, var)) return leibniz_test(expr, var);
    const double p = estimate_p(expr, var);
    if (std::isfinite(p) && std::abs(p) < 10) return p_series_test(expr, var);
    const std::string ratio = series_convergence(expr, var);
    if (ratio == "绝对收敛") return "convergent";
    if (ratio == "发散") return "divergent";
    return "inconclusive";
}

/* ── 数列乘积与绝对收敛 ────────────────────────────────────────────────────
 * 复用上面的 eval_n()：通项在整数 n 处的值（SymEngine 整数代换）。
 */

double product_sequence(const std::string& expr, const std::string& var,
                        long long a, long long b) {
    if (b < a) return 1.0;          // 空积约定
    if (b - a > 100000) throw std::invalid_argument("乘积项数过多（上限 100000）");
    double p = 1.0;
    for (long long k = a; k <= b; ++k) {
        const double t = eval_n(expr, var, (double)k);
        if (!std::isfinite(t)) {
            if (k == a) throw std::invalid_argument("通项在该处无定义");
            break;                  // 后面的项算不动了，停在已算出的部分
        }
        p *= t;
        if (!std::isfinite(p) || p == 0.0) return p;   // 上溢/下溢：直接给结果
    }
    return p;
}

InfiniteProductResult infinite_product(const std::string& expr,
                                       const std::string& var) {
    InfiniteProductResult r;
    const long long ns[] = {10, 100, 1000, 10000};
    double part = 1.0;
    double last_dev = 1.0;
    bool all_finite = true;
    long long k = 1;
    for (int i = 0; i < 4; ++i) {
        for (; k <= ns[i]; ++k) {
            const double t = eval_n(expr, var, (double)k);
            if (!std::isfinite(t)) { all_finite = false; break; }
            part *= t;
            last_dev = std::abs(t - 1.0);
        }
        if (!all_finite) break;
    }
    r.value = part;

    if (!all_finite) {
        r.converges = false;
        r.note = "通项在部分整数处无定义或数值溢出，无法判定";
        return r;
    }
    // 收敛的必要条件：a_n → 1
    if (last_dev > 1e-6) {
        r.converges = false;
        r.note = "通项不趋于 1（n=10000 处 |a_n - 1| ≈ " + std::to_string(last_dev) +
                 "），无穷乘积必发散 —— 这是收敛的必要条件。";
        return r;
    }
    const bool stable = std::isfinite(part) && std::abs(part) > 1e-300;
    r.converges = stable;
    r.note = stable
        ? "通项趋于 1（n=10000 处 |a_n - 1| ≈ " + std::to_string(last_dev) +
          "），部分积到 n=10000 为 " + std::to_string(part) +
          "；数值上收敛（严格判定需对 Σ ln a_n 用级数判别法）。"
        : "部分积已上溢或下溢为 0，实际发散。";
    return r;
}

std::string absolute_convergence(const std::string& expr, const std::string& var) {
    // 主用**柯西凝聚后的指数估计**：见 estimate_p_condensed 的说明 ——
    // 对数因子被吸收成常数，1/(n·ln n) 能被正确判为发散（旧法误判收敛）。
    const double p = estimate_p_condensed(expr, var);
    if (std::isfinite(p) && std::abs(p) < 500.0) {
        std::ostringstream os;
        os << (p > 1.0 ? "绝对收敛" : "发散") << "（柯西凝聚后按 b_k = 2^k·a(2^k) 估指数 P ≈ "
           << p << (p > 1.0 ? " > 1，故 Σ|aₙ| 收敛" : " ≤ 1，故 Σ|aₙ| 发散") << "）";
        return os.str();
    }

    // 补充：比值法（p 估计不好用时才用），只在 |r-1| 明显时下结论
    double r = std::numeric_limits<double>::quiet_NaN();
    for (long long n : {1000000LL, 100000LL, 10000LL, 1000LL}) {
        const double a1 = std::abs(eval_n(expr, var, (double)n));
        const double a2 = std::abs(eval_n(expr, var, (double)(n + 1)));
        if (std::isfinite(a1) && std::isfinite(a2) && a1 > 0.0) { r = a2 / a1; break; }
    }
    if (std::isfinite(r)) {
        if (r < 1.0 - 1e-3)
            return "绝对收敛（比值法：lim |a_{n+1}/a_n| ≈ " + std::to_string(r) + " < 1）";
        if (r > 1.0 + 1e-3)
            return "发散（比值法：lim |a_{n+1}/a_n| ≈ " + std::to_string(r) +
                   " > 1，通项不趋于 0）";
    }
    return std::string("无法判定（p-级数与比值法都不适用") +
           (std::isfinite(r) ? "，r ≈ " + std::to_string(r) : "") +
           "；建议换积分判别法）";
}

}  // namespace mf::calculus
