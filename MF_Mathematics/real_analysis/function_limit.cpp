#include "function_limit.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/derivative.h>
#include <symengine/parser.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include "ra_internal.h"

namespace mf::real_analysis {

namespace {

using mf::real_analysis::detail::ExprEval;
using mf::real_analysis::detail::LimitProbe;
using mf::real_analysis::detail::nan_d;

// 左右两侧极限的独立探测(不做任何平均)。
struct SideLimits {
    LimitProbe left;
    LimitProbe right;
};

SideLimits side_limits(const ExprEval& f, double point) {
    const double h0 = detail::probe_scale(point);
    SideLimits s;
    s.left = detail::one_sided_limit([&](double t) { return f.at(t); }, point,
                                     -1.0, h0);
    s.right = detail::one_sided_limit([&](double t) { return f.at(t); }, point,
                                      +1.0, h0);
    return s;
}

// 双侧极限：左右两侧各自 Richardson 外推到 h→0，两者都存在有限极限且相等。
//
// 旧实现把 h∈{1e-3,1e-4,1e-5} 上 ±两侧采样值直接取平均：
//   * x² 在 1 处给出 1 + O(h²) ≈ 1.0000003，与真实极限 1 差 3.4e-7，
//     直接撞死 real_is_continuous 里 1e-8 的固定容差；
//   * 1/x 在 0 处左 -1/h、右 +1/h 恰好在每个 h 上抵消成 0，
//     凭空造出「极限 L=0」。
// 这两件事都不是「极限没算准」，而是「用采样均值代替了极限」。
double numeric_limit(const ExprEval& f, double point) {
    const SideLimits s = side_limits(f, point);
    if (!s.left.ok || !s.right.ok) return nan_d();
    const double tol = 1e-8 * std::max(
        1.0, std::max(std::abs(s.left.value), std::abs(s.right.value)));
    if (std::abs(s.left.value - s.right.value) > tol) return nan_d();
    return 0.5 * (s.left.value + s.right.value);
}

}  // namespace

EpsDeltaResult limit_epsilon_delta(const std::string& expr, double point,
                                   double epsilon) {
    EpsDeltaResult r;
    const ExprEval f(expr, "x");
    if (!f.ok()) return r;
    r.L = numeric_limit(f, point);
    // 双侧极限不存在(如 1/x 在 0 处)时不再报出任何有限 L：
    // 此时返回 NaN(JSON 序列化为 null)，delta 保持 0。
    if (!std::isfinite(r.L)) {
        r.L = nan_d();
        return r;
    }
    // δ ≈ ε/|f'(point)|。
    const auto x = SymEngine::symbol("x");
    const auto d = SymEngine::diff(SymEngine::parse(expr), x);
    const auto sub = d->subs({{x, SymEngine::real_double(point)}});
    const double df = SymEngine::eval_double(*sub);
    r.delta = (std::abs(df) > 1e-10) ? epsilon / std::abs(df) : epsilon;
    return r;
}

bool real_is_continuous(const std::string& expr, double point) {
    const ExprEval f(expr, "x");
    if (!f.ok()) return false;
    const double f0 = f.at(point);
    if (!std::isfinite(f0)) return false;
    const double lim = numeric_limit(f, point);
    if (!std::isfinite(lim)) return false;
    // 用相对容差比较：f0 本身可能带有尺度(如 e² 在 2 处)。
    return std::abs(lim - f0) <= 1e-8 * std::max(1.0, std::abs(f0));
}

// 一致连续性：紧区间上 f 一致连续 ⟺ 连续模 ω(δ) = sup_{|x-y|≤δ}|f(x)-f(y)| → 0。
//
// 旧实现只检查 1001 个网格点上 f 是否有限，而 tan 在 π/2 处的浮点值是
// 1.63e16（有限），于是把 [0,π] 上的极点整个漏掉。
// 这里改为量 ω(δ) 本身：δ 逐级减半，要求 ω 按正的幂次速度衰减
// （ω(δ) ≈ C·δ^p, p > 0）。极点处 ω(δ) ~ 1/δ 会放大，从而被判为非一致连续；
// 1/δ^p 形式的衰减对 √x 这类仅 Hölder 连续的函数同样成立。
bool uniform_continuity(const std::string& expr, double a, double b) {
    if (a > b) std::swap(a, b);
    const ExprEval f(expr, "x");
    if (!f.ok()) return false;
    const double width = b - a;
    if (!(width > 0.0)) return true;

    const int ns[5] = {128, 256, 512, 1024, 2048};
    std::vector<double> omega;
    for (int n : ns) {
        const double h = width / n;
        double prev = f.at(a);
        if (!std::isfinite(prev)) return false;
        double mx = 0.0;
        for (int i = 1; i <= n; ++i) {
            const double cur = f.at(a + h * i);
            if (!std::isfinite(cur)) return false;
            mx = std::max(mx, std::abs(cur - prev));
            prev = cur;
        }
        omega.push_back(mx);
    }
    const std::size_t K = omega.size() - 1;
    if (omega[K] == 0.0) return true;  // 常函数
    // 末三级必须都在收缩(ω_{2δ} ≤ 0.9·ω_δ 即指数 p ≥ 0.15)。
    for (std::size_t k = K - 3; k < K; ++k)
        if (!(omega[k + 1] <= 0.9 * omega[k])) return false;
    return true;
}

std::string real_discontinuity_classify(const std::string& expr, double point) {
    const ExprEval f(expr, "x");
    if (!f.ok()) return "振荡间断点";
    const SideLimits s = side_limits(f, point);
    const double f0 = f.at(point);
    const bool left_bad = !s.left.ok;    // 无有限左极限(无穷/振荡/无定义)
    const bool right_bad = !s.right.ok;

    if (s.left.diverges || s.right.diverges) return "无穷间断点";
    if (left_bad && right_bad) return "振荡间断点";
    if (left_bad || right_bad) {
        // 单侧有有限极限、另一侧没有：若有限的那侧等于 f0，说明另一侧是振荡。
        return "振荡间断点";
    }
    const double scale =
        std::max(1.0, std::max(std::abs(s.left.value), std::abs(s.right.value)));
    if (std::abs(s.left.value - s.right.value) <= 1e-8 * scale) {
        if (std::isfinite(f0) &&
            std::abs(s.left.value - f0) <= 1e-8 * std::max(1.0, std::abs(f0)))
            return "连续（非间断点）";
        return "可去间断点";
    }
    return "跳跃间断点";
}

ExtremeValueResult extreme_value(const std::string& expr, double a, double b) {
    if (a > b) std::swap(a, b);
    ExtremeValueResult r;
    struct Pt {
        double x, v;
    };
    const ExprEval f(expr, "x");
    std::vector<Pt> pts = {{a, f.at(a)}, {b, f.at(b)}};

    // 驻点:f'=0 在 [a,b] 内的根。
    const auto x = SymEngine::symbol("x");
    const auto d = SymEngine::diff(SymEngine::parse(expr), x);
    // 符号求解失败(如 eˣ=0 这类非多项式方程)按原样报错 —— 保留「求解器能力限制」
    // 这一已记录的行为，不在这里偷偷降级。
    const auto roots = SymEngine::solve(d, x);
    std::vector<double> critical;
    if (SymEngine::is_a<SymEngine::FiniteSet>(*roots)) {
        const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*roots);
        for (const auto& rt : fs.get_args()) {
            try {
                const double xp = SymEngine::eval_double(*rt);
                if (std::isfinite(xp) && xp >= a && xp <= b) critical.push_back(xp);
            } catch (...) {
            }
        }
    }

    // 数值补扫 f' 在 [a,b] 上的变号点。cos(x)=0 这类超越方程 SymEngine::solve
    // 解不出来(返回的不是有限根集合)，只比端点会漏掉 sin 在 [0,2π] 上的 ±1。
    {
        const std::string ds = SymEngine::str(*d);
        const ExprEval df(ds, "x");
        const int N = 4000;
        double px = a, pv = df.at(a);
        for (int i = 1; i <= N; ++i) {
            const double t = a + (b - a) * i / N;
            const double v = df.at(t);
            if (std::isfinite(pv) && std::isfinite(v) && pv * v < 0.0) {
                double lo = px, hi = t, flo = pv;
                for (int it = 0; it < 80; ++it) {
                    const double m = 0.5 * (lo + hi);
                    const double fm = df.at(m);
                    if (!std::isfinite(fm)) break;
                    if (flo * fm <= 0.0) { hi = m; } else { lo = m; flo = fm; }
                }
                const double root = 0.5 * (lo + hi);
                bool known = false;
                for (double c : critical)
                    if (std::abs(c - root) <= 1e-7 * (std::abs(b - a) + 1.0))
                        known = true;
                if (!known) critical.push_back(root);
            }
            px = t;
            pv = v;
        }
    }

    for (double xp : critical) {
        const double v = f.at(xp);
        if (std::isfinite(v)) pts.push_back({xp, v});
    }

    r.max_point = pts[0].x;
    r.max = pts[0].v;
    r.min_point = pts[0].x;
    r.min = pts[0].v;
    for (const auto& p : pts) {
        if (p.v > r.max) {
            r.max = p.v;
            r.max_point = p.x;
        }
        if (p.v < r.min) {
            r.min = p.v;
            r.min_point = p.x;
        }
    }
    return r;
}

double intermediate_value(const std::string& expr, double a, double b,
                          double value) {
    const ExprEval f(expr, "x");
    const double fa = f.at(a);
    const double fb = f.at(b);
    if (!std::isfinite(fa) || !std::isfinite(fb)) {
        return nan_d();
    }
    if (std::min(fa, fb) <= value && value <= std::max(fa, fb)) {
        const double xi = detail::find_root(expr, a, b, value);
        return std::isfinite(xi) ? xi : 0.5 * (a + b);
    }
    return nan_d();
}

}  // namespace mf::real_analysis
