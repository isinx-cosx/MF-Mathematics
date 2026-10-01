// parser_lib.h — 数学表达式解析器 + 求值 + 符号微分(仅头文件)。
//
// 从 parser.cpp 提取并头文件化,供数值计算内核求值 f(x) / f(t,y)。
// 支持:+ - * / **、括号、单变量/多变量、函数 sin cos tan sqrt log exp。
//
// 用法:
//   auto root = mf::expr::parse("x**2 + 1");
//   double v = mf::expr::eval(root.get(), 2.0);      // 5
//   auto d = mf::expr::differentiate(root.get());    // 2*x
//   double dv = mf::expr::eval(d.get(), 2.0);        // 4

#pragma once

#include <cmath>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>

#include "math_input.h"

namespace mf::expr {

// ── 表达式树 ────────────────────────────────────────────────────────────────

enum class NodeType { Number, Variable, Binary, Function };

struct ExprNode {
    NodeType type = NodeType::Number;
    double value = 0.0;
    std::string name;                      // 变量名 / 函数名
    char op = 0;                           // '+','-','*','/','^'
    std::unique_ptr<ExprNode> left, right, arg;
};

namespace detail {

// 节点工厂
inline std::unique_ptr<ExprNode> make_number(double v) {
    auto n = std::make_unique<ExprNode>();
    n->type = NodeType::Number;
    n->value = v;
    return n;
}
inline std::unique_ptr<ExprNode> make_variable(const std::string& name) {
    auto n = std::make_unique<ExprNode>();
    n->type = NodeType::Variable;
    n->name = name;
    return n;
}
inline std::unique_ptr<ExprNode> make_binary(char op, std::unique_ptr<ExprNode> l,
                                             std::unique_ptr<ExprNode> r) {
    auto n = std::make_unique<ExprNode>();
    n->type = NodeType::Binary;
    n->op = op;
    n->left = std::move(l);
    n->right = std::move(r);
    return n;
}
inline std::unique_ptr<ExprNode> make_function(const std::string& name,
                                               std::unique_ptr<ExprNode> a) {
    auto n = std::make_unique<ExprNode>();
    n->type = NodeType::Function;
    n->name = name;
    n->arg = std::move(a);
    return n;
}

inline bool is_digit(char c) { return c >= '0' && c <= '9'; }
inline bool is_letter(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
}
inline bool is_ident_char(char c) { return is_letter(c) || is_digit(c); }
inline bool is_space(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f';
}

/**
 * 函数名 → 规范名（不认识的返回空串）。
 *
 * 同时承担**别名归一**：教科书/中文教材写 tg、ctg，LaTeX 与多数软件写 arcsin，
 * 这里统一映射到规范名，于是 "ctgx"、"arcsinx" 这类写法也能被下面的
 * "函数名前缀切分"识别。放在这里而不是靠字符串替换，是为了避免
 * "把变量名里恰好含 tg 的部分改掉"这类误伤。
 */
inline std::string canonical_function(const std::string& n) {
    // 三角
    if (n == "sin") return "sin";
    if (n == "cos") return "cos";
    if (n == "tan" || n == "tg") return "tan";
    if (n == "cot" || n == "ctg") return "cot";
    if (n == "sec") return "sec";
    if (n == "csc") return "csc";
    // 反三角
    if (n == "asin" || n == "arcsin") return "asin";
    if (n == "acos" || n == "arccos") return "acos";
    if (n == "atan" || n == "arctan") return "atan";
    if (n == "acot" || n == "arccot") return "acot";
    if (n == "asec" || n == "arcsec") return "asec";
    if (n == "acsc" || n == "arccsc") return "acsc";
    // 双曲
    if (n == "sinh") return "sinh";
    if (n == "cosh") return "cosh";
    if (n == "tanh") return "tanh";
    if (n == "asinh") return "asinh";
    if (n == "acosh") return "acosh";
    if (n == "atanh") return "atanh";
    // 指数与对数（ln、lg 是中文教材写法）
    if (n == "exp") return "exp";
    if (n == "ln") return "log";
    if (n == "log") return "log";
    if (n == "lg") return "log10";
    if (n == "log10") return "log10";
    if (n == "log2") return "log2";
    // 根式与其它
    if (n == "sqrt") return "sqrt";
    if (n == "cbrt") return "cbrt";
    if (n == "abs") return "abs";
    if (n == "sign") return "sign";
    if (n == "floor") return "floor";
    if (n == "ceil") return "ceil";
    if (n == "round") return "round";
    if (n == "factorial") return "factorial";   // 阶乘：factorial(n) 与 n! 两种写法
    return std::string();
}

inline bool is_function_name(const std::string& name) {
    return !canonical_function(name).empty();
}

// √ 的 UTF-8 字节序列与"首字节判定"。
// char 有符号是这里最容易写错的地方：'\xE2' 作为 int 是 226，
// 而 s_[pos_] 是 char(-30)，直接比较恒为 false。
inline const std::string kSqrtUtf8 = "\xE2\x88\x9A";
inline bool is_sqrt_head(char c) { return static_cast<unsigned char>(c) == 0xE2; }

/** 数学常量：pi、e（自然对数底）、oo/inf（无穷）。返回 false 表示不是常量名。 */
inline bool constant_value(const std::string& name, double& out) {
    if (name == "pi" || name == "PI") { out = 3.14159265358979323846; return true; }
    if (name == "e") { out = 2.71828182845904523536; return true; }
    // 无穷：归一化把 ∞ 写成 oo（与 limit 的趋近值记号一致），inf/infinity 一并认。
    if (name == "oo" || name == "inf" || name == "infinity" ||
        name == "Inf" || name == "INF") {
        out = std::numeric_limits<double>::infinity();
        return true;
    }
    return false;
}


// ── 递归下降解析器 ──────────────────────────────────────────────────────────

class Parser {
public:
    explicit Parser(const std::string& s) : s_(s), pos_(0) {}

    std::unique_ptr<ExprNode> parse() {
        skip_spaces();
        if (pos_ >= s_.size()) throw_err("空表达式");
        auto root = parse_expr();
        skip_spaces();
        if (pos_ < s_.size()) throw_err("表达式后存在多余字符");
        return root;
    }

private:
    const std::string& s_;
    std::size_t pos_ = 0;
    int abs_open_ = 0;  // |...| 的嵌套深度，用于区分竖线的开与闭

    [[noreturn]] void throw_err(const std::string& msg) const {
        throw std::runtime_error(msg + " (位置 " + std::to_string(pos_) + ")");
    }
    void skip_spaces() {
        while (pos_ < s_.size() && is_space(s_[pos_])) ++pos_;
    }
    char peek() {
        skip_spaces();
        return pos_ < s_.size() ? s_[pos_] : '\0';
    }
    bool starts_with(const std::string& kw) const {
        return s_.compare(pos_, kw.size(), kw) == 0;
    }

    std::unique_ptr<ExprNode> parse_expr() {
        auto left = parse_term();
        for (;;) {
            char c = peek();
            if (c != '+' && c != '-') break;
            ++pos_;
            auto right = parse_term();
            left = make_binary(c, std::move(left), std::move(right));
        }
        return left;
    }

    /** 下一个字符是否能开启一个新的因子（用于隐式乘法判定）。
     *  竖线要区分"开"与"闭"：只有在**不在**绝对值内部时，'|' 才开启新因子
     *  （于是 2|x| 能隐式相乘），否则 |-3| 里闭合的那根竖线会被当成乘法，
     *  接着去找缺失的操作数而报错。 */
    bool starts_factor() {
        const char c = peek();
        if (is_digit(c) || c == '.' || is_letter(c)) return true;
        if (c == '(' || is_sqrt_head(c)) return true;
        if (c == '|' && abs_open_ == 0) return true;
        return false;
    }

    std::unique_ptr<ExprNode> parse_term() {
        auto left = parse_factor();
        for (;;) {
            char c = peek();
            if (c == '*' || c == '/') {
                ++pos_;
                auto right = parse_factor();
                left = make_binary(c, std::move(left), std::move(right));
                continue;
            }
            // 隐式乘法：2x、2pi、2(x+1)、(x+1)(x-1)、x sin(x)、3√x …
            // 教科书语法里这是默认写法，此前完全不支持（2x 直接报"多余字符"）。
            if (starts_factor()) {
                auto right = parse_factor();
                left = make_binary('*', std::move(left), std::move(right));
                continue;
            }
            break;
        }
        return left;
    }
    std::unique_ptr<ExprNode> parse_factor() { return parse_unary(); }
    std::unique_ptr<ExprNode> parse_unary() {
        if (peek() == '-' ) {
            ++pos_;
            auto operand = parse_unary();
            return make_binary('-', make_number(0.0), std::move(operand));
        }
        if (peek() == '+') {  // 一元正号：教科书里很常见（+x、+1）
            ++pos_;
            return parse_unary();
        }
        return parse_power();
    }
    std::unique_ptr<ExprNode> parse_power() {
        auto base = parse_postfix();
        skip_spaces();
        // 幂运算符同时支持 ** 与 ^：前者是程序写法，后者是教科书/LaTeX 写法
        if (starts_with("**")) {
            pos_ += 2;
        } else if (pos_ < s_.size() && s_[pos_] == '^') {
            ++pos_;
        } else {
            return base;
        }
        auto exp = parse_unary();
        return make_binary('^', std::move(base), std::move(exp));
    }
    // 后缀运算符（目前只有阶乘 `!`）：5! → factorial(5)，且可连续（5!! 会自然报溢出）
    std::unique_ptr<ExprNode> parse_postfix() {
        auto node = parse_primary();
        for (;;) {
            skip_spaces();
            if (pos_ < s_.size() && s_[pos_] == '!') {
                ++pos_;
                node = make_function("factorial", std::move(node));
                continue;
            }
            return node;
        }
    }
    std::unique_ptr<ExprNode> parse_primary() {
        char c = peek();
        if (c == '(') {
            ++pos_;
            auto inner = parse_expr();
            skip_spaces();
            if (pos_ >= s_.size() || s_[pos_] != ')') throw_err("缺少右括号 ')'");
            ++pos_;
            return inner;
        }
        // |x| —— 绝对值，教科书写法
        if (c == '|') {
            ++pos_;
            ++abs_open_;
            auto inner = parse_expr();
            skip_spaces();
            if (pos_ >= s_.size() || s_[pos_] != '|') throw_err("缺少配对的竖线 '|'");
            --abs_open_;
            ++pos_;
            return make_function("abs", std::move(inner));
        }
        // √x —— 根号，直接作用于紧随其后的因子。
        // 注意：UTF-8 的 √ 首字节是 0xE2，而 char 在 MSVC 下是**有符号**的，
        // 直接写 c == '\xE2' 会因为符号扩展而永远不相等（实测就是这里漏了），
        // 必须转成 unsigned char 再比。
        if (is_sqrt_head(c) && s_.compare(pos_, kSqrtUtf8.size(), kSqrtUtf8) == 0) {
            pos_ += kSqrtUtf8.size();
            auto inner = parse_unary();
            return make_function("sqrt", std::move(inner));
        }
        if (is_digit(c) || c == '.') return parse_number();
        if (is_letter(c)) return parse_identifier();
        if (c == '\0') throw_err("表达式意外结束(缺少操作数)");
        throw_err(std::string("未预期的字符 '") + c + "'");
    }
    std::unique_ptr<ExprNode> parse_number() {
        const std::size_t start = pos_;
        bool has_digit = false;
        bool has_dot = false;
        while (pos_ < s_.size()) {
            const char c = s_[pos_];
            if (is_digit(c)) {
                has_digit = true;
                ++pos_;
            } else if (c == '.' && !has_dot) {
                has_dot = true;
                ++pos_;
            } else {
                break;
            }
        }
        if (!has_digit) throw_err("无效的数字");
        return make_number(std::stod(s_.substr(start, pos_ - start)));
    }
    /**
     * 标识符 → 函数调用 / 常量 / 变量。
     *
     * 处理三类教科书写法（此前都不支持）：
     *   · 函数名与实参之间无括号、无空格：cosx、lnx、sin2x、ctgx、arcsinx
     *     —— 先按"最长的函数名前缀"切分标识符，再按隐式实参解析；
     *   · 函数后直接跟幂：sin^2x 视为 (sin x)²（教材记法）；
     *   · 常量：pi、e。
     */
    std::unique_ptr<ExprNode> parse_identifier() {
        const std::size_t start = pos_;
        while (pos_ < s_.size() && is_ident_char(s_[pos_])) ++pos_;
        std::string name = s_.substr(start, pos_ - start);

        // ① 整体就是函数名
        std::string fn = canonical_function(name);
        bool is_call = !fn.empty();

        // ② 否则试着"函数名前缀 + 剩余实参"切分（cosx → cos | x）
        if (!is_call) {
            for (std::size_t len = name.size(); len-- > 1;) {
                const std::string cand = canonical_function(name.substr(0, len));
                if (!cand.empty()) {
                    fn = cand;
                    is_call = true;
                    name = name.substr(0, len);
                    pos_ = start + len;  // 回退到剩余实参的起点
                    break;
                }
            }
        }

        if (is_call) {
            skip_spaces();
            // f^2(...) / f^2x —— 教材里的"先取函数值再乘方"
            if (peek() == '^' || starts_with("**")) {
                if (starts_with("**")) pos_ += 2; else ++pos_;
                auto exp = parse_unary();       // 指数（如 2、-1）
                skip_spaces();
                auto arg = parse_function_argument();
                auto f = make_function(fn, std::move(arg));
                return make_binary('^', std::move(f), std::move(exp));
            }
            auto arg = parse_function_argument();
            return make_function(fn, std::move(arg));
        }

        // ③ 常量（pi、e）。
        // 记下名字（Number 节点的 name 默认空着），这样 LaTeX 预览里
        // 显示的是 π 而不是 3.141592654 —— 后者既长又看不出是常数。
        double cv = 0.0;
        if (constant_value(name, cv)) {
            auto n = make_number(cv);
            n->name = (name == "PI") ? std::string("pi") : name;
            return n;
        }

        return make_variable(name);
    }

    /** 函数实参：带括号就取括号内容，否则取一个"隐式因子链"。 */
    std::unique_ptr<ExprNode> parse_function_argument() {
        skip_spaces();
        if (pos_ < s_.size() && s_[pos_] == '(') {
            ++pos_;
            auto inner = parse_expr();
            skip_spaces();
            if (pos_ >= s_.size() || s_[pos_] != ')') throw_err("缺少右括号 ')'");
            ++pos_;
            return inner;
        }
        if (pos_ >= s_.size()) throw_err("函数后缺少实参");
        // 隐式实参：一个一元因子，后接若干**隐式**相乘的因子。
        // 只吃隐式乘法（不吃 *、/），于是 cosx*2 = cos(x)*2，
        // 而 cos2x = cos(2x)，与教材记法一致。
        auto left = parse_unary();
        for (;;) {
            if (!starts_factor()) break;
            auto right = parse_unary();
            left = make_binary('*', std::move(left), std::move(right));
        }
        return left;
    }
};

}  // namespace detail

// ── 解析 ────────────────────────────────────────────────────────────────────

inline std::unique_ptr<ExprNode> parse(const std::string& s) {
    // 统一在这里做输入规范化：cosx、2x、x^2、pi、√x、|x|、全角字符、LaTeX 片段…
    // 这是所有解析路径的唯一入口（绘图求值/网格/数值方法/泛函），
    // 放在这里，调用方就都能直接吃课本写法，不必各自预处理。
    // ⚠ 规范化结果必须存进具名变量：Parser 内部持有 const std::string&，
    //   直接传 normalize(s).text 会传一个临时对象、构造完即析构，
    //   解析器随后读到悬垂内存（实测表现为所有输入都报"空表达式"）。
    const std::string normalized = mf::input::normalize(s).text;
    detail::Parser p(normalized);
    return p.parse();
}

// ── 求值 ────────────────────────────────────────────────────────────────────

inline double apply_function(const std::string& name, double v) {
    // 阶乘：只对非负整数精确求值（170! 已经接近 double 上限）
    if (name == "factorial") {
        if (v < 0) throw std::runtime_error("阶乘只对非负整数有定义");
        if (std::fabs(v - std::round(v)) > 1e-12)
            throw std::runtime_error("阶乘目前只支持非负整数（先把小数取整，或用 Γ 函数）");
        const double n = std::round(v);
        if (n > 170.0) throw std::runtime_error("阶乘超出浮点范围（n 最大 170）");
        double r = 1.0;
        for (double k = 2.0; k <= n; k += 1.0) r *= k;
        return r;
    }
    // 三角
    if (name == "sin") return std::sin(v);
    if (name == "cos") return std::cos(v);
    if (name == "tan") return std::tan(v);
    if (name == "cot") return 1.0 / std::tan(v);
    if (name == "sec") return 1.0 / std::cos(v);
    if (name == "csc") return 1.0 / std::sin(v);
    // 反三角（asin/acos 定义域 [-1,1]，越界时如实报错而不是返回 NaN）
    if (name == "asin") {
        if (v < -1.0 || v > 1.0) throw std::runtime_error("asin 的定义域是 [-1, 1]");
        return std::asin(v);
    }
    if (name == "acos") {
        if (v < -1.0 || v > 1.0) throw std::runtime_error("acos 的定义域是 [-1, 1]");
        return std::acos(v);
    }
    if (name == "atan") return std::atan(v);
    if (name == "acot") return std::atan(1.0 / v);
    if (name == "asec") {
        if (std::fabs(v) < 1.0) throw std::runtime_error("asec 要求 |x| ≥ 1");
        return std::acos(1.0 / v);
    }
    if (name == "acsc") {
        if (std::fabs(v) < 1.0) throw std::runtime_error("acsc 要求 |x| ≥ 1");
        return std::asin(1.0 / v);
    }
    // 双曲
    if (name == "sinh") return std::sinh(v);
    if (name == "cosh") return std::cosh(v);
    if (name == "tanh") return std::tanh(v);
    if (name == "asinh") return std::asinh(v);
    if (name == "acosh") {
        if (v < 1.0) throw std::runtime_error("acosh 要求 x ≥ 1");
        return std::acosh(v);
    }
    if (name == "atanh") {
        if (v <= -1.0 || v >= 1.0) throw std::runtime_error("atanh 要求 |x| < 1");
        return std::atanh(v);
    }
    // 指数与对数
    if (name == "exp") return std::exp(v);
    if (name == "log") {
        if (v <= 0.0) throw std::runtime_error("ln 的参数必须大于 0");
        return std::log(v);
    }
    if (name == "log10") {
        if (v <= 0.0) throw std::runtime_error("lg 的参数必须大于 0");
        return std::log10(v);
    }
    if (name == "log2") {
        if (v <= 0.0) throw std::runtime_error("log2 的参数必须大于 0");
        return std::log2(v);
    }
    // 根式与其它
    if (name == "sqrt") {
        if (v < 0.0) throw std::runtime_error("sqrt 的参数不能为负数");
        return std::sqrt(v);
    }
    if (name == "cbrt") return std::cbrt(v);
    if (name == "abs") return std::fabs(v);
    if (name == "sign") return (v > 0.0) - (v < 0.0);
    if (name == "floor") return std::floor(v);
    if (name == "ceil") return std::ceil(v);
    if (name == "round") return std::round(v);
    throw std::runtime_error("未知函数: " + name);
}

inline double eval(const ExprNode* n, const std::map<std::string, double>& vars) {
    if (!n) throw std::runtime_error("表达式树为空");
    switch (n->type) {
        case NodeType::Number:
            return n->value;
        case NodeType::Variable: {
            auto it = vars.find(n->name);
            if (it == vars.end())
                throw std::runtime_error("未提供变量 '" + n->name + "' 的值");
            return it->second;
        }
        case NodeType::Binary: {
            const double l = eval(n->left.get(), vars);
            const double r = eval(n->right.get(), vars);
            switch (n->op) {
                case '+': return l + r;
                case '-': return l - r;
                case '*': return l * r;
                case '/':
                    if (r == 0.0) throw std::runtime_error("除数为 0");
                    return l / r;
                case '^': return std::pow(l, r);
                default: throw std::runtime_error("未知的二元运算符");
            }
        }
        case NodeType::Function:
            return apply_function(n->name, eval(n->arg.get(), vars));
    }
    throw std::runtime_error("未知的节点类型");
}

inline double eval(const ExprNode* n, double x) {
    return eval(n, std::map<std::string, double>{{"x", x}});
}

// ── 符号微分(对变量 var)───────────────────────────────────────────────────

// 深拷贝节点(供符号微分复用子树)
inline std::unique_ptr<ExprNode> clone(const ExprNode* n) {
    if (!n) return nullptr;
    auto c = std::make_unique<ExprNode>();
    c->type = n->type;
    c->value = n->value;
    c->name = n->name;
    c->op = n->op;
    c->left = clone(n->left.get());
    c->right = clone(n->right.get());
    c->arg = clone(n->arg.get());
    return c;
}

// 子树是否引用变量 var(用于判断指数是否为"表达式形式的常数")。
inline bool contains_var(const ExprNode* n, const std::string& var) {
    if (!n) return false;
    switch (n->type) {
        case NodeType::Number:
            return false;
        case NodeType::Variable:
            return n->name == var;
        case NodeType::Binary:
            return contains_var(n->left.get(), var) || contains_var(n->right.get(), var);
        case NodeType::Function:
            return contains_var(n->arg.get(), var);
    }
    return false;
}

inline std::unique_ptr<ExprNode> differentiate(const ExprNode* n,
                                               const std::string& var = "x") {
    using namespace detail;
    if (!n) throw std::runtime_error("表达式树为空");
    switch (n->type) {
        case NodeType::Number:
            return make_number(0.0);
        case NodeType::Variable:
            return make_number(n->name == var ? 1.0 : 0.0);
        case NodeType::Binary: {
            auto dl = differentiate(n->left.get(), var);
            auto dr = differentiate(n->right.get(), var);
            switch (n->op) {
                case '+': return make_binary('+', std::move(dl), std::move(dr));
                case '-': return make_binary('-', std::move(dl), std::move(dr));
                case '*':  // d(l·r) = dl·r + l·dr
                    return make_binary('+',
                        make_binary('*', std::move(dl), clone(n->right.get())),
                        make_binary('*', clone(n->left.get()), std::move(dr)));
                case '/': {  // d(l/r) = (dl·r - l·dr)/r²
                    auto num = make_binary('-',
                        make_binary('*', std::move(dl), clone(n->right.get())),
                        make_binary('*', clone(n->left.get()), std::move(dr)));
                    auto den = make_binary('^', clone(n->right.get()), make_number(2.0));
                    return make_binary('/', std::move(num), std::move(den));
                }
                case '^': {
                    // 常量指数(Number 或表达式形式的常数如 2+0):v·u^(v-1)·du。
                    // 用 contains_var 判断而非只看节点类型,避免对 u≤0 引入 log(u)。
                    if (!contains_var(n->right.get(), var)) {
                        auto v_minus_1 = make_binary('-', clone(n->right.get()),
                                                      make_number(1.0));
                        return make_binary('*',
                            make_binary('*', clone(n->right.get()),
                                        make_binary('^', clone(n->left.get()),
                                                    std::move(v_minus_1))),
                            std::move(dl));
                    }
                    // 一般情形:d(u^v) = u^v·(dv·ln(u) + v·du/u)
                    auto ln_u = make_function("log", clone(n->left.get()));
                    auto dv_ln = make_binary('*', std::move(dr), std::move(ln_u));
                    auto du_d_u = make_binary('/', std::move(dl), clone(n->left.get()));
                    auto v_du = make_binary('*', clone(n->right.get()), std::move(du_d_u));
                    auto inner = make_binary('+', std::move(dv_ln), std::move(v_du));
                    return make_binary('*', clone(n), std::move(inner));
                }
                default: throw std::runtime_error("未知的二元运算符");
            }
        }
        case NodeType::Function: {
            auto du = differentiate(n->arg.get(), var);
            if (n->name == "sin")
                return make_binary('*', make_function("cos", clone(n->arg.get())),
                                   std::move(du));
            if (n->name == "cos")
                return make_binary('*',
                                   make_binary('-', make_number(0.0),
                                               make_function("sin", clone(n->arg.get()))),
                                   std::move(du));
            if (n->name == "tan")
                return make_binary('*',
                                   make_binary('/', make_number(1.0),
                                               make_binary('^',
                                                           make_function("cos", clone(n->arg.get())),
                                                           make_number(2.0))),
                                   std::move(du));
            if (n->name == "sqrt")
                return make_binary('/',
                                   std::move(du),
                                   make_binary('*', make_number(2.0),
                                               make_function("sqrt", clone(n->arg.get()))));
            if (n->name == "log")
                return make_binary('*', std::move(du),
                                   make_binary('/', make_number(1.0), clone(n->arg.get())));
            if (n->name == "exp")
                return make_binary('*', make_function("exp", clone(n->arg.get())),
                                   std::move(du));
            throw std::runtime_error("未知函数: " + n->name);
        }
    }
    throw std::runtime_error("未知的节点类型");
}

}  // namespace mf::expr
