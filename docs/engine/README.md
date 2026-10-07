# 引擎（`MF_Mathematics/`）

> **本文只回答一个问题：引擎是什么、由哪两个构建目标组成、怎么构建、怎么跑测试。**
>
> 与同层其它文档的分工：
> - [`TESTS.md`](TESTS.md) —— 19 个可执行目标 / 16 个 CTest 用例 / 守门断言的复跑清单（本文只给入口，不复述用例清单）；
> - [`CONTRACT.md`](CONTRACT.md) —— args JSON 形状与**键名契约**、必填参数拒绝、"未实现"的返回形状（本文只讲这两个 C ABI 函数的**机械语义**，不讲键名）；
> - [`MODULES.md`](MODULES.md) —— 12 个学科模块逐个的 action 清单与边界（本文只讲**怎么注册**，不讲注册了什么）；
> - [`BOUNDARIES.md`](BOUNDARIES.md) —— 如实的能力边界与 `NOT_EXPOSED` 口径；
> - [`NUMERIC.md`](NUMERIC.md) —— `special_numeric` / `complex_numeric` 的容差与精度策略。

**证据基线**：2026-10-07 本机实测。被测产物 `MF_Mathematics/build/bin/Release/mf_mathematics.dll`
（LastWriteTime 2026-10-06 05:43:00，3,379,712 字节）、`probe_call.exe`（05:43:03）。
`MF_Mathematics/build/` 不入 git（[`.gitignore`](../../.gitignore) 的「引擎构建目录」段），
所以**本文每个数字都附复跑命令**——换产物就要重跑，别把本文当现状。

---

## 1. 引擎是什么

`MF_Mathematics/` 是 **C++17 静态/动态两层**的数学计算层，是整棵树里**唯一产生数学结论的地方**
（[`../../README.md`](../../README.md):84「为什么前端一行数学都不算」）。

| 事实 | 值 | 出处 / 复跑 |
| --- | --- | --- |
| 语言标准 | C++17，`CMAKE_CXX_EXTENSIONS OFF` | `CMakeLists.txt`:4-6 |
| CMake 下限 | 3.16 | `CMakeLists.txt`:1 |
| 引擎源码文件数 | **110 个 `.cpp`**（不含 `build/`、`tests/`） | `Get-ChildItem MF_Mathematics -Recurse -Filter *.cpp \| ? {$_.FullName -notmatch '\\build\\\|\\tests\\'}` |
| 实际编译进产物的编译单元 | **103 个** = core 的 102 个 + `api.cpp` | `CMakeLists.txt`:29-130（102 条）+ `:167`；差额见文末「已知的文档债」第 3 条 |
| 注册的 action 总数 | **424** | 见 [§5](#5-424-这个数有三个独立来源) |
| 第三方依赖 | SymEngine + flint + gmp + mpfr（链接）+ Eigen（仅头文件） | `CMakeLists.txt`:13-20、`:139-144` |
| 头文件 | 根目录 11 个：`api.h` `api_helpers.h` `json.hpp` `math_input.h` `math_latex.h` `mf_export.h` `parser_lib.h` `special_numeric.h` `symbolic_pretty.h` `symbolic_util.h` `complex_numeric.h` | `Get-ChildItem MF_Mathematics -File` |
| 辅助脚本（非构建） | `tools/` 6 个 `.py`：`stress_scan.py`、`verify_hang_fixes.py`、`add_bounded_using.py`、`apply_int_caps.py`、`fix_cap_regressions.py`、`relax_lower_bounds.py` | `Get-ChildItem MF_Mathematics/tools` |

**它不做什么**（三条纪律在引擎侧的落点，详见 [`../DESIGN.md`](../DESIGN.md)）：

| 纪律 | 引擎侧的机制 | 出处 |
| --- | --- | --- |
| ① 不编造结果 | 算不出来返回 `{"isError":true,...}`，不返回占位串；未识别的名字**报错** | `registry.cpp`:37-38、`api_helpers.h`:52-56 |
| ② AI 不承担计算 | 引擎**只**接受 `math_call` 进来的名字+参数，不感知调用方是 UI 还是 AI | `api.cpp`:14-25 |
| ③ 每个修复留证据 | 契约用 CTest 钉住：`add_test(NAME symbolic_contract ...)` 等 16 条 | `CMakeLists.txt`:340-353、[`TESTS.md`](TESTS.md) §3 |

---

## 2. 两个构建目标

`CMakeLists.txt` 里只有**两个**目标产出二进制，其余 19 个都是测试/探针：

| 目标 | 别名 | 类型 | 源文件 | 定义 | 关键属性 |
| --- | --- | --- | --- | --- | --- |
| `mf_mathematics_core` | `MFMath::engine` | **STATIC** | `CMakeLists.txt`:29-130 共 **102** 个 `.cpp` | `:28` | **不**定义 `MF_BUILD_DLL`；`PUBLIC` 头文件路径与 4 个第三方 `.lib` |
| `mf_mathematics` | `MFMath::cabi` | **SHARED** | **只有 `api.cpp`** | `:167` | 唯一定义 `MF_BUILD_DLL` → 唯一 `dllexport` 的目标 |

别名在 `CMakeLists.txt`:199-200，注释（`:186-198`）说明用途：CI 的准确性套件链 `MFMath::engine`，
宿主/JS 桥这类跨语言消费者链 `MFMath::cabi`。

### 2.1 core：全部数学实现

| 属性 | 内容 | 出处 |
| --- | --- | --- |
| `target_include_directories` | `PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}`、`PUBLIC ${MF_EIGEN_INCLUDE_DIR}`、`PRIVATE number_theory` | `CMakeLists.txt`:132-136 |
| `target_link_libraries` | `PUBLIC` symengine / flint / gmp / mpfr 四个 `.lib`（注释明说为了让调用方不必重复列） | `:139-144` |
| 编译选项 | `/utf-8 /W4 /external:W0 /external:I "${MF_SYMENGINE_ROOT}/include"` | `:148-149` |
| POST_BUILD | 拷 5 个运行时 DLL（`symengine-0.14.dll` `flint-24.dll` `gmp-10.dll` `mpfr-6.dll` `pthreadVC3.dll`）到输出目录；注释说明**挂在 core 而不是 DLL 上**，否则单独构建某个测试目标不会触发拷贝 | `:155-161` |
| 产物 | `MF_Mathematics/build/lib/Release/mf_mathematics_core.lib`，**140,059,286 字节**（实测） | `Get-ChildItem MF_Mathematics\build\lib -Recurse` |

### 2.2 cabi：只有两个导出

`CMakeLists.txt`:167-169 三行就是全部定义：`add_library(mf_mathematics SHARED api.cpp)`、
`target_link_libraries(... PRIVATE mf_mathematics_core)`、`target_compile_definitions(... PRIVATE MF_BUILD_DLL)`。

导出面为什么恰好是两个 —— 两层原因，缺一不可：

1. `MF_API` 只在 `mf_export.h`:8-12 定义，`MF_BUILD_DLL` 只在这个目标上（`CMakeLists.txt`:169）；
2. **域内头文件已不再使用 `MF_API`** —— 全树 grep `MF_API` 只命中三处：`api.h`:10、`api.h`:18、
   `mf_export.h` 自己（`Get-ChildItem MF_Mathematics -Recurse -Include *.h,*.hpp,*.cpp | Select-String MF_API`）。

**实测导出表**（`dumpbin /exports`，本机 VS 18 的 `dumpbin.exe`）：

```
1 ordinal base
2 number of functions
2 number of names
     ordinal hint RVA      name
          1    0 00001C00 function_exists
          2    1 00001CC0 math_call
```

复跑：

```powershell
& 'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x64\dumpbin.exe' `
  /exports MF_Mathematics\build\bin\Release\mf_mathematics.dll
```

> 这条边界是有意的：DLL 不再暴露 `std::string` / `std::vector` / `SymEngine::RCP`，
> 内部函数签名就能自由重构而不牵动 ABI（`CMakeLists.txt`:24-27）。

---

## 3. 两个 C ABI 函数的机械语义

声明在 `api.h`，实现在 `api.cpp`（27 行，全部内容就是转发到注册表）：

| 函数 | 签名 | 语义 | 出处 |
| --- | --- | --- | --- |
| `function_exists` | `bool function_exists(const char*)` | `nullptr` → `false`；否则查注册表键是否存在 | `api.h`:10、`api.cpp`:9-12、`registry.cpp`:22-24 |
| `math_call` | `int math_call(const char*, const char*, char*, int)` | 参数任一为 `nullptr` 或 `out_size <= 0` → **`-1`**；结果长度 +1 > `out_size` → **`-1`**；成功则 `memcpy` 含结尾 `'\0'`，返回**不含 `'\0'`** 的字节数 | `api.h`:18-19、`api.cpp`:14-25 |

三条容易踩的：

1. **未知函数名不是 `-1`** —— `dispatch()` 返回合法 JSON `{"isError":true,"value":"未找到函数: <name>"}`，
   `math_call` 照常返回正数字节数（`registry.cpp`:34-41）。这是[§4](#4-注册器与-wholearchive-为什么必须加) 静默失效的观察面。
2. **异常被 `make_handler` 拦在 C ABI 边界内** —— 参数错误 → `{"isError":true}`（会附人类可读签名，`api_helpers.h`:337-340）；
   其他 `std::exception` → 同上；**`catch(...)` 兜住非 std 异常**，注释写明不拦就会穿过 `extern "C"` 边界成为未定义行为、
   表现为**宿主进程被终止**（`api_helpers.h`:343-354）。
3. **`-1` 只有三种原因**：`nullptr` / `out_size <= 0` / 缓冲区不足 —— 都不是"引擎算不出来"。
   算不出来走的是 `isError`。这条区分是失败分类的前提（[§7](#7-失败先分类再归因)）。

`probe_call.cpp`:18 只 `#include "api.h"`，注释（`:11-12`）说明这样"探针观察到的与 C#/JS 调用方看到的是同一条路径"。

---

## 4. 注册器与 /WHOLEARCHIVE：为什么必须加

每个 `*_api.cpp` 靠一个**没有外部引用的全局对象**把 handler 塞进注册表。注册表本体是 Meyers 单例
（`registry.cpp`:12-15，注释标明这样静态初始化顺序安全），`register_function` 是 `map()[name] = handler`
（`:18-20`，**后注册覆盖先注册**）。

18 个 `*_api.cpp` 全部是这个形状（`struct Registrar { Registrar() { register_all(); } };` + 一个文件级 `const Registrar`）：

| 模块 | 注册器位置 | 该文件的 `register_function` 数 |
| --- | --- | --- |
| （根）表达式 | `expr_api.cpp`:294-295 | 9 |
| （根）分形 | `fractal_api.cpp`:60-61 | 1 |
| （根）自省 | `introspect_api.cpp`:32-33 | 1 |
| （根）绘图 | `plot_api.cpp`:477-478 | 4 |
| （根）符号 | `symbolic_api.cpp`:1367-1368 | 7 |
| 代数 | `algebra/algebra_api.cpp`:621-624 | 79 |
| 代数拓扑 | `algebraic_topology/at_api.cpp`:310-313 | 17 |
| 微积分 | `calculus/calculus_api.cpp`:349-352 | 35 |
| 复分析 | `complex_analysis/complex_analysis_api.cpp`:395-398 | 30 |
| 扩展 | `extras/extras_api.cpp`:304-307 | 25 |
| 泛函分析 | `functional_analysis/fa_api.cpp`:292-295 | 21 |
| 调和分析 | `harmonic_analysis/harmonic_analysis_api.cpp`:313-316 | 22 |
| 线性代数 | `linear_algebra/linear_algebra_api.cpp`:410-413 | 32 |
| 测度论 | `measure_theory/measure_theory_api.cpp`:541-544 | 24 |
| 数论 | `number_theory/number_theory_api.cpp`:293-296 | 24 |
| 数值 | `numerical/numerical_api.cpp`:336-339 | 25 |
| 概率 | `probability/probability_api.cpp`:548-551 | 40 |
| 实分析 | `real_analysis/real_analysis_api.cpp`:282-285 | 28 |
| **合计** | 18 个文件 | **424** |

合计数的复跑命令：

```powershell
Get-ChildItem MF_Mathematics -Recurse -File -Filter *_api.cpp |
  Where-Object { $_.FullName -notmatch '\\build\\' } |
  ForEach-Object { (Select-String -Path $_.FullName -Pattern 'register_function\s*\(' | Measure-Object).Count }
```

### 4.1 失效机理（`CMakeLists.txt`:173-181 的注释，已与代码对照）

链接静态库时，链接器**只抽取"解决了未定义符号"的目标文件**。这些 `Registrar` 对象不被任何符号引用，
于是整个 `*_api.cpp` 被丢弃 → 注册表为空 → 424 个 action 集体消失。
`/WHOLEARCHIVE:$<TARGET_FILE:mf_mathematics_core>`（`:182-183`）强制全量纳入 core 解决它。

**失效为什么是静默的**（这是本节最该记住的一句）：

| 观察点 | 失效后的表现 | 与"正常"的区别 |
| --- | --- | --- |
| DLL 加载 | 照常成功 | 无 |
| `function_exists("gcd")` | 照常能调用，返回 `false` | 只有返回值不同，不报错 |
| `math_call("gcd", ...)` | **返回正数字节数的合法 JSON**，`{"isError":true,"value":"未找到函数: gcd"}` | 只有 `value` 文案不同 |
| 导出表 | 依然"漂亮"：仍然是 2 个导出 | 无 |

所以**不能**用"能加载 / 能导出 / 不崩"判断注册器是否活着，只能数 action。

### 4.2 守门断言：`probe_call list_functions` 的 `count` 必须是 424

```powershell
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'
# 期望：{"isError":false,"value":{"count":424,"functions":[...]}}   看 .value.count，不看退出码
```

本机实测输出（2026-10-07，cwd 为仓库根，`probe_call.exe` 与 DLL 同目录故能找到运行时依赖）：
`count` = **424**，`functions` 首个为 `abs_value`、末个为 `zeta_series`。

三种等价写法（都走 `list_functions`，任选）：

| 写法 | 路径 | 出处 |
| --- | --- | --- |
| `probe_call.exe list_functions '{}'` | 泛用分支（`argc>=3` 解析 args） | `probe_call.cpp`:68-91 |
| `probe_call.exe list_functions` | 同上，args 缺省为 `"{}"` | `probe_call.cpp`:68 |
| `probe_call.exe --list` | 专用分支，失败退出码 3 | `probe_call.cpp`:48-56 |

> ⚠ 这个断言**目前只能手工跑**：`MF_Mathematics/tests/` 下没有任何代码检查 `count == 424`
> ——见文末「已知的文档债」第 1 条。自动化侧最接近的是端到端用例
> `MF_UI/MFMath.UI.Vue/tests/cdp-ai.mjs`:409 的 `toolFacts.count >= 300`，它的**阈值不是 424**。

`probe_call` 的另外两种用法（人造核对时用得到）：`probe_call <函数名> [args_json]` 直接打印引擎原始返回；
`probe_call --has <函数名>` 查存在性并以退出码 0/1 表达；参数可写 `@路径` 从文件读 JSON
（`probe_call.cpp`:4-6、`:58-63`、`:65-84`，注释说明 `@` 形式是为了绕开 shell 拆引号）。

---

## 5. 424 这个数有三个独立来源

424 不是一个可以手抄的数字 —— 它有三条互相独立的来源，**任一条对不上就说明有东西漂了**：

| # | 来源 | 怎么取 | 2026-10-07 实测 |
| --- | --- | --- | --- |
| ① **权威源**：签名表 | `MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json` 的**顶层键数** | `(Get-Content <该文件> -Raw \| ConvertFrom-Json).PSObject.Properties.Count` | **424**（96,794 字节 / 5,905 行） |
| ② 运行时注册表 | `probe_call.exe list_functions '{}'` 的 `.value.count` | 见 §4.2 | **424** |
| ③ 源码 `register_function` 调用点数 | 18 个 `*_api.cpp` 的匹配数之和 | 见 §4 的脚本 | **424** |

**为什么把签名表叫作权威源**：`docs/README.md`:52 明确写"权威源是
[`engine-signatures.json`](../../MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json)（424 个 action）"，
因为函数工具箱与 AI 的工具表都以它为**唯一数据源**，而 `list_functions` 只返回函数名、不含参数
（`tools/engine-signatures.mjs`:11-14）。它的 `file` 字段记录了每条是从哪个 `*_api.cpp` 刮出来的
（例如 `list_functions` → `introspect_api.cpp`）。

**它的漂移检查是自动化的**，也是本文里唯一一条进 `npm run check` 的引擎侧断言：

```powershell
node MF_UI/MFMath.UI.Vue/tools/engine-signatures.mjs --check     # 或 npm --prefix MF_UI/MFMath.UI.Vue run check:signatures
```

本机实测输出（exit 0）：

```
引擎签名对账：源码 register_function 424 条 / 表 424 条
提示（不判定失败）124 处，--verbose 看全部
✓ 无漂移：函数集合一致，且源码读取的每个参数都在表里、必填/可选不矛盾
```

判据是**单向**的（`engine-signatures.mjs`:136-147）：只有"函数集合不一致 / 源码明确读了某参数而表里没有 /
源码按必填读而表里写成可选"三类判失败；"表里有、源码没刮到"只作提示 —— 因为 `args["k"]` 与域内辅助函数
读参数的方式刮取器看不见，放宽会产出上百条假差异（脚本注释记了前两版都栽在这里）。

### 5.1 别把三个数混起来

| 数 | 是什么 | 出处 |
| --- | --- | --- |
| **424** | 引擎注册的 **action** 数 | §5 ①②③ |
| **415 / 139** | 前端**界面模式**数 / 参数弹窗字段数（`ENGINE_MAP` / `ENGINE_VAR_SPECS`，含 `engineMapExtra.js` 的增量） | `node -e "import('./src/lib/engine/engineMap.js')..."` → 415 / 139；`engineMap.js`:8-10 说明 324/19 是**旧版快照** |
| **2** | DLL 导出函数数 | §2.2 |

三者互不相等是正常的：一个 action 可以被多个界面模式复用（例如 `exp_complex` 既映射「复数运算」又映射「复指数」，
`engineMap.js` 的 `RAW_MAP`），一个模式也可能没有引擎实现。前端侧的可达性守门见
[`../ui/ENGINE-BINDING.md`](../ui/ENGINE-BINDING.md) 与 [`TESTS.md`](TESTS.md)。

---

## 6. 构建：三步里的第一步

### 6.1 前置依赖

| 用途 | 需要 | 出处 |
| --- | --- | --- |
| 引擎 | CMake ≥ 3.16、Visual Studio（C++ 工具链）、vcpkg 装 `symengine` `flint` `gmp` `mpfr` `eigen3` | `CMakeLists.txt`:1；[`../../README.md`](../../README.md):105 |
| 前端 | Node.js ≥ 18（`npm`） | [`../../README.md`](../../README.md):106 |
| 宿主 | Rust（`cargo`）+ WebView2 Runtime | [`../../README.md`](../../README.md):107；[`../../MFMath.Host.Rust/docs/ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md) |

两个缓存变量有**硬编码默认值**（都是本机 vcpkg 路径，换机器必须用 `-D` 覆盖）：

| 变量 | 默认值 | 出处 | 本机 CMakeCache 实际值 |
| --- | --- | --- | --- |
| `MF_SYMENGINE_ROOT` | `C:/Users/fsafsafsa/vcpkg/installed/x64-windows` | `CMakeLists.txt`:18-20 | 同默认值 |
| `MF_EIGEN_INCLUDE_DIR` | `C:/Users/fsafsafsa/vcpkg/installed/x64-windows/include/eigen3` | `CMakeLists.txt`:13-15 | 同默认值 |

### 6.2 三步顺序不可颠倒（引擎是第 1 步）

[`../../README.md`](../../README.md):109-131 的三步构建，本文只负责第 1 步：

```powershell
# 1) 引擎
cmake -S MF_Mathematics -B MF_Mathematics/build -G "Visual Studio 18 2026" -A x64 `
      -DMF_SYMENGINE_ROOT="$env:VCPKG_ROOT\installed\x64-windows" `
      -DMF_EIGEN_INCLUDE_DIR="$env:VCPKG_ROOT\installed\x64-windows\include\eigen3"
cmake --build MF_Mathematics/build --config Release --target mf_mathematics

# 2) 前端（B 面，见 ../../AGENTS.md §2；入口 MF_UI/MFMath.UI.Vue/package.json）
npm --prefix MF_UI/MFMath.UI.Vue install
npm --prefix MF_UI/MFMath.UI.Vue run build

# 3) 宿主（→ MFMath.Host.Rust/docs/ACCEPTANCE.md；README 里那行 dotnet 构的是已废弃宿主）
```

| 事实 | 值 / 出处 |
| --- | --- |
| 生成器字符串 | `"Visual Studio 18 2026"`，平台 `x64` —— 本机 `build/CMakeCache.txt` 的 `CMAKE_GENERATOR:INTERNAL` / `CMAKE_GENERATOR_PLATFORM:INTERNAL` 实测值，与 README 的命令一致 |
| 为什么顺序不能改 | 宿主 csproj 用相对路径引用引擎产物与前端的 `dist`，`CopyToOutputDirectory=PreserveNewest` 自动跟随 → 顺序必须是「引擎 → 前端 → 宿主」（[`../../README.md`](../../README.md):130-131） |
| 输出目录 | `CMAKE_RUNTIME_OUTPUT_DIRECTORY=${CMAKE_BINARY_DIR}/bin`、`CMAKE_ARCHIVE_OUTPUT_DIRECTORY=${CMAKE_BINARY_DIR}/lib`（`CMakeLists.txt`:9-10）；MSVC 多配置会再套一层 `Release\` |
| 关键产物 | `build/bin/Release/mf_mathematics.dll`（3,379,712 字节）、`build/lib/Release/mf_mathematics_core.lib`（140,059,286 字节）、`build/bin/Release/` 下 5 个运行时 DLL |
| `--target mf_mathematics` | **只建 DLL 与它依赖的 core，不建测试与探针** —— 所以第 1 步之后还不能直接 `ctest` |

**并发互斥**（[`../../AGENTS.md`](../../AGENTS.md) §4）：构建前把临时目录指到仓库内，避免与别的会话抢
`%TEMP%`：`$env:TEMP="$repo\.tmp-build"; $env:TMP=$env:TEMP`。`MF_Mathematics/build/` 已进 `.gitignore`，
**不要提交编译产物**（[`../../AGENTS.md`](../../AGENTS.md) §6；`.gitignore` 说明理由是"每个版本 21.8 MB 二进制会让历史迅速膨胀"）。

---

## 7. 跑测试：两条命令 + 一条守门

```powershell
# 1) 建全量（含 19 个测试/探针目标）——不能只建 mf_mathematics
cmake --build MF_Mathematics/build --config Release

# 2) 16 个 CTest 用例
ctest --test-dir MF_Mathematics/build -C Release --output-on-failure

# 3) 守门断言（§4.2）
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'      # .value.count 应为 424
```

**本机实测（2026-10-07）**：`100% tests passed out of 16`，`Total Test time (real) = 2.88 sec`；
逐个用例均 `Passed`（`limits` 0.16s … `symbolic_contract` 0.75s、`probe_bugs` 0.08s）。

### 7.1 19 个目标 ≠ 16 个用例

| 划分 | 数 | 内容 | 复跑 |
| --- | --- | --- | --- |
| `add_executable` | **19** | 15 个 `test_*.cpp` + 4 个 `probe_*.cpp` | `(Select-String MF_Mathematics/CMakeLists.txt -Pattern 'add_executable\(').Count` |
| `add_test`（CTest 注册） | **16** | 15 个 `test_*` + `probe_bugs` | `ctest --test-dir MF_Mathematics/build -C Release -N` → `Total Tests: 16` |
| 未注册进 CTest 的探针 | **3** | `probe_call`（`:386`）、`probe_solve_safety`（`:371`）、`probe_scan`（`:394`） | 三者都没有配套的 `add_test` |

未注册是**有意的**：它们是"人工核对/诊断"探针而非回归（`probe_call.cpp`:1 注释、
`CMakeLists.txt`:384-385、`:393`）。逐个用例的判据与怎么加一条，见 [`TESTS.md`](TESTS.md) §2–§6。

### 7.2 测试为什么同时链两个目标

`CMakeLists.txt`:207 这类写法是 `target_link_libraries(test_x PRIVATE mf_mathematics mf_mathematics_core ...)`：
测试既可以用 C ABI（走 DLL，和宿主同一条路），也可以直接调 core 的 C++ 函数。
`probe_bugs` / `probe_solve_safety` / `probe_scan` 只链 core（`:356`、`:372`、`:395`），
`probe_call` 链两个（`:387`）。

### 7.3 跑不出来时先看环境

| 现象 | 分类 | 判据 / 处置 |
| --- | --- | --- |
| `mf_mathematics.dll` 找不到 / 启动即失败 | **环境没准备好** | 5 个运行时 DLL 是否与 exe 同目录（`CMakeLists.txt`:155-161 的 POST_BUILD 负责）；`MF_SYMENGINE_ROOT` 是否指对 |
| CMake 配置失败、找不到 `symengine.lib` | **环境没准备好** | 依赖没装或路径没覆盖；`CMakeLists.txt`:139-144 是用 `${MF_SYMENGINE_ROOT}/lib/...` 拼出来的 |
| `probe_call.exe list_functions` 能跑但 `count` < 424 | **产品缺陷（构建配置）** | `/WHOLEARCHIVE` 没生效或 core 被裁；先确认 `CMakeLists.txt`:182-183 未被动过，再确认链接的是新产物 |
| CTest 某条用例失败 | **产品缺陷 或 用例判据错**（必须二选一，不许含糊） | 用 [`TESTS.md`](TESTS.md) §8 的三分类流程；不许写成"大概环境问题" |
| `engine-signatures.mjs --check` 报漂移 | **产品缺陷（契约漂移）** | 源码加了 action / 改了参数名而表没跟上；`--write` 重建后人工核对（脚本 `:199-200` 的输出就是这么写的） |

⚠ `probe_call` 的失败退出码语义：**参数非法/缓冲区不足 → 3**（`probe_call.cpp`:86-89`），
`--has` 的否 → 1（`:62`），用法错误 → 2（`:28`）。所以"退出码 0"只说明进程跑通，
**判定 424 必须看 `.value.count`**——这也是 [`../../AGENTS.md`](../../AGENTS.md):36 那条验收命令的读法。

---

## 8. 与本层其它文档、以及上下游的接口

| 你想知道 | 读 |
| --- | --- |
| 某个 action 的键名 / 必填参数 | [`CONTRACT.md`](CONTRACT.md)；**权威源**是签名表 `params` / `required` / `optional` |
| 12 个学科模块各有多少 action | [`MODULES.md`](MODULES.md)（由签名表生成，不手抄） |
| 全 424 个函数怎么在界面上"直接调用" | [`../ui/ENGINE-BINDING.md`](../ui/ENGINE-BINDING.md)、函数工具箱 |
| 前端怎么把界面接到引擎（`Dispatch` 那一段） | [`../../README.md`](../../README.md):64-82 的架构图、[`../link/README.md`](../link/README.md) |
| 宿主侧的 FFI 封装 | [`../../MFMath.Host.Rust/src/engine.rs`](../../MFMath.Host.Rust/src/engine.rs):1-8（注释也写着"引擎只有两个 C ABI 导出"）、`:63-73` 用 `GetProcAddress` 取这两个符号 |
| 谁在什么时候会改引擎 | [`../PROJECT-BOARD.md`](../PROJECT-BOARD.md)（C 面）、[`../OPEN-ITEMS.md`](../OPEN-ITEMS.md) |

---

## 已知的文档债

以下都是**本次以代码为准核对时发现的"注释/旧文档说 X、实际是 Y"**。按 [`../../AGENTS.md`](../../AGENTS.md) §5，
逐条给出 `文件:行` 与复跑方式；**不改代码，只登记**。

| # | 位置 | 注释/文档说 | 代码/实测是 | 复跑 |
| --- | --- | --- | --- | --- |
| 1 | `MF_Mathematics/CMakeLists.txt`:181 | "守住它的是对 `list_functions` 的 `count == 424` 断言（**见 tests/**）" | `MF_Mathematics/tests/` 下**没有任何** 424 断言；全 `MF_Mathematics` 树 grep `424` 只命中 `CMakeLists.txt`:178、`:181` 两处**注释**。自动化侧只有 `MF_UI/MFMath.UI.Vue/tests/cdp-ai.mjs`:409 的 `toolFacts.count >= 300`（阈值不是 424，且要起宿主才跑） | `Get-ChildItem MF_Mathematics -Recurse -File -Include *.cpp,*.h,*.hpp \| Select-String 424` → 无命中 |
| 2 | `MF_Mathematics/introspect_api.cpp`:6 | "如 Vue 的 `ENGINE_MAP`，**324 条**" | `ENGINE_MAP` 对外导出是 **415** 条（324 只是 `RAW_MAP` 旧快照）；`engineMap.js`:8-10 自己写明"数量别写在这里"并给了 415/139 | `cd MF_UI/MFMath.UI.Vue; node -e "import('./src/lib/engine/engineMap.js').then(m=>console.log(Object.keys(m.ENGINE_MAP).length))"` → 415 |
| 3 | [`../../README.md`](../../README.md):180 | 引擎源码"（仅 C++，**110 个 `.cpp`**）" | 110 是**文件数**；真正进产物的编译单元是 **103** 个（core `:29-130` 的 102 个 + `api.cpp`）。未编译的 7 个：`demo/main.cpp`、`demo/eigen_test.cpp`、`numerical/{interpolation,matrix,numerical,ode,optimization}_core.cpp` —— 后 5 个是 **pybind11 胶水层**（各自含 `PYBIND11_MODULE`，如 `numerical/numerical_core.cpp`:77） | §1 的差集脚本；`Select-String MF_Mathematics\numerical\*_core.cpp -Pattern PYBIND11_MODULE` |
| 4 | `MF_Mathematics/CMakeLists.txt`:220、`:276` | "库的链接是 PRIVATE，所以这里**必须**显式再链一次 symengine/flint/gmp/mpfr" | `mf_mathematics_core` 对这四个库是 **PUBLIC**（`:139`），而同为"链两个目标"的 `test_number_theory`（`:233-234`）没有再链也能构建并运行通过（16/16）。**未证实**：我没有逐个单独构建目标去验证"去掉重复项后仍可链接"，故不判定注释是错的，只登记"必须"这个措辞与 PUBLIC 传播不一致 | `Select-String MF_Mathematics/CMakeLists.txt -Pattern 'PRIVATE mf_mathematics mf_mathematics_core'` |
| 5 | [`../../README.md`](../../README.md):261-263 | "唯一有意保留的是 `MF_Mathematics/tests/accuracy/`（28 个 `.py`，2180 条）" | 该路径在 **v2.0 树里不存在**（`git ls-files` 不匹配，磁盘上也没有 `accuracy` 目录）。同一事实已由 [`TESTS.md`](TESTS.md) §5.1 与 §「已知的文档债」第 2 条登记，本文不重复判定 | `git ls-files MF_Mathematics/tests/accuracy` → 空 |
| 6 | [`../../README.md`](../../README.md):126-137、`:97-99` | 三步构建第 3 步与运行命令写的是 **`dotnet build MFMath.Host/...`** 与 `MFMath.exe` | 那是**已废弃的 C# 宿主**；现役宿主是 `MFMath.Host.Rust/`。README 自己在 `:6-15`、`:97-99` 已声明这一段未重写，属**已登记**的过期描述 | [`../../AGENTS.md`](../../AGENTS.md) §2；[`../../MFMath.Host.Rust/docs/ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md) |

**本文没有验证的部分（未证实，别当结论用）**：

| 项 | 为什么没证实 | 怎么才能证实 |
| --- | --- | --- |
| "去掉 `/WHOLEARCHIVE` 后 `count` 会掉到多少" | 需要重配一次构建，会动 `build/` 产物，与并行会话冲突（[`../../AGENTS.md`](../../AGENTS.md) §4） | 在**副本**的构建目录里配 `-DCMAKE_...` 去掉该选项后跑 §4.2 命令；预期 `count` 远小于 424，但具体值未测，**本文不写** |
| `mf_mathematics_core.lib` 里到底有多少个 `.obj` | `dumpbin /linkermember` 未跑 | 跑一次并记录，可与"core 列了 102 个源文件"对照 |
| 非 MSVC 工具链（clang-cl / MinGW）能否构建 | 未在非 MSVC 上配过；`/WHOLEARCHIVE`、`/external:` 都是 MSVC 专有写法（`CMakeLists.txt`:146-150、`:171-184`） | 在非 MSVC 上跑 §6.2，把 `if(MSVC)` 分支之外的替代方案记下来 |
