#pragma once
// mfmath_autorun.hpp — 宿主编译时用 `-include` 强制注入，用户代码不需要（也不该）include 它。
//
// 解决一个 C++ 特有的坑：控制台把子进程的 stdout/stderr 接成**管道**，
// 而管道默认是 4~8 KB 全缓冲。用户代码若抛出未捕获异常，标准库会
// std::terminate → abort()，**缓冲区不会冲刷**，于是异常之前打印的内容全部丢失
// （Python 没这个问题：它退出时正常冲刷，所以 traceback 前面还能看到输出）。
//
// 实测（MinGW 16.1.0 / x86_64-w64-mingw32）：
//   · setvbuf(stdout, ..., _IOLBF, ...) 返回 0 表示"成功"，但在 Windows 上**并不生效**，
//     输出照样丢；
//   · 真正管用的是 C++ 流自己的 std::unitbuf（每次输出后 flush），
//     C stdio 侧则靠 _IONBF 兜住 printf 路径。
//   代价（10 万行 std::cout）：167 ms → 654 ms，控制台场景完全可接受。
//
// 实现依赖：本文件用 -include 排在用户代码最前面，其中 <iostream> 会先构造
// std::ios_base::Init，所以构造函数里可以安全使用 std::cout。

#include <cstdio>
#include <iostream>

namespace mfm_detail {

struct StreamSetup {
    StreamSetup() {
        std::cout << std::unitbuf;    // 每次 << 之后立即冲刷 → abort 也不丢
        std::cerr << std::unitbuf;    // 本来就是，写上更明确
        std::setvbuf(stdout, nullptr, _IONBF, 0);   // 覆盖 printf/fputs 路径
        std::setvbuf(stderr, nullptr, _IONBF, 0);
    }
};

// 具名静态对象：构造时机在 main 之前
static const StreamSetup g_stream_setup;

}  // namespace mfm_detail
