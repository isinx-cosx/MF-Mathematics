// symbolic_util.h — 符号判定工具（仅头文件）
//
// 用途：在符号 API 里区分"纯数值表达式"与"含自由参数的表达式"，
// 从而在无法精确处理时**显式报错**，而不是数值化失败后静默降级。
// 另提供：
//   · safe_solve        求解前拦截超越函数，避免 SymEngine 求解器栈溢出崩溃
//   · node_count        表达式复杂度，用于在多个候选形式中挑"最简"
//   · sign_definite     Δ 之类表达式的**可证明**符号判定（非抽样）
//   · perfect_sqrt      √(a²) → a 的完全平方识别
//   · reduce_root_radicals  根集整体归约（多项式恒等验证后才采用）
//   · equation_realness 含参方程实根性判定（绘图交点的实虚性依据）
#pragma once

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/mul.h>
#include <symengine/number.h>
#include <symengine/parser.h>
#include <symengine/pow.h>
#include <symengine/printers.h>
#include <symengine/rational.h>
#include <symengine/sets.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/symengine_rcp.h>
#include <symengine/symbol.h>
#include <symengine/visitor.h>

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <functional>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "special_numeric.h"

namespace mf::symutil {

using SymEngine::Basic;
using SymEngine::RCP;

/** 提取表达式中的自由符号名（按字典序去重）。 */
inline std::vector<std::string> symbol_names(const SymEngine::Basic& e) {
  std::vector<std::string> out;
  const SymEngine::set_basic syms = SymEngine::free_symbols(e);
  for (const auto& s : syms) {
    if (SymEngine::is_a<SymEngine::Symbol>(*s))
      out.push_back(SymEngine::down_cast<const SymEngine::Symbol&>(*s).get_name());
  }
  std::sort(out.begin(), out.end());
  out.erase(std::unique(out.begin(), out.end()), out.end());
  return out;
}

/** 是否存在除 var 之外的自由符号（即表达式"含参数"）。 */
inline bool has_other_symbols(const SymEngine::Basic& e, const std::string& var) {
  for (const auto& n : symbol_names(e))
    if (n != var) return true;
  return false;
}

/** 表达式是否含任何自由符号。 */
inline bool is_symbolic(const SymEngine::Basic& e) { return !symbol_names(e).empty(); }

/**
 * 表达式 e 里是否出现自由符号 var。
 *
 * 用于「残余项是否已经把 var 消干净」这类判据：判别式 / 实根性都要求先确认
 * 目标式**确实是**关于 var 的二次式——只看 coeff(x²)≠0 不够，x³-6x²+11x-6
 * 的 coeff(x²) 是 -6≠0，残余的 x³-6 会被折进常数项，于是「判别式」里出现未知量。
 */
inline bool contains_symbol(const SymEngine::Basic& e, const std::string& var) {
  for (const auto& n : symbol_names(e))
    if (n == var) return true;
  return false;
}

/** 把自由符号名拼成可读列表（用于错误信息）。 */
inline std::string join_names(const std::vector<std::string>& names) {
  std::string out;
  for (std::size_t i = 0; i < names.size(); ++i) {
    if (i) out += ", ";
    out += names[i];
  }
  return out;
}

/** 把精确根字符串格式化为一次因式：(x - r) / (x + r) / (x) 。 */
inline std::string factor_of_root(const std::string& var, const std::string& root) {
  if (root == "0") return "(" + var + ")";
  if (!root.empty() && root[0] == '-') return "(" + var + " + " + root.substr(1) + ")";
  return "(" + var + " - " + root + ")";
}

// ── 安全求解 ────────────────────────────────────────────────────────────────
//
// 背景：SymEngine 的通用求解器 solve() 对"未知量出现在超越函数内部"的方程会
// **栈溢出崩溃**（实测 20*cos(20*x)=0 即 sin(20*x) 的驻点方程会崩），
// 这是进程级故障，catch 不住，所以必须先于 solve() 判断。
//
// 但旧实现是"对打印出来的整串做子串匹配"，判据过宽，把可精确求解的也算进来了：
//   sin(x)=0      —— 三角方程，教科书标准题
//   x^2 - sin(1)  —— sin(1) 只是常数，未知量是多项式
//   sqrt(x) = 2   —— 代数运算（sqrt/cbrt/pow 不是超越），x=4
//   abs(x) = 3    —— 分段运算
//   x*sin(x)=0    —— 乘积形式，x=0 是精确解
// 现在改为**结构化判据**：走一遍表达式树，只有当某节点的超越函数**它的自变量里含
// 未知量**时才算危险；并分三类区别对待（超越 / 分段 / 未知量在指数上）。

/** 超越函数头（按节点字符串前缀识别：不依赖 SymEngine 的类层次，跨版本稳） */
inline const std::vector<std::string>& transcendental_heads() {
  static const std::vector<std::string> kHeads = {
      "sin(", "cos(", "tan(", "csc(", "sec(", "cot(",
      "asin(", "acos(", "atan(", "acsc(", "asec(", "acot(",
      "arcsin(", "arccos(", "arctan(",
      "sinh(", "cosh(", "tanh(", "asinh(", "acosh(", "atanh(",
      "exp(", "log(", "gamma(", "erf(", "zeta(", "lambertw",
  };
  return kHeads;
}

/** 三角函数头（这些可以交给 SymEngine 的 solve_trig，而不是拒绝） */
inline const std::vector<std::string>& trig_heads() {
  static const std::vector<std::string> kHeads = {
      "sin", "cos", "tan", "csc", "sec", "cot",
      "asin", "acos", "atan", "acsc", "asec", "acot",
      "arcsin", "arccos", "arctan",
  };
  return kHeads;
}

/** 分段/多值函数头。它们**不是**超越函数，但通用求解器对它们给不出正确解
 *  （会静默返回空集或错误解），所以必须单独识别、单独说明 —— 不能当"安全"放过，
 *  那样等于把一个错答案返给用户。 */
inline const std::vector<std::string>& piecewise_heads() {
  static const std::vector<std::string> kHeads = {
      "Abs(", "abs(", "sign(", "signum(", "floor(", "ceil(", "Max(", "Min(",
  };
  return kHeads;
}

/** 根式头。实测：通用求解器对 sqrt(x)-2 直接返回**空集**（答案 x=4 明明存在），
 *  属静默错答，比报错更糟；根式方程本就该"平方去根号 + 验根"，所以单独拦住并说清楚。 */
inline const std::vector<std::string>& radical_heads() {
  static const std::vector<std::string> kHeads = {"sqrt(", "cbrt("};
  return kHeads;
}

/** 节点是否以某个函数头开头；命中则返回函数名（去掉左括号） */
inline std::string head_of(const SymEngine::Basic& b, const std::vector<std::string>& heads) {
  const std::string s = SymEngine::str(b);
  for (const auto& h : heads) {
    if (s.rfind(h, 0) == 0) return h.substr(0, h.size() - 1);
  }
  return "";
}

/** 该节点的参数里是否含未知量（即"自变量含未知量"） */
inline bool args_contain_symbol(const SymEngine::Basic& b, const std::string& var) {
  for (const auto& a : b.get_args()) {
    if (contains_symbol(*a, var)) return true;
  }
  return false;
}

/**
 * 找"未知量出现在其内部的"超越/分段函数头。
 * @param is_piecewise 输出：命中的是分段函数（而非超越函数）
 * @return 函数名；空串表示表达式对求解器是安全的
 */
inline std::string unsafe_head(const SymEngine::Basic& b, const std::string& var, bool& is_piecewise) {
  std::string h = head_of(b, transcendental_heads());
  bool pw = false;
  if (h.empty()) {
    h = head_of(b, piecewise_heads());
    pw = !h.empty();
  }
  if (!h.empty() && args_contain_symbol(b, var)) {
    is_piecewise = pw;
    return h;
  }
  for (const auto& a : b.get_args()) {
    const std::string r = unsafe_head(*a, var, is_piecewise);
    if (!r.empty()) return r;
  }
  return "";
}

/** 未知量出现在指数上（x^x、2^x 之类）也属超越方程，通用求解器同样会崩 */
inline bool symbolic_exponent(const SymEngine::Basic& b, const std::string& var) {
  if (SymEngine::is_a<SymEngine::Pow>(b)) {
    const auto& args = b.get_args();
    if (args.size() == 2 && contains_symbol(*args[1], var)) return true;
  }
  for (const auto& a : b.get_args()) {
    if (symbolic_exponent(*a, var)) return true;
  }
  return false;
}

inline bool is_trig_head(const std::string& h) {
  for (const auto& t : trig_heads()) {
    if (h == t) return true;
  }
  return false;
}

/** 是否存在"含未知量的根式"：sqrt(x)、cbrt(x)、x^(1/2) 之类 */
inline bool has_unknown_radical(const SymEngine::Basic& b, const std::string& var) {
  if (!head_of(b, radical_heads()).empty() && args_contain_symbol(b, var)) return true;
  if (SymEngine::is_a<SymEngine::Pow>(b)) {
    const auto& a = b.get_args();
    // 非整数指数且底数含未知量 → 根式/多值
    if (a.size() == 2 && SymEngine::is_a<SymEngine::Rational>(*a[1])
        && contains_symbol(*a[0], var)) {
      return true;
    }
  }
  for (const auto& c : b.get_args()) {
    if (has_unknown_radical(*c, var)) return true;
  }
  return false;
}

/**
 * 求解器返回的集合是否"真的是一组解"。
 * 必须排掉两种"看着像成功其实没解出来"的返回：
 *   · ConditionSet：实测 solve_trig 对 x*sin(x) 返回 {x | 0 == x*sin(x)} ——
 *     这只是把原方程复述了一遍，当通解报给用户等于什么都没说；
 *   · 空集：分不清"确实无解"和"没解出来"（sqrt(x)-2 就返回空集，而 x=4 是解）。
 * 因此：非空 FiniteSet 算解；ImageSet（如 {2*n*pi | n∈Z}）是真正的参数族，算解；
 * Union 逐个成员判断（sin(x)=0 的通解就是两个 ImageSet 的并集）。
 * strict 模式下不接受无穷族与并集 —— 驻点/交点这类场景拿到"部分解"会静默漏解，
 * 比报错更糟。
 */
inline bool is_usable_solution(const SymEngine::RCP<const SymEngine::Set>& s, bool allow_infinite) {
  if (SymEngine::is_a<SymEngine::FiniteSet>(*s)) return !s->get_args().empty();
  if (!allow_infinite) return false;
  if (SymEngine::is_a<SymEngine::ImageSet>(*s)) return true;
  if (SymEngine::is_a<SymEngine::Union>(*s)) {
    bool any = false;
    for (const auto& part : s->get_args()) {
      const auto ps = SymEngine::rcp_dynamic_cast<const SymEngine::Set>(part);
      if (ps.is_null()) return false;          // RCP 没有 operator!，用 is_null()
      if (!is_usable_solution(ps, true)) return false;
      any = true;
    }
    return any;
  }
  return false;
}

/**
 * 求解策略。
 *   Strict    —— 危险形式直接抛错。**驻点/交点/实根性判定必须用这个**：
 *                那些场景下"部分解"会静默漏掉极值或交点，比报错更糟。
 *   Decompose —— 先做乘积零积分解，把能精确求解的部分解出来，
 *                解不了的部分写进 note。**只有 solve_sym 用这个**：
 *                它的职责就是把解集报给用户看，部分解 + 说明是诚实的。
 *                factor_sym（expression.cpp）仍走 Strict —— 因式分解只认确定的
 *                有限根，给出不完整的根表比直接说不支持更糟。
 */
enum class SolvePolicy { Strict, Decompose };

/** 把 f=0 按乘积拆成因式，逐个尝试精确求解；解不了的记进 unsolved */
inline void decompose_factors(const SymEngine::RCP<const SymEngine::Basic>& eq,
                              const SymEngine::RCP<const SymEngine::Symbol>& x,
                              const std::string& var,
                              SymEngine::set_basic& roots,
                              std::vector<std::string>& unsolved) {
  using SymEngine::RCP;
  using SymEngine::Basic;
  // Pow(f, n) = 0 ⇔ f = 0（n 为正整数时；常数因子直接跳过）
  if (SymEngine::is_a<SymEngine::Pow>(*eq)) {
    const auto& a = eq->get_args();
    if (a.size() == 2 && SymEngine::is_a_Number(*a[1])) {
      decompose_factors(a[0], x, var, roots, unsolved);
      return;
    }
  }
  if (SymEngine::is_a<SymEngine::Mul>(*eq)) {
    for (const auto& f : eq->get_args()) {
      if (SymEngine::is_a_Number(*f)) continue;
      if (!contains_symbol(*f, var)) continue;   // 不含未知量的因子不影响解
      decompose_factors(f, x, var, roots, unsolved);
    }
    return;
  }
  bool pw = false;
  if (!unsafe_head(*eq, var, pw).empty() || symbolic_exponent(*eq, var)) {
    // 这一项本身解不了：先看能不能当三角方程解（solve_trig），否则记为未解
    if (!pw) {
      try {
        const auto s = SymEngine::solve_trig(eq, x);
        if (SymEngine::is_a<SymEngine::FiniteSet>(*s)) {
          for (const auto& r : s->get_args()) roots.insert(r);
          return;
        }
      } catch (...) {
        // 落到下面的"未解"
      }
    }
    unsolved.push_back(SymEngine::str(*eq));
    return;
  }
  try {
    const auto sol = SymEngine::solve(eq, x);
    if (SymEngine::is_a<SymEngine::FiniteSet>(*sol)) {
      for (const auto& r : sol->get_args()) roots.insert(r);
      return;
    }
  } catch (...) {
    // 求解器自己失败 → 记为未解
  }
  unsolved.push_back(SymEngine::str(*eq));
}

/**
 * 安全求解。
 *
 * @param eq       已化简为 f(x)=0 形式的表达式
 * @param x        求解变量
 * @param what     调用方描述（用于错误信息，如 "驻点方程"、"交点方程"）
 * @param policy   见 SolvePolicy
 * @param note_out 非空时写入说明（部分解、通解形式等），调用方应回传给用户
 */
inline SymEngine::RCP<const SymEngine::Set> safe_solve(
    const SymEngine::RCP<const SymEngine::Basic>& eq,
    const SymEngine::RCP<const SymEngine::Symbol>& x,
    const std::string& what = "方程",
    SolvePolicy policy = SolvePolicy::Strict,
    std::string* note_out = nullptr) {
  using namespace SymEngine;
  const std::string var = x->get_name();
  const std::string s = SymEngine::str(*eq);

  bool piecewise = false;
  const std::string head = unsafe_head(*eq, var, piecewise);
  const bool sym_exp = symbolic_exponent(*eq, var);

  // ① 判据通过（未知量不在超越函数内部、不在指数上、不在根式里）→ 正常交给求解器。
  //    这里包含 sin(1) 这类**常数**超越函数：它不含未知量，是普通系数，不该被拦。
  if (head.empty() && !sym_exp && !has_unknown_radical(*eq, var)) {
    return SymEngine::solve(eq, x);
  }

  // ② 含未知量的根式：实测通用求解器对 sqrt(x)-2 返回**空集**（x=4 明明有解），
  //    属静默错答。根式方程本就该"平方去根号 + 验根"，这里拦住并说清做法。
  if (has_unknown_radical(*eq, var)) {
    throw std::invalid_argument(
        what + "含未知量的根式（" + s +
        "）；通用求解器对根式方程会返回空集或引入增根，本接口不返回可能错误的解集。"
        "请先平方（或换元）去根号后求解，再代回原方程验根；也可用数值求根。");
  }

  // ③ 三角方程：SymEngine 有专用求解器 solve_trig，不必拒绝。
  //    通用 solve() 会在 sin(20*x)=0 这类上栈溢出，而 solve_trig 正是为此写的。
  //    但它的返回必须过 is_usable_solution：实测它对 x*sin(x) 返回的是
  //    {x | 0 == x*sin(x)}（复述原方程的条件集），当通解报出去等于什么都没说。
  if (!piecewise && is_trig_head(head)) {
    try {
      const auto s_trig = SymEngine::solve_trig(eq, x);
      // strict 只认"确定的有限解"：拿到参数族或空集会让驻点/交点静默漏解
      const bool allow_infinite = (policy == SolvePolicy::Decompose);
      if (is_usable_solution(s_trig, allow_infinite)) {
        if (note_out && !SymEngine::is_a<SymEngine::FiniteSet>(*s_trig)) {
          *note_out = "该三角方程的解是无穷族（周期通解），以集合形式给出，含整数参数";
        }
        return s_trig;
      }
    } catch (...) {
      // solve_trig 也解不了 → 继续走下面的分解/报错
    }
  }

  // ③b 指数/对数：走 exp/log 的专用路径 solve_rational（递归远浅于通用 solve）。
  //     只接受**非空有限解集**：空集分不清"确实无解"和"没解出来"，宁可退回报错。
  if (!piecewise && (head == "exp" || head == "log")) {
    try {
      const auto s_rat = SymEngine::solve_rational(eq, x);
      if (is_usable_solution(s_rat, false)) {
        return s_rat;
      }
    } catch (...) {
      // 落到下面的分解/报错
    }
  }

  // ③ 乘积形式：按零积分解出可求解的因子（x*sin(x)=0 → x=0）
  if (policy == SolvePolicy::Decompose) {
    set_basic roots;
    std::vector<std::string> unsolved;
    decompose_factors(eq, x, var, roots, unsolved);
    if (!unsolved.empty() && note_out) {
      std::string joined;
      for (std::size_t i = 0; i < unsolved.size(); ++i) {
        if (i) joined += "、";
        joined += unsolved[i];
      }
      *note_out = "精确解只覆盖可因式分解的部分；下列因子含超越函数，需要数值方法"
                  "（zeros_and_poles / intersections / local_extrema）或参数化解：" + joined;
    }
    if (!roots.empty() || unsolved.empty()) {
      return SymEngine::make_rcp<const SymEngine::FiniteSet>(roots);
    }
  }

  // ④ 仍然不行 → 报错，但要说清"是哪个函数、哪一类、能怎么办"
  if (piecewise) {
    throw std::invalid_argument(
        what + "含分段函数 " + head + "()（" + s +
        "），需要分区间讨论；通用求解器对分段方程会给出不完整的结果，"
        "本接口不返回可能错误的解集。请分区间改写后分别求解，或改用数值方法"
        "（曲线交点 / 极值的数值扫描）。");
  }
  if (sym_exp) {
    throw std::invalid_argument(
        what + "的未知量出现在指数上（" + s +
        "），属超越方程；通用求解器对这类形式会栈溢出，本接口已拦截以避免进程崩溃。"
        "请改用数值方法（zeros_and_poles / intersections），或代入具体参数后再求。");
  }
  throw std::invalid_argument(
      what + "含超越函数 " + head + "()，且未知量就在它内部（" + s +
      "）；SymEngine 的通用求解器对这类方程会栈溢出，本接口已拦截以避免进程崩溃。"
      "可用的替代：数值求根（zeros_and_poles / intersections / local_extrema）、"
      "或代入具体参数后再求。");
}

/** 字符串形式的安全求解（内部先解析）。 */
inline SymEngine::RCP<const SymEngine::Set> safe_solve_str(
    const std::string& expr, const std::string& var, const std::string& what = "方程",
    SolvePolicy policy = SolvePolicy::Strict, std::string* note_out = nullptr) {
  return safe_solve(SymEngine::parse(expr), SymEngine::symbol(var), what, policy, note_out);
}

// ── 表达式复杂度 ────────────────────────────────────────────────────────────

/**
 * 节点数（运算符数）。用于在 multiple 候选形式中挑选"最简"：
 * 同一表达式的 simplify / expand 结果不同，单看某一个可能比原始形式更差
 * （如 (x-a)^2-(x+a)^2 的 simplify 原样返回，而 expand 给出 -4*a*x）。
 */
inline std::size_t node_count(const SymEngine::Basic& b) {
  std::size_t n = 1;
  for (const auto& a : b.get_args()) n += node_count(*a);
  return n;
}

// ── 完全平方识别与根式归约 ──────────────────────────────────────────────────

namespace sqrt_detail {

/** 数值开平方：能开出整数/分数才返回，否则返回 null（表示非完全平方）。
 *  形参保持 RCP<const Basic>（不要写 RCP<const Number>：那需要向下转换，
 *  SymEngine 的 RCP 不支持从基类指针构造派生类 RCP）。 */
inline SymEngine::RCP<const SymEngine::Basic> number_sqrt(
    const SymEngine::RCP<const SymEngine::Basic>& v) {
  using namespace SymEngine;
  if (!is_a_Number(*v)) return null;
  if (down_cast<const Number&>(*v).is_negative())
    return null;  // 负数平方根非实，不当成完全平方处理
  const RCP<const Basic> r = SymEngine::pow(v, rational(1, 2));
  if (is_a<Pow>(*r)) return null;  // 没被开出来（如 2 → sqrt(2)）→ 非完全平方
  return r;
}

/** 指数的偶性：偶数返回 true 并给出 exp/2。 */
inline bool half_exponent(const SymEngine::RCP<const SymEngine::Basic>& exp,
                          SymEngine::RCP<const SymEngine::Basic>& half) {
  using namespace SymEngine;
  if (!is_a<Integer>(*exp)) return false;
  // 显式限定 SymEngine::div / pow：全局命名空间还有 C 的 div/std::pow，
  // 不加限定会与它们构成重载歧义。
  //
  // 必须先确认商仍是整数：div(1,2) 返回有理数 1/2，若只比较
  // mul(q,2)==exp 就会把**奇数**指数 1 误判为偶数（曾导致 4*a 被判成恒非负）。
  const RCP<const Basic> q = SymEngine::div(exp, integer(2));
  if (!is_a<Integer>(*q)) return false;  // 除不尽 → 指数为奇数
  if (SymEngine::neq(*SymEngine::mul(q, integer(2)), *exp)) return false;
  half = q;
  return true;
}

}  // namespace sqrt_detail

/**
 * 若 u 是"可直接开方的完全平方"（a²、4a²、9、a²b²），返回其平方根；否则 null。
 * 例：perfect_sqrt(a²) = a，perfect_sqrt(4a²) = 2a，perfect_sqrt(a²+4) = null。
 */
inline SymEngine::RCP<const SymEngine::Basic> perfect_sqrt(
    const SymEngine::RCP<const SymEngine::Basic>& u) {
  using namespace SymEngine;
  const RCP<const Basic> e = expand(u);

  if (is_a_Number(*e)) return sqrt_detail::number_sqrt(e);

  if (is_a<Pow>(*e)) {
    const auto& p = down_cast<const Pow&>(*e);
    RCP<const Basic> half;
    if (sqrt_detail::half_exponent(p.get_exp(), half))
      return SymEngine::pow(p.get_base(), half);
    return null;
  }

  if (is_a<Mul>(*e)) {
    const auto& m = down_cast<const Mul&>(*e);
    RCP<const Basic> acc = sqrt_detail::number_sqrt(m.get_coef());
    if (acc.is_null()) return null;
    for (const auto& kv : m.get_dict()) {
      RCP<const Basic> half;
      if (!sqrt_detail::half_exponent(kv.second, half)) return null;
      acc = mul(acc, SymEngine::pow(kv.first, half));
    }
    return acc;
  }
  return null;  // 和式等：不做猜测（如 a²+4 并非完全平方）
}

namespace sqrt_detail {

/** 把单个根表达式里的 √(u) 归约为完全平方根（±√(a²) → ±a）。 */
inline SymEngine::RCP<const SymEngine::Basic> reduce_one(
    const SymEngine::RCP<const SymEngine::Basic>& r) {
  using namespace SymEngine;
  const RCP<const Basic> half = rational(1, 2);

  // 形式一：sqrt(u)
  if (is_a<Pow>(*r)) {
    const auto& p = down_cast<const Pow&>(*r);
    if (eq(*p.get_exp(), *half)) {
      const RCP<const Basic> v = perfect_sqrt(p.get_base());
      if (!v.is_null()) return v;
    }
    return r;
  }

  // 形式二：c*sqrt(u)（如 -sqrt(a**2)）
  if (is_a<Mul>(*r)) {
    const auto& m = down_cast<const Mul&>(*r);
    if (m.get_dict().size() == 1) {
      const auto& kv = *m.get_dict().begin();
      if (eq(*kv.second, *half)) {
        const RCP<const Basic> v = perfect_sqrt(kv.first);
        if (!v.is_null()) return mul(m.get_coef(), v);
      }
    }
  }
  return r;
}

}  // namespace sqrt_detail

/**
 * 根集整体归约：把 {±sqrt(a**2)} 变成 {±a}，于是因式分解给出
 * (x + a)*(x - a) 而不是 (x - sqrt(a**2))*(x + sqrt(a**2))。
 *
 * 为什么必须验证：√(a²) 与 a 单独并不恒等（a<0 时差一个符号），
 * 但**根集整体**相同。因此这里先归约、再用多项式恒等 ∏(x-r'i) ≡ ∏(x-ri)
 * 展开比对，只有完全相同才采用；否则原样返回，不做无据化简。
 */
inline std::vector<std::string> reduce_root_radicals(
    const std::vector<std::string>& roots, const std::string& var) {
  using namespace SymEngine;
  if (roots.empty()) return roots;

  const RCP<const Basic> x = symbol(var);
  std::vector<RCP<const Basic>> orig, cand;
  bool changed = false;
  for (const auto& s : roots) {
    const RCP<const Basic> r = parse(s);
    const RCP<const Basic> r2 = sqrt_detail::reduce_one(r);
    if (neq(*r, *r2)) changed = true;
    orig.push_back(r);
    cand.push_back(r2);
  }
  if (!changed) return roots;

  const auto product = [&](const std::vector<RCP<const Basic>>& rs) {
    RCP<const Basic> p = one;
    for (const auto& r : rs) p = mul(p, sub(x, r));
    return expand(p);
  };
  if (!eq(*product(orig), *product(cand))) return roots;  // 不等价 → 放弃

  std::vector<std::string> out;
  out.reserve(cand.size());
  for (const auto& r : cand) out.push_back(str(*r));
  return out;
}

// ── 符号的可证明判定（不做抽样猜测）─────────────────────────────────────────

/** 表达式对参数的符号确定性。Unknown 表示会随参数取值变号（需分类讨论）。 */
enum class Sign { Positive, NonNegative, Zero, NonPositive, Negative, Unknown };

inline const char* sign_name(Sign s) {
  switch (s) {
    case Sign::Positive: return "positive";
    case Sign::NonNegative: return "nonnegative";
    case Sign::Zero: return "zero";
    case Sign::NonPositive: return "nonpositive";
    case Sign::Negative: return "negative";
    default: return "unknown";
  }
}

namespace sign_detail {

struct Monomial {
  bool ok = false;             // 是否成功分解为 系数 × Π(底^次)
  bool coef_positive = false;  // 数值系数为正
  bool all_even = true;        // 每个幂的指数都是偶数（或该项为常数）
  bool is_constant = false;    // 无变量（纯常数项）
};

/** 把单项拆成 数值系数 × 各底数的幂，判断"系数正、幂次全偶"。 */
inline Monomial analyze_monomial(const SymEngine::RCP<const SymEngine::Basic>& t) {
  using namespace SymEngine;
  Monomial out;

  const RCP<const Basic>* body = &t;
  RCP<const Number> coef = one;

  if (is_a<Mul>(*t)) {
    const auto& m = down_cast<const Mul&>(*t);
    coef = m.get_coef();
    if (m.get_dict().empty()) {
      out.ok = true;
      out.is_constant = true;
      out.coef_positive = coef->is_positive();
      return out;
    }
    for (const auto& kv : m.get_dict()) {
      RCP<const Basic> half;
      if (!sqrt_detail::half_exponent(kv.second, half)) out.all_even = false;
    }
    out.ok = true;
    out.is_constant = false;
    out.coef_positive = coef->is_positive();
    return out;
  }

  if (is_a_Number(**body)) {
    out.ok = true;
    out.is_constant = true;
    out.coef_positive = down_cast<const Number&>(**body).is_positive();
    return out;
  }

  if (is_a<Pow>(**body)) {
    RCP<const Basic> half;
    if (!sqrt_detail::half_exponent(down_cast<const Pow&>(**body).get_exp(), half))
      out.all_even = false;
    out.ok = true;
    out.coef_positive = true;
    return out;
  }

  // 裸符号（指数 1，奇）→ 会变号
  if (is_a<Symbol>(**body)) {
    out.ok = true;
    out.all_even = false;
    out.coef_positive = true;
    return out;
  }
  return out;  // 未知结构（函数调用等）
}

}  // namespace sign_detail

/**
 * 判定 f（关于参数，视参数取遍实数）的符号是否恒定，且给出**可证明**的结论。
 *
 * 判据（充分条件，非抽样）：展开后
 *   · f 为常数 → 直接取符号；
 *   · f = 偶次幂 → f ≥ 0；
 *   · f 的每一项都是「正系数 × 各参数偶次幂」→ f ≥ 0；若还有正的常数项 → f > 0。
 *
 * 这是**保守**判定：返回 Unknown 只表示"本算法证明不了"（确实可能变号），
 * 不是"不定号"的结论。例：
 *   a² + 4 → Positive ✓        a² → NonNegative ✓
 *   -4     → Negative ✓        a² - 1 → Unknown（确实变号）✓
 */
namespace sign_detail {

struct NonnegTest {
  bool holds = false;          // 「每项都是正系数 × 偶次幂」是否成立
  bool strictly_positive = false;  // 是否含正的常数项（故 ≥ 严格 > 0）
};

/** 测试 f ≥ 0 是否可用「正系数 × 偶次幂」这一充分条件证明。 */
inline NonnegTest test_nonnegative(const SymEngine::RCP<const SymEngine::Basic>& e) {
  using namespace SymEngine;
  NonnegTest out;

  if (is_a_Number(*e)) {
    out.holds = down_cast<const Number&>(*e).is_positive();
    out.strictly_positive = out.holds;
    return out;
  }

  // 偶次幂整体 ≥ 0（可能取 0，故不 strictly_positive）
  if (is_a<Pow>(*e)) {
    RCP<const Basic> half;
    if (sqrt_detail::half_exponent(down_cast<const Pow&>(*e).get_exp(), half)) {
      out.holds = true;
      return out;
    }
  }

  // 拆成「常数项 + 各变量项」。
  // 注意 Add 把常数项单独放在 get_coef()，不在 get_dict() 里——
  // 漏掉它就会把 a²+4 判成「非负」而不是「恒正」，同理也会漏掉 -4-4a² 的负常数。
  RCP<const Number> constant = zero;  // 非 Add 时无独立常数项（整体已是一个单项）
  std::vector<std::pair<RCP<const Basic>, RCP<const Number>>> terms;
  if (is_a<Add>(*e)) {
    const auto& ad = down_cast<const Add&>(*e);
    constant = ad.get_coef();
    for (const auto& kv : ad.get_dict()) terms.push_back(kv);
  } else {
    terms.push_back({e, one});
  }

  if (constant->is_negative()) return out;  // 常数项为负 → 不满足 ≥0
  const bool has_positive_constant = !constant->is_zero();

  for (const auto& kv : terms) {
    const RCP<const Basic>& term = kv.first;
    const auto& coef = *kv.second;
    if (!coef.is_positive()) return out;  // 系数为 0 的项已被合并，故只可能是负
    const auto m = analyze_monomial(term);
    if (!m.ok || !m.coef_positive || !m.all_even) return out;
  }
  out.holds = true;
  out.strictly_positive = has_positive_constant;
  return out;
}

}  // namespace sign_detail

inline Sign sign_definite(const SymEngine::RCP<const SymEngine::Basic>& f) {
  using namespace SymEngine;
  const RCP<const Basic> e = expand(f);

  if (is_a_Number(*e)) {
    const auto& n = down_cast<const Number&>(*e);
    if (n.is_zero()) return Sign::Zero;
    return n.is_positive() ? Sign::Positive : Sign::Negative;
  }

  const auto pos = sign_detail::test_nonnegative(e);
  if (pos.holds)
    return pos.strictly_positive ? Sign::Positive : Sign::NonNegative;

  // 整体取负再试（覆盖 f = -a² 这类恒负情形）。
  // 注意只试一次：不可递归调用 sign_definite，否则 -a² → a² → -a² 会无限递归。
  const auto neg = sign_detail::test_nonnegative(expand(mul(minus_one, e)));
  if (neg.holds)
    return neg.strictly_positive ? Sign::Negative : Sign::NonPositive;

  return Sign::Unknown;
}

// ── 自然定义域约束 ──────────────────────────────────────────────────────────
//
// 背景：导数零点只是"驻点"，是不是**极值点**还取决于它是否落在函数定义域内。
// 典型反例：f = a·x − ln x（定义域 x>0），f' = a − 1/x 的零点是 x = 1/a：
//   · a<0 时 1/a < 0，根本不在定义域内 → 该分支**没有极值点**；
//   · a=0 时 1/a 无定义 → 同样没有。
// 只按 f''(x₀) 的符号报 minimum/maximum，就会给出"看似合理但错"的答案——
// 在高考导数题里 ln 是最高频形态，这类错误影响面很大。

/**
 * 单条定义域约束。
 *
 * 说明：所有约束都被归约成"对某个表达式的**数值**做一个判断"，因为这样
 * 判定逻辑只需要一处、也不必为每种函数写专门代码：
 *   log(u)            → (u, Positive)
 *   tan(u)            → (cos u, Nonzero)
 *   asin(u)           → (1-u², NonNegative)
 *   Gamma(u)          → (u, NotNonPositiveInteger)   ← 极点在 0,-1,-2,…
 *   zeta(u)           → (u, NotEqualConst{1})
 * 少数无法用符号比较刻画的（极点落在离散集合上）用专门的操作符。
 */
enum class DomainOp {
  Nonzero,                  // v ≠ 0
  Positive,                 // v > 0
  NonNegative,              // v ≥ 0
  NotNonPositiveInteger,    // v ∉ {0,-1,-2,…}（Gamma/Beta/PolyGamma 的极点）
  NotEqualConst,            // v ≠ 常数（用 value 字段给出）
};

struct DomainConstraint {
  SymEngine::RCP<const SymEngine::Basic> expr;  // 被约束的表达式（关于 var 与参数）
  DomainOp op = DomainOp::Nonzero;
  std::string why;   // 可读来源说明，如 "log 的真数要求 > 0"
  double value = 0.0;  // 仅供 NotEqualConst 使用
};

inline const char* domain_op_text(DomainOp op) {
  switch (op) {
    case DomainOp::Nonzero: return "≠ 0";
    case DomainOp::Positive: return "> 0";
    case DomainOp::NonNegative: return "≥ 0";
    case DomainOp::NotNonPositiveInteger: return "∉ {0,−1,−2,…}";
    default: return "≠ 给定值";
  }
}

namespace domain_detail {

inline void collect(const SymEngine::RCP<const SymEngine::Basic>& e,
                    std::vector<DomainConstraint>& out) {
  using namespace SymEngine;

  const auto one_arg = [](const SymEngine::RCP<const SymEngine::Basic>& f) {
    return f->get_args()[0];
  };

  // log(u[, base])：真数 u > 0
  if (is_a<Log>(*e)) {
    out.push_back({one_arg(e), DomainOp::Positive, "log 的真数要求 > 0"});
  }
  // tan/sec：cos(u) ≠ 0；cot/csc：sin(u) ≠ 0
  // 约束写成"某个表达式的值不等于 0"，这样判定仍只需一次符号检查；
  // 直接用 u ∉ {π/2+kπ} 无法用初等表达式刻画。
  if (is_a<Tan>(*e) || is_a<Sec>(*e)) {
    out.push_back({cos(one_arg(e)), DomainOp::Nonzero, "tan/sec 要求 cos(u) ≠ 0"});
  }
  if (is_a<Cot>(*e) || is_a<Csc>(*e)) {
    out.push_back({sin(one_arg(e)), DomainOp::Nonzero, "cot/csc 要求 sin(u) ≠ 0"});
  }
  // asin/acos：|u| ≤ 1 ⟺ 1 - u² ≥ 0
  if (is_a<ASin>(*e) || is_a<ACos>(*e)) {
    out.push_back({sub(one, pow(one_arg(e), integer(2))), DomainOp::NonNegative,
                   "asin/acos 要求 |u| ≤ 1"});
  }
  // asec/acsc：|u| ≥ 1 ⟺ u² - 1 ≥ 0
  if (is_a<ASec>(*e) || is_a<ACsc>(*e)) {
    out.push_back({sub(pow(one_arg(e), integer(2)), one), DomainOp::NonNegative,
                   "asec/acsc 要求 |u| ≥ 1"});
  }
  // atanh/acoth：|u| < 1 ⟺ 1 - u² > 0
  if (is_a<ATanh>(*e)) {
    out.push_back({sub(one, pow(one_arg(e), integer(2))), DomainOp::Positive,
                   "atanh 要求 |u| < 1"});
  }
  if (is_a<ACoth>(*e)) {
    out.push_back({sub(pow(one_arg(e), integer(2)), one), DomainOp::Positive,
                   "acoth 要求 |u| > 1"});
  }
  // acosh：u ≥ 1
  if (is_a<ACosh>(*e)) {
    out.push_back({sub(one_arg(e), one), DomainOp::NonNegative, "acosh 要求 u ≥ 1"});
  }

  // ── 特殊函数 ──────────────────────────────────────────────────────────────
  // Gamma(u)：极点在 u = 0, -1, -2, …（非正整数），这些点不属于定义域
  if (is_a<Gamma>(*e)) {
    out.push_back({one_arg(e), DomainOp::NotNonPositiveInteger,
                   "Gamma 在 0 与负整数处有极点"});
  }
  // LogGamma(u)：只对 u > 0 取实值
  if (is_a<LogGamma>(*e)) {
    out.push_back({one_arg(e), DomainOp::Positive, "log Γ 要求 u > 0"});
  }
  // Beta(a, b)：两个自变量都不得落在非正整数上
  if (is_a<Beta>(*e)) {
    for (const auto& a : e->get_args())
      out.push_back({a, DomainOp::NotNonPositiveInteger, "Beta 在非正整数处有极点"});
  }
  // PolyGamma(n, x)：只约束 **x**。第 1 个参数 n 是求导阶数，是常数不是自变量；
  // 若把常量 n=0 也当自变量加约束，会得到 "0 ∉ {0,−1,−2,…}" 这种恒不成立的
  // 约束，把每个分支都判成"在定义域外"。
  if (is_a<PolyGamma>(*e) && e->get_args().size() >= 2) {
    out.push_back({e->get_args()[1], DomainOp::NotNonPositiveInteger,
                   "PolyGamma 在非正整数处有极点"});
  }
  // zeta(u)：u = 1 处有极点
  if (is_a<Zeta>(*e)) {
    out.push_back({sub(one_arg(e), one), DomainOp::Nonzero, "zeta 在 u = 1 处有极点"});
  }
  // erf / erfc / abs / sign 等在全实轴有定义（整函数），无需约束

  if (is_a<Pow>(*e)) {
    const auto& p = down_cast<const Pow&>(*e);
    const RCP<const Basic> base = p.get_base();
    const RCP<const Basic> exp = p.get_exp();

    if (is_a<Integer>(*exp)) {
      // 整数指数：仅负次幂要求底数 ≠ 0（偶数次幂对负数也成立，无额外约束）
      if (down_cast<const Integer&>(*exp).is_negative())
        out.push_back({base, DomainOp::Nonzero, "分母（负指数）要求 ≠ 0"});
    } else if (is_a<Rational>(*exp)) {
      const auto& r = down_cast<const Rational&>(*exp);
      const RCP<const Integer> den = r.get_den();
      const RCP<const Basic> half = SymEngine::div(den, integer(2));
      if (is_a<Integer>(*half) && eq(*SymEngine::mul(half, integer(2)), *den)) {
        // 偶次根号：u ≥ 0
        out.push_back({base, DomainOp::NonNegative, "偶次根号要求 ≥ 0"});
      } else if (down_cast<const Rational&>(*exp).is_negative()) {
        out.push_back({base, DomainOp::Nonzero, "分母（负指数）要求 ≠ 0"});
      } else {
        // 1/3 之类奇次根号对负数也有定义，无约束
      }
    } else if (!is_a_Number(*exp)) {
      // 指数含变量（如 x^x）：底数必须 > 0
      out.push_back({base, DomainOp::Positive, "指数含变量，底数要求 > 0"});
    } else if (down_cast<const Number&>(*exp).is_negative()) {
      out.push_back({base, DomainOp::Nonzero, "分母（负指数）要求 ≠ 0"});
    }
  }
  for (const auto& a : e->get_args()) collect(a, out);
}

}  // namespace domain_detail

/** 收集表达式对 var 的自然定义域约束（log / 偶次根号 / 分母）。 */
inline std::vector<DomainConstraint> domain_constraints(
    const SymEngine::RCP<const SymEngine::Basic>& e) {
  std::vector<DomainConstraint> out;
  domain_detail::collect(e, out);
  return out;
}

/** 定义域检查结论。 */
enum class DomainVerdict {
  Inside,     // 全部约束满足
  Outside,    // 至少一条被违反 → 该点不在定义域内
  Undefined,  // 约束表达式本身算不出实数（如 log(-1) 的中间步骤）
  Unknown,    // 无法判定
};

/**
 * 在给定取值下检查定义域约束。
 * sub 必须把约束里出现的自由符号都映射到具体数值（含自变量）。
 */
inline DomainVerdict check_domain(
    const std::vector<DomainConstraint>& cs,
    const SymEngine::map_basic_basic& sub) {
  using namespace SymEngine;
  if (cs.empty()) return DomainVerdict::Inside;
  for (const auto& c : cs) {
    double v = 0.0;
    try {
      v = mf::num::eval_double_ex(c.expr, sub);
    } catch (...) {
      return DomainVerdict::Undefined;
    }
    if (!std::isfinite(v)) return DomainVerdict::Undefined;
    // 浮点容差：tan 的极点判据是 cos(u) ≠ 0，而在 u = π/2 附近 cos 只会得到一个
    // 极小的非零值（~1e-17）。若严格要求 v != 0，恰好落在极点上的驻点会被
    // 误判为"在定义域内"。这里把 |v| < 1e-12 视作零——方向是**偏保守**的
    // （宁可报"无极值点"也不虚构一个极值），其它四种约束仍按精确比较。
    constexpr double kZeroTol = 1e-12;
    bool ok = false;
    switch (c.op) {
      case DomainOp::Nonzero: ok = (std::fabs(v) > kZeroTol); break;
      case DomainOp::Positive: ok = (v > 0.0); break;
      case DomainOp::NonNegative: ok = (v >= -kZeroTol); break;
      case DomainOp::NotEqualConst: ok = (std::fabs(v - c.value) > 1e-9); break;
      case DomainOp::NotNonPositiveInteger: {
        // 是否为非正整数（0, -1, -2, …）：整数且在 0 或负侧
        const double r = std::round(v);
        const bool at_integer = std::fabs(v - r) <= 1e-9;
        ok = !(at_integer && r <= 0.0);
        break;
      }
    }
    if (!ok) return DomainVerdict::Outside;
  }
  return DomainVerdict::Inside;
}

// ── 数值求根（符号求解不可用时的回退）──────────────────────────────────────
//
// 用途：SymEngine::solve 对含 tan/asin/sqrt/exp 的方程要么栈溢出、要么静默
// 返回空集，而"无解"和"求解器不会算"必须区分开——前者可以如实回答，后者
// 必须换手段。数值扫描不依赖求解器，能给出**正确但非精确**的驻点，调用方
// 必须把它标注为数值结果，不能冒充精确解。

struct NumericRoot {
  double x = 0.0;
  double residual = 0.0;  // |f(x)|，用于调用方判断这个根有多可信
};

/** 扫描结果：除了根，还要告诉调用方"到底有多少点算得出来"。
 *  gamma/polygamma 等函数没有双精度求值实现时，所有点都算不出，
 *  此时说"未发现驻点"是误导——真实原因是**压根无法数值求值**。 */
struct NumericScan {
  std::vector<NumericRoot> roots;
  int evaluated = 0;       // 成功求值的样本点数
  int total = 0;           // 样本点总数
  bool truncated = false;  // 命中数超过上限，已截断
  // 区间内 |f| 的最小值及其位置：无根时用来判断"确实没有驻点"还是"驻点在区间外"
  double min_mag = std::numeric_limits<double>::infinity();
  double min_mag_x = 0.0;
  // 只要**有一部分**区间可求值就算可用（如 asin 只在 [-1,1] 上有定义，
  // 大范围扫描里绝大多数点都落在定义域外，这不代表无法求值）。
  // 调用方会把可求值比例一并写进说明，让人能自行判断扫描覆盖度。
  bool usable() const { return evaluated > 0 && evaluated * 100 >= total; }
};

/**
 * 在 [lo, hi] 上扫描 f 的零点：
 *   · 变号区间 → 二分细化；
 *   · 重根（不变号）→ 靠"|f| 的局部极小"识别。
 *
 * 已知局限（须如实告知调用方，不能当作完备求根）：
 *   · 只在给定区间内找，区间外的一律看不到；
 *   · 重根若既不变号、又没被网格点正好踩到，仍会漏掉；
 *   · 极点附近的变号会被二分残差检验排除（1/x 在 x=0 处不会误报为根）。
 *
 * @param sub 预先固定的参数取值（把含参方程化为单变量方程）
 */
inline NumericScan numeric_roots_in_range(
    const SymEngine::RCP<const SymEngine::Basic>& f, const std::string& var,
    double lo, double hi, int steps, const SymEngine::map_basic_basic& sub) {
  using namespace SymEngine;
  NumericScan out;
  if (steps < 2 || !(hi > lo)) return out;
  const RCP<const Symbol> x = symbol(var);

  const auto eval_at = [&](double xv, double& v) -> bool {
    try {
      SymEngine::map_basic_basic s = sub;
      s[x] = real_double(xv);
      const double r = mf::num::eval_double_ex(f, s);
      if (!std::isfinite(r)) return false;
      v = r;
      return true;
    } catch (...) {
      return false;  // 该函数没有双精度求值实现时，每个点都会走到这里
    }
  };

  const double h = (hi - lo) / static_cast<double>(steps);
  constexpr double kTol = 1e-6;           // 变号路径的残差门槛
  constexpr double kTangentTol = 1e-9;    // 相切零点经三分细化后的门槛
  constexpr std::size_t kMaxRoots = 200;  // 上限：防止病态输入产出成千上万个"根"
  constexpr int kMaxRefine = 5000;        // 上限：限制三分细化的次数

  /** 三分搜索用的单点求值（返回 (值, 是否可用)）。 */
  const auto probe = [&](double xv) {
    double v = 0.0;
    const bool ok = eval_at(xv, v);
    return std::make_pair(v, ok);
  };

  // ── 第 1 趟：把全部采样点算出来存下 ────────────────────────────────────────
  // 存下来有两个好处：邻域判断不再重复求值；并且能算出整体量级用于筛选。
  std::vector<double> vals(static_cast<std::size_t>(steps) + 1,
                           std::numeric_limits<double>::quiet_NaN());
  std::vector<double> mags;
  for (int i = 0; i <= steps; ++i) {
    ++out.total;
    double v = 0.0;
    if (!eval_at(lo + i * h, v)) continue;
    vals[static_cast<std::size_t>(i)] = v;
    ++out.evaluated;
    mags.push_back(std::fabs(v));
  }
  if (mags.empty()) return out;
  std::sort(mags.begin(), mags.end());
  const double scale = mags[mags.size() / 2] > 0.0 ? mags[mags.size() / 2]
                                                   : mags.back();  // |f| 的中位数
  // 相切零点的候选门槛：相对整体量级。用相对值而不是绝对值，是因为
  // 平坦区里 |f| 的浮点抖动会造成大量"假局部极小"——x·erf(x) 在 [-10,10]
  // 上就有 3243 个假候选，足以把细化次数上限耗尽，真正的零点反而轮不到
  // （实测就是这个原因导致 x=0 被漏掉）。相对筛选能滤掉这些抖动。
  const double candidate_tol = std::max(1e-300, 1e-3 * scale);

  const auto record = [&](double root, double fr) -> bool {
    for (const auto& r : out.roots)
      if (std::fabs(r.x - root) < 1e-9) return true;
    if (out.roots.size() >= kMaxRoots) {
      out.truncated = true;
      return false;
    }
    out.roots.push_back({root, fr});
    return true;
  };

  /**
   * 确认相切零点（f 只在一点触碰 0、不变号，如 cosh(x)-1 在 0）。
   * 判据是"|f| 的局部极小 + 量级相对小"，再在邻域内三分搜索最小化 |f|，
   * 只有确实降到 0 才认定为根。
   */
  int refined = 0;
  const auto confirm_tangent = [&](double lo_c, double hi_c) -> bool {
    if (refined >= kMaxRefine) return false;
    ++refined;
    double a = lo_c, b = hi_c;
    for (int k = 0; k < 70 && (b - a) > 1e-16; ++k) {
      const double m1 = a + (b - a) / 3.0;
      const double m2 = b - (b - a) / 3.0;
      const auto va = probe(m1);
      const auto vb = probe(m2);
      if (!va.second || !vb.second) return false;
      if (std::fabs(va.first) < std::fabs(vb.first)) b = m2;
      else a = m1;
    }
    const double root = 0.5 * (a + b);
    const auto vr = probe(root);
    return vr.second && std::fabs(vr.first) <= kTangentTol && record(root, vr.first);
  };

  // ── 第 2 趟：候选判定 ─────────────────────────────────────────────────────
  //
  // 先把所有"相切零点候选"收集起来，**按 |f| 从小到大排序**再细化。
  // 这一步看似多余，实则是完备性的关键：细化次数有上限，而噪声候选（平坦区
  // 里 |f| 的浮点抖动）可能上千个。按 |f| 排序保证"最像零点"的候选优先拿到
  // 细化额度，真零点不会被噪声挤掉。
  std::vector<std::pair<double, int>> cands;
  cands.reserve(static_cast<std::size_t>(steps) + 1);
  for (int i = 0; i <= steps; ++i) {
    const double vc = vals[static_cast<std::size_t>(i)];
    if (!std::isfinite(vc)) continue;
    const double av = std::fabs(vc);
    if (av > candidate_tol) continue;
    double vl = 0.0, vr = 0.0;
    const bool ok_l = (i > 0) && std::isfinite(vals[i - 1]) && ((vl = vals[i - 1]), true);
    const bool ok_r = (i < steps) && std::isfinite(vals[i + 1]) && ((vr = vals[i + 1]), true);
    const bool le_l = !ok_l || av <= std::fabs(vl);
    const bool le_r = !ok_r || av <= std::fabs(vr);
    const bool candidate = (ok_l && ok_r) ? (le_l && le_r)
                                          : (i == 0 ? le_r : (i == steps ? le_l : false));
    if (candidate) cands.emplace_back(av, i);
  }
  std::sort(cands.begin(), cands.end(),
            [](const std::pair<double, int>& a, const std::pair<double, int>& b) {
              if (a.first != b.first) return a.first < b.first;
              return a.second < b.second;
            });
  for (const auto& c : cands) {
    const double xc = lo + c.second * h;
    if (!confirm_tangent(xc - h, xc + h) && out.truncated) return out;
  }

  // 严格变号 → 二分细化
  for (int i = 1; i <= steps; ++i) {
    const double vc = vals[static_cast<std::size_t>(i)];
    const double vp = vals[static_cast<std::size_t>(i - 1)];
    if (!std::isfinite(vc) || !std::isfinite(vp)) continue;
    if ((vp < 0.0 && vc > 0.0) || (vp > 0.0 && vc < 0.0)) {
      double a = lo + (i - 1) * h, b = lo + i * h, fa = vp;
      for (int k = 0; k < 100 && (b - a) > 1e-15; ++k) {
        const double m = 0.5 * (a + b);
        double fm = 0.0;
        if (!eval_at(m, fm)) break;
        if ((fa < 0.0 && fm < 0.0) || (fa > 0.0 && fm > 0.0)) { a = m; fa = fm; }
        else { b = m; }
      }
      const double root = 0.5 * (a + b);
      double fr = 0.0;
      // 残差检验：极点附近的变号（如 1/x 在 0 处）二分后 |f| 会变大，据此排除
      if (eval_at(root, fr) && std::fabs(fr) < kTol) {
        if (!record(root, fr)) return out;
      }
    }
  }

  // 记录区间内 |f| 的最小值与位置：一个驻点都找不到时，这个值能让调用方
  // 判断"是确实没有驻点，还是驻点就在区间外"（此前只能笼统地说区间外看不到）。
  for (std::size_t i = 0; i < vals.size(); ++i) {
    if (!std::isfinite(vals[i])) continue;
    const double av = std::fabs(vals[i]);
    if (av < out.min_mag) {
      out.min_mag = av;
      out.min_mag_x = lo + static_cast<double>(i) * h;
    }
  }

  std::sort(out.roots.begin(), out.roots.end(),
            [](const NumericRoot& a, const NumericRoot& b) { return a.x < b.x; });
  return out;
}

// ── 含参方程的实根性（绘图交点的 real 依据）─────────────────────────────────

/** 参数分支的代表值取样表：p>0 → 1，p=0 → 0，p<0 → -1。 */
struct Branch {
  std::vector<int> values;  // 每个参数的代表值
  std::string assume;       // 可读假设，如 "a>0, b=0"
};

/**
 * 枚举参数的正/零/负组合。参数多于 3 个时不做枚举（3^n 爆炸）而返回空表，
 * 调用方须自行处理"未枚举"的情形，不得假装覆盖完整。
 */
inline std::vector<Branch> param_branches(const std::vector<std::string>& params) {
  std::vector<Branch> out;
  if (params.empty() || params.size() > 3) return out;
  std::size_t total = 1;
  for (std::size_t i = 0; i < params.size(); ++i) total *= 3;
  for (std::size_t code = 0; code < total; ++code) {
    Branch b;
    std::size_t c = code;
    for (std::size_t i = 0; i < params.size(); ++i) {
      const int s = static_cast<int>(c % 3);
      c /= 3;
      b.values.push_back(s == 0 ? 1 : (s == 1 ? 0 : -1));
      if (!b.assume.empty()) b.assume += ", ";
      b.assume += params[i] + (s == 0 ? ">0" : (s == 1 ? "=0" : "<0"));
    }
    out.push_back(b);
  }
  return out;
}

// ── 表达式等价判定（三态）───────────────────────────────────────────────────
//
// 背景：compare_expr 原实现只用 expand 判「两式之差是否为 0」，而 expand 不做
// 三角恒等，于是 sin²x+cos²x 与 1 被判成「不等」；字段又只有 true/false 两态，
// 调用方无从区分「确实不等」与「本算法证不出」。这里把判定做成三态：
//
//   Equal         已证明恒等（符号方法）
//   NotEqual      已证明不恒等（差为数值常数，或找到数值反例）
//   Undetermined  证不出（**不得**当成 NotEqual 使用）
//
// 判据由强到弱，任一步给出结论即返回：
//   ① 结构相同
//   ② 差的展开为 0            —— 多项式 / 有理式恒等
//   ③ 差为数值常数（非 0）    —— 恒不等，精确
//   ④ simplify 及其组合化差为 0
//   ⑤ 三角恒等替换（sin²u ↔ 1-cos²u）后再化简
//   ⑥ 通分后分子展开为 0      —— 有理式恒等（如 1/(x+1) 与 (x-1)/(x²-1)）
//   ⑦ 无自由符号 → 数值化
//   ⑧ 数值采样：**只用来证明不等**（一个反例即证）。全部样本都 ≈0 只说明
//      「抽样下未见差异」，不构成证明，因此绝不据此返回 Equal。
enum class Equivalence { Equal, NotEqual, Undetermined };

inline const char* equivalence_name(Equivalence v) {
  switch (v) {
    case Equivalence::Equal: return "equal";
    case Equivalence::NotEqual: return "not-equal";
    default: return "undetermined";
  }
}

struct EquivReport {
  Equivalence verdict = Equivalence::Undetermined;
  std::string how;   // 判据（可读，供结果字段说明"凭什么给这个结论"）
};

namespace equiv_detail {

/** 抽样点：全部取正数，避开 log/偶次根号的域外点（域外样本一律跳过，不算证据）。 */
inline const double* sample_points() {
  static const double kPts[] = {2.3, 0.7, 1.9, 3.1, 0.35, 1.4};
  return kPts;
}
inline std::size_t sample_point_count() { return 6; }

/** 把符号换成实数值并求值；任一步不可求值（域外/复数）返回 false。 */
inline bool eval_at(const SymEngine::RCP<const SymEngine::Basic>& e,
                    const std::vector<std::string>& names, std::size_t seed,
                    double& out) {
  using namespace SymEngine;
  map_basic_basic sub;
  const double* pts = sample_points();
  const std::size_t n = sample_point_count();
  try {
    for (std::size_t i = 0; i < names.size(); ++i)
      sub[symbol(names[i])] = real_double(pts[(seed + i) % n]);
    const auto v = e->subs(sub);
    out = eval_double(*v);
  } catch (...) {
    return false;
  }
  return std::isfinite(out);
}

/**
 * 数值反例：任一样本点上两侧明显不等 → 证明不恒等。
 * 用相对阈值（按两侧量级缩放），避免把 1e-17 的舍入噪声当成差异。
 */
inline bool sampling_proves_not_equal(const SymEngine::RCP<const SymEngine::Basic>& a,
                                      const SymEngine::RCP<const SymEngine::Basic>& b,
                                      const std::vector<std::string>& names,
                                      std::string& witness) {
  for (std::size_t k = 0; k < sample_point_count(); ++k) {
    double va = 0.0, vb = 0.0;
    if (!eval_at(a, names, k, va)) continue;
    if (!eval_at(b, names, k, vb)) continue;
    const double scale = 1.0 + std::fabs(va) + std::fabs(vb);
    if (std::fabs(va - vb) > 1e-9 * scale) {
      witness = "在样本点 " + std::to_string(va) + " ≠ " + std::to_string(vb) +
                " 处取值不同";
      return true;
    }
  }
  return false;
}

/**
 * arg 是不是「2 倍」形式（Mul 且数值系数恰好为 2，如 2x、2π）。
 * 倍角恒等式只对这种形式的实参使用，这样 cos(x) 这类普通节点不会被改写成
 * 半角形式 2cos²(x/2)-1——恒等式本身没错，但会把两个待比较的式子一起搅乱，
 * 反而让 simplify 更不容易化到 0。
 */
inline bool is_double_form(const SymEngine::RCP<const SymEngine::Basic>& arg) {
  using namespace SymEngine;
  if (is_a<Integer>(*arg) || is_a<Rational>(*arg)) return true;
  if (!is_a<Mul>(*arg)) return false;
  return eq(*down_cast<const Mul&>(*arg).get_coef(), *integer(2));
}

/**
 * 三角恒等替换表：把 d 里出现的三角节点换成**恒等**的另一种写法，
 * 让「expand 化不开、simplify 也证不出」的等式能被判成相等。
 *
 *   sin²u   → 1 - cos²u         平方关系（只取这一支：两个方向都用会原地打转）
 *   cos(2u) → 2cos²u - 1        倍角
 *   sin(2u) → 2 sin u · cos u   倍角
 *   tan u   → sin u / cos u     商数关系
 *
 * 全是恒等式（在两侧共同的定义域上逐点相等），替换不改变数学含义；
 * 替换结果是否被采纳仍取决于化简后差是否为 0，因此不可能凭替换产生错判。
 */
inline void collect_trig_identities(
    const SymEngine::RCP<const SymEngine::Basic>& e,
    SymEngine::map_basic_basic& out) {
  using namespace SymEngine;
  if (is_a<Pow>(*e)) {
    const auto& p = down_cast<const Pow&>(*e);
    if (eq(*p.get_exp(), *integer(2)) && is_a<Sin>(*p.get_base())) {
      try {
        const auto& u = p.get_base()->get_args()[0];
        out[e] = sub(one, pow(cos(u), integer(2)));
      } catch (...) {
      }
    }
  } else if (is_a<Cos>(*e) || is_a<Sin>(*e) || is_a<Tan>(*e)) {
    try {
      const auto& u = e->get_args()[0];
      if (is_a<Tan>(*e)) {
        out[e] = mul(sin(u), pow(cos(u), integer(-1)));
      } else if (is_double_form(u)) {
        // u = 2h（SymEngine 会自动约掉系数），于是 cos(2h) = 2cos²h - 1
        const auto h = mul(rational(1, 2), u);
        out[e] = is_a<Cos>(*e)
                     ? sub(mul(integer(2), pow(cos(h), integer(2))), one)
                     : mul(integer(2), mul(sin(h), cos(h)));
      }
    } catch (...) {
    }
  }
  for (const auto& a : e->get_args()) collect_trig_identities(a, out);
}

}  // namespace equiv_detail

inline EquivReport prove_equivalent(const SymEngine::RCP<const SymEngine::Basic>& a,
                                    const SymEngine::RCP<const SymEngine::Basic>& b) {
  using namespace SymEngine;
  EquivReport rep;
  if (eq(*a, *b)) {
    rep.verdict = Equivalence::Equal;
    rep.how = "两式结构相同";
    return rep;
  }

  RCP<const Basic> d;
  try {
    d = expand(sub(a, b));
  } catch (...) {
    d = null;
  }

  if (!d.is_null()) {
    if (eq(*d, *zero)) {
      rep.verdict = Equivalence::Equal;
      rep.how = "差的展开为 0";
      return rep;
    }
    if (is_a_Number(*d)) {
      // 非零常数差 → 两式处处相差同一个常数，恒不等（精确，不依赖抽样）
      rep.verdict = Equivalence::NotEqual;
      rep.how = "差的展开是非零常数 " + str(*d);
      return rep;
    }
  }

  // simplify 及其组合
  if (!d.is_null()) {
    static const char* kForms[] = {"simplify", "simplify(expand)", "expand(simplify)"};
    for (int i = 0; i < 3; ++i) {
      try {
        RCP<const Basic> s = (i == 0)   ? simplify(d)
                             : (i == 1) ? simplify(expand(d))
                                        : expand(simplify(d));
        if (eq(*s, *zero)) {
          rep.verdict = Equivalence::Equal;
          rep.how = std::string("差的 ") + kForms[i] + " 为 0";
          return rep;
        }
      } catch (...) {
      }
    }
  }

  // 三角恒等：sin²u → 1-cos²u（只取一支）、倍角 cos2u → 2cos²u-1 / sin2u → 2 sin u cos u、
  // tan u → sin u / cos u。SymEngine::simplify 不做三角恒等，缺了这几条就会把
  // 「sin²x+cos²x 与 1」「cos2x 与 2cos²x-1」这类恒等式判成「证不出」。
  if (!d.is_null()) {
    // 同一批恒等替换可能要把差式化简到 0，不同组合顺序对不同形式有效，逐个试。
    static const int kOrders[] = {0, 1, 2};
    SymEngine::map_basic_basic subs_map;
    equiv_detail::collect_trig_identities(d, subs_map);
    if (!subs_map.empty()) {
      for (int ord : kOrders) {
        try {
          const RCP<const Basic> replaced = d->subs(subs_map);
          const RCP<const Basic> s = (ord == 0)   ? simplify(replaced)
                                     : (ord == 1) ? simplify(expand(replaced))
                                                  : expand(simplify(replaced));
          if (eq(*s, *zero)) {
            rep.verdict = Equivalence::Equal;
            rep.how = "三角恒等替换（sin²u→1-cos²u / 倍角 / tan→sin,cos）后差为 0";
            return rep;
          }
        } catch (...) {
        }
      }
    }
  }

  // 有理式恒等：通分后分子展开为 0（1/(x+1) 与 (x-1)/(x²-1) 这类）
  if (!d.is_null()) {
    try {
      RCP<const Basic> num, den;
      as_numer_denom(d, outArg(num), outArg(den));
      if (eq(*expand(num), *zero)) {
        rep.verdict = Equivalence::Equal;
        rep.how = "通分后分子为 0";
        return rep;
      }
    } catch (...) {
    }
  }

  const std::vector<std::string> names = symbol_names(*a);

  // 无自由符号：直接数值化（常数之间的比较可以精确到双精度）
  if (names.empty()) {
    double va = 0.0, vb = 0.0;
    try {
      va = eval_double(*a);
      vb = eval_double(*b);
    } catch (...) {
      rep.verdict = Equivalence::Undetermined;
      rep.how = "双方均为数值但无法求值（含非实数或特殊函数）";
      return rep;
    }
    if (std::isfinite(va) && std::isfinite(vb)) {
      const double scale = 1.0 + std::fabs(va) + std::fabs(vb);
      if (std::fabs(va - vb) > 1e-9 * scale) {
        rep.verdict = Equivalence::NotEqual;
        rep.how = "两值数值不同";
        return rep;
      }
      if (std::fabs(va - vb) <= 1e-12 * scale) {
        rep.verdict = Equivalence::Equal;
        rep.how = "两值在双精度下相同";
        return rep;
      }
    }
    rep.verdict = Equivalence::Undetermined;
    rep.how = "两值过于接近，无法在双精度下判定";
    return rep;
  }

  // 数值采样：只用来证明不等
  std::string witness;
  if (!d.is_null() && equiv_detail::sampling_proves_not_equal(a, b, names, witness)) {
    rep.verdict = Equivalence::NotEqual;
    rep.how = witness;
    return rep;
  }

  rep.verdict = Equivalence::Undetermined;
  rep.how = "符号方法与数值抽样都未能给出结论（不代表两式不等）";
  return rep;
}

/** 方程的实根性：Real 两根皆实；Complex 无实根；Conditional 视参数取值而定。 */
enum class RootRealness { Real, Complex, Conditional, Unknown };

inline const char* root_realness_name(RootRealness r) {
  switch (r) {
    case RootRealness::Real: return "real";
    case RootRealness::Complex: return "complex";
    case RootRealness::Conditional: return "conditional";
    default: return "unknown";
  }
}

struct RealnessReport {
  RootRealness kind = RootRealness::Unknown;
  std::string reason;      // 人类可读依据
  std::string delta;       // 判别式（非二次式时为空）
  Sign delta_sign = Sign::Unknown;
};

/**
 * 判定"方程 h = 0（关于 var）"的实根性，供绘图决定交点是否可见。
 *
 * 关键：含参数时不能默认判为虚根。旧实现对含参根直接 eval_double，
 * 失败即 real=false，导致 x² = a·x+1（Δ = a²+4 > 0 恒成立）的两个实交点
 * 被标成虚根，解析几何的判别式分类讨论因此全错。本实现改为：
 *   ① 关于 var 的二次式 → 算 Δ，用 sign_definite 证明其符号：
 *      Δ 恒 ≥ 0 → Real（对任意实参数都成立）
 *      Δ 恒 ≤ 0 → Complex
 *      证不出   → Conditional（确实依赖参数，需分类讨论）
 *   ② 更高次且含参数 → 用参数分支代表值抽样，全部实→Real，
 *      全部虚→Complex，有实有虚→Conditional，并注明依据为抽样。
 */
inline RealnessReport equation_realness(
    const SymEngine::RCP<const SymEngine::Basic>& h, const std::string& var) {
  using namespace SymEngine;
  RealnessReport rep;
  // 保持 RCP<const Symbol>：SymEngine::solve 需要 Symbol 形参，
  // 写成 RCP<const Basic> 会触发 Basic→Symbol 的向下转换（RCP 不支持）。
  const SymEngine::RCP<const SymEngine::Symbol> x = SymEngine::symbol(var);

  // ① 二次式：判别式符号可证
  //
  // ⚠ 先确认 h **真的是**关于 var 的二次式，再看 Δ。旧实现只看 coeff(x²)≠0，
  // 于是三次式 x³-6x²+11x-6（coeff(x²) = -6 ≠ 0）也进了这一支：残余的 x³-6
  // 被折进常数项 a0，「判别式」算成含未知量 x 的 -23+24x³，符号自然证不出，
  // realness 被误报成 conditional（实际三个根 1、2、3 全为实根，params=[]）。
  // 判据：coeff(x²) 非 0，且扣掉 a2x²+a1x 后的残余项里不再出现 var。
  const RCP<const Basic> a2 = coeff(*h, *x, *integer(2));
  const RCP<const Basic> a1 = coeff(*h, *x, *integer(1));
  const RCP<const Basic> a0 =
      expand(sub(sub(h, mul(a2, SymEngine::pow(x, integer(2)))), mul(a1, x)));
  if (neq(*a2, *zero) && !contains_symbol(*a0, var)) {
    const RCP<const Basic> d =
        expand(sub(SymEngine::pow(a1, integer(2)), mul(integer(4), mul(a2, a0))));
    rep.delta = str(*d);
    rep.delta_sign = sign_definite(d);
    switch (rep.delta_sign) {
      case Sign::Positive:
        rep.kind = RootRealness::Real;
        rep.reason = "判别式 Δ = " + rep.delta + " 恒为正，对任意实参数都有两个不同实根";
        return rep;
      case Sign::NonNegative:
        rep.kind = RootRealness::Real;
        rep.reason = "判别式 Δ = " + rep.delta + " 恒非负，对任意实参数都有实根（可能重根）";
        return rep;
      case Sign::Zero:
        rep.kind = RootRealness::Real;
        rep.reason = "判别式 Δ = 0，恒为二重实根";
        return rep;
      case Sign::Negative:
        rep.kind = RootRealness::Complex;
        rep.reason = "判别式 Δ = " + rep.delta + " 恒为负，对任意实参数都无实根";
        return rep;
      case Sign::NonPositive:
        rep.kind = RootRealness::Complex;
        rep.reason = "判别式 Δ = " + rep.delta + " 恒非正，仅可能为二重实根";
        return rep;
      case Sign::Unknown:
      default:
        rep.kind = RootRealness::Conditional;
        rep.reason = "判别式 Δ = " + rep.delta +
                     " 的符号依赖参数取值：需按参数分类讨论（Δ>0 两实根，Δ=0 重根，Δ<0 无实根）";
        return rep;
    }
  }

  // ② 更高次含参：抽样参数代表值（明确标注依据为抽样，不冒充证明）
  const auto names = symbol_names(*h);
  std::vector<std::string> params;
  for (const auto& n : names)
    if (n != var) params.push_back(n);

  if (params.empty()) {
    // 无参数的非二次方程：直接精确求解，再逐个判根是实是复。
    // 旧实现这里一律回 Unknown（"交由数值扫描判定"），三次式 x³-6x²+11x-6
    // 即使三个根 1、2、3 全为实根、且 params=[] 也拿不到 realness=real，
    // 绘图交点只能退到数值路径。
    // 只对**多项式**尝试：含超越函数的方程交给数值扫描，且 SymEngine 求解器
    // 对这类输入会**栈溢出崩溃**（进程级故障，catch 不住），必须走 safe_solve 拦截。
    try {
      const auto sol = safe_solve(h, x, "实根性判定");
      if (is_a<FiniteSet>(*sol)) {
        int n_real = 0, n_complex = 0;
        for (const auto& r : down_cast<const FiniteSet&>(*sol).get_args()) {
          if (has_other_symbols(*r, var)) { ++n_complex; continue; }
          double v = 0.0;
          try {
            v = eval_double(*r);
          } catch (...) {
            v = std::numeric_limits<double>::quiet_NaN();
          }
          if (std::isfinite(v)) ++n_real; else ++n_complex;
        }
        if (n_real + n_complex > 0) {
          if (n_complex == 0) {
            rep.kind = RootRealness::Real;
            rep.reason = "精确解出 " + std::to_string(n_real) + " 个根，全为实根";
            return rep;
          }
          if (n_real == 0) {
            rep.kind = RootRealness::Complex;
            rep.reason = "精确解出 " + std::to_string(n_complex) + " 个根，全为复根（无实根）";
            return rep;
          }
          // 有实有复：既不能报 real 也不能报 complex（后者语义是「无实根」），
          // 如实回 unknown 并说明根都已解出，避免调用方误读。
          rep.kind = RootRealness::Unknown;
          rep.reason = "方程既有实根也有复根（" + std::to_string(n_real) + " 实 / " +
                       std::to_string(n_complex) + " 复），实虚性用 roots 逐根区分";
          return rep;
        }
      }
    } catch (...) {
      // 求解失败不致命：回退到原来的「交由数值扫描判定」
    }
    rep.kind = RootRealness::Unknown;
    rep.reason = "非二次式且无参数，实根性交由数值扫描判定";
    return rep;
  }
  if (params.size() > 3) {
    rep.kind = RootRealness::Unknown;
    rep.reason = "参数多于 3 个，未做分支抽样";
    return rep;
  }

  // 以 p>0→1, p=0→0, p<0→-1 为主，再补 2 / -2 两个非 ±1 样本，
  // 避免"代表值恰好退化"，从而减少把 Conditional 误判为 Real 的机会。
  static const int kSamples[] = {1, -1, 2, -2};
  int real_hits = 0, complex_hits = 0, total = 0;
  for (int s : kSamples) {
    for (int s2 : kSamples) {
      if (params.size() > 1 && s2 != s) continue;  // 单参数时只扫一维
      map_basic_basic sub;
      for (std::size_t i = 0; i < params.size(); ++i)
        sub[symbol(params[i])] = integer(i == 0 ? s : s2);
      RCP<const Basic> hv;
      try {
        hv = expand(h->subs(sub));
      } catch (...) {
        continue;
      }
      if (has_other_symbols(*hv, var)) continue;
      std::vector<double> roots;
      try {
        const auto sol = solve(hv, x);
        if (!is_a<FiniteSet>(*sol)) continue;
        for (const auto& r : down_cast<const FiniteSet&>(*sol).get_args()) {
          double d = 0.0;
          try {
            d = eval_double(*r);
          } catch (...) {
            d = std::numeric_limits<double>::quiet_NaN();
          }
          if (std::isfinite(d)) roots.push_back(d);
        }
      } catch (...) {
        continue;
      }
      ++total;
      if (roots.empty())
        ++complex_hits;
      else
        ++real_hits;
    }
  }
  if (total == 0) {
    rep.kind = RootRealness::Unknown;
    rep.reason = "参数抽样未能得到可用样本（方程形式超出判定范围）";
    return rep;
  }
  if (complex_hits == 0) {
    rep.kind = RootRealness::Real;
    rep.reason = "在 " + std::to_string(total) + " 组参数样本下均有实根（抽样判定，非证明）";
  } else if (real_hits == 0) {
    rep.kind = RootRealness::Complex;
    rep.reason = "在 " + std::to_string(total) + " 组参数样本下均无实根（抽样判定，非证明）";
  } else {
    rep.kind = RootRealness::Conditional;
    rep.reason = "实根与否随参数取值改变（" + std::to_string(real_hits) + " 组有实根 / " +
                 std::to_string(complex_hits) + " 组无实根，抽样判定）";
  }
  return rep;
}

}  // namespace mf::symutil
