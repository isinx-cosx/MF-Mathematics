// special_numeric.h — 特殊函数的双精度求值（SymEngine::eval_double 的补充）
//
// 背景：SymEngine 的 eval_double 没有实现 Gamma / PolyGamma / Zeta / Beta /
// LambertW，于是含这些函数的导数**一个采样点都算不出来**——数值回退直接失效，
// 我们只能报"无法数值求值"。
//
// 本文件补上这些函数的纯数值实现（C++ 标准库能直接给的优先用标准库）：
//   Γ  : lgamma + 反射公式（负非整数用 π/(sin πx · Γ(1-x))）
//   logΓ: lgamma（仅 x>0 取实值）
//   ψ  : 递推 + 渐近展开
//   ψ⁽ⁿ⁾: (−1)^(n+1)·n!·ζ(n+1, x)（Hurwitz zeta）
//   ζ  : Euler–Maclaurin 求和；s<1 走函数方程
//   erf/erfc: 标准库
//   W₀ : 牛顿迭代解 w·eʷ = x
//
// 约定：算不出实数一律返回 NaN（而不是抛异常或返回错值），
// 让调用方沿用"NaN = 该点不可求值"的统一判断。
#pragma once

#include <symengine/basic.h>
#include <symengine/complex.h>
#include <symengine/constants.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/number.h>
#include <symengine/pow.h>
#include <symengine/real_double.h>
#include <symengine/symbol.h>

#include <cmath>
#include <limits>

namespace mf::num {

inline constexpr double kPi = 3.14159265358979323846;

/** 是否为整数（容差内）。 */
inline bool is_integer_value(double x) {
  return std::fabs(x - std::round(x)) <= 1e-12;
}

/** Γ(x) 的实数值；x 为非正整数（极点）或算不出时返回 NaN。 */
inline double gamma_real(double x) {
  if (!std::isfinite(x)) return std::numeric_limits<double>::quiet_NaN();
  if (x <= 0.0) {
    if (is_integer_value(x)) return std::numeric_limits<double>::quiet_NaN();  // 极点
    // 反射公式 Γ(x)Γ(1−x) = π / sin(πx)
    const double s = std::sin(kPi * x);
    if (std::fabs(s) < 1e-300) return std::numeric_limits<double>::quiet_NaN();
    return kPi / (s * std::exp(std::lgamma(1.0 - x)));
  }
  return std::exp(std::lgamma(x));
}

/** log Γ(x)；仅 x > 0 取实值。 */
inline double loggamma_real(double x) {
  if (!(x > 0.0) || !std::isfinite(x)) return std::numeric_limits<double>::quiet_NaN();
  return std::lgamma(x);
}

/** 双伽马 ψ(x) = d/dx ln Γ(x)；极点处返回 NaN。 */
inline double digamma_real(double x) {
  if (!std::isfinite(x)) return std::numeric_limits<double>::quiet_NaN();
  if (x <= 0.0) {
    if (is_integer_value(x)) return std::numeric_limits<double>::quiet_NaN();  // 极点
    // ψ(1−x) − ψ(x) = π cot(πx)
    const double t = std::tan(kPi * x);
    if (std::fabs(t) < 1e-300) return std::numeric_limits<double>::quiet_NaN();
    return digamma_real(1.0 - x) - kPi / t;
  }
  double r = 0.0;
  double y = x;
  // 递推 ψ(y) = ψ(y+1) − 1/y，把自变量抬到渐近展开有效的区间
  while (y < 8.0) { r -= 1.0 / y; y += 1.0; }
  const double inv = 1.0 / y;
  const double inv2 = inv * inv;
  r += std::log(y) - 0.5 * inv;
  // ψ(y) ~ ln y − 1/(2y) − Σ B_{2k}/(2k y^{2k})
  r -= inv2 * (1.0 / 12.0 -
               inv2 * (1.0 / 120.0 -
                       inv2 * (1.0 / 252.0 -
                               inv2 * (1.0 / 240.0 - inv2 * (1.0 / 132.0)))));
  return r;
}

/** Hurwitz zeta ζ(s, a) = Σ (a+k)^{−s}，Euler–Maclaurin 求和（a>0, s≠1）。
 *  n_terms 是直接求和的项数：s 越小需要的项数越多（见 zeta_real 的说明）。 */
inline double hurwitz_zeta(double s, double a, int n_terms = 16) {
  if (!(a > 0.0) || !std::isfinite(s)) return std::numeric_limits<double>::quiet_NaN();
  if (n_terms < 2) n_terms = 2;
  double sum = 0.0;
  for (int k = 0; k < n_terms; ++k) sum += std::pow(a + k, -s);
  const double an = a + n_terms;
  if (std::fabs(s - 1.0) < 1e-14) return std::numeric_limits<double>::quiet_NaN();  // s=1 极点
  sum += std::pow(an, 1.0 - s) / (s - 1.0);
  sum += 0.5 * std::pow(an, -s);
  // Σ_{j≥1} B_{2j}/(2j)! · (s)_{2j−1} · an^{−s−2j+1}
  static const double kB[6] = {1.0 / 6.0,  -1.0 / 30.0, 1.0 / 42.0,
                               -1.0 / 30.0, 5.0 / 66.0, -691.0 / 2730.0};
  double poch = s;          // (s)_{2j−1}
  double fact = 1.0;        // (2j)!
  double term_pow = std::pow(an, -s - 1.0);
  const double an2 = 1.0 / (an * an);
  for (int j = 1; j <= 6; ++j) {
    fact *= static_cast<double>((2 * j - 1) * (2 * j));
    if (j > 1) poch *= (s + 2.0 * j - 3.0) * (s + 2.0 * j - 2.0);
    sum += kB[j - 1] / fact * poch * term_pow;
    term_pow *= an2;
  }
  return sum;
}

/**
 * Riemann ζ(s) 的实数值；s = 1 处返回 NaN。
 *
 * 分支说明（这里踩过坑，务必看清）：
 *   · s ≥ 1  → Euler–Maclaurin 直接求和；
 *   · 0 < s < 1 → 仍用 Euler–Maclaurin，但直接求和项数要**显著加大**：
 *     s 小时 Σk^{-s} 与解析延拓项 N^{1-s}/(s-1) 是两个大数相消，
 *     项数不够就会被浮点抵消误差吃掉精度；
 *   · s ≤ 0 → 函数方程降到 1−s ≥ 1。
 *     **注意**：函数方程只对 s ≤ 0 才真正降阶；若对 0<s<1 也套函数方程，
 *     1−s 仍落在 (0,1)，就会 ζ(0.5) → ζ(0.5) 无限递归直接爆栈（实测崩溃）。
 */
inline double zeta_real(double s) {
  const double nan = std::numeric_limits<double>::quiet_NaN();
  if (!std::isfinite(s)) return nan;
  if (std::fabs(s - 1.0) < 1e-14) return nan;  // 极点
  if (s == 0.0) return -0.5;                    // ζ(0) = −1/2（函数方程在此失效）
  if (s >= 1.0) return hurwitz_zeta(s, 1.0, 16);
  if (s > 0.0) {
    // 项数随 s→0⁺ 增大：200/正数 保证抵消误差被压到 1e-12 量级
    int n = static_cast<int>(200.0 / (s + 0.1));
    if (n < 64) n = 64;
    if (n > 200000) n = 200000;
    return hurwitz_zeta(s, 1.0, n);
  }
  // s < 0：函数方程 ζ(s) = 2^s π^{s−1} sin(πs/2) Γ(1−s) ζ(1−s)
  const double g = gamma_real(1.0 - s);
  const double z = zeta_real(1.0 - s);  // 1−s > 1，不再进入本分支
  if (!std::isfinite(g) || !std::isfinite(z)) return nan;
  return std::pow(2.0, s) * std::pow(kPi, s - 1.0) * std::sin(kPi * s / 2.0) * g * z;
}

/**
 * ψ⁽ⁿ⁾(x)（n ≥ 1）。x ≤ 0 时用**递推**把自变量抬到正半轴，而不是套反射公式：
 *   ψ⁽ⁿ⁾(x) = ψ⁽ⁿ⁾(x+1) − (−1)ⁿ n! / x^(n+1)
 * 逐次右移，途中若撞上非正整数（极点）立即返回 NaN。
 * 校验：ψ′(1/2) = π²/2 ≈ 4.9348；ψ′(−1/2) = π²/2 + 4 ≈ 8.9348 ✓
 */
inline double polygamma_real(int n, double x) {
  const double nan = std::numeric_limits<double>::quiet_NaN();
  if (n < 0 || !std::isfinite(x)) return nan;
  if (n == 0) return digamma_real(x);
  if (is_integer_value(x) && x <= 0.0) return nan;  // 极点

  double fact = 1.0;
  for (int i = 2; i <= n; ++i) fact *= static_cast<double>(i);

  // 递推项系数 −(−1)ⁿ·n!
  const double rec = ((n % 2 == 0) ? -1.0 : 1.0) * fact;
  double r = 0.0;
  double y = x;
  int guard = 0;
  while (y < 1.0) {
    if (++guard > 1000000) return nan;
    if (is_integer_value(y) && y <= 0.0) return nan;  // 途中撞上极点
    r += rec / std::pow(y, static_cast<double>(n) + 1.0);
    y += 1.0;
  }
  // ψ⁽ⁿ⁾(y) = (−1)^(n+1) n! ζ(n+1, y)（y ≥ 1 > 0）
  const double sign2 = (n % 2 == 1) ? 1.0 : -1.0;
  const double z = hurwitz_zeta(static_cast<double>(n) + 1.0, y);
  if (!std::isfinite(z)) return nan;
  return r + sign2 * fact * z;
}

/** β(a,b) = Γ(a)Γ(b)/Γ(a+b)。 */
inline double beta_real(double a, double b) {
  const double ga = gamma_real(a), gb = gamma_real(b), gab = gamma_real(a + b);
  if (!std::isfinite(ga) || !std::isfinite(gb) || !std::isfinite(gab) || gab == 0.0)
    return std::numeric_limits<double>::quiet_NaN();
  return ga * gb / gab;
}

/** Lambert W 的主支 W₀(x)（x ≥ −1/e）；牛顿迭代解 w·eʷ = x。 */
inline double lambertw0_real(double x) {
  const double e_inv = 1.0 / std::exp(1.0);
  if (!std::isfinite(x) || x < -e_inv - 1e-15)
    return std::numeric_limits<double>::quiet_NaN();
  if (x == 0.0) return 0.0;
  double w = (x < 0.0) ? -0.5 : (std::log(x > 1.0 ? x : 1.0) + 0.1);
  for (int i = 0; i < 100; ++i) {
    const double ew = std::exp(w);
    const double f = w * ew - x;
    const double d = ew * (w + 1.0);
    if (std::fabs(d) < 1e-300) break;
    const double dw = f / d;
    w -= dw;
    if (std::fabs(dw) < 1e-16) break;
  }
  return w;
}

/**
 * 分支 W₋₁(x)（定义域 −1/e ≤ x < 0，值域 (−∞, −1]）。
 * 用 Halley 迭代；初值按"靠近 0⁻"和"靠近分支点"两种渐近式分别给出，
 * 否则迭代在分支点附近会不收敛。
 */
inline double lambertw_m1_real(double x) {
  const double nan = std::numeric_limits<double>::quiet_NaN();
  const double e_inv = 1.0 / std::exp(1.0);
  if (!std::isfinite(x) || x < -e_inv - 1e-15 || x >= 0.0) return nan;
  if (std::fabs(x + e_inv) < 1e-12) return -1.0;  // 分支点

  double w;
  if (x > -0.1) {
    const double l1 = std::log(-x);
    const double l2 = std::log(-l1);
    w = l1 - l2 + l2 / l1;  // x → 0⁻ 的渐近展开
  } else {
    const double t = std::sqrt(2.0 * (std::exp(1.0) * x + 1.0));
    w = -1.0 - t - t * t / 3.0;  // 分支点附近
  }
  for (int i = 0; i < 200; ++i) {
    const double ew = std::exp(w);
    const double f = w * ew - x;
    const double wp1 = w + 1.0;
    if (std::fabs(wp1) < 1e-300) break;
    const double dw = f / (ew * wp1);
    w -= dw;
    if (std::fabs(dw) < 1e-16) break;
  }
  return (w <= 0.0) ? w : nan;  // W₋₁ 必落在 (−∞, −1]
}

/** 按分支号取 W_k(x)：k=0 主轴，k=−1 负支。 */
inline double lambertw_real(double x, long long k) {
  if (k == 0) return lambertw0_real(x);
  if (k == -1) return lambertw_m1_real(x);
  return std::numeric_limits<double>::quiet_NaN();
}

// ── 与 SymEngine 表达式对接 ─────────────────────────────────────────────────

namespace detail {

/** 取数值实参（RealDouble / Integer / Rational），非数值返回 false。 */
inline bool arg_real(const SymEngine::RCP<const SymEngine::Basic>& a, double& out) {
  using namespace SymEngine;
  if (is_a<RealDouble>(*a)) { out = down_cast<const RealDouble&>(*a).as_double(); return true; }
  if (is_a<Integer>(*a)) { out = static_cast<double>(down_cast<const Integer&>(*a).as_int()); return true; }
  if (is_a<Rational>(*a)) {
    const auto& r = down_cast<const Rational&>(*a);
    const double n = static_cast<double>(r.get_num()->as_int());
    const double d = static_cast<double>(r.get_den()->as_int());
    if (d == 0.0) return false;
    out = n / d;
    return true;
  }
  return false;
}

}  // namespace detail

/**
 * 若 b 是"本文件支持的特殊函数节点且实参已是数值"，计算其值。
 * 返回 true 表示已处理（值可能为 NaN，表示该点无定义）。
 */
inline bool special_value_of(const SymEngine::Basic& b, double& out) {
  using namespace SymEngine;
  const auto args = b.get_args();
  const auto arg0 = [&](double& v) {
    return !args.empty() && detail::arg_real(args[0], v);
  };
  double x = 0.0, y = 0.0;

  if (is_a<Gamma>(b) && arg0(x)) { out = gamma_real(x); return true; }
  if (is_a<LogGamma>(b) && arg0(x)) { out = loggamma_real(x); return true; }
  if (is_a<Erf>(b) && arg0(x)) { out = std::erf(x); return true; }
  if (is_a<Erfc>(b) && arg0(x)) { out = std::erfc(x); return true; }
  if (is_a<Zeta>(b) && arg0(x)) { out = zeta_real(x); return true; }
  // lambertw(x) 或 lambertw(x, k)：k=0 主轴、k=−1 负支
  if (is_a<LambertW>(b) && arg0(x)) {
    long long k = 0;
    if (args.size() == 2) {
      double kd = 0.0;
      if (!detail::arg_real(args[1], kd)) return false;
      k = static_cast<long long>(std::llround(kd));
    }
    out = lambertw_real(x, k);
    return true;
  }
  if (is_a<PolyGamma>(b) && args.size() == 2 && detail::arg_real(args[0], x) &&
      detail::arg_real(args[1], y)) {
    out = polygamma_real(static_cast<int>(std::lround(x)), y);
    return true;
  }
  if (is_a<Beta>(b) && args.size() == 2 && detail::arg_real(args[0], x) &&
      detail::arg_real(args[1], y)) {
    out = beta_real(x, y);
    return true;
  }
  return false;
}

double eval_double_ex(const SymEngine::RCP<const SymEngine::Basic>& e,
                      const SymEngine::map_basic_basic& sub, int depth);

/**
 * 对不求值的 Derivative 节点做**数值微分**。
 *
 * SymEngine 的 diff 对 zeta 这类函数返回的是不求值节点 Derivative(zeta(x), x)，
 * 它既没有原生的 eval_double 实现，也不能直接代入 —— 代入会把求导变量换成数字
 * （变成"对 0.5 求导"这种无意义的东西）。因此必须在替换**之前**处理：
 * 用中心差分在 sub 给出的取值处算出导数值。
 *   f'(x0) ≈ (f(x0+h) − f(x0−h)) / (2h)
 *   f''(x0) ≈ (f(x0+h) − 2f(x0) + f(x0−h)) / h²
 * 只支持对同一个符号求导（阶数 1 或 2）；其它形式一律不处理。
 */
inline bool numeric_derivative_value(const SymEngine::Basic& b,
                                     const SymEngine::map_basic_basic& sub,
                                     int depth, double& out) {
  using namespace SymEngine;
  if (!is_a<Derivative>(b)) return false;
  if (depth > 3) return false;
  const auto& d = down_cast<const Derivative&>(b);
  const auto& syms = d.get_symbols();
  if (syms.empty()) return false;

  // 求导变量必须唯一（多重集里同一个符号出现几次就是几阶导）
  RCP<const Basic> var;
  int order = 0;
  for (const auto& s : syms) {
    if (!is_a<Symbol>(*s)) return false;
    if (var.is_null()) var = s;
    else if (neq(*var, *s)) return false;
    ++order;
  }
  if (order < 1 || order > 2) return false;

  const auto it = sub.find(var);
  if (it == sub.end()) return false;
  double x0 = 0.0;
  if (!detail::arg_real(it->second, x0)) return false;

  const double h = ((order == 1) ? 1e-6 : 1e-4) * std::max(1.0, std::fabs(x0));
  const auto at = [&](double xv) {
    SymEngine::map_basic_basic s = sub;
    s[var] = real_double(xv);
    return eval_double_ex(d.get_arg(), s, depth + 1);
  };
  const double fp = at(x0 + h), fm = at(x0 - h);
  if (!std::isfinite(fp) || !std::isfinite(fm)) return false;
  if (order == 1) {
    out = (fp - fm) / (2.0 * h);
    return std::isfinite(out);
  }
  const double f0 = at(x0);
  if (!std::isfinite(f0)) return false;
  out = (fp - 2.0 * f0 + fm) / (h * h);
  return std::isfinite(out);
}

/**
 * 自底向上把"当前实参已是数值的特殊函数节点"替换为 RealDouble，
 * 使剩下的表达式只含 eval_double 支持的算子。无法处理时返回 null。
 */
inline SymEngine::RCP<const SymEngine::Basic> numericize_special(
    const SymEngine::RCP<const SymEngine::Basic>& e) {
  using namespace SymEngine;
  const vec_basic args = e->get_args();
  SymEngine::map_basic_basic m;
  bool changed = false;
  for (const auto& a : args) {
    const auto na = numericize_special(a);
    if (na.is_null()) return null;
    if (neq(*na, *a)) { m[a] = na; changed = true; }
  }
  SymEngine::RCP<const SymEngine::Basic> node = e;
  if (changed && !m.empty()) node = e->subs(m);

  double v = 0.0;
  if (special_value_of(*node, v)) return real_double(v);
  return node;
}

/**
 * 增强求值：三级递进，任何一级成功即返回。
 *   ① 原生：替换后直接 eval_double（覆盖绝大多数表达式）
 *   ② Derivative 数值微分：在**替换前**处理不求值导数节点（zeta 等）
 *   ③ 特殊函数数值化：替换后把 Γ/ψ/ζ/W 等换成分数，再交给 eval_double
 * 任何算不出实数的情况统一返回 NaN。
 */
inline double eval_double_ex(const SymEngine::RCP<const SymEngine::Basic>& e,
                             const SymEngine::map_basic_basic& sub, int depth = 0) {
  using namespace SymEngine;
  const double nan = std::numeric_limits<double>::quiet_NaN();
  if (depth > 6) return nan;

  // ① 原生
  try {
    const auto e1 = e->subs(sub);
    const double v = eval_double(*e1);
    if (std::isfinite(v)) return v;
  } catch (...) {
    // 落到下一级
  }

  // ② 不求值导数（必须在替换前处理：替换会把求导变量变成常数）
  {
    double v = 0.0;
    if (numeric_derivative_value(*e, sub, depth, v)) return v;
  }

  // ③ 特殊函数数值化后再交给 eval_double
  SymEngine::RCP<const SymEngine::Basic> e1;
  try {
    e1 = e->subs(sub);
  } catch (...) {
    return nan;
  }
  const auto e2 = numericize_special(e1);
  if (e2.is_null()) return nan;
  try {
    const double v = eval_double(*e2);
    return std::isfinite(v) ? v : nan;
  } catch (...) {
    return nan;
  }
}

}  // namespace mf::num
