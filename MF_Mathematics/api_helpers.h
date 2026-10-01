// api_helpers.h — 各模块 JSON 分发层共用的辅助函数(仅头文件)。
//
// 提供参数提取、结果对象构造与 handler 包装,避免每个 *_api.cpp 重复。
// 用法示例见 number_theory_api.cpp 与 at_api.cpp。

#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "json.hpp"
#include "math_input.h"
#include "registry.hpp"

namespace mf::api {

/**
 * 该参数是不是"用户写的数学表达式"。
 * 是的话，取值时统一补上隐式乘法的 `*`：SymEngine 那条路径（求导/积分/解方程/化简…）
 * 只认显式乘法，而引擎自己的解析器认得 2x、(x+1)(x-1) —— 不补齐就会出现
 * "绘图能画、求导报 syntax error"这种同一输入两种结果的问题。
 * 只列表达式键，像 dist/method/space/contour 这类"名字/选项"不动。
 */
inline bool is_expression_key(const char* key) {
    static const char* keys[] = {
        "expr", "eq", "f", "g", "f_n", "func", "x_expr", "y_expr", "g_expr",
        "expr1", "expr2", "compare_expr", "seq", "seq_expr", "rule", "phi",
        "series", "body", "expression", "ex", "ey",
    };
    for (const char* k : keys)
        if (std::string(key) == k) return true;
    return false;
}

/** 表达式参数取值：先做隐式乘法规范化 */
inline std::string normalize_expr_arg(const std::string& v) {
    return mf::input::normalize(v).text;   // 含 LaTeX→引擎语法、√/|…| 改写、隐式乘法
}

using mf::json::Value;

inline Value result_ok(Value v) {
    Value obj = Value::make_object();
    obj.set("isError", Value(false));
    obj.set("value", std::move(v));
    return obj;
}

inline Value result_err(const std::string& msg) {
    Value obj = Value::make_object();
    obj.set("isError", Value(true));
    obj.set("value", Value(msg));
    return obj;
}

// ── 参数错误 ────────────────────────────────────────────────────────────────
//
// 参数类错误单独成类型，便于 handler 层统一补上「期望签名」。
// 背景：旧信息只写「缺少参数 a」，调用方得靠试错去猜参数名、类型与必填性
// （如 compare_expr 三轮才猜到要 {a, b} 且都必须是字符串）。
// 现在一次说清：缺什么、要什么类型、实际收到什么、本函数收到了哪些键。

struct arg_error : std::invalid_argument {
    explicit arg_error(const std::string& m) : std::invalid_argument(m) {}
};

inline const char* value_type_name(const Value& v) {
    if (v.is_null()) return "null";
    if (v.is_bool()) return "布尔";
    if (v.is_int()) return "整数";
    if (v.is_number()) return "数字";
    if (v.is_string()) return "字符串";
    if (v.is_array()) return "数组";
    if (v.is_object()) return "对象";
    return "未知类型";
}

/** 本次调用实际传入的参数键，用于「你是不是把名字写错了」这类排查。 */
inline std::string keys_of(const Value& args) {
    if (!args.is_object()) return "（参数不是 JSON 对象）";
    std::string out;
    for (const auto& k : args.keys()) {
        if (!out.empty()) out += ", ";
        out += k;
    }
    return out.empty() ? "（无）" : out;
}

/** 必需参数缺失时抛出，信息里带期望类型与实际传入的键。 */
inline void throw_missing(const Value& args, const char* key, const char* type) {
    throw arg_error(std::string("缺少必填参数 ") + key + "（应为" + type +
                    "）。本次调用传入的参数键：" + keys_of(args));
}

/** 参数存在但类型不符时抛出。 */
[[noreturn]] inline void throw_type(const Value& args, const char* key,
                                    const char* type) {
    const Value& v = args[key];
    throw arg_error(std::string("参数 ") + key + " 类型错误：应为" + type +
                    "，实际收到" + value_type_name(v) + "。本次调用传入的参数键：" +
                    keys_of(args));
}

/** 类型不符时统一给出可定位的错误（不再只报「值不是字符串」）。 */
template <typename T, typename Fn>
inline T with_type_check(const Value& args, const char* key, const char* type,
                         Fn&& get) {
    if (!args.is_object() || !args.has(key)) throw_missing(args, key, type);
    try {
        return get();
    } catch (const std::exception&) {
        throw_type(args, key, type);
    }
}

// ── 参数提取(缺键/类型不符抛 arg_error)────────────────────────────────────

inline long long get_int(const Value& args, const char* key) {
    return with_type_check<long long>(args, key, "整数",
                                      [&] { return args[key].as_int(); });
}

inline long long get_int_opt(const Value& args, const char* key, long long def) {
    if (!args.is_object() || !args.has(key)) return def;
    return with_type_check<long long>(args, key, "整数",
                                      [&] { return args[key].as_int(); });
}

inline double get_double(const Value& args, const char* key) {
    return with_type_check<double>(args, key, "数字",
                                   [&] { return args[key].as_double(); });
}

inline double get_double_opt(const Value& args, const char* key, double def) {
    if (!args.is_object() || !args.has(key)) return def;
    return with_type_check<double>(args, key, "数字",
                                   [&] { return args[key].as_double(); });
}

inline bool get_bool_opt(const Value& args, const char* key, bool def) {
    if (!args.is_object() || !args.has(key)) return def;
    return args[key].as_bool();
}

inline std::string get_string(const Value& args, const char* key) {
    const std::string v = with_type_check<std::string>(args, key, "字符串",
                                                       [&] { return args[key].as_string(); });
    return is_expression_key(key) ? normalize_expr_arg(v) : v;
}

inline std::string get_string_opt(const Value& args, const char* key,
                                  const std::string& def) {
    if (!args.is_object() || !args.has(key)) return def;
    const std::string v = with_type_check<std::string>(args, key, "字符串",
                                                      [&] { return args[key].as_string(); });
    return is_expression_key(key) ? normalize_expr_arg(v) : v;
}

/**
 * 关键词参数取值：**不做**表达式归一化。
 *
 * `is_expression_key` 是按**键名**判断"这个参数是不是用户写的数学表达式"的，可同一个
 * 键在不同 action 里语义可能完全不同：
 *   · `random_variable` 的 `rule` 是关键词（"identity" / "square"），源码用 == 比较；
 *   · `recurrence_sequence` 的 `rule` 才是表达式（"a[-1] + a[-2]"）。
 * 按键统一归一化会把 "square" 补上隐式乘法变成 `s*q*u*a*r*e`，于是关键词分支永远
 * 匹配不上、落到 else 分支，还把 `X(ω) = s*q*u*a*r*e` 当描述返回、取值全成 NaN。
 * 凡是源码里拿参数跟字面量比较的，都该用这个取值函数。
 */
inline std::string get_keyword(const Value& args, const char* key) {
    return with_type_check<std::string>(args, key, "字符串",
                                        [&] { return args[key].as_string(); });
}

inline std::string get_keyword_opt(const Value& args, const char* key,
                                   const std::string& def) {
    if (!args.is_object() || !args.has(key)) return def;
    return with_type_check<std::string>(args, key, "字符串",
                                        [&] { return args[key].as_string(); });
}

/**
 * 方程参数取值：表达式规范化 + 允许课本的"左 = 右"写法（整理成 =0 形式）。
 *
 * 只有**语义上就是方程**的函数才该用它——解方程、判别式、隐函数求导这类，
 * 它们问的本就是 "f(x)=0 的解"，等号属于它们的语言。
 * 其余函数（求导、化简、绘图…）仍只收表达式：输入里混进等号时，
 * make_handler 会用 friendly_parse_error 给出可操作的中文说明，
 * 而不是把 SymEngine 的 "Unknown token: '='" 原样抛给用户。
 */
inline std::string normalize_equation_arg(const std::string& v) {
    std::string t = normalize_expr_arg(v);
    std::string err;
    if (!mf::input::equation_to_zero(t, err)) throw arg_error(err);
    return t;
}

inline std::string get_equation(const Value& args, const char* key) {
    const std::string v = with_type_check<std::string>(args, key, "字符串",
                                                       [&] { return args[key].as_string(); });
    return is_expression_key(key) ? normalize_equation_arg(v) : v;
}

inline std::string get_equation_opt(const Value& args, const char* key,
                                    const std::string& def) {
    if (!args.is_object() || !args.has(key)) return def;
    return get_equation(args, key);
}

// 参数可为字符串或数字:数字按 JSON 序列化规则转字符串(整数去小数点)。
inline std::string get_string_or_number(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key))
        throw_missing(args, key, "字符串或数字");
    const Value& v = args[key];
    if (v.is_string()) return v.as_string();
    if (v.is_int()) return std::to_string(v.as_int());
    if (v.is_number()) return Value(v.as_double()).to_string();
    throw_type(args, key, "字符串或数字");
}

inline std::vector<long long> get_int_array(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw_missing(args, key, "整数数组");
    const Value& arr = args[key];
    std::vector<long long> out;
    for (std::size_t i = 0; i < arr.size(); ++i) {
        try {
            out.push_back(arr.at(i).as_int());
        } catch (const std::exception&) {
            throw arg_error(std::string("数组参数 ") + key + " 的第 " +
                            std::to_string(i) + " 项不是整数（实际为" +
                            value_type_name(arr.at(i)) + "）");
        }
    }
    return out;
}

inline std::vector<double> get_double_array(const Value& args, const char* key) {
    if (!args.is_object() || !args.has(key) || !args[key].is_array())
        throw_missing(args, key, "数字数组");
    const Value& arr = args[key];
    std::vector<double> out;
    for (std::size_t i = 0; i < arr.size(); ++i) {
        try {
            out.push_back(arr.at(i).as_double());
        } catch (const std::exception&) {
            throw arg_error(std::string("数组参数 ") + key + " 的第 " +
                            std::to_string(i) + " 项不是数字（实际为" +
                            value_type_name(arr.at(i)) + "）");
        }
    }
    return out;
}

// ── 序列化辅助 ──────────────────────────────────────────────────────────────

inline Value to_int_array(const std::vector<long long>& v) {
    Value arr = Value::make_array();
    for (long long x : v) arr.push_back(Value(x));
    return arr;
}

inline Value to_double_array(const std::vector<double>& v) {
    Value arr = Value::make_array();
    for (double x : v) arr.push_back(Value(x));
    return arr;
}

// ── handler 包装:解析参数 → 执行 → 序列化;异常转 {"isError":true} ────────
//
// signature 为可选的人类可读调用签名（如 "{expr: string, var?: string}"）。
// 参数类错误会自动补上它，使调用方一次就能看出「该怎么调」，
// 而不必靠反复试错去猜参数名与类型。

/**
 * 把 SymEngine 的机器话错误换成可操作的中文。
 *
 * 实测：用户在「求导」里输入 x^2+2x+1=0（课本写法），拿到的是
 * "Unknown token: '='" —— 既没说哪里错，也没说该怎么办。
 * 等号本身不是错误，只是**用错了函数**：解方程类函数收它。
 */
inline std::string friendly_parse_error(const std::string& raw) {
    const bool about_eq = raw.find("'='") != std::string::npos ||
                          raw.find("Unknown token: =") != std::string::npos;
    if (about_eq && (raw.find("Unknown token") != std::string::npos ||
                     raw.find("unknown token") != std::string::npos)) {
        return "表达式里出现了 '='，而这个函数只接受表达式。"
               "解方程 / 判别式 / 隐函数求导可以直接写 x^2+2x+1=0；"
               "其它函数请把等号右边移到左边（x^2+2x+1=0 → x^2+2x+1，引擎按 =0 处理）。"
               "原始信息：" + raw;
    }
    return raw;
}

template <typename Fn>
mf::registry::Handler make_handler(Fn&& fn, const std::string& signature = "") {
    return [fn, signature](const std::string& args_json) -> std::string {
        try {
            const Value args = Value::parse(args_json);
            return result_ok(fn(args)).to_string();
        } catch (const arg_error& e) {
            std::string msg = e.what();
            if (!signature.empty()) msg += "。期望签名：" + signature;
            return result_err(msg).to_string();
        } catch (const std::exception& e) {
            return result_err(friendly_parse_error(e.what())).to_string();
        }
    };
}

}  // namespace mf::api
