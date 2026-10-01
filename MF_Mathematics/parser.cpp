// ============================================================
// parser.cpp —— 表达式解析器 + 表达式树
//
// 支持:
//   - 运算符: + - * / 和幂运算符 ** (优先级: ** > * / > + -)
//   - 括号: ( )
//   - 变量: 任意标识符,如 x、y、x1(可扩展多个变量)
//   - 函数: sin cos sqrt log exp tan(至少包含 sin/cos)
//   - 数字: 整数和小数,如 3、3.14、.5、1.
//
// 编译运行:
//   g++ -Wall -Wextra -std=c++17 parser.cpp -o parser
//   ./parser
// ============================================================

#include <cmath>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>

// ---------- 表达式树 ----------

// 节点类型:数字、变量、二元运算、函数调用
enum class NodeType {
    Number,    // 数字节点
    Variable,  // 变量节点
    Binary,    // 二元运算节点
    Function   // 函数调用节点
};

// 表达式树节点:所有类型共用一个结构,通过 type 区分
// 子节点用 unique_ptr 管理,树析构时自动释放全部内存
struct ExprNode {
    NodeType type = NodeType::Number;
    double value = 0.0;             // NumberNode 使用的数值
    std::string name;               // VariableNode 变量名 / FunctionNode 函数名
    char op = 0;                    // BinaryNode 运算符,其中 '^' 表示 '**'
    std::unique_ptr<ExprNode> left; // BinaryNode 左子节点
    std::unique_ptr<ExprNode> right;// BinaryNode 右子节点
    std::unique_ptr<ExprNode> arg;  // FunctionNode 参数子节点
};

// 创建数字节点
std::unique_ptr<ExprNode> makeNumber(double v) {
    auto n = std::make_unique<ExprNode>();
    n->type = NodeType::Number;
    n->value = v;
    return n;
}

// 创建变量节点(记录变量名,如 "x")
std::unique_ptr<ExprNode> makeVariable(const std::string& name) {
    auto n = std::make_unique<ExprNode>();
    n->type = NodeType::Variable;
    n->name = name;
    return n;
}

// 创建二元运算节点(op 为 '+','-','*','/','^'('^' 代表 '**'))
std::unique_ptr<ExprNode> makeBinary(char op, std::unique_ptr<ExprNode> l,
                                     std::unique_ptr<ExprNode> r) {
    auto n = std::make_unique<ExprNode>();
    n->type = NodeType::Binary;
    n->op = op;
    n->left = std::move(l);
    n->right = std::move(r);
    return n;
}

// 创建函数调用节点(记录函数名和参数子节点)
std::unique_ptr<ExprNode> makeFunction(const std::string& name,
                                       std::unique_ptr<ExprNode> a) {
    auto n = std::make_unique<ExprNode>();
    n->type = NodeType::Function;
    n->name = name;
    n->arg = std::move(a);
    return n;
}

// ---------- 字符分类辅助函数 ----------
namespace {

// 判断字符是否为数字 '0'-'9'
bool isDigit(char c) { return c >= '0' && c <= '9'; }

// 判断字符是否为字母或下划线(标识符开头)
bool isLetter(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
}

// 判断字符是否为标识符的组成部分(字母/数字/下划线)
bool isIdentChar(char c) { return isLetter(c) || isDigit(c); }

// 判断字符是否为空白字符
bool isSpace(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' ||
           c == '\f';
}

// 判断是否为已支持的内置函数名
bool isFunctionName(const std::string& name) {
    return name == "sin" || name == "cos" || name == "sqrt" ||
           name == "log" || name == "exp" || name == "tan";
}

}  // namespace

// ---------- 递归下降解析器 ----------
class Parser {
public:
    explicit Parser(const std::string& s) : s_(s), pos_(0) {}

    // 解析完整表达式,返回表达式树根节点(unique_ptr 自动管理内存)
    // 语法错误时抛出 std::runtime_error,不会崩溃
    std::unique_ptr<ExprNode> parse() {
        skipSpaces();
        if (pos_ >= s_.size()) throwErr("空表达式");
        std::unique_ptr<ExprNode> root = parseExpr();
        skipSpaces();
        if (pos_ < s_.size()) throwErr("表达式后存在多余字符");
        return root;
    }

private:
    const std::string& s_;  // 待解析的表达式字符串
    size_t pos_;            // 当前解析位置

    // 抛出带位置信息的解析错误(该函数不会返回)
    [[noreturn]] void throwErr(const std::string& msg) {
        throw std::runtime_error(msg + " (位置 " + std::to_string(pos_) + ")");
    }

    // 跳过当前位置之后的空白字符
    void skipSpaces() {
        while (pos_ < s_.size() && isSpace(s_[pos_])) ++pos_;
    }

    // 返回下一个有效字符(自动跳过空白);已到末尾时返回 '\0'
    char peek() {
        skipSpaces();
        return pos_ < s_.size() ? s_[pos_] : '\0';
    }

    // 判断当前位置开始的子串是否等于 kw(例如 "**")
    bool startsWith(const std::string& kw) const {
        return s_.compare(pos_, kw.size(), kw) == 0;
    }

    // expr := term (('+'|'-') term)* —— 加减法,优先级最低,左结合
    std::unique_ptr<ExprNode> parseExpr() {
        std::unique_ptr<ExprNode> left = parseTerm();
        for (;;) {
            char c = peek();
            if (c != '+' && c != '-') break;
            ++pos_;  // 吃掉运算符
            std::unique_ptr<ExprNode> right = parseTerm();
            left = makeBinary(c, std::move(left), std::move(right));
        }
        return left;
    }

    // term := factor (('*'|'/') factor)* —— 乘除法,优先级中等,左结合
    std::unique_ptr<ExprNode> parseTerm() {
        std::unique_ptr<ExprNode> left = parseFactor();
        for (;;) {
            char c = peek();
            if (c != '*' && c != '/') break;
            ++pos_;  // 吃掉运算符
            std::unique_ptr<ExprNode> right = parseFactor();
            left = makeBinary(c, std::move(left), std::move(right));
        }
        return left;
    }

    // factor := unary —— 只做一层语义分层,方便以后扩展
    std::unique_ptr<ExprNode> parseFactor() { return parseUnary(); }

    // unary := '-' unary | power
    // 只允许一元负号(用 0 - operand 表示);一元正号 '+' 会被拒绝,
    // 因此 "2++3" 这类输入会正确报错
    std::unique_ptr<ExprNode> parseUnary() {
        if (peek() == '-') {
            ++pos_;
            std::unique_ptr<ExprNode> operand = parseUnary();
            return makeBinary('-', makeNumber(0.0), std::move(operand));
        }
        return parsePower();
    }

    // power := primary ('**' unary)?
    // '**' 为幂运算符,优先级最高且右结合: 2**3**2 == 2**(3**2);
    // 指数允许带负号,如 2**-3
    std::unique_ptr<ExprNode> parsePower() {
        std::unique_ptr<ExprNode> base = parsePrimary();
        skipSpaces();
        if (startsWith("**")) {
            pos_ += 2;  // 吃掉 "**"
            std::unique_ptr<ExprNode> exp = parseUnary();
            return makeBinary('^', std::move(base), std::move(exp));
        }
        return base;
    }

    // primary := number | '(' expr ')' | function '(' expr ')' | variable
    std::unique_ptr<ExprNode> parsePrimary() {
        char c = peek();
        if (c == '(') {
            ++pos_;
            std::unique_ptr<ExprNode> inner = parseExpr();
            skipSpaces();
            if (pos_ >= s_.size() || s_[pos_] != ')') throwErr("缺少右括号 ')'");
            ++pos_;  // 吃掉 ')'
            return inner;
        }
        if (isDigit(c) || c == '.') return parseNumber();
        if (isLetter(c)) return parseIdentifier();
        if (c == '+') throwErr("不支持一元正号 '+'");
        if (c == ')') throwErr("多余的右括号 ')'");
        if (c == '\0') throwErr("表达式意外结束(缺少操作数)");
        throwErr(std::string("未预期的字符 '") + c + "'");
    }

    // 解析数字:整数或小数,如 3、3.14、.5、1.
    std::unique_ptr<ExprNode> parseNumber() {
        const size_t start = pos_;
        bool hasDigit = false;
        bool hasDot = false;
        while (pos_ < s_.size()) {
            const char c = s_[pos_];
            if (isDigit(c)) {
                hasDigit = true;
                ++pos_;
            } else if (c == '.' && !hasDot) {
                hasDot = true;
                ++pos_;
            } else {
                break;  // 第二个小数点等留给"多余字符"检查报错
            }
        }
        if (!hasDigit) throwErr("无效的数字");
        return makeNumber(std::stod(s_.substr(start, pos_ - start)));
    }

    // 解析标识符:若后面紧跟 '(' 且是已知函数名则为函数调用,
    // 否则视为变量;已知函数名后缺 '(' 会报错
    std::unique_ptr<ExprNode> parseIdentifier() {
        const size_t start = pos_;
        while (pos_ < s_.size() && isIdentChar(s_[pos_])) ++pos_;
        const std::string name = s_.substr(start, pos_ - start);

        skipSpaces();
        if (pos_ < s_.size() && s_[pos_] == '(') {
            if (!isFunctionName(name)) throwErr("未知函数 '" + name + "'");
            ++pos_;  // 吃掉 '('
            std::unique_ptr<ExprNode> arg = parseExpr();
            skipSpaces();
            if (pos_ >= s_.size() || s_[pos_] != ')') throwErr("缺少右括号 ')'");
            ++pos_;  // 吃掉 ')'
            return makeFunction(name, std::move(arg));
        }
        if (isFunctionName(name)) throwErr("函数 '" + name + "' 后需要左括号 '('");
        return makeVariable(name);
    }
};

// 对外接口:把表达式字符串解析成表达式树
// 返回动态分配的根节点(归调用者所有,需要 delete,或用 unique_ptr 包装);
// 输入非法时抛出 std::runtime_error(含位置信息),不会崩溃
ExprNode* parse(const std::string& s) {
    Parser p(s);
    return p.parse().release();
}

// ---------- 求值 ----------

// 计算内置函数 f(v) 的值;遇到未知函数或定义域问题抛出异常
double applyFunction(const std::string& name, double v) {
    if (name == "sin") return std::sin(v);
    if (name == "cos") return std::cos(v);
    if (name == "sqrt") {
        if (v < 0) throw std::runtime_error("sqrt 的参数不能为负数");
        return std::sqrt(v);
    }
    if (name == "log") {
        if (v <= 0) throw std::runtime_error("log 的参数必须大于 0");
        return std::log(v);
    }
    if (name == "exp") return std::exp(v);
    if (name == "tan") return std::tan(v);
    throw std::runtime_error("未知函数: " + name);
}

// 对表达式树求值(多变量版本):变量值通过 vars 传入,缺失的变量抛出异常
double eval(const ExprNode* n, const std::map<std::string, double>& vars) {
    if (!n) throw std::runtime_error("表达式树为空(null)");
    switch (n->type) {
        case NodeType::Number:
            return n->value;
        case NodeType::Variable: {
            const auto it = vars.find(n->name);
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
                default:  throw std::runtime_error("未知的二元运算符");
            }
        }
        case NodeType::Function:
            return applyFunction(n->name, eval(n->arg.get(), vars));
    }
    throw std::runtime_error("未知的节点类型");
}

// 对表达式树求值(单变量 x 版本):等价于 eval(n, {{"x", x}})
double eval(const ExprNode* n, double x) {
    return eval(n, std::map<std::string, double>{{"x", x}});
}

// ---------- 辅助:打印表达式树(仅用于演示/调试) ----------
// 以缩进方式输出整棵树的结构
void dump(const ExprNode* n, int depth = 0) {
    if (!n) return;
    const std::string indent(static_cast<size_t>(depth) * 2, ' ');
    switch (n->type) {
        case NodeType::Number:
            std::cout << indent << "Number(" << n->value << ")\n";
            break;
        case NodeType::Variable:
            std::cout << indent << "Variable(" << n->name << ")\n";
            break;
        case NodeType::Binary:
            std::cout << indent << "Binary('"
                      << (n->op == '^' ? "**" : std::string(1, n->op))
                      << "')\n";
            dump(n->left.get(), depth + 1);
            dump(n->right.get(), depth + 1);
            break;
        case NodeType::Function:
            std::cout << indent << "Function(" << n->name << ")\n";
            dump(n->arg.get(), depth + 1);
            break;
    }
}

// ---------- 测试 ----------

// 单变量求值测试:解析 + 求值,结果与期望值误差小于 1e-9 即通过
bool runExprTest(const std::string& expr, double x, double expected) {
    try {
        std::unique_ptr<ExprNode> root(parse(expr));
        const double got = eval(root.get(), x);
        const bool ok = std::fabs(got - expected) < 1e-9;
        std::cout << "  " << expr << "  @x=" << x << " => " << got
                  << " (期望 " << expected << ") " << (ok ? "[通过]" : "[失败]")
                  << "\n";
        return ok;
    } catch (const std::exception& e) {
        std::cout << "  " << expr << " 求值出错: " << e.what() << "\n";
        return false;
    }
}

// 多变量求值测试:通过 vars 传入多个变量的值
bool runExprTestVars(const std::string& expr,
                     const std::map<std::string, double>& vars,
                     double expected) {
    try {
        std::unique_ptr<ExprNode> root(parse(expr));
        const double got = eval(root.get(), vars);
        const bool ok = std::fabs(got - expected) < 1e-9;
        std::cout << "  " << expr << " => " << got << " (期望 " << expected
                  << ") " << (ok ? "[通过]" : "[失败]") << "\n";
        return ok;
    } catch (const std::exception& e) {
        std::cout << "  " << expr << " 求值出错: " << e.what() << "\n";
        return false;
    }
}

// 非法输入测试:解析阶段必须抛出异常才算通过
bool runBadTest(const std::string& s) {
    try {
        std::unique_ptr<ExprNode> root(parse(s));
        std::cout << "  [" << s << "] 未报错(意外解析成功) => [失败]\n";
        return false;
    } catch (const std::exception& e) {
        std::cout << "  [" << s << "] 正确报错: " << e.what() << "\n";
        return true;
    }
}

// 运行时错误测试:解析成功,但求值应抛出异常(除零、定义域错误、缺变量等)
bool runRuntimeBadTest(const std::string& s, double x) {
    try {
        std::unique_ptr<ExprNode> root(parse(s));
        const double v = eval(root.get(), x);
        std::cout << "  [" << s << "] 求值未报错(值=" << v << ") => [失败]\n";
        return false;
    } catch (const std::exception& e) {
        std::cout << "  [" << s << "] 正确报错: " << e.what() << "\n";
        return true;
    }
}

int main() {
    system("chcp 65001 > nul");
    int failed = 0;

    std::cout << "===== 1. 题目要求的基础测试 =====\n";
    failed += !runExprTest("x**2 + 2*x + 1", 3.0, 16.0);
    failed += !runExprTest("(x+2)*(x-3)", 5.0, 14.0);
    failed += !runExprTest("sin(x)**2 + cos(x)", 0.0, 1.0);

    std::cout << "\n===== 2. 优先级与结合性 =====\n";
    failed += !runExprTest("2 + 3 * 4", 0.0, 14.0);     // 乘除优先于加减
    failed += !runExprTest("(2 + 3) * 4", 0.0, 20.0);   // 括号改变优先级
    failed += !runExprTest("2 * 3 ** 2", 0.0, 18.0);    // 幂优先于乘除
    failed += !runExprTest("2 ** 3 ** 2", 0.0, 512.0);  // 幂右结合:2**(3**2)
    failed += !runExprTest("(2 ** 3) ** 2", 0.0, 64.0); // 括号强制左结合
    failed += !runExprTest("-x ** 2", 3.0, -9.0);       // -(x**2)
    failed += !runExprTest("(-x) ** 2", 3.0, 9.0);      // (-3)**2
    failed += !runExprTest("2 ** -1", 0.0, 0.5);        // 负指数
    failed += !runExprTest("10 / 4", 0.0, 2.5);         // 除法得到小数
    failed += !runExprTest("1 - 2 - 3", 0.0, -4.0);     // 加减左结合:(1-2)-3
    failed += !runExprTest("20 / 5 / 2", 0.0, 2.0);     // 乘除左结合:(20/5)/2

    std::cout << "\n===== 3. 函数测试 =====\n";
    failed += !runExprTest("sqrt(16)", 0.0, 4.0);
    failed += !runExprTest("sqrt(x)", 9.0, 3.0);
    failed += !runExprTest("log(1)", 0.0, 0.0);
    failed += !runExprTest("log(x)", 2.718281828459045, 1.0);  // log(e)=1
    failed += !runExprTest("exp(0)", 0.0, 1.0);
    failed += !runExprTest("tan(0)", 0.0, 0.0);
    failed += !runExprTest("cos(0) + sin(0)", 0.0, 1.0);
    failed += !runExprTest("sin(x)*sin(x) + cos(x)*cos(x)", 1.2345, 1.0); // 恒等式
    failed += !runExprTest("sqrt(sin(x)*sin(x) + 1)", 0.0, 1.0);          // 函数嵌套
    failed += !runExprTest("sin(x**2) + cos(x)", 0.0, 1.0);               // 混合使用

    std::cout << "\n===== 4. 小数与多变量 =====\n";
    failed += !runExprTest("0.5 + 0.25", 0.0, 0.75);
    failed += !runExprTest(".5 * 2", 0.0, 1.0);
    failed += !runExprTest("1.5 * 2", 0.0, 3.0);
    failed += !runExprTest("3.14 * x", 2.0, 6.28);
    failed += !runExprTestVars("x*y + 1", {{"x", 2.0}, {"y", 3.0}}, 7.0);
    failed += !runExprTestVars("x + y + z", {{"x", 1.0}, {"y", 2.0}, {"z", 3.0}}, 6.0);
    failed += !runExprTestVars("a**2 + b**2", {{"a", 3.0}, {"b", 4.0}}, 25.0);

    std::cout << "\n===== 5. 非法输入(解析应报错) =====\n";
    const char* bad[] = {"x**", "2++3", "(x+1", "1.2.3", "sin", "2 3",
                         "sin(x", "", "1/", "*2", "2**", "2^^3", "()",
                         "x +", "(x+1))", "1..2", ".", "x 2", "-"};
    for (const char* s : bad) failed += !runBadTest(s);

    std::cout << "\n===== 6. 运行时错误(求值应报错) =====\n";
    failed += !runRuntimeBadTest("1/0", 0.0);       // 除数为 0
    failed += !runRuntimeBadTest("sqrt(-1)", 0.0);  // 负数开方
    failed += !runRuntimeBadTest("log(0)", 0.0);    // log(0) 无定义
    failed += !runRuntimeBadTest("log(-2)", 0.0);   // log 负数无定义
    failed += !runRuntimeBadTest("x + y", 1.0);     // 缺少变量 y 的值

    std::cout << "\n===== 7. 表达式树结构展示 =====\n";
    {
        std::unique_ptr<ExprNode> demo(parse("x**2 + 2*x + 1"));
        std::cout << "  x**2 + 2*x + 1:\n";
        dump(demo.get());
    }
    {
        std::unique_ptr<ExprNode> demo(parse("sin(x)**2 + cos(x)"));
        std::cout << "  sin(x)**2 + cos(x):\n";
        dump(demo.get());
    }

    std::cout << "\n===== 我的额外测试 =====\n";
    failed += !runExprTest("2**10", 0.0, 1024.0);        // 大幂
    failed += !runExprTest("(x+1)**2", 2.0, 9.0);         // 你练过的展开
    failed += !runExprTest("(x+1)*(x-1)", 5.0, 24.0);     // 平方差
    failed += !runExprTestVars("x**2 - y**2", {{"x",5.0},{"y",3.0}}, 16.0); // 多变量

    if (failed == 0) {
        std::cout << "\n全部测试通过!\n";
        return 0;
    }
    std::cout << "\n有 " << failed << " 项测试未通过!\n";

    return 1;
}