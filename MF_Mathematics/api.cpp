#include "api.h"
#include "registry.hpp"

#include <cstring>
#include <string>

extern "C" {

bool function_exists(const char* function_name) {
    if (function_name == nullptr) return false;
    return mf::registry::function_exists(function_name);
}

int math_call(const char* name, const char* args_json, char* out_buffer,
              int out_size) {
    if (name == nullptr || args_json == nullptr || out_buffer == nullptr ||
        out_size <= 0) {
        return -1;
    }
    const std::string result = mf::registry::dispatch(name, args_json);
    // 需要容纳结果 + 结尾 '\0';缓冲区不足返回 -1
    if (result.size() + 1 > static_cast<std::size_t>(out_size)) return -1;
    std::memcpy(out_buffer, result.c_str(), result.size() + 1);
    return static_cast<int>(result.size());
}

}  // extern "C"
