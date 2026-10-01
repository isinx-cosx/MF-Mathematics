#include "analysis.h"

#include "../calculus/integrals.h"
#include "../calculus/limits.h"

#include <algorithm>
#include <cmath>
#include <complex>
#include <functional>
#include <limits>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <utility>

#include <Eigen/Dense>
#include <Eigen/Eigenvalues>

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/derivative.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/lambda_double.h>
#include <symengine/mul.h>
#include <symengine/parser.h>
#include <symengine/pow.h>
#include <symengine/real_double.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>
#include <symengine/visitor.h>

namespace mf::extras {

namespace {

const double kNaN = std::numeric_limits<double>::quiet_NaN();

double eval_basic(const SymEngine::RCP<const SymEngine::Basic>& e,
                  const std::string& var, double x) {
    try {
        const auto v = SymEngine::real_double(x);
        const auto s = e->subs({{SymEngine::symbol(var), v}});
        return SymEngine::eval_double(*s);
    } catch (...) {
        return kNaN;
    }
}

double eval_at(const std::string& expr, const std::string& var, double x) {
    try {
        return eval_basic(SymEngine::parse(expr), var, x);
    } catch (...) {
        return kNaN;
    }
}

/** 一阶导（符号求导优先，失败退中心差分） */
double deriv1(const std::string& expr, const std::string& var, double x, int order = 1) {
    try {
        auto e = SymEngine::parse(expr);
        const auto sym = SymEngine::symbol(var);
        for (int i = 0; i < order; ++i) e = SymEngine::diff(e, sym);
        const double v = eval_basic(e, var, x);
        if (std::isfinite(v)) return v;
    } catch (...) {
    }
    const double h = order == 1 ? 1e-5 : 1e-4;
    if (order == 1) {
        const double f1 = eval_at(expr, var, x + h), f0 = eval_at(expr, var, x - h);
        return (f1 - f0) / (2 * h);
    }
    const double f1 = eval_at(expr, var, x + h), f0 = eval_at(expr, var, x),
                 fm = eval_at(expr, var, x - h);
    return (f1 - 2 * f0 + fm) / (h * h);
}

/** 去掉引擎不定积分结果里自带的积分常数："-x + C" → "-x"、"C + sin(x)" → "sin(x)" */
std::string strip_integration_constant(const std::string& s) {
    std::string out = s;
    const std::string pats[] = {" + C", "- C", "+C", "-C", "C + ", "C - "};
    for (const auto& p : pats) {
        std::size_t pos;
        while ((pos = out.find(p)) != std::string::npos)
            out.replace(pos, p.size(), p == "C + " ? "" : (p == "C - " ? "-" : ""));
    }
    while (!out.empty() && (out.front() == ' ')) out.erase(out.begin());
    while (!out.empty() && (out.back() == ' ')) out.pop_back();
    if (out.empty()) out = "0";
    return out;
}

// 有效数字取 12 位：渐近线的值要拿来跟 π/2 这类常数比（容差 1e-6），
// 6 位有效数字会把 π/2 打成 1.5708（误差 3.7e-6）直接越界。
std::string num(double v) {    if (!std::isfinite(v)) return v > 0 ? "∞" : (v < 0 ? "-∞" : "未定义");
    std::ostringstream os;
    os.precision(12);
    os << v;
    return os.str();
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 通用工具（一）：复值求值、多项式求根、极点定位
 *
 * 这批工具是 extras 自带的。原先 calc_asymptotes / zeros_and_poles 各自写了一套
 * 「网格点碰巧落在答案上才成立」的扫描：把根/极点当网格上的局部极值去下降，
 * 步长减半一旦没有改进就 break。实测 z²-2 的零点（±√2 不在网格点上）全丢、
 * sin z 只剩 0、x²/(x-1) 的斜渐近线 b 变成 0。这里统一改成
 * 「先解析（多项式/分母）精确化，再数值细化到机器精度」。
 * ═══════════════════════════════════════════════════════════════════════════ */

using Cplx = std::complex<double>;

bool cfinite(const Cplx& z) { return std::isfinite(z.real()) && std::isfinite(z.imag()); }

/** 表达式 → 可反复调用的复函数：用 SymEngine 的 lambda 编译一次，
 *  避免在网格扫描里逐点 subs（120×120 网格 ≈ 1.4 万次 subs 是数量级差别）。
 *  编译不支持的类型时退化为逐点 subs。 */
std::function<Cplx(Cplx)> compile_complex(const SymEngine::RCP<const SymEngine::Basic>& e,
                                          const SymEngine::RCP<const SymEngine::Symbol>& z) {
    try {
        auto v = std::make_shared<SymEngine::LambdaComplexDoubleVisitor>();
        v->init({z}, *e);
        return [v](Cplx t) {
            const std::vector<Cplx> in{t};
            return v->call(in);
        };
    } catch (...) {
        // 落到下面的逐点求值
    }
    return [e, z](Cplx t) {
        try {
            const auto s = e->subs({{z, SymEngine::complex_double(t)}});
            return SymEngine::eval_complex_double(*s);
        } catch (...) {
            return Cplx(kNaN, kNaN);
        }
    };
}

/** 表达式是否含某个符号（出错时按"含"处理，宁可退回通用路径） */
bool has_var(const SymEngine::RCP<const SymEngine::Basic>& e,
             const SymEngine::RCP<const SymEngine::Symbol>& v) {
    try {
        return SymEngine::has_symbol(*e, *v);
    } catch (...) {
        return true;
    }
}

/** as_numer_denom 的安全包装：SymEngine 对 Pow(x, RealDouble) 会无限递归
 *  （栈溢出直接杀进程，limits.cpp 里也有同样的绕行），含浮点幂就不拆。 */
bool safe_numer_denom(const SymEngine::RCP<const SymEngine::Basic>& e,
                      SymEngine::RCP<const SymEngine::Basic>& num,
                      SymEngine::RCP<const SymEngine::Basic>& den) {
    bool float_pow = false;
    std::function<void(const SymEngine::RCP<const SymEngine::Basic>&)> scan =
        [&](const SymEngine::RCP<const SymEngine::Basic>& t) {
            if (SymEngine::is_a<SymEngine::Pow>(*t)) {
                const auto& p = SymEngine::down_cast<const SymEngine::Pow&>(*t);
                if (SymEngine::is_a<SymEngine::RealDouble>(*p.get_exp())) float_pow = true;
            }
            for (const auto& a : t->get_args()) scan(a);
        };
    try {
        scan(e);
        if (float_pow) return false;
        SymEngine::as_numer_denom(e, SymEngine::outArg(num), SymEngine::outArg(den));
        return true;
    } catch (...) {
        return false;
    }
}

// ── 多项式（**降幂**系数：c[0] 是最高次项）───────────────────────────────

Cplx poly_eval(const std::vector<Cplx>& c, const Cplx& z) {
    Cplx r(0.0, 0.0);
    for (const auto& a : c) r = r * z + a;
    return r;
}

Cplx poly_eval_d(const std::vector<Cplx>& c, const Cplx& z) {
    const int n = static_cast<int>(c.size()) - 1;
    Cplx r(0.0, 0.0);
    for (int i = 0; i < n; ++i)
        r = r * z + c[static_cast<std::size_t>(i)] * static_cast<double>(n - i);
    return r;
}

/** 多项式全部复根：Durand–Kerner（同时迭代，互异根收敛很快）+ Newton 抛光。
 *  只用于**平方自由**多项式（重根时 DK 退化成线性收敛），重数由调用方先用精确的
 *  平方自由分解（Yun）单独定出。 */
std::vector<Cplx> poly_roots(std::vector<Cplx> c) {
    while (c.size() > 1 && c.front() == Cplx(0.0, 0.0)) c.erase(c.begin());
    if (c.size() < 2) return {};
    const Cplx lead = c.front();
    if (!cfinite(lead) || std::abs(lead) == 0.0) return {};
    for (auto& v : c) v /= lead;                       // 首一化，改善数值条件
    const int n = static_cast<int>(c.size()) - 1;
    if (n == 1) return {-c[1]};
    if (n == 2) {
        const Cplx b = c[1], cc = c[2];
        const Cplx disc = std::sqrt(b * b - Cplx(4.0, 0.0) * cc);
        return {0.5 * (-b + disc), 0.5 * (-b - disc)};
    }
    std::vector<Cplx> r(static_cast<std::size_t>(n));
    Cplx seed(0.4, 0.9), p(1.0, 0.0);
    for (int i = 0; i < n; ++i) {
        p *= seed;
        r[static_cast<std::size_t>(i)] = p;
    }
    for (int it = 0; it < 500; ++it) {
        double worst = 0.0;
        for (int i = 0; i < n; ++i) {
            auto& zi = r[static_cast<std::size_t>(i)];
            const Cplx f = poly_eval(c, zi);
            Cplx den(1.0, 0.0);
            for (int j = 0; j < n; ++j)
                if (j != i) den *= (zi - r[static_cast<std::size_t>(j)]);
            if (std::abs(den) < 1e-300) den = Cplx(1e-300, 0.0);
            const Cplx step = f / den;
            if (!cfinite(step)) break;
            zi -= step;
            worst = std::max(worst, std::abs(step));
        }
        if (worst < 1e-15) break;
    }
    for (int i = 0; i < n; ++i) {                       // Newton 抛光
        auto& zi = r[static_cast<std::size_t>(i)];
        for (int it = 0; it < 60; ++it) {
            const Cplx df = poly_eval_d(c, zi);
            if (std::abs(df) < 1e-300) break;
            const Cplx step = poly_eval(c, zi) / df;
            if (!cfinite(step)) break;
            zi -= step;
            if (std::abs(step) <= 1e-16 * (1.0 + std::abs(zi))) break;
        }
    }
    return r;
}

// ── 表达式 → 数值系数多项式 ──────────────────────────────────────────────

bool collect_poly_term(const SymEngine::RCP<const SymEngine::Basic>& t,
                       const SymEngine::RCP<const SymEngine::Symbol>& v, int deg,
                       const Cplx& coef, std::map<int, Cplx>& out, int depth) {
    if (depth > 64) return false;
    if (!has_var(t, v)) {                               // 纯常数 → 数值化
        try {
            out[deg] += coef * SymEngine::eval_complex_double(*t);
        } catch (...) {
            return false;
        }
        return true;
    }
    if (SymEngine::eq(*t, *v)) {
        out[deg + 1] += coef;
        return true;
    }
    if (SymEngine::is_a<SymEngine::Add>(*t)) {
        for (const auto& a : t->get_args())
            if (!collect_poly_term(a, v, deg, coef, out, depth + 1)) return false;
        return true;
    }
    if (SymEngine::is_a<SymEngine::Mul>(*t)) {
        int d = deg;
        Cplx cc = coef;
        for (const auto& f : t->get_args()) {
            if (!has_var(f, v)) {
                try {
                    cc *= SymEngine::eval_complex_double(*f);
                } catch (...) {
                    return false;
                }
                continue;
            }
            if (SymEngine::eq(*f, *v)) {
                ++d;
                continue;
            }
            if (SymEngine::is_a<SymEngine::Pow>(*f)) {
                const auto& pw = SymEngine::down_cast<const SymEngine::Pow&>(*f);
                if (SymEngine::eq(*pw.get_base(), *v) &&
                    SymEngine::is_a<SymEngine::Integer>(*pw.get_exp())) {
                    const long long iv =
                        SymEngine::down_cast<const SymEngine::Integer&>(*pw.get_exp()).as_int();
                    if (iv < 0 || iv > 64) return false;
                    d += static_cast<int>(iv);
                    continue;
                }
            }
            return false;                               // 含 v 的非常数因子 → 不是多项式
        }
        out[d] += cc;
        return true;
    }
    /* v 的整数次幂。**必须放在顶层**：原来的实现只在 Mul 因子内部认 Pow，
     *  于是 Add 的直接项 x**2（"1+x**2"、"x**2-1" 展开后都是 Add(1/±1, x**2)）
     *  掉到最后的 return false —— 分母 1+x²、x²-1 全被判成"不是多项式"，
     *  有理函数积分表整条路径失效（∫dx/(1+x²) 因此永远拿不到 atan(x)）。 */
    if (SymEngine::is_a<SymEngine::Pow>(*t)) {
        const auto& pw = SymEngine::down_cast<const SymEngine::Pow&>(*t);
        if (SymEngine::eq(*pw.get_base(), *v) &&
            SymEngine::is_a<SymEngine::Integer>(*pw.get_exp())) {
            const long long iv =
                SymEngine::down_cast<const SymEngine::Integer&>(*pw.get_exp()).as_int();
            if (iv < 0 || iv > 64) return false;
            out[deg + static_cast<int>(iv)] += coef;
            return true;
        }
        return false;                                   // 非常数指数（x**y、√x…）→ 不是多项式
    }
    return false;
}

/** 表达式 → var 的幂系数（数值化）。返回真即「以 var 为变元的数值系数多项式」，
 *  传进来的表达式先 expand（(z-1)*(z+2) 这类乘积必须展开成幂和）。 */
bool poly_coeffs(const SymEngine::RCP<const SymEngine::Basic>& e,
                 const SymEngine::RCP<const SymEngine::Symbol>& v,
                 std::map<int, Cplx>& out) {
    out.clear();
    SymEngine::RCP<const SymEngine::Basic> ex;
    try {
        ex = SymEngine::expand(e);
    } catch (...) {
        return false;
    }
    if (!collect_poly_term(ex, v, 0, Cplx(1.0, 0.0), out, 0)) return false;
    for (auto it = out.begin(); it != out.end();) {
        if (it->second == Cplx(0.0, 0.0)) it = out.erase(it);
        else ++it;
    }
    for (const auto& kv : out)
        if (!cfinite(kv.second) || kv.first < 0) return false;
    return !out.empty();
}

/** 幂系数表（升幂）→ 降幂系数向量 */
std::vector<Cplx> coeffs_desc(const std::map<int, Cplx>& m) {
    const int hi = m.rbegin()->first;
    std::vector<Cplx> out(static_cast<std::size_t>(hi) + 1, Cplx(0.0, 0.0));
    for (const auto& kv : m)
        if (kv.first >= 0 && kv.first <= hi)
            out[static_cast<std::size_t>(hi - kv.first)] = kv.second;
    return out;
}

/** 圆盘 |z - center| ≤ radius 内的全部零点：网格取 |g| 的小值点当起点，
 *  再用 Newton（符号导数）细化。网格分辨率只决定「能不能找到」，
 *  精度完全由 Newton 决定 —— 这正是原实现缺的一环。 */
std::vector<Cplx> roots_in_disc(const std::function<Cplx(Cplx)>& g,
                                const std::function<Cplx(Cplx)>& dg,
                                const Cplx& center, double radius) {
    const int N = 120;
    const double h = 2.0 * radius / static_cast<double>(N);
    const auto at = [&](int i, int j) {
        return center + Cplx(-radius + h * i, -radius + h * j);
    };
    const std::size_t sz = static_cast<std::size_t>(N) + 1;
    std::vector<std::vector<double>> val(sz, std::vector<double>(sz, kNaN));
    double scale = 0.0;
    for (int i = 0; i <= N; ++i) {
        for (int j = 0; j <= N; ++j) {
            const double u = -radius + h * i, v = -radius + h * j;
            if (u * u + v * v > radius * radius) continue;
            const Cplx w = g(at(i, j));
            if (!cfinite(w)) continue;
            const double a = std::abs(w);
            val[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)] = a;
            scale = std::max(scale, a);
        }
    }
    const double accept = 1e-9 * std::max(1.0, scale);
    std::vector<std::pair<double, Cplx>> cand;
    for (int i = 1; i < N; ++i) {
        for (int j = 1; j < N; ++j) {
            const double m = val[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)];
            if (!std::isfinite(m)) continue;
            bool locmin = true;
            for (int di = -1; di <= 1 && locmin; ++di) {
                for (int dj = -1; dj <= 1; ++dj) {
                    if (di == 0 && dj == 0) continue;
                    const double n = val[static_cast<std::size_t>(i + di)]
                                        [static_cast<std::size_t>(j + dj)];
                    if (std::isfinite(n) && n < m) {
                        locmin = false;
                        break;
                    }
                }
            }
            if (locmin) cand.push_back({m, at(i, j)});
        }
    }
    std::sort(cand.begin(), cand.end(),
              [](const std::pair<double, Cplx>& a, const std::pair<double, Cplx>& b) {
                  return a.first < b.first;
              });
    if (cand.size() > 100) cand.resize(100);
    std::vector<Cplx> out;
    for (const auto& c : cand) {
        Cplx z = c.second;
        for (int it = 0; it < 200; ++it) {
            if (std::abs(z) > 1e12) break;
            const Cplx fv = g(z);
            if (!cfinite(fv)) break;
            const Cplx dv = dg(z);
            if (!cfinite(dv) || std::abs(dv) < 1e-300) break;
            const Cplx step = fv / dv;
            if (!cfinite(step)) break;
            z -= step;
            if (std::abs(step) <= 1e-15 * (1.0 + std::abs(z))) break;
        }
        const Cplx fv = g(z);
        if (!cfinite(fv) || std::abs(fv) > accept) continue;      // 必须真的到 0
        if (std::abs(z - center) > radius * (1.0 + 1e-9)) continue;
        bool dup = false;
        for (const auto& q : out)
            if (std::abs(q - z) < 1e-7 * (1.0 + radius)) {
                dup = true;
                break;
            }
        if (!dup) out.push_back(z);
        if (out.size() >= 16) break;
    }
    return out;
}

/** 实轴区间 [a,b] 上的全部实根（网格起点 + Newton），用于非多项式分母。 */
std::vector<double> real_roots_on(const std::function<Cplx(Cplx)>& g,
                                  const std::function<Cplx(Cplx)>& dg, double a, double b) {
    const int N = 4000;
    const double h = (b - a) / static_cast<double>(N);
    std::vector<double> val(static_cast<std::size_t>(N) + 1, kNaN);
    double scale = 0.0;
    for (int i = 0; i <= N; ++i) {
        const Cplx w = g(Cplx(a + h * i, 0.0));
        if (!cfinite(w)) continue;
        val[static_cast<std::size_t>(i)] = std::abs(w);
        scale = std::max(scale, val[static_cast<std::size_t>(i)]);
    }
    const double accept = 1e-9 * std::max(1.0, scale);
    std::vector<double> out;
    for (int i = 1; i < N; ++i) {
        const double m = val[static_cast<std::size_t>(i)];
        if (!std::isfinite(m)) continue;
        const double l = val[static_cast<std::size_t>(i - 1)],
                     r = val[static_cast<std::size_t>(i + 1)];
        if ((std::isfinite(l) && l < m) || (std::isfinite(r) && r < m)) continue;
        Cplx z(a + h * i, 0.0);
        for (int it = 0; it < 100; ++it) {
            const Cplx fv = g(z);
            if (!cfinite(fv)) break;
            const Cplx dv = dg(z);
            if (!cfinite(dv) || std::abs(dv) < 1e-300) break;
            const Cplx step = fv / dv;
            if (!cfinite(step)) break;
            z -= step;
            if (std::abs(step) <= 1e-15 * (1.0 + std::abs(z))) break;
        }
        const Cplx fv = g(z);
        if (!cfinite(fv) || std::abs(fv) > accept) continue;
        if (z.real() < a - 1e-9 || z.real() > b + 1e-9) continue;
        if (std::abs(z.imag()) > 1e-7 * (1.0 + std::abs(z.real()))) continue;
        bool dup = false;
        for (double q : out)
            if (std::abs(q - z.real()) < 1e-6) {
                dup = true;
                break;
            }
        if (!dup) out.push_back(z.real());
        if (out.size() >= 24) break;
    }
    return out;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 通用工具（二）：精确有理数 → 表达式文本、有理函数积分
 * ═══════════════════════════════════════════════════════════════════════════ */

/** 数值 → 表达式片段：能写成小分母有理数就写成 "p/q"（关键！
 *  实数的近似文本会让「解代回原式残差 = 0」变成残差 ≈ 1e-12，
 *  而核验要求**精确**为 0），否则退回 12 位有效数字。 */
std::string exact_num(double v) {
    if (!std::isfinite(v)) return num(v);
    if (v == 0.0) return "0";
    const double r = std::round(v);
    if (std::abs(v - r) < 1e-12 * std::max(1.0, std::abs(v)) && std::abs(r) < 1e15)
        return num(r);
    // 连分数逼近（分母 ≤ 1e6，误差 ≤ 1e-12）
    long long p0 = 0, q0 = 1, p1 = 1, q1 = 0;
    double x = v;
    for (int i = 0; i < 40; ++i) {
        const double a = std::floor(x);
        if (!std::isfinite(a) || std::abs(a) > 1e15) break;
        const long long ai = static_cast<long long>(a);
        const long long p2 = ai * p1 + p0, q2 = ai * q1 + q0;
        if (q2 != 0 && std::abs(static_cast<double>(p2) / static_cast<double>(q2) - v) < 1e-12)
            return "(" + std::to_string(p2) + "/" + std::to_string(q2) + ")";
        if (std::abs(q2) > 1000000) break;
        p0 = p1; q0 = q1; p1 = p2; q1 = q2;
        const double frac = x - a;
        if (frac < 1e-15) break;
        x = 1.0 / frac;
    }
    return num(v);
}

/** 系数前缀：1 → ""，-1 → "-"，其它 → "c*" */
std::string coef_prefix(double c) {
    if (std::abs(c - 1.0) < 1e-14) return "";
    if (std::abs(c + 1.0) < 1e-14) return "-";
    return exact_num(c) + "*";
}

/** 多项式的积分（升幂系数），结果直接是表达式文本 */
std::string integrate_polynomial(const std::vector<double>& c, const std::string& v) {
    std::string out;
    for (std::size_t k = 0; k < c.size(); ++k) {
        if (std::abs(c[k]) < 1e-300) continue;
        const double coef = c[k] / static_cast<double>(k + 1);
        std::string body;
        if (k == 0) body = v;
        else if (k == 1) body = v + "**2";
        else body = v + "**" + std::to_string(k + 1);
        const std::string term = coef_prefix(coef) + body;
        if (out.empty()) out = term;
        else out += (coef > 0 ? " + " + term : " - " + coef_prefix(-coef) + body);
    }
    return out.empty() ? std::string("0") : out;
}

/** ∫ (p1·v + p0)/(a·v² + b·v + c) dv（a ≠ 0），结果是表达式文本 */
std::string integrate_over_quadratic(double a, double b, double c, double p1, double p0,
                                     const std::string& v) {
    const double D = b * b - 4.0 * a * c;
    // (p1 v + p0)/Q = (p1/(2a))·Q'/Q + (p0 - p1·b/(2a))/Q
    const double k1 = p1 / (2.0 * a);
    const double k0 = p0 - k1 * b;
    std::string out;
    if (std::abs(k1) > 1e-14)
        out += coef_prefix(k1) + "log(abs((" + exact_num(a) + "*" + v + "**2 + " +
               exact_num(b) + "*" + v + " + " + exact_num(c) + ")))";
    if (std::abs(k0) > 1e-14) {
        std::string body;
        if (D > 1e-12) {                                  // 两个实根 → 对数
            const double s = std::sqrt(D);
            const double m = 2.0 * a / s, r1 = (b - s) / s, r2 = (b + s) / s;
            body = coef_prefix(k0 / s) + "log(abs((" + coef_prefix(m) + v + " + " +
                   exact_num(r1) + ")/(" + coef_prefix(m) + v + " + " + exact_num(r2) + ")))";
        } else if (D < -1e-12) {                           // 一对共轭复根 → arctan
            const double s = std::sqrt(-D);
            const double m = 2.0 * a / s, r0 = b / s;
            std::string arg;
            if (std::abs(b) < 1e-14)
                arg = (std::abs(m - 1.0) < 1e-14 ? v : "(" + coef_prefix(m) + v + ")");
            else
                arg = "(" + coef_prefix(m) + v + " + " + exact_num(r0) + ")";
            body = coef_prefix(2.0 * k0 / s) + "atan(" + arg + ")";
        } else {                                           // 重根
            body = coef_prefix(-2.0 * k0 / (2.0 * a)) + "/(" + coef_prefix(2.0 * a) + v +
                   " + " + exact_num(b) + ")";
        }
        if (!out.empty()) out += " + ";
        out += body;
    }
    return out.empty() ? std::string("0") : out;
}

/** ∫ (p1·v + p0)/(a·v + b) dv */
std::string integrate_over_linear(double a, double b, double p1, double p0,
                                  const std::string& v) {
    const double k = p1 / a;                                // 商
    const double r = p0 - k * b;                            // 余项系数
    std::string out = coef_prefix(k) + v;
    if (std::abs(r) > 1e-14) {
        if (out != "0") out += " + ";
        out += coef_prefix(r / a) + "log(abs(" + coef_prefix(a) + v + " + " + exact_num(b) + "))";
    }
    return out;
}

/** 把数值系数多项式（升幂）还原成表达式文本；失败返回空串 */
std::string poly_text(const std::vector<double>& c, const std::string& v) {
    std::string out;
    for (std::size_t k = 0; k < c.size(); ++k) {
        if (std::abs(c[k]) < 1e-300) continue;
        std::string body = (k == 0) ? "" : (k == 1 ? v : v + "**" + std::to_string(k));
        const std::string term = (body.empty() ? exact_num(c[k]) : coef_prefix(c[k]) + body);
        if (out.empty()) out = term;
        else out += (c[k] > 0 ? " + " + term : " - " + coef_prefix(-c[k]) + body);
    }
    return out;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 通用工具（三）：x→±∞ 的数值极限
 * ═══════════════════════════════════════════════════════════════════════════ */

enum class InfLimit { finite, no_limit, unknown };

/** x→±∞ 的数值极限。
 *
 *  取 t = 1/|x| 按 1/2 递减（|x| 从 16 一路到 5.4e8），对 t 的幂级数误差做
 *  Richardson 外推，并要求「原始序列差值按几何速度收缩」+「外推前后一致」。
 *  这样 atan(x)（误差 ≈ 1/x）能算到 1e-12，而 sin(x) 这类有界振荡不会被
 *  误判成「收敛到某个值」。 */
InfLimit limit_at_infinity(const std::string& expr, const std::string& var, int sign,
                           double& out) {
    const int K = 26;
    std::vector<double> s;
    s.reserve(static_cast<std::size_t>(K));
    int bad = 0;
    for (int i = 0; i < K; ++i) {
        const double t = std::ldexp(1.0, -(4 + i));
        // sign 是**方向索引**（与调用方 asymptotes 的 dir/target 一致）：0 → +∞、1 → -∞。
        // 原来写的是 `sign >= 0 ? 1.0 : -1.0`，而 sign 只取 0/1，条件恒真 ——
        // 两侧都在 +∞ 采样，于是 atan(x) 的 x→-∞ 侧输出 +π/2（真值 -π/2）、
        // exp(-x) 的 x→-∞ 侧输出 0（真值发散）。
        const double x = (sign == 0 ? 1.0 : -1.0) / t;
        const double v = eval_at(expr, var, x);
        if (!std::isfinite(v)) ++bad;
        s.push_back(v);
    }
    if (bad > K / 4) return InfLimit::unknown;              // 值都算不出来 → 交给上层
    if (bad > 0) return InfLimit::no_limit;                 // 途中发散（如 exp(-x) 在 -∞）
    int good = 0, bad_d = 0;
    for (int i = 1; i + 1 < K; ++i) {
        const double a0 = std::abs(s[static_cast<std::size_t>(i)] -
                                   s[static_cast<std::size_t>(i - 1)]);
        const double a1 = std::abs(s[static_cast<std::size_t>(i + 1)] -
                                   s[static_cast<std::size_t>(i)]);
        if (a0 == 0.0 && a1 == 0.0) ++good;
        else if (a1 <= 0.75 * a0) ++good;
        else ++bad_d;
    }
    if (bad_d > 2 || good < K - 5) return InfLimit::no_limit;   // 振荡 / 不收缩
    std::vector<double> col = s;
    std::vector<double> diag;
    for (int j = 1; j <= 8; ++j) {                          // Richardson（步长减半）
        const double denom = std::ldexp(1.0, j) - 1.0;
        for (int i = K - 1; i >= j; --i)
            col[static_cast<std::size_t>(i)] +=
                (col[static_cast<std::size_t>(i)] - col[static_cast<std::size_t>(i - 1)]) /
                denom;
        diag.push_back(col[static_cast<std::size_t>(K - 1)]);
    }
    const double L = diag.back();
    if (!std::isfinite(L)) return InfLimit::no_limit;
    const double scale = std::max(1.0, std::abs(L));
    for (std::size_t i = 1; i < diag.size(); ++i)
        if (!std::isfinite(diag[i]) || std::abs(diag[i] - L) > 1e-6 * scale)
            return InfLimit::no_limit;                      // 外推不稳定
    out = L;
    return InfLimit::finite;
}

/** f 在 x0 附近是否真的趋向 ∞（用来区分极点与可去奇点）：
 *  只比较「距离缩小 100 倍后 |f| 是否长大 20 倍以上」——量纲无关，
 *  所以系数很小的极点（0.001/(x-2)）也认得出来，而 (x²-1)/(x-1) 这种
 *  可去奇点会被正确排除。 */
bool blows_up_at(const std::string& expr, const std::string& var, double x0) {
    const double d = std::max(1e-4, 1e-6 * std::abs(x0));
    double near_max = 0.0, far_max = 0.0;
    bool near_inf = false;
    for (double s : {-1.0, 1.0}) {
        const double vn = std::abs(eval_at(expr, var, x0 + s * d));
        if (!std::isfinite(vn)) near_inf = true;
        else near_max = std::max(near_max, vn);
        const double vf = std::abs(eval_at(expr, var, x0 + s * 100.0 * d));
        if (std::isfinite(vf)) far_max = std::max(far_max, vf);
    }
    if (near_inf) return true;
    return near_max > 20.0 * std::max(far_max, 1e-300);
}

/** 在 [x1,x2] 上用三分搜索把 |f| 的极大点逼到机器精度（极点处 |f| → ∞） */
double locate_blowup(const std::string& expr, const std::string& var, double x1, double x2) {
    double a = x1, b = x2;
    for (int it = 0; it < 200 && b - a > 0.0; ++it) {
        const double m1 = a + (b - a) / 3.0, m2 = b - (b - a) / 3.0;
        double w1 = std::abs(eval_at(expr, var, m1));
        double w2 = std::abs(eval_at(expr, var, m2));
        if (!std::isfinite(w1)) w1 = 1e300;
        if (!std::isfinite(w2)) w2 = 1e300;
        if (w1 < w2) a = m1;
        else b = m2;
    }
    return 0.5 * (a + b);
}


/** 在 [a,b] 上找 g 的**变号点**（数值求根，二分细化）。
 *
 *  判据只看「左右两侧的符号是否相反」。采样点恰好落在 g = 0 上**不算**变号点：
 *  那样会把 f = x⁴（f'' = 12x²，恒 ≥ 0，x = 0 不是拐点）误报成有拐点。
 *  零点采样直接跳过（既不作为依据，也不刷新上一点），由它两侧的**非零**采样点
 *  决定：符号相反才二分细化，符号相同就不是拐点。 */
template <typename G>
std::vector<double> roots_by_sign_change(G g, double a, double b, int n = 2000) {
    std::vector<double> out;
    double xp = a, gp = g(a);
    const double tol0 = 1e-12;
    for (int i = 1; i <= n; ++i) {
        const double x = a + (b - a) * (double)i / (double)n;
        const double gv = g(x);
        if (!std::isfinite(gv)) {   // 无定义点：不能跨过去比较符号
            xp = x; gp = gv;
            continue;
        }
        if (std::abs(gv) < tol0) continue;   // 恰好落在根上：跳过，等两侧的非零采样
        if (std::isfinite(gp) && std::abs(gp) >= tol0 && ((gp < 0) != (gv < 0))) {
            double lo = xp, hi = x, gl = gp;
            for (int it = 0; it < 80; ++it) {
                const double mid = 0.5 * (lo + hi);
                const double gm = g(mid);
                if (!std::isfinite(gm)) break;
                if ((gl < 0) != (gm < 0)) { hi = mid; } else { lo = mid; gl = gm; }
            }
            out.push_back(0.5 * (lo + hi));
        }
        xp = x; gp = gv;
    }
    std::vector<double> uniq;   // 相邻网格点都落在根上时会重复
    for (double v : out) {
        bool dup = false;
        for (double u : uniq)
            if (std::abs(u - v) < (b - a) / n * 1.5) { dup = true; break; }
        if (!dup) uniq.push_back(v);
    }
    return uniq;
}

}  // namespace

/* ── 凹凸性 ─────────────────────────────────────────────────────────────── */

ConcavityResult concavity(const std::string& expr, const std::string& var,
                          double a, double b) {
    if (!(b > a)) throw std::invalid_argument("区间必须满足 b > a");
    ConcavityResult r;
    r.a = a; r.b = b;
    const int n = 40;
    // 逐段取中点判断 f'' 的符号，并把相邻同号段合并
    int cur = 0;               // 1: 凹(下凸, f''>0), -1: 凸(上凸, f''<0), 0: 无法判定
    double seg_start = a;
    for (int i = 0; i < n; ++i) {
        const double xm = a + (b - a) * ((double)i + 0.5) / (double)n;
        const double d2 = deriv1(expr, var, xm, 2);
        int s = 0;
        if (std::isfinite(d2)) s = d2 > 1e-9 ? 1 : (d2 < -1e-9 ? -1 : 0);
        if (s != cur) {
            if (cur != 0 && i > 0) {
                const double seg_end = a + (b - a) * (double)i / (double)n;
                r.segments.push_back("(" + num(seg_start) + ", " + num(seg_end) + ") 上 f''" +
                                     (cur > 0 ? "> 0，曲线凹（下凸，开口向上）"
                                              : "< 0，曲线凸（上凸，开口向下）"));
            }
            cur = s;
            seg_start = a + (b - a) * (double)i / (double)n;
        }
    }
    if (cur != 0)
        r.segments.push_back("(" + num(seg_start) + ", " + num(b) + ") 上 f''" +
                             (cur > 0 ? "> 0，曲线凹（下凸，开口向上）"
                                      : "< 0，曲线凸（上凸，开口向下）"));
    if (r.segments.empty()) {
        r.conclusion = "在 [" + num(a) + ", " + num(b) + "] 上 f'' 恒为 0 或无定义，"
                       "无法判定凹凸性；拐点请单独用「拐点」模式查。";
    } else {
        r.conclusion = "在 [" + num(a) + ", " + num(b) + "] 上按 f'' 的符号分段共 " +
                       std::to_string(r.segments.size()) + " 段（分段点的左右两侧 f'' 变号，"
                       "那里通常是拐点）。";
    }
    return r;
}

/* ── 拐点 ───────────────────────────────────────────────────────────────── */

InflectionResult inflection_points(const std::string& expr, const std::string& var,
                                   double a, double b) {
    if (!(b > a)) throw std::invalid_argument("区间必须满足 b > a");
    InflectionResult r;
    r.a = a; r.b = b;
    const auto g = [&](double x) { return deriv1(expr, var, x, 2); };
    for (double x : roots_by_sign_change(g, a, b)) {
        const double y = eval_at(expr, var, x);
        if (std::isfinite(y)) r.points.push_back({x, y});
    }
    r.note = r.points.empty()
        ? "在 [" + num(a) + ", " + num(b) + "] 上没找到 f'' 变号的点（数值扫描 2000 个采样点）"
        : "数值结果：f'' 在该区间上变号 " + std::to_string(r.points.size()) +
          " 次，对应点为下表（判定标准是 f'' 变号且函数在该点连续）。";
    return r;
}

/* ── 渐近线 ─────────────────────────────────────────────────────────────── */

AsymptoteResult asymptotes(const std::string& expr, const std::string& var) {
    AsymptoteResult r;
    const double lo = -50.0, hi = 50.0;

    /* ── 垂直渐近线 ──────────────────────────────────────────────────────
     * 主路径是**解析**的：把 f 拆成 num/den，分母的实根就是候选极点
     * （多项式分母用 Durand–Kerner，非多项式分母在实轴上数值求根）。
     * 兜底路径是数值扫描：相邻采样点 |f| 增长 >10³ 或出现不可求值，就用
     * 三分搜索把 |f| 的极大点逼到机器精度。
     * 两条路径的候选都要过 blows_up_at（|f| 真的趋向 ∞），
     * 所以 (x²-1)/(x-1) 在 x=1 的可去奇点不会被当成渐近线。 */
    std::vector<double> verts;
    {
        SymEngine::RCP<const SymEngine::Basic> num, den;
        bool have_den = false;
        try {
            const auto e = SymEngine::parse(expr);
            if (safe_numer_denom(e, num, den) && !SymEngine::eq(*den, *SymEngine::one))
                have_den = true;
        } catch (...) {
            have_den = false;
        }
        if (have_den) {
            const auto vs = SymEngine::symbol(var);
            std::map<int, Cplx> co;
            if (poly_coeffs(den, vs, co)) {
                for (const auto& z : poly_roots(coeffs_desc(co)))
                    if (std::abs(z.imag()) <= 1e-9 * (1.0 + std::abs(z.real())) &&
                        z.real() >= lo && z.real() <= hi)
                        verts.push_back(z.real());
            } else {
                const auto g = compile_complex(den, vs);
                const auto dg = compile_complex(SymEngine::diff(den, vs), vs);
                for (double x : real_roots_on(g, dg, lo, hi)) verts.push_back(x);
            }
        }
    }
    if (verts.size() < 24) {        // 兜底：数值扫描 + 三分细化
        const int n = 4000;
        const double step = (hi - lo) / n;
        double prev_x = lo, prev_v = kNaN;
        for (int i = 0; i <= n; ++i) {
            const double x = lo + step * (double)i;
            const double y = eval_at(expr, var, x);
            if (std::isfinite(prev_v)) {
                const double grow = std::abs(y) / std::max(1e-300, std::abs(prev_v));
                bool suspect = false;
                if (std::isfinite(y) && grow > 1e3) suspect = true;
                else if (!std::isfinite(y) && std::abs(prev_v) > 1.0) suspect = true;
                if (suspect) verts.push_back(locate_blowup(expr, var, prev_x, x));
            }
            prev_x = x; prev_v = y;
        }
    }
    std::vector<double> kept;
    for (double x : verts) {
        if (!std::isfinite(x) || x < lo || x > hi) continue;
        if (!blows_up_at(expr, var, x)) continue;              // 可去奇点排除
        bool dup = false;
        for (double u : kept)
            if (std::abs(u - x) <= 1e-6 * (1.0 + std::abs(x))) { dup = true; break; }
        if (!dup) kept.push_back(x);
        if (kept.size() >= 24) break;
    }
    std::sort(kept.begin(), kept.end());
    for (double x : kept) {
        const double v = std::abs(eval_at(expr, var, x));
        std::string mag;
        if (!std::isfinite(v)) mag = "该处 |f| 不可求值（分母为零）";
        else mag = "该处 |f| ≈ " + num(v);
        r.vertical.push_back("x ≈ " + num(x) + "（" + mag + "，随 x→该值趋向无穷）");
    }

    /* ── 水平 / 斜渐近线：不依赖引擎的符号极限 ────────────────────────────
     * 取 t = 1/|x| 递减，对 t 的幂级数误差做 Richardson 外推（见
     * limit_at_infinity）。原来走引擎的 limit，实测两条都错：
     *   limit("x**2/(x-1) - x", x→±∞) 给 0（真值 1）→ 斜渐近线 b 变 0；
     *   limit("atan(x)", x→∞) 直接抛「不定式「函数在 ∞」暂未实现」→ 水平渐近线全丢。 */
    for (int sign = 0; sign < 2; ++sign) {
        const std::string dir = sign == 0 ? "x→+∞ " : "x→-∞ ";
        double L = kNaN;
        InfLimit st = limit_at_infinity(expr, var, sign, L);
        if (st == InfLimit::finite) {
            r.horizontal.push_back(dir + "时 f → " + num(L) + "，水平渐近线 y = " + num(L));
            continue;   // 有水平渐近线就不必再找斜的
        }
        if (st == InfLimit::unknown) {   // 数值外推无法判定 → 退回引擎符号极限
            const double target = sign == 0 ? std::numeric_limits<double>::infinity()
                                            : -std::numeric_limits<double>::infinity();
            try { L = limit(expr, var, target, ""); } catch (...) { L = kNaN; }
            if (std::isfinite(L)) {
                r.horizontal.push_back(dir + "时 f → " + num(L) + "，水平渐近线 y = " + num(L));
                continue;
            }
        }
        double k = kNaN;
        const std::string kexpr = "((" + expr + ")/(" + var + "))";
        if (limit_at_infinity(kexpr, var, sign, k) != InfLimit::finite) continue;
        const double kr = std::round(k);
        if (std::abs(k - kr) < 1e-9 * std::max(1.0, std::abs(k))) k = kr;   // 消掉浮点噪声
        if (!std::isfinite(k) || std::abs(k) <= 1e-12) continue;
        const std::string bexpr = "((" + expr + ") - (" + exact_num(k) + ")*(" + var + "))";
        double bb = kNaN;
        if (limit_at_infinity(bexpr, var, sign, bb) != InfLimit::finite) continue;
        r.oblique.push_back(dir + "时 k = " + num(k) + "，b = " + num(bb) +
                            "，斜渐近线 y = " + num(k) + "x + " + num(bb));
    }
    r.note = "垂直渐近线按分母的实根定位（多项式分母精确求根；非多项式分母在 ±50 内数值"
             "求根，另有相邻采样点增长比 >10³ 的扫描兜底），并核对 |f| 确实在该处趋向无穷"
             "（可去奇点不算）；水平/斜渐近线用 t=1/|x| 的数值极限 + Richardson 外推"
             "（不依赖符号极限）。某侧没有输出说明该侧没有渐近线。";
    return r;
}

/* ── 曲率与曲率半径 ─────────────────────────────────────────────────────── */

CurvatureResult curvature(const std::string& expr, const std::string& var, double x0) {
    CurvatureResult r;
    r.x = x0;
    r.y = eval_at(expr, var, x0);
    r.dy = deriv1(expr, var, x0, 1);
    r.d2y = deriv1(expr, var, x0, 2);
    if (!std::isfinite(r.y) || !std::isfinite(r.dy) || !std::isfinite(r.d2y))
        throw std::invalid_argument("函数在该点的值或导数无法求出（可能不在定义域内）");
    const double denom = std::pow(1.0 + r.dy * r.dy, 1.5);
    r.curvature = std::abs(r.d2y) / denom;
    if (r.curvature < 1e-12) {
        r.is_straight = true;
        r.radius = std::numeric_limits<double>::infinity();
    } else {
        r.radius = 1.0 / r.curvature;
    }
    return r;
}

/* ── Cauchy 中值定理 ────────────────────────────────────────────────────── */

CauchyMvtResult cauchy_mvt(const std::string& f, const std::string& g,
                           const std::string& var, double a, double b) {
    if (!(b > a)) throw std::invalid_argument("区间必须满足 b > a");
    CauchyMvtResult r;
    const double fa = eval_at(f, var, a), fb = eval_at(f, var, b);
    const double ga = eval_at(g, var, a), gb = eval_at(g, var, b);
    if (!std::isfinite(fa) || !std::isfinite(fb) || !std::isfinite(ga) || !std::isfinite(gb))
        throw std::invalid_argument("函数在端点处无法求值");
    const double dg = gb - ga;
    if (std::abs(dg) < 1e-14) throw std::invalid_argument("g(b) = g(a)，Cauchy 中值定理的条件不满足");
    // H(x) = f'(x)·[g(b)-g(a)] - g'(x)·[f(b)-f(a)]，Cauchy 中值定理就是 H(c) = 0
    const auto H = [&](double x) {
        return deriv1(f, var, x, 1) * dg - deriv1(g, var, x, 1) * (fb - fa);
    };
    const auto roots = roots_by_sign_change(H, a, b, 4000);
    if (roots.empty()) {
        r.note = "在 (a,b) 内没有扫描到 H 的变号点（数值结果；H(x)=f'(x)[g(b)-g(a)]-g'(x)[f(b)-f(a)]）";
        return r;
    }
    r.found = true;
    r.c = roots.front();
    r.lhs = deriv1(f, var, r.c, 1) / deriv1(g, var, r.c, 1);
    r.rhs = (fb - fa) / dg;
    r.note = "数值解 c ≈ " + num(r.c) + "（扫描 " + num(a) + "~" + num(b) +
             " 共 4000 点 + 二分细化）。核对：f'(c)/g'(c) = " +
             num(deriv1(f, var, r.c, 1) / deriv1(g, var, r.c, 1)) +
             "，[f(b)-f(a)]/[g(b)-g(a)] = " + num((fb - fa) / dg);
    return r;
}

/* ── 一阶 ODE ───────────────────────────────────────────────────────────── */

namespace {

/** 引擎的不定积分结果是不是一个能用的表达式。
 *  实测 integrate_indefinite("1/(1+x**2)") **无异常**地返回字面量「未实现」，
 *  原实现把它直接拼进通解，于是用户看到 "y = 未实现 + C" —— 这不是答案，
 *  是垃圾。这里要求结果既能被 SymEngine 解析、又不含「未」这类占位词。 */
bool usable_integral(const std::string& s) {
    if (s.empty()) return false;
    if (s.find("未") != std::string::npos) return false;
    if (s.find("∫") != std::string::npos) return false;
    if (s == "0") return true;
    try {
        SymEngine::parse(s);
    } catch (...) {
        return false;
    }
    return true;
}

/** extras 自带的有理函数不定积分（引擎求不出时的兜底）。
 *  支持：数值系数多项式 / 一次分母 / 二次分母（含商式与余项）。
 *  不是这类形式就返回空串，由调用方如实报错，而不是编一个答案。 */
std::string integrate_rational(const std::string& f, const std::string& var) {
    SymEngine::RCP<const SymEngine::Basic> e;
    try {
        e = SymEngine::parse(f);
    } catch (...) {
        return "";
    }
    const auto v = SymEngine::symbol(var);
    SymEngine::RCP<const SymEngine::Basic> num, den;
    if (!safe_numer_denom(e, num, den)) return "";
    std::map<int, Cplx> cn, cd;
    if (!poly_coeffs(num, v, cn) || !poly_coeffs(den, v, cd)) return "";
    const int dn = cn.rbegin()->first, dd = cd.rbegin()->first;
    std::vector<double> pn(static_cast<std::size_t>(dn) + 1, 0.0), pd(static_cast<std::size_t>(dd) + 1, 0.0);
    for (const auto& kv : cn) {
        if (std::abs(kv.second.imag()) > 1e-12) return "";      // 只处理实系数
        pn[static_cast<std::size_t>(kv.first)] = kv.second.real();
    }
    for (const auto& kv : cd) {
        if (std::abs(kv.second.imag()) > 1e-12) return "";
        pd[static_cast<std::size_t>(kv.first)] = kv.second.real();
    }
    if (dd == 0) return integrate_polynomial(pn, var);           // 分母是常数 → 多项式
    // 带余除法：pn = q·pd + r
    std::vector<double> q(static_cast<std::size_t>(std::max(0, dn - dd)) + 1, 0.0);
    std::vector<double> rem = pn;
    for (int k = dn - dd; k >= 0; --k) {
        const double c = rem[static_cast<std::size_t>(k + dd)] / pd[static_cast<std::size_t>(dd)];
        q[static_cast<std::size_t>(k)] = c;
        for (int j = 0; j <= dd; ++j)
            rem[static_cast<std::size_t>(k + j)] -= c * pd[static_cast<std::size_t>(j)];
    }
    while (!rem.empty() && std::abs(rem.back()) < 1e-300) rem.pop_back();
    std::string out;
    bool any = false;
    if (dn >= dd) {
        std::string qs = integrate_polynomial(q, var);
        if (qs != "0") { out += qs; any = true; }
    }
    if (!rem.empty()) {
        if (dd == 1) {
            std::string rs = integrate_over_linear(pd[1], pd[0], rem.size() > 1 ? rem[1] : 0.0,
                                                   rem[0], var);
            if (any) out += " + " + rs;
            else { out = rs; }
            any = true;
        } else if (dd == 2) {
            std::string rs = integrate_over_quadratic(pd[2], pd[1], pd[0],
                                                      rem.size() > 1 ? rem[1] : 0.0, rem[0], var);
            if (any) out += " + " + rs;
            else { out = rs; }
            any = true;
        } else {
            return "";                                           // 更高次分母：本表不覆盖
        }
    }
    return any ? out : std::string("0");
}

/** ∫ f dvar（**不含**积分常数）。先问引擎，引擎给不出可用结果就用自己的有理函数表；
 *  两条路都不行就抛异常（绝不返回「未实现」这种占位文本）。 */
std::string do_integrate(const std::string& f, const std::string& var) {
    try {
        const std::string got = strip_integration_constant(
            mf::calculus::integrate_indefinite(f, var));
        if (usable_integral(got)) return got;
    } catch (...) {
        // 落到下面的兜底
    }
    const std::string mine = integrate_rational(f, var);
    if (usable_integral(mine)) return mine;
    throw std::invalid_argument("无法求出 ∫(" + f + ") d" + var +
                                " 的解析原函数：引擎的不定积分未覆盖该形式，"
                                "extras 自带的有理函数积分表也不适用");
}

/** 把 f(x,y) 精确拆成 g(x)·h(y)（乘性结构上按因子归属符号），拆不出返回假。
 *  这比原来「除以 f(0,0) 再看比值」稳：f(0,0)=0 时（cos(x)·sin(y)、y²、x·y²）
 *  老判据直接退化，全部落到 unknown。 */
bool separate_product(const SymEngine::RCP<const SymEngine::Basic>& e,
                      const SymEngine::RCP<const SymEngine::Symbol>& xs,
                      const SymEngine::RCP<const SymEngine::Symbol>& ys,
                      SymEngine::RCP<const SymEngine::Basic>& g,
                      SymEngine::RCP<const SymEngine::Basic>& h) {
    using namespace SymEngine;
    std::vector<RCP<const Basic>> xf, yf;
    std::function<bool(const RCP<const Basic>&)> walk = [&](const RCP<const Basic>& t) {
        /* 先拆乘法，再判「同时含两个变量」。顺序反了就等于对**每一个含 y 的右端**
         * 直接返回假：整式 f = cos(x)·sin(y) 的顶层 Mul 同时含 x、y，原来第一句
         * `if (hx && hy) return false;` 立刻命中，Mul 分解根本没机会执行 ——
         * 于是 cos(x)·sin(y)、x·y² 这类标准可分离型全被误判成 unknown。 */
        if (is_a<Mul>(*t)) {
            for (const auto& f : t->get_args())
                if (!walk(f)) return false;
            return true;
        }
        const bool hx = has_var(t, xs), hy = has_var(t, ys);
        if (hx && hy) return false;                 // 单个因子同时含两个变量 → 拆不开
        if (is_a<Pow>(*t) && hx && has_var(down_cast<const Pow&>(*t).get_base(), ys))
            return false;
        if (hx) xf.push_back(t);
        else if (hy) yf.push_back(t);
        else xf.push_back(t);                       // 纯常数并进 g
        return true;
    };
    if (!walk(e)) return false;
    g = one;
    h = one;
    for (const auto& t : xf) g = mul(g, t);
    for (const auto& t : yf) h = mul(h, t);
    return true;
}

/** 由 h(y) 的形状给出**显式**通解（∫dy/h = R + C 再解出 y）。
 *  解析表覆盖常见的几型；不在表内返回空串（调用方给出隐式通解并说明）。 */
std::string separable_explicit(const SymEngine::RCP<const SymEngine::Basic>& h,
                               const SymEngine::RCP<const SymEngine::Symbol>& ys,
                               const std::string& R, const std::string& yv,
                               std::string& how) {
    using namespace SymEngine;
    const RCP<const Basic> y = ys;
    if (eq(*h, *one)) {
        how = "h = 1（右端只含 x）：y = ∫g dx + C";
        return "y = " + R + " + C";
    }
    if (eq(*h, *y)) {
        how = "h = y：∫dy/y = ln|y| ⟹ y = C·e^{∫g dx}";
        return "y = C*exp(" + R + ")";
    }
    if (is_a<Pow>(*h)) {
        const auto& pw = down_cast<const Pow&>(*h);
        if (eq(*pw.get_base(), *y) && is_a<Integer>(*pw.get_exp())) {
            const long long p = down_cast<const Integer&>(*pw.get_exp()).as_int();
            if (p != 1) {
                const double k = 1.0 - static_cast<double>(p);
                how = "h = " + yv + "^" + std::to_string(p) + "：∫" + yv + "^{-" +
                      std::to_string(p) + "}d" + yv + " = " + yv + "^{" + std::to_string(1 - p) +
                      "}/" + std::to_string(1 - p) + "，再解出 " + yv;
                return "y = (" + exact_num(k) + "*(" + R + " + C))**(" + exact_num(1.0 / k) + ")";
            }
        }
    }
    if (eq(*h, *sin(y))) {
        how = "h = sin y：∫dy/sin y = ln|tan(y/2)|，反解 y = 2·atan(C·e^R)";
        return "y = 2*atan(C*exp(" + R + "))";
    }
    if (eq(*h, *cos(y))) {
        how = "h = cos y：∫dy/cos y = ln|tan(y/2 + π/4)|，反解 y = 2·atan(C·e^R) − π/2";
        return "y = 2*atan(C*exp(" + R + ")) - pi/2";
    }
    if (eq(*h, *add(one, pow(y, integer(2))))) {
        how = "h = 1 + y²：∫dy/(1+y²) = atan y，反解 y = tan(R + C)";
        return "y = tan(" + R + " + C)";
    }
    if (eq(*h, *sub(one, pow(y, integer(2))))) {
        how = "h = 1 − y²：∫dy/(1−y²) = artanh y，反解 y = tanh(R + C)";
        return "y = tanh(" + R + " + C)";
    }
    if (eq(*h, *sqrt(sub(one, pow(y, integer(2)))))) {
        how = "h = √(1−y²)：∫dy/√(1−y²) = asin y，反解 y = sin(R + C)";
        return "y = sin(" + R + " + C)";
    }
    how.clear();
    return "";
}

}  // namespace

OdeResult ode_first_order(const std::string& f, const std::string& xvar,
                          const std::string& yvar) {
    OdeResult r;
    SymEngine::RCP<const SymEngine::Basic> e;
    try {
        e = SymEngine::parse(f);
    } catch (const std::exception& ex) {
        throw std::invalid_argument(std::string("右端表达式解析失败：") + ex.what());
    }
    const auto xs = SymEngine::symbol(xvar), ys = SymEngine::symbol(yvar);

    // ① 不含 y → 直接积分 y = ∫f dx + C
    auto fy = [&](double x, double y) {
        try {
            return eval_basic(e->subs({{xs, SymEngine::real_double(x)},
                                       {ys, SymEngine::real_double(y)}}), xvar, x);
        } catch (...) { return kNaN; }
    };
    auto dydy = [&]() -> SymEngine::RCP<const SymEngine::Basic> {
        try { return SymEngine::diff(e, ys); } catch (...) { return SymEngine::integer(0); }
    }();
    const std::string dydy_s = dydy.is_null() ? std::string("0") : SymEngine::str(*dydy);
    if (dydy_s == "0") {
        r.kind = "direct";
        // do_integrate 先剥掉引擎结果里自带的常数（否则出现 "x**2 + C + C"），
        // 拿不到**可用**原函数就抛异常，绝不再拼出 "y = 未实现 + C"。
        const std::string integral = do_integrate(f, xvar);
        r.solution = yvar + " = " + integral + " + C";
        r.note = "右端不含 " + yvar + "，属于直接积分型 y' = f(" + xvar + ")：两边对 " +
                 xvar + " 积分即可。";
        return r;
    }

    // ② 一阶线性 y' = A(x) + B(x)·y
    const bool linear = [&] {
        for (double x : {-2.0, -0.5, 0.3, 1.7, 3.0}) {
            const double A = fy(x, 0.0), B1 = fy(x, 1.0) - fy(x, 0.0);
            for (double y : {-3.0, -0.25, 0.9, 2.5}) {
                const double lhs = fy(x, y);
                if (!std::isfinite(lhs) || !std::isfinite(A) || !std::isfinite(B1)) return false;
                if (std::abs(lhs - (A + B1 * y)) > 1e-6 * (1.0 + std::abs(lhs))) return false;
            }
        }
        return true;
    }();
    if (linear) {
        r.kind = "linear";
        // y' = A(x) + B(x)·y ⇒ y' + P y = Q，P = -B = -∂f/∂y，Q = f(x,0)。
        // 通解 y = (∫μQ dx + C)/μ，μ = e^{∫P dx}。
        // ⚠ 引擎的不定积分结果里**自带积分常数**（返回 "-x + C"），
        //   直接拿去当 ∫P dx 会让 μ = e^{-x+C}、再在外层加一个 C，解就废了
        //   （实测 y'=y 输出了 "y = (0 + C + C)*exp(-(-x + C))"）。所以先剥掉常数。
        std::string P, Q, mu_exp, inner, sol;
        try {
            const std::string By = SymEngine::str(*dydy);
            P = "(-(" + By + "))";
            const auto qexpr = e->subs({{ys, SymEngine::integer(0)}});
            Q = SymEngine::str(*qexpr);
            const std::string Pdx = do_integrate(P, xvar);
            mu_exp = "exp(" + Pdx + ")";
            inner = do_integrate("(" + mu_exp + ")*(" + Q + ")", xvar);
            sol = "y = ( " + inner + " + C ) * exp(-(" + Pdx + "))";
            r.solution = sol;
            r.note = "一阶线性：y' + P(x)y = Q(x)，其中 P = -∂f/∂" + yvar + " = " + P +
                     "，Q = f(" + xvar + ",0) = " + Q + "；积分因子 μ = e^{∫P dx} = " +
                     mu_exp + "。通解 y = (∫μQ d" + xvar + " + C)/μ，上式已代入并化简。";
        } catch (const std::exception& ex) {
            r.solution = "y = e^{-∫P(" + xvar + ")d" + xvar + "} · ( ∫ Q(" + xvar +
                         ")·e^{∫P(" + xvar + ")d" + xvar + "} d" + xvar + " + C )，" +
                         "其中 P = -∂f/∂" + yvar + "，Q = f(" + xvar + ",0)";
            r.note = "识别为一阶线性（∂f/∂" + yvar + " = " + dydy_s +
                     "），但积分因子中的积分无法解析求出（" + ex.what() +
                     "），因此给出通解公式；把 P、Q 代入后逐项积分即可。";
        }
        return r;
    }

    // ③ 可分离 y' = g(x)·h(y)：**符号**判别（把 f 按乘性因子归属到 x 或 y），
    //    不用「除以 f(0,0)」那种在零点退化的数值判据。
    SymEngine::RCP<const SymEngine::Basic> gx, hy;
    if (separate_product(e, xs, ys, gx, hy)) {
        const std::string gs = SymEngine::str(*gx), hs = SymEngine::str(*hy);
        // 抽样复核 g(x)·h(y) 与 f(x,y) 一致（防"拆错"）
        bool agree = true;
        for (double x : {-1.3, 0.6, 2.1}) {
            for (double y : {-2.0, 0.5, 1.4}) {
                const double lhs = fy(x, y);
                if (!std::isfinite(lhs)) continue;
                const double gv = eval_basic(gx->subs({{xs, SymEngine::real_double(x)}}), xvar, x);
                const double hv = eval_basic(hy->subs({{ys, SymEngine::real_double(y)}}), yvar, y);
                if (!std::isfinite(gv) || !std::isfinite(hv) ||
                    std::abs(lhs - gv * hv) > 1e-9 * (1.0 + std::abs(lhs))) { agree = false; break; }
            }
            if (!agree) break;
        }
        if (agree) {
            r.kind = "separable";
            std::string R;
            try {
                R = do_integrate(gs, xvar);
            } catch (const std::exception& ex) {
                r.solution = "（可分离型，但 ∫g(" + xvar + ")d" + xvar + " 求不出解析原函数：" +
                             ex.what() + "）";
                r.note = "可分离型 y' = g(" + xvar + ")·h(" + yvar + ")，g = " + gs +
                         "、h = " + hs + "；分离变量后需要 ∫g d" + xvar + "，引擎无法解析求出。";
                return r;
            }
            std::string how;
            const std::string expl = separable_explicit(hy, ys, R, yvar, how);
            if (!expl.empty()) {
                r.solution = expl;
                r.note = "可分离型 y' = g(" + xvar + ")·h(" + yvar + ")：g = " + gs +
                         "，h = " + hs + "；分离变量 ∫dy/h(" + yvar + ") = ∫g d" + xvar +
                         " + C 后得到 " + how + "。";
            } else {
                r.solution = "∫dy/(" + hs + ") [以 " + yvar + " 为变量] = " + R + " + C（隐式通解）";
                r.note = "可分离型 y' = g(" + xvar + ")·h(" + yvar + ")：g = " + gs +
                         "，h = " + hs + "；h 的原函数/反函数不在本引擎的解析表内，"
                         "因此给出隐式通解（分离变量后两边积分）。";
            }
            return r;
        }
    }

    r.kind = "unknown";
    r.solution = "（未识别出可直接求解的类型）";
    r.note = "本引擎解一阶 ODE 的三类标准型：直接积分 y'=f(x)、可分离 y'=g(x)h(y)、"
             "一阶线性 y'+P(x)y=Q(x)。该右端不属于这三类（符号判别未通过），"
             "可用「ODE数值解」模式求数值解，或先把方程化到上述形式。";
    return r;
}

/* ── 高阶常系数 ODE ─────────────────────────────────────────────────────── */

namespace {

/* 特征多项式的**精确**处理：根与重数是代数事实，不该交给浮点特征值去"猜"。
 * 实测伴随矩阵对 (r+1)³ 给出 -0.999994 与 -1±5.58e-06i：3 重根被当成两对复根，
 * 于是 3 个任意常数变成 5 个。
 * 做法：系数先精确化成整数 → 用有理系数多项式的 Yun 平方自由分解定出「哪个根
 * 是几重」→ 每个**互不相同**的根再用 Durand–Kerner + Newton 算到机器精度。 */

struct Frac {
    long long n = 0, d = 1;   // 已约分，d > 0
};

[[noreturn]] void frac_overflow() {
    throw std::overflow_error("特征多项式精确运算溢出（系数过于悬殊）");
}

long long chk_mul(long long a, long long b) {
    if (a == 0 || b == 0) return 0;
    const long double r = static_cast<long double>(a) * static_cast<long double>(b);
    if (r > 9.0e18L || r < -9.0e18L) frac_overflow();
    return a * b;
}

Frac frac_of(long long n, long long d) {
    if (d == 0) frac_overflow();
    if (d < 0) { n = -n; d = -d; }
    const long long g = std::gcd(n < 0 ? -n : n, d);
    if (g > 1) { n /= g; d /= g; }
    return Frac{n, d};
}

Frac f_add(const Frac& a, const Frac& b) {
    return frac_of(chk_mul(a.n, b.d) + chk_mul(b.n, a.d), chk_mul(a.d, b.d));
}
Frac f_sub(const Frac& a, const Frac& b) {
    return frac_of(chk_mul(a.n, b.d) - chk_mul(b.n, a.d), chk_mul(a.d, b.d));
}
Frac f_mul(const Frac& a, const Frac& b) { return frac_of(chk_mul(a.n, b.n), chk_mul(a.d, b.d)); }
Frac f_div(const Frac& a, const Frac& b) {
    if (b.n == 0) frac_overflow();
    return frac_of(chk_mul(a.n, b.d), chk_mul(a.d, b.n));
}
bool f_zero(const Frac& a) { return a.n == 0; }

using QPoly = std::vector<Frac>;                       // 升幂系数

void qp_trim(QPoly& p) {
    while (!p.empty() && f_zero(p.back())) p.pop_back();
}
int qp_deg(const QPoly& p) { return static_cast<int>(p.size()) - 1; }
bool qp_const(const QPoly& p) { return p.size() <= 1; }

QPoly qp_deriv(const QPoly& p) {
    QPoly out;
    for (std::size_t i = 1; i < p.size(); ++i)
        out.push_back(f_mul(p[i], frac_of(static_cast<long long>(i), 1)));
    qp_trim(out);
    return out;
}

QPoly qp_sub(const QPoly& a, const QPoly& b) {
    QPoly out(std::max(a.size(), b.size()));
    for (std::size_t i = 0; i < out.size(); ++i) {
        const Frac x = i < a.size() ? a[i] : Frac{0, 1};
        const Frac y = i < b.size() ? b[i] : Frac{0, 1};
        out[i] = f_sub(x, y);
    }
    qp_trim(out);
    return out;
}

/** 带余除法（有理系数，总是精确） */
QPoly qp_divmod(const QPoly& a, const QPoly& b, QPoly* rem) {
    QPoly A = a;
    QPoly B = b;
    qp_trim(A);
    qp_trim(B);
    if (B.empty()) frac_overflow();
    QPoly q;
    const int db = qp_deg(B);
    int guard = 0;
    while (!A.empty() && qp_deg(A) >= db && guard++ < 64) {
        const int shift = qp_deg(A) - db;
        const Frac c = f_div(A.back(), B.back());
        if (q.size() <= static_cast<std::size_t>(shift)) q.resize(static_cast<std::size_t>(shift) + 1);
        q[static_cast<std::size_t>(shift)] = f_add(q[static_cast<std::size_t>(shift)], c);
        for (int j = 0; j <= db; ++j)
            A[static_cast<std::size_t>(shift + j)] =
                f_sub(A[static_cast<std::size_t>(shift + j)],
                      f_mul(c, B[static_cast<std::size_t>(j)]));
        qp_trim(A);
    }
    qp_trim(q);
    if (rem) *rem = A;
    return q;
}

QPoly qp_monic(QPoly p) {
    qp_trim(p);
    if (p.empty()) return p;
    const Frac lead = p.back();
    for (auto& c : p) c = f_div(c, lead);
    return p;
}

QPoly qp_gcd(QPoly a, QPoly b) {
    qp_trim(a);
    qp_trim(b);
    int guard = 0;
    while (!b.empty() && !qp_const(b) && guard++ < 32) {
        QPoly r;
        qp_divmod(a, b, &r);
        a = b;
        b = r;
    }
    if (b.empty()) return qp_monic(a);
    return QPoly{frac_of(1, 1)};                      // 余式是常数 → 互素
}

struct SqFactor {
    QPoly poly;
    int mult = 1;
};

/** Yun 平方自由分解：第 i 个因子就是「重数为 i 的那些不可约因子的乘积」，
 *  所以它的根全部互不相同、重数恰好是 i。 */
std::vector<SqFactor> square_free_factors(const QPoly& f) {
    std::vector<SqFactor> out;
    const QPoly a = qp_monic(f);
    const QPoly g = qp_gcd(a, qp_deriv(a));
    QPoly b = qp_divmod(a, g, nullptr);
    QPoly c = qp_divmod(qp_deriv(a), g, nullptr);
    QPoly d = qp_sub(c, qp_deriv(b));
    int i = 1;
    int guard = 0;
    while (!qp_const(b) && !b.empty() && i < 16 && guard++ < 32) {
        const QPoly ai = qp_gcd(b, d);
        const QPoly bnext = qp_divmod(b, ai, nullptr);
        const QPoly cnext = qp_divmod(d, ai, nullptr);
        const QPoly dnext = qp_sub(cnext, qp_deriv(bnext));
        if (!qp_const(ai) && !ai.empty()) out.push_back(SqFactor{ai, i});
        b = bnext;
        d = dnext;
        ++i;
    }
    if (out.empty()) out.push_back(SqFactor{a, 1});   // 兜底：按互异根处理
    return out;
}

/** 系数（double）→ 精确整数系数：每个 double 都是 m·2^E，乘 2^k 后必为整数，
 *  k 取能让所有系数都变成整数的最小值。整数系数让后面的有理运算全程精确。 */
bool to_integer_coeffs(const std::vector<double>& c, std::vector<long long>& out) {
    for (int k = 0; k <= 60; ++k) {
        std::vector<long long> cand;
        bool ok = true;
        for (double v : c) {
            const double s = std::ldexp(v, k);
            if (!std::isfinite(s) || std::abs(s) > 4.0e18) { ok = false; break; }
            const double r = std::round(s);
            if (s != r) { ok = false; break; }
            cand.push_back(static_cast<long long>(r));
        }
        if (ok && !cand.empty()) {
            out = cand;
            return true;
        }
    }
    return false;
}

}  // namespace

HigherOdeResult ode_constant_coefficients(const std::vector<double>& coeffs) {
    // coeffs: [a0, a1, ..., an]（a0 是 y 的系数，an 是最高阶导数的系数）
    if (coeffs.size() < 2) throw std::invalid_argument("至少需要 2 个系数（a₀ y + a₁ y' = 0）");
    const int n = static_cast<int>(coeffs.size()) - 1;
    if (n > 4) throw std::invalid_argument("本实现支持到 4 阶（当前 " + std::to_string(n) + " 阶）");
    if (coeffs[static_cast<std::size_t>(n)] == 0.0)
        throw std::invalid_argument("最高阶导数的系数不能为 0（否则方程不是 " +
                                    std::to_string(n) + " 阶的，阶数要按非零的最高次项算）");
    bool all_zero = true;
    for (double c : coeffs)
        if (c != 0.0) all_zero = false;
    if (all_zero) throw std::invalid_argument("系数不能全为 0（该方程没有给出任何约束）");

    HigherOdeResult r;
    std::ostringstream os;
    for (int i = n; i >= 0; --i) {
        if (i < n) os << " + ";
        os << coeffs[static_cast<std::size_t>(i)] << "·r^" << i;
    }
    r.characteristic = os.str() + " = 0";

    // ── ① 特征根与重数（精确路径：整数化 + Yun 平方自由分解）─────────────
    std::vector<std::pair<Cplx, int>> roots;          // (根, 重数)
    bool exact = false;
    std::vector<long long> icoeff;
    if (to_integer_coeffs(coeffs, icoeff)) {
        try {
            QPoly p(icoeff.size());
            for (std::size_t i = 0; i < icoeff.size(); ++i) p[i] = frac_of(icoeff[i], 1);
            qp_trim(p);
            for (const auto& sf : square_free_factors(p)) {
                std::vector<Cplx> desc(sf.poly.size());
                for (std::size_t i = 0; i < sf.poly.size(); ++i)
                    desc[sf.poly.size() - 1 - i] =
                        Cplx(static_cast<double>(sf.poly[i].n) / static_cast<double>(sf.poly[i].d),
                             0.0);
                for (const auto& z : poly_roots(desc)) roots.push_back({z, sf.mult});
            }
            exact = true;
        } catch (...) {
            roots.clear();
            exact = false;
        }
    }
    if (!exact) {
        // 兜底（系数无法精确整数化）：伴随矩阵特征值 + 就近合并同根
        Eigen::MatrixXd C = Eigen::MatrixXd::Zero(n, n);
        for (int i = 1; i < n; ++i) C(i, i - 1) = 1.0;
        for (int i = 0; i < n; ++i)
            C(i, n - 1) = -coeffs[static_cast<std::size_t>(i)] /
                          coeffs[static_cast<std::size_t>(n)];
        Eigen::EigenSolver<Eigen::MatrixXd> es(C, false);
        for (int i = 0; i < n; ++i) {
            const Cplx z = es.eigenvalues()(i);
            bool merged = false;
            for (auto& pr : roots)
                if (std::abs(pr.first - z) <= 1e-5 * (1.0 + std::abs(z))) {
                    ++pr.second;
                    merged = true;
                    break;
                }
            if (!merged) roots.push_back({z, 1});
        }
    }

    // ── ② 分组：实根各自一组，共轭复根合成一组（实系数 → 非实根必成对）─────
    std::sort(roots.begin(), roots.end(),
              [](const std::pair<Cplx, int>& a, const std::pair<Cplx, int>& b) {
                  return a.first.real() != b.first.real() ? a.first.real() < b.first.real()
                                                          : a.first.imag() < b.first.imag();
              });
    struct Group {
        double alpha = 0.0, beta = 0.0;
        int mult = 1;
    };
    std::vector<Group> groups;
    std::vector<bool> used(roots.size(), false);
    for (std::size_t i = 0; i < roots.size(); ++i) {
        if (used[i]) continue;
        used[i] = true;
        const Cplx z = roots[i].first;
        const int m = roots[i].second;
        const double tol = 1e-8 * (1.0 + std::abs(z));
        if (std::abs(z.imag()) <= tol) {
            groups.push_back(Group{z.real(), 0.0, m});
            continue;
        }
        std::size_t partner = roots.size();
        for (std::size_t j = 0; j < roots.size(); ++j) {
            if (used[j]) continue;
            if (std::abs(roots[j].first.real() - z.real()) <= tol &&
                std::abs(roots[j].first.imag() + z.imag()) <= tol) {
                partner = j;
                break;
            }
        }
        if (partner < roots.size()) {                 // α±βi 合成一个实解模板（2 个常数）
            used[partner] = true;
            groups.push_back(Group{(z.real() + roots[partner].first.real()) / 2.0,
                                   (std::abs(z.imag()) + std::abs(roots[partner].first.imag())) / 2.0,
                                   std::max(m, roots[partner].second)});
        } else {                                      // 配不上对（理论上不会）→ 按实根计
            groups.push_back(Group{z.real(), 0.0, m});
        }
    }

    // ── ③ 通解：常数个数 = Σ 重数 = 方程阶数 n ────────────────────────────
    std::string sol = "y = ";
    int idx = 1;
    bool first = true;
    for (const auto& g : groups) {
        const int m = g.mult;
        const double alpha = (g.alpha == 0.0) ? 0.0 : g.alpha;
        if (g.beta > 1e-12) r.roots.push_back("r = " + num(alpha) + " ± " + num(g.beta) + "i");
        else r.roots.push_back("r = " + num(alpha));
        std::string term;
        if (g.beta <= 1e-12) {                        // 实根（含重根）：x^k·e^{rx} 模板
            std::string inner;
            for (int k = 0; k < m; ++k) {
                inner += (k ? " + " : "") + std::string("C") + std::to_string(idx++);
                if (k == 1) inner += "*x";
                else if (k > 1) inner += "*x^" + std::to_string(k);
            }
            if (m == 1 && alpha == 0.0) term = inner;
            else if (m == 1) term = inner + "·e^{" + num(alpha) + "x}";
            else term = "(" + inner + ")·e^{" + num(alpha) + "x}";
        } else {                                      // 共轭复根：e^{αx}(C cos βx + C' sin βx)
            std::string a1, a2;
            for (int k = 0; k < m; ++k) {
                a1 += (k ? " + " : "") + std::string("C") + std::to_string(idx++);
                a2 += (k ? " + " : "") + std::string("C") + std::to_string(idx++);
                if (k == 1) { a1 += "*x"; a2 += "*x"; }
                else if (k > 1) { a1 += "*x^" + std::to_string(k); a2 += "*x^" + std::to_string(k); }
            }
            const std::string amp = (alpha == 0.0) ? "" : "e^{" + num(alpha) + "x}·";
            term = amp + "(" + a1 + ")·cos(" + num(g.beta) + "x) + " + amp + "(" + a2 +
                   ")·sin(" + num(g.beta) + "x)";
        }
        if (!first) sol += " + ";
        sol += term;
        first = false;
    }
    r.solution = sol;
    return r;
}

/* ── 线性 ODE 组 ────────────────────────────────────────────────────────── */

OdeSystemResult ode_linear_system(const std::vector<std::vector<double>>& A) {
    if (A.empty() || A.size() != A[0].size())
        throw std::invalid_argument("系数矩阵必须为非空方阵");
    const long long n = static_cast<long long>(A.size());
    Eigen::MatrixXd M(n, n);
    for (long long i = 0; i < n; ++i)
        for (long long j = 0; j < n; ++j) M(i, j) = A[static_cast<std::size_t>(i)][static_cast<std::size_t>(j)];
    Eigen::EigenSolver<Eigen::MatrixXd> es(M, true);
    OdeSystemResult r;
    std::ostringstream ev;
    bool all_real = true;
    for (long long i = 0; i < n; ++i) {
        if (i) ev << ", ";
        ev << num(es.eigenvalues()(i).real());
        if (std::abs(es.eigenvalues()(i).imag()) > 1e-9) {
            ev << " ± " << num(std::abs(es.eigenvalues()(i).imag())) << "i";
            all_real = false;
        }
    }
    r.eigenvalues = ev.str();

    std::ostringstream sol;
    if (all_real) {
        sol << "y(t) = ";
        for (long long i = 0; i < n; ++i) {
            if (i) sol << " + ";
            const auto l = es.eigenvalues()(i).real();
            sol << "C" << (i + 1) << "·e^{" << num(l) << "t}·v" << (i + 1);
        }
        r.note = "按特征值给出的实解（v_i 为对应的特征向量，按列取自结果矩阵）。";
    } else {
        sol << "y(t) = Σ C_i·e^{λ_i t}·v_i（λ 为共轭复根时取实部与虚部组成实解："
               "e^{αt}(C₁cos βt - C₂sin βt)·Re v + e^{αt}(C₁sin βt + C₂cos βt)·Im v）";
        r.note = "存在复特征值，实解按 α±βi 的实部/虚部组合（上式给出了标准写法）。";
    }
    r.solution = sol.str();
    return r;
}

/* ── 二阶 PDE 分类 ──────────────────────────────────────────────────────── */

PdeClassResult classify_second_order_pde(double A, double B, double C) {
    PdeClassResult r;
    r.discriminant = B * B - A * C;
    if (A == 0.0 && B == 0.0)
        throw std::invalid_argument("A 与 B 不能同时为 0（该方程不是二阶 PDE）");
    if (r.discriminant > 1e-12) {
        r.type = "双曲线型（hyperbolic）";
        const double sq = std::sqrt(r.discriminant);
        const std::string l1 = "(" + num(B) + " + " + num(sq) + ")/" + num(A);
        const std::string l2 = "(" + num(B) + " - " + num(sq) + ")/" + num(A);
        r.canonical = "特征方程 " + num(A) + "(dy/dx)² - 2" + num(B) + "(dy/dx) + " + num(C) +
                      " = 0，解得 dy/dx = " + l1 + " 与 " + l2 +
                      "；取 ξ = y - (" + l1 + ")x，η = y - (" + l2 + ")x 可化到 u_ξη = 0（标准形）。";
        r.note = "判别式 B²-AC > 0：有两族实特征线，标准形为 u_ξη = Φ。";
    } else if (std::abs(r.discriminant) <= 1e-12) {
        r.type = "抛物型（parabolic）";
        r.canonical = "特征方程有重根 dy/dx = " + num(B / A) +
                      "；取 ξ = y - (" + num(B / A) + ")x，η 任取与 ξ 线性无关的量，"
                      "可化到 u_ηη = Φ（标准形）。";
        r.note = "判别式 B²-AC = 0：只有一族特征线，标准形为 u_ηη = Φ。";
    } else {
        r.type = "椭圆型（elliptic）";
        const std::complex<double> l = std::complex<double>(B, std::sqrt(-r.discriminant)) /
                                       std::complex<double>(A, 0.0);
        r.canonical = "特征方程给出一对共轭复根 dy/dx = " + num(l.real()) + " ± " +
                      num(std::abs(l.imag())) + "i；取 ξ = Re(解)，η = Im(解)，"
                      "可化到 u_ξξ + u_ηη = Φ（标准形）。";
        r.note = "判别式 B²-AC < 0：无实特征线，标准形为 u_ξξ + u_ηη = Φ（如 Laplace 方程）。";
    }
    return r;
}

/* ── 一阶线性 PDE ───────────────────────────────────────────────────────── */

FirstOrderPdeResult first_order_linear_pde(double a, double b, double c) {
    if (a == 0.0 && b == 0.0) throw std::invalid_argument("a 与 b 不能同时为 0");
    FirstOrderPdeResult r;
    r.characteristics = "特征方程 dx/" + num(a) + " = dy/" + num(b) + " = du/" + num(c);
    if (std::abs(c) < 1e-14) {
        // a u_x + b u_y = 0
        r.solution = "u(x,y) = F(" + num(b) + "x - " + num(a) + "y)，F 为任意一元函数";
        r.note = "齐次常系数：沿特征线 " + num(b) + "x - " + num(a) + "y = C 上 u 为常数。";
        return r;
    }
    // 非齐次：沿特征线 du/ds = c，用特征坐标可积出
    if (std::abs(b) > 1e-14) {
        r.solution = "u(x,y) = (" + num(c / b) + ")y + F(" + num(b) + "x - " + num(a) + "y)";
        r.note = "非齐次：取特征坐标 s = (" + num(a) + "x + " + num(b) + "y)/√(a²+b²) 与 t = " +
                 num(b) + "x - " + num(a) + "y，方程化为 du/ds = " + num(c / std::sqrt(a * a + b * b)) +
                 "，积分得 " + num(c / b) + "y + F(t)（F 由初值确定）。";
    } else {
        r.solution = "u(x,y) = (" + num(c / a) + ")x + F(y)";
        r.note = "b = 0：方程退化为 " + num(a) + "u_x = " + num(c) + "，直接对 x 积分。";
    }
    return r;
}

/* ── 复分析：零点与极点 ─────────────────────────────────────────────────── */

ZeroPoleResult zeros_and_poles(const std::string& func,
                               std::complex<double> center, double radius) {
    if (!(radius > 0.0)) throw std::invalid_argument("半径必须为正");
    ZeroPoleResult r;
    SymEngine::RCP<const SymEngine::Basic> e;
    try {
        e = SymEngine::parse(func);
    } catch (const std::exception& ex) {
        throw std::invalid_argument(std::string("复函数解析失败：") + ex.what());
    }
    const auto zs = SymEngine::symbol("z");
    const auto f = compile_complex(e, zs);

    /* 零点 = 分子的根，极点 = 分母的根。
     * 原实现把零点/极点都当成「|f| 或 1/|f| 在 60×60 网格上的局部极小」，
     * 细化时只走"步长减半的下降"，一旦某步没有改进就 break —— 于是**只有恰好
     * 落在网格点上的根**能被找到：z²-2 的 ±√2 全部丢失（把 center 挪到 √2
     * 上就立刻能找出来，正是这个原因）；sin z 只剩 0。 */
    SymEngine::RCP<const SymEngine::Basic> numer = e, denom = SymEngine::one;
    const bool split = safe_numer_denom(e, numer, denom);
    if (!split) numer = e;
    const bool has_den = split && !SymEngine::eq(*denom, *SymEngine::one);
    // 整函数（分母为 1）也要能找到极点（如 tan z）：等价于求 1/f 的零点
    SymEngine::RCP<const SymEngine::Basic> pole_expr =
        has_den ? denom : SymEngine::pow(e, SymEngine::integer(-1));

    const auto find_in_disc = [&](const SymEngine::RCP<const SymEngine::Basic>& target) {
        std::vector<Cplx> out;
        if (target.is_null()) return out;
        std::map<int, Cplx> co;
        if (poly_coeffs(target, zs, co)) {
            // 多项式：直接算全部复根（不依赖任何网格分辨率）
            for (const auto& z : poly_roots(coeffs_desc(co)))
                if (std::abs(z - center) <= radius * (1.0 + 1e-9)) out.push_back(z);
            return out;
        }
        return roots_in_disc(compile_complex(target, zs),
                             compile_complex(SymEngine::diff(target, zs), zs), center, radius);
    };

    // 局部尺度：用来把「|f| 相对邻域小到可以当零点」量化
    const double probe = radius / 20.0;
    const auto local_scale = [&](const Cplx& z) {
        double s = 0.0;
        for (int k = 0; k < 4; ++k) {
            const Cplx w = f(z + std::polar(probe, k * 1.5707963267948966));
            if (cfinite(w)) s = std::max(s, std::abs(w));
        }
        return s;
    };
    /** 极点判据（尺度无关）：距离缩小 100 倍后 |f| 是否涨 4 倍以上。
     *  简单极点涨 ~100 倍、可去奇点几乎不变，所以能区分两者。 */
    const auto is_pole = [&](const Cplx& z) {
        const double d = std::max(radius * 1e-4, 1e-8);
        double near_max = 0.0, far_max = 0.0;
        bool near_inf = false;
        for (int k = 0; k < 8; ++k) {
            const double ang = k * 0.7853981633974483;
            const Cplx wn = f(z + std::polar(d, ang));
            if (!cfinite(wn)) near_inf = true;
            else near_max = std::max(near_max, std::abs(wn));
            const Cplx wf = f(z + std::polar(10.0 * d, ang));
            if (cfinite(wf)) far_max = std::max(far_max, std::abs(wf));
        }
        if (near_inf) return true;
        return near_max > 4.0 * std::max(far_max, 1e-300);
    };

    std::vector<std::pair<double, double>> zeros, poles;
    // ── 零点：分子的根，要求 f 在该处确实为 0（排除分子分母公根的可去奇点）──
    if (numer.is_null() || !SymEngine::eq(*numer, *SymEngine::zero)) {
        for (const auto& z : find_in_disc(numer)) {
            if (zeros.size() >= 16) break;
            const Cplx v = f(z);
            if (!cfinite(v)) continue;                       // f(z) = 0/0 → 不是零点
            if (std::abs(v) > 1e-8 * std::max(1.0, local_scale(z))) continue;
            zeros.push_back({z.real(), z.imag()});
        }
    }
    // ── 极点：分母的根（或 1/f 的零点），要求 |f| 在该处确实趋向 ∞ ──
    for (const auto& z : find_in_disc(pole_expr)) {
        if (poles.size() >= 16) break;
        if (!is_pole(z)) continue;
        poles.push_back({z.real(), z.imag()});
    }

    const auto dedup = [&](std::vector<std::pair<double, double>>& pts, double tol) {
        std::vector<std::pair<double, double>> out;
        for (const auto& p : pts) {
            bool dup = false;
            for (const auto& q : out)
                if (std::hypot(p.first - q.first, p.second - q.second) < tol) { dup = true; break; }
            if (!dup) out.push_back(p);
        }
        return out;
    };
    r.zeros = dedup(zeros, std::max(1e-9, radius * 1e-6));
    r.poles = dedup(poles, std::max(1e-9, radius * 1e-6));
    r.note = "数值结果：在 |z - (" + num(center.real()) + (center.imag() >= 0 ? "+" : "-") +
             num(std::abs(center.imag())) + "i)| ≤ " + num(radius) +
             " 内求零点与极点 —— 零点取分子的根、极点取分母的根（整函数取 1/f 的零点），"
             "并用 |f| 在该点是否为 0（零点）、是否随距离缩小而发散（极点）逐个复核。"
             "多项式用 Durand–Kerner 直接求根、Newton 抛光；非多项式（如 sin z）先用"
             "120×120 网格取 |f| 的小值点当起点再 Newton 细化，精度不受网格分辨率限制。"
             "各取最多 16 个，重根/高阶极点会合并成同一位置。"
             "需要计数时可用「辐角原理」（圆内零点数−极点数）。";
    return r;
}

}  // namespace mf::extras
