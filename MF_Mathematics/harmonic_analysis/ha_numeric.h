// ha_numeric.h — harmonic_analysis 数值积分内核(仅头文件)。
//
// 提供「截断半径自适应 + 振荡分辨 + 渐近尾校正」的通用数值傅里叶积分:
//
//     F(w) = ∫_{-∞}^{∞} f(x)·e^{-i·w·x} dx
//
// 为什么需要它(tests/accuracy/cases_harmonic_analysis.py 里的失败项):
//   * 旧实现把积分区间硬编码成 ±20、固定 4000 点辛普森。对衰减尺度远大于 20
//     的被积函数(如 1/(1+x²))它截掉了真实质量; 对高频振荡它又完全欠采样, 于是
//     静默返回一个错数(1/(1+x²) 在 ξ=0 给 2·arctan(20), 在 ξ=5 给 -5e-7)。
//   * 本实现:
//       1) 先用「衰减阶梯」测出被积函数的尺度, 决定截断半径 R
//          (尾部可忽略→直接截断; 代数衰减→R 由频率决定, 尾部另算);
//       2) 有限部分 [-R,R] 的采样步长同时满足「分辨函数」和「分辨振荡」两个要求,
//          用梯形/辛普森双规则 + 逐次加密的实测误差(Richardson)判收敛;
//       3) 代数衰减的尾部用分部积分得到的渐近级数
//              Tail(R,w) = e^{-i·w·R}·Σ_{n≥0} (-i/w)^{n+1} f^{(n)}(R)
//          (符号求导算出, 只有级数项确实递减才采信), 而不是拿欠采样的振荡积分
//          充当结果;
//       4) ω→0(相位在有效区间内几乎不变)退化到几何面板法: 面板宽度倍增,
//          逐面板自适应加密, 直到尾板贡献低于容差 ⇒ 可以一直积到 1e13。
//   * 任何情况下都把实测误差 error 与 reliable 标志带回去: 收敛不了就如实报告,
//     绝不把欠采样的值当成结果。
#pragma once

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <vector>

#include <symengine/basic.h>
#include <symengine/derivative.h>
#include <symengine/lambda_double.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include "ha_internal.h"

namespace mf::harmonic_analysis::detail {

using SymEngine::Basic;
using SymEngine::RCP;
using SymEngine::Symbol;

inline constexpr double kInfD = std::numeric_limits<double>::infinity();

// ── 数值傅里叶积分结果 ──────────────────────────────────────────────────────
struct NumericFT {
    std::complex<double> value{0.0, 0.0};
    double error = kInfD;    // 实测误差估计(有限部分 + 尾部 + 舍入噪声底)
    double radius = 0.0;     // 有限部分截断半径
    double measure = 0.0;    // ∫|f| 的粗略测度(量级/噪声底用)
    int tail_terms = 0;      // 尾部渐近级数实际用了多少项
    long long evals = 0;     // 被积函数求值次数
    bool converged = false;  // 实测误差是否达到容差
    bool reliable = false;   // |value| 是否明显大于 error(值可用)
};

// ── 实数被积函数求值器 ──────────────────────────────────────────────────────
// LambdaRealDoubleVisitor 把表达式预编译成 lambda(比 subs+eval_double 快约 40 倍);
// 不支持的节点或调用期异常一律回退到 eval_double_expr。
class RealFn {
public:
    RealFn(const RCP<const Basic>& e, const RCP<const Symbol>& x) : e_(e), x_(x) {
        try {
            lam_.init({x}, *e_);
            use_lam_ = true;
        } catch (...) {
            use_lam_ = false;
        }
    }

    double operator()(double t) const {
        if (use_lam_) {
            try {
                double in = t, out = 0.0;
                lam_.call(&out, &in);
                return out;
            } catch (...) {
                use_lam_ = false;
            }
        }
        return eval_double_expr(e_, x_, t);
    }

    const RCP<const Basic>& expr() const { return e_; }
    const RCP<const Symbol>& var() const { return x_; }

private:
    RCP<const Basic> e_;
    RCP<const Symbol> x_;
    mutable SymEngine::LambdaRealDoubleVisitor lam_;
    mutable bool use_lam_ = false;
};

// ── 复被积函数 g(x) = f(x)·e^{-i·w·x} ───────────────────────────────────────
struct FTIntegrand {
    const RealFn* f = nullptr;
    double w = 0.0;

    std::complex<double> operator()(double t) const {
        const double v = (*f)(t);
        if (w == 0.0) return {v, 0.0};
        const double a = w * t;
        return {v * std::cos(a), -v * std::sin(a)};
    }
};

// 补偿求和(振荡被积函数的大幅相消需要它)。
struct KahanC {
    std::complex<double> s{0.0, 0.0}, c{0.0, 0.0};
    void add(const std::complex<double>& v) {
        const std::complex<double> y = v - c;
        const std::complex<double> t = s + y;
        c = (t - s) - y;
        s = t;
    }
};

// ── 复值辛普森 / 梯形 ───────────────────────────────────────────────────────
inline std::complex<double> simpson_ft(const FTIntegrand& g, double a, double b, int n) {
    if (n % 2 != 0) ++n;
    const double h = (b - a) / n;
    KahanC se, so;
    se.add(g(a) + g(b));
    for (int i = 1; i < n; ++i) {
        const double t = a + i * h;
        if (i % 2 == 1) so.add(g(t));
        else se.add(g(t));
    }
    return (se.s + 4.0 * so.s) * (h / 3.0);
}

inline std::complex<double> trapz_ft(const FTIntegrand& g, double a, double b, int n) {
    if (n < 1) n = 1;
    const double h = (b - a) / n;
    KahanC s;
    s.add(0.5 * (g(a) + g(b)));
    for (int i = 1; i < n; ++i) s.add(g(a + i * h));
    return s.s * h;
}

// 粗测度 ∫_R^{2R}|f| dx(用于判断尾部是否已可忽略)。
inline double tail_measure(const RealFn& f, double R, int n = 64) {
    const double h = R / n;
    double s = 0.5 * (std::abs(f(R)) + std::abs(f(2.0 * R)));
    for (int i = 1; i < n; ++i) s += std::abs(f(R + i * h));
    return s * h;
}

// ── 尺度探测 ────────────────────────────────────────────────────────────────
struct ScaleInfo {
    double fmax = 0.0;      // 峰值
    double r_hump = 0.0;    // |f| 降到峰值 2% 的半径
    double r_decay = -1.0;  // 尾部测度相对于总质量可忽略的半径(-1: 代数衰减)
    double decay_measure = 0.0;
    double measure = 0.0;   // ∫|f| 粗略测度
    long long evals = 0;
};

inline ScaleInfo probe_scales(const RealFn& f, long long budget) {
    ScaleInfo s;
    s.fmax = std::abs(f(0.0));
    for (double t : {-0.5, 0.5, -1.0, 1.0, -2.0, 2.0, -4.0, 4.0})
        s.fmax = std::max(s.fmax, std::abs(f(t)));
    s.evals += 9;
    if (!(s.fmax > 0.0)) return s;
    {   // 中心 [-1,1] 的测度
        const int n = 64;
        const double h = 2.0 / n;
        double a = 0.5 * (std::abs(f(-1.0)) + std::abs(f(1.0)));
        for (int i = 1; i < n; ++i) a += std::abs(f(-1.0 + i * h));
        s.measure = a * h;
        s.evals += n + 1;
    }
    double R = 1.0;
    for (int j = 0; j < 46; ++j) {
        if (s.evals + 66 > budget) break;
        const double v = std::abs(f(R));
        s.evals += 1;
        if (s.r_hump == 0.0 && v <= 0.02 * s.fmax) s.r_hump = R;
        const double m = tail_measure(f, R);
        s.evals += 65;
        s.measure += m;
        // 尾部相对总质量可忽略 ⇒ 半径外不必再积。
        if (s.r_decay < 0.0 && m <= 1e-15 * std::max(s.measure, s.fmax)) {
            s.r_decay = R;
            s.decay_measure = m;
        }
        if (s.r_hump > 0.0 && s.r_decay > 0.0) break;
        if (R > 1e13) break;
        R *= 2.0;
    }
    if (s.r_hump == 0.0) s.r_hump = 8.0;
    return s;
}

// ── 有限区间 [-R,R] ────────────────────────────────────────────────────────
struct FinitePart {
    std::complex<double> value{0.0, 0.0};
    double error = kInfD;
    int n = 0;
    long long evals = 0;
    bool converged = false;
};

inline FinitePart integrate_finite(const FTIntegrand& g, double R, double tol,
                                   long long budget) {
    FinitePart r;
    const double w = std::abs(g.w);
    const int n_init = static_cast<int>(
        std::max(64.0, std::ceil(2.0 * R * w * 8.0 / (2.0 * kPi))));
    // ① 梯形优先: 解析被积函数下它指数收敛, 代价远低于辛普森。
    {
        int n = n_init;
        std::complex<double> prev(0.0, 0.0);
        bool have = false;
        for (int lvl = 0; lvl < 6 && n <= 8192; ++lvl) {
            const std::complex<double> t = trapz_ft(g, -R, R, n);
            r.evals += n + 1;
            r.n = n;
            if (have) {
                const double et = std::abs(t - prev) / 2.0;
                if (et <= tol) {
                    // 同点辛普森交叉验证, 防梯形规则的混叠巧合。
                    const std::complex<double> s = simpson_ft(g, -R, R, n);
                    r.evals += n + 1;
                    if (std::abs(s - t) <= 8.0 * et + 1e-15 * std::abs(t)) {
                        r.value = t;
                        r.error = et;
                        r.converged = true;
                        return r;
                    }
                }
            }
            prev = t;
            have = true;
            n *= 2;
        }
    }
    // ② 辛普森阶梯(有拐点/不解析的被积函数由它兜底)。
    {
        int n = n_init;
        std::complex<double> prev(0.0, 0.0), last(0.0, 0.0);
        double last_e = kInfD;
        bool have = false;
        for (int lvl = 0; lvl < 32; ++lvl) {
            if (r.evals + (n + 1) > budget) break;
            const std::complex<double> s = simpson_ft(g, -R, R, n);
            r.evals += n + 1;
            r.n = n;
            last = s;
            if (have) {
                last_e = std::abs(s - prev) / 8.0;
                if (last_e <= tol) {
                    r.value = s;
                    r.error = last_e;
                    r.converged = true;
                    return r;
                }
            }
            prev = s;
            have = true;
            n *= 2;
            if (n > (1 << 23)) break;
        }
        r.value = last;
        r.error = last_e;
        return r;
    }
}

// ── 尾部渐近级数 ────────────────────────────────────────────────────────────
// ∫_R^∞      f(x)e^{-iwx}dx = e^{-iwR}·Σ_{n≥0} (-i/w)^{n+1} f^{(n)}(R)
// ∫_{-∞}^{-R} f(x)e^{-iwx}dx = e^{+iwR}·Σ_{n≥0} ( i/w)^{n+1} (-1)^n f^{(n)}(-R)
struct TailSeries {
    std::complex<double> value{0.0, 0.0};
    double error = kInfD;
    int terms = 0;
    long long evals = 0;
    bool ok = false;  // 级数项确实递减(渐近展开有效)
};

inline TailSeries asymptotic_tails(const RCP<const Basic>& e,
                                   const RCP<const Symbol>& x, double R, double w,
                                   double tol, long long budget) {
    TailSeries r;
    const std::complex<double> ir(0.0, -1.0 / w);  // -i/w
    const std::complex<double> il(0.0, 1.0 / w);   //  i/w
    std::complex<double> pr(1.0, 0.0), pl(1.0, 0.0);
    std::complex<double> sr(0.0, 0.0), sl(0.0, 0.0);
    double prev_mr = kInfD, prev_ml = kInfD;
    double er = kInfD, el = kInfD;
    bool dr = true, dl = true;  // 该侧是否仍在递减
    int n = 0;
    auto d = e;
    for (; n < 200; ++n) {
        if (r.evals + 2 > budget) break;
        const double vr = eval_double_expr(d, x, R);
        const double vl = eval_double_expr(d, x, -R);
        r.evals += 2;
        pr *= ir;
        pl *= il;
        const std::complex<double> tr = pr * vr;
        const std::complex<double> tl = pl * ((n % 2 == 0) ? vl : -vl);
        const double mr = std::abs(tr), ml = std::abs(tl);
        if (mr > prev_mr) dr = false; else { prev_mr = mr; er = mr; }
        if (ml > prev_ml) dl = false; else { prev_ml = ml; el = ml; }
        if (dr) sr += tr;
        if (dl) sl += tl;
        r.terms = n + 1;
        if (!dr && !dl) break;
        if (mr <= tol * 1e-3 && ml <= tol * 1e-3) break;
        if (n + 1 < 200) d = SymEngine::diff(d, x);
    }
    r.value = std::exp(std::complex<double>(0.0, -w * R)) * sr +
              std::exp(std::complex<double>(0.0, w * R)) * sl;
    // 误差取"最后一项"的量级(渐近级数的经典余项界), 两侧取大者。
    r.error = 4.0 * std::max(er, el);
    r.ok = std::isfinite(r.error) && r.error <= tol;
    return r;
}

// ── 几何面板法(ω 很小或为 0: 相位在有效区间内几乎不变) ─────────────────────
struct RayResult {
    std::complex<double> value{0.0, 0.0};
    double error = kInfD;
    double radius = 0.0;
    long long evals = 0;
    bool ok = false;
};

// ∫_R0^∞ f(x)e^{-iwx}dx: 面板 [R,2R] 倍增, 逐面板自适应加密到 tol*0.02,
// 尾板贡献低于 tol*0.05 且前后两块贡献按几何衰减 ⇒ 余项被 3·尾板界住。
inline RayResult integrate_ray(const RealFn& f, double R0, double w, double tol,
                               long long budget) {
    RayResult r;
    const FTIntegrand g{&f, w};
    double R = R0;
    double err_acc = 0.0;
    std::complex<double> acc(0.0, 0.0);
    double last = kInfD, prev_last = kInfD;
    for (int j = 0; j < 80; ++j) {
        const double a = R, b = 2.0 * R;
        int n = 48;
        const double span = std::abs(w) * (b - a);
        if (span > 0.5)
            n = static_cast<int>(std::max<double>(n, 1.0 + 16.0 * span / (2.0 * kPi)));
        if (n % 2 != 0) ++n;
        std::complex<double> prev(0.0, 0.0), cur(0.0, 0.0);
        double e = kInfD;
        bool have = false;
        for (int lvl = 0; lvl < 24; ++lvl) {
            if (r.evals + (n + 1) > budget || n >= (1 << 20)) break;
            cur = simpson_ft(g, a, b, n);
            r.evals += n + 1;
            if (have) {
                e = std::abs(cur - prev) / 8.0;
                if (e <= tol * 0.02) break;
            }
            prev = cur;
            have = true;
            n *= 2;
        }
        if (!std::isfinite(e)) e = 1e-12 * std::abs(cur) + 1e-300;
        acc += cur;
        err_acc += e;
        prev_last = last;
        last = std::abs(cur);
        r.value = acc;
        r.error = err_acc + 3.0 * last;
        r.radius = b;
        if (last <= tol * 0.05 && last <= 0.55 * prev_last) {
            r.ok = true;
            break;
        }
        if (r.evals > budget) break;
        R = b;
    }
    return r;
}

// ── 双指数(tanh-sinh)在 (-∞,∞) 上的积分 ────────────────────────────────────
//
// 为什么单独做一条：面板 + 尾部渐近级数的做法对**慢衰减**（1/(1+x²) 的尾巴只有
// 1/R）需要 R 到 1e7 才够，尾部级数一旦少补一项就整体偏小（实测 π 给成 1.957、
// √π 给成 1.477，都差固定比例 5/6）。双指数变换
//     x = sinh((π/2)·sinh t),  dx = (π/2)·cosh t·cosh((π/2)sinh t)·dt
// 把整条实轴压进有限区间，且对被积函数两端做了双指数衰减，于是
// **多项式衰减（如 1/x²）与指数衰减同样收敛**，不需要尾巴级数。
// 逐次把步长减半直到相邻两次结果一致，收敛性由实测差值给出。
inline NumericFT integrate_line_double_exponential(const RealFn& f, double w,
                                                   double tol, long long budget) {
    NumericFT out;
    const FTIntegrand g{&f, w};
    const double half_pi = 1.5707963267948966;
    std::complex<double> prev(0.0, 0.0);
    bool have_prev = false;
    bool have_err = false;
    double prev_err = kInfD;
    double err = kInfD;
    for (int lv = 1; lv <= 13; ++lv) {
        const double h = std::ldexp(1.0, -lv);          // 1/2, 1/4, …
        const double T = 4.0 + 0.60 * lv;               // t 的截断半径
        std::complex<double> sum(0.0, 0.0);
        long long n = 0;
        for (double t = -T; t <= T + 1e-12; t += h) {
            const double u = half_pi * std::sinh(t);
            const double xv = std::sinh(u);
            const double dx = half_pi * std::cosh(t) * std::cosh(u);
            if (!std::isfinite(xv) || !std::isfinite(dx)) continue;
            ++n;
            if (out.evals + n > budget) break;
            sum += g(xv) * dx;
        }
        out.evals += n;
        sum *= h;
        if (have_prev) {
            err = std::abs(sum - prev);
            // 达到调用方容差就提前收工（省算力）；否则**继续减半步长到最细一层**。
            // 不在"层间差停滞"时提前接受：停滞点的值往往比更细一层差得多
            // （实测 Gaussian 的逆变换：停滞层给 1e-4 级、最细层给 1e-13 级）。
            const double scale = (std::max)(1.0, std::abs(sum));
            if (err <= (std::max)(tol * scale,
                                  4.0 * std::numeric_limits<double>::epsilon() * scale)) {
                out.value = sum;
                out.error = err;
                out.radius = std::sinh(half_pi * std::sinh(T));
                out.converged = true;
                out.reliable = true;
                return out;
            }
        }
        prev = sum;
        have_prev = true;
        if (out.evals > budget) break;
    }
    // 跑到最细一层：返回值就是这里的和，误差用与上一层的差作**保守上界**。
    // 可用性判据按**值本身的量级**相对判（不能用 max(1,|sum|)）：
    // 振荡积分的结果可能很小（如 1/(1+x²) 在 ω=12.6 处只有 1e-5），
    // 若拿 1 当基准，1e-3 就变成绝对容差，会把"误差比结果还大"的噪声判成可用
    // —— 实测就是这样把 F(2) 的符号都弄反了。
    // 超过相对 1e-3 就交回尾部渐近路径（ω 很大、双指数网格分辨不了振荡的情形）。
    out.value = prev;
    out.error = std::isfinite(err) ? err : kInfD;
    {
        const double mag = std::abs(prev);
        out.converged = std::isfinite(err) && mag > 0.0 && err <= 1e-3 * mag;
        out.reliable = out.converged;
    }
    return out;
}

// 全直线(ω≈0): 中心 [-1,1] + 两侧几何面板
inline NumericFT integrate_line_panels(const RealFn& f, double w, double tol,
                                       long long budget) {
    NumericFT out;
    const FTIntegrand g{&f, w};
    {   // 中心 [-1,1] 自适应辛普森
        int n = 64;
        std::complex<double> prev(0.0, 0.0), cur = simpson_ft(g, -1.0, 1.0, n);
        out.evals += n + 1;
        double e = kInfD;
        bool have = false;
        for (int lvl = 0; lvl < 24; ++lvl) {
            if (have) {
                e = std::abs(cur - prev) / 8.0;
                if (e <= tol * 0.05) break;
            }
            if (out.evals + (2 * n + 2) > budget || n >= (1 << 20)) break;
            prev = cur;
            have = true;
            n *= 2;
            cur = simpson_ft(g, -1.0, 1.0, n);
            out.evals += n + 1;
        }
        if (!std::isfinite(e)) e = 1e-12 * std::abs(cur) + 1e-300;
        out.value = cur;
        out.error = e;
    }
    const RayResult rp = integrate_ray(f, 1.0, w, tol, budget - out.evals);
    out.evals += rp.evals;
    const auto neg = SymEngine::mul(SymEngine::integer(-1), f.var());
    const auto e_neg = f.expr()->subs({{f.var(), neg}});
    const RealFn fn(e_neg, f.var());
    const RayResult rm = integrate_ray(fn, 1.0, -w, tol, budget - out.evals);
    out.evals += rm.evals;

    out.value += rp.value + rm.value;
    out.error += rp.error + rm.error;
    out.radius = std::max(rp.radius, rm.radius);
    out.converged = rp.ok && rm.ok;
    out.reliable = out.converged || (std::abs(out.value) > 8.0 * out.error);
    return out;
}

// ── 主入口 ──────────────────────────────────────────────────────────────────
// rel_tol>0: 绝对容差 = max(abs_tol, rel_tol·max(1,∫|f|));  否则用 abs_tol。
inline NumericFT numeric_fourier_transform(const RCP<const Basic>& e,
                                           const RCP<const Symbol>& x, double w,
                                           double rel_tol, double abs_tol,
                                           long long budget) {
    NumericFT out;
    const RealFn f(e, x);
    ScaleInfo sc = probe_scales(f, budget / 4);
    out.evals += sc.evals;
    out.measure = sc.measure;
    if (!(sc.fmax > 0.0)) {  // 恒零函数
        out.value = {0.0, 0.0};
        out.error = 0.0;
        out.converged = true;
        out.reliable = true;
        return out;
    }
    double tol = abs_tol;
    if (rel_tol > 0.0) tol = std::max(abs_tol, rel_tol * std::max(1.0, sc.measure));
    if (!(tol > 0.0)) tol = 1e-12 * std::max(1.0, sc.measure);

    // 首选双指数变换：对慢衰减（1/x² 型）与振荡核都稳，不需要尾巴级数。
    // 它自称不可靠（未收敛）时才退回原来的面板法 + 渐近尾部。
    {
        NumericFT de = integrate_line_double_exponential(f, w, tol, budget - out.evals);
        de.evals += out.evals;
        de.measure = sc.measure;
        if (de.converged) return de;
    }

    if (std::abs(w) < 1e-13) {  // 相位在有效区间内几乎不变 ⇒ 面板法
        NumericFT r = integrate_line_panels(f, w, tol, budget - out.evals);
        r.evals += out.evals;
        r.measure = sc.measure;
        return r;
    }

    const FTIntegrand g{&f, w};
    double R;
    std::complex<double> tail(0.0, 0.0);
    double tail_err = 0.0;
    int tail_terms = 0;
    if (sc.r_decay > 0.0) {
        R = sc.r_decay;                      // 快速衰减: 半径外可忽略
        tail_err = 3.0 * sc.decay_measure;
    } else {
        // 代数衰减: R 取「进入渐近区」与「R·|w| 足够大使尾级数收敛」的较大者。
        R = std::max(sc.r_hump, 30.0 / std::abs(w));
        TailSeries ts;
        for (int attempt = 0; attempt < 4; ++attempt) {
            ts = asymptotic_tails(e, x, R, w, tol * 0.25, budget / 4);
            out.evals += ts.evals;
            if (ts.ok) break;
            R *= 2.0;
            if (R > 1e12) break;
        }
        tail = ts.value;
        tail_err = ts.error;
        tail_terms = ts.terms;
    }
    const FinitePart fin = integrate_finite(g, R, tol * 0.5, budget - out.evals);
    out.evals += fin.evals;
    out.value = fin.value + tail;
    out.radius = R;
    out.tail_terms = tail_terms;
    const double noise =
        8.0 * 2.2204460492503131e-16 * (sc.measure + std::abs(out.value));
    out.error = fin.error + tail_err + noise;
    out.converged = fin.converged && (tail_err <= tol);
    out.reliable = out.converged || (std::abs(out.value) > 8.0 * out.error);
    return out;
}

}  // namespace mf::harmonic_analysis::detail
