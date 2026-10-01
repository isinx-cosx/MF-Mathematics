// math_input.h — 数学输入规范化（仅头文件）
//
// 目的：让人按**课本写法**输入，而不是按程序语法输入。
//
// 实测旧解析器只认"程序员写法"：cosx、sin x、2x、x^2、pi、√x、|x|、lnx、asin
// 全部解析失败（2x 报"多余字符"、x^2 同样、pi 被当成未定义变量）。
// 其中"函数名后无括号"这一类由 parser_lib.h 的词法层解决；本文件负责
// **字符层面的归一**，两类改动互不重叠：
//
//   ① 全角字符：（）＋－＊／＾＝，　以及全角数字/字母 → 半角
//   ② Unicode 数学符号：× · ÷ − ² ³ ≤ ≥ ≠ π θ √ ∛
//   ③ LaTeX 命令：\frac{}{}、\sqrt{}、\sin、\pi、\cdot、\left/\right、{ }
//
// 全部改写都记录在 notes 里，界面可以显示"你输入的被这样理解了"——
// 这比静默改写安全：用户能立刻发现自己想写的其实不是这个。
//
// 设计约束：只做**字符级**替换，绝不重排表达式结构；
// 拿不准的一律不改（宁可报错，也不猜）。
#pragma once

#include <cctype>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

namespace mf::input {

// 把隐式乘法写成显式乘法（定义在文件末尾，normalize 里要用）
inline std::string implicit_multiplication(const std::string& s);
// √x → sqrt(x)、|x| → abs(x)（同理）
inline std::string sqrt_fences_to_function(const std::string& s);
inline std::string abs_fences_to_function(const std::string& s);
// 方程写法 "左 = 右"（定义见文件末尾）
inline bool is_equation(const std::string& s);
inline bool equation_to_zero(std::string& text, std::string& error);

/** 规范化结果。 */
struct Prepared {
    std::string text;                // 规范化后的表达式（引擎可直接解析）
    std::vector<std::string> notes;  // 做了哪些类别的改写（可读，供界面展示）

    bool changed() const { return !notes.empty(); }
};

namespace detail {

/** UTF-8 解码为码点序列；非法字节按单字节原样保留（0x80|b）。 */
inline std::vector<std::uint32_t> utf8_decode(const std::string& s) {
    std::vector<std::uint32_t> out;
    out.reserve(s.size());
    std::size_t i = 0;
    while (i < s.size()) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        std::size_t n = 0;
        std::uint32_t cp = 0;
        if (c < 0x80) { n = 1; cp = c; }
        else if ((c & 0xE0) == 0xC0) { n = 2; cp = c & 0x1Fu; }
        else if ((c & 0xF0) == 0xE0) { n = 3; cp = c & 0x0Fu; }
        else if ((c & 0xF8) == 0xF0) { n = 4; cp = c & 0x07u; }
        else { out.push_back(c); ++i; continue; }
        if (i + n > s.size()) { out.push_back(c); ++i; continue; }
        bool ok = true;
        for (std::size_t k = 1; k < n; ++k) {
            const unsigned char cc = static_cast<unsigned char>(s[i + k]);
            if ((cc & 0xC0) != 0x80) { ok = false; break; }
            cp = (cp << 6) | (cc & 0x3Fu);
        }
        if (!ok) { out.push_back(c); ++i; continue; }
        out.push_back(cp);
        i += n;
    }
    return out;
}

/** 码点 → 替换文本；返回空表示不需要替换。 */
inline std::string map_codepoint(std::uint32_t cp, bool& is_fullwidth_alnum) {
    is_fullwidth_alnum = false;
    // ① 全角 ASCII（U+FF01..U+FF5E → U+0021..U+007E）
    if (cp >= 0xFF01 && cp <= 0xFF5E) {
        const char a = static_cast<char>(cp - 0xFF01 + 0x21);
        if ((a >= '0' && a <= '9') || (a >= 'A' && a <= 'Z') || (a >= 'a' && a <= 'z'))
            is_fullwidth_alnum = true;
        return std::string(1, a);
    }
    if (cp == 0x3000) return " ";  // 全角空格
    // ② Unicode 数学符号
    switch (cp) {
        case 0x00D7: return "*";   // ×
        case 0x00B7: return "*";   // ·
        case 0x22C5: return "*";   // ⋅
        case 0x2219: return "*";   // ∙
        case 0x00F7: return "/";   // ÷
        case 0x2212: return "-";   // − 减号
        case 0x2010: case 0x2011: case 0x2012:
        case 0x2013: case 0x2014: return "-";  // ‐ ‑ ‒ – —
        case 0x00B2: return "^2";  // ²
        case 0x00B3: return "^3";  // ³
        case 0x00B9: return "^1";  // ¹
        case 0x2070: return "^0";  // ⁰
        case 0x2074: return "^4";  // ⁴
        case 0x2075: return "^5";
        case 0x2076: return "^6";
        case 0x2077: return "^7";
        case 0x2078: return "^8";
        case 0x2079: return "^9";
        case 0x207B: return "-";   // ⁻（上标减号，如 x⁻¹）
        case 0x2264: return "<=";  // ≤
        case 0x2265: return ">=";  // ≥
        case 0x2260: return "!=";  // ≠
        case 0x2261: return "==";  // ≡
        case 0x03C0: case 0x03A0: return "pi";      // π Π
        case 0x03B8: return "theta";                // θ
        case 0x221B: return "cbrt";                 // ∛
        case 0x221E: return "oo";   // ∞：引擎与 SymEngine 都认 oo（原先写的是 Inf，两条路径都不认 → "无法解析"）
        case 0x221A: return "sqrt"; // √（后面没有括号/参数时也能被 sqrt_fences_to_function 接住）
        default: break;
    }
    return std::string();
}

/** 判断码点是否为标识符字符（ASCII 字母数字下划线）。 */
inline bool is_ident_cp(std::uint32_t cp) {
    return (cp >= '0' && cp <= '9') || (cp >= 'A' && cp <= 'Z') ||
           (cp >= 'a' && cp <= 'z') || cp == '_';
}

inline bool is_space_cp(std::uint32_t cp) { return cp == ' ' || cp == '\t'; }

inline void note(std::vector<std::string>& notes, const std::string& n) {
    for (const auto& x : notes)
        if (x == n) return;
    notes.push_back(n);
}

}  // namespace detail

/** 展开"包装类"命令：把 \operatorname{X} 之类替换成 X（保留花括号里的内容）。
 *  必须在主扫描**之前**做，因为这些命令可能嵌在 \frac{}/\sqrt{} 的参数里，
 *  而参数是整段原样取出的（MathLive 的类型化输入常产生 \placeholder{}）。 */
inline std::string unwrap_wrapper_commands(const std::string& s) {
    static const char* kWrap[] = {"\\operatorname", "\\mathrm", "\\mathit",
                                 "\\text", "\\placeholder", "\\mathord"};
    std::string cur = s;
    bool again = true;
    while (again) {
        again = false;
        for (const char* w : kWrap) {
            const std::string cmd(w);
            const std::size_t p = cur.find(cmd);
            if (p == std::string::npos) continue;
            std::size_t q = p + cmd.size();
            if (q < cur.size() && cur[q] == '{') {
                // 找到配对的花括号，只保留其中的内容
                int depth = 0;
                std::size_t close = std::string::npos;
                for (std::size_t k = q; k < cur.size(); ++k) {
                    if (cur[k] == '{') ++depth;
                    else if (cur[k] == '}') { if (--depth == 0) { close = k; break; } }
                }
                if (close == std::string::npos) { cur.erase(p, cmd.size()); again = true; break; }
                cur = cur.substr(0, p) + cur.substr(q + 1, close - q - 1) + cur.substr(close + 1);
            } else {
                cur.erase(p, cmd.size());
            }
            again = true;
            break;
        }
    }
    return cur;
}

/**
 * 科学计数法字面量 → 普通十进制字面量：1e-9 → 0.000000001、1.5E2 → 150。
 *
 * 为什么非做不可：引擎自己的解析器不认科学计数法，而 `e` 又恰好是自然常数，
 * 于是 `1e-9` 被读成 `1*e-9` = e − 9 ≈ **−6.2817** —— 一个不报错的错答案；
 * `1e3` 则报「未提供变量 'e3'」这种跟真实原因完全无关的信息。
 * 原版走 sympy，`1e-9` 就是 1e-9，所以这是移植引入的回归。
 *
 * 只在满足下面全部条件时才改写（否则宁可不动）：
 *   · 数字字面量（可带小数点）紧接 `e`/`E`；
 *   · `e` 后面是可选正负号 + 至少一位数字（`1e`、`2ex` 这类不碰）；
 *   · 该数字的**前一个字符不是字母、数字、下划线或点**，即它确实是一个新字面量
 *     （`xe-9`、`x1e-9` 这种不碰，避免把变量名拆坏）。
 * 改写是**纯字符串十进制平移**，不经过 double，所以舍入行为与原字面量一致。
 */
inline std::string scientific_notation_to_decimal(const std::string& s) {
    const auto is_digit = [](char c) { return c >= '0' && c <= '9'; };
    const auto prev_blocks = [](char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') ||
               (c >= 'A' && c <= 'Z') || c == '_' || c == '.';
    };
    std::string out;
    out.reserve(s.size());
    std::size_t i = 0;
    while (i < s.size()) {
        const bool starts_literal =
            is_digit(s[i]) && (out.empty() || !prev_blocks(out.back()));
        if (!starts_literal) {
            out.push_back(s[i++]);
            continue;
        }
        // 1) 取数字字面量：整数部分[.小数部分]
        const std::size_t lit_begin = i;
        std::string int_part;
        while (i < s.size() && is_digit(s[i])) int_part.push_back(s[i++]);
        std::string frac_part;
        if (i < s.size() && s[i] == '.') {
            ++i;
            while (i < s.size() && is_digit(s[i])) frac_part.push_back(s[i++]);
        }
        // 2) 看是否紧跟 e/E + 指数
        if (i < s.size() && (s[i] == 'e' || s[i] == 'E')) {
            std::size_t j = i + 1;
            int exp_sign = 1;
            if (j < s.size() && (s[j] == '+' || s[j] == '-')) {
                if (s[j] == '-') exp_sign = -1;
                ++j;
            }
            std::size_t digits_begin = j;
            long long exp_val = 0;
            while (j < s.size() && is_digit(s[j])) {
                if (exp_val < 1000000) exp_val = exp_val * 10 + (s[j] - '0');
                ++j;
            }
            if (j > digits_begin && !int_part.empty()) {
                // 确实是指数形式 → 十进制平移
                exp_val *= exp_sign;
                const std::string digits = int_part + frac_part;
                const long long point =
                    static_cast<long long>(int_part.size()) + exp_val;
                std::string ip, fp;
                if (point <= 0) {
                    ip = "0";
                    fp = std::string(static_cast<std::size_t>(-point), '0') + digits;
                } else if (point >= static_cast<long long>(digits.size())) {
                    ip = digits + std::string(
                             static_cast<std::size_t>(point) - digits.size(), '0');
                    fp = "";
                } else {
                    ip = digits.substr(0, static_cast<std::size_t>(point));
                    fp = digits.substr(static_cast<std::size_t>(point));
                }
                // 去掉整数部分的前导零、小数部分的后导零
                std::size_t nz = ip.find_first_not_of('0');
                ip = (nz == std::string::npos) ? "0" : ip.substr(nz);
                while (!fp.empty() && fp.back() == '0') fp.pop_back();
                out += ip;
                if (!fp.empty()) { out.push_back('.'); out += fp; }
                i = j;
                continue;
            }
        }
        // 不是指数形式 → 原样搬回
        out.append(s, lit_begin, i - lit_begin);
    }
    return out;
}

/**
 * 规范化数学输入。
 *
 * 处理顺序很重要：先还原 LaTeX 命令（它们需要花括号承载参数），
 * 再把剩下的花括号当普通括号，最后做字符映射。
 */
inline Prepared normalize(const std::string& raw) {
    Prepared out;
    // ── 第 0 步：去掉 LaTeX 的排版指令 \left \right \, \; \! 与前后空白 ──
    std::string s = unwrap_wrapper_commands(raw);
    {
        static const char* kDrop[] = {"\\left", "\\right", "\\,", "\\;", "\\!",
                                      "\\quad", "\\qquad", "\\displaystyle"};
        bool dropped = false;
        for (const char* d : kDrop) {
            std::string needle(d);
            std::size_t p = 0;
            while ((p = s.find(needle, p)) != std::string::npos) {
                s.erase(p, needle.size());
                dropped = true;
            }
        }
        if (dropped) detail::note(out.notes, "去掉了 LaTeX 排版指令（\\left \\right 等）");
    }

    // ── 第 1 步：LaTeX 命令 → 引擎语法（需要读花括号参数，故用码点扫描）──
    {
        auto cps = detail::utf8_decode(s);
        std::string t;
        bool used_latex = false;

        // 从位置 i 的 '{' 开始取配对内容（支持嵌套）
        const auto take_group = [&](std::size_t& i, std::string& dst) -> bool {
            if (i >= cps.size() || cps[i] != '{') return false;
            int depth = 0;
            std::size_t j = i;
            std::string inner;
            for (; j < cps.size(); ++j) {
                if (cps[j] == '{') { ++depth; if (depth == 1) continue; }
                else if (cps[j] == '}') { --depth; if (depth == 0) break; }
                // 把码点按 UTF-8 重新编码（只处理 ASCII 与原样回写）
                if (cps[j] < 0x80) inner.push_back(static_cast<char>(cps[j]));
                else if (cps[j] < 0x800) {
                    inner.push_back(static_cast<char>(0xC0 | (cps[j] >> 6)));
                    inner.push_back(static_cast<char>(0x80 | (cps[j] & 0x3F)));
                } else if (cps[j] < 0x10000) {
                    inner.push_back(static_cast<char>(0xE0 | (cps[j] >> 12)));
                    inner.push_back(static_cast<char>(0x80 | ((cps[j] >> 6) & 0x3F)));
                    inner.push_back(static_cast<char>(0x80 | (cps[j] & 0x3F)));
                }
            }
            if (depth != 0) return false;
            i = j;
            dst = inner;
            return true;
        };

        const auto read_command = [&](std::size_t i, std::string& cmd, std::size_t& after) {
            if (i >= cps.size() || cps[i] != '\\') return false;
            std::size_t j = i + 1;
            std::string name;
            while (j < cps.size() && detail::is_ident_cp(cps[j])) {
                name.push_back(static_cast<char>(cps[j]));
                ++j;
            }
            if (name.empty()) return false;
            cmd = name;
            after = j;
            return true;
        };

        for (std::size_t i = 0; i < cps.size(); ++i) {
            std::string cmd;
            std::size_t after = 0;
            if (read_command(i, cmd, after)) {
                if (cmd == "frac") {
                    std::size_t p = after;
                    std::string a, b;
                    if (take_group(p, a)) {
                        std::size_t q = p + 1;  // 跳过 a 的 '}'
                        if (take_group(q, b)) {
                            t += "((" + a + ")/(" + b + "))";
                            i = q;
                            used_latex = true;
                            continue;
                        }
                    }
                } else if (cmd == "sqrt") {
                    // 支持 \sqrt{x} 与 \sqrt[n]{x}
                    std::size_t p = after;
                    std::string idx, a;
                    bool have_idx = false;
                    if (p < cps.size() && cps[p] == '[') {
                        std::size_t q = p + 1;
                        std::string inner;
                        while (q < cps.size() && cps[q] != ']') {
                            if (cps[q] < 0x80) inner.push_back(static_cast<char>(cps[q]));
                            ++q;
                        }
                        if (q < cps.size()) { idx = inner; have_idx = true; p = q + 1; }
                    }
                    if (take_group(p, a)) {
                        t += have_idx ? ("((" + a + ")^(1/(" + idx + ")))")
                                      : ("sqrt(" + a + ")");
                        i = p;
                        used_latex = true;
                        continue;
                    }
                } else if (cmd == "cdot" || cmd == "times" || cmd == "ast") {
                    t += "*";
                    i = after - 1;
                    used_latex = true;
                    continue;
                } else if (cmd == "le" || cmd == "leq") {
                    t += "<="; i = after - 1; used_latex = true; continue;
                } else if (cmd == "ge" || cmd == "geq") {
                    t += ">="; i = after - 1; used_latex = true; continue;
                } else if (cmd == "ne" || cmd == "neq") {
                    t += "!="; i = after - 1; used_latex = true; continue;
                } else if (cmd == "div") {
                    t += "/";
                    i = after - 1;
                    used_latex = true;
                    continue;
                } else if (cmd == "operatorname" || cmd == "mathrm" || cmd == "mathit" ||
                           cmd == "text" || cmd == "placeholder" || cmd == "mathord") {
                    // 正常情况下已被前置展开处理；此处兜底（参数取值失败时跳过）
                    std::size_t p = after;
                    std::string inner;
                    if (take_group(p, inner)) {
                        t += inner;
                        i = p;
                        used_latex = true;
                        continue;
                    }
                } else {
                    // \sin^{-1} 之类：教材与 MathLive 都表示反函数，必须整体识别，
                    // 否则会被解析成 (sin x)⁻¹ —— 意思完全不同。
                    std::string inv;
                    if (cmd == "sin") inv = "asin";
                    else if (cmd == "cos") inv = "acos";
                    else if (cmd == "tan") inv = "atan";
                    if (!inv.empty() && after < cps.size() && cps[after] == '^') {
                        std::size_t p = after + 1;
                        std::string exp;
                        if (take_group(p, exp) && (exp == "-1" || exp == "- 1")) {
                            t += inv;
                            i = p;
                            used_latex = true;
                            continue;
                        }
                    }
                    if (cmd == "exponentialE") { t += "e"; i = after - 1; used_latex = true; continue; }
                    if (cmd == "imaginaryI") { t += "i"; i = after - 1; used_latex = true; continue; }
                    // \sin \cos \pi \theta \ln … → 去掉反斜杠，交给解析器
                    t += cmd;
                    i = after - 1;
                    used_latex = true;
                    continue;
                }
            }
            // 花括号统一当圆括号（LaTeX 里多为分组）
            if (cps[i] == '{') { t += '('; used_latex = true; continue; }
            if (cps[i] == '}') { t += ')'; used_latex = true; continue; }
            if (cps[i] < 0x80) t.push_back(static_cast<char>(cps[i]));
            else if (cps[i] < 0x800) {
                t.push_back(static_cast<char>(0xC0 | (cps[i] >> 6)));
                t.push_back(static_cast<char>(0x80 | (cps[i] & 0x3F)));
            } else if (cps[i] < 0x10000) {
                t.push_back(static_cast<char>(0xE0 | (cps[i] >> 12)));
                t.push_back(static_cast<char>(0x80 | ((cps[i] >> 6) & 0x3F)));
                t.push_back(static_cast<char>(0x80 | (cps[i] & 0x3F)));
            } else {
                t.push_back(static_cast<char>(0xF0 | (cps[i] >> 18)));
                t.push_back(static_cast<char>(0x80 | ((cps[i] >> 12) & 0x3F)));
                t.push_back(static_cast<char>(0x80 | ((cps[i] >> 6) & 0x3F)));
                t.push_back(static_cast<char>(0x80 | (cps[i] & 0x3F)));
            }
        }
        s = t;
        if (used_latex) detail::note(out.notes, "把 LaTeX 写法转换成了引擎语法（\\frac → /、\\sqrt → sqrt、\\sin → sin 等）");
    }

    // ── 第 2 步：字符映射（全角、Unicode 数学符号）──
    {
        std::string t;
        bool fullwidth = false, symbol = false, greek = false;
        for (std::uint32_t cp : detail::utf8_decode(s)) {
            bool alnum = false;
            const std::string rep = detail::map_codepoint(cp, alnum);
            if (!rep.empty()) {
                t += rep;
                if (alnum) fullwidth = true;
                else if (rep == "pi" || rep == "theta") greek = true;
                else symbol = true;
                continue;
            }
            // 原样回写
            if (cp < 0x80) t.push_back(static_cast<char>(cp));
            else if (cp < 0x800) {
                t.push_back(static_cast<char>(0xC0 | (cp >> 6)));
                t.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
            } else if (cp < 0x10000) {
                t.push_back(static_cast<char>(0xE0 | (cp >> 12)));
                t.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
                t.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
            } else {
                t.push_back(static_cast<char>(0xF0 | (cp >> 18)));
                t.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
                t.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
                t.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
            }
        }
        s = t;
        if (fullwidth) detail::note(out.notes, "全角字符已转换为半角");
        if (symbol) detail::note(out.notes, "Unicode 数学符号已转换（× · ÷ − ² ≤ π 等）");
        if (greek) detail::note(out.notes, "希腊字母已转换为变量名（π → pi、θ → theta）");
    }

    // ── 第 3 步：压缩空白（不影响语义，但让规范化结果更好读）──
    {
        std::string t;
        bool prev_space = false;
        for (char c : s) {
            const bool sp = (c == ' ' || c == '\t');
            if (sp) {
                if (!prev_space) t.push_back(' ');
                prev_space = true;
            } else {
                t.push_back(c);
                prev_space = false;
            }
        }
        while (!t.empty() && t.front() == ' ') t.erase(t.begin());
        while (!t.empty() && t.back() == ' ') t.pop_back();
        s = t;
    }

    // ── 第 3.5 步：科学计数法 → 十进制字面量 ──
    // 必须在隐式乘法之前：`1e-9` 一旦进了第 4 步，`e` 会被当自然常数、
    // 结果变成 e−9（静默错答案，还不报错）。
    {
        const std::string t = scientific_notation_to_decimal(s);
        if (t != s) {
            s = t;
            detail::note(out.notes, "科学计数法已改写成十进制字面量（如 1e-9 → 0.000000001）");
        }
    }

    // ── 第 3.6 步：√x → sqrt(x)、|x| → abs(x) ──    // 引擎自己的解析器认得 √ 和 |…|，SymEngine（求导/积分/解方程）不认，
    // 于是同一串输入会"绘图能画、求导报 syntax error"。统一成函数写法即可。
    {
        const std::string t = sqrt_fences_to_function(s);
        if (t != s) { s = t; detail::note(out.notes, "√ 已改写成 sqrt(...)"); }
    }
    {
        const std::string t = abs_fences_to_function(s);
        if (t != s) { s = t; detail::note(out.notes, "|…| 已改写成 abs(...)"); }
    }

    // ── 第 4 步：隐式乘法 → 显式乘法 ──
    // 学生写的是 2x、(x+1)(x-1)、2sin(x)、πx、\frac{1}{2}x；
    // 引擎自己的解析器认得这些，但 SymEngine（求导/积分/解方程/化简都走它）
    // 只认显式 `*`，于是同一串输入在绘图里能算、在求导里报 syntax error。
    // 在这里统一补上 `*`，两条解析路径就一致了。
    {
        const std::string t = implicit_multiplication(s);
        if (t != s) {
            s = t;
            detail::note(out.notes, "隐式乘法已写成显式（如 2x → 2*x）");
        }
    }

    out.text = s;
    return out;
}

/**
 * 把隐式乘法写成显式乘法。规则尽量保守（宁可不动，也不猜）：
 *   · 只在这些邻接处插入 `*`：
 *       数字 → 字母/`(`/`[`/`|`/`√`        例：2x、2(x+1)、2|x|、2√x
 *       `)`/`]`/`|` → 字母/数字/`(`/`√`    例：(x+1)(x-1)、(x+1)2、|x|y
 *       字母 → `(`（且该字母不是函数名）     例：x(x+1)；但 sin(x) 不插
 *       空白分隔的两个因子                   例："x y" → x*y、"2 x" → 2*x
 *       幂之后紧跟因子                       例：x^2y → x^2*y（原来被读成 x^(2y)）
 *   · 不插入的情况：
 *       函数名后紧跟 `(`（sin(x)、sqrt(x)…），否则会破坏函数调用
 *       `/` 右侧的因子（1/2x 保持 1/(2x)：这是教材上分数条的写法，改动会改变语义）
 *       数字与数字之间（"2 3" 视为笔误，不做乘法）
 *       `xy` 这种连写（引擎把多字母标识符当作一个变量名，维持原样）
 */
inline bool is_function_name(const std::string& w) {    static const char* names[] = {
        "sin", "cos", "tan", "tg", "cot", "ctg", "sec", "csc", "asin", "acos",
        "atan", "acot", "asec", "acsc", "arcsin", "arccos", "arctan",
        "arccot", "arcsec", "arccsc", "sinh", "cosh", "tanh", "asinh",
        "acosh", "atanh", "ln", "log",
        "log2", "log10", "lg", "exp", "sqrt", "cbrt", "abs", "sign",
        "floor", "ceil", "round", "min", "max", "gamma", "loggamma", "zeta",
        "erf", "erfc", "factorial", "polygamma", "psi", "digamma", "beta",
        "lambertw", "lambertw0", "w0", "hurwitz_zeta", "acot", "arccot",
        "asec", "arcsec", "acsc", "arccsc", "asinh", "acosh", "atanh",
    };
    for (const char* n : names)
        if (w == n) return true;
    return false;
}

/** √x → sqrt(x)、√(x+1) → sqrt(x+1)、√2 → sqrt(2) */
inline std::string sqrt_fences_to_function(const std::string& s) {
    const std::string kSqrt = "\xE2\x88\x9A";
    if (s.find(kSqrt) == std::string::npos) return s;
    std::string out;
    for (std::size_t i = 0; i < s.size();) {
        if (s.compare(i, kSqrt.size(), kSqrt) == 0) {
            std::size_t j = i + kSqrt.size();
            if (j < s.size() && s[j] == '(') { out += "sqrt"; i = j; continue; }
            std::size_t k = j;
            if (k < s.size() && (std::isalnum(static_cast<unsigned char>(s[k])) || s[k] == '.')) {
                while (k < s.size() && (std::isalnum(static_cast<unsigned char>(s[k])) || s[k] == '.' || s[k] == '_')) ++k;
            }
            if (k > j) { out += "sqrt(" + s.substr(j, k - j) + ")"; i = k; continue; }
        }
        out += s[i++];
    }
    return out;
}

/** |x| → abs(x)（只处理不嵌套的情形，嵌套时原样保留交给引擎自己的解析器） */
inline std::string abs_fences_to_function(const std::string& s) {
    if (s.find('|') == std::string::npos) return s;
    std::string out;
    std::size_t i = 0;
    while (i < s.size()) {
        if (s[i] != '|') { out += s[i++]; continue; }
        std::size_t p = out.size();
        while (p > 0 && out[p - 1] == ' ') --p;
        const char prev = p > 0 ? out[p - 1] : '\0';
        // 不要求前面是运算符：2|x|、|x|y 都是"绝对值当因子"的常见写法，
        // 真正的判据是**后面有没有同层级的闭合 |**（下面找得到才改写）
        (void)prev;
        std::size_t j = i + 1;
        int depth = 0;
        bool nested = false;
        for (; j < s.size(); ++j) {
            if (s[j] == '(' || s[j] == '[') ++depth;
            else if (s[j] == ')' || s[j] == ']') --depth;
            else if (s[j] == '|' && depth == 0) break;
            else if (s[j] == '|') nested = true;
        }
        if (j >= s.size() || nested) { out += s[i++]; continue; }
        out += "abs(" + s.substr(i + 1, j - i - 1) + ")";
        i = j + 1;
    }
    return out;
}

/**
 * 这个词要"整体保留"吗：函数名、常量名、希腊字母名都不能拆。
 * 例：pi 是圆周率，theta 是 θ，oo 是无穷，拆开就错了。
 */
inline bool is_known_word(const std::string& w);
/** 词汇表里的名字（常量 pi/oo/inf 与希腊字母名）——**不含函数名**。
 *  切词时必须用这个：is_known_word 同时包含函数名，
 *  拿它判断"是不是希腊字母同名"会把 sin 也当成变量（实测踩过）。 */
inline bool is_word_name(const std::string& w) {
    static const char* words[] = {
        "pi", "oo", "inf", "nan", "theta", "alpha", "beta", "gamma", "delta",
        "epsilon", "varepsilon", "zeta", "eta", "lambda", "mu", "nu", "xi",
        "rho", "sigma", "tau", "upsilon", "phi", "varphi", "chi", "psi", "omega",
    };
    for (const char* x : words)
        if (w == x) return true;
    return false;
}

inline bool is_known_word(const std::string& w) {
    return is_function_name(w) || is_word_name(w);
}

/** 词尾是不是函数名（xsin → x*sin；sinx 由前缀规则处理） */
inline std::size_t function_suffix_length(const std::string& w) {
    static const char* fns[] = {
        "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "sin", "cos",
        "tan", "tg", "cot", "ctg", "sec", "csc", "asin", "acos", "atan",
        "acot", "asec", "acsc", "arccot", "arcsec", "arccsc", "asinh", "acosh",
        "atanh", "log10", "log2", "digamma", "erf", "erfc", "beta",
        "log", "ln", "lg", "exp", "sqrt", "cbrt", "abs", "sign", "gamma", "zeta",
    };
    for (const char* fn : fns) {
        const std::size_t n = std::string(fn).size();
        if (w.size() > n && w.compare(w.size() - n, n, fn) == 0) return n;
    }
    return 0;
}
/** 词切分：函数名/常量名（最长优先）＋单字母变量 */
namespace detail {

/** 函数别名 → 规范名（SymEngine 与教材解析器都认的名字）。
 *  实测 SymEngine 不认 tg/ctg（会静默当成未知函数），必须换名。 */
inline std::string canonical_fn_name(const std::string& w) {
    if (w == "tg") return "tan";
    if (w == "ctg") return "cot";
    return w;
}

struct Piece { bool fn; std::string text; };

/**
 * 把一个连写标识符切成"函数名 / 常量名 / 单字母变量"。
 *   sinx      → sin | x          （不是变量 sinx）
 *   xsinx     → x | sin | x
 *   sinxcosx  → sin | x | cos | x
 *   xe        → x | e
 *   xy        → x | y
 *   pi/theta  → 整词保留（常量名/希腊字母名）
 *   XA/a1/x2  → 整词保留（含大写或数字，可能是矩阵/下标变量，不拆）
 * 既是希腊字母名又是函数名的（beta/gamma/zeta/psi）按**变量**处理，
 * 只有后面紧跟 `(` 时才是调用（gamma(x)）。
 */
inline std::vector<Piece> segment_word(const std::string& w) {
    std::vector<Piece> out;
    // 既是希腊字母名又是函数名的（beta/gamma/zeta/psi）按变量处理，
    // 只有后面紧跟 `(` 时才是调用（gamma(x)）——由补乘号那一步保证。
    if (is_function_name(w) && is_word_name(w)) { out.push_back(Piece{false, w}); return out; }
    if (is_function_name(w)) { out.push_back(Piece{true, canonical_fn_name(w)}); return out; }
    if (is_word_name(w)) { out.push_back(Piece{false, w}); return out; }

    // 以函数名开头（可能紧跟着写参数）：sin2x → sin|2|x、sqrt2 → sqrt|2、
    // cos2x、ln2x、sinhx、asinx、arcsinx、absx —— 这类必须切开，
    // 否则整词会被当成一个变量（正是"sin 当变量"的同族错误）。
    std::size_t fn_prefix = 0;
    for (std::size_t n = w.size(); n >= 2; --n) {
        if (n >= w.size()) continue;   // 整词是函数名的情况上面已经处理过
        const std::string cand = w.substr(0, n);
        if (is_function_name(cand) && !is_word_name(cand)) { fn_prefix = n; break; }
    }
    if (fn_prefix == 0) {
        // 不含函数名开头：含大写或数字的整词保留（XA、a1、x2 可能是矩阵/下标变量）
        for (char ch : w)
            if (ch < 'a' || ch > 'z') { out.push_back(Piece{false, w}); return out; }
    } else {
        out.push_back(Piece{true, canonical_fn_name(w.substr(0, fn_prefix))});
    }

    // 剩余部分：数字串与字母/常量名轮流切
    std::size_t i = fn_prefix;
    while (i < w.size()) {
        if (w[i] >= '0' && w[i] <= '9') {
            std::size_t j = i;
            while (j < w.size() && w[j] >= '0' && w[j] <= '9') ++j;
            out.push_back(Piece{false, w.substr(i, j - i)});
            i = j;
            continue;
        }
        std::size_t fn_len = 0, word_len = 0;
        for (std::size_t n = w.size() - i; n >= 2; --n) {
            const std::string cand = w.substr(i, n);
            if (!fn_len && is_function_name(cand) && !is_word_name(cand)) { fn_len = n; break; }
        }
        for (std::size_t n = w.size() - i; n >= 2; --n) {
            const std::string cand = w.substr(i, n);
            if (is_word_name(cand)) { word_len = n; break; }
        }
        const std::size_t take = fn_len ? fn_len : (word_len ? word_len : 1);
        const std::string piece = w.substr(i, take);
        out.push_back(Piece{fn_len != 0, fn_len ? canonical_fn_name(piece) : piece});
        i += take;
    }
    return out;
}

/** 输出里不允许出现"裸函数名"（函数名后面没有 `(`）——那正是把 sin 当变量的病根。
 *
 *  例外：**整串就是一个函数名**时放行。引擎里有把函数名当参数的接口
 *  （如 trig_periodicity 的 func: "sin"），那不是在写表达式；
 *  真正的病是 `sin x` / `8x sin x` 这类**表达式里**的函数名被当成变量。 */
inline void require_calls_have_parens(const std::string& text) {
    for (std::size_t i = 0; i < text.size();) {
        const unsigned char c = static_cast<unsigned char>(text[i]);
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_')) { ++i; continue; }
        std::size_t j = i;
        while (j < text.size()) {
            const unsigned char d = static_cast<unsigned char>(text[j]);
            if ((d >= 'a' && d <= 'z') || (d >= 'A' && d <= 'Z') || d == '_' ||
                (d >= '0' && d <= '9')) ++j;
            else break;
        }
        const std::string w = text.substr(i, j - i);
        const bool whole = (i == 0 && j == text.size());
        if (is_function_name(w) && !is_word_name(w) && !whole &&
            (j >= text.size() || text[j] != '('))
            throw std::runtime_error("函数 " + w + " 后面缺少自变量（写 " + w + " x 或 " + w + "(x)）");
        i = j;
    }
}

}  // namespace detail

/**
 * 教材写法 → 显式语法。
 *
 * 目标：**输出的文本对任何解析器都只有一种读法**，且本函数**幂等**（跑两遍结果相同）。
 *
 * 为什么必须这样（实测的静默错算）：
 *   引擎里有两条解析路径——教材解析器（parser_lib，负责求值/绘图）与
 *   SymEngine（负责求导/积分/解方程/化简）。旧版在这里只补 `*`，
 *   碰到"函数名后跟空格"就靠"不插乘号"假装那是函数调用，于是：
 *       sin x      → sinx      教材解析器读成 sin(x)（对），SymEngine 读成变量 sinx（错）
 *       8x sin x   → 8*x*sinx  d/dx 输出 8*sinx —— 看着像结果，其实是错的
 *       8xsinx     → 8*x*s*i*n*x（把 sin 拆成 s·i·n）
 *       sinxcosx   → sin(xcosx)
 *       1/2x       两条路径连语义都不一致（0.5x vs 1/(2x)）
 *   于是"界面显示的归一化文本"和"引擎真正计算的文本"也不一致（菜谱跑两遍才碰巧对）。
 *
 * 现在的规则：
 *   · 函数名一律补全括号：sin x → sin(x)、sin2x → sin(2*x)、sinx → sin(x)
 *   · 函数名的幂：sin^2x → (sin(x))^2（SymEngine 认不出 sin^2x）
 *   · 连写字母按"函数名/常量名（最长优先）＋单字母变量"切分：
 *       xsinx → x*sin(x)、8xsinx → 8*x*sin(x)、sinxcosx → sin(x)*cos(x)、xe → x*e
 *   · 隐式乘法一律补 `*`：2x、x(x+1)、(x+1)(x-1)、x^2y
 *   · `/` 后面连写的一串因子整体作分母：1/2x → 1/(2*x)（教材分数条写法）
 *   · 幂统一用 `^`：输入里的 `**` 也会被归一成 `^`（本项目只用 `^`，界面不再做转换）
 *   · 无法解释的（函数名后面没有自变量，如孤立的 `sin`）**明确报错**，不猜
 */
inline std::string implicit_multiplication(const std::string& s) {
    enum Kind { NUM, IDENT, FN, OPEN, CLOSE, PREFIX, OP };
    struct Tok { Kind kind; std::string text; bool spaced; };

    // ── ① 词法扫描 ──
    std::vector<Tok> raw;
    for (std::size_t i = 0; i < s.size();) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        if (c == ' ' || c == '\t') { ++i; continue; }
        const bool spaced = (i > 0) && (s[i - 1] == ' ' || s[i - 1] == '\t');
        if (c >= '0' && c <= '9') {
            std::size_t j = i;
            while (j < s.size() && (std::isdigit(static_cast<unsigned char>(s[j])) || s[j] == '.')) ++j;
            // 科学计数法：1e-6、2.5e3 是一个数
            if (j < s.size() && (s[j] == 'e' || s[j] == 'E')) {
                std::size_t k = j + 1;
                if (k < s.size() && (s[k] == '+' || s[k] == '-')) ++k;
                std::size_t d = k;
                while (d < s.size() && std::isdigit(static_cast<unsigned char>(s[d]))) ++d;
                if (d > k) j = d;
            }
            raw.push_back(Tok{NUM, s.substr(i, j - i), spaced});
            i = j;
        } else if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_' || c >= 0x80) {
            std::size_t j = i;
            while (j < s.size()) {
                const unsigned char d = static_cast<unsigned char>(s[j]);
                if ((d >= 'a' && d <= 'z') || (d >= 'A' && d <= 'Z') || d == '_' ||
                    (d >= '0' && d <= '9') || d >= 0x80) ++j;
                else break;
            }
            raw.push_back(Tok{IDENT, s.substr(i, j - i), spaced});
            i = j;
        } else if (c == ')' || c == ']') {
            raw.push_back(Tok{CLOSE, std::string(1, s[i]), spaced}); ++i;
        } else if (c == '(' || c == '[') {
            raw.push_back(Tok{OPEN, std::string(1, s[i]), spaced}); ++i;
        } else if (c == '|') {
            // `|` 既是绝对值左界也是右界：前面是因子就当右界
            const bool after_factor = !raw.empty() &&
                (raw.back().kind == NUM || raw.back().kind == IDENT || raw.back().kind == CLOSE);
            raw.push_back(Tok{after_factor ? CLOSE : PREFIX, "|", spaced}); ++i;
        } else if (c == '*' && i + 1 < s.size() && s[i + 1] == '*') {
            // `**` 与 `^` 是同一个幂算符。**统一成 `^`**（本项目只使用 `^`）：
            // 界面不再做 ^ → ** 的转换，但用户/旧脚本仍可能写 **，而 SymEngine 的
            // 打印器输出也是 ** —— 这里合并成一个算符，后面所有幂的判断只需认 `^`。
            raw.push_back(Tok{OP, "^", spaced}); i += 2;
        } else {
            raw.push_back(Tok{OP, std::string(1, s[i]), spaced}); ++i;
        }
    }

    // ── ② 长标识符切分：函数名/常量名（最长优先）＋单字母变量 ──
    std::vector<Tok> toks;
    for (const Tok& t : raw) {
        if (t.kind != IDENT) { toks.push_back(t); continue; }
        for (const auto& p : detail::segment_word(t.text))
            toks.push_back(Tok{p.fn ? FN : IDENT, p.text, t.spaced});
    }

    // ── ③ 函数名 → 显式调用：sin x → sin(x)、sin^2x → (sin(x))^2 ──
    std::vector<Tok> calls;
    for (std::size_t k = 0; k < toks.size(); ++k) {
        const Tok& cur = toks[k];
        if (cur.kind != FN) { calls.push_back(cur); continue; }
        if (k + 1 < toks.size() && toks[k + 1].kind == OPEN) {   // 本来就带括号
            calls.push_back(cur);
            continue;
        }
        // 函数名的幂：先取指数，再取自变量
        bool powered = false;
        std::vector<Tok> exponent;
        std::size_t p = k + 1;
        if (p < toks.size() && toks[p].kind == OP && toks[p].text == "^") {
            std::size_t e = p + 1;
            if (e < toks.size() && toks[e].kind == OPEN) {
                int depth = 0;
                std::size_t q = e;
                for (; q < toks.size(); ++q) {
                    if (toks[q].kind == OPEN) ++depth;
                    else if (toks[q].kind == CLOSE) { --depth; if (depth == 0) { ++q; break; } }
                }
                if (depth != 0) throw std::runtime_error("括号没有配对：" + s);
                for (std::size_t q2 = e; q2 < q; ++q2) exponent.push_back(toks[q2]);
                e = q;
            } else if (e < toks.size() && (toks[e].kind == NUM || toks[e].kind == IDENT)) {
                exponent.push_back(toks[e]);
                ++e;
            } else {
                throw std::runtime_error("幂次写法看不懂：" + s);
            }
            p = e;
            powered = true;
        }
        // 自变量：紧随其后的因子串（遇到 + - * / 、右括号、另一个函数名就结束；
        // `^` 归属它前面的因子，所以 sin x^2 是 sin(x^2)）
        const std::size_t arg_begin = p;
        std::size_t arg_end = p;
        while (arg_end < toks.size()) {
            const Tok& t = toks[arg_end];
            if (t.kind == FN) break;                                  // sin x cos x → 自变量只到 x
            if (t.kind == CLOSE) break;
            if (t.kind == OP && t.text != "^") break;                 // + - * / 结束
            if (t.kind == PREFIX) break;
            ++arg_end;
        }
        if (arg_end == arg_begin) {
            // 整串就是一个函数名（如 trig_periodicity 的 func: "sin"）：那是"函数名参数"，
            // 不是在写表达式，原样放行。真正的病是**表达式里**出现的裸函数名。
            if (calls.empty() && k == 0 && k + 1 == toks.size()) {
                calls.push_back(cur);
                continue;
            }
            throw std::runtime_error("函数 " + cur.text + " 后面缺少自变量（写 " + cur.text +
                                     " x 或 " + cur.text + "(x)）");
        }
        if (powered) calls.push_back(Tok{OPEN, "(", false});
        calls.push_back(Tok{OPEN, cur.text + "(", false});            // 整个 "sin(" 当作一个左括号
        for (std::size_t q = arg_begin; q < arg_end; ++q) calls.push_back(toks[q]);
        calls.push_back(Tok{CLOSE, ")", false});
        if (powered) {
            calls.push_back(Tok{CLOSE, ")", false});
            calls.push_back(Tok{OP, "^", false});
            for (const Tok& e : exponent) calls.push_back(e);
        }
        k = arg_end - 1;                                              // 自变量已消费
    }

    // ── ④ `/` 后面连写的因子串整体作分母：1/2x → 1/(2*x) ──
    std::vector<Tok> grouped;
    for (std::size_t k = 0; k < calls.size(); ++k) {
        if (!(calls[k].kind == OP && calls[k].text == "/")) { grouped.push_back(calls[k]); continue; }
        grouped.push_back(calls[k]);
        // 收集紧随其后的因子串（只认"连写"的：中间不能有空格）
        const auto is_factor = [](Kind k) { return k == NUM || k == IDENT || k == OPEN; };
        std::size_t j = k + 1;
        std::size_t factors = 0, end = j;
        bool fused = true;
        while (end < calls.size()) {
            const Tok& t = calls[end];
            if (t.kind == OP && t.text == "^") { ++end; continue; }     // 幂归属前一个因子
            if (!is_factor(t.kind)) break;
            if (t.spaced) { fused = false; break; }
            ++factors;
            if (t.kind == OPEN) {
                // 括号组整体算**一个**因子（否则 1/(2*x) 会被再包一层括号，归一化不幂等）
                int depth = 0;
                for (; end < calls.size(); ++end) {
                    if (calls[end].kind == OPEN) ++depth;
                    else if (calls[end].kind == CLOSE) { --depth; if (depth == 0) { ++end; break; } }
                }
                continue;
            }
            ++end;
        }
        if (factors >= 2 && fused) {
            grouped.push_back(Tok{OPEN, "(", false});
            for (std::size_t q = j; q < end; ++q) grouped.push_back(calls[q]);
            grouped.push_back(Tok{CLOSE, ")", false});
            k = end - 1;
        }
    }

    // ── ⑤ 因子之间补 `*` ──
    std::string out;
    for (std::size_t k = 0; k < grouped.size(); ++k) {
        const Tok& cur = grouped[k];
        if (k > 0) {
            const Tok& prev = grouped[k - 1];
            const bool prev_factor = prev.kind == NUM || prev.kind == IDENT || prev.kind == CLOSE;
            const bool cur_factor = cur.kind == NUM || cur.kind == IDENT || cur.kind == OPEN ||
                                    cur.kind == PREFIX || cur.kind == FN;
            bool need = prev_factor && cur_factor;
            // 函数名紧跟 `(` 是调用，不是乘法（希腊字母名 gamma(x) 走这条）
            if (need && cur.kind == OPEN && prev.kind == IDENT && is_function_name(prev.text)) need = false;
            // "2 3" 当笔误：不在两个数字之间补乘号（否则 2 3 静默变成 6）
            if (prev.kind == NUM && cur.kind == NUM) need = false;
            if (need) out += "*";
        }
        out += cur.text;
    }
    detail::require_calls_have_parens(out);
    return out;
}

// ── 方程写法："左 = 右" ────────────────────────────────────────────────────
//
// 课本里 x^2+2x+1=0 是一个**完整对象**；而表达式解析器只吃表达式。
// 把"两边"整理成"左边减右边"是**表达式的改写**，所以归引擎层做，
// 而不是让界面把字符串劈成两半——界面不该懂数学，也不该决定 =0 的语义。
//
// 故意保守（宁可报错也不猜）：
//   · 只认一个等号；== <= >= != 里的等号不算（那是比较，不是方程）
//   · 某一侧为空 → 报错（"=0"、"x^2=" 是残句）
//   · 两个以上等号 → 报错（不支持 a=b=c 连等）
inline bool is_equation(const std::string& s) {
    std::size_t n = 0;
    for (std::size_t i = 0; i < s.size(); ++i) {
        if (s[i] != '=') continue;
        const char prev = i > 0 ? s[i - 1] : '\0';
        const char next = i + 1 < s.size() ? s[i + 1] : '\0';
        if (prev == '<' || prev == '>' || prev == '!' || prev == '=') continue;
        if (next == '=') continue;
        ++n;
    }
    return n > 0;
}

inline bool equation_to_zero(std::string& text, std::string& error) {
    error.clear();
    const auto trim = [](const std::string& v) {
        std::size_t a = 0, b = v.size();
        while (a < b && std::isspace(static_cast<unsigned char>(v[a]))) ++a;
        while (b > a && std::isspace(static_cast<unsigned char>(v[b - 1]))) --b;
        return v.substr(a, b - a);
    };

    std::vector<std::size_t> hits;
    for (std::size_t i = 0; i < text.size(); ++i) {
        if (text[i] != '=') continue;
        const char prev = i > 0 ? text[i - 1] : '\0';
        const char next = i + 1 < text.size() ? text[i + 1] : '\0';
        if (prev == '<' || prev == '>' || prev == '!' || prev == '=') continue;
        if (next == '=') continue;
        hits.push_back(i);
    }
    if (hits.empty()) return true;   // 不是方程：原样通过

    if (hits.size() > 1) {
        error = "一个方程只能有一个等号（不支持 a=b=c 这种连等）：" + text;
        return false;
    }
    const std::string lhs = trim(text.substr(0, hits[0]));
    const std::string rhs = trim(text.substr(hits[0] + 1));
    if (lhs.empty() || rhs.empty()) {
        error = "等号两侧都不能为空（输入：" + text + "）。请写成 x^2+2x+1=0 这样的完整方程。";
        return false;
    }
    text = "(" + lhs + ") - (" + rhs + ")";
    return true;
}

}  // namespace mf::input
