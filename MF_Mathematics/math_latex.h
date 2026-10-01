// math_latex.h — 表达式 → LaTeX（仅头文件）
//
// 两个入口：
//   latex_of_expr(ExprNode*)        绘图用的表达式树 → LaTeX
//   latex_of_symengine(RCP<Basic>)  符号引擎的表达式 → LaTeX
//
// 为什么需要自己的 AST 打印器：绘图路径用的是 mf::expr 的表达式树，
// 而 SymEngine 的 LatexPrinter 只认识自己的 Basic。两者都要能出 LaTeX，
// 才能让"输入框下方实时显示解析结果"覆盖全部输入。
//
// 约定：输出的是**展示用** LaTeX，不保证能被 LaTeX 引擎原样编译（不处理
// 宏包、不做 \operatorname* 之类），目标是被 KaTeX 正确渲染。
#pragma once

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

#include "parser_lib.h"

#include <symengine/basic.h>
#include <symengine/parser.h>
#include <symengine/printers/latex.h>
#include <symengine/symengine_rcp.h>

namespace mf::latex {

// 运算符优先级（数值越大结合越紧），用于决定是否要加括号
enum Prec { PREC_ADD = 1, PREC_MUL = 2, PREC_POW = 3, PREC_ATOM = 4 };

// ⚠ 二元节点的运算符存在 ExprNode::op（char），不是 name。
//   一开始误用了 name，于是所有二元运算都落到兜底分支，
//   LaTeX 里只剩两个空格（`x^2+1` 渲染成 `x  2  1`）——字节级比对才定位到。
inline int node_prec(const expr::ExprNode* n) {
    if (!n) return PREC_ATOM;
    if (n->type == expr::NodeType::Binary) {
        const char op = n->op;
        if (op == '+' || op == '-') return PREC_ADD;
        if (op == '*' || op == '/') return PREC_MUL;
        if (op == '^') return PREC_POW;
    }
    return PREC_ATOM;
}

inline std::string wrap(const std::string& s, int p, int need) {
    return p < need ? "\\left(" + s + "\\right)" : s;
}

/** 是否字面常量 0（用于识别一元负号；命名常量 pi/e 不算） */
inline bool is_literal_zero(const expr::ExprNode* n) {
    return n && n->type == expr::NodeType::Number && n->name.empty() && n->value == 0.0;
}

/** 函数名 → LaTeX 命令（三角/对数等要用 \sin \ln 这样的正体）。 */
inline std::string fn_command(const std::string& name) {
    if (name == "sin" || name == "cos" || name == "tan" || name == "cot" ||
        name == "sec" || name == "csc" || name == "sinh" || name == "cosh" ||
        name == "tanh" || name == "arcsin" || name == "arccos" || name == "arctan" ||
        name == "ln" || name == "log" || name == "exp" || name == "lg" ||
        name == "min" || name == "max")
        return "\\" + name;
    if (name == "asin") return "\\arcsin";
    if (name == "acos") return "\\arccos";
    if (name == "atan") return "\\arctan";
    if (name == "log10") return "\\lg";
    if (name == "log2") return "\\log_{2}";
    if (name == "abs") return "\\left|\\cdot\\right|";  // 由调用方特殊处理
    if (name == "sqrt") return "\\sqrt";
    return "\\operatorname{" + name + "}";
}

/** 数字 → LaTeX（保持原样，整数不显示小数点）。 */
inline std::string number_latex(double v) {
    // 尽量打印成最短表示；整数补成整数形式
    char buf[64];
    if (v == static_cast<long long>(v) && std::fabs(v) < 1e15) {
        std::snprintf(buf, sizeof(buf), "%lld", static_cast<long long>(v));
    } else {
        std::snprintf(buf, sizeof(buf), "%.10g", v);
    }
    return std::string(buf);
}

std::string expr_to_latex(const expr::ExprNode* n);

/** 函数实参的 LaTeX：abs 用竖线，其余用括号。 */
inline std::string arg_latex(const expr::ExprNode* n) {
    if (n && n->type == expr::NodeType::Function && n->name == "abs")
        return "\\left|" + expr_to_latex(n->arg.get()) + "\\right|";
    return wrap(expr_to_latex(n), node_prec(n), PREC_ADD);  // 实参永远加括号最稳
}

inline std::string expr_to_latex(const expr::ExprNode* n) {
    if (!n) return "";
    using namespace expr;

    switch (n->type) {
        case NodeType::Number:
            // 常量（pi/e）保留名字，渲染成 \pi 而不是 3.141592654
            if (n->name == "pi") return "\\pi";
            if (n->name == "e") return "e";
            return number_latex(n->value);

        case NodeType::Variable:
            // 希腊字母类参数名转成数学体，其余按多字母下标处理
            if (n->name == "theta") return "\\theta";
            if (n->name == "pi") return "\\pi";
            if (n->name.size() == 1) return n->name;
            return "\\mathrm{" + n->name + "}";

        case NodeType::Function: {
            const std::string arg = expr_to_latex(n->arg.get());
            if (n->name == "abs") return "\\left|" + arg + "\\right|";
            if (n->name == "sqrt") return "\\sqrt{" + arg + "}";
            if (n->name == "cbrt") return "\\sqrt[3]{" + arg + "}";
            if (n->name == "exp") return "e^{" + arg + "}";
            return fn_command(n->name) + "\\left(" + arg + "\\right)";
        }

        case NodeType::Binary: {
            const std::string L = expr_to_latex(n->left.get());
            const std::string R = expr_to_latex(n->right.get());
            const int lp = node_prec(n->left.get());
            const int rp = node_prec(n->right.get());
            // 一元负号：解析器把 `-sqrt(a)` 建成 `0 - sqrt(a)`，直接按二元减法渲染
            // 会显示成 "0 - √a"。左侧是字面 0 时改写成前缀负号（数学上等价，读起来才是原式）。
            if (n->op == '-' && is_literal_zero(n->left.get()))
                return "-" + wrap(R, rp, PREC_MUL);
            switch (n->op) {
                case '+': return wrap(L, lp, PREC_ADD) + " + " + wrap(R, rp, PREC_MUL);
                case '-': return wrap(L, lp, PREC_ADD) + " - " + wrap(R, rp, PREC_MUL);
                case '*':
                    // 分数与根式并排时用 \cdot，否则紧密排版容易误读
                    return wrap(L, lp, PREC_MUL) + " \\cdot " + wrap(R, rp, PREC_POW);
                case '/': return "\\frac{" + L + "}{" + R + "}";
                case '^': return wrap(L, lp, PREC_POW) + "^{" + R + "}";
                default: break;
            }
            return L + " " + R;
        }
    }
    return "";
}

/** SymEngine 表达式 → LaTeX（用 SymEngine 自带的 LaTeX 打印器）。 */
inline std::string symengine_to_latex(const SymEngine::RCP<const SymEngine::Basic>& e) {
    if (e.is_null()) return "";
    try {
        SymEngine::LatexPrinter printer;
        return printer.apply(*e);
    } catch (...) {
        return "";
    }
}

/** 字符串形式（内部先解析为 SymEngine 表达式）。 */
inline std::string symengine_to_latex_str(const std::string& expr) {
    try {
        return symengine_to_latex(SymEngine::parse(expr));
    } catch (...) {
        return "";
    }
}

}  // namespace mf::latex
