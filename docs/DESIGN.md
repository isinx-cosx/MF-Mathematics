# 设计理念

> 本文说明这个软件为什么是这个形状：哪些选择是刻意的、每条选择由哪段代码保证、违反之后如何被检出。
> 与兄弟文档的分工：[`DESIGN-BOUNDARIES.md`](DESIGN-BOUNDARIES.md) 登记明确不做、推迟与尚未验证的事项；
> [`DECISIONS.md`](DECISIONS.md) 记录逐条决定及其代价；产品门面在 [`../README.md`](../README.md)。

## 设计目标

全部设计指向同一个目标：让「结论」只有一个来源，且可复现、可证伪。数学工具最坏的失败方式不是报错，而是给出一个看似正确的错误答案。六条理念分别守住「结论」的不同侧面：

| 结论 | 唯一来源 | 追溯方式 |
| --- | --- | --- |
| 数值或符号结果 | 引擎注册表 | 结果 JSON 信封 `{"isError","value"}` |
| 一次改动是否成立 | 一条可复跑的判据 | 构建期自检 + CTest + CDP 用例 |
| 一次失败是否产品缺陷 | 失败分类（产品 / 判据 / 环境） | 失败点所在的那一层 |

## 六条理念

### ① 计算来源唯一：前端一行数学都不算

全部数值与符号结果出自引擎的函数注册表，入口是 `mf::registry::dispatch()`
（`Select-String -Path MF_Mathematics/registry.cpp -Pattern "dispatch"`）。跨进程边界只有两个 C ABI 函数：`math_call` 与 `function_exists`
（`Select-String -Path MF_Mathematics/api.cpp -Pattern 'extern "C"'`，命中 2 处）。前端只做参数构造、调用与展示：输入转成 args JSON 在 `src/lib/engine/calcArgs.js`，展示格式化在 `src/lib/engine/resultFormat.js`。调用点收敛在 `src/lib/bridge.js` 的 `engineCall()`，它落到 `window.chrome.webview.hostObjects.sync.mf.Dispatch`
（`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/bridge.js -Pattern "hostObjects"`）。渲染层不存在自行计算的入口。

验证方法：端到端用例里有一条防架构退化的断言，假端点故意返回 `1+1=3`，断言界面不得把它当作计算结果。假端点由用例自行拉起，不依赖真网络
（`Select-String -Path MF_UI/MFMath.UI.Vue/tests/cdp-ai.mjs -Pattern "1\+1=3"`；假端点是 [`../MF_UI/MFMath.UI.Vue/tests/fake-ai-server.mjs`](../MF_UI/MFMath.UI.Vue/tests/fake-ai-server.mjs)）。

边界：没有宿主进程就没有数学。取不到桥时 `engineCall()` 与 `engineCallAsync()` 都返回 `null`（`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/bridge.js -Pattern "if \(!mf\) return"`）。浏览器预览因此只是界面开发用的壳，不是可用的计算环境。

### ② 结果不臆造：算不出来就说算不出来

机制分四层：

| 层 | 做法 | 定位命令 |
| --- | --- | --- |
| 符号上如实 | 求不出初等原函数时 `integrate_indefinite()` 返回字符串 `"未实现"` | `Select-String -Path MF_Mathematics/calculus/integrals.cpp -Pattern '"未实现"'` |
| 数值上设安全阀 | `make_fv()` 对绝对值大于 `1e12` 的函数值抛错，防止极点附近采出量级有限的假值 | `Select-String -Path MF_Mathematics/calculus/integrals.cpp -Pattern "1e12"` |
| 积分前提校验 | `collect_denominators()` 与 `denominator_roots()` 找瑕点，`antiderivative_unbounded_near()` 判断该侧是否收敛，发散即抛错 | `Select-String -Path MF_Mathematics/calculus/integrals.cpp -Pattern "antiderivative_unbounded_near"` |
| 接口上如实 | 未注册的 action 返回 `{"isError":true,"value":"未找到函数: <name>"}`；handler 抛出的 `std::exception` 由 `make_handler()` 转成错误信封 | `Select-String -Path MF_Mathematics/registry.cpp -Pattern "未找到函数"`；`Select-String -Path MF_Mathematics/api_helpers.h -Pattern "make_handler"` |

不可返回的路径同样堵死：`make_handler()` 额外接住 `catch (...)`
（`Select-String -Path MF_Mathematics/api_helpers.h -Pattern "catch \(\.\.\.\)"`）。非标准异常若穿过 `extern "C"` 边界，会终止整个宿主进程，而不是一次可恢复的调用失败。

构建上如实：每个 `*_api.cpp` 靠一个没有外部引用的全局注册器登记自己。不加 `/WHOLEARCHIVE` 时链接器会丢弃整个目标文件，注册表变空；这种失效是静默的——DLL 照常加载、`function_exists` 照常可调，只是每个 action 都返回「未找到函数」。守门判据是数出来的 action 数：

```powershell
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'   # count 应为 424
```

`/WHOLEARCHIVE` 的写法在 [`../MF_Mathematics/CMakeLists.txt`](../MF_Mathematics/CMakeLists.txt) 的 `target_link_options`（`Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern "WHOLEARCHIVE"`）。当前 `count` 是 424，随引擎新增 action 变化，用上面的命令复跑。

验证方法：引擎 CTest 全绿（`ctest --test-dir MF_Mathematics/build -C Release --output-on-failure`）加上面的 `count == 424`。不定积分规则另有求导自证，见理念 ③。

### ③ 修改可验证：每个修复都留下「为什么」与「怎么证明」

数学层：待证结论自己证明自己。18 条不定积分规则每条配一条求导自证——对结果求导、再与原式在若干点上数值比对，判据是相对误差 `1e-9`。自证函数是 `antideriv_self_checks_out()`
（`Select-String -Path MF_Mathematics/tests/test_calculus.cpp -Pattern "1e-9"`）。当前规则数是 18，随新增规则变化，复跑：

```powershell
(Select-String -Path MF_Mathematics/tests/test_calculus.cpp -Pattern 'antideriv_self_checks_out\("').Count
```

工程层：每条守卫先证明「它会失败」。[`../MF_UI/MFMath.UI.Vue/tools/check-ui.mjs`](../MF_UI/MFMath.UI.Vue/tools/check-ui.mjs) 的每条断言在入库前经过一次反向验证：临时制造一个违反，确认自检报错并 `exit 1`，再还原。只写一条永远为真的断言等于没写。

登记与执行双向对照：端到端用例 `tests/cdp-*.mjs` 与 `run-all.ps1` 的登记双向校验，任一侧多出来即失败（`Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "NOT_IN_SUITE"`）。这条拦住「写了用例却永远不跑」：当前 `cdp-*.mjs` 是 49 个，登记 49 个，随用例增减变化，由 `node tools/check-ui.mjs` 复跑。

### ④ 结论可追溯：失败先分类，再归因

结论写成「在哪个产物上、用什么命令、什么时刻实测」，而不是「应该是这样」。失败事实与原因之间隔着一步「当时测的是哪份产物」，这一步不记，归因就会过期。

失败先分成三类，三类不混写：

| 类别 | 判据 | 处理 |
| --- | --- | --- |
| 产品缺陷 | 干净产物上、无并发驱动时仍可复现 | 修产品，并留下可复跑判据 |
| 用例自身判据错 | 与产品行为一致，是断言写错 | 改用例 |
| 环境没准备好 | 依赖的产物 / 端口 / 权限不在位 | 记明缺什么，不记为产品缺陷 |

第三条有实例：异步 job 通道的无头自检原先「派一个 600×600 分形 → 睡 250 ms → 取消」，而本机这个活约 253 ms 跑完，取消打在已完成上，用例随机变红而产品没有问题。这是测试自身制造的竞态。改法是轮询到任务真的在跑再取消，与机器快慢无关。实现是 `wait_running()`
（`Select-String -Path MFMath.Host.Rust/src/jobs.rs -Pattern "fn wait_running"`）。

验证方法：无头自检 `mfmath-host-rust.exe --selftest-jobs` 覆盖派活 → 串行排队 → 轮询 → 完成 → 取消（排队中 / 运行中）五条语义；端到端在真实宿主会话里跑 `powershell -NoProfile -File MF_UI/MFMath.UI.Vue/tests/run-all.ps1 -NoLaunch`。端到端只跑一套，否则用例互相踩，套件自己会打印 `INTERFERENCE` 提示。

### ⑤ 离线范围与隐私默认

离线边界可验收。断网后本地计算、绘图、教程、控制台照常；只有联网搜索、账号与 AI 助手需要网络。涉及网络的用例一律跑在自带的假端点上，因此判据本身不需要真网络。

隐私默认不上报。崩溃与前端未捕获异常写进 `%LOCALAPPDATA%\MFMath\logs\`：`app.log`（单文件上限 2 MB，轮转成 `app.1.log`）与 `crash-*.log`（环境 + 异常 + 最近 200 行 `app.log` 尾部，只留最近 20 个）。常量是 `MAX_BYTES`、`CRASH_TAIL_LINES`、`KEEP_CRASH_FILES`
（`Select-String -Path MFMath.Host.Rust/src/logging.rs -Pattern "MAX_BYTES|KEEP_CRASH_FILES"`）。不联网上报。交出日志是用户的一个动作：「设置 → 存储与数据 → 导出诊断包」调用宿主的 `ExportDiagnostics`（`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "ExportDiagnostics"`）。

### ⑥ 失效可见：不静默兜底

项目里有一批刻意保留的可见失效，共同点是「不悄悄兜底」。机制与判据：

| 手法 | 机制 | 落点 |
| --- | --- | --- |
| 显式登记 + 双向校验 | 引擎有映射、页面选不到的模式必须登记进 `NOT_EXPOSED_GROUPS`；登记了却又能选到的报「过时条目」 | `check-ui.mjs` 的 `NOT_EXPOSED` |
| 重名不静默 | 功能可达但名字选不到的模式登记进 `DUPLICATE_NAME_GROUPS`；同一模式名挂到两个视图登记进 `CROSS_VIEW_DUP_OK` | `check-ui.mjs` 的 `DUPLICATE_NAME_GROUPS` / `CROSS_VIEW_DUP_OK` |
| 冻结要看得见 | Vue 绘图组 6 个文件是冻结的回退资产，白名单逐一对应，且必须仍然无人 import | `check-ui.mjs` 的 `FROZEN_VUE_PLOT_FILES` |
| 参数契约不许静默失效 | 由 `get_interval` 读区间的 handler 固定列在 `INTERVAL_FNS`，其 args 缺少 `interval` 键即失败 | `check-ui.mjs` 的 `INTERVAL_FNS` |
| 默认路径要能过 | 概率表类模式必须能用弹窗自带默认值构造出非空表 | `check-ui.mjs` 的 `prob_table` 段 |
| 降级要可见 | 取消在引擎层做不到真停，界面文案是「已停止等待」，不写「已停止」 | `jobs.rs` 的 `cancel_job()` |
| 慢活不许假死 | 重活走后台任务通道：`DispatchJob` 入队即返回 jobId，界面用 `PollJob` 轮询 | `jobs.rs` 的 `dispatch_job()` / `poll_job()` |

这些判据是自检的输出。单独复跑命令（在 `MF_UI/MFMath.UI.Vue/` 下执行）：

```powershell
node tools/check-ui.mjs
```

当前输出中随代码变化的数字：

| 项目 | 当前值 |
| --- | --- |
| 引擎模式可达性 | 映射 415 个 / 页面并集 391 个 / 取不到 0 个 |
| 区间参数契约 | 10 个 handler / 命中 10 个 / 缺 interval 0 个 |
| 概率表契约 | 4 个模式 / 空表 0 个 |
| 冻结的 Vue 绘图组 | 6/6 个文件在位，被 import 0 处 |
| 重名模式登记 | 已登记 24 个，未登记 0 个 |
| 跨视图重名 | 2 处（已登记 2，未登记 0） |
| i18n 弹窗字段 | 186 条唯一标签，缺译文 0 条 |
| i18n 结果标签 | 78 个字段，缺译文 0 条 |
| 数学键盘 | 6 分类 / 126 键 |
| 端到端用例 | cdp-* 49 个，已登记 49 个 |

## 判据汇总

| 理念 | 机制落点 | 验证命令 | 通过判据 |
| --- | --- | --- | --- |
| ① 计算来源唯一 | `math_call` / `function_exists`；`engineCall()` | `Select-String -Path MF_Mathematics/api.cpp -Pattern 'extern "C"'` | 导出面恰好 2 个函数 |
| ② 结果不臆造 | `"未实现"`；`1e12` 安全阀；瑕点检测；错误信封 | `& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'` | `count` = 424 |
| ③ 修改可验证 | `antideriv_self_checks_out()`；`check-ui.mjs` | `ctest --test-dir MF_Mathematics/build -C Release --output-on-failure` | 全绿 |
| ④ 结论可追溯 | 失败分类；`wait_running()` | `mfmath-host-rust.exe --selftest-jobs` | `RESULT\|selftest-jobs\|PASS` |
| ⑤ 离线与隐私 | `logging.rs`；`ExportDiagnostics` | `Select-String -Path MFMath.Host.Rust/src/logging.rs -Pattern "MAX_BYTES"` | 2 MB 轮转、崩溃留 20 个 |
| ⑥ 失效可见 | `NOT_EXPOSED` / `FROZEN_VUE_PLOT_FILES` / `INTERVAL_FNS` | `node tools/check-ui.mjs`（在 `MF_UI/MFMath.UI.Vue/` 下） | `exit 0`，缺口计数为 0 |

## 理念之间的取舍

理念不是免费的。下表是「选了哪边、代价是什么」：

| 取舍 | 选择 | 代价 |
| --- | --- | --- |
| 单一来源 vs 启动依赖 | 计算全在引擎 | 没有宿主进程就没有数学；纯浏览器里 `engineCall()` 返回 `null` |
| 同步 vs 异步 | 判据是规模，不是「重不重」 | 阈值是数出来的工作量：`mandelbrot` 1.5e8、`complex_grid` 2.5e5、`expr_eval_grid` 2.5e5、`matrix_multiply` 2e6（`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern "1.5e8"`）。绘图页每条曲线一次的采样保持同步，改上界就必须改回异步 |
| 串行 vs 吞吐 | 引擎调用串行执行 | 一次只跑一个重活。引擎里除 `numerical/numerical_integration.cpp` 的一个 `thread_local` 外没有同步原语，`math_call` 是无锁的 dispatch + `memcpy`，并发会踩 FLINT / SymEngine 的全局缓存 |
| 可取消 vs 引擎不改 | 取消只做到「停止等待 + 丢弃结果」 | 工作线程会把这一步算完。界面文案因此受限为「已取消等待」；真停只能靠进程边界 |
| 冻结 vs 删除 | Vue 绘图组迁到 React 后，6 个文件保留为回退资产 | 仓库里有一份不参与构建、不在类型检查范围的代码。删除更干净，但失去回退，所以选「冻结 + 断言不许悄悄接回」 |

引擎的注册边界不允许出现 `std::string` / `std::vector` / `SymEngine::RCP`。两个 C ABI 函数只收发 `const char*` 与调用方给的缓冲区，缓冲区不够就返回 `-1`
（`Select-String -Path MF_Mathematics/api.cpp -Pattern "out_size"`）。同一理由的另一面在 `make_handler()`：任何异常都必须在那里被接住，不能穿过 `extern "C"`。

## 使用这份文档

- 想改架构：先看「六条理念」是否允许；不允许就不改，改了要同步更新本文与 [`DECISIONS.md`](DECISIONS.md)。
- 觉得某个行为像缺陷：先查 [`DESIGN-BOUNDARIES.md`](DESIGN-BOUNDARIES.md)，它区分明确不做 / 推迟 / 能力边界 / 尚未验证，并写明推翻每一条需要什么证据。
- 发现本文与代码不一致：以代码为准，然后改本文。
- 想加一条理念：它必须同时满足两条——代码里有对应机制、违反时有可复跑判据。
- 想知道某个数字怎么来的：数字旁边就是命令；行号会漂，命令不会。
- 安装包路径的现状：安装器已自带（[`../MFMath.Installer/`](../MFMath.Installer/)，自解压单 exe、向导三页），一条命令出包：`.\MFMath.Installer\tools\build-setup.ps1`，产物 `Multifunctional-Mathematics_<版本>_x64-setup.exe` 约 18.29 MB。「安装 → 启动 → 卸载」已在 Windows 11 本机跑通（安装后主程序 `--selftest-jobs` 5/5，卸载后目录 / 快捷方式 / 注册表项全清、用户数据保留）；未在其它 Windows 版本与高 DPI 缩放下验证。安装包**未签名**，首次运行会弹 SmartScreen，点「更多信息 → 仍要运行」。设计与验证记录见 [`../MFMath.Host.Rust/docs/INSTALLER.md`](../MFMath.Host.Rust/docs/INSTALLER.md)；载荷构成与体积实测见 [`../MFMath.Host.Rust/docs/PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md)。
