# 引擎测试资产（`MF_Mathematics/`）

> 本文说明引擎测试资产的目标、用例划分、覆盖范围、准确性用例的位置、注册表守门断言，以及新增测试的方法。
> 调用契约见 [`CONTRACT.md`](CONTRACT.md)，模块清单见 [`MODULES.md`](MODULES.md)，能力边界见 [`BOUNDARIES.md`](BOUNDARIES.md)，构建与运行入口见 [`../../README.md`](../../README.md)。

## 1. 测试目标

| 类别 | 目标 | 判据 |
| --- | --- | --- |
| 回归套件（`test_*.cpp`） | 钉住内核函数与 JSON 分发层的行为 | 进程退出码 0 表示全部通过 |
| 探针（`probe_*.cpp`） | 诊断内部行为、观察对外返回 | 人读输出；`probe_bugs` 例外，注册进 CTest |

两类测试的分野是判据：回归套件有稳定的通过/失败判据；探针没有稳定判据，打印内部状态供人核对。

## 2. 用例划分

`MF_Mathematics/tests/` 下存在两个维度的划分，互不相加：

| 维度 | 口径 | 值 |
| --- | --- | --- |
| 可执行目标 | `add_executable` 条数 | 19 |
| CTest 用例 | `add_test` 条数 | 16 |

19 个可执行目标由 15 个 `test_*.cpp` 加 4 个 `probe_*.cpp` 组成。16 个 CTest 用例由 15 个 `test_*` 全部加 `probe_bugs` 组成；其余 3 个探针（`probe_solve_safety`、`probe_call`、`probe_scan`）没有 `add_test`，不进 CTest。

核对命令：

```powershell
(Get-ChildItem MF_Mathematics/tests -Filter '*.cpp' -File).Count                    # 19
(Get-ChildItem MF_Mathematics/tests -Filter 'test_*.cpp' -File).Count               # 15
(Get-ChildItem MF_Mathematics/tests -Filter 'probe_*.cpp' -File).Count              # 4
(Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern '^\s*add_test\(').Count        # 16
(Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern '^\s*add_executable\(').Count  # 19
ctest --test-dir MF_Mathematics/build -C Release -N                                  # Total Tests: 16
```

`probe_bugs` 位于两套划分的交集：文件名以 `probe_` 开头，同时有 `add_test`。`CMakeLists.txt` 中没有任何 `set_tests_properties`、`LABELS`、`WILL_FAIL` 或超时设置，判据完全落在进程退出码上。

## 3. 目标清单

### 3.1 回归套件

| 目标 | CTest 名 | 覆盖范围 |
| --- | --- | --- |
| `test_limits` | `limits` | 极限契约：确定形式给对值、不定式给对或如实拒绝 |
| `test_complex_grid` | `complex_grid` | `complex_grid` 返回结构、索引布局、null/nan 语义、点数上限 |
| `test_number_theory` | `number_theory` | number_theory 内核 + JSON 分发层 |
| `test_algebraic_topology` | `algebraic_topology` | homology / cohomology |
| `test_algebra` | `algebra` | combinatorics + number_theory 内核 |
| `test_numerical` | `numerical` | 积分 / ODE / 插值 / 误差 / 优化 |
| `test_functional_analysis` | `functional_analysis` | functional_analysis 包 |
| `test_calculus` | `calculus` | calculus 包；含求导自证：对积分结果求导再与原式数值比对 |
| `test_real_analysis` | `real_analysis` | differentiability |
| `test_linear_algebra` | `linear_algebra` | linear_algebra 包 |
| `test_harmonic_analysis` | `harmonic_analysis` | harmonic_analysis 包 |
| `test_measure_theory` | `measure_theory` | measure_theory 包 |
| `test_probability` | `probability` | probability 包 |
| `test_complex_analysis` | `complex_analysis` | complex_analysis 包 |
| `test_symbolic_contract` | `symbolic_contract` | 符号 API 契约：实际反馈的缺陷逐条钉住 |

`NAME` 与目标名不必相同，`ctest -R` 匹配的是 `NAME`。本仓库唯一的不同是 `test_limits` 的 `NAME` 是 `limits`。

### 3.2 探针

| 目标 | 链接 | CTest 名 | 用途 |
| --- | --- | --- | --- |
| `probe_bugs` | 只链 core + symengine 系 | `probe_bugs` | 边界对抗探针，直接包含各模块内部头 |
| `probe_solve_safety` | 只链 core + symengine 系 | — | 实证 `SymEngine::solve` 对各类方程是否安全 |
| `probe_call` | DLL + core | — | 通用调用探针，只包含 `api.h`，走 C ABI |
| `probe_scan` | 只链 core + symengine 系 | — | 数值扫描内部行为诊断，非回归 |

两点划分依据：

1. 只有走 C ABI 的目标链 DLL（`mf_mathematics`）。链 core 的目标绕过导出面、能看到内部行为，其结论不能当作「调用方看到的行为」的证据；`probe_call` 只包含 `api.h`，走与 C#/JS 相同的 C ABI 路径，其输出可直接作为对外行为的证据。
2. 只链 core 的目标不需要 `/WHOLEARCHIVE`，那是导出 DLL 的专属链接选项。

## 4. 覆盖范围

回归套件的期望值来源分三类：

| 来源 | 套件数 | 哪些 |
| --- | --- | --- |
| v1 Python 版 `self_test()` 的断言 | 12 | 12 个 `test_*.cpp` |
| 数学事实（非「当前实现输出」） | 1 | `test_limits` |
| 实际反馈的缺陷 + 契约 | 2 | `test_complex_grid`、`test_symbolic_contract` |

v1 的 Python 后端已从本仓库移除，因此 12 份套件里的期望值是冻结的字面量，无法回到原始出处重算。改动这些数字只能依据独立参考实现，不能依据「v1 当时算得是某值」。

## 5. 准确性用例的位置

`MF_Mathematics/tests/accuracy/` 在本仓库中不存在。准确性套件位于 v1 树：

```text
../Multifunctional-Mathematics/MF_Mathematics/tests/accuracy/
```

这是测试资产，不是运行时代码。它经 `ctypes.CDLL` 加载引擎 DLL 调用 `math_call`，可对任意引擎 DLL 运行。

| 项 | 值 |
| --- | --- |
| `.py` 文件数 | 28 |
| 用例域文件 `cases_*.py` 数 | 14 |
| 最近一次运行的通过用例数 | 2180 |
| 覆盖的 action 数 | 424 / 424 |

核对命令：

```powershell
$ACC = "..\Multifunctional-Mathematics\MF_Mathematics\tests\accuracy"
(Get-ChildItem $ACC -Filter '*.py' -File).Count          # 28
(Get-ChildItem $ACC -Filter 'cases_*.py' -File).Count    # 14
$r = Get-Content "$ACC\report.json" -Raw | ConvertFrom-Json
$r.totals.ok; $r.totals.fail; $r.totals.skip; $r.totals.err   # 2180 / 0 / 0 / 0
$r.totals.covered_actions; $r.totals.total_actions           # 424 / 424
```

DLL 选择由 `harness.py` 决定：`DLL = os.environ.get("MF_ACC_DLL") or ENGINE_DLL`，其中 `ENGINE_DLL` 指向本仓库的构建产物。`MF_ACC_DLL` 用于覆盖默认值。

运行方式：

```powershell
python "$ACC\run_accuracy.py"                 # 全部域
python "$ACC\run_accuracy.py" number_theory   # 单域
python "$ACC\run_accuracy.py" --coverage      # 只看覆盖缺口
python "$ACC\run_accuracy.py" --json "$ACC\report.json"
```

2180 这个数字来自 `report.json` 的 `totals.ok`。该报告不包含被测 DLL 路径与时间戳，无法自证测的是哪个 DLL；要确认当前引擎的准确性，需重跑 `run_accuracy.py` 并检查新报告的 `totals`。

## 6. 注册表断言

引擎的每个 `*_api.cpp` 靠一个没有外部引用的全局注册器对象注册 action。静态库链接时，链接器只抽取解决了未定义符号的目标文件；注册器不被任何符号引用，会被整体丢弃，注册表随之变空。这种失效是静默的：DLL 照常加载、`function_exists` 照常可调，每个 action 返回「未找到函数」。

导出 DLL `mf_mathematics` 因此强制全量纳入 core：

```cmake
target_link_options(mf_mathematics PRIVATE "/WHOLEARCHIVE:$<TARGET_FILE:mf_mathematics_core>")
```

定位命令：

```powershell
Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern 'WHOLEARCHIVE'
```

守门断言是 `list_functions` 的 `count` 取值 424。核对命令：

```powershell
$j = & MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}' | ConvertFrom-Json
$j.value.count                                       # 424
$j.isError                                           # False
$j.value.functions.Count                             # 424
($j.value.functions | Sort-Object -Unique).Count     # 424
```

判据打在 JSON 上，不打在进程退出码上。`probe_call` 调用不存在的 action 时仍返回退出码 0，因此退出码不能作为判据。`probe_call` 的三个入口是 `probe_call <函数名> [args_json]`、`--list`、`--has <函数名>`；`args_json` 支持 `@文件路径` 从文件读 JSON，用于传含空格、引号或竖线的参数。

## 7. 新增测试方法

### 7.1 CTest 回归套件

最小模板以 `test_number_theory` 为最简样板：

```cmake
add_executable(test_foo tests/test_foo.cpp)
target_link_libraries(test_foo PRIVATE mf_mathematics mf_mathematics_core)
target_include_directories(test_foo PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
if(MSVC)
    target_compile_options(test_foo PRIVATE /utf-8 /W4)
endif()
add_test(NAME foo COMMAND test_foo)
```

细节：

| 细节 | 说明 |
| --- | --- |
| `/utf-8` 不可省略 | 源码含中文字面量，缺它 MSVC 按本地代码页解释 |
| SymEngine / Eigen 需显式加 | 库链接是 PRIVATE、不传递；用 SymEngine 需再加四个 `.lib` 与 include 目录，用 Eigen 需加 `${MF_EIGEN_INCLUDE_DIR}` |
| `NAME` 与目标名解耦 | `ctest -R` 匹配 `NAME`，不是目标名 |

源文件形状以 `test_limits.cpp` 为范式：`g_checks` 与 `g_failures` 两个计数、`CHECK` 宏累计，`main` 末尾打印检查数与失败数并返回 `g_failures == 0 ? 0 : 1`。期望值必须来自独立参考实现或数学事实，不能来自「当前实现输出」。

加完后的两步：

1. 确认新用例会失败：把被测行为改错，确认 `ctest -R foo` 变红，再改回。
2. 确认进 CTest：`ctest -N` 的 `Total Tests` 增加 1。

探针不进 CTest 的情形：目标是打印内部状态供人核对时，不 `add_test`，否则污染全绿信号。

### 7.2 准确性用例

准确性用例改的是 v1 树里的文件：

```powershell
python "$ACC\extract_signatures.py"   # 从 C++ 注册源码提取参数契约 → signatures.json
python "$ACC\gen_specs.py"            # 按域生成任务书 spec_<domain>.md
# 在 cases_<domain>.py 里补用例；期望值写成运行时现算的 callable
python "$ACC\run_accuracy.py" <domain> --coverage
```

| 规矩 | 说明 |
| --- | --- |
| 期望值来自独立参考实现 | mpmath / sympy / numpy / scipy，写成 callable 运行时现算 |
| 改行为先跑准确性套件再跑 ctest | 准确性套件是行为面，ctest 是内核面 |
| 新增 action 需同源 | 签名表 → 任务书 → 用例；`signatures.json` 从源码提取，源码改了要重新提取 |
