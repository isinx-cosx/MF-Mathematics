# 引擎测试资产（`MF_Mathematics/`）

> **本文只回答一个问题：引擎的测试资产有哪些、怎么加一条、守门断言是什么？**
>
> 与同层其它文档的分工：
> - [`README.md`](README.md) —— 两个构建目标、C ABI 恰好两个导出、构建入口（本文只讲怎么**验**，不讲怎么**建**）；
> - [`CONTRACT.md`](CONTRACT.md) —— args JSON 形状与键名契约（本文不重复键名，只讲哪条用例钉住了它）；
> - [`MODULES.md`](MODULES.md) —— 12 个学科模块的 action 清单与边界（本文只讲用例覆盖到哪些模块）；
> - [`BOUNDARIES.md`](BOUNDARIES.md) —— 如实的能力边界与 `NOT_EXPOSED` 口径（本文只讲"算不出来"该由哪条用例守）；
> - [`NUMERIC.md`](NUMERIC.md) —— 容差与精度策略（本文不解释容差怎么定，只讲用例里容差写在哪儿）。

**证据基线**：2026-10-07 10:39 本机实测。被测产物 `MF_Mathematics/build/bin/Release/mf_mathematics.dll`
（LastWriteTime 2026-10-06 05:43:00）、`probe_call.exe`（05:43:03）。`build/` 不入 git
（[`AGENTS.md`](../../AGENTS.md) §6），故每个数字都附复跑命令——**换产物就要重跑，别把本文数字当现状**。

---

## 1. 先纠正一个划分：两套账不能混在一句话里

`MF_Mathematics/tests/` 下同时存在两种划分，它们**不是一个维度**：

| 划分 | 口径 | 实测值 | 依据 |
| --- | --- | --- | --- |
| 按**可执行目标** | `add_executable` 条数 | **19** | `MF_Mathematics/CMakeLists.txt`；`(Get-ChildItem tests -Filter *.cpp).Count` = 19 |
| 按**是否进 CTest** | `add_test` 条数 | **16** | `CMakeLists.txt`；`ctest -N` 报 `Total Tests: 16` |

两个数字不能相加。正确表述：

> **19 个可执行目标 = 15 个 `test_*.cpp` + 4 个 `probe_*.cpp`；其中 16 个注册进 CTest
> （15 个 `test_*` 全部 + `probe_bugs`）；另外 3 个探针 `probe_solve_safety`、`probe_call`、
> `probe_scan` 没有 `add_test`。**

```powershell
$T = "MF_Mathematics\tests"
(Get-ChildItem $T -Filter 'test_*.cpp'  -File).Count                                       # 15
(Get-ChildItem $T -Filter 'probe_*.cpp' -File).Count                                       # 4
(Select-String -Path MF_Mathematics\CMakeLists.txt -Pattern '^\s*add_test\(').Count         # 16
(Select-String -Path MF_Mathematics\CMakeLists.txt -Pattern '^\s*add_executable\(').Count   # 19
ctest --test-dir MF_Mathematics/build -C Release -N                                        # Total Tests: 16
```

> 📌 **"16 个 CTest 套件 + 4 个探针 = 19 个可执行目标"这句话是错的**：它把两套划分混在一句话里相加，
> 得数少 1。该错误曾出现在根 README，更正过程见 [`../PROJECT-BOARD.md`](../PROJECT-BOARD.md):330-332。
> 现在 [`../../README.md`](../../README.md):181 已是正确划分，但同文件 :149 / :163 仍写"16 个 CTest 套件"
> ——见文末文档债第 1 条。

**分叉的原因**：`probe_bugs` 自称"探针"（`probe_bugs.cpp`:1）却 `add_test` 进了 CTest（`CMakeLists.txt`:367），
所以它在两套账里；那 3 个没进 CTest 的探针则是**人工诊断工具**，判据是"打印出什么给人看"。

---

## 2. 19 个可执行目标

`test_*` 是**回归套件**（判据：退出码 0 = 全过）；`probe_*` 除 `probe_bugs` 外是**诊断工具**
（判据：人读输出）。产物统一出到 `build/bin/<Config>/`（`CMakeLists.txt`:9），
SymEngine 运行时 DLL 由 core 的 POST_BUILD 拷到同目录（`CMakeLists.txt`:155-160）。

| 目标 | 链接 | CTest 名 | 用途（出处） |
| --- | --- | --- | --- |
| `test_limits` | DLL + core + symengine 系 | `limits` | 极限契约；"期望值全部来自数学事实，不来自当前实现输出"（`test_limits.cpp`:8） |
| `test_complex_grid` | DLL + core + symengine 系 | `complex_grid` | `complex_grid` 返回结构/索引布局/null-nan 语义/点数上限（`test_complex_grid.cpp`:1） |
| `test_number_theory` | DLL + core | `number_theory` | 内核 + JSON 分发层（`test_number_theory.cpp`:1） |
| `test_algebraic_topology` | DLL + core | `algebraic_topology` | homology / cohomology（`test_algebraic_topology.cpp`:1） |
| `test_algebra` | DLL + core | `algebra` | combinatorics + number_theory 内核（`test_algebra.cpp`:1） |
| `test_numerical` | DLL + core + Eigen 头 | `numerical` | 积分/ODE/插值/误差/优化（`test_numerical.cpp`:1） |
| `test_functional_analysis` | DLL + core + Eigen 头 | `functional_analysis` | functional_analysis 包（`test_functional_analysis.cpp`:1） |
| `test_calculus` | DLL + core + symengine 系 | `calculus` | 含"求导自证"：对积分结果求导再与原式数值比对（`CMakeLists.txt`:274-276） |
| `test_real_analysis` | DLL + core | `real_analysis` | differentiability（`test_real_analysis.cpp`:1） |
| `test_linear_algebra` | DLL + core + Eigen 头 | `linear_algebra` | linear_algebra 包（`test_linear_algebra.cpp`:1） |
| `test_harmonic_analysis` | DLL + core | `harmonic_analysis` | harmonic_analysis 包（`test_harmonic_analysis.cpp`:1） |
| `test_measure_theory` | DLL + core | `measure_theory` | measure_theory 包（`test_measure_theory.cpp`:1） |
| `test_probability` | DLL + core | `probability` | probability 包（`test_probability.cpp`:1） |
| `test_complex_analysis` | DLL + core | `complex_analysis` | complex_analysis 包（`test_complex_analysis.cpp`:1） |
| `test_symbolic_contract` | DLL + core + symengine 系 | `symbolic_contract` | 实际反馈过的符号缺陷逐条钉住（`test_symbolic_contract.cpp`:5）；直接包含 `special_numeric.h` 做数值自检（`CMakeLists.txt`:346） |
| `probe_bugs` | **只链 core** + symengine 系 | `probe_bugs` | 边界对抗探针；直接 `#include` 各模块内部头（`probe_bugs.cpp`:8-24） |
| `probe_solve_safety` | 只链 core + symengine 系 | — | 实证 `SymEngine::solve` 对各类方程是否安全；崩溃点即证据（`CMakeLists.txt`:369-370） |
| `probe_call` | DLL + core | — | 通用调用探针；只 `#include "api.h"`（`probe_call.cpp`:18），走与 C#/JS 相同的 C ABI 路径 |
| `probe_scan` | 只链 core + symengine 系 | — | 数值扫描内部行为诊断，非回归（`CMakeLists.txt`:393） |

两个要点：

1. **只有走 C ABI 的目标才链 DLL**（`mf_mathematics`）。链 core 的目标绕过导出面、能直接看内部行为，
   所以 `probe_bugs` / `probe_scan` / `probe_solve_safety` 的结论**不能**当"调用方看到的行为"的证据，
   `probe_call` 才能（`probe_call.cpp`:11-12）。
2. **只链 core 的目标不需要 `/WHOLEARCHIVE`** —— 那是导出 DLL 的专属坑（`CMakeLists.txt`:196-198`）。

**期望值来源分三类**（`Select-String '期望值取自 Python 版'` 得 12）：

| 来源 | 条数 | 哪些 |
| --- | --- | --- |
| v1 Python 版 `self_test()` 的断言 | **12** | 12 个 `test_*.cpp` 头部第 3 行 |
| 数学事实（非"当前实现输出什么"） | 1 | `test_limits`（`test_limits.cpp`:8） |
| 实际反馈的缺陷 + 契约 | 2 | `test_complex_grid`、`test_symbolic_contract` |

⚠ 前一类有个**已发生的后果**：v1 的 Python 后端（277 个 `.py`）已删除（[`../../README.md`](../../README.md):257-259、
[`../OPEN-ITEMS.md`](../OPEN-ITEMS.md):120），那 12 份用例里的期望值现在是**冻结的字面量**，无法回到原始出处
重算；要改这些数字只能靠独立参考实现（见 §5），不能靠"v1 当时算的是这个"。

---

## 3. CTest 注册的 16 个用例

`add_test` 的 `NAME` 与目标名不必相同（`ctest -R` 匹配的是 `NAME`）；本仓库目前唯一不同的是
`test_limits` → `limits`。

| # | 用例名 | 目标 | `add_test` 位置 |
| --- | --- | --- | --- |
| 1 | `limits` | `test_limits` | `CMakeLists.txt`:216 |
| 2 | `complex_grid` | `test_complex_grid` | :231 |
| 3 | `number_theory` | `test_number_theory` | :239 |
| 4 | `algebraic_topology` | `test_algebraic_topology` | :247 |
| 5 | `algebra` | `test_algebra` | :255 |
| 6 | `numerical` | `test_numerical` | :263 |
| 7 | `functional_analysis` | `test_functional_analysis` | :271 |
| 8 | `calculus` | `test_calculus` | :288 |
| 9 | `real_analysis` | `test_real_analysis` | :296 |
| 10 | `linear_algebra` | `test_linear_algebra` | :304 |
| 11 | `harmonic_analysis` | `test_harmonic_analysis` | :312 |
| 12 | `measure_theory` | `test_measure_theory` | :320 |
| 13 | `probability` | `test_probability` | :328 |
| 14 | `complex_analysis` | `test_complex_analysis` | :336 |
| 15 | `symbolic_contract` | `test_symbolic_contract` | :353 |
| 16 | `probe_bugs` | `probe_bugs` | :367 |

**没有任何 `set_tests_properties`（除 CMake 自动生成的 `_BACKTRACE_TRIPLES`）、没有 `LABELS`、
没有 `WILL_FAIL`、没有超时设置。** 判据完全落在进程退出码上。所以：

- 套件必须**始终**以非 0 表示失败——`test_limits.cpp`:173-174 是范式
  （打印 `%d 项检查,%d 项失败`，再 `return g_failures == 0 ? 0 : 1`）；
- ⚠ `probe_bugs` 返回的是**失败计数本身**（`probe_bugs.cpp`:35-37、:223 `return bad;`），不是 0/1。计数 > 255 时
  Windows 退出码截断到低 8 位，**理论上存在"256 个失败显示成 0"的窗口**——此边界从代码读出，**未实测**
  （证伪：造一个 `bad` ≥ 256 的输入）。当前失败点是个位数，触发不到。

```powershell
ctest --test-dir MF_Mathematics/build -C Release --output-on-failure
ctest --test-dir MF_Mathematics/build -C Release -R symbolic_contract --output-on-failure   # 单条
```

---

## 4. 守门断言：`/WHOLEARCHIVE` 与 `count == 424`

这是本仓库**最重要的一条测试**，因为它守的失效是**静默**的。

| 环节 | 机制 | 出处 |
| --- | --- | --- |
| 注册方式 | 每个 `*_api.cpp` 靠一个**没有外部引用的全局对象**注册（`struct Registrar { Registrar(){ register_all(); } };` + 一个 `const Registrar` 全局量） | `CMakeLists.txt`:174-177 |
| 静态库陷阱 | 链接器只抽取"解决了未定义符号"的目标文件；注册器不被任何符号引用 → 整个 `*_api.cpp` 被丢弃 → 注册表为空 | `CMakeLists.txt`:177-180 |
| 防它 | 导出 DLL 必须强制全量纳入 core：`target_link_options(mf_mathematics PRIVATE "/WHOLEARCHIVE:$<TARGET_FILE:mf_mathematics_core>")` | `CMakeLists.txt`:182-183 |
| 失效的样子 | DLL 照常加载、`function_exists` 照常能调，**只是每个 action 都返回"未找到函数: xxx"** | `CMakeLists.txt`:179-180 |
| 守门断言 | `list_functions` 的 `count` 必须是 **424** | [`../../README.md`](../../README.md):153-154、:196-199 |

**实测（2026-10-07 10:39，`build/bin/Release/probe_call.exe`）**：

```powershell
cd MF_Mathematics\build\bin\Release
.\probe_call.exe list_functions '{}'   # 或 --list；两种写法输出逐字节相同（实测 identical = True）
```

```json
{"isError":false,"value":{"count":424,"functions":["abs_value","absolute_convergence", ... ]}}
```

| 量 | 实测值 |
| --- | --- |
| `value.count` | **424** |
| `value.functions` 数组长度 | **424** |
| `value.functions` 去重后长度 | **424** |
| `isError` | `false` |

两个**踩过的坑**：

1. **`count` 在 `.value` 下。** PowerShell 里 `$j = (... | ConvertFrom-Json); $j.count` 返回 **1** ——
   PowerShell 给任何对象都挂了自带的 `Count` 属性，把 JSON 的 `count` 遮蔽了。必须写 `$j.value.count`。
   （本文作者第一次就把它读成了 1。）
2. **进程退出码不能当判据。** 调不存在的 action（`.\probe_call.exe no_such_action '{}'`）返回
   `{"isError":true,"value":"未找到函数: no_such_action"}`，**退出码是 0**（`probe_call.cpp`:86-91）。
   判据必须打在 JSON 的 `isError` / `count` 上。

`probe_call` 三个入口（`probe_call.cpp`:22-29 用法、:48-63 分支）：`probe_call <函数名> [args_json]` 调该函数并
原样打印返回 JSON（`math_call` 返回 < 0 → 退出码 3）；`--list` 等价于 `probe_call list_functions '{}'`；
`--has <函数名>` 打印 `yes` / `no` 并以 0 / 1 退出。`args_json` 支持 `@文件路径` 从文件读 JSON（`:65-84`）
——命令行传含空格/引号/竖线的 JSON 会被 shell 拆开，**之前因此把 5 条正常用例误判成失败**（`:66-67` 注释所述）。

⚠ `count == 424` 目前**靠人看**，没有自动化脚本把它接进 `ctest`（[`../../AGENTS.md`](../../AGENTS.md) §2、
[`../PROJECT-BOARD.md`](../PROJECT-BOARD.md):69）——**最关键的守门断言没有机器化的"不通过就红"**。

---

## 5. 准确性套件（2180 条）

### 5.1 它在哪 —— 一个必须说清的事实

⚠ **`MF_Mathematics/tests/accuracy/` 在本仓库（v2.0 树）里不存在。**

| 断言 | 证据（2026-10-07 实测） |
| --- | --- |
| v2.0 树下没有 `accuracy/` | 本树内 `Get-ChildItem -Directory -Recurse -Filter accuracy` 无命中；`git ls-files --error-unmatch MF_Mathematics/tests/accuracy` → `did not match any file(s) known to git` |
| 它在 **v1 树** | `Multifunctional系列\Multifunctional-Mathematics\MF_Mathematics\tests\accuracy` |
| 官方说法 | [`../STATUS-and-ROADMAP.md`](../STATUS-and-ROADMAP.md):349："准确性套件目前仍在 v1 树" |

[`../../README.md`](../../README.md):261-263 把它写成 `MF_Mathematics/tests/accuracy/`：那一段的语境是
"与 v1 的关系"（讲 v1 树里保留了什么），**在 v1 树里是对的**，但读者在 v2.0 树下按该相对路径去找会一无所获。
见文档债第 2 条。

### 5.2 它是什么 —— 测试资产，不是运行时后端

| 特征 | 证据 |
| --- | --- |
| 28 个 `.py` | `(Get-ChildItem -File -Filter *.py).Count` = 28（v1 树的 accuracy 目录） |
| 14 个用例域文件 | `cases_*.py` 计 14：`cases_core/algebra/algebraic_topology/calculus/complex_analysis/extras/functional_analysis/harmonic_analysis/linear_algebra/measure_theory/number_theory/numerical/probability/real_analysis` |
| 直接 `ctypes.CDLL` 加载 DLL 调 `math_call`；**可对任意引擎 DLL 跑** | `harness.py`:71-74、`:46` `DLL = os.environ.get("MF_ACC_DLL") or ENGINE_DLL` |
| 默认指向 v2.0 的构建产物（绝对路径） | `harness.py`:41-44 |

**所以它是"可以对任意引擎 DLL 运行的测试资产"，不是"让 v1 跑起来的 Python 后端"。**
v1 的 Python 后端 277 个 `.py` 已删（[`../../README.md`](../../README.md):257-259），
只有这份 `accuracy/` 被有意保留（[`../OPEN-ITEMS.md`](../OPEN-ITEMS.md):120）。

### 5.3 怎么跑

```powershell
$V1ACC = "..\Multifunctional-Mathematics\MF_Mathematics\tests\accuracy"
python "$V1ACC\run_accuracy.py"                 # 全部域
python "$V1ACC\run_accuracy.py" number_theory   # 单域
python "$V1ACC\run_accuracy.py" --coverage      # 只看覆盖缺口
python "$V1ACC\run_accuracy.py" --json "$V1ACC\report.json"
python "$V1ACC\consistency.py"                  # 交叉一致性 A~E
python "$V1ACC\smoke.py"                        # 基座自检
```

（命令形状源自 v1 `accuracy/README.md`:51-60 与 `run_accuracy.py`:26-31 的 argparse；
**本机未执行**，见 5.5。）

**`MF_ACC_DLL` 的现状：不再是必填。** `harness.py`:46 已有默认值（v2.0 树的
`build/bin/Release/mf_mathematics.dll` 绝对路径），[`../MIGRATION-GAPS.md`](../MIGRATION-GAPS.md):322-324
也这么写。它现在的用途是**覆盖**：并行修复时各自指向自己的构建目录（v1 `accuracy/README.md`:44-47）。

引擎侧另有两个读同一环境变量的诊断脚本（不属 CTest，也不是准确性套件）：
`tools/stress_scan.py`:290 与 `tools/verify_hang_fixes.py`:110 的 `--dll` 默认取 `MF_ACC_DLL`，
否则取 `build/bin/Release/mf_mathematics.dll`（两者分别在 `:42`、`:31` 定义）。

### 5.4 "2180" 这个数字的出处

v1 树 `accuracy/report.json` 与 `_failures.txt`（最近一次运行的机器可读报告）：

| 字段 | 值 |
| --- | --- |
| `totals.ok` / `fail` / `err` / `skip` | **2180** / 0 / 0 / 0 |
| `totals.covered_actions` / `total_actions` | **424 / 424** |
| `totals.seconds` / `failures` | 43.71 / `[]` |

14 个域的 `cases` 之和 = **2180**（180+137+171+159+142+127+146+108+368+100+82+117+142+201），
与 `totals.ok` 一致，可交叉核对。

### 5.5 本文**没有**验证的部分（未证实）

| 未证实项 | 为什么 | 怎么才能证实 |
| --- | --- | --- |
| 2180 条**现在**是否仍全过 | 只读了 `report.json`，**没真跑**（未确认本机 Python 与 mpmath/sympy/numpy/scipy 可用） | 按 5.3 跑 `run_accuracy.py`，看新 `report.json` 的 `totals` |
| 那份 `report.json` 测的是**哪个** DLL | 文件里**没有**被测 DLL 路径、没有时间戳（读全文确认） | 重跑时 `--json` 落一份带时间戳的报告；或给 harness 加一条"把 `DLL` 写进报告" |

⚠ 前两条不是小瑕疵：`harness.py`:37-40 的注释记录过一次**静默测错对象**（默认值曾指向 v1 树里旧引擎的
DLL，"命令跑得通、数字也在动，测的却不是当前引擎"）。报告不带被测对象标识，等于把那个坑留在了报告这一层。

---

## 6. 怎么加一条 CTest 用例

### 6.1 最小模板

每个套件都是同一段五步式（以 `test_number_theory` 为最简样板，`CMakeLists.txt`:233-239）：

```cmake
add_executable(test_foo tests/test_foo.cpp)
target_link_libraries(test_foo PRIVATE mf_mathematics mf_mathematics_core)
target_include_directories(test_foo PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_foo PRIVATE /utf-8 /W4)
endif()
add_test(NAME foo COMMAND test_foo)
```

### 6.2 四个必须记住的细节

| 细节 | 说明 | 出处 |
| --- | --- | --- |
| **`/utf-8` 不能省** | 源码含中文字面量（错误信息、打印），缺它 MSVC 会按本地代码页解释 | 全部套件的 `target_compile_options` |
| **用 SymEngine / Eigen 就得自己再加一次** | 库链接是 PRIVATE、不传递：SymEngine 需显式加四个 `.lib` **和** `include` 目录（`:274-287`、`:338-353`）；Eigen 需加 `${MF_EIGEN_INCLUDE_DIR}`（`:259`、`:267`、`:300`） | `CMakeLists.txt` |
| **`NAME` 与目标名解耦** | `ctest -R` 匹配 `NAME`，不是目标名 | `CMakeLists.txt`:206 / `:216` |

### 6.3 源文件里必须遵守的形状

以 `test_limits.cpp` 为范式（`:23-33`、`:173-175`）：

```cpp
static int g_checks = 0;
static int g_failures = 0;

#define CHECK(cond, msg) do { ++g_checks; if (!(cond)) { ++g_failures; \
    std::printf("[FAIL] %s\n", msg); } } while (0)

int main() {
    // ... 各 test_xxx() ...
    std::printf("\n%d 项检查,%d 项失败\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
```

**判据纪律（三条纪律 ① 的引擎版）**：期望值必须来自**独立参考实现或数学事实**——`test_limits.cpp`:8 写死了
这条（"期望值全部来自数学事实，不来自'当前实现输出什么'"）；反面口径见 v1 `accuracy/README.md`:14-16、:81：
期望值来自 mpmath/sympy/numpy/scipy，**且不要为了让用例变绿而放宽期望值**。

### 6.4 加完必须做的两件事

1. **确认它真的会失败。** 恒真的断言等于没写：把被测行为故意改错，确认 `ctest -R foo` 变红，再改回
   （[`../ui/CHECKS.md`](../ui/CHECKS.md) 把这条叫"守卫必须验证过会失败"）。
2. **确认它进了 CTest**：`-N` 的 `Total Tests` 应从 16 变 17。

**探针不进 CTest 的情形**：目标若是"打印内部状态给人看"（像 `probe_scan`），就**不要** `add_test` ——
没有稳定通过判据的用例进 CTest 只会污染全绿信号（`CMakeLists.txt`:393 注释写明"非回归"）。

---

## 7. 怎么加一条准确性用例

改的是 **v1 树**里的文件（见 §5.1），流程写在 v1 `accuracy/README.md`:96-99：

```powershell
python "$V1ACC\extract_signatures.py"   # 从 C++ 注册源码静态提取参数契约 → signatures.json
python "$V1ACC\gen_specs.py"            # 按域生成任务书 spec_<domain>.md
# 在 cases_<domain>.py 里补用例；期望值写成运行时现算的 callable
python "$V1ACC\run_accuracy.py" <domain> --coverage
```

四条硬规矩：

| 规矩 | 说明 | 出处 |
| --- | --- | --- |
| 期望值来自**独立参考实现** | mpmath / sympy / numpy / scipy，写成 callable 运行时现算，避免抄错常数 | v1 `accuracy/README.md`:14-21 |
| 引擎改了行为：**先跑准确性套件，再跑 ctest** | "本套件是行为面，ctest 是内核面" | v1 `accuracy/README.md`:96 |
| 新增 action：签名表 → 任务书 → 用例；且引擎源码与套件**必须同源** | 覆盖率报告直接列出"未被任何用例覆盖的 action"；`signatures.json` 从源码提取，源码改了要重新提取 | v1 `accuracy/README.md`:97-99 |

**检查器清单不在本文重复**（在 v1 `accuracy/README.md`:62-81）——重复就是两份真相。

---

## 8. 失败要先分类（三种，不能混着写）

[`AGENTS.md`](../../AGENTS.md) §5 第 3 条要求把失败归到三类之一，引擎侧各举一例：

| 类别 | 引擎侧的样子 | 判据 / 处置 |
| --- | --- | --- |
| **产品缺陷** | 引擎给了**看着像结果的错值**（不是拒绝作答） | 加回归用例钉住，修完留下"为什么 + 怎么证明"（纪律 ③） |
| **用例判据错** | 期望值本身错、或容差过紧；也可能像 `STATUS-and-ROADMAP.md`:56 那样"3 处失败复核为**预期改进**" | 就地更新用例，并写明"为什么改期望值"，否则等于把缺陷藏起来 |
| **环境没准备好** | `找不到引擎 DLL`（`harness.py`:66-70）、SymEngine 运行时 DLL 没拷到 `build/bin`（`CMakeLists.txt`:155-160） | 不缺修复动作，缺的是环境；**不要说成引擎缺陷** |

⚠ 最危险的是把"产品缺陷"写成"环境没准备好"——它会静默留一个错值在用户面前。纪律 ① 的引擎版判据：
**拒绝作答（"未实现"）不算缺陷，给错值才算**（`test_limits.cpp`:5-6）。

---

## 9. 复跑清单（换产物就重跑）

```powershell
$V2 = "C:\Users\fsafsafsa\Desktop\MVS知识库\Multifunctional系列\Multifunctional-Mathematics-v2.0"

# 1) 构建（产物出到 MF_Mathematics/build/bin/Release）
cmake --build "$V2\MF_Mathematics\build" --config Release

# 2) 16 个 CTest 用例；期望 100% tests passed, 0 tests failed out of 16
ctest --test-dir "$V2\MF_Mathematics\build" -C Release --output-on-failure

# 3) 守门断言：count 必须 424（注意 .value.count，别看退出码）
$j = (& "$V2\MF_Mathematics\build\bin\Release\probe_call.exe" list_functions '{}' | ConvertFrom-Json)
$j.value.count          # 424
$j.isError              # False

# 4) 准确性套件（v1 树；默认 DLL 已指向 v2.0，见 §5.3）
python "$V2\..\Multifunctional-Mathematics\MF_Mathematics\tests\accuracy\run_accuracy.py"
```

本文**未验证**第 2 步与第 4 步的**执行本身**：§1 的 `ctest -N` 只**列用例**（`Total Tests: 16`，已跑），
没跑用例。要拿到"16/16 通过"与"2180 / 0"这两个现状数字，必须真跑第 2、4 步。

---

## 已知的文档债

| # | 文件:行 | 文档说 X | 代码 / 实测是 Y |
| --- | --- | --- | --- |
| 1 | [`../../README.md`](../../README.md):149、:163 | "① 引擎：**16 个 CTest 套件**"、"引擎 **16/16 套件**" | 16 是 `add_test` 条数，**正确**；但把 `probe_bugs`（`probe_bugs.cpp`:1 自称"探针"）也算进"套件"了。准确写法见同文件 :181 与本文 §1。属**口径不精确**，不是数字错误；[`../PROJECT-BOARD.md`](../PROJECT-BOARD.md):68 的"16/16 套件"同理 |
| 2 | [`../../README.md`](../../README.md):261-263 | "唯一有意保留的是 `MF_Mathematics/tests/accuracy/`（28 个 `.py`，2180 条准确性用例）" | 该路径在 **v2.0 树里不存在**（`git ls-files` 不匹配），实际在 v1 树。该段语境是"与 v1 的关系"，内容不错，但路径歧义会让读者在 v2.0 树下白找。28 与 2180 已由本文 §5.2/§5.4 复核为真 |
| 3 | [`../STATUS-and-ROADMAP.md`](../STATUS-and-ROADMAP.md):349（及 :122） | "准确性套件目前仍在 v1 树，**用 `MF_ACC_DLL` 指到 v2.0 的 DLL 运行**" | `harness.py`:46 已有默认值（v2.0 绝对路径），**不需要**再设 `MF_ACC_DLL`；[`../MIGRATION-GAPS.md`](../MIGRATION-GAPS.md):322-324 已按新事实写。属**状态类文档过期**，按 [`docs/README.md`](../README.md) §0 的口径应更新或加时间戳 |
| 4 | v1 树 `accuracy/README.md`:11 | "`tests/test_*.cpp`（ctest，**16 套件**）" | v2.0 树实测 `test_*.cpp` 是 **15** 个；注册进 CTest 的 16 = 15 个 `test_*` + `probe_bugs`。该文件在 **v1 树**（不在本仓库管辖范围，[`AGENTS.md`](../../AGENTS.md) §2），但会被照抄，故登记 |
| 5 | v1 树 `accuracy/README.md`:52、`harness.py`:33 | `cd C:\Users\fsafsafsa\Desktop\cppcshap\MF_Mathematics`；`ROOT = os.path.dirname(PKG)  # .../cppcshap` | 实际父目录是 `Multifunctional系列`，没有 `cppcshap` 这一层（实测路径解析）。同属 v1 树的**注释/文档过期** |
| 6 | v1 树 `accuracy/report.json` | 给出 `ok: 2180`、`covered_actions: 424` | **不含被测 DLL 路径、不含时间戳**，无法自证"测的是哪个引擎"；而 `harness.py`:37-40 记录过"静默测错对象"的历史。建议重跑时把 `DLL` 与运行时间写进报告 |
| 7 | `tests/probe_call.cpp`:11-12 | "只使用 C ABI（`api.h`），不引用内部注册表头文件" | 源码确实只 `#include "api.h"`（实测 `#include` 只有 `<cstdio>/<cstring>/<string>/<vector>` + `api.h`）——**注释没错**；但 CMake 链接行同时链了 `mf_mathematics_core`（`CMakeLists.txt`:387）。两点不矛盾（调用路径仍只走 C ABI），只是注释没覆盖"链接面比调用面宽"，易被误读成"该探针不会看到内部行为" |

**未证实的数字（本文一处都没编）**：2180、43.71 秒、16/16 全绿 —— 见 §5.4、§5.5、§9。
它们都有明确复跑命令，但**本文没有跑**，因此只能标"取自 v1 树 `report.json` 与文档"，不能标"本文实测"。
