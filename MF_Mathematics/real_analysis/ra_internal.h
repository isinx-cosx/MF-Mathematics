// ra_internal.h — real_analysis 包共享辅助(仅头文件)。
//
// 提供:表达式实数求值、数值积分、求根、极限外推、数列极限数值检测。
//
// 【数值判据的立场】本文件里所有的「极限」判定统一按下面的方式做，而不是
// 拿固定步长/固定网格上的采样值去比某个固定绝对容差：
//
//   * 以 h_k = h0·2^{-k}(k = 0..12) 采样，h 逐级减半；
//   * 对采样列做 Richardson 外推 R[m][k] = R[m-1][k+1] + (R[m-1][k+1] - R[m-1][k])/(2^m - 1)，
//     R[m][·] 的误差为 O(h^{m+1})；取对角线 R[m][K-m] 作为第 m 级估计；
//   * 判据 = 「相邻两级估计之差 ≤ 1e-9·max(1,|估计|)」，即极限本身已经稳定，
//     而不是「某个采样点与某个常数足够近」。
//
// 旧实现(采样均值 + 固定 1e-6/1e-8/0.01 阈值)的具体失效见各处调用点注释。

#pragma once

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/eval_double.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

namespace mf::real_analysis::detail {

// 每个方向/子列的采样点数(h 从 h0 减半 kProbeSamples-1 次)。
constexpr int kProbeSamples = 13;
// Richardson 相邻两级的相对收敛阈值。
constexpr double kProbeTol = 1e-9;

inline double nan_d() { return std::numeric_limits<double>::quiet_NaN(); }

inline double inf_d() { return std::numeric_limits<double>::infinity(); }

// 探测尺度：以点本身的数量级取初始步长，使 h 与 point 相比不会小到丢失有效位。
inline double probe_scale(double point) {
    return 0.25 * std::max(1.0, std::abs(point));
}

// ── 求值器(表达式只解析一次，可反复对同一变量求值) ──────────────────────

class ExprEval {
public:
    ExprEval() = default;
    ExprEval(const std::string& expr, const std::string& var) {
        try {
            expr_ = SymEngine::parse(expr);
            sym_ = SymEngine::symbol(var);
            ok_ = true;
        } catch (...) {
            ok_ = false;
        }
    }
    bool ok() const { return ok_; }
    double at(double v) const {
        if (!ok_) return nan_d();
        try {
            const auto sub = expr_->subs({{sym_, SymEngine::real_double(v)}});
            return SymEngine::eval_double(*sub);
        } catch (...) {
            return nan_d();
        }
    }

private:
    SymEngine::RCP<const SymEngine::Basic> expr_;
    SymEngine::RCP<const SymEngine::Symbol> sym_;
    bool ok_ = false;
};

// 双变量求值器(典型用途:(x, n) 的函数列 f_n(x))。
class ExprEval2 {
public:
    ExprEval2(const std::string& expr, const std::string& v1,
              const std::string& v2) {
        try {
            expr_ = SymEngine::parse(expr);
            s1_ = SymEngine::symbol(v1);
            s2_ = SymEngine::symbol(v2);
            ok_ = true;
        } catch (...) {
            ok_ = false;
        }
    }
    bool ok() const { return ok_; }
    double at(double a, double b) const {
        if (!ok_) return nan_d();
        try {
            const auto sub = expr_->subs({{s1_, SymEngine::real_double(a)},
                                          {s2_, SymEngine::real_double(b)}});
            return SymEngine::eval_double(*sub);
        } catch (...) {
            return nan_d();
        }
    }

private:
    SymEngine::RCP<const SymEngine::Basic> expr_;
    SymEngine::RCP<const SymEngine::Symbol> s1_;
    SymEngine::RCP<const SymEngine::Symbol> s2_;
    bool ok_ = false;
};

// ── 单变量表达式求值(每次重新解析的旧接口，保留给少量低频调用点) ────────

inline double eval_str(const std::string& expr, double x) {
    return ExprEval(expr, "x").at(x);
}

inline double eval_var(const std::string& expr, const std::string& var,
                       double val) {
    return ExprEval(expr, var).at(val);
}

inline double eval_xn(const std::string& expr, double x, double n) {
    return ExprEval2(expr, "x", "n").at(x, n);
}

// ── 极限外推 ────────────────────────────────────────────────────────────

struct LimitProbe {
    bool ok = false;        // h→0 存在有限极限
    bool diverges = false;  // 幅度按几何速度放大(数值上判定为趋于 ±∞)
    double value = 0.0;     // ok 时的极限估计
    double uncertainty = 0.0;
    double last = 0.0;      // 最细步长处的采样值(用于判断发散的方向)
};

// v[k] 必须是步长 h_k = h0·2^{-k} 上的采样值(单调减半)。
inline LimitProbe extrapolate_limit(const std::vector<double>& v) {
    LimitProbe r;
    const int K = static_cast<int>(v.size()) - 1;
    if (K < 5) return r;
    r.last = v[K];

    // (1) 尾部出现非有限值：±inf ⇒ 无界；NaN ⇒ 无有限极限。
    for (int k = 0; k <= K; ++k) {
        if (std::isinf(v[k])) {
            r.diverges = true;
            return r;
        }
        if (std::isnan(v[k])) return r;
    }

    // (2) 尾部幅度按几何速度放大 ⇒ 趋于 ±∞。
    //     例如 1/x 在 0 的右侧：h 减半时采样值精确翻倍，比值 ≈ 2 > 1.25。
    {
        bool grow = true;
        for (int k = K - 3; k < K; ++k) {
            const double a = std::abs(v[k]);
            const double b = std::abs(v[k + 1]);
            if (!(b > 1.25 * a)) {
                grow = false;
                break;
            }
        }
        if (grow) {
            r.diverges = true;
            return r;
        }
    }

    // (3) Richardson 外推。v[k] = L + Σ_j c_j h_k^{p_j}，p_j 单调增；
    //     第 m 级消掉前 m 个误差项，取对角线 R[m][K-m]。
    std::vector<double> prev = v;
    double last = v[K];
    const int mmax = std::min(K - 1, 10);
    for (int m = 1; m <= mmax; ++m) {
        std::vector<double> cur(prev.size() - 1);
        const double denom = std::pow(2.0, static_cast<double>(m)) - 1.0;
        for (std::size_t k = 0; k + 1 < prev.size(); ++k)
            cur[k] = prev[k + 1] + (prev[k + 1] - prev[k]) / denom;
        const double est = cur.back();
        const double diff = std::abs(est - last);
        if (m >= 2 && diff <= kProbeTol * std::max(1.0, std::abs(est))) {
            r.ok = true;
            r.value = est;
            r.uncertainty = diff;
            return r;
        }
        last = est;
        prev.swap(cur);
    }

    // (4) 非整数幂衰减的备用外推：a_n ~ C·n^{-p}(p 非整数，如 1/√n)时误差项
    //     不是 h 的整数次幂，Richardson 消不掉，但它仍是几何尾：
    //     v_k − L ≈ q·(v_{k−1} − L)，q = 2^{-p}。用几何尾公式
    //     L_k = v_k + (v_k − v_{k−1})·q/(1−q) 直接外推。
    //     必须有证书才接受：最近三个增量同号、严格收缩，且相邻两级给出的
    //     L 必须一致(1/log n 这类同样「增量递减」但不收敛的列会被这一步挡掉)。
    if (K >= 4) {
        const double d1 = v[K - 2] - v[K - 3];
        const double d2 = v[K - 1] - v[K - 2];
        const double d3 = v[K] - v[K - 1];
        const bool same_sign = (d1 > 0.0 && d2 > 0.0 && d3 > 0.0) ||
                               (d1 < 0.0 && d2 < 0.0 && d3 < 0.0);
        if (same_sign) {
            const double q = d3 / d2;
            const double q0 = d2 / d1;
            if (q > 0.0 && q < 0.95 && q0 > 0.0 && q0 < 0.95) {
                const double tail = q / (1.0 - q);
                const double l1 = v[K] + d3 * tail;
                const double l2 = v[K - 1] + d2 * tail;
                const double scale = std::max(1.0, std::abs(l1));
                if (std::abs(l1 - l2) <= 1e-6 * scale) {
                    r.ok = true;
                    r.value = l1;
                    r.uncertainty = std::abs(l1 - l2);
                }
            }
        }
    }
    return r;
}

// 单侧极限：dir = -1(左) 或 +1(右)。f 是任意可调用对象。
template <class F>
inline LimitProbe one_sided_limit(F f, double point, double dir, double h0) {
    std::vector<double> v;
    v.reserve(kProbeSamples);
    double h = h0;
    for (int k = 0; k < kProbeSamples; ++k) {
        v.push_back(f(point + dir * h));
        h *= 0.5;
    }
    return extrapolate_limit(v);
}

// ── 数列极限 ────────────────────────────────────────────────────────────

struct SeqLimitProbe {
    bool ok = false;
    bool diverges = false;
    double value = 0.0;
    double sign = 1.0;  // diverges 时的符号
    double uncertainty = 0.0;
    double last = 0.0;
};

// a_n → L ⟺ 偶子列与奇子列都收敛到 L。
// 取 n_k = 1000·2^k(精确可表示)与 n_k + 1，两列分别 Richardson 外推：
// 偶奇不一致(如 (-1)^n)即为振荡，无极限。
template <class F>
inline SeqLimitProbe sequence_limit_probe(F f) {
    std::vector<double> ve, vo;
    ve.reserve(kProbeSamples);
    vo.reserve(kProbeSamples);
    double n = 1000.0;
    for (int k = 0; k < kProbeSamples; ++k) {
        ve.push_back(f(n));
        vo.push_back(f(n + 1.0));
        n *= 2.0;
    }
    const LimitProbe pe = extrapolate_limit(ve);
    const LimitProbe po = extrapolate_limit(vo);

    SeqLimitProbe r;
    if (pe.diverges || po.diverges) {
        r.diverges = true;
        const double s = pe.diverges ? pe.last : po.last;
        r.sign = s >= 0.0 ? 1.0 : -1.0;
        r.last = s;
        return r;
    }
    if (!pe.ok || !po.ok) return r;
    const double scale =
        std::max(1.0, std::max(std::abs(pe.value), std::abs(po.value)));
    if (std::abs(pe.value - po.value) > 1e-6 * scale) return r;  // 振荡
    r.ok = true;
    r.value = 0.5 * (pe.value + po.value);
    r.uncertainty = std::max(pe.uncertainty, po.uncertainty);
    r.last = po.last;
    return r;
}

// 求值器版本的数列极限：发散返回 ±inf，振荡/无极限返回 NaN。
template <class F>
inline double sequence_limit_of(F f) {
    const SeqLimitProbe p = sequence_limit_probe(f);
    if (p.diverges) return p.sign > 0 ? inf_d() : -inf_d();
    return p.ok ? p.value : nan_d();
}

// ── 数值积分 / 求根 ─────────────────────────────────────────────────────

inline double simpson(const std::function<double(double)>& f, double a, double b,
                      int n = 1000) {
    if (n % 2 != 0) ++n;
    const double h = (b - a) / n;
    double s = f(a) + f(b);
    for (int i = 1; i < n; ++i) {
        const double t = a + i * h;
        s += (i % 2 == 1) ? 4.0 * f(t) : 2.0 * f(t);
    }
    return s * h / 3.0;
}

inline double integrate_expr(const std::string& expr, double a, double b) {
    const ExprEval f(expr, "x");
    return simpson([&](double t) { return f.at(t); }, a, b, 2000);
}

// f(x) = c 在 [a, b] 内的根(网格 + 二分)。找不到返回 NaN。
inline double find_root(const std::string& expr, double a, double b, double c) {
    const ExprEval e(expr, "x");
    const auto f = [&](double t) { return e.at(t) - c; };
    const int N = 2000;
    double pt = a, pv = f(a);
    for (int i = 1; i <= N; ++i) {
        const double t = a + (b - a) * i / N;
        const double v = f(t);
        if (std::isfinite(pv) && std::isfinite(v) && pv * v < 0.0) {
            double lo = pt, hi = t, flo = pv;
            for (int it = 0; it < 60; ++it) {
                const double m = 0.5 * (lo + hi);
                const double fm = f(m);
                if (!std::isfinite(fm)) break;
                if (flo * fm <= 0.0) { hi = m; } else { lo = m; flo = fm; }
            }
            return 0.5 * (lo + hi);
        }
        pt = t;
        pv = v;
    }
    // 端点为根。
    if (std::abs(f(a)) < 1e-9) return a;
    if (std::abs(f(b)) < 1e-9) return b;
    return nan_d();
}

// 数列极限数值检测:返回极限值;发散返回 ±inf,振荡返回 NaN。
inline double sequence_limit_value(const std::string& expr,
                                   const std::string& var = "n") {
    const ExprEval e(expr, var);
    if (!e.ok()) return nan_d();
    return sequence_limit_of([&](double n) { return e.at(n); });
}

}  // namespace mf::real_analysis::detail
