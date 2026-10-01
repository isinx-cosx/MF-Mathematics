// probe_call.cpp — 通用引擎调用探针（人工核对用，非回归测试）
//
// 用法：
//   probe_call <函数名> [args_json]    调用引擎函数，原样打印返回 JSON
//   probe_call --list                  列出全部已注册函数（list_functions）
//   probe_call --has <函数名>          查询函数是否存在（退出码 0/1）
//
// 设计意图：不必启动宿主/WebView2 就能直接观察引擎对某个输入的真实返回，
// 便于核对「字段语义」「错误信息」「机器记号外泄」这类契约层面的问题。
//
// 只使用 C ABI（api.h），不引用内部注册表头文件——这样探针观察到的
// 与 C#/JS 调用方看到的是同一条路径，探针结果可直接作为对外行为的证据。
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "api.h"

namespace {

int usage() {
  std::fprintf(stderr,
               "用法：\n"
               "  probe_call <函数名> [args_json]   调用引擎函数，原样打印返回 JSON\n"
               "  probe_call --list                 列出全部已注册函数\n"
               "  probe_call --has <函数名>         查询函数是否存在\n");
  return 2;
}

/** 调用引擎并把原始返回写入 out；返回是否成功。 */
bool call(const std::string& name, const std::string& args, std::string& out) {
  std::vector<char> buf(4 << 20);  // 4 MiB：足够容纳大型 grid/采样结果
  const int n = math_call(name.c_str(), args.c_str(), buf.data(),
                          static_cast<int>(buf.size()));
  if (n < 0) return false;
  out.assign(buf.data(), static_cast<std::size_t>(n));
  return true;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) return usage();

  const std::string first = argv[1];

  if (first == "--list") {
    std::string out;
    if (!call("list_functions", "{}", out)) {
      std::fprintf(stderr, "调用 list_functions 失败\n");
      return 3;
    }
    std::printf("%s\n", out.c_str());
    return 0;
  }

  if (first == "--has") {
    if (argc < 3) return usage();
    const bool ok = function_exists(argv[2]);
    std::printf("%s\n", ok ? "yes" : "no");
    return ok ? 0 : 1;
  }

  // 参数可以写成 @路径：从文件读取 JSON。
  // 便于脚本化测试——命令行传含空格/引号/竖线的 JSON 会被 shell 拆开或转义，
  // 之前就因此把 5 条正常用例误判成失败。
  std::string args = (argc >= 3) ? argv[2] : "{}";
  if (!args.empty() && args[0] == '@') {
    std::FILE* fp = std::fopen(args.c_str() + 1, "rb");
    if (fp == nullptr) {
      std::fprintf(stderr, "无法打开参数文件: %s\n", args.c_str() + 1);
      return 4;
    }
    std::string content;
    char chunk[4096];
    std::size_t got = 0;
    while ((got = std::fread(chunk, 1, sizeof(chunk), fp)) > 0) content.append(chunk, got);
    std::fclose(fp);
    while (!content.empty() && (content.back() == '\n' || content.back() == '\r' ||
                                content.back() == ' '))
      content.pop_back();
    args = content;
  }
  std::string out;
  if (!call(first, args, out)) {
    std::fprintf(stderr, "调用失败：缓冲区不足或参数非法（name=%s）\n", first.c_str());
    return 3;
  }
  std::printf("%s\n", out.c_str());
  return 0;
}
