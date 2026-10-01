// symbolic_api.cpp — 符号能力接口（保留精确形式，禁止数值化降级）
//
// 背景：引擎原有符号函数（discriminant / factor / monotonicity / local_extrema）
// 在关键路径上调用 SymEngine::eval_double 把精确结果强行转 double，
// 遇到自由符号（如 x^2-a 中的 a）就失败：轻则报 "Symbol cannot be evaluated."，
// 重则被 catch 吞掉后静默返回空结果（错答）。
//
// 本文件提供"符号版"接口，全程不对自由符号做数值化：
//   solve_sym        {expr, var}  → 精确解集合（含自由符号）+ 实根性
//   discriminant_sym {expr, var}  → 符号判别式 Δ = b²-4ac + 可证明的符号
//   factor_sym       {expr}       → 符号因式分解
//   compare_expr     {a, b}       → 表达式等价判定
//   simplify_sym     {expr}       → 精确化简（多候选取最简）
//   extrema_sym      {expr}       → 含参极值 + 参数分类讨论
//   free_symbols_of  {expr}       → 表达式的自由符号列表（辅助/前置检查）
//
// 输出统一用 pretty_math() 排版（教科书记号），不再外泄 a**(-1) 这类机器记号。
#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"
#include "symbolic_util.h"
#include "symbolic_pretty.h"

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/derivative.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/mul.h>
#include <symengine/parser.h>
#include <symengine/pow.h>
#include <symengine/sets.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>
#include <symengine/visitor.h>

#include <algorithm>
#include <cctype>
#include <functional>
#include <cstddef>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using mf::api::make_handler;
using mf::api::get_string;
using mf::api::get_string_opt;
using mf::api::get_equation;
using mf::api::get_double_opt;

using SymEngine::Basic;
using SymEngine::RCP;

using mf::symutil::symbol_names;
using mf::symutil::has_other_symbols;
using mf::symutil::factor_of_root;

/**
 * 符号名是否像合法标识符（ASCII 字母/下划线开头，其后只允许字母数字下划线）。
 *
 * 存在意义：SymEngine 的解析器对非 ASCII 串**不报错**，而是把整串当成一个符号名
 * ——实测 SymEngine::parse("√2") 成功，free_symbols = ['√2']。于是 "√2" 会被静默
 * 读成"名为 √2 的变量"：compare_expr({"a":"√2","b":"2"}) 因此给出"在样本点
 * 2.3 ≠ 2.0 处取值不同"这种把用户输入当自变量的错答。凡是解析出的符号名不像
 * 标识符，就说明这串其实该先规范化（√ → sqrt、π → pi、\frac → /…）再解析。
 */
bool plausible_symbol_name(const std::string& n) {
  if (n.empty()) return false;
  const unsigned char first = static_cast<unsigned char>(n[0]);
  if (!(std::isalpha(first) || first == '_')) return false;
  for (std::size_t i = 1; i < n.size(); ++i) {
    const unsigned char c = static_cast<unsigned char>(n[i]);
    if (!(std::isalnum(c) || c == '_')) return false;
  }
  return true;
}

/** 表达式里是否存在"不像标识符"的符号名（即该串需要先规范化）。 */
bool has_implausible_symbols(const Basic& e) {
  for (const auto& n : symbol_names(e))
    if (!plausible_symbol_name(n)) return true;
  return false;
}

// ── 辅助 ────────────────────────────────────────────────────────────────────

Value to_string_array(const std::vector<std::string>& v) {
  Value arr = Value::make_array();
  for (const auto& s : v) arr.push_back(Value(s));
  return arr;
}

/** 字符串数组 → 教科书记号数组。
 *
 *  安全网：排版结果必须能重新解析回**等价**的表达式才采用，否则保留原字符串。
 *  这些字段（如 solve_sym 的 solutions）会被调用方回喂给引擎（complex_eval 等），
 *  一旦排版引入不可解析的写法（例如把虚数单位写成 i、把 zoo 写成中文），
 *  调用方就会静默拿不到结果。往返校验把这类风险挡在这里。 */
Value to_pretty_array(const std::vector<std::string>& v) {
  Value arr = Value::make_array();
  for (const auto& s : v) {
    try {
      const auto orig = SymEngine::parse(s);
      const auto text = mf::symutil::pretty_math_str(s);
      if (SymEngine::eq(*SymEngine::parse(text), *orig)) {
        arr.push_back(Value(text));
        continue;
      }
    } catch (...) {
    }
    arr.push_back(Value(s));  // 不可往返 → 原样保留
  }
  return arr;
}

/** 求解精确根集合；非有限解集时抛异常（不静默返回空）。
 *
 *  结果先经 reduce_root_radicals 归约：把 √(a²) 这类"其实能开出来"的根
 *  化为 a（如 x²-a² 的根 ±√(a²) → ±a，因式分解即得 (x + a)*(x - a)）。
 *  归约只在多项式恒等验证通过后采用，不做无据化简。 */
std::vector<std::string> exact_roots(const RCP<const Basic>& eq,
                                     const std::string& var,
                                     mf::symutil::SolvePolicy policy = mf::symutil::SolvePolicy::Strict,
                                     std::string* note = nullptr,
                                     std::string* general = nullptr) {
  const auto x = SymEngine::symbol(var);
  const auto sol = mf::symutil::safe_solve(eq, x, "方程", policy, note);
  std::vector<std::string> out;
  if (!SymEngine::is_a<SymEngine::FiniteSet>(*sol)) {
    // 非有限集（例如三角方程的周期通解 ImageSet/ConditionSet）：
    // 有 general 出口就原样回传，没有就按老规矩报错 —— 不静默丢结果。
    if (general != nullptr) {
      *general = SymEngine::str(*sol);
      return out;
    }
    throw std::invalid_argument(
        "无法求出精确解集（该方程形式超出符号求解范围；若含参数请逐项处理）");
  }
  const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*sol);
  for (const auto& rt : fs.get_args()) out.push_back(SymEngine::str(*rt));
  out = mf::symutil::reduce_root_radicals(out, var);
  std::sort(out.begin(), out.end());
  out.erase(std::unique(out.begin(), out.end()), out.end());
  return out;
}

/** 对"已无自由符号"的表达式做符号判定（非降级：调用方须先确保无参数）。
 *  含虚数单位（如 a<0 时 √a → 纯虚）→ 明确标注 no-real-value，而不是含糊的 unknown。 */
std::string classify_numeric(const RCP<const Basic>& v) {
  try {
    // 用增强求值：Gamma/PolyGamma 等没有原生 eval_double 实现，
    // 直接调用会把极值类型误判成 no-real-value
    const double d = mf::num::eval_double_ex(SymEngine::simplify(v), {});
    if (d < 0.0) return "maximum";
    if (d > 0.0) return "minimum";
    if (d == 0.0) return "degenerate";
    return "unknown";
  } catch (...) {
    // eval_double 不接受复数 → 该分支下二阶导非实数，极值判定不适用
    return "no-real-value";
  }
}

/** 参数分支代表值取样：已抽到 symbolic_util.h，供绘图侧（intersections）共用。 */
using mf::symutil::param_branches;
using mf::symutil::Branch;


/** 收集形如 sin(u)**2 / cos(u)**2 的子表达式（供三角恒等替换使用）。 */
void collect_trig_squares(const RCP<const Basic>& e,
                          std::vector<RCP<const Basic>>& sins,
                          std::vector<RCP<const Basic>>& coss) {
  using namespace SymEngine;
  if (is_a<Pow>(*e)) {
    const auto& p = down_cast<const Pow&>(*e);
    if (eq(*p.get_exp(), *integer(2))) {
      if (is_a<Sin>(*p.get_base())) sins.push_back(e);
      else if (is_a<Cos>(*p.get_base())) coss.push_back(e);
    }
  }
  for (const auto& a : e->get_args()) collect_trig_squares(a, sins, coss);
}

// ── 驻点有效性判定 ──────────────────────────────────────────────────────────
//
// 导数零点只是"驻点"，要成为**极值点**还必须：① 该点本身存在；
// ② 落在函数定义域内。两件事都必须逐分支检查，否则会给出看似合理的错答案：
//   f = a·x − ln x（定义域 x>0），f'=0 的根是 x=1/a
//     · a<0 → x=1/a < 0，不在定义域内 → 该分支**无极值点**
//     · a=0 → 1/a 无定义      → 该分支**无极值点**
//   旧实现只看 f''(1/a)=a²>0，两个分支都报 minimum。

struct CritPoint {
  bool exists = false;
  std::string kind;  // exists=false 时的原因分类
  std::string note;  // 可读说明
  double x = 0.0;
};

/** 判断驻点在给定参数取值下是否存在、是否落在定义域内、是否真的满足 f'=0。 */
CritPoint eval_critical_point(
    const RCP<const Basic>& root, const std::string& var,
    const SymEngine::map_basic_basic& param_sub,
    const std::vector<mf::symutil::DomainConstraint>& dom,
    const RCP<const Basic>& derivative) {
  using namespace SymEngine;
  CritPoint out;

  // ⓿ 先看 f′ 在该分支下是否**退化成常数**（不再含自变量）。
  //    这种情况方程 f′=0 根本无解，必须说"无极值点"，而不是等到残差复核
  //    发现"求解器给的根不满足 f′=0"再说"结果不可信"——后者把
  //    "本来就没有驻点"错说成"求解器算错了"，粒度对不上。
  //    例：f = x − a·ln x 在 a=0 时 f′ ≡ 1；f = a/x − x 在 a=0 时 f′ ≡ −1。
  if (!derivative.is_null()) {
    RCP<const Basic> dsub;
    try {
      dsub = derivative->subs(param_sub);
    } catch (...) {
      dsub = null;
    }
    if (!dsub.is_null()) {
      bool still_has_var = false;
      for (const auto& n : mf::symutil::symbol_names(*dsub))
        if (n == var) still_has_var = true;
      if (!still_has_var) {
        const double cv = mf::num::eval_double_ex(dsub, {});
        if (std::isfinite(cv)) {
          char buf[64];
          std::snprintf(buf, sizeof(buf), "%.6g", cv);
          if (std::fabs(cv) > 1e-12) {
            out.kind = "no-critical-point";
            out.note = std::string("该分支下 f′ 退化为常数 ") + buf +
                       " ≠ 0，方程 f′=0 无解，因此不存在极值点";
          } else {
            out.kind = "degenerate";
            out.note = "该分支下 f′ ≡ 0：函数为常数，处处是驻点但无极值";
          }
          return out;
        }
      }
    }
  }

  // ① 驻点本身是否存在（1/a 在 a=0、√a 在 a<0 都不存在）
  RCP<const Basic> xv;
  try {
    xv = root->subs(param_sub);
  } catch (...) {
    out.kind = "no-critical-point";
    out.note = "驻点表达式在该分支下无定义";
    return out;
  }
  double xnum = 0.0;
  bool finite = true;
  try {
    xnum = eval_double(*xv);
    finite = std::isfinite(xnum);
  } catch (...) {
    finite = false;
  }
  if (!finite) {
    out.kind = "no-critical-point";
    out.note = "驻点 " + mf::symutil::pretty_math(root) +
               " 在该分支下无定义或不是实数（分母为零 / 偶次根号内为负）";
    return out;
  }
  out.x = xnum;

  // ② 驻点必须真的满足 f'(x₀) = 0。
  //    SymEngine::solve 偶尔给出未化简、甚至只在个别参数取值下才成立的根：
  //    例 f = a·x + atan(x)，真实驻点是 ±√(−(1+a)/a)，求解器却返回
  //    sqrt(-1 + a/a)（a/a 没约成 1，于是被当成 x = 0）。
  //    只按"数值有限"就接受，会凭空报出一个错误的驻点及其极值类型。
  //    做法：用分支代表值代入 f'，残差必须为 0（浮点容差内）。
  if (!derivative.is_null()) {
    try {
      SymEngine::map_basic_basic rsub = param_sub;
      rsub[symbol(var)] = real_double(xnum);
      const double r = eval_double(*derivative->subs(rsub));
      if (std::isfinite(r) && std::fabs(r) > 1e-6) {
        char buf[64];
        std::snprintf(buf, sizeof(buf), "%.6g", r);
        out.kind = "solver-unreliable";
        out.note = std::string("求解器给出的驻点在当前参数下并不满足 f′=0（残差 ") +
                   buf + "），该结果不可信，已拒绝据此判定极值";
        return out;
      }
    } catch (...) {
      // 残差算不出实数（如 f' 在该点有极点）→ 无法复核，保持后续正常判定
    }
  }

  // ③ 是否落在定义域内
  if (!dom.empty()) {
    SymEngine::map_basic_basic sub = param_sub;
    sub[symbol(var)] = real_double(xnum);
    const auto v = mf::symutil::check_domain(dom, sub);
    if (v == mf::symutil::DomainVerdict::Outside) {
      char buf[64];
      std::snprintf(buf, sizeof(buf), "%.6g", xnum);
      out.kind = "outside-domain";
      out.note = std::string("驻点 x = ") + buf + " 落在定义域之外，该分支无极值点";
      return out;
    }
    if (v == mf::symutil::DomainVerdict::Undefined) {
      out.kind = "outside-domain";
      out.note = "驻点处定义域约束的表达式不是实数，该点不在定义域内";
      return out;
    }
    if (v == mf::symutil::DomainVerdict::Unknown)
      out.note = "定义域未能判定，按驻点有效处理";
  }

  out.exists = true;
  return out;
}

/**
 * 把一个参数分支的"代表值"展开成**多个样本**。
 *
 * 单个代表值可能恰好是特例：f = a·x + atan(x) 的真实驻点是 ±√(−(1+a)/a)，
 * 但求解器返回的表达式在 a = −1 时恰好给出正确的 x = 0，在 a = −2 时才暴露
 * 它并不满足 f′=0。只取一个代表值就会把这种"特例成立"误当成"该分支成立"。
 * 因此每个非零参数取同号的两个不同值，任一取值复核失败即判该分支不可信。
 */
std::vector<std::vector<int>> branch_sample_sets(const std::vector<int>& values) {
  std::vector<std::vector<int>> per_param;
  per_param.reserve(values.size());
  for (int v : values) {
    if (v > 0) per_param.push_back({1, 3});
    else if (v < 0) per_param.push_back({-1, -2});
    else per_param.push_back({0});
  }
  std::vector<std::vector<int>> out = {{}};
  for (const auto& opts : per_param) {
    std::vector<std::vector<int>> next;
    next.reserve(out.size() * opts.size());
    for (const auto& base : out)
      for (int o : opts) {
        auto row = base;
        row.push_back(o);
        next.push_back(std::move(row));
      }
    out = std::move(next);
  }
  return out;
}

/** 结论严重度：样本之间不一致时，取最严重的那个结论作为该分支的结论。 */
int crit_kind_rank(const std::string& kind) {
  if (kind == "solver-unreliable") return 3;  // 结果本身不可信，最优先告知
  if (kind == "outside-domain") return 2;
  if (kind == "no-critical-point") return 1;
  return 0;
}

/** 教科书记号排版（带往返校验）：排版结果必须能解析回**等价**表达式才采用，
 *  否则退回 SymEngine 原生字符串。
 *
 *  为什么必须校验：SymEngine 重排表达式时可能出现不等价的改写，例如把
 *  -(1+a)/a 表示成 -1 + a/a（而 a/a 不会约成 1，数值上并不相等）。
 *  直接展示排版结果就会把 a=-2 时的 -0.5 显示成 0。 */
std::string display(const RCP<const Basic>& e) {
  try {
    const std::string text = mf::symutil::pretty_math(e);
    if (SymEngine::eq(*SymEngine::parse(text), *e)) return text;
  } catch (...) {
  }
  return SymEngine::str(*e);
}

// ── 换元降次求驻点 ──────────────────────────────────────────────────────────
//
// SymEngine::solve 对含 sqrt/tan 的驻点方程要么栈溢出、要么静默返回空集，
// 但这两类正是高考高频形态。解法就是学生本来就会的那一手**换元**：
//   · 出现 √(c₁x+c₀) → 令 t = √g，则 g = t²，x = (t²-c₀)/c₁
//   · 出现 tan(c₁x+c₀) → 令 t = tan g，则 g = atan(t) + kπ，x = (atan(t)+kπ-c₀)/c₁
// 换元后方程化为关于 t 的有理式，清分母即得多项式方程，求解器的安全区。
// 回代得到的 x 仍会被后面的"f'(x₀)=0 残差复核"逐分支验证，
// 因此换元引入的伪根不会漏到结论里。

/** g 关于 var 线性？是则给出 g = c1*var + c0。 */
bool linear_in(const RCP<const Basic>& g, const std::string& var,
               RCP<const Basic>& c1, RCP<const Basic>& c0) {
  using namespace SymEngine;
  const auto x = symbol(var);
  RCP<const Basic> e;
  try {
    e = expand(g);
  } catch (...) {
    return false;
  }
  c1 = coeff(*e, *x, *integer(1));
  if (eq(*c1, *zero)) return false;
  RCP<const Basic> rest;
  try {
    rest = expand(sub(e, mul(c1, x)));
  } catch (...) {
    return false;
  }
  for (const auto& n : symbol_names(*rest))
    if (n == var) return false;  // 仍有 var → 非线性
  c0 = rest;
  return true;
}

/** 收集 √g 的被开方式与 tan 的自变量。
 *  注意根式常以**负指数**出现（如 a/(2√x) = a/2 · x^(−1/2)），
 *  只找指数 +1/2 会漏掉这类，导致换元根本不触发。 */
void collect_generators(const RCP<const Basic>& e,
                        std::vector<RCP<const Basic>>& sqrt_bases,
                        std::vector<RCP<const Basic>>& tan_args) {
  using namespace SymEngine;
  if (is_a<Pow>(*e)) {
    const auto& p = down_cast<const Pow&>(*e);
    const RCP<const Basic> exp = p.get_exp();
    // 指数分母为 2（±1/2、±3/2…）即根式
    if (is_a<Rational>(*exp)) {
      const auto& r = down_cast<const Rational&>(*exp);
      if (eq(*r.get_den(), *integer(2)) && !eq(*r.get_num(), *zero))
        sqrt_bases.push_back(p.get_base());
    }
  }
  if (is_a<Tan>(*e)) tan_args.push_back(e->get_args()[0]);
  for (const auto& a : e->get_args()) collect_generators(a, sqrt_bases, tan_args);
}

/** 根式 Pow(g, p/2) 对应的 t 的幂：t = √g ⇒ g^(p/2) = t^p（t>0，负指数同样成立）。 */
bool sqrt_exponent_power(const RCP<const Basic>& exp, RCP<const Basic>& tpow) {
  using namespace SymEngine;
  if (!is_a<Rational>(*exp)) return false;
  const auto& r = down_cast<const Rational&>(*exp);
  if (!eq(*r.get_den(), *integer(2))) return false;
  tpow = r.get_num();  // p（可为负）
  return true;
}

struct ReducedSolve {
  bool ok = false;
  std::string method;
  std::string note;
  std::vector<std::string> roots;  // 关于 var 的根（精确形式）
};

/** 把关于新变量的解回代为关于 var 的解，并按字符串去重。 */
std::vector<std::string> dedup_strings(std::vector<std::string> v) {
  std::sort(v.begin(), v.end());
  v.erase(std::unique(v.begin(), v.end()), v.end());
  return v;
}

/**
 * 尝试换元求驻点。返回 ok=false 表示该形式不在换元覆盖范围内
 * （调用方据此改走数值回退或如实报错，不得假装已覆盖）。
 */
ReducedSolve reduced_critical_points(const RCP<const Basic>& d1,
                                     const std::string& var) {
  using namespace SymEngine;
  ReducedSolve out;
  const auto x = symbol(var);
  const auto t = symbol("t__sub");

  std::vector<RCP<const Basic>> sq, tn;
  collect_generators(d1, sq, tn);

  // ── 换元一：√(c₁x+c₀) = t ────────────────────────────────────────────────
  // 只处理**唯一**一个根式的情形：多个根式需要逐个消去，超出本层能力，
  // 硬做会得到不可靠的结果，不如交给数值回退。
  if (sq.size() == 1 && tn.empty()) {
    RCP<const Basic> c1, c0;
    if (linear_in(sq[0], var, c1, c0)) {
      try {
        // 该根式所有出现形式（含负指数）都换成 t 的对应幂
        map_basic_basic m;
        for (const auto& node : d1->get_args())
          (void)node;
        {
          // 遍历 d1 收集所有 Pow(g, p/2)（g 为同一线性式）
          std::vector<RCP<const Basic>> pows;
          std::function<void(const RCP<const Basic>&)> walk =
              [&](const RCP<const Basic>& n) {
                if (is_a<Pow>(*n)) {
                  const auto& p = down_cast<const Pow&>(*n);
                  if (eq(*p.get_base(), *sq[0])) {
                    RCP<const Basic> tp;
                    if (sqrt_exponent_power(p.get_exp(), tp)) pows.push_back(n);
                  }
                }
                for (const auto& a : n->get_args()) walk(a);
              };
          walk(d1);
          for (const auto& n : pows) {
            RCP<const Basic> tp;
            sqrt_exponent_power(down_cast<const Pow&>(*n).get_exp(), tp);
            m[n] = pow(t, tp);
          }
        }
        if (m.empty()) return out;
        const auto e1 = d1->subs(m);
        map_basic_basic m2;
        m2[x] = div(sub(pow(t, integer(2)), c0), c1);
        const auto e2 = expand(e1->subs(m2));
        bool still_var = false;
        for (const auto& n : symbol_names(*e2))
          if (n == var) still_var = true;
        if (!still_var) {
          RCP<const Basic> num, den;
          as_numer_denom(e2, outArg(num), outArg(den));
          const auto sol = mf::symutil::safe_solve(expand(num), t, "换元后的驻点方程");
          if (is_a<FiniteSet>(*sol)) {
            const auto& fs = down_cast<const FiniteSet&>(*sol);
            std::vector<std::string> roots;
            for (const auto& rt : fs.get_args()) {
              // t = √g，回代 x = (t²-c₀)/c₁；t 与 -t 给出同一个 x，故无需筛选符号
              const auto xi = SymEngine::simplify(
                  div(sub(pow(rt, integer(2)), c0), c1));
              roots.push_back(SymEngine::str(*xi));
            }
            if (!roots.empty()) {
              out.ok = true;
              out.method = "substitution-sqrt";
              out.note = "换元 t = √(" + SymEngine::str(*sq[0]) +
                         ") 化为多项式方程后求解，再回代 x = (t² − " +
                         SymEngine::str(*c0) + ") / " + SymEngine::str(*c1);
              out.roots = dedup_strings(std::move(roots));
            }
          }
        }
      } catch (...) {
        // 换元后仍不可解 → 交给数值回退
      }
    }
  }

  // ── 换元二：tan(c₁x+c₀) = t ──────────────────────────────────────────────
  if (!out.ok && tn.size() == 1 && sq.empty()) {
    RCP<const Basic> c1, c0;
    if (linear_in(tn[0], var, c1, c0)) {
      try {
        map_basic_basic m;
        m[tan(tn[0])] = t;
        const auto e1 = d1->subs(m);
        // 换元后若 var 仍出现，就无法只用 t 表示 x（代入 atan 后不再是多项式）
        bool still_var = false;
        for (const auto& n : symbol_names(*e1))
          if (n == var) still_var = true;
        if (!still_var) {
          RCP<const Basic> num, den;
          as_numer_denom(e1, outArg(num), outArg(den));
          const auto sol = mf::symutil::safe_solve(expand(num), t, "换元后的驻点方程");
          if (is_a<FiniteSet>(*sol)) {
            const auto& fs = down_cast<const FiniteSet&>(*sol);
            std::vector<std::string> roots;
            for (const auto& rt : fs.get_args()) {
              // c₁x + c₀ = atan(t) + kπ → 取 k = 0 的主值，周期性在 note 中说明
              const auto xi = SymEngine::simplify(
                  div(sub(atan(rt), c0), c1));
              roots.push_back(SymEngine::str(*xi));
            }
            if (!roots.empty()) {
              out.ok = true;
              out.method = "substitution-tan";
              out.note = "换元 t = tan(" + SymEngine::str(*tn[0]) +
                         ") 化为多项式方程后求解，回代取主值 x = (atan(t) − " +
                         SymEngine::str(*c0) + ") / " + SymEngine::str(*c1) +
                         "；由周期性，通解为 x + kπ/" + SymEngine::str(*c1) +
                         "（k ∈ ℤ，主值与其余分支的极值类型相同）";
              out.roots = dedup_strings(std::move(roots));
            }
          }
        }
      } catch (...) {
      }
    }
  }

  return out;
}

/** 读取可选参数对象 vars（与 intersections 的 read_vars 同义），
 *  用于把参数替换成具体数值后再做数值求解。 */
std::map<std::string, double> read_vars(const Value& args) {
  std::map<std::string, double> out;
  if (!args.is_object() || !args.has("vars")) return out;
  const Value& v = args["vars"];
  if (!v.is_object()) return out;
  for (const auto& k : v.keys()) {
    try {
      out[k] = v[k].as_double();
    } catch (...) {
      // 非数值参数（如字符串）忽略，按"未给出"处理
    }
  }
  return out;
}

/** term 中是否出现子表达式 node（用"替换后是否改变"判定，比遍历结构更稳）。 */
bool contains_node(const RCP<const Basic>& term, const RCP<const Basic>& node) {
  using namespace SymEngine;
  try {
    const auto probe = symbol("__mf_probe__");
    return neq(*term->subs({{node, probe}}), *term);
  } catch (...) {
    return false;
  }
}

/** 收集表达式中所有"根式节点"Pow(g, p/q)（q >= 2），按节点去重。 */
std::vector<RCP<const Basic>> distinct_radicals(const RCP<const Basic>& e) {
  using namespace SymEngine;
  std::vector<RCP<const Basic>> out;
  std::function<void(const RCP<const Basic>&)> walk = [&](const RCP<const Basic>& n) {
    if (is_a<Pow>(*n)) {
      const auto& p = down_cast<const Pow&>(*n);
      const auto exp = p.get_exp();
      if (is_a<Rational>(*exp)) {
        const auto& r = down_cast<const Rational&>(*exp);
        if (!eq(*r.get_den(), *one) && !eq(*r.get_num(), *zero)) {
          bool dup = false;
          for (const auto& x : out)
            if (eq(*x, *n)) dup = true;
          if (!dup) out.push_back(n);
        }
      }
    }
    for (const auto& a : n->get_args()) walk(a);
  };
  walk(e);
  return out;
}

/**
 * 多根式的逐次消元（隔离-平方法）。
 *
 * 原理就是学生解这类题的手法： sqrt(A) + sqrt(B) = C ->
 *   移项 sqrt(A) = C - sqrt(B) -> 平方 A = C^2 - 2C*sqrt(B) + B -> 再移项再平方 -> 多项式。
 * 每轮只针对选定的那一个根式操作，平方后根式个数必须下降；
 * 平方会引入伪根，但调用方对每个候选点都做 f'(x0)=0 残差复核，伪根过不了那一关。
 */
ReducedSolve radical_elimination(const RCP<const Basic>& d1,
                                 const std::string& var) {
  using namespace SymEngine;
  ReducedSolve out;
  const auto x = symbol(var);

  RCP<const Basic> cur;
  try {
    RCP<const Basic> num, den;
    as_numer_denom(d1, outArg(num), outArg(den));
    cur = expand(num);
  } catch (...) {
    return out;
  }
  if (distinct_radicals(cur).empty()) return out;

  std::size_t rounds = 0;
  while (rounds++ < 4) {
    const auto radicals = distinct_radicals(cur);
    if (radicals.empty()) break;

    bool progressed = false;
    for (const auto& r : radicals) {
      RCP<const Basic> L = zero, M = zero;
      for (const auto& t : cur->get_args()) {
        if (contains_node(t, r)) L = add(L, t);
        else M = add(M, t);
      }
      if (eq(*L, *zero)) continue;
      RCP<const Basic> next;
      try {
        next = expand(sub(expand(mul(L, L)), expand(mul(M, M))));
      } catch (...) {
        continue;
      }
      if (distinct_radicals(next).size() >= radicals.size()) continue;
      cur = next;
      progressed = true;
      break;
    }
    if (!progressed) return out;  // 消不动了，交给数值回退（不硬猜）
  }
  if (!distinct_radicals(cur).empty()) return out;

  try {
    const auto sol = mf::symutil::safe_solve(expand(cur), x, "消元后的驻点方程");
    if (!is_a<FiniteSet>(*sol)) return out;
    std::vector<std::string> roots;
    for (const auto& rt : down_cast<const FiniteSet&>(*sol).get_args())
      roots.push_back(SymEngine::str(*rt));
    if (roots.empty()) return out;
    out.ok = true;
    out.method = "elimination-radical";
    out.note =
        "含多个根式，采用隔离-平方逐次消元化为多项式方程后求解；"
        "平方运算会引入伪根，已由 f'(x0)=0 残差复核逐个筛除";
    out.roots = dedup_strings(std::move(roots));
  } catch (...) {
  }
  return out;
}

void register_all() {
  using mf::registry::register_function;

  // ── 自由符号列表（前置检查用：调用方据此判断能否走数值路径）─────────────
  register_function("free_symbols_of", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const auto e = SymEngine::parse(expr);
    const auto names = symbol_names(*e);
    Value obj = Value::make_object();
    obj.set("symbols", to_string_array(names));
    obj.set("symbolic", Value(!names.empty()));
    return obj;
  }, "{expr: string}"));

  // ── 精确解（含自由符号，如 x^2-a → [-sqrt(a), sqrt(a)]）────────────────
  // 输入允许课本的方程写法：x^2+2x+1=0 与 x^2+2x+1 等价（都按 =0 求解）。
  register_function("solve_sym", make_handler([](const Value& args) {
    const std::string expr = get_equation(args, "expr");
    const std::string var = get_string_opt(args, "var", "x");
    const auto e = SymEngine::parse(expr);
    // Decompose：x*sin(x)=0 这类乘积形式先把可解因式解出来（得 x=0），
    // 解不了的部分写进 note。旧行为是一律抛错，等于把"有精确解的那部分"也一起拒了。
    std::string note;
    std::string general;
    const auto roots = exact_roots(e, var, mf::symutil::SolvePolicy::Decompose, &note, &general);
    // 参数列表：除求解变量外的自由符号
    std::vector<std::string> params;
    for (const auto& n : symbol_names(*e))
      if (n != var) params.push_back(n);

    // 实根性：含参时给出可证明的结论（二次式用判别式符号），而不是默认虚根
    const auto rn = mf::symutil::equation_realness(e, var);

    Value obj = Value::make_object();
    obj.set("solutions", to_pretty_array(roots));
    obj.set("params", to_string_array(params));
    obj.set("exact", Value(true));
    obj.set("realness", Value(std::string(mf::symutil::root_realness_name(rn.kind))));
    obj.set("realnessReason", Value(rn.reason));
    if (!rn.delta.empty()) {
      obj.set("delta", Value(rn.delta));
      obj.set("deltaSign", Value(std::string(mf::symutil::sign_name(rn.delta_sign))));
    }
    // 通解（周期解等无穷族）与部分解说明：有就给，避免"看起来解完了其实没解完"
    if (!general.empty()) obj.set("generalSolution", Value(general));
    if (!note.empty()) obj.set("note", Value(note));
    return obj;
  }, "{expr: string, var?: string = \"x\"}"));

  // ── 符号判别式 Δ = b²-4ac（系数保留表达式，不转 double）────────────────
  // 同样接受方程写法：判别式问的就是"这个方程"的 Δ。
  register_function("discriminant_sym", make_handler([](const Value& args) {
    const std::string expr = get_equation(args, "expr");
    const std::string var = get_string_opt(args, "var", "x");
    const auto x = SymEngine::symbol(var);
    // 先展开再取系数：SymEngine::coeff 对**未展开**的 Pow/Mul 返回 0，
    // 于是 (x-1)^2 的二次项系数被读成 0，报出「二次项系数为 0，不是一元二次式」
    // ——这句话本身就是错的（(x-1)² 展开后二次项系数是 1，Δ = 0 是二重根）。
    // 同族的 (x+1)*(x+2) 在 plot_api 的 intersections 里先 expand 再判，
    // 判别式给的是正确的 1；只有这里少了 expand。
    const auto e = SymEngine::expand(SymEngine::parse(expr));

    const RCP<const Basic> a = SymEngine::coeff(*e, *x, *SymEngine::integer(2));
    const RCP<const Basic> b = SymEngine::coeff(*e, *x, *SymEngine::integer(1));
    // c = e - a·x² - b·x
    const RCP<const Basic> c = SymEngine::simplify(SymEngine::sub(
        SymEngine::sub(e, SymEngine::mul(a, SymEngine::pow(x, SymEngine::integer(2)))),
        SymEngine::mul(b, x)));

    // 必须**真的是**二次式：既要求 x² 系数非 0，也要求扣掉 a·x²+b·x 之后的
    // 残余项里不再含 var。旧实现只看 a≠0，于是三次式 x³-6x²+11x-6
    // （coeff(x²) = -6 ≠ 0）被当成二次式，残余的 x³-6 被折进常数项 c，
    // 「判别式」于是算成含未知量 x 的 -23+24x³，而同一次响应又标 symbolic=false、
    // nature="（数值判别式，请用 discriminant 获取根性质）"——自相矛盾。
    // 三次式没有 b²-4ac 这个对象，与一次式一样应当拒绝。
    if (SymEngine::eq(*a, *SymEngine::zero) || mf::symutil::contains_symbol(*c, var))
      throw std::invalid_argument(
          "不是一元二次式（关于 " + var + " 的次数不为 2）：判别式 Δ=b²-4ac 只对一元"
          "二次方程有定义。线性式请用 discriminant，高次方程请用 solve_sym / roots"
          "（三次及以上的根性质不是单个判别式能刻画的）");

    // Δ = b² - 4ac（符号形式）
    const RCP<const Basic> delta = SymEngine::expand(SymEngine::sub(
        SymEngine::pow(b, SymEngine::integer(2)),
        SymEngine::mul(SymEngine::integer(4), SymEngine::mul(a, c))));

    const bool symbolic = has_other_symbols(*delta, var);
    // 用可证明的符号判定取代"含参就放弃"：a²+4 这类恒正判别式能直接给出结论，
    // 只有真正会变号的（如 a²-1）才标为 unknown 交由上层分类讨论。
    const mf::symutil::Sign ds = mf::symutil::sign_definite(delta);

    std::string nature;
    if (!symbolic) {
      nature = "（数值判别式，请用 discriminant 获取根性质）";
    } else {
      switch (ds) {
        case mf::symutil::Sign::Positive:
          nature = "Δ 恒为正：对任意实参数都有两个不同实根";
          break;
        case mf::symutil::Sign::NonNegative:
          nature = "Δ 恒非负：对任意实参数都有实根（可能为重根）";
          break;
        case mf::symutil::Sign::Negative:
          nature = "Δ 恒为负：对任意实参数都无实根（两根为共轭复数）";
          break;
        case mf::symutil::Sign::NonPositive:
          nature = "Δ 恒非正：仅可能为二重实根";
          break;
        case mf::symutil::Sign::Zero:
          nature = "Δ 恒为 0：恒为二重实根";
          break;
        default:
          nature = "Δ 的符号依赖参数取值：需按参数分类讨论（Δ>0 两实根，Δ=0 重根，Δ<0 无实根）";
          break;
      }
    }

    Value obj = Value::make_object();
    obj.set("delta", Value(mf::symutil::pretty_math(delta)));
    obj.set("a", Value(mf::symutil::pretty_math(a)));
    obj.set("b", Value(mf::symutil::pretty_math(b)));
    obj.set("c", Value(mf::symutil::pretty_math(c)));
    obj.set("symbolic", Value(symbolic));
    obj.set("deltaSign", Value(std::string(mf::symutil::sign_name(ds))));
    obj.set("nature", Value(nature));
    // 恒非负/恒非正属于「可证明」的结论；unknown 只表示本算法证明不了，
    // 不表示不定号——字段名刻意用 signDefinite + unknown 加以区分。
    obj.set("signDefinite", Value(ds != mf::symutil::Sign::Unknown));
    Value params = Value::make_array();
    for (const auto& n : symbol_names(*delta))
      if (n != var) params.push_back(Value(n));
    obj.set("params", params);
    return obj;
  }, "{expr: string, var?: string = \"x\"}"));

  // ── 符号因式分解（如 x^2-a^2 → (x + a)*(x - a)）────────────────────────
  register_function("factor_sym", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const std::string var = get_string_opt(args, "var", "x");
    const auto x = SymEngine::symbol(var);
    const auto e = SymEngine::parse(expr);

    const auto roots = exact_roots(e, var);
    if (roots.empty())
      throw std::invalid_argument("无法求出精确根，因式分解失败（请确认表达式为多项式）");

    // 根已由 exact_roots 归约（√(a²) → a），此处按教科书记号拼接因式
    std::vector<std::string> pretty_roots;
    for (const auto& r : roots) {
      try {
        pretty_roots.push_back(mf::symutil::pretty_math_str(r));
      } catch (...) {
        pretty_roots.push_back(r);
      }
    }

    std::string factored;
    for (std::size_t i = 0; i < pretty_roots.size(); ++i) {
      if (i) factored += "*";
      factored += factor_of_root(var, pretty_roots[i]);
    }
    Value obj = Value::make_object();
    obj.set("factored", Value(factored));
    obj.set("roots", to_pretty_array(roots));
    Value params = Value::make_array();
    for (const auto& n : symbol_names(*e))
      if (n != var) params.push_back(Value(n));
    obj.set("params", params);
    return obj;
  }, "{expr: string, var?: string = \"x\"}"));

  // ── 表达式等价判定（比较两式是否恒等）──────────────────────────────────
  //
  // 判定交给 mf::symutil::prove_equivalent（三态：equal / not-equal / undetermined），
  // 它严格强于本处原先的 `expand(差)==0`：还会依次试 simplify、simplify(expand)、
  // expand(simplify)、三角恒等 sin²u→1-cos²u、通分后分子展开、最后的数值抽样
  // （抽样只用来证「不等」，绝不据此判「相等」）。
  //
  // 为什么必须换：expand 不做三角恒等，于是把「本算法证不出」直接当成了「不等」。
  // 实测 a="sin(x)^2+cos(x)^2"、b="1" 时差为 -1+sin(x)**2+cos(x)**2 ≠ 0，
  // equal 被报成 false；而同文件的 simplify_sym 对同一输入返回 1，
  // 即引擎自己知道两者相等——同一个响应集里自相矛盾。
  register_function("compare_expr", make_handler([](const Value& args) {
    // a / b 是表达式参数，但键名不能进 api_helpers 的表达式键表
    // （那里的 a/b 是椭圆半轴、二次项系数等**数值**参数），于是 get_string
    // 不做归一化，同一串在 compare_expr 与 expr_eval/diff/solve_sym 里结果不同。
    //
    // 修法：**先原样解析，只有拿到可疑结果才改用归一化串**。
    //   · 引擎自己打印的串（simplify_sym / factor_sym / solve_sym 的结果）会被回喂，
    //     必须原样可解析、语义不变，所以不能一上来就归一化；
    //   · 但"原样解析成功"并不代表解析对了：SymEngine 的解析器会把 '√2' 整个
    //     当成**符号名**√2（实测 free_symbols = ['√2']），于是 √2 被静默读成变量、
    //     compare_expr 给出"不等"这个错答。凡解析出的自由符号名不像合法标识符，
    //     就改用规范化串重解析（√→sqrt、π→pi、\frac→/…）。
    //   · 隐式乘法（2x、(x+1)(x-1)）在 SymEngine 里直接是语法错误，走 catch 分支。
    auto parse_expr_arg = [](const std::string& s) -> RCP<const Basic> {
      try {
        const RCP<const Basic> raw = SymEngine::parse(s);
        if (!has_implausible_symbols(*raw)) return raw;
      } catch (...) {
        // 解析失败 → 交给下面的归一化重试
      }
      return SymEngine::parse(mf::api::normalize_expr_arg(s));
    };
    const std::string lhs = mf::api::get_keyword(args, "a");
    const std::string rhs = mf::api::get_keyword(args, "b");
    const auto ea = parse_expr_arg(lhs);
    const auto eb = parse_expr_arg(rhs);
    const auto rep = mf::symutil::prove_equivalent(ea, eb);
    // difference 仍保留「差的展开」：界面要显示它，人工也要拿它复核
    RCP<const Basic> diff;
    try {
      diff = SymEngine::expand(SymEngine::sub(ea, eb));
    } catch (...) {
      diff = SymEngine::sub(ea, eb);
    }
    Value obj = Value::make_object();
    obj.set("equal", Value(rep.verdict == mf::symutil::Equivalence::Equal));
    obj.set("difference", Value(mf::symutil::pretty_math(diff)));
    // 三态结论与依据一并外露：调用方能区分「确实不等」与「本算法证不出」
    // （equal 字段只有两态时，undetermined 会被读成「不等」）
    obj.set("verdict", Value(std::string(mf::symutil::equivalence_name(rep.verdict))));
    obj.set("reason", Value(rep.how));
    return obj;
  }, "{a: string, b: string}（两项都必须是字符串，如 {\"a\":\"(x+1)^2\",\"b\":\"x^2+2*x+1\"}）"));

  // ── 含参极值与参数分类讨论（符号驻点 + 参数分支代表值取样）────────────
  //
  // 说明：这是 engine 侧对"assumption-aware 推理"的有界实现——
  //   · 驻点用精确符号形式（±√a），不做数值化
  //   · 参数取值会影响结论时，按参数正/零/负组合**显式分情况**给出结论，
  //     每个分支标注假设条件（如 "a>0"），而非静默给出单一结果
  //   · 分支判定用代表值（p>0→1, p=0→0, p<0→-1）：覆盖常见情形，
  //     属于"分支预览"而非完备证明；完备分类讨论由上层按需展开
  //   · **每个分支都会检查驻点是否存在、是否落在定义域内**（ln 的真数 >0、
  //     偶次根号 ≥0、分母 ≠0）。这两件事都会改变结论，漏掉就是静默错答。
  //
  // ⚠ 字段语义（曾有歧义，务必按名读取）：
  //   exists   该分支下驻点是否存在且落在定义域内
  //   kind     极值类型：maximum/minimum/degenerate；
  //            exists=false 时为 no-critical-point / outside-domain
  //   f_value  该分支下**函数值** f(x₀)      ← 这才是"极值"
  //   f2_value 该分支下**二阶导值** f''(x₀)  ← 仅用于判定极大/极小
  //   旧版把二阶导值命名为 value，与 local_extrema 的 (x₀, f(x₀)) 语义冲突，
  //   照字面读会把极值读成 f''——已改名为 f2_value 并补上 f_value。
  register_function("extrema_sym", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const std::string var = get_string_opt(args, "var", "x");
    const auto x = SymEngine::symbol(var);
    // 数值扫描区间可配置：默认 [-20,20] 只适合常见初等函数，
    // 周期函数或大尺度函数的驻点会落在区间外，必须允许调用方指定。
    const double scan_lo = get_double_opt(args, "xmin", -20.0);
    const double scan_hi = get_double_opt(args, "xmax", 20.0);
    if (scan_hi <= scan_lo)
      throw std::invalid_argument("xmax 必须大于 xmin（当前 xmin=" +
                                  std::to_string(scan_lo) + ", xmax=" +
                                  std::to_string(scan_hi) + "）");
    // 可选：直接给出参数取值（如绘图侧滑块的当前值）。给了就按具体数值处理，
    // 于是"含参 + 非有理导数"（如 a·x+eˣ）也能走数值回退求得驻点，
    // 而不是只能回一句"请代入具体参数"。
    const std::map<std::string, double> given = read_vars(args);
    const bool has_given = !given.empty();

    RCP<const Basic> base = SymEngine::parse(expr);
    if (has_given) {
      SymEngine::map_basic_basic m;
      for (const auto& kv : given)
        m[SymEngine::symbol(kv.first)] = SymEngine::real_double(kv.second);
      base = base->subs(m);
    }
    const auto e = base;  // 后续一律基于"已代入选定参数值"的表达式
    const auto d1 = SymEngine::diff(e, x);
    const auto d2 = SymEngine::diff(d1, x);

    // 定义域约束取自原函数（而非导数）：ln(x) 无论参数取何值都要求 x>0
    const auto dom = mf::symutil::domain_constraints(e);
    const bool has_domain = !dom.empty();

    // 求解驻点方程 f'(x)=0。三级策略，每级都如实标注用的哪一种：
    //   ① 符号直接求解（多项式/有理式/log/atan —— 其导数是有理式）
    //   ② 换元降次（t=√g、t=tan g —— 学生解这类题的标准手法，仍给出精确形式）
    //   ③ 数值扫描（仅当无自由参数；给出正确但非精确的驻点，必须标注）
    // 任一级都不"假装成功"：全都失败时如实报错。
    std::vector<std::string> roots;
    std::string solve_method = "symbolic";
    std::string solve_note;
    try {
      roots = exact_roots(d1, var);
    } catch (const std::exception& solve_err) {
      // 多根式优先走消元（换元只覆盖单个根式）；单根式/三角仍走换元
      ReducedSolve red = radical_elimination(d1, var);
      if (!red.ok) red = reduced_critical_points(d1, var);
      if (red.ok) {
        roots = red.roots;
        solve_method = red.method;
        solve_note = red.note;
      } else {
        // 含自由参数时无法数值回退：数值根是具体数字，回代不成参数表达式，
        // 会给出一组与参数无关的假结论。此时如实报出求解器限制。
        bool has_params = false;
        for (const auto& n : symbol_names(*e))
          if (n != var) has_params = true;
        if (has_params) throw;

        const auto scan = mf::symutil::numeric_roots_in_range(
            d1, var, scan_lo, scan_hi, 8000, {});
        if (scan.roots.empty() && !scan.usable()) {
          // 压根无法数值求值（gamma/polygamma 等没有双精度实现）：
          // 这时说什么都是猜，如实报出求解器的限制。
          // 若该函数有定义域约束，一并带上——否则用户只知道"算不了"，
          // 连"哪些点本来就不该考虑"也看不到。
          std::string dom_hint;
          for (const auto& c : dom) {
            if (!dom_hint.empty()) dom_hint += "；";
            dom_hint += mf::symutil::pretty_math(c.expr) + " " +
                        mf::symutil::domain_op_text(c.op) + "（" + c.why + "）";
          }
          throw std::invalid_argument(
              std::string(solve_err.what()) +
              "；换元降次（t=√g、t=tan g）对该形式不适用；f'(x) 无法数值求值（" +
              std::to_string(scan.total - scan.evaluated) + "/" +
              std::to_string(scan.total) +
              " 个采样点算不出实数，该函数可能没有双精度求值实现）" +
              (dom_hint.empty() ? "" : "；该函数的定义域约束为 " + dom_hint));
        }
        char buf[64];
        for (const auto& h : scan.roots) {
          // 数值求值在零点附近会因消去误差直接给出 0（如 cosh(x)-1 在 |x|<1e-8
          // 处恒为 0），把这类"精度意义下的 0"统一写成 0，避免显示 1.49e-08
          const double xv = (std::fabs(h.x) < 1e-7) ? 0.0 : h.x;
          std::snprintf(buf, sizeof(buf), "%.12g", xv);
          roots.push_back(buf);
        }
        solve_method = "numeric";
        const std::string coverage =
            "（区间内 " + std::to_string(scan.evaluated) + "/" +
            std::to_string(scan.total) +
            " 个采样点可求值，其余落在定义域外或无法求值）";
        // 区间内 |f'| 的最小值：无根时用它区分"确实没有驻点"与"驻点在区间外"，
        // 而不是只丢一句"区间外看不到"让调用方无从判断。
        char min_buf[64], minx_buf[64];
        std::snprintf(min_buf, sizeof(min_buf), "%.6g", scan.min_mag);
        std::snprintf(minx_buf, sizeof(minx_buf), "%.6g", scan.min_mag_x);
        solve_note =
            scan.roots.empty()
                ? ("符号求解不可用，改用在 [" + std::to_string((int)scan_lo) + ", " +
                   std::to_string((int)scan_hi) +
                   "] 上数值扫描 f'(x)：**未发现驻点**" + coverage +
                   "。区间内 |f'| 的最小值为 " + min_buf + "（在 x = " + minx_buf +
                   " 处）：该值若明显不为 0，说明驻点很可能落在区间外，"
                   "可放大 xmin/xmax 后重试。数值扫描本身不是完备判定——"
                   "既不变号又没被网格踩中的重根也会被漏掉")
                : ("符号求解不可用，改用在 [" + std::to_string((int)scan_lo) + ", " +
                   std::to_string((int)scan_hi) +
                   "] 上数值扫描 f'(x) 的零点（变号区间二分 + 相切零点三分细化）；"
                   "结果为数值近似（非精确解）" + coverage +
                   std::string(scan.truncated ? "；命中数超过上限已截断" : ""));
      }
    }

    // 定义域约束（下方求解策略也需要它，故先算）

    std::vector<std::string> params;
    for (const auto& n : symbol_names(*e))
      if (n != var) params.push_back(n);

    Value pts = Value::make_array();
    for (const auto& r : roots) {
      const auto rv = SymEngine::parse(r);
      const auto f2 = SymEngine::simplify(d2->subs({{x, rv}}));
      const auto fv = SymEngine::simplify(e->subs({{x, rv}}));

      // 是否需要按参数分支讨论？判据**不能只看 f2**：
      //   x²−a·ln x 的 f''(x₀)=4 不含 a，但驻点 ±√(a/2) 依赖 a
      //   （a<0 非实、负根在定义域外）——只看 f2 会完全漏掉分支讨论，
      //   并给出 "branches: [] 却宣告 minimum" 这种既不报错也不解释的结果。
      std::vector<std::string> branch_params;
      const auto add_params = [&](const SymEngine::Basic& b) {
        for (const auto& n : symbol_names(b))
          if (n != var &&
              std::find(branch_params.begin(), branch_params.end(), n) ==
                  branch_params.end())
            branch_params.push_back(n);
      };
      add_params(*f2);
      if (has_domain) {
        add_params(*rv);
        for (const auto& c : dom) add_params(*c.expr);
      }
      std::sort(branch_params.begin(), branch_params.end());

      Value pt = Value::make_object();
      pt.set("x", Value(display(rv)));
      pt.set("f", Value(display(fv)));   // 函数值（符号形式）
      pt.set("f2", Value(display(f2)));  // 二阶导（符号形式）

      if (branch_params.empty()) {
        // 无参数依赖：直接精确判定，但先确认驻点存在且在定义域内
        pt.set("symbolic", Value(false));
        const auto st = eval_critical_point(rv, var, {}, dom, d1);
        if (!st.exists) {
          pt.set("exists", Value(false));
          pt.set("kind", Value(st.kind));
          pt.set("note", Value(st.note));
          pt.set("f2_value", Value(std::string("—")));
          pt.set("f_value", Value(std::string("—")));
        } else {
          pt.set("exists", Value(true));
          pt.set("kind", Value(classify_numeric(f2)));
          try {
            pt.set("f_value", Value(display(fv)));
          } catch (...) {
          }
          if (!st.note.empty()) pt.set("note", Value(st.note));
        }
      } else {
        pt.set("kind", Value(std::string("需按参数分类讨论")));
        pt.set("symbolic", Value(true));
        const auto branches = param_branches(branch_params);
        if (!branches.empty()) {
          Value arr = Value::make_array();
          for (const auto& b : branches) {
            SymEngine::map_basic_basic psub;  // 只替换参数，保持符号形式
            for (std::size_t i = 0; i < branch_params.size(); ++i)
              psub[SymEngine::symbol(branch_params[i])] =
                  SymEngine::integer(b.values[i]);

            Value br = Value::make_object();
            br.set("assume", Value(b.assume));

            // ① 驻点存在性 + 定义域 + f'=0 残差复核。这一步的结论优先于 f'' 符号。
            //    在分支内取多个参数样本：单个代表值可能恰好是特例
            //    （a·x+atan(x) 在 a=-1 时 x=0 恰好成立，a=-2 时并不成立）。
            //    注意用值而不是指针保存结论——指向循环体内局部量的指针会在
            //    下一轮迭代后悬垂（曾导致 kind 读成空串）。
            const auto samples = branch_sample_sets(b.values);
            CritPoint worst;
            bool has_worst = false;
            int exist_hits = 0, miss_hits = 0;
            std::string hit_label, miss_label;
            for (const auto& values : samples) {
              SymEngine::map_basic_basic ssub;
              std::string label;
              for (std::size_t i = 0; i < branch_params.size(); ++i) {
                ssub[SymEngine::symbol(branch_params[i])] =
                    SymEngine::integer(values[i]);
                if (!label.empty()) label += ",";
                label += branch_params[i] + "=" + std::to_string(values[i]);
              }
              const auto v = eval_critical_point(rv, var, ssub, dom, d1);
              if (v.exists) {
                ++exist_hits;
                if (hit_label.empty()) hit_label = label;
              } else {
                ++miss_hits;
                if (!has_worst ||
                    crit_kind_rank(v.kind) > crit_kind_rank(worst.kind)) {
                  worst = v;
                  has_worst = true;
                  miss_label = label;
                }
              }
            }

            if (samples.size() > 1)
              br.set("samples", Value(static_cast<long long>(samples.size())));

            if (exist_hits > 0 && miss_hits > 0) {
              // 分支内结论不唯一：如 a·x+atan(x) 的 a<0 里，-1<a<0 有驻点、
              // a≤-1 没有。既不报"有"也不报"没有"，而是明确标注未定，
              // 并把两侧的取值一起给出（沿用 intersections 的 null = 未定约定）。
              br.set("exists", Value());
              br.set("uniform", Value(false));
              br.set("kind", Value(std::string("conditional-within-branch")));
              br.set("f2_value", Value(std::string("—")));
              br.set("f_value", Value(std::string("—")));
              br.set("note", Value(std::string("该分支内结论不唯一：") + hit_label +
                                   " 时驻点存在，而 " + miss_label + " 时不存在（" +
                                   worst.note + "）——需进一步细分参数范围"));
              arr.push_back(br);
              continue;
            }

            if (miss_hits > 0) {
              br.set("exists", Value(false));
              br.set("kind", Value(worst.kind));
              br.set("note", Value(worst.note));
              br.set("f2_value", Value(std::string("—")));
              br.set("f_value", Value(std::string("—")));
              arr.push_back(br);
              continue;
            }
            br.set("exists", Value(true));

            // ② 存在且落在定义域内：再由 f'' 符号判极大/极小
            try {
              // 二阶导值：只作极大/极小的符号判据，命名为 f2_value 以免被误读成极值
              const auto v2 = SymEngine::simplify(f2->subs(psub));
              if (mf::symutil::has_nonfinite(*v2)) {
                br.set("f2_value", Value(std::string("无定义")));
                br.set("kind", Value(std::string("no-real-value")));
              } else {
                br.set("f2_value", Value(display(v2)));
                br.set("kind", Value(classify_numeric(v2)));
              }
            } catch (...) {
              // 该分支下驻点非实数/无定义（如 a<0 时的 √a）
              br.set("f2_value", Value(std::string("非实数或无定义")));
              br.set("kind", Value(std::string("no-real-value")));
            }
            try {
              // 函数值：这才是该分支下的极值本身
              const auto vf = SymEngine::simplify(fv->subs(psub));
              if (mf::symutil::has_nonfinite(*vf))
                br.set("f_value", Value(std::string("无定义")));
              else
                br.set("f_value", Value(display(vf)));
            } catch (...) {
              br.set("f_value", Value(std::string("非实数或无定义")));
            }
            arr.push_back(br);
          }
          pt.set("branches", arr);
        } else {
          pt.set("note", Value(std::string("参数多于 3 个，未枚举分支")));
        }
      }
      pts.push_back(pt);
    }

    Value obj = Value::make_object();
    obj.set("expr", Value(expr));
    obj.set("var", Value(var));
    obj.set("d1", Value(display(d1)));
    obj.set("d2", Value(display(d2)));
    obj.set("critical_points", to_pretty_array(roots));
    obj.set("params", to_string_array(params));
    // 求解手段如实标注：symbolic / substitution-sqrt / substitution-tan / numeric
    obj.set("solveMethod", Value(solve_method));
    if (!solve_note.empty()) obj.set("solveNote", Value(solve_note));
    // 定义域：说明"驻点还需落在定义域内才是极值点"，供调用方理解 exists=false
    Value doms = Value::make_array();
    for (const auto& c : dom) {
      doms.push_back(Value(mf::symutil::pretty_math(c.expr) + " " +
                           mf::symutil::domain_op_text(c.op) + "（" + c.why + "）"));
    }
    obj.set("domain", doms);
    // 字段语义声明：调用方（含 C# 快路径）据此读取，避免把 f2_value 当极值
    obj.set("valueFieldNote", Value(std::string(
        "exists = 该分支下驻点是否存在且落在定义域内（false 时 kind 为 "
        "no-critical-point[驻点无定义/非实] 或 outside-domain[不在定义域内]，此时 f_value/f2_value 无意义）；"
        "kind = maximum/minimum/degenerate；"
        "f_value = 函数值 f(x₀)（极值本身）；f2_value = 二阶导值 f''(x₀)（仅用于判极大/极小）；"
        "点级 f/f2 为对应的符号形式")));
    obj.set("points", pts);
    return obj;
  }, "{expr: string, var?: string = \"x\"}"));

  // ── 精确化简 ───────────────────────────────────────────────────────────
  //
  // 单一 SymEngine::simplify 并不总是"最简"：例如
  //   (x-a)^2 - (x+a)^2  的 simplify 原样返回，而 expand 给出 -4*a*x。
  // 因此这里生成多个候选形式，按**节点数**挑选最简，并把候选一并返回以便核对。
  register_function("simplify_sym", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const auto e = SymEngine::parse(expr);

    struct Candidate {
      const char* form;
      RCP<const Basic> value;
    };
    std::vector<Candidate> cands;
    const auto add = [&](const char* form, RCP<const Basic> v) {
      if (v.is_null()) return;
      cands.push_back({form, v});
    };

    try { add("原始形式", e); } catch (...) {}
    try { add("expand", SymEngine::expand(e)); } catch (...) {}
    try { add("simplify", SymEngine::simplify(e)); } catch (...) {}
    try { add("simplify(expand)", SymEngine::simplify(SymEngine::expand(e))); } catch (...) {}
    try { add("expand(simplify)", SymEngine::expand(SymEngine::simplify(e))); } catch (...) {}
    // 有理式约分：分母分子同乘同一因式时，上面的候选都化不掉，
    // 用多项式 GCD 约分（SymEngine 的 gcd 不公开在 simplify 里，需显式调用）
    try {
      RCP<const Basic> num, den;
      SymEngine::as_numer_denom(e, SymEngine::outArg(num), SymEngine::outArg(den));
      if (neq(*den, *SymEngine::one)) {
        const auto c = SymEngine::expand(SymEngine::div(num, den));
        add("expand(商的展开)", c);
      }
    } catch (...) {}

    // 三角恒等：SymEngine::simplify 不做三角恒等，故显式补一条
    // sin²u → 1-cos²u（及反向），把 sin²u+cos²u 这类化到 1。
    // 对同一自变量只替换其中一个方向，否则两项互换会原地打转；
    // 只作为候选加入，是否采用仍由「节点数最少」规则决定。
    {
      std::vector<RCP<const Basic>> sins, coss;
      collect_trig_squares(e, sins, coss);
      SymEngine::map_basic_basic by_sin, by_cos;
      for (const auto& s : sins) {
        const auto u = SymEngine::down_cast<const SymEngine::Pow&>(*s).get_base()->get_args()[0];
        by_sin[s] = SymEngine::sub(SymEngine::one,
                                   SymEngine::pow(SymEngine::cos(u), SymEngine::integer(2)));
      }
      for (const auto& c : coss) {
        const auto u = SymEngine::down_cast<const SymEngine::Pow&>(*c).get_base()->get_args()[0];
        by_cos[c] = SymEngine::sub(SymEngine::one,
                                   SymEngine::pow(SymEngine::sin(u), SymEngine::integer(2)));
      }
      if (!by_sin.empty()) {
        try {
          add("三角恒等 sin²→1-cos²",
              SymEngine::simplify(SymEngine::expand(e->subs(by_sin))));
        } catch (...) {}
      }
      if (!by_cos.empty()) {
        try {
          add("三角恒等 cos²→1-sin²",
              SymEngine::simplify(SymEngine::expand(e->subs(by_cos))));
        } catch (...) {}
      }
    }

    if (cands.empty())
      throw std::invalid_argument("无法处理该表达式（解析或化简失败）");

    // 选节点数最少者；并列时取字符串更短者，保证结果稳定可复现
    std::size_t best = 0;
    for (std::size_t i = 1; i < cands.size(); ++i) {
      const std::size_t a = mf::symutil::node_count(*cands[i].value);
      const std::size_t b = mf::symutil::node_count(*cands[best].value);
      if (a < b || (a == b && SymEngine::str(*cands[i].value).size() <
                                  SymEngine::str(*cands[best].value).size()))
        best = i;
    }

    Value list = Value::make_array();
    for (const auto& c : cands) {
      Value item = Value::make_object();
      item.set("form", Value(std::string(c.form)));
      item.set("expr", Value(mf::symutil::pretty_math(c.value)));
      item.set("ops", Value(static_cast<long long>(mf::symutil::node_count(*c.value))));
      list.push_back(item);
    }

    Value obj = Value::make_object();
    obj.set("simplified", Value(mf::symutil::pretty_math(cands[best].value)));
    obj.set("chosen", Value(std::string(cands[best].form)));
    obj.set("expanded", Value(mf::symutil::pretty_math(SymEngine::expand(e))));
    // 候选清单：把"为什么选它"摆出来，避免只给一个结果却无法核对
    obj.set("candidates", list);
    obj.set("symbols", to_string_array(symbol_names(*e)));
    return obj;
  }, "{expr: string}"));
}

struct Registrar { Registrar() { register_all(); } };
const Registrar g_symbolic_registrar;

}  // namespace
