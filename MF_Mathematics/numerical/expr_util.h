// expr_util.h — 表达式字符串 → 可调用函数的辅助(仅头文件)。
//
// 数值计算模块的 Python 版接收函数字符串并用 sympy lambdify;这里用
// parser_lib.h 的解析器实现等价功能。

#pragma once

#include "../parser_lib.h"

#include <functional>
#include <memory>
#include <string>
#include <utility>

namespace mf::numerical {

// 解析 f(x) 为可调用一元函数。共享指针保证 lambda 可拷贝(供 std::function)。
inline std::function<double(double)> make_unary(const std::string& expr) {
    std::shared_ptr<const mf::expr::ExprNode> root = mf::expr::parse(expr);
    return [root](double x) { return mf::expr::eval(root.get(), x); };
}

// 解析 f(t, y) 为可调用二元函数(ODE 右端)。
inline std::function<double(double, double)> make_binary(const std::string& expr) {
    std::shared_ptr<const mf::expr::ExprNode> root = mf::expr::parse(expr);
    return [root](double t, double y) {
        return mf::expr::eval(root.get(), std::map<std::string, double>{{"t", t}, {"y", y}});
    };
}

// 解析 f(x, y) 为可调用二元函数(相图系统右端,变量为 x/y)。
inline std::function<double(double, double)> make_xy(const std::string& expr) {
    std::shared_ptr<const mf::expr::ExprNode> root = mf::expr::parse(expr);
    return [root](double x, double y) {
        return mf::expr::eval(root.get(), std::map<std::string, double>{{"x", x}, {"y", y}});
    };
}

}  // namespace mf::numerical
