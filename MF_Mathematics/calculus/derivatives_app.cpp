#include "derivatives_app.h"
#include "symbolic_util.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/derivative.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

namespace mf::calculus {

namespace {
using SymEngine::RCP;
using SymEngine::Basic;

RCP<const SymEngine::Symbol> sym(const std::string& v) { return SymEngine::symbol(v); }

double eval_at(const std::string& expr, const std::string& var, double x) {
    const auto xs = sym(var);
    const auto sub = SymEngine::parse(expr)->subs({{xs, SymEngine::real_double(x)}});
    return SymEngine::eval_double(*sub);
}

std::string deriv(const std::string& expr, const std::string& var) {
    return SymEngine::str(*SymEngine::diff(SymEngine::parse(expr), sym(var)));
}

double eval_deriv_val(const std::string& expr, const std::string& var, double x) {
    const auto xs = sym(var);
    const auto d = SymEngine::diff(SymEngine::parse(expr), xs);
    const auto sub = d->subs({{xs, SymEngine::real_double(x)}});
    return SymEngine::eval_double(*sub);
}

// 数值二分求 g(x)=0(在 (a,b) 内)。
double bisect(const std::function<double(double)>& g, double a, double b) {
    const int N = 2000;
    double pt = a, pv = g(a);
    for (int i = 1; i <= N; ++i) {
        const double t = a + (b - a) * i / N;
        const double v = g(t);
        if (std::isfinite(pv) && std::isfinite(v) && pv * v < 0.0) {
            double lo = pt, hi = t, flo = pv;
            for (int it = 0; it < 60; ++it) {
                const double m = 0.5 * (lo + hi);
                const double fm = g(m);
                if (!std::isfinite(fm)) break;
                if (flo * fm <= 0.0) { hi = m; } else { lo = m; flo = fm; }
            }
            return 0.5 * (lo + hi);
        }
        pt = t;
        pv = v;
    }
    return std::numeric_limits<double>::quiet_NaN();
}

// f'(x) = target 在 (a, b) 内的实根(SymEngine solve + 数值二分兜底)。
std::vector<double> roots_of_deriv(const std::string& expr,
                                   const std::string& var, double target,
                                   double a, double b) {
    std::vector<double> roots;
    const auto xs = sym(var);
    const auto d = SymEngine::diff(SymEngine::parse(expr), xs);
    const auto eq = SymEngine::sub(d, SymEngine::real_double(target));
    const auto sol = mf::symutil::safe_solve(eq, xs, "驻点方程");
    if (SymEngine::is_a<SymEngine::FiniteSet>(*sol)) {
        const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*sol);
        for (const auto& rt : fs.get_args()) {
            try {
                const double v = SymEngine::eval_double(*rt);
                if (v > a && v < b) roots.push_back(v);
            } catch (...) {
            }
        }
    }
    std::sort(roots.begin(), roots.end());
    roots.erase(std::unique(roots.begin(), roots.end(),
                            [](double p, double q) { return std::abs(p - q) < 1e-8; }),
                roots.end());
    if (!roots.empty()) return roots;
    // 数值二分兜底。
    const auto g = [&](double t) { return eval_deriv_val(expr, var, t) - target; };
    const double xr = bisect(g, a, b);
    if (std::isfinite(xr)) roots.push_back(xr);
    return roots;
}

// 泰勒系数 c_k = f^{(k)}(point)/k!。
std::string coeff_at(const std::string& expr, const std::string& var,
                     double point, long long k) {
    const auto xs = sym(var);
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

std::vector<double> calc_rolle_theorem(const std::string& expr,
                                       const std::string& var, double a, double b) {
    const double fa = eval_at(expr, var, a);
    const double fb = eval_at(expr, var, b);
    if (std::abs(fa - fb) > 1e-10) return {};
    return roots_of_deriv(expr, var, 0.0, a, b);
}

double calc_lagrange_theorem(const std::string& expr, const std::string& var,
                             double a, double b) {
    const double secant = (eval_at(expr, var, b) - eval_at(expr, var, a)) / (b - a);
    const auto roots = roots_of_deriv(expr, var, secant, a, b);
    if (!roots.empty()) return roots[0];
    // 数值二分兜底。
    return bisect([&](double t) { return eval_deriv_val(expr, var, t) - secant; }, a, b);
}

double lhopital_impl(const std::string& expr, const std::string& var,
                     double point, int depth) {
    if (depth > 20)
        throw std::invalid_argument("洛必达迭代过深,无法求极限");
    RCP<const Basic> num, den;
    SymEngine::as_numer_denom(SymEngine::parse(expr), outArg(num), outArg(den));
    // 数值极限(两侧采样)。
    const auto lim = [&](const RCP<const Basic>& e) {
        const auto xs = sym(var);
        double acc = 0.0;
        int cnt = 0;
        for (double h : {1e-4, 1e-5, 1e-6}) {
            const double vl = SymEngine::eval_double(
                *e->subs({{xs, SymEngine::real_double(point - h)}}));
            const double vr = SymEngine::eval_double(
                *e->subs({{xs, SymEngine::real_double(point + h)}}));
            if (std::isfinite(vl) && std::isfinite(vr)) {
                acc += 0.5 * (vl + vr);
                ++cnt;
            }
        }
        return cnt == 0 ? std::numeric_limits<double>::quiet_NaN() : acc / (double)cnt;
    };
    const double nl = lim(num), dl = lim(den);
    const bool indet = (std::abs(nl) < 1e-8 && std::abs(dl) < 1e-8) ||
                       (std::abs(nl) > 1e8 && std::abs(dl) > 1e8);
    if (indet) {
        const auto dn = SymEngine::diff(num, sym(var));
        const auto dd = SymEngine::diff(den, sym(var));
        const std::string ratio = "(" + SymEngine::str(*dn) + ")/(" + SymEngine::str(*dd) + ")";
        return lhopital_impl(ratio, var, point, depth + 1);
    }
    return nl / dl;
}

double lhopital(const std::string& expr, const std::string& var, double point) {
    return lhopital_impl(expr, var, point, 0);
}

std::vector<std::string> monotonicity(const std::string& expr,
                                      const std::string& var) {
    const std::string d = deriv(expr, var);
    const auto xs = sym(var);
    const auto eq = SymEngine::parse(d);
    // 含自由参数时驻点无法数值化（如 √a），显式报错而非静默给出错误区间
    if (mf::symutil::has_other_symbols(*eq, var)) {
        throw std::invalid_argument(
            "表达式含自由参数（" + mf::symutil::join_names(mf::symutil::symbol_names(*eq)) +
            "），单调区间依赖参数取值：请用 solve_sym 得到含参驻点，或指定参数值后再调用");
    }
    const auto sol = mf::symutil::safe_solve(eq, xs, "驻点方程");
    // 精确根字符串与数值根并行保存：前者用于展示（±1 而非 -1.000000），后者用于方向判定
    std::vector<double> crit;
    std::vector<std::string> crit_str;
    if (SymEngine::is_a<SymEngine::FiniteSet>(*sol)) {
        const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*sol);
        for (const auto& rt : fs.get_args()) {
            try {
                crit.push_back(SymEngine::eval_double(*rt));
                crit_str.push_back(SymEngine::str(*rt));
            } catch (...) {
                // 不可数值化的驻点：绝不静默丢弃
                throw std::invalid_argument("驻点 " + SymEngine::str(*rt) +
                                            " 无法数值化，单调区间无法给出数值端点");
            }
        }
    }
    // 按数值排序，并同步精确字符串
    std::vector<std::size_t> idx(crit.size());
    for (std::size_t i = 0; i < idx.size(); ++i) idx[i] = i;
    std::sort(idx.begin(), idx.end(),
              [&](std::size_t a, std::size_t b) { return crit[a] < crit[b]; });
    std::vector<double> sorted_crit;
    std::vector<std::string> sorted_str;
    for (std::size_t i : idx) {
        sorted_crit.push_back(crit[i]);
        sorted_str.push_back(crit_str[i]);
    }
    crit = sorted_crit;
    crit_str = sorted_str;

    std::vector<double> boundaries;
    std::vector<std::string> boundary_str;
    for (std::size_t i = 0; i < crit.size(); ++i) {
        if (boundaries.empty() || crit[i] - boundaries.back() > 1e-8) {
            boundaries.push_back(crit[i]);
            boundary_str.push_back(crit_str[i]);
        }
    }

    // ⚠ f' 的**极点**也必须当分界：x²/(x−1) 的 f' = x(x−2)/(x−1)²，驻点是 0 与 2，
    //   若只按驻点分区间，区间 [0,2] 的中点恰好是极点 x=1，那里 f' 求值得到 NaN
    //   → 被判成"常值"（错），而真值是 (0,1) 递减、(1,2) 递减。
    //   把分母的零点解出来一起作为分界即可（区间变成 [0,1] 与 [1,2]）。
    try {
        SymEngine::RCP<const SymEngine::Basic> dn, dd;
        SymEngine::as_numer_denom(SymEngine::parse(d), SymEngine::outArg(dn),
                                  SymEngine::outArg(dd));
        if (!SymEngine::eq(*dd, *SymEngine::one)) {
            const auto dsol = mf::symutil::safe_solve(dd, xs, "导数极点方程");
            if (SymEngine::is_a<SymEngine::FiniteSet>(*dsol)) {
                const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*dsol);
                for (const auto& rt : fs.get_args()) {
                    double v = 0.0;
                    try {
                        v = SymEngine::eval_double(*rt);
                    } catch (...) {
                        continue;   // 不可数值化的极点跳过（不猜）
                    }
                    if (!std::isfinite(v)) continue;
                    boundaries.push_back(v);
                    boundary_str.push_back(SymEngine::str(*rt));
                }
            }
        }
    } catch (...) {
        // 极点求解失败不致命：退还成"仅按驻点分区间"的老行为
    }
    // 重新排序（驻点 + 极点混在一起）并去重
    {
        std::vector<std::size_t> bi(boundaries.size());
        for (std::size_t i = 0; i < bi.size(); ++i) bi[i] = i;
        std::sort(bi.begin(), bi.end(),
                  [&](std::size_t a, std::size_t b) { return boundaries[a] < boundaries[b]; });
        std::vector<double> bs;
        std::vector<std::string> bst;
        for (std::size_t i : bi) {
            if (bs.empty() || boundaries[i] - bs.back() > 1e-8) {
                bs.push_back(boundaries[i]);
                bst.push_back(boundary_str[i]);
            }
        }
        boundaries = bs;
        boundary_str = bst;
    }

    std::vector<std::string> out;
    const auto direction = [&](double x) -> std::string {
        const double v = eval_at(d, var, x);
        if (!std::isfinite(v)) return std::string("该区间上无法判定（导数在此点无定义）");
        return v > 0 ? std::string("单调递增")
                     : (v < 0 ? std::string("单调递减") : std::string("常值"));
    };
    // 区间内取点：优先中点；中点落在极点上时向两侧挪，避免误判。
    const auto probe = [&](double lo, double hi) {
        const double span = hi - lo;
        for (double frac : {0.5, 0.25, 0.75, 0.125, 0.875}) {
            const double v = eval_at(d, var, lo + span * frac);
            if (std::isfinite(v)) return v;
        }
        return std::numeric_limits<double>::quiet_NaN();
    };
    const auto dir_of = [&](double v) -> std::string {
        if (!std::isfinite(v)) return std::string("该区间上无法判定（导数处处无定义）");
        return v > 0 ? std::string("单调递增")
                     : (v < 0 ? std::string("单调递减") : std::string("常值"));
    };
    if (boundaries.empty()) {
        out.push_back(std::string("(-∞, +∞): ") + direction(0.0));
        return out;
    }
    // (-∞, b0)：端点用精确形式展示
    out.push_back(std::string("(-∞, ") + boundary_str[0] + "): " +
                  direction(boundaries[0] - 1.0));
    for (std::size_t i = 0; i + 1 < boundaries.size(); ++i) {
        const double lo = boundaries[i], hi = boundaries[i + 1];
        out.push_back("[" + boundary_str[i] + ", " + boundary_str[i + 1] + "): " +
                      dir_of(probe(lo, hi)));
    }
    out.push_back("[" + boundary_str.back() + ", +∞): " +
                  direction(boundaries.back() + 1.0));
    return out;
}

LocalExtremaResult local_extrema(const std::string& expr,
                                 const std::string& var) {
    LocalExtremaResult r;
    const std::string d1 = deriv(expr, var);
    const auto xs = sym(var);
    const auto eq = SymEngine::parse(d1);
    // 含自由参数：极值位置依赖参数（如 ±√a），数值接口无法给出正确结论 → 显式报错。
    // （原实现在此静默返回空集，isError=false，属"错答"，已修正）
    const auto params = mf::symutil::symbol_names(*eq);
    bool has_param = false;
    for (const auto& n : params)
        if (n != var) has_param = true;
    if (has_param) {
        throw std::invalid_argument(
            "表达式含自由参数（" + mf::symutil::join_names(params) +
            "），极值位置与参数取值有关：请用 solve_sym 求含参驻点，或指定参数值后再调用");
    }
    const auto sol = mf::symutil::safe_solve(eq, xs, "驻点方程");
    if (!SymEngine::is_a<SymEngine::FiniteSet>(*sol)) {
        // 无法求出驻点集合（非有限集）：不能等同于"无极值"
        throw std::invalid_argument("无法求出驻点集合，无法判定极值");
    }
    const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*sol);
    for (const auto& rt : fs.get_args()) {
        double c;
        try {
            c = SymEngine::eval_double(*rt);
        } catch (...) {
            // 有驻点却无法数值化：绝不静默跳过（否则给出不完整/错误答案）
            throw std::invalid_argument("驻点 " + SymEngine::str(*rt) +
                                        " 无法数值化，极值无法给出数值结果");
        }
        const double f2 = eval_deriv_val(deriv(expr, var), var, c);
        const double fv = eval_at(expr, var, c);
        if (f2 < 0) {
            r.maxima_x.push_back(c);
            r.maxima_val.push_back(fv);
        } else if (f2 > 0) {
            r.minima_x.push_back(c);
            r.minima_val.push_back(fv);
        }
    }
    return r;
}

GlobalExtremaResult global_extrema(const std::string& expr,
                                   const std::string& var, double a, double b) {
    GlobalExtremaResult r;
    struct Pt { double x, v; };
    std::vector<Pt> pts = {{a, eval_at(expr, var, a)}, {b, eval_at(expr, var, b)}};
    const auto sol = mf::symutil::safe_solve(SymEngine::parse(deriv(expr, var)), sym(var), "驻点方程");
    if (SymEngine::is_a<SymEngine::FiniteSet>(*sol)) {
        const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*sol);
        for (const auto& rt : fs.get_args()) {
            try {
                const double c = SymEngine::eval_double(*rt);
                if (c >= a && c <= b) pts.push_back({c, eval_at(expr, var, c)});
            } catch (...) {
            }
        }
    }
    r.max_point = pts[0].x;
    r.max = pts[0].v;
    r.min_point = pts[0].x;
    r.min = pts[0].v;
    for (const auto& p : pts) {
        if (p.v > r.max) { r.max = p.v; r.max_point = p.x; }
        if (p.v < r.min) { r.min = p.v; r.min_point = p.x; }
    }
    return r;
}

std::string taylor(const std::string& expr, const std::string& var, double point,
                   long long order) {
    const bool zero_center = std::abs(point) < 1e-12;
    std::string out;
    for (long long k = 0; k <= order; ++k) {
        const std::string c = coeff_at(expr, var, point, k);
        if (c == "0") continue;
        std::string term;
        if (k == 0) {
            term = c;
        } else {
            std::string pw = (k == 1) ? (zero_center ? var : "(" + var + " - " + std::to_string(point) + ")")
                                      : (zero_center ? var + "**" + std::to_string(k)
                                                     : "(" + var + " - " + std::to_string(point) + ")**" + std::to_string(k));
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

}  // namespace mf::calculus
