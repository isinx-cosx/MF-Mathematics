// symbolic_pretty.h — 符号结果的「教科书式」排版（仅头文件）
//
// 背景：SymEngine::str() 输出的是**机器记号**，负指数写成 a**(-1)、
// 分数写成 (1/3)*sqrt(3)*sqrt(a**(-1))，系数 1/-1 也照写（-1*a），
// 特殊值写成 zoo / oo / nan。这类字符串直接进入 UI/答案是不合适的：
//   · 学生看到 a**(-1)、zoo 会以为是笔误；
//   · 负指数掩盖了「这是分式」的结构，看不出定义域限制。
//
// pretty_math() 在**不改动数学含义**的前提下重排为：
//   a**(-1)                      → 1/a
//   a**(-1/2)                    → 1/sqrt(a)
//   x**(1/2) / x**(1/3)          → sqrt(x) / cbrt(x)
//   (1/3)*sqrt(3)*sqrt(a**(-1))  → sqrt(3)/(3*sqrt(a))
//   -1*a                         → -a
//   -1*x + 2                     → 2 - x
//   zoo / oo / -oo / nan         → 无定义 / +∞ / -∞ / 未定义
//   2 + 3*I                      → 2 + 3*I（虚数单位保持 SymEngine 的 I）
//
// 实现要点：Mul 分支自行把因子按指数正负拆成分子/分母，因此输出里
// **不会出现任何负指数**，也不依赖 as_numer_denom 的化简程度。
//
// ⚠ 括号（曾整批丢失，见下）：打印器只做书写重排，**不改变运算顺序**，
// 所以凡是「和式出现在乘法/除法/幂的因子位置」都必须补括号，否则重解析出来的
// 是另一个表达式：
//   (x+2)*(x+3)  曾经打成 "2 + x*3 + x"（重解析 = 2+4x，真值 x²+5x+6）
//   (x+1)/(x+2)  曾经打成 "1 + x/2 + x"（重解析 = 1+3x/2）
//   (x^2-1)/(x-1) 曾经打成 "-1 + x**2/-1 + x"
// 这些串会被回喂引擎（to_engine_expr / compare_expr / —— 见 to_pretty_array 的
// 往返校验），所以括号的正确性与数值正确性是同一件事。
#pragma once

#include <symengine/add.h>
#include <symengine/basic.h>
#include <symengine/complex.h>
#include <symengine/constants.h>
#include <symengine/infinity.h>
#include <symengine/integer.h>
#include <symengine/mul.h>
#include <symengine/nan.h>
#include <symengine/number.h>
#include <symengine/parser.h>
#include <symengine/pow.h>
#include <symengine/printers.h>
#include <symengine/rational.h>
#include <symengine/real_double.h>
#include <symengine/symbol.h>

#include <cctype>
#include <string>

namespace mf::symutil {

using SymEngine::Basic;
using SymEngine::RCP;

namespace pretty_detail {

// 运算符优先级（数值越大结合越紧）
enum Prec { PREC_ADD = 1, PREC_MUL = 2, PREC_POW = 3, PREC_ATOM = 4 };

inline int prec_of(const Basic& b) {
  if (SymEngine::is_a<SymEngine::Add>(b)) return PREC_ADD;
  if (SymEngine::is_a<SymEngine::Mul>(b)) return PREC_MUL;
  if (SymEngine::is_a<SymEngine::Pow>(b)) return PREC_POW;
  return PREC_ATOM;
}

inline std::string wrap(const std::string& s, int prec, int need) {
  return prec < need ? "(" + s + ")" : s;
}

/** 数字是否带负号（Mul 取其数值系数）。 */
inline bool leading_negative(const RCP<const Basic>& t) {
  using namespace SymEngine;
  if (is_a<Integer>(*t)) return down_cast<const Integer&>(*t).is_negative();
  if (is_a<Rational>(*t)) return down_cast<const Rational&>(*t).is_negative();
  if (is_a<RealDouble>(*t)) return down_cast<const RealDouble&>(*t).is_negative();
  if (is_a<Mul>(*t)) {
    const auto& c = *down_cast<const Mul&>(*t).get_coef();
    // 纯虚系数（如 -1/2*I）：Complex::is_negative() 恒为 false，
    // 需看虚部符号，否则会打印出 " + -(1/2)*I*sqrt(3)" 这种双符号
    if (is_a<Complex>(c)) {
      const auto& cx = down_cast<const Complex&>(c);
      if (cx.real_part()->is_zero()) return cx.imaginary_part()->is_negative();
      return false;
    }
    return c.is_negative();
  }
  return false;
}

std::string print_expr(const RCP<const Basic>& e);

/** 乘积因子：优先级低于乘法时补括号。 */
inline std::string factor_str(const RCP<const Basic>& e) {
  return wrap(print_expr(e), prec_of(*e), PREC_MUL);
}

/** 特殊值：SymEngine 的机器记号 → 可读文本。 */
inline const char* special_value(const RCP<const Basic>& e) {
  using namespace SymEngine;
  if (is_a<NaN>(*e)) return "未定义";
  if (is_a<Infty>(*e)) {
    if (eq(*e, *ComplexInf)) return "无定义（复无穷）";
    if (eq(*e, *NegInf)) return "-∞";
    return "+∞";
  }
  return nullptr;
}

/** 幂：指数为 1/n 用根号，负指数转分式。 */
inline std::string pow_str(const RCP<const Basic>& base,
                           const RCP<const Basic>& exp) {
  using namespace SymEngine;
  if (eq(*exp, *one)) return print_expr(base);

  if (eq(*exp, *rational(1, 2))) return "sqrt(" + print_expr(base) + ")";
  if (eq(*exp, *rational(1, 3))) return "cbrt(" + print_expr(base) + ")";

  // 负指数 → 1/(底^|指数|)，保证输出里没有 a**(-1)
  if (is_a_Number(*exp) && down_cast<const Number&>(*exp).is_negative()) {
    const RCP<const Basic> pos = SymEngine::mul(minus_one, exp);
    const std::string inner = pow_str(base, pos);
    const int p = prec_of(*base) == PREC_POW ? PREC_POW : prec_of(*base);
    // 分母为原子或单个幂时不必加括号：1/a、1/sqrt(a)、1/x**2
    const bool atom_like =
        is_a<Symbol>(*base) || is_a<Pow>(*base) || is_a_Number(*base);
    return "1/" + (atom_like ? inner : "(" + inner + ")");
  }

  const std::string bs = wrap(print_expr(base), prec_of(*base), PREC_POW);
  const std::string es = print_expr(exp);
  return bs + "**" + (is_a_Number(*exp) && !is_a<Integer>(*exp) ? "(" + es + ")" : wrap(es, prec_of(*exp), PREC_POW));
}

/**
 * 乘积里的一个因子：base^exp。
 *
 * 幂（exp≠1）的优先级高于乘法，pow_str 已把底数按 PREC_POW 处理，故无需再包；
 * 但 exp==1 时因子就是 base 本身——base 是**和式**时必须补括号，否则
 * (2+x)*(3+x) 会打成 "2 + x*3 + x"（重解析 = 2+4x，真值 x²+5x+6）。
 */
inline std::string mul_factor_str(const RCP<const Basic>& base,
                                  const RCP<const Basic>& exp) {
  using namespace SymEngine;
  if (eq(*exp, *one)) return wrap(print_expr(base), prec_of(*base), PREC_MUL);
  return pow_str(base, exp);
}

/** 数值系数的文字：返回前缀（含符号），并置 present。 */
inline std::string coef_prefix(const RCP<const SymEngine::Number>& coef,
                               bool& present) {
  using namespace SymEngine;
  present = false;
  const bool neg = coef->is_negative();
  if (eq(*coef, *one)) return "";
  if (eq(*coef, *minus_one)) {
    present = true;
    return "-";
  }
  RCP<const Basic> abs_c = neg ? SymEngine::mul(minus_one, coef) : coef;
  // 走 print_expr 而不是 str()：这样 -2*I 、zoo 这类系数也能得到可读文本
  std::string s = print_expr(abs_c);
  // 带分母的分数系数加括号，避免 1/3*x 被读成 1/(3x)
  const bool fractional = is_a<Rational>(*abs_c) &&
                          !eq(*down_cast<const Rational&>(*abs_c).get_den(), *one);
  // 复数系数（含 i 或自身带符号）整体加括号，避免 (-2*i)*sqrt(3) 写成 -2*i*sqrt(3)
  const bool complex_like = is_a<Complex>(*abs_c);
  present = true;
  return (neg ? "-" : "") + (fractional || complex_like ? "(" + s + ")" : s) + "*";
}

inline std::string print_expr(const RCP<const Basic>& e) {
  using namespace SymEngine;

  if (const char* sp = special_value(e)) return sp;

  // 虚数单位：SymEngine 用 I，本打印器**保持 I**。
  // 这些字符串会被回喂引擎（solve_sym 的解 → complex_eval、to_pretty_array 的
  // 往返校验…），而 SymEngine 的解析器只认 I：写成小写 i 会被当成自由变量
  // （free_symbols_of('(x + I)*(x - i)') = ['i','x']），且与 Mul 分支打印出的
  // 系数 I（见下方 is_a<Complex> 分支）自相矛盾——同一个打印器两种写法。
  if (eq(*e, *I)) return "I";

  if (is_a<Symbol>(*e)) return down_cast<const Symbol&>(*e).get_name();
  if (is_a<Integer>(*e) || is_a<Rational>(*e) || is_a<RealDouble>(*e))
    return e->__str__();
  if (is_a<Complex>(*e)) {
    // 虚数单位保持 SymEngine 的 I，**不做 I → i 的替换**：
    // 这些字符串会被调用方回喂给引擎（如 solve_sym 的结果再交给 complex_eval），
    // 而 SymEngine 的解析器只认 I。改成 i 会让解析失败、复根整批消失
    // （曾导致复平面视图 8 项用例失败）。I 也是各类 CAS 的通用写法。
    return e->__str__();
  }

  if (is_a<Add>(*e)) {
    const auto& args = e->get_args();
    std::string out;
    for (std::size_t i = 0; i < args.size(); ++i) {
      RCP<const Basic> term = args[i];
      const bool neg = leading_negative(term);
      if (neg) term = SymEngine::mul(minus_one, term);
      const std::string s = print_expr(term);
      if (i == 0)
        out += neg ? ("-" + s) : s;
      else
        out += neg ? (" - " + s) : (" + " + s);
    }
    return out;
  }

  if (is_a<Mul>(*e)) {
    const auto& m = down_cast<const Mul&>(*e);
    // 分子 / 分母：按指数正负分组，输出中不出现负指数
    std::string num_body, den_body;
    std::size_t den_factors = 0;   // 分母里的因子个数（>1 时整个分母必须加括号）
    for (const auto& kv : m.get_dict()) {
      const RCP<const Basic>& base = kv.first;
      const RCP<const Basic>& exp = kv.second;
      const bool neg_exp = is_a_Number(*exp) && down_cast<const Number&>(*exp).is_negative();
      const std::string t =
          mul_factor_str(base, neg_exp ? SymEngine::mul(minus_one, exp) : exp);
      std::string& bucket = neg_exp ? den_body : num_body;
      if (!bucket.empty()) bucket += "*";
      bucket += t;
      if (neg_exp) ++den_factors;
    }

    // 纯虚系数拆开：把虚部单独提成 I 因子，得到 (1/2)*I*sqrt(3) 而不是
    // (1/2*I)*sqrt(3)。后者虽等价，但把虚数单位裹进括号会让
    // "含 I*sqrt(3)" 这类形式的识别失效（UI 与测试都按前者书写）。
    RCP<const Number> coef = m.get_coef();
    if (is_a<Complex>(*coef)) {
      const auto& cx = down_cast<const Complex&>(*coef);
      if (cx.real_part()->is_zero()) {
        coef = cx.imaginary_part();  // 系数退化为实数虚部（如 1/2、-2）
        num_body = num_body.empty() ? "I" : ("I*" + num_body);
      }
    }

    bool coef_present = false;
    const std::string head = coef_prefix(coef, coef_present);

    // 只有系数（如 1/3 已并入 get_coef，dict 为空）时直接输出系数
    std::string num_part;
    if (coef_present && head == "-") {
      num_part = num_body.empty() ? "-1" : ("-" + num_body);
    } else {
      num_part = head + num_body;
      if (num_part.empty()) num_part = "1";
    }
    if (den_body.empty()) return num_part;
    // 分母是**乘积**时必须整体加括号：1/(a*b) 与 1/a*b 不是一回事。
    // 分母只有一个因子时，若它是和式，mul_factor_str 已经补过括号（(x+1)/(x+2)），
    // 因此这里只看因子个数——旧实现用 "分母串里有没有 *" 判断，于是分母是
    // 「和式且无乘法」时括号被丢掉（(x+1)/(x+2) → "1 + x/2 + x"）。
    return num_part + "/" + (den_factors > 1 ? "(" + den_body + ")" : den_body);
  }

  if (is_a<Pow>(*e)) {
    const auto& p = down_cast<const Pow&>(*e);
    return pow_str(p.get_base(), p.get_exp());
  }

  // 其它（sin/cos/log/… 及各类函数）：退回原打印器
  return e->__str__();
}

}  // namespace pretty_detail

/**
 * 教科书记号排版：负指数转分式、系数 ±1 省略、根式用 sqrt/cbrt、特殊值中文化。
 * 数学含义与原表达式完全相同（只做书写重排，不做化简）。
 */
inline std::string pretty_math(const RCP<const Basic>& e) {
  return pretty_detail::print_expr(e);
}
inline std::string pretty_math(const Basic& e) {
  return pretty_detail::print_expr(e.rcp_from_this());
}

/** 字符串形式（内部先解析）。 */
inline std::string pretty_math_str(const std::string& expr) {
  return pretty_detail::print_expr(SymEngine::parse(expr));
}

/**
 * 表达式是否含非有限值（±∞ / 复无穷 zoo / NaN）。
 * 用于把「该分支下驻点退化、函数值无定义」这类结论写成一句人话，
 * 而不是输出 无定义（复无穷）*sqrt(3) 这种拼接结果。
 */
inline bool has_nonfinite(const SymEngine::Basic& e) {
  if (pretty_detail::special_value(e.rcp_from_this()) != nullptr) return true;
  for (const auto& a : e.get_args())
    if (has_nonfinite(*a)) return true;
  return false;
}

}  // namespace mf::symutil
