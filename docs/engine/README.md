# 引擎（`MF_Mathematics/`）

> 本文说明引擎的结构：两个构建目标、两个 C ABI 导出、`/WHOLEARCHIVE` 的作用，以及构建与测试方式。
> 调用契约（参数 JSON、键名、错误形状）见 [`CONTRACT.md`](CONTRACT.md)，各学科模块的 action 清单见 [`MODULES.md`](MODULES.md)，测试资产与新增方法见 [`TESTS.md`](TESTS.md)，能力边界见 [`BOUNDARIES.md`](BOUNDARIES.md)。
> 本文的数字均附复跑命令，命令在仓库根执行。

## 1. 引擎是什么

`MF_Mathematics/` 是 C++17 实现的数学计算层。全部数学结论由这一层产生，前端与宿主不承担计算。

| 项 | 值 | 出处 / 复跑 |
| --- | --- | --- |
| 语言标准 | C++17，`CMAKE_CXX_EXTENSIONS OFF` | `Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern 'CXX_STANDARD|CXX_EXTENSIONS'` |
| CMake 下限 | 3.16 | `cmake_minimum_required(VERSION 3.16)` |
| 输出目录 | 可执行与 DLL 到 `${CMAKE_BINARY_DIR}/bin`，静态库到 `${CMAKE_BINARY_DIR}/lib` | `CMAKE_RUNTIME_OUTPUT_DIRECTORY` / `CMAKE_ARCHIVE_OUTPUT_DIRECTORY` |
| 注册的 action 数 | 424 | 见「/WHOLEARCHIVE 与 424 这个数」一节 |

构建目录 `MF_Mathematics/build/` 不入 git。产物可重建，本文不记录产物字节数。

## 2. 两个构建目标

`CMakeLists.txt` 定义两个产出二进制的目标，其余是测试与探针：

| 目标 | 别名 | 类型 | 源文件 | 关键属性 |
| --- | --- | --- | --- | --- |
| `mf_mathematics_core` | `MFMath::engine` | STATIC | 102 个 `.cpp` | 不定义 `MF_BUILD_DLL`，导出面为空 |
| `mf_mathematics` | `MFMath::cabi` | SHARED | 仅 `api.cpp` | 唯一定义 `MF_BUILD_DLL`，导出 C ABI |

目标与别名定位：

```powershell
Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern 'add_library\('
```

core 的源文件数（进入 `add_library(mf_mathematics_core ...)` 编译列表的 `.cpp` 行数）：

```powershell
(Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern '^\s+[A-Za-z0-9_/.]+\.cpp$').Count   # 102
```

102 个编译单元的构成：96 个模块文件（12 个学科模块 93 个加 `extras/` 3 个）加 6 个根目录文件（`registry.cpp`、`introspect_api.cpp`、`expr_api.cpp`、`fractal_api.cpp`、`symbolic_api.cpp`、`plot_api.cpp`）。`api.cpp` 不在 core 内，它属于 DLL 目标。

### 2.1 core：全部数学实现

`mf_mathematics_core` 汇聚除 `api.cpp` 外的全部实现。各模块的 `*_api.cpp` 在静态初始化阶段把 handler 登记进注册表（见「/WHOLEARCHIVE 与 424 这个数」一节）。

| 属性 | 内容 | 出处 |
| --- | --- | --- |
| 头文件路径 | `PUBLIC` 当前源目录、`PUBLIC` Eigen 头目录、`PRIVATE` `number_theory` | `target_include_directories` |
| 链接库 | `PUBLIC` symengine / flint / gmp / mpfr 四个 `.lib` | `target_link_libraries` |
| 运行时 DLL 拷贝 | POST_BUILD 拷贝 `symengine-0.14.dll`、`flint-24.dll`、`gmp-10.dll`、`mpfr-6.dll`、`pthreadVC3.dll` | `add_custom_command(TARGET mf_mathematics_core POST_BUILD ...)` |

静态库产物是 `MF_Mathematics/build/lib/Release/mf_mathematics_core.lib`。

### 2.2 cabi：只有两个导出

`mf_mathematics` 只编译 `api.cpp`，链接 core，并定义 `MF_BUILD_DLL`：

```cmake
add_library(mf_mathematics SHARED api.cpp)
target_link_libraries(mf_mathematics PRIVATE mf_mathematics_core)
target_compile_definitions(mf_mathematics PRIVATE MF_BUILD_DLL)
```

`MF_API` 宏（[`../../MF_Mathematics/mf_export.h`](../../MF_Mathematics/mf_export.h)）在定义 `MF_BUILD_DLL` 时展开为 `__declspec(dllexport)`，否则为 `__declspec(dllimport)`。域内头文件不使用 `MF_API`，因此导出面是 [`../../MF_Mathematics/api.h`](../../MF_Mathematics/api.h) 里声明的两个函数。运行时导出表可用 `dumpbin /exports` 复核：

```powershell
$dump = (Get-ChildItem 'C:\Program Files\Microsoft Visual Studio' -Recurse -Filter dumpbin.exe | Select-Object -First 1).FullName
& $dump /exports MF_Mathematics/build/bin/Release/mf_mathematics.dll   # number of functions 应为 2
```

边界是有意的：DLL 不暴露 `std::string`、`std::vector` 或 SymEngine 的 `RCP`，内部函数签名可自由重构而不牵动 ABI。

## 3. 两个 C ABI 函数的语义

声明在 [`../../MF_Mathematics/api.h`](../../MF_Mathematics/api.h)，实现在 [`../../MF_Mathematics/api.cpp`](../../MF_Mathematics/api.cpp)：

| 函数 | 签名 | 语义 |
| --- | --- | --- |
| `function_exists` | `bool function_exists(const char* name)` | `name == nullptr` 返回 `false`；否则返回该名字是否已在注册表 |
| `math_call` | `int math_call(const char* name, const char* args_json, char* out_buffer, int out_size)` | 任一指针为 `nullptr` 或 `out_size <= 0` 返回 `-1`；结果长度加 1 超过 `out_size` 返回 `-1`；成功写入含结尾 `'\0'` 的 JSON，返回不含 `'\0'` 的字节数 |

定位：

```powershell
Select-String -Path MF_Mathematics/api.cpp -Pattern 'function_exists|math_call'
```

`math_call` 返回 `-1` 只对应三种输入问题：`nullptr` 参数、非正缓冲区、缓冲区不足。引擎「算不出来」不经过 `-1`，而是返回 `{"isError":true,...}` 或 `{"isError":false,"value":"未实现"}`。未知函数名由注册表返回合法 JSON `{"isError":true,"value":"未找到函数: <name>"}`，`math_call` 照常返回正数字节数。

`function_exists` 与 `dispatch` 的实现见 [`../../MF_Mathematics/registry.cpp`](../../MF_Mathematics/registry.cpp)，其中 `dispatch` 是 `math_call` 的实际分发入口。

## 4. /WHOLEARCHIVE 与 424 这个数

### 4.1 注册机制

每个 `*_api.cpp` 用一个无外部引用的文件级全局对象在静态初始化阶段完成注册：

```cpp
struct Registrar { Registrar() { register_all(); } };
const Registrar g_xxx_registrar;
```

注册表本体是 Meyers 单例（[`../../MF_Mathematics/registry.cpp`](../../MF_Mathematics/registry.cpp) 的 `map()` 返回函数内 `static` 容器）。`register_function` 是 `map()[name] = handler`，后注册覆盖先注册。

带此 `Registrar` 形状的 `*_api.cpp` 文件共有 18 个，全部 `register_function(` 调用点之和是 424：

```powershell
(Get-ChildItem MF_Mathematics -Recurse -File -Filter *_api.cpp |
   Where-Object { $_.FullName -notmatch '\\build\\' } |
   Select-String -Pattern 'const Registrar' | Measure-Object).Count   # 18

(Get-ChildItem MF_Mathematics -Recurse -File -Filter *_api.cpp |
   Where-Object { $_.FullName -notmatch '\\build\\' } |
   ForEach-Object { (Select-String -Path $_.FullName -Pattern 'register_function\s*\(' | Measure-Object).Count } |
   Measure-Object -Sum).Sum   # 424
```

### 4.2 失效机理

链接静态库时，链接器只抽取解决了未定义符号的目标文件。`Registrar` 对象不被任何符号引用，因此没有 `/WHOLEARCHIVE` 时整个 `*_api.cpp` 会被丢弃，注册表为空，全部 action 静默消失。

`/WHOLEARCHIVE:$<TARGET_FILE:mf_mathematics_core>` 强制全量纳入 core，是 `mf_mathematics` 目标上的 MSVC 专用链接选项：

```cmake
target_link_options(mf_mathematics PRIVATE
    "/WHOLEARCHIVE:$<TARGET_FILE:mf_mathematics_core>")
```

失效是静默的：DLL 照常加载，导出表仍是两个导出，`math_call` 对每个 action 返回「未找到函数」。判断注册器是否存活只能数 action，不能用「能加载 / 能导出 / 不崩溃」作为依据。

### 4.3 424 的取值与验证

424 是引擎注册的 action 总数，由三个独立来源交叉验证：

| 来源 | 取法 |
| --- | --- |
| 运行时注册表 | `probe_call.exe list_functions '{}'` 返回的 `value.count` |
| 源码调用点 | 18 个 `*_api.cpp` 中 `register_function(` 的匹配数之和（见「注册机制」一节） |
| 前端签名表 | [`../../MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json) 的顶层键数 |

复跑：

```powershell
& MF_Mathematics/build/bin/Release/probe_call.exe list_functions '{}'

node -e "const j=require('./MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json'); console.log(Object.keys(j).length)"
```

两条命令的输出均为 424。任一对不上，说明注册表与签名表之间发生了漂移。

## 5. 构建

### 5.1 前置依赖

| 用途 | 需要 |
| --- | --- |
| 引擎 | CMake ≥ 3.16、Visual Studio C++ 工具链、vcpkg 的 `symengine` `flint` `gmp` `mpfr` `eigen3` |

两个缓存变量有默认值，指向 vcpkg 安装位置，换机器用 `-D` 覆盖：

| 变量 | 含义 | 定位 |
| --- | --- | --- |
| `MF_SYMENGINE_ROOT` | SymEngine / FLINT / GMP / MPFR 安装根目录 | `set(MF_SYMENGINE_ROOT ... CACHE PATH ...)` |
| `MF_EIGEN_INCLUDE_DIR` | Eigen 头文件目录 | `set(MF_EIGEN_INCLUDE_DIR ... CACHE PATH ...)` |

### 5.2 命令

```powershell
cmake -S MF_Mathematics -B MF_Mathematics/build -G "Visual Studio 18 2026" -A x64 `
      -DMF_SYMENGINE_ROOT="$env:VCPKG_ROOT\installed\x64-windows" `
      -DMF_EIGEN_INCLUDE_DIR="$env:VCPKG_ROOT\installed\x64-windows\include\eigen3"
cmake --build MF_Mathematics/build --config Release --target mf_mathematics
```

生成器字符串与平台取自本机构建缓存，复跑：

```powershell
Select-String MF_Mathematics/build/CMakeCache.txt -Pattern 'CMAKE_GENERATOR:INTERNAL|CMAKE_GENERATOR_PLATFORM:INTERNAL'
```

`--target mf_mathematics` 只构建 DLL 与其依赖的 core，不构建测试与探针。关键产物：

| 产物 | 路径 |
| --- | --- |
| 引擎 DLL | `MF_Mathematics/build/bin/Release/mf_mathematics.dll` |
| 引擎静态库 | `MF_Mathematics/build/lib/Release/mf_mathematics_core.lib` |
| 运行时依赖 | `MF_Mathematics/build/bin/Release/` 下 5 个第三方 DLL |

## 6. 测试

```powershell
cmake --build MF_Mathematics/build --config Release
ctest --test-dir MF_Mathematics/build -C Release --output-on-failure
& MF_Mathematics/build/bin/Release/probe_call.exe list_functions '{}'
```

第一条命令构建全量目标（含测试与探针），第二条运行 CTest，第三条核对 `value.count == 424`。

可执行目标与 CTest 用例是两个口径：

| 口径 | 值 | 复跑 |
| --- | --- | --- |
| `add_executable` 数 | 19 | `(Select-String MF_Mathematics/CMakeLists.txt -Pattern 'add_executable\(').Count` |
| `add_test` 数 | 16 | `ctest --test-dir MF_Mathematics/build -C Release -N` |

19 个可执行目标由 15 个 `test_*` 加 4 个探针组成；16 个 CTest 用例由 15 个 `test_*` 加 `probe_bugs` 组成。用例清单与判据见 [`TESTS.md`](TESTS.md)。

`probe_call.exe`（[`../../MF_Mathematics/tests/probe_call.cpp`](../../MF_Mathematics/tests/probe_call.cpp)）只包含 `api.h`，走 C ABI，是核对引擎真实返回的入口：

| 用法 | 作用 |
| --- | --- |
| `probe_call <函数名> [args_json]` | 调用引擎，原样打印返回 JSON |
| `probe_call --list` | 列出全部已注册函数 |
| `probe_call --has <函数名>` | 查询函数是否存在，退出码 0/1 |
| `args_json` 写为 `@路径` | 从文件读取 JSON，绕开 shell 拆引号 |
