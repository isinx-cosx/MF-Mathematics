#include "expression.h"
#include "symbolic_util.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <string>
#include <vector>

#include <symengine/basic.h>
#include <symengine/constants.h>
#include <symengine/eval_double.h>
#include <symengine/functions.h>
#include <symengine/integer.h>
#include <symengine/ntheory.h>
#include <symengine/parser.h>
#include <symengine/printers.h>
#include <symengine/rational.h>
#include <symengine/real_double.h>
#include <symengine/sets.h>
#include <symengine/simplify.h>
#include <symengine/solve.h>
#include <symengine/subs.h>
#include <symengine/symbol.h>

namespace mf::algebra {

namespace {
using SymEngine::RCP;
using SymEngine::Basic;

// 因式分解:按**真实次数**分解,并对每个候选分解做一次**能失败的**恒等式校验。
//
// 说明：全程使用符号判等与精确根（SymEngine::str），不对自由符号做数值化——
// 原实现用"数值采样 + eval_double"验证多项式身份，表达式含参数（如 x^2-a^2）时
// 会抛 "Symbol cannot be evaluated."，已修正。
//
// ⚠ 旧实现的自检是**空泛**的（本文件历史上最大的隐患）：
//   a 取 coeff(x,2)、c 取 e − a·x² − b·x，于是 c 吞掉三次及以上的**全部**项，
//   "重建 == e" 对任何多项式都成立 —— 校验永远通过、永不报警。三次式
//   x³+x²+x+1 因此被当成二次式交给 SymEngine::solve（只回 2 个根），
//   输出 (x+1)*(x+I)，其展开 = −x³+I·x−1+I ≠ 原式（数值 x=2：6+3i vs 15）。
//   自检失效比单点算错更危险，所以这里换成**三条能被违反**的判据：
//     ① 系数不含 x（排除 x²·sin(x)、1/(x−1) 这类"看着像多项式"的输入）；
//     ② 次数取真实次数 d = max{k : c_k ≠ 0}，重建 Σ_{k≤d} c_k·x^k 与 e 精确比对；
//     ③ 候选分解展开后必须与原式恒等，**渲染成字符串后再解析回来再校验一次**。
//   任何一条不成立 → 一律退回展开式，绝不输出看着像答案的错式。

constexpr int kMaxPolyDeg = 32;          // 多项式次数上限（超出即退回展开式）
constexpr long long kCoefLimit = 100000; // 有理根分解允许的最大系数绝对值

// 升幂系数 → 多项式表达式。
RCP<const Basic> poly_from_asc(const std::vector<RCP<const Basic>>& asc, const RCP<const SymEngine::Symbol>& x) {
    RCP<const Basic> out = SymEngine::zero;
    for (std::size_t k = asc.size(); k-- > 0;) {
        if (SymEngine::eq(*asc[k], *SymEngine::zero)) continue;
        out = SymEngine::add(out, SymEngine::mul(
            asc[k], SymEngine::pow(x, SymEngine::integer(static_cast<int>(k)))));
    }
    return out;
}

// 分解恒等式校验：候选分解展开后必须与原式恒等。**这个判据是能失败的**。
bool factorization_holds(const RCP<const Basic>& candidate,
                         const RCP<const Basic>& original) {
    try {
        return SymEngine::eq(*SymEngine::expand(candidate),
                             *SymEngine::expand(original));
    } catch (...) {
        return false;
    }
}

// 把 e 视为 x 的多项式，输出升幂系数（含 0）。返回 false 表示"e 不是 x 的多项式"。
bool poly_coeffs_asc(const RCP<const Basic>& e, const RCP<const SymEngine::Symbol>& x,
                     std::vector<RCP<const Basic>>& asc) {
    asc.clear();
    int deg = -1;
    try {
        for (int k = 0; k <= kMaxPolyDeg; ++k) {
            const auto c = SymEngine::coeff(*e, *x, *SymEngine::integer(k));
            // ① 系数不得再含 x：否则 e 不是 x 的多项式（如 x²·sin(x)、(x−1)⁻¹）。
            for (const auto& s : SymEngine::free_symbols(*c))
                if (SymEngine::eq(*s, *x)) return false;
            asc.push_back(c);
            if (!SymEngine::eq(*c, *SymEngine::zero)) deg = k;
        }
    } catch (...) {
        return false;
    }
    if (deg < 0) return false;  // 恒 0，或 x 的负次幂等
    asc.resize(static_cast<std::size_t>(deg) + 1);
    // ② 真实次数重建：重建覆盖到 x^d，这个恒等式**可以被违反**。
    if (!factorization_holds(poly_from_asc(asc, x), e)) return false;
    return true;
}

// 二次式：解 a·x²+b·x+c=0 取精确根（±a、±√a 等），再校验。
std::string factor_quadratic(const std::vector<RCP<const Basic>>& asc,
                             const RCP<const Basic>& e, const RCP<const SymEngine::Symbol>& x) {
    const auto& a = asc[2];
    RCP<const SymEngine::Set> roots;
    try {
        roots = mf::symutil::safe_solve(poly_from_asc(asc, x), x, "因式分解方程");
    } catch (const std::exception&) {
        // 求解器主动拦截（如系数含超越函数）→ 不做分解，由调用方退回展开式。
        // 这是"显式拒绝"而非"猜一个答案"。
        return {};
    }
    if (!SymEngine::is_a<SymEngine::FiniteSet>(*roots)) return {};
    const auto& fs = SymEngine::down_cast<const SymEngine::FiniteSet&>(*roots);
    std::vector<RCP<const Basic>> distinct;
    for (const auto& r : fs.get_args()) {
        bool dup = false;
        for (const auto& q : distinct)
            if (SymEngine::eq(*q, *r)) { dup = true; break; }
        if (!dup) distinct.push_back(r);
    }
    // 二次式只能有 1（重根）或 2 个不同根；其它情况说明求解结果不可信 → 拒绝。
    if (distinct.empty() || distinct.size() > 2) return {};

    std::vector<RCP<const Basic>> used = distinct;
    if (distinct.size() == 1) used.push_back(distinct[0]);  // 单根 ⇒ 二重根

    RCP<const Basic> cand = a;
    for (const auto& r : used) cand = SymEngine::mul(cand, SymEngine::sub(x, r));
    if (!factorization_holds(cand, e)) return {};           // ③ 不成立的分解 → 拒绝

    std::vector<std::string> rv;
    rv.reserve(distinct.size());
    for (const auto& r : distinct) rv.push_back(SymEngine::str(*r));
    std::sort(rv.begin(), rv.end());
    std::string out;
    if (!SymEngine::eq(*a, *SymEngine::one)) out += SymEngine::str(*a) + "*";
    if (rv.size() == 1)
        out += mf::symutil::factor_of_root("x", rv[0]) + "**2";
    else
        out += mf::symutil::factor_of_root("x", rv[0]) + "*" +
               mf::symutil::factor_of_root("x", rv[1]);
    // ③ 渲染后的字符串再解析回来校验一次（根为负号时 "+"/"−" 的选取也可能写错）。
    try {
        if (!factorization_holds(SymEngine::parse(out), e)) return {};
    } catch (...) {
        return {};
    }
    return out;
}

// ── 三次及以上：有理根定理 + 精确综合除法降次 ───────────────────────────────
//
// factor 的语义与 sympy.factor 一致：在**有理数域**上分解。
//   · 用有理根定理找有理根 p/q，再用 (q·x − p) 做精确综合除法降次；
//   · 降到二次后若无有理根，就保持二次式（ℚ 上不可约）—— 这正是
//     x³+x²+x+1 → (x+1)*(x²+1) 而不是 (x+1)*(x−I)*(x+I) 的原因；
//   · 次数 ≥ 4 且无有理根时保留残余多项式，不做没有依据的进一步拆分。

long long gcd_ll(long long a, long long b) {
    if (a < 0) a = -a;
    if (b < 0) b = -b;
    while (b) { const long long t = a % b; a = b; b = t; }
    return a;
}

std::vector<long long> divisors_of(long long n) {
    std::vector<long long> out;
    if (n < 0) n = -n;
    if (n == 0) return out;
    for (long long i = 1; i * i <= n; ++i) {
        if (n % i != 0) continue;
        out.push_back(i);
        if (i != n / i) out.push_back(n / i);
    }
    std::sort(out.begin(), out.end());
    return out;
}

// 取小数整数值：只在能被 long long 安全表示时成功。
// （Integer::as_int() 在 Windows 上是 32 位，因此额外用十进制位数设上限；
//  超限即放弃有理根分解，绝不猜。）
bool to_small_int(const RCP<const Basic>& c, long long& out) {
    const std::string s = SymEngine::str(*c);
    if (s.empty() || s.size() > 9) return false;
    for (char ch : s)
        if (!((ch >= '0' && ch <= '9') || ch == '-')) return false;
    try {
        out = std::stoll(s);
    } catch (...) {
        return false;
    }
    return (out < 0 ? -out : out) <= kCoefLimit;
}

// 用 (q·x − p) 精确除升幂系数多项式；整除成功返回商，否则返回 false。
bool divide_by_linear(const std::vector<RCP<const Basic>>& a, long long p, long long q,
                      std::vector<RCP<const Basic>>& out) {
    const std::size_t d = a.size() - 1;
    const RCP<const Basic> Q = SymEngine::integer(static_cast<int>(q));
    const RCP<const Basic> P = SymEngine::integer(static_cast<int>(p));
    std::vector<RCP<const Basic>> b(d, SymEngine::zero);
    RCP<const Basic> carry = SymEngine::zero;
    for (std::size_t i = d; i >= 1; --i) {
        const RCP<const Basic> t = SymEngine::add(a[i], SymEngine::mul(P, carry));
        b[i - 1] = SymEngine::div(t, Q);
        carry = b[i - 1];
    }
    const RCP<const Basic> rem = SymEngine::add(a[0], SymEngine::mul(P, carry));
    if (!SymEngine::eq(*SymEngine::expand(rem), *SymEngine::zero)) return false;
    out = b;
    return true;
}

// 整系数多项式在 p/q 处是否为 0（精确代入，不做浮点判断）。
bool evaluates_to_zero(const RCP<const Basic>& poly, const RCP<const SymEngine::Symbol>& x,
                       long long p, long long q) {
    try {
        const auto v = poly->subs({{x, SymEngine::rational(p, q)}});
        return SymEngine::eq(*SymEngine::expand(v), *SymEngine::zero);
    } catch (...) {
        return false;
    }
}

// 一次因式 (q·x − p) 的可读渲染。
std::string render_linear(long long p, long long q) {
    if (q == 1) return mf::symutil::factor_of_root("x", std::to_string(p));
    std::string body = std::to_string(q) + "*x";
    if (p < 0) body += " + " + std::to_string(-p);
    else if (p > 0) body += " - " + std::to_string(p);
    return "(" + body + ")";
}

// 整系数残余多项式（升幂）→ 降幂教材写法（系数 1 省略）。
std::string render_int_poly(const std::vector<long long>& c) {
    std::string out;
    for (int k = static_cast<int>(c.size()) - 1; k >= 0; --k) {
        if (c[k] == 0) continue;
        const bool neg = c[k] < 0;
        const long long av = neg ? -c[k] : c[k];
        std::string term;
        if (k == 0) {
            term = std::to_string(av);
        } else {
            if (av != 1) term = std::to_string(av) + "*";
            term += (k == 1) ? "x" : ("x**" + std::to_string(k));
        }
        if (out.empty()) out = (neg ? "-" : "") + term;
        else out += (neg ? " - " : " + ") + term;
    }
    return out.empty() ? "0" : out;
}

std::string factor_by_rational_roots(const std::vector<RCP<const Basic>>& asc0,
                                     const RCP<const Basic>& e,
                                     const RCP<const SymEngine::Symbol>& x) {
    // ① 只处理有理系数：先通分得到整数系数 J = L·e，再提出内容 g。
    std::vector<long long> ints(asc0.size(), 0);
    long long L = 1;
    for (std::size_t i = 0; i < asc0.size(); ++i) {
        const auto& c = asc0[i];
        long long n = 0, q = 1;
        if (SymEngine::is_a<SymEngine::Integer>(*c)) {
            if (!to_small_int(c, n)) return {};
        } else if (SymEngine::is_a<SymEngine::Rational>(*c)) {
            const auto& r = SymEngine::down_cast<const SymEngine::Rational&>(*c);
            if (!to_small_int(r.get_num(), n) || !to_small_int(r.get_den(), q)) return {};
            if (q <= 0) return {};
        } else {
            return {};  // 含参数/无理数/浮点系数 → 不做有理根分解
        }
        // 统一到同一分母 L。
        n *= (L / gcd_ll(L, q));
        if (q != 1) {
            const long long scale = q / gcd_ll(L, q);
            for (std::size_t j = 0; j < i; ++j) ints[j] *= scale;
            L *= scale;
        }
        ints[i] = n;
    }
    long long g = 0;
    for (long long v : ints) g = gcd_ll(g, v);
    if (g == 0) return {};
    for (long long& v : ints) v /= g;
    const long long num_scalar = g, den_scalar = L;

    std::vector<long long> cur = ints;
    std::vector<std::string> pieces;
    int extracted = 0;
    bool ok = true;
    for (int guard = 0; guard < kMaxPolyDeg && ok; ++guard) {
        while (cur.size() > 1 && cur.back() == 0) cur.pop_back();
        if (cur.size() <= 1) { pieces.push_back(render_int_poly(cur)); break; }

        const std::size_t d = cur.size() - 1;
        std::vector<long long> cand_p, cand_q;
        if (cur[0] == 0) {
            cand_p.push_back(0);          // 常数项为 0 ⇒ x 是因子
            cand_q.push_back(1);
        } else {
            cand_p = divisors_of(cur[0]);
            for (long long& v : cand_p) v = -v;         // 先试负根（教材题常见）
            const auto pos = divisors_of(cur[0]);
            cand_p.insert(cand_p.end(), pos.begin(), pos.end());
            cand_q = divisors_of(cur[d]);
        }

        const RCP<const Basic> poly = poly_from_asc(
            [&] { std::vector<RCP<const Basic>> a; for (long long v : cur) a.push_back(SymEngine::integer(static_cast<int>(v))); return a; }(), x);

        bool found = false;
        long long rp = 0, rq = 1;
        for (long long qq : cand_q) {
            if (found) break;
            for (long long pp : cand_p) {
                if (pp == 0 && qq != 1) continue;
                long long gg = gcd_ll(pp, qq);
                if (gg == 0) gg = 1;
                const long long p2 = pp / gg, q2 = qq / gg;
                if (q2 <= 0) continue;
                if (q2 == 0) continue;
                if (!evaluates_to_zero(poly, x, p2, q2)) continue;
                // divide_by_linear 吃的是**升幂系数向量**（不是多项式对象）：
                // 用 (q·x − p) 做精确带余除法，余式为 0 才算整除。
                std::vector<RCP<const Basic>> coeffs;
                coeffs.reserve(cur.size());
                for (long long v : cur)
                    coeffs.push_back(SymEngine::integer(static_cast<int>(v)));
                std::vector<RCP<const Basic>> quot;
                if (!divide_by_linear(coeffs, p2, q2, quot)) continue;
                found = true; rp = p2; rq = q2;
                cur.clear();
                for (const auto& b : quot) {
                    long long v = 0;
                    if (!to_small_int(b, v)) { found = false; break; }
                    cur.push_back(v);
                }
                break;
            }
        }
        if (!found) { pieces.push_back(render_int_poly(cur)); break; }
        pieces.push_back(render_linear(rp, rq));
        ++extracted;
    }
    if (!ok || extracted == 0) return {};
    if (pieces.empty()) return {};

    // ② 组装字符串 + 展开恒等校验（校验失败一律退回展开式）。
    std::string out;
    if (num_scalar != den_scalar) {
        if (den_scalar == 1) out = std::to_string(num_scalar) + "*";
        else out = std::to_string(num_scalar) + "/" + std::to_string(den_scalar) + "*";
    }
    for (std::size_t i = 0; i < pieces.size(); ++i) {
        if (i) out += "*";
        out += (pieces[i].size() >= 2 && pieces[i][0] == '(' && pieces[i].back() == ')')
                   ? pieces[i]
                   : ("(" + pieces[i] + ")");
    }
    try {
        const auto cand = SymEngine::parse(out);
        if (!factorization_holds(cand, e)) return {};
    } catch (...) {
        return {};
    }
    return out;
}

std::string factor_expr(const std::string& expr) {
    const auto x = SymEngine::symbol("x");
    const auto e = SymEngine::parse(expr);
    const std::string expanded = SymEngine::str(*SymEngine::expand(e));

    std::vector<RCP<const Basic>> asc;
    if (!poly_coeffs_asc(e, x, asc)) return expanded;  // 不是 x 的多项式 → 原样展开
    const std::size_t d = asc.size() - 1;
    if (d < 2) return expanded;                        // 0/1 次：没有可分解的因式

    const std::string out = (d == 2) ? factor_quadratic(asc, e, x)
                                     : factor_by_rational_roots(asc, e, x);
    if (out.empty()) return expanded;                  // 分解不成立/超出能力 → 退回展开式
    return out;
}

// 检查表达式是否含 sqrt。
bool has_sqrt(const std::string& s) {
    return s.find("sqrt") != std::string::npos;
}

std::string simplify1(const std::string& expr) {
    return SymEngine::str(*SymEngine::simplify(SymEngine::parse(expr)));
}
}  // namespace

std::string simplify_polynomial(const std::string& expr) {
    const std::string f = factor_expr(expr);
    if (f != SymEngine::str(*SymEngine::expand(SymEngine::parse(expr))))
        return f;  // 能分解则返回分解。
    return simplify1(expr);
}

std::string expand_expression(const std::string& expr) {
    return SymEngine::str(*SymEngine::expand(SymEngine::parse(expr)));
}

std::string factor(const std::string& expr) { return factor_expr(expr); }
std::string factor_common(const std::string& expr) { return factor_expr(expr); }
std::string factor_perfect_square(const std::string& expr) { return factor_expr(expr); }
std::string factor_difference_squares(const std::string& expr) { return factor_expr(expr); }
std::string factor_cross(const std::string& expr) { return factor_expr(expr); }
std::string factor_group(const std::string& expr) { return factor_expr(expr); }

std::string simplify_fraction(const std::string& expr) { return simplify1(expr); }

CommonDenominatorResult common_denominator(const std::string& e1,
                                           const std::string& e2) {
    CommonDenominatorResult r;
    const auto p1 = SymEngine::parse(e1);
    const auto p2 = SymEngine::parse(e2);
    RCP<const Basic> n1, d1, n2, d2;
    SymEngine::as_numer_denom(p1, outArg(n1), outArg(d1));
    SymEngine::as_numer_denom(p2, outArg(n2), outArg(d2));
    const auto lcm = SymEngine::simplify(SymEngine::mul(d1, d2));
    r.den = SymEngine::str(*lcm);
    r.new1 = simplify1("(" + SymEngine::str(*n1) + ")*(" + SymEngine::str(*lcm) +
                       ")/(" + SymEngine::str(*d1) + ")");
    r.new2 = simplify1("(" + SymEngine::str(*n2) + ")*(" + SymEngine::str(*lcm) +
                       ")/(" + SymEngine::str(*d2) + ")");
    return r;
}

std::string fraction_operations(const std::string& e1, const std::string& op,
                                const std::string& e2) {
    if (op == "/") {
        const bool zero = SymEngine::eq(*SymEngine::simplify(SymEngine::parse(e2)),
                                        *SymEngine::zero);
        if (zero) throw std::invalid_argument("除数不能为零");
    }
    return simplify1("(" + e1 + ")" + op + "(" + e2 + ")");
}

std::string rationalize_denominator(const std::string& expr) {
    return simplify1(expr);
}

// 化简 sqrt(N)(整数):提出最大平方因子。
std::string sqrt_simplify_int(long long N) {
    if (N < 0) return "sqrt(" + std::to_string(N) + ")";
    long long square = 1, rest = N;
    for (long long f = 2; f * f <= N; ++f) {
        while (rest % (f * f) == 0) {
            square *= f;
            rest /= f * f;
        }
    }
    if (square > 1 && rest > 1) return std::to_string(square) + "*sqrt(" +
                                       std::to_string(rest) + ")";
    if (rest > 1) return "sqrt(" + std::to_string(rest) + ")";
    return std::to_string(square);
}

// 把串里所有 sqrt(N)（N 为十进制整数）替换成提出平方因子后的形式：√8 → 2*√2。
//
// SymEngine 的 simplify **不会**自动提出根号内的平方因子：simplify(sqrt(8)) 仍是
// 8**(1/2)，于是 √8/√2 化简后仍带根号，让「比值不再含根式 ⇒ 同类根式」这条判据
// 把 √8 与 √2 误判成不同类。判同类之前必须先做这一步真实的化简。
std::string pull_square_factors(const std::string& s) {
    std::string out;
    std::size_t pos = 0;
    while (pos < s.size()) {
        const std::size_t sp = s.find("sqrt(", pos);
        if (sp == std::string::npos) {
            out.append(s, pos, std::string::npos);
            break;
        }
        const std::size_t open = sp + 5;
        const std::size_t close = s.find(')', open);
        if (close == std::string::npos) {  // 括号不配对 → 剩余部分原样保留
            out.append(s, pos, std::string::npos);
            break;
        }
        const std::string inner = s.substr(open, close - open);
        bool digits = !inner.empty();
        for (char ch : inner)
            if (ch < '0' || ch > '9') { digits = false; break; }
        long long n = 0;
        if (digits) {
            try {
                n = std::stoll(inner);
            } catch (...) {
                digits = false;
            }
        }
        // 根号下不是正整数（sqrt(x)、sqrt(x-1)…）或 0/1 这类无需提因子的情形：
        // 原样搬回，交给调用方的 simplify1 处理。
        if (!digits || n < 2) {
            out.append(s, pos, open - pos);
            pos = open;
            continue;
        }
        out.append(s, pos, sp - pos);
        out += sqrt_simplify_int(n);
        pos = close + 1;
    }
    return out;
}

std::string simplify_radical(const std::string& expr) {
    const std::size_t sp = expr.find("sqrt(");
    if (sp == std::string::npos) return simplify1(expr);
    const std::size_t close = expr.rfind(')');
    if (close == std::string::npos || close <= sp) return simplify1(expr);
    const std::string inner = expr.substr(sp + 5, close - sp - 5);
    try {
        const long long N = std::stoll(inner);
        return sqrt_simplify_int(N);
    } catch (...) {
        return simplify1(expr);
    }
}

// 若表达式恰为 "sqrt(N)",返回 N;否则 -1。
long long extract_radicand(const std::string& expr) {
    std::string s = expr;
    const std::size_t sp = s.find("sqrt(");
    if (sp == std::string::npos) return -1;
    if (sp != 0 && s.substr(0, sp).find_first_not_of(" \t") != std::string::npos)
        return -1;
    const std::size_t close = s.rfind(')');
    if (close != s.size() - 1) return -1;
    const std::string inner = s.substr(sp + 5, close - sp - 5);
    try {
        return std::stoll(inner);
    } catch (...) {
        return -1;
    }
}

LikeRadicalsResult like_radicals(const std::string& e1, const std::string& e2) {
    LikeRadicalsResult r;
    // 先提出平方因子（√8 → 2√2）再做符号化简：SymEngine 自己不会提,
    // 不提的话 √8/√2 的比值里还留着根号，判据必然误判。
    r.radical1 = simplify1(pull_square_factors(e1));
    r.radical2 = simplify1(pull_square_factors(e2));
    // 比值是否不再含根式 → 同类根式。
    const std::string ratio = simplify1("(" + r.radical1 + ")/(" + r.radical2 + ")");
    r.is_like = !has_sqrt(ratio) && ratio.find("x") == std::string::npos;
    return r;
}

std::string radical_operations(const std::string& e1, const std::string& op,
                               const std::string& e2) {
    const long long n1 = extract_radicand(e1);
    const long long n2 = extract_radicand(e2);
    if (n1 > 0 && n2 > 0) {
        if (op == "*") return sqrt_simplify_int(n1 * n2);
        if (op == "/") {
            // sqrt(a)/sqrt(b) = sqrt(a/b),化简为有理形式。
            return simplify1("sqrt(" + std::to_string(n1) + ")/sqrt(" +
                             std::to_string(n2) + ")");
        }
        if (op == "+" || op == "-") {
            // 同类根式合并系数。
            const std::string sa = simplify1("sqrt(" + std::to_string(n1) + ")");
            const std::string sb = simplify1("sqrt(" + std::to_string(n2) + ")");
            if (sa == sb) return (op == "+" ? "2*" : "0") + sa;
            return simplify1("(" + e1 + ")" + op + "(" + e2 + ")");
        }
    }
    return simplify1("(" + e1 + ")" + op + "(" + e2 + ")");
}

}  // namespace mf::algebra
