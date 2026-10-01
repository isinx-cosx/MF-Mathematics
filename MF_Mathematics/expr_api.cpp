// expr_api.cpp — 表达式求值注册（暴露 mf::expr 解析器给 registry）
// 提供：
//   expr_eval          {expr, x}              → 单点求值
//   expr_eval_batch    {expr, xs:[...]}       → 批量求值（曲线）
//   expr_eval2         {expr, x, y}           → 二元单点求值（z = f(x,y)）
//   expr_eval_grid     {expr, xs, ys}         → 二元网格求值（3D 曲面 / 向量场）
//   expr_eval_vars     {expr, vars:{...}}     → 任意变量字典单点求值（绘图参数代入）
//   expr_eval_vars_batch {expr, xs, vars}     → 带参数的批量求值（参数曲线/滑块重绘）
//   prepare_expr         {expr}               → 输入规范化 + 校验 + LaTeX（界面实时预览）
//   sym_latex            {expr}               → 符号表达式 → LaTeX（结果渲染）
#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"
#include "math_input.h"
#include "math_latex.h"
#include "parser_lib.h"

#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using mf::json::Value;
using mf::api::make_handler;
using mf::api::get_string;
using mf::api::get_double_opt;
using mf::api::get_double_array;
using mf::api::to_double_array;

/**
 * 读取**用户原始输入串**（一个字符都不做规范化）。
 *
 * 背景：to_engine_expr.changed 与 prepare_expr.input 问的正是「用户写的」和
 * 「引擎理解的」之间的差别，而 get_string 对表达式键会先跑一遍
 * normalize（api_helpers.h:151）——原始串在进入 handler 之前就已经被改写，
 * 于是 handler 里再 normalize 一次（幂等）只会得到空 notes：
 *   to_engine_expr({"expr":"√2"}) → changed 恒 false（输入明明从 √2 变成了 sqrt(2)）
 *   prepare_expr({"expr":"√2"})   → input 恒等于 normalized（"sqrt(2)"，不是用户写的 "√2"）
 * 所以这两个接口必须绕开 get_string 的归一化，直接取 JSON 里的原串。
 */
std::string raw_expr_arg(const Value& args, const char* key) {
  if (!args.is_object() || !args.has(key))
    mf::api::throw_missing(args, key, "字符串");
  std::string out;
  try {
    out = args[key].as_string();
  } catch (const std::exception&) {
    mf::api::throw_type(args, key, "字符串");
  }
  return out;
}

/** 读取可选的 vars 对象 → 变量字典（键为变量名，值为数值） */
std::map<std::string, double> read_vars(const Value& args) {
  std::map<std::string, double> vars;
  if (!args.is_object() || !args.has("vars")) return vars;
  const Value& v = args["vars"];
  if (!v.is_object()) return vars;
  for (const auto& key : v.keys()) {
    const Value& item = v[key];
    if (item.is_number() || item.is_int()) vars[key] = item.as_double();
  }
  return vars;
}

/**
 * 批量求值的逐点容错：域外点留空（NaN → JSON null → 曲线断开），而不是整批报错。
 *
 * 实测的病：`e^x - ln x` 的默认采样区间 x∈[-15,15] 里有一半点是 ln 的域外点，
 * 旧实现让第一个异常把**整批 300 点**变成 isError，界面于是"什么都画不出来"，
 * 而且曲线是静默消失的（没有任何提示）。逐点容错后：有定义的地方照画，
 * 没定义的地方自然断开——这也是教科书上这类图的画法。
 */
double safe_eval_point(const mf::expr::ExprNode* root,
                       const std::map<std::string, double>& vars) {
  try {
    return mf::expr::eval(root, vars);
  } catch (...) {
    return std::numeric_limits<double>::quiet_NaN();
  }
}
double safe_eval_point(const mf::expr::ExprNode* root, double x) {
  try {
    return mf::expr::eval(root, x);
  } catch (...) {
    return std::numeric_limits<double>::quiet_NaN();
  }
}

/** 单点求值的结果：∞/-∞ 如实给记号（JSON 里的 ±inf 只能写成 null，会丢信息）；
 *  NaN 明确报错，避免界面显示 null。 */
Value finite_or_text(double v) {
  if (v != v) throw std::invalid_argument("结果未定义（NaN），例如 ∞−∞、0/0 这类不确定形式");
  if (v == std::numeric_limits<double>::infinity()) return Value(std::string("∞"));
  if (v == -std::numeric_limits<double>::infinity()) return Value(std::string("-∞"));
  return Value(v);
}

void register_all() {
  using mf::registry::register_function;

  // 单点求值：y = f(x)
  register_function("expr_eval", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const double x = get_double_opt(args, "x", 0.0);
    auto root = mf::expr::parse(expr);             // 解析成表达式树
    return finite_or_text(mf::expr::eval(root.get(), x));   // 求值
  }));

  // 批量求值：一次调用算整条曲线/场
  register_function("expr_eval_batch", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const std::vector<double> xs = get_double_array(args, "xs");
    auto root = mf::expr::parse(expr);
    std::vector<double> ys;
    ys.reserve(xs.size());
    for (double x : xs) ys.push_back(safe_eval_point(root.get(), x));   // 逐点容错
    return to_double_array(ys);
  }));

  // 二元单点求值：z = f(x, y)
  register_function("expr_eval2", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const double x = get_double_opt(args, "x", 0.0);
    const double y = get_double_opt(args, "y", 0.0);
    auto root = mf::expr::parse(expr);
    return finite_or_text(mf::expr::eval(root.get(), std::map<std::string, double>{{"x", x}, {"y", y}}));
  }));

  // 二元网格求值：f(x,y) 在 xs×ys 网格上的值（行优先展平）
  // 支持可选 vars（隐式方程 / 二元区域含参数时的代入）
  register_function("expr_eval_grid", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const std::vector<double> xs = get_double_array(args, "xs");
    const std::vector<double> ys = get_double_array(args, "ys");
    const std::map<std::string, double> vars = read_vars(args);
    auto root = mf::expr::parse(expr);
    std::vector<double> zs;
    zs.reserve(xs.size() * ys.size());
    std::map<std::string, double> local = vars;
    for (double y : ys) {
      local["y"] = y;
      for (double x : xs) {
        local["x"] = x;
        zs.push_back(safe_eval_point(root.get(), local));   // 逐点容错（曲面同样有域外点）
      }
    }
    return to_double_array(zs);
  }));

  // 任意变量字典单点求值（绘图参数代入：expr 含 a,b…，vars 给出其值）
  // var 指定自变量名（默认 x）：垂直关系用 y、极坐标用 theta、参数方程用 t
  //
  // ⚠ 自变量取值必须有来源，**不允许静默默认成 0**：
  //   旧实现只认键 "x" 且缺省取 0.0，于是
  //     · 传 {"var":"t","values":[2]} 这类写法时 values 被忽略 → 按 t=0 算出错值；
  //     · expr 含自变量却漏传取值 → 同样按 0 算，返回一个"看起来正常"的数字。
  //   两者都是静默错答，比报错危险得多。现在只在**表达式确实不含该变量**时
  //   才允许缺省（此时取值不影响结果）。
  register_function("expr_eval_vars", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const std::string var_name = mf::api::get_string_opt(args, "var", "x");
    std::map<std::string, double> vars = read_vars(args);

    // 取值来源，按优先级：
    //   ① 与自变量同名的键        {"var":"t","t":2}
    //   ② values 数组的首元素     {"values":[2]}
    //   ③ 兼容早期调用方的键 "x"   {"var":"x","x":2}
    bool have_t = false;
    double t = 0.0;
    const auto take_key = [&](const std::string& key) -> bool {
      if (!args.is_object() || !args.has(key)) return false;
      try {
        t = args[key].as_double();
        return true;
      } catch (...) {
        return false;
      }
    };
    if (take_key(var_name)) have_t = true;
    if (!have_t && args.is_object() && args.has("values")) {
      const Value& v = args["values"];
      if (v.is_array() && v.size() > 0) {
        try {
          t = v.at(0).as_double();
          have_t = true;
        } catch (...) {
        }
      }
    }
    if (!have_t) have_t = take_key("x");

    auto root = mf::expr::parse(expr);
    if (!have_t && mf::expr::contains_var(root.get(), var_name))
      throw std::invalid_argument(
          "未提供自变量 " + var_name + " 的值（表达式含该变量，不能按 0 代入）。"
          "请用 {\"var\":\"" + var_name + "\", \"" + var_name + "\":<数值>}，"
          "或 {\"values\":[<数值>]}；参数用 vars 对象传入");
    if (!have_t) t = 0.0;  // 表达式不含该变量，取值不影响结果
    vars[var_name] = t;
    return Value(mf::expr::eval(root.get(), vars));
  }, "{expr: string, var?: string = \"x\", vars?: object, <var>?: number, values?: [number]}"));

  // 带参数的批量求值：自变量（var，默认 x）扫描 xs，参数由 vars 提供
  // 滑块拖动时整条曲线重算；极坐标/参数方程/垂直关系也都走这里
  register_function("expr_eval_vars_batch", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    const std::string var_name = mf::api::get_string_opt(args, "var", "x");
    const std::vector<double> xs = get_double_array(args, "xs");
    const std::map<std::string, double> vars = read_vars(args);
    auto root = mf::expr::parse(expr);
    std::vector<double> ys;
    ys.reserve(xs.size());
    std::map<std::string, double> local = vars;
    for (double t : xs) {
      local[var_name] = t;
      ys.push_back(safe_eval_point(root.get(), local));   // 逐点容错：域外点留空，不拖垮整条曲线
    }
    return to_double_array(ys);
  }));

  // MathLive 的 <math-field> 给的是 LaTeX；计算要的是引擎语法。
  // 这个接口只做"规范化"这一件事（不解析、不生成 LaTeX），
  // 因为它在每次按键时都会被调用，要尽量轻。
  register_function("to_engine_expr", make_handler([](const Value& args) {
    const std::string raw = raw_expr_arg(args, "expr");
    const auto prep = mf::input::normalize(raw);
    Value notes = Value::make_array();
    for (const auto& n : prep.notes) notes.push_back(Value(n));
    Value obj = Value::make_object();
    obj.set("expr", Value(prep.text));
    obj.set("changed", Value(prep.changed()));
    obj.set("notes", notes);
    return obj;
  }, "{expr: string}"));

  // 输入准备：规范化 + 校验 + LaTeX。
  // 界面用它做两件事：① 实时渲染"这段输入被理解成了什么"，把 cosx 这类误读
  // 立刻暴露出来，而不是等画不出图才发现；② 自动改写时给出说明。
  register_function("prepare_expr", make_handler([](const Value& args) {
    const std::string raw = raw_expr_arg(args, "expr");
    const auto prep = mf::input::normalize(raw);
    Value notes = Value::make_array();
    for (const auto& n : prep.notes) notes.push_back(Value(n));

    Value obj = Value::make_object();
    obj.set("input", Value(raw));
    obj.set("normalized", Value(prep.text));
    obj.set("changed", Value(prep.changed()));
    obj.set("notes", notes);
    try {
      auto root = mf::expr::parse(raw);  // parse 内部会再规范化一次（幂等）
      obj.set("ok", Value(true));
      obj.set("latex", Value(mf::latex::expr_to_latex(root.get())));
    } catch (const std::exception& e) {
      obj.set("ok", Value(false));
      obj.set("error", Value(std::string(e.what())));
      obj.set("latex", Value(std::string("")));
    }
    return obj;
  }, "{expr: string}"));

  // 符号表达式 → LaTeX：把引擎返回的表达式字符串（驻点、解、交点…）
  // 渲染成数学排版，而不是原样显示 (1/2)*sqrt(3)。
  register_function("sym_latex", make_handler([](const Value& args) {
    const std::string expr = get_string(args, "expr");
    Value obj = Value::make_object();
    try {
      const auto e = SymEngine::parse(expr);
      obj.set("latex", Value(mf::latex::symengine_to_latex(e)));
      obj.set("ok", Value(true));
    } catch (const std::exception& e) {
      // 解析不了就如实说明，让调用方退回纯文本显示
      obj.set("latex", Value(std::string("")));
      obj.set("ok", Value(false));
      obj.set("error", Value(std::string(e.what())));
    }
    return obj;
  }, "{expr: string}"));
}

struct Registrar { Registrar() { register_all(); } };
const Registrar g_expr_registrar;

}  // namespace
