// registry.cpp — 注册表实现(Meyers 单例,静态初始化顺序安全)。
#include "registry.hpp"

#include <algorithm>
#include <string>
#include <unordered_map>
#include <vector>

namespace mf::registry {

namespace {
std::unordered_map<std::string, Handler>& map() {
    static std::unordered_map<std::string, Handler> registry;
    return registry;
}
}  // namespace

void register_function(const std::string& name, Handler handler) {
    map()[name] = handler;
}

bool function_exists(const std::string& name) {
    return map().count(name) != 0;
}

std::vector<std::string> registered_names() {
    std::vector<std::string> out;
    out.reserve(map().size());
    for (const auto& kv : map()) out.push_back(kv.first);
    std::sort(out.begin(), out.end());
    return out;
}

std::string dispatch(const std::string& name, const std::string& args_json) {
    const auto& m = map();
    auto it = m.find(name);
    if (it == m.end()) {
        return "{\"isError\":true,\"value\":\"未找到函数: " + name + "\"}";
    }
    return it->second(args_json);
}

}  // namespace mf::registry
