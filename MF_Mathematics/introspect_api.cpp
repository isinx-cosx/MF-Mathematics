// introspect_api.cpp — 引擎自省能力
//
//   list_functions {} → 全部已注册函数名（按字典序）
//
// 动机：前端/桌面端存在多份「界面模式 → 引擎函数」的映射表（如 Vue 的
// ENGINE_MAP，324 条）。硬编码表会与真实注册表漂移，出现「界面选了某模式、
// 引擎却根本没这个函数」的静默失败。有了 list_functions，调用方可以启动时
// 自检一次，把未接入的模式显式标注出来。
#include "registry.hpp"
#include "api_helpers.h"
#include "json.hpp"

#include <string>

namespace {

using mf::json::Value;
using mf::api::make_handler;

void register_all() {
  mf::registry::register_function("list_functions", make_handler([](const Value&) {
    const std::vector<std::string> names = mf::registry::registered_names();
    Value arr = Value::make_array();
    for (const auto& n : names) arr.push_back(Value(n));
    Value obj = Value::make_object();
    obj.set("functions", arr);
    obj.set("count", Value(static_cast<long long>(names.size())));
    return obj;
  }, "{}（无参数）"));
}

struct Registrar { Registrar() { register_all(); } };
const Registrar g_introspect_registrar;

}  // namespace
