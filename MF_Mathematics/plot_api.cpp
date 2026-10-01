// plot_api.cpp — 绘图相关引擎能力
//
// 提供：
//   intersections {expr1, expr2, var?, vars?, xmin?, xmax?}
//       → 两条曲线的交点。策略：
//         ① 符号求解 f1 - f2 = 0（精确，含参数时给出符号形式）
//         ② 符号失败则数值扫描 + 二分细化（超越方程兜底）
//       对齐 Desmos 的"自动标记交点"，但精确解优先（Desmos 为数值近似）。
//   complex_eval {expr}
//       → 把（可能含虚数单位 I 的）符号表达式数值化为复数 {re, im}
//       复平面绘图用：solve_sym 求出的根（如 -1/2 + sqrt(3)*I/2）由此得到坐标。
//   complex_grid {expr, x0, x1, y0, y1, nx, ny?, digits?, var?}
//       → 在复矩形上求 f(z) 的网格值（复变函数可视化：相位图 / 模长曲面 /
//         向量场 / HSV 域着色 / 共形映射网格 都靠它取数据）。
//         返回 {re:[], im:[], nx, ny, ok, nan, maxMag, unsupported}，行优先（j 为 y 下标）。
//         为什么返回 re/im 而不是 mag/arg：共形映射需要 w 平面的坐标本身，
//         而 mag/arg 可以由前端一步算出；反过来则拿不回 w。
//         为什么放在引擎里：SymEngine 的复值求值只覆盖初等函数，zeta/gamma/erf
//         需要自己补（见 complex_numeric.h）——这些计算属于数学，不能挪到 JS。
//
// 设计约束：全程不做「静默降级」——符号与数值结果分别标注在 method/exact 字段。
#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"
#include "symbolic_util.h"
#include "symbolic_pretty.h"
#include "complex_numeric.h"

#include <cctype>

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/complex_double.h>
#include <symengine/constants.h>
#include <symengine/eval_double.h>
#include <symengine/integer.h>
#include <symengine/parser.h>
#include <symengine/real_double.h>
#include <symengine/sets.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

#include <algorithm>
#include <cmath>
#include <complex>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using mf::api::make_handler;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_double_opt;
using mf::api::get_double;

using SymEngine::Basic;
using SymEngine::RCP;

/** 读取 vars 参数（变量名 → 数值） */
std::map<std::string, double> read_vars(const Value& args) {
  std::map<std::string, double> vars;
  if (!args.is_object() || !args.has("vars")) return vars;
  const Value& v = args["vars"];
  if (!v.is_object()) return vars;
  for (const auto& key : v.keys()) {
    const Value& item = v[key];
    if (item.is_number() || item.is_int()) vars[key] = item.as_double();
  }
  return vars;
}

/** 把参数值代入表达式（参数未给出则保留为自由符号） */
RCP<const Basic> substitute_params(const RCP<const Basic>& e,
                                   const std::map<std::string, double>& vars) {
  if (vars.empty()) return e;
  SymEngine::map_basic_basic m;
  for (const auto& [k, v] : vars) m[SymEngine::symbol(k)] = SymEngine::real_double(v);
  return e->subs(m);
}

/** 在给定自变量取值下数值求值（用于数值回退） */
double eval_at(const RCP<const Basic>& e, const std::string& var, double xv) {
  const auto x = SymEngine::symbol(var);
  const auto v = e->subs({{x, SymEngine::real_double(xv)}});
  return SymEngine::eval_double(*SymEngine::simplify(v));
}

/** 数值求根：区间扫描找符号变化 + 二分细化 */
std::vector<double> numeric_roots(const RCP<const Basic>& h, const std::string& var,
                                  double x0, double x1, int samples = 4000) {
  std::vector<double> roots;
  const double dx = (x1 - x0) / samples;
  double prevX = x0, prevY = 0.0;
  bool hasPrev = false;
  for (int i = 0; i <= samples; ++i) {
    const double x = x0 + dx * i;
    double y;
    try {
      y = eval_at(h, var, x);
    } catch (...) {
      hasPrev = false;
      continue;   // 该点无定义（如 1/x），跳过并断开
    }
    if (!std::isfinite(y)) { hasPrev = false; continue; }

    if (hasPrev) {
      // 命中零点附近
      if (y == 0.0) { roots.push_back(x); }
      else if ((prevY < 0.0 && y > 0.0) || (prevY > 0.0 && y < 0.0)) {
        // 二分细化
        double a = prevX, b = x, fa = prevY;
        for (int k = 0; k < 80; ++k) {
          const double m = 0.5 * (a + b);
          double fm;
          try { fm = eval_at(h, var, m); } catch (...) { break; }
          if (!std::isfinite(fm)) break;
          if ((fa < 0.0 && fm < 0.0) || (fa > 0.0 && fm > 0.0)) { a = m; fa = fm; }
          else b = m;
        }
        roots.push_back(0.5 * (a + b));
      }
    }
    prevX = x; prevY = y; hasPrev = true;
  }
  // 去重（相邻极近的解视为同一交点）
  std::sort(roots.begin(), roots.end());
  std::vector<double> uniq;
  for (double r : roots) {
    if (uniq.empty() || std::abs(r - uniq.back()) > 1e-7) uniq.push_back(r);
  }
  return uniq;
}

void register_all() {
  using mf::registry::register_function;

  // ── 虚数单位归一化 ────────────────────────────────────────────────────
  //
  // 数学写法里虚数单位是小写 i（1+2i、3i，工程里还常用 j），而 SymEngine 的解析器
  // 只认大写 I；小写 i 会被当成一个自由符号，然后报"Symbol cannot be evaluated"。
  // 这里做一次受控替换，并且**必须按独立标识符判断**：
  //   · pi 里的 i（前一个字符是 p）不能动
  //   · sin 里的 i 不能动
  //   · 2i / 3j 这种隐式乘法要补成 2*I —— 否则 "2i" 会变成 "2I"，解析器认不出
  // 为什么放在引擎而不是前端：前端各处的归一化路径不一样，写在这儿才能保证
  // 所有调用方（结果弹窗、复平面绘图、控制台）行为一致。
  const auto normalize_imaginary_unit = [](const std::string& s) {
    std::string out;
    out.reserve(s.size() + 8);
    const auto is_word = [](char c) {
      return std::isalnum(static_cast<unsigned char>(c)) || c == '_';
    };
    for (std::size_t i = 0; i < s.size(); ++i) {
      const char c = s[i];
      if (c == 'i' || c == 'j') {
        const bool prev_word = i > 0 && is_word(s[i - 1]);
        const bool next_word = i + 1 < s.size() && is_word(s[i + 1]);
        if (!prev_word && !next_word) { out.push_back('I'); continue; }   // 独立的 i / j
        // 紧跟数字或右括号的 i（2i、(1+x)i）＝ 隐式乘法
        if (prev_word && !next_word && i > 0 &&
            (std::isdigit(static_cast<unsigned char>(s[i - 1])) || s[i - 1] == ')')) {
          out.push_back('*');
          out.push_back('I');
          continue;
        }
      }
      out.push_back(c);
    }
    return out;
  };

  // ── 复数数值化：符号表达式（可含 I）→ {re, im} ────────────────────────
  // 复平面绘图用：solve_sym 求出的根可能含虚数单位，需转成坐标才能画点。
  register_function("complex_eval", make_handler([normalize_imaginary_unit](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const auto e = SymEngine::parse(normalize_imaginary_unit(expr));
    std::complex<double> z;
    try {
      z = SymEngine::eval_complex_double(*e);
    } catch (const std::exception& ex) {
      throw std::invalid_argument(std::string("复数求值失败：") + ex.what());
    }
    if (!std::isfinite(z.real()) || !std::isfinite(z.imag())) {
      throw std::invalid_argument("复数求值得到非有限值（表达式含未绑定符号？）");
    }
    Value obj = Value::make_object();
    obj.set("re", Value(z.real()));
    obj.set("im", Value(z.imag()));
    obj.set("isReal", Value(std::abs(z.imag()) < 1e-12));
    return obj;
  }));

  // ── 批量复数数值化（一次转多个根，减少桥调用次数）──────────────────────
  register_function("complex_eval_many", make_handler([normalize_imaginary_unit](const Value& args) {
    if (!args.is_object() || !args.has("exprs") || !args["exprs"].is_array())
      throw std::invalid_argument("缺少数组参数 exprs");
    const Value& arr = args["exprs"];
    Value out = Value::make_array();
    for (std::size_t i = 0; i < arr.size(); ++i) {
      const std::string expr = arr.at(i).as_string();
      Value obj = Value::make_object();
      obj.set("expr", Value(expr));
      try {
        const auto z = SymEngine::eval_complex_double(*SymEngine::parse(normalize_imaginary_unit(expr)));
        if (std::isfinite(z.real()) && std::isfinite(z.imag())) {
          obj.set("re", Value(z.real()));
          obj.set("im", Value(z.imag()));
          obj.set("ok", Value(true));
        } else {
          obj.set("ok", Value(false));
          obj.set("error", Value(std::string("非有限值")));
        }
      } catch (const std::exception& ex) {
        obj.set("ok", Value(false));
        obj.set("error", Value(std::string(ex.what())));
      }
      out.push_back(obj);
    }
    return out;
  }));

  // ── 复网格求值：复变函数可视化的数据来源 ────────────────────────────────
  //
  // 五种绘制模式共用这一份数据：
  //   相位图 / HSV 域着色 / 3D 模长曲面 → 用 mag、arg
  //   向量场                            → 用中心点的 mag、arg
  //   共形映射网格                      → 用 w = f(z) 的坐标本身（所以必须给 re/im）
  //
  // 为什么一次返回整块网格而不是逐点调：200×200 = 4 万个点，逐点过桥的话
  // 光序列化开销就够呛；整块返回只过一次 JSON。
  //
  // 点数上限 400000：JSON 里每个数约 12 字节，400k 点 × 2 个数 ≈ 9.6 MB，
  // 超过这个量桥的缓冲就顶不住了（宿主那边会自动扩容重试，但也不该无上限）。
  // 超限直接报错说明原因，而不是悄悄降分辨率——静默降级是本项目禁止的。
  register_function("complex_grid", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const std::string var = mf::api::get_string_opt(args, "var", "z");
    const double x0 = get_double(args, "x0");
    const double x1 = get_double(args, "x1");
    const double y0 = get_double(args, "y0");
    const double y1 = get_double(args, "y1");
    const long long nx = (long long)get_double(args, "nx");
    const long long ny = (long long)get_double_opt(args, "ny", (double)nx);
    const long long digits = (long long)get_double_opt(args, "digits", 7.0);

    if (nx < 1 || ny < 1) throw std::invalid_argument("nx/ny 必须为正整数");
    if (nx * ny > 400000)
      throw std::invalid_argument(
          "网格点数 " + std::to_string(nx) + "×" + std::to_string(ny) +
          " 超过上限 400000，请降低分辨率（建议 ≤ 600×600）");

    // var 不是 z 时把表达式里的该符号改名为 z，求值器只认 z
    std::string src = expr;
    auto e = SymEngine::parse(src);
    if (var != "z") {
      using SymEngine::symbol;
      e = e->subs({{symbol(var), symbol("z")}});
    }

    mf::cnum::Ctx ctx;
    const std::size_t total = (std::size_t)(nx * ny);
    Value re = Value::make_array();
    Value im = Value::make_array();

    double max_mag = 0.0, min_mag = std::numeric_limits<double>::infinity();
    long long nan_count = 0;
    const auto round_to = [digits](double v) {
      if (!std::isfinite(v)) return v;
      if (digits <= 0 || digits > 17) return v;
      // 0 必须原样返回。下面那个 mag 由 log10(|v|) 推出来，v=0 时
      // log10(1e-300) = -300 → mag = 10^(digits+299)；digits ≥ 10 时这个幂超过
      // double 上限变成 +inf，于是 round(0*inf)/inf = NaN，JSON 写成 null，
      // 前端就把"值为 0"误判成"域外点"。
      // 这不是显示瑕疵：相位图里 re=0 或 im=0 的**整条线**（例如 1/z 的虚轴）
      // 会变成空白，而 nan 计数并不增加 → 调用方无法区分 0 和极点。
      // 边界实测：digits≤9 正常（10^308 仍有限），10~17 坏，≥18 走上面的原样返回分支。
      if (v == 0.0) return 0.0;
      // 保留 digits 位有效数字：JSON 体积直接减半，而画图用不到更多
      const double mag = std::pow(10.0, digits - 1 - std::floor(std::log10(std::abs(v))));
      return std::round(v * mag) / mag;
    };

    for (long long j = 0; j < ny; ++j) {
      const double y = ny == 1 ? y0 : y0 + (y1 - y0) * (double)j / (double)(ny - 1);
      for (long long i = 0; i < nx; ++i) {
        const double x = nx == 1 ? x0 : x0 + (x1 - x0) * (double)i / (double)(nx - 1);
        const std::complex<double> z(x, y);
        std::complex<double> w;
        try {
          w = mf::cnum::eval_node(*e, z, ctx);
        } catch (...) {
          w = std::complex<double>(std::numeric_limits<double>::quiet_NaN(), 0.0);
        }
        if (!mf::cnum::finite_c(w)) {
          // 域外点（分支点、极点、溢出）一律给 null，由前端画成空白——
          // 这是全项目统一的「域外点」表达方式（见 expr_api 的 finite_or_text）
          re.push_back(Value());
          im.push_back(Value());
          ++nan_count;
          continue;
        }
        const double m = std::abs(w);
        if (std::isfinite(m)) {
          if (m > max_mag) max_mag = m;
          if (!(m < 1e-12)) { if (m < min_mag) min_mag = m; }
        }
        re.push_back(Value(round_to(w.real())));
        im.push_back(Value(round_to(w.imag())));
      }
    }

    Value obj = Value::make_object();
    obj.set("re", re);
    obj.set("im", im);
    obj.set("nx", Value(nx));
    obj.set("ny", Value(ny));
    obj.set("ok", Value((long long)(total - nan_count)));
    obj.set("nan", Value(nan_count));
    obj.set("x0", Value(x0));
    obj.set("x1", Value(x1));
    obj.set("y0", Value(y0));
    obj.set("y1", Value(y1));
    obj.set("maxMag", Value(std::isfinite(max_mag) ? max_mag : 0.0));
    obj.set("minMag", Value(std::isfinite(min_mag) ? min_mag : 0.0));
    // 表达式中出现了算不出来的东西 → 明确报出来，别让用户对着空白图猜
    obj.set("unsupported", Value(ctx.unsupported));
    return obj;
  }));

  register_function("intersections", make_handler([](const Value& args) {
    const std::string e1s = get_string(args, "expr1");
    const std::string e2s = get_string(args, "expr2");
    const std::string var = get_string_opt(args, "var", "x");
    const std::map<std::string, double> vars = read_vars(args);
    const double xmin = get_double_opt(args, "xmin", -50.0);
    const double xmax = get_double_opt(args, "xmax", 50.0);

    const auto f1 = substitute_params(SymEngine::parse(e1s), vars);
    const auto f2 = substitute_params(SymEngine::parse(e2s), vars);
    const auto h = SymEngine::expand(SymEngine::sub(f1, f2));

    Value points = Value::make_array();
    std::string method = "numeric";
    bool exact = false;

    // ① 符号求解（仅当 h 不含自由符号时结果可直接使用；含参数时保留符号形式）
    //    注意：判断的是「除自变量外是否还有参数」，而非「是否含任何符号」
    //    （自变量 var 本身也是自由符号，误判会导致复数解不被过滤）
    const bool symbolic = mf::symutil::has_other_symbols(*h, var);
    long long skipped_complex = 0;

    // 实根性判定：含参数时**不能**默认判为虚根。旧实现直接对含参根调
    // eval_double，失败即 real=false，于是 x² = a·x+1（Δ = a²+4 > 0 恒成立）
    // 的两个实交点被标成虚根，解析几何的判别式分类讨论整体失效。
    // 现在先做可证明的实根性判定（二次式用 Δ 符号），再把结论写到每个点上。
    const mf::symutil::RealnessReport rn =
        mf::symutil::equation_realness(h, var);

    try {
      const auto roots = mf::symutil::safe_solve(h, SymEngine::symbol(var), "交点方程");
      if (SymEngine::is_a<SymEngine::FiniteSet>(*roots)) {
        const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*roots);
        for (const auto& rt : fs.get_args()) {
          const auto yv = SymEngine::simplify(
              f1->subs({{SymEngine::symbol(var), rt}}));
          // 绘图用的交点只在实轴上：无参数（纯数值）情形下过滤复数解
          // （如 x²=-1 的解 ±i 不是可视交点）。含参时无法判定实虚，保留符号形式。
          double xnum = 0.0, ynum = 0.0;
          bool numeric_ok = true;
          try {
            xnum = SymEngine::eval_double(*rt);
            ynum = SymEngine::eval_double(*yv);
            if (!std::isfinite(xnum) || !std::isfinite(ynum)) numeric_ok = false;
          } catch (...) {
            numeric_ok = false;
          }

          // 实根性结论：可证明时给出 true/false；含参且证不出时**不下结论**
          // （real 输出 null，而不是把「未知」伪装成「虚根」）
          bool known = false;
          bool real_flag = false;
          std::string realness;
          switch (rn.kind) {
            case mf::symutil::RootRealness::Real:
              known = true; real_flag = true; realness = "real"; break;
            case mf::symutil::RootRealness::Complex:
              known = true; real_flag = false; realness = "complex"; break;
            case mf::symutil::RootRealness::Conditional:
              realness = "conditional"; break;
            default:
              if (symbolic) { realness = "unknown"; }
              else { known = numeric_ok; real_flag = numeric_ok; realness = numeric_ok ? "real" : "complex"; }
              break;
          }
          // 具体代入数值后能算出实数的，以数值结果为准（最直接、无争议）
          if (numeric_ok) { known = true; real_flag = true; realness = "real"; }

          if (!symbolic && !numeric_ok) { skipped_complex++; continue; }
          if (!symbolic && known && !real_flag) { skipped_complex++; continue; }

          Value pt = Value::make_object();
          pt.set("x", Value(mf::symutil::pretty_math(rt)));
          pt.set("y", Value(mf::symutil::pretty_math(yv)));
          // real：可判定时为 true/false；含参且无法判定时为 null（显式「未知」）
          pt.set("real", known ? Value(real_flag) : Value());
          pt.set("realness", Value(realness));
          if (numeric_ok) {
            pt.set("xNum", Value(xnum));
            pt.set("yNum", Value(ynum));
          }
          points.push_back(pt);
        }
        if (points.size() > 0) method = "symbolic";
        exact = true;
      }
    } catch (...) {
      // 符号求解失败 → 走数值回退（下面处理）
    }

    // ② 数值回退：符号无解或无实根时，在 [xmin, xmax] 扫描
    if (!exact || points.size() == 0) {
      points = Value::make_array();
      method = "numeric";
      exact = false;
      std::vector<double> roots;
      try {
        roots = numeric_roots(h, var, xmin, xmax);
      } catch (...) {
        roots.clear();
      }
      for (double r : roots) {
        Value pt = Value::make_object();
        char buf[64];
        std::snprintf(buf, sizeof(buf), "%.12g", r);
        pt.set("x", Value(std::string(buf)));
        pt.set("xNum", Value(r));
        try {
          const double y = eval_at(f1, var, r);
          char ybuf[64];
          std::snprintf(ybuf, sizeof(ybuf), "%.12g", y);
          pt.set("y", Value(std::string(ybuf)));
          pt.set("yNum", Value(y));
        } catch (...) {
          pt.set("y", Value(std::string("—")));
        }
        points.push_back(pt);
      }
    }

    Value obj = Value::make_object();
    obj.set("method", Value(method));
    obj.set("exact", Value(exact));
    obj.set("symbolic", Value(symbolic));
    obj.set("var", Value(var));
    obj.set("points", points);
    obj.set("count", Value(static_cast<long long>(points.size())));
    // 实根性总览：调用方（含解析几何的判别式分类讨论）据此分段，
    // 而不是去猜 real=false 到底是「虚根」还是「没判定出来」。
    obj.set("realness", Value(std::string(mf::symutil::root_realness_name(rn.kind))));
    obj.set("realnessReason", Value(rn.reason));
    if (!rn.delta.empty()) {
      obj.set("delta", Value(rn.delta));
      obj.set("deltaSign", Value(std::string(mf::symutil::sign_name(rn.delta_sign))));
    }
    // 复数解计数：绘图只画实轴交点，复数解被过滤（明确告知，不静默）
    obj.set("skippedComplex", Value(skipped_complex));
    return obj;
  }));
}

struct Registrar { Registrar() { register_all(); } };
const Registrar g_plot_registrar;

}  // namespace
