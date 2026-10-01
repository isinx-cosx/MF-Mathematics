// registry.hpp — 函数注册表 + JSON 分发(内部使用)。
//
// 各模块的 API 适配层(如 number_theory_api.cpp)在加载时向注册表登记
// action 名 → handler(args_json) → 结果 JSON 字符串。C ABI(api.cpp)
// 通过 dispatch() 对外提供调用。

#pragma once

#include <functional>
#include <string>
#include <vector>

namespace mf {

class Json;

namespace registry {

// handler:接收原始 JSON 参数字符串,返回 JSON 结果字符串。
// 实现约定:无论成功失败都返回合法 JSON 对象 {isError, value}。
using Handler = std::function<std::string(const std::string& args_json)>;

void register_function(const std::string& name, Handler handler);
bool function_exists(const std::string& name);

// 全部已注册函数名（按字典序）。用于 list_functions 与探针工具，
// 也便于前端核对「某个界面模式是否真的有引擎实现」，而非依赖硬编码映射表。
std::vector<std::string> registered_names();

// 调用注册的 handler;未知函数返回 {"isError":true,...}。
std::string dispatch(const std::string& name, const std::string& args_json);

}  // namespace registry
}  // namespace mf
