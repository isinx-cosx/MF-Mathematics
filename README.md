# MF-Mathematics v2.0

**Windows 桌面数学工作台：多功能可视化科学计算，离线优先。**

> 本文说明这个软件是什么、如何构建与运行、覆盖哪些功能、边界在哪。
> 内部机制见 [`docs/DESIGN.md`](docs/DESIGN.md)，操作步骤见 [`docs/manual/WORKFLOWS.md`](docs/manual/WORKFLOWS.md)，
> 宿主与打包见 [`MFMath.Host.Rust/README.md`](MFMath.Host.Rust/README.md)，全部文档的入口是 [`docs/README.md`](docs/README.md)。
> 文中随代码变化的数字，在就近给出复跑命令。

## 定位

MF-Mathematics 是单目录树、自包含、离线优先的数学工作台。一个进程承载三层：C++ 引擎负责全部计算，Vue 外壳负责界面，Rust/Tauri 宿主负责窗口与系统能力。

- **15 个计算视图**：基础运算页 `/calc/basic` 加 14 个学科视图（代数、微积分、解析几何、数列、线性代数、概率论与数理统计、数值分析、数论、实分析、泛函分析、复分析、代数拓扑、测度论、调和分析）。
- **7 种绘图**：2D 函数（含隐函数 / 参数方程）、极坐标、3D 曲面、复平面、向量场、自由几何、分形。
- **424 个引擎 action**，可由界面、控制台与 AI 助手调用。
- **离线优先**：断网后本地计算、绘图、教程、控制台照常；联网搜索、账号与 AI 助手需要网络。

三条写进代码与测试的纪律：

1. **不编造结果**。算不出来返回「未实现」，不硬凑式子。
2. **AI 不承担计算**。AI 助手只调用引擎 action，不自行估算数值。
3. **每个修复留下「为什么」与「怎么证明」**。没有可复跑判据的修改不算完成。

逐条对应的机制与代码位置见 [`docs/DESIGN.md`](docs/DESIGN.md)。前端不执行数学运算：所有数值与符号结果来自 `mf_mathematics.dll`，界面只做参数构造、展示与编排。

平台与工具链：

| 项 | 取值 |
| --- | --- |
| 操作系统 | Windows 10 / 11 (x64) |
| 引擎 | C++17，CMake ≥ 3.16，MSVC |
| 外壳 | Vue 3 + Vite（`MF_UI/MFMath.UI.Vue`） |
| 绘图组 | React 19（`MF_UI/MFMath.UI.React`，被外壳内嵌） |
| 宿主 | Rust edition 2024 + Tauri v2 + WebView2 |

## 功能

| 分区 | 内容 |
| --- | --- |
| 学科计算 | `/calc/basic` 基础运算 + 14 个学科视图 |
| 绘图 | 7 个绘图路由，全部由 React 绘图组渲染 |
| 工具 | 联网搜索 `/tools/search`、控制台 `/tools/console`、函数工具箱 `/tools/toolbox` |
| AI | 助手抽屉、步骤推导、可调引擎的数学问答（流式输出、可中断） |
| 学习 | 交互式教程、示例任务库、分类数学键盘 |
| 系统 | 设置面板、工作区保存与还原、结果导出图片、账号、更新检查、深浅色主题 |

导航结构即功能清单，共 4 个分组、27 个导航项：

| 分组 | `id` | 项数 | 路由前缀 |
| --- | --- | ---: | --- |
| 计算模式 | `calc` | 15 | `/calc/*` |
| 绘图模式 | `plot` | 7 | `/plot/*` |
| 工具 | `tools` | 3 | `/tools/*` |
| 帮助 | `help` | 2 | `/tutorial`、`/examples` |

```powershell
(Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/router/nav.js -Pattern 'route:').Count   # 27
```

教程篇数、步骤数、FAQ 条数与键盘键数由构建期自检输出，复跑 `npm run check --prefix MF_UI/MFMath.UI.Vue`。

## 架构

三层，两个跨语言接缝。现役宿主只有 Rust/Tauri 一个。

```
 外壳（前端）   MF_UI/MFMath.UI.Vue/    Vue 3 + Vite → dist/，再拷成 wwwroot/
                MF_UI/MFMath.UI.React/  React 绘图组，被外壳内嵌
                页面 URL：https://mfmath.local/index.html
      │  接缝①：WebView2 同步 COM 宿主对象
      │  window.chrome.webview.hostObjects.sync.<对象>.<方法>(…)
      │  对象：mf / sys / diag / win / push / update / account / search / con
      ▼
 宿主           MFMath.Host.Rust/    Rust edition 2024 + Tauri v2 + WebView2
                9 个宿主对象 / 84 个方法；窗口无边框，标题栏由页面自绘
                数据目录 %LOCALAPPDATA%\MFMath；CDP 调试端口 9222
      │  接缝②：C ABI，DLL 恰好导出两个函数
      │  bool function_exists(const char* function_name)
      │  int  math_call(const char* name, const char* args_json, char* out_buffer, int out_size)
      ▼
 引擎           MF_Mathematics/    C++17，110 个 .cpp（不含 build/ 与 tests/）
                13 个模块目录 + 7 个根级 .cpp；424 个已注册 action
                SymEngine + FLINT + GMP + MPFR + Eigen
                DLL 边界不暴露 std::string / std::vector / SymEngine::RCP
```

接缝①是同步的：`mf.Dispatch` 出现在采样链与绘图网格的热路径上，必须当场返回字符串。Tauri 没有 `AddHostObjectToScript` 的官方对应物，但 `with_webview()` 交出底层 `ICoreWebView2`，同步桥由此保留。符号名与实现见 [`main.rs`](MFMath.Host.Rust/src/main.rs) 的 `HOST_OBJECTS` 与各 `*_SPEC` 常量
（`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "HOST_OBJECTS"`）。

接缝②的两个导出函数声明在 [`api.h`](MF_Mathematics/api.h)，实现在 [`api.cpp`](MF_Mathematics/api.cpp)。

### 宿主对象与方法数

| 宿主对象 | 方法数 | 覆盖 |
| --- | ---: | --- |
| `mf` | 16 | 引擎调用、异步 job 通道、符号计算 |
| `sys` | 8 | 设置、存储、诊断包导出 |
| `diag` | 1 | 前端异常写入宿主日志 |
| `win` | 9 | 窗口操作 + 文件对话框 |
| `push` | 3 | 宿主 → 页面推送 |
| `update` | 6 | 更新检查（只提示，不自动安装） |
| `account` | 19 | 登录、注册、令牌刷新 |
| `search` | 12 | 联网搜索 |
| `con` | 10 | 控制台 + 可选组件下载 |
| **合计** | **84** | 9 个对象 |

方法表权威源是 [`main.rs`](MFMath.Host.Rust/src/main.rs) 的各 `*_SPEC` 常量。复跑：

```powershell
Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'MethodSpec \{ name:' | Measure-Object   # 84
Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern '^\s*\("[a-z]+", [A-Z_]+_SPEC\)' | Measure-Object   # 9
```

### 引擎的两个构建目标

| 目标 / 别名 | 类型 | 内容 |
| --- | --- | --- |
| `mf_mathematics_core`（`MFMath::engine`） | STATIC | 全部数学实现 |
| `mf_mathematics`（`MFMath::cabi`） | SHARED | 只有 `api.cpp`，导出两个 C ABI 函数 |

自建导出 DLL 并链接 `MFMath::engine` 时加 `/WHOLEARCHIVE`。每个 `*_api.cpp` 靠一个没有外部引用的全局注册器登记，不加会被链接器整体丢弃、注册表变空；这种失效是静默的——DLL 照常加载、`function_exists` 照常可调，但每个 action 都返回「未找到函数」。守门断言是 `list_functions` 的 `count == 424`，实现见 [`CMakeLists.txt`](MF_Mathematics/CMakeLists.txt) 的 `target_link_options`
（`Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern "WHOLEARCHIVE"`）。

## 快速开始

仓库不含编译产物：`MF_Mathematics/build/`、`dist/`、`target/`、`bin/`、`obj/` 均在 `.gitignore` 中。克隆后按下述三步构建，顺序不可颠倒。

### 前置依赖

| 用途 | 需要 |
| --- | --- |
| 引擎 | CMake ≥ 3.16、Visual Studio C++ 工具链、[vcpkg](https://github.com/microsoft/vcpkg) 提供 `symengine` `flint` `gmp` `mpfr` `eigen3` |
| 前端 | Node.js ≥ 18 |
| 宿主 | Rust 工具链（`cargo`）、WebView2 Runtime（Win11 自带；Win10 需安装） |

引擎依赖路径是两个 CMake 缓存变量，默认指向 vcpkg 安装位置，可用 `-D` 覆盖：`MF_SYMENGINE_ROOT` 与 `MF_EIGEN_INCLUDE_DIR`（`Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern "MF_SYMENGINE_ROOT|MF_EIGEN_INCLUDE_DIR"`）。

### 三步构建

```powershell
git clone https://github.com/isinx-cosx/MF-Mathematics.git
cd MF-Mathematics

# ① 引擎 —— 目标 mf_mathematics 是只含 C ABI 的 DLL
cmake -S MF_Mathematics -B MF_Mathematics/build -A x64 `
      -DMF_SYMENGINE_ROOT="$env:VCPKG_ROOT\installed\x64-windows" `
      -DMF_EIGEN_INCLUDE_DIR="$env:VCPKG_ROOT\installed\x64-windows\include\eigen3"
cmake --build MF_Mathematics/build --config Release --target mf_mathematics

# ② 前端 —— build 走 vite build，末尾跑 scripts/prune-fonts.mjs 裁字体
npm --prefix MF_UI/MFMath.UI.Vue install
npm --prefix MF_UI/MFMath.UI.Vue run build

# ③ 宿主 —— build.rs 把引擎 DLL 与前端 dist 同步到 exe 同目录的 wwwroot/
cargo build --release --manifest-path MFMath.Host.Rust/Cargo.toml
```

`cargo build` 的 `build.rs` 只在新时才拷贝，缺了只警告：把引擎产物（`mf_mathematics.dll` 与 5 个运行时依赖）拷到 exe 同目录、把 `MF_UI/MFMath.UI.Vue/dist` 拷成 `<exe 同目录>/wwwroot`、检查图标。缺第 1 件时界面照常打开，但启动自检写「引擎未加载」；缺第 2 件时页面退回 Tauri 内嵌资产，URL 变成 `http://tauri.localhost`。

手工同步用 [`MFMath.Host.Rust/tools/`](MFMath.Host.Rust/tools/) 下的两个脚本，`--dest` 含义不同：

```powershell
node MFMath.Host.Rust/tools/sync-engine.mjs   --dest "<exe 目录>"              # 引擎：--dest 是 exe 所在目录
node MFMath.Host.Rust/tools/sync-wwwroot.mjs --exe "<exe 目录>\mfmath-host-rust.exe"  # 界面：wwwroot 落到 exe 同目录
```

### 运行

```powershell
& MFMath.Host.Rust\target\release\mfmath-host-rust.exe
```

| 环境变量 | 作用 |
| --- | --- |
| `MF_WWWROOT` | 指定 UI 目录，默认 exe 同目录的 `wwwroot`（[`main.rs`](MFMath.Host.Rust/src/main.rs) 的 `wwwroot_dir()`） |
| `MF_WEBVIEW2_DIR` | 指定 WebView2 用户数据目录，默认 `%LOCALAPPDATA%\MFMath\webview2`（同文件的 `webview_data_dir()`） |
| `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` | 宿主未设置时自动设为 `--remote-debugging-port=9222`，端到端用例靠它接入 |

同一数据目录只允许一个实例。宿主在建窗口前以独占共享模式打开数据目录里的 `.mf-instance` 锁文件
（[`main.rs`](MFMath.Host.Rust/src/main.rs) 的 `lock_webview_dir()`）；第二个实例拿到 `ERROR_SHARING_VIOLATION`，并在错误信息里报出持有者 pid。目录不可写等其它原因不阻止启动，只跳过单实例检查。

改了前端之后：重跑 `npm run build`，再 `cargo build` 让 `build.rs` 重新同步 `wwwroot/`；或用 `MF_WWWROOT` 把宿主直接指到 `MF_UI/MFMath.UI.Vue/dist`。宿主不内置 Vite dev server 集成。

## 验证与测试

四层，全部可在本机运行，每层有可复跑判据。

```powershell
# ① 引擎：CTest
cmake --build MF_Mathematics/build --config Release
ctest --test-dir MF_Mathematics/build -C Release --output-on-failure

# ② 引擎注册表守门：/WHOLEARCHIVE 失效时这个数会掉
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'   # count 应为 424

# ③ 前端：类型检查 + 引擎签名 + 参数契约 + 构建期自检
npm run check --prefix MF_UI/MFMath.UI.Vue
npm run check:types --prefix MF_UI/MFMath.UI.React

# ④ 端到端：CDP 用例，跑在一个真实宿主会话里
powershell -NoProfile -File MF_UI/MFMath.UI.Vue/tests/run-all.ps1
```

`run-all.ps1` 默认自己起一个宿主；加 `-NoLaunch` 附着到已在 127.0.0.1:9222 监听的宿主
（`Select-String -Path MF_UI/MFMath.UI.Vue/tests/run-all.ps1 -Pattern "NoLaunch"`）。

| 层 | 规模 | 权威源 |
| --- | --- | --- |
| 引擎 CTest | `tests/` 下 19 个可执行目标，其中 16 个注册进 CTest | [`CMakeLists.txt`](MF_Mathematics/CMakeLists.txt) 的 `add_test` / `add_executable` |
| 注册表守门 | `count == 424` | `probe_call.exe list_functions` |
| 前端构建闸门 | `npm run check` = `check:types` + `check:signatures` + `check:args` + `check:ui` | [`package.json`](MF_UI/MFMath.UI.Vue/package.json) 的 `scripts`；[`docs/ui/CHECKS.md`](docs/ui/CHECKS.md) |
| 端到端 | 48 个 `cdp-*.mjs` | [`MF_UI/MFMath.UI.Vue/tests/`](MF_UI/MFMath.UI.Vue/tests/) |

```powershell
(Get-ChildItem MF_Mathematics/tests -Filter *.cpp).Count                                          # 19
(Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern 'add_test\(').Count                   # 16
(Get-ChildItem MF_UI/MFMath.UI.Vue/tests -Filter 'cdp-*.mjs').Count                               # 48
```

无头自检（不需要 WebView2，受限环境可运行），用于确认宿主本身未损坏：

```powershell
& MFMath.Host.Rust\target\release\mfmath-host-rust.exe --selftest-jobs     # 异步 job 通道
& MFMath.Host.Rust\target\release\mfmath-host-rust.exe --selftest-common   # DPAPI / sha256 / zip / HTTP
```

`--selftest-common` 的 zip 往返项需要可写临时目录；受限环境里把 `TEMP`/`TMP` 指到仓库内再跑。

## 目录结构

| 路径 | 内容 |
| --- | --- |
| [`MF_Mathematics/`](MF_Mathematics/) | 引擎：C++17，110 个 `.cpp`（不含 `build/` 与 `tests/`）；`tests/` 下 19 个可执行目标 |
| [`MFMath.Host.Rust/`](MFMath.Host.Rust/) | 现役宿主：Rust + Tauri + WebView2，9 个宿主对象；`build.rs` 负责同步引擎与 UI；`console/` 下是控制台的 Python/C++ 门面 |
| [`MF_UI/MFMath.UI.Vue/`](MF_UI/MFMath.UI.Vue/) | Vue 3 界面：`src/`（107 个文件）、`tests/`（48 个 CDP 用例）、`tools/`（构建期闸门） |
| [`MF_UI/MFMath.UI.React/`](MF_UI/MFMath.UI.React/) | React 绘图组，经 `@shared` 别名复用 Vue 侧 `src/lib/` 下与框架无关的模块 |
| [`docs/`](docs/) | 文档，入口是 [`docs/README.md`](docs/README.md) |
| [`tools/`](tools/) | 仓库级小工具 |

`MF_UI/MFMath.UI.React/` 与 Vue 侧共享 `src/lib/` 下的纯 JS 模块（经 `@shared` 别名），某个能力在 React 侧看似无引用时，在 Vue 侧仍可能是活的——查引用要同时覆盖两个工程（[`docs/ui/README.md`](docs/ui/README.md)）。

## 文档

全部文档的入口是 [`docs/README.md`](docs/README.md)，按「我想知道 X 该读哪份」编排；构建与安装的完整说明在 [`docs/manual/INSTALL.md`](docs/manual/INSTALL.md)。

| 你是 | 先读 |
| --- | --- |
| 使用者 / 评估者 | [`docs/manual/README.md`](docs/manual/README.md)、[`docs/manual/FEATURES.md`](docs/manual/FEATURES.md)、[`docs/manual/WORKFLOWS.md`](docs/manual/WORKFLOWS.md)、[`docs/manual/FAQ.md`](docs/manual/FAQ.md)、[`docs/manual/TROUBLESHOOTING.md`](docs/manual/TROUBLESHOOTING.md) |
| 想读懂代码 | [`docs/DESIGN.md`](docs/DESIGN.md)、[`docs/engine/README.md`](docs/engine/README.md)、[`docs/ui/ENGINE-BINDING.md`](docs/ui/ENGINE-BINDING.md)、[`docs/link/README.md`](docs/link/README.md) |
| 想查引擎契约 | [`docs/engine/CONTRACT.md`](docs/engine/CONTRACT.md)、[`docs/engine/MODULES.md`](docs/engine/MODULES.md)、[`docs/engine/TESTS.md`](docs/engine/TESTS.md) |
| 想知道边界 | [`docs/DESIGN-BOUNDARIES.md`](docs/DESIGN-BOUNDARIES.md)、[`docs/engine/BOUNDARIES.md`](docs/engine/BOUNDARIES.md) |
| 调宿主 / 打包 | [`MFMath.Host.Rust/README.md`](MFMath.Host.Rust/README.md)、[`MFMath.Host.Rust/docs/ACCEPTANCE.md`](MFMath.Host.Rust/docs/ACCEPTANCE.md)、[`MFMath.Host.Rust/docs/PACKAGING.md`](MFMath.Host.Rust/docs/PACKAGING.md) |

## 边界

完整清单见 [`docs/DESIGN-BOUNDARIES.md`](docs/DESIGN-BOUNDARIES.md)。容易被误解的几条：

- **数学能力边界**：不定积分对非初等函数返回「未实现」，部分不定式极限与复变不定积分同理。一个错误的原函数比「未实现」危害更大。
- **多语言只覆盖界面层**：导航、顶栏、14 个学科视图的模式名、参数弹窗标签、结果字段、键盘分类已中英双语，可在「设置 → 外观 → 界面语言」切换并记忆；页面正文与教程正文仍是中文。迁移方法是把要翻的文本包一层 `t()` 并补 `src/lib/i18n/en-*.js`，`npm run check` 会拦住漏译。
- **安装包的「安装 → 启动」路径未验证**：宿主可出 NSIS 安装包（`tauri.conf.json` 的 `bundle` 段，见 [`MFMath.Host.Rust/docs/PACKAGING.md`](MFMath.Host.Rust/docs/PACKAGING.md)），但「装完能启动」没有真机验证记录。「三步构建 + 直接运行 exe」是当前唯一可依据的路径。
- **崩溃只本地记录，不联网上报**：写入 `%LOCALAPPDATA%\MFMath\logs\`，由用户在「设置 → 存储与数据 → 导出诊断包」主动交出。
- **宿主只有一个**：`MFMath.Host.Rust/`（Rust + Tauri + WebView2）。早期的 C#/.NET 宿主已从仓库移除。

## 与 v1 的关系

v2.0 从 v1 取走 Vue 前端与引擎 C++ 源码，重写为单目录树、单一计算来源的结构。v1 的计算依赖一套 Python 后端，v2 把计算全部搬进 `mf_mathematics.dll`，v1 的 Python 后端与无法重建的二进制已从本树移除。

v1 有意保留的准确性用例资产不在本仓库，它位于：

```text
../Multifunctional-Mathematics/MF_Mathematics/tests/accuracy/
```

它是测试资产而非运行时代码，可对任意引擎 DLL 运行（用环境变量 `MF_ACC_DLL` 指定），v2 的引擎也能用它验证。

## 许可证

暂未提供许可证（保留所有权利）。依默认版权规则，未经作者许可不得复制、修改或分发。需要以其它方式使用时应联系作者。
