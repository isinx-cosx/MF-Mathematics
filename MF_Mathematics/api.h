#pragma once

#include "mf_export.h"

#ifdef __cplusplus
extern "C" {
#endif

// 查询注册表中是否存在名为 function_name 的函数。
MF_API bool function_exists(const char* function_name);

// 以 JSON 调用注册函数。
//   name:       函数名
//   args_json:  参数 JSON 对象,如 "{\"n\":10}"
//   out_buffer: 输出缓冲区,写入结果 JSON 字符串(含结尾 '\0')
//   out_size:   缓冲区字节数
// 返回:结果 JSON 的字节数(不含 '\0');失败或缓冲区不足返回 -1。
MF_API int math_call(const char* name, const char* args_json,
                     char* out_buffer, int out_size);

#ifdef __cplusplus
}
#endif
