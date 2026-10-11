# 架构决策

> 本文记录已落地的架构决策与各自代价，每条按「背景 / 决定 / 代价」陈述。设计原则见 [`DESIGN.md`](DESIGN.md)，明确不做与未验证的部分见 [`DESIGN-BOUNDARIES.md`](DESIGN-BOUNDARIES.md)；实现入口是 [`engine/README.md`](engine/README.md)、[`ui/ARCHITECTURE.md`](ui/ARCHITECTURE.md) 与 [`link/README.md`](link/README.md)。

## 索引

| 决定 | 内容 | 主要代价 |
| --- | --- | --- |
| [C ABI 只导出两个函数](#c-abi-只导出两个函数) | 数学实现在静态库，共享库只含 `api.cpp` | 每次调用序列化 JSON，错误靠字符串约定 |
| [前端不计算](#前端不计算) | 数值与符号结果只来自引擎 | 没有宿主就没有数学，交互多一次跨进程往返 |
| [注册表靠 /WHOLEARCHIVE 保留](#注册表靠-wholearchive-保留) | 自注册对象必须全量纳入 | 失效静默，需数字守门 |
| [AI 由页面直连](#ai-由页面直连) | AI 归前端，密钥明文存 ai.json | 密钥同机可读 |
| [绘图组由 React 实现](#绘图组由-react-实现) | 7 条绘图路由指向 React，Vue 版冻结 | 留下一份不可达但需维护的代码 |
| [宿主是 Rust 与 Tauri](#宿主是-rust-与-tauri) | 现役宿主 `MFMath.Host.Rust/`，9 个宿主对象 | 早期 C# 宿主不再演进 |
| [构建期自检](#构建期自检) | `npm run check` 拦运行期难察觉的失效 | 自检本身是要维护的代码 |
| [崩溃只写本地](#崩溃只写本地) | 日志与崩溃写在用户数据目录，不上报 | 看不到线上崩溃分布 |
| [复用站点端点](#复用站点端点) | 账号、版本检测等打既有站点 | 受站点发布节奏牵制 |
| [不提供许可证](#不提供许可证) | 仓库根无 LICENSE，保留所有权利 | 他人不能合法复制、修改、分发 |

## C ABI 只导出两个函数

背景：符号计算由 SymEngine（连同 FLINT、GMP、MPFR）承担，线性代数由 Eigen 承担。这些库的接口包含 C++ 模板、`SymEngine::RCP` 智能指针与标准库容器，跨工具链没有稳定的 C++ ABI。

决定：数学实现全部放进 STATIC 目标 `mf_mathematics_core`（别名 `MFMath::engine`）。SHARED 目标 `mf_mathematics`（别名 `MFMath::cabi`）只编译 `api.cpp` 一个翻译单元，导出两个 C ABI 函数：

| 导出 | 签名 | 契约 |
| --- | --- | --- |
| `function_exists` | `bool function_exists(const char* function_name)` | 查询注册表；空指针返回 `false` |
| `math_call` | `int math_call(const char* name, const char* args_json, char* out_buffer, int out_size)` | 成功返回结果 JSON 字节数；参数为空、`out_size <= 0` 或缓冲区装不下「结果 + 结尾 `'\0'`」时返回 `-1` |

`MF_BUILD_DLL` 只由 `mf_mathematics` 定义，`mf_export.h` 的 `MF_API` 因此只在该目标上触发导出。`api.cpp` 22 行、`api.h` 18 行。

代价：每次调用在边界序列化与反序列化 JSON，采样与绘图网格为此付出开销。错误靠返回 JSON 里的 `isError` 之类的键表达，编译期不校验键名。`function_exists` 只回答有无，不回答参数形状，这是签名表副本与注册表守门存在的原因。

```powershell
(Get-Content MF_Mathematics\api.cpp | Measure-Object -Line).Lines   # 22
(Get-Content MF_Mathematics\api.h | Measure-Object -Line).Lines     # 18
Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern "MFMath::engine|MFMath::cabi"
```

## 前端不计算

背景：早期版本是「Python 后端 + 旧 JS 界面」并存，同一功能在两处各有一份实现，结果可以不一致。

决定：所有数值与符号结果只来自引擎。前端只构造参数、展示结果、编排调用。桥面是同步字符串往返 `window.chrome.webview.hostObjects.sync.mf.Dispatch(name, argsJson)`；长任务走 `mf` 对象上的异步通道（`DispatchJob` / `PollJob` / `CancelJob` / `JobStats`），由 `lib/bridge.js` 的 `engineCallAsync` 依 `DispatchJob` 是否存在决定分流。

代价：没有宿主就没有数学，「宿主未就绪」直接表现为算不出结果。每次交互多一次跨进程字符串往返；不写成异步的调用会冻结渲染进程，绘图与长计算必须显式走异步。前端不优化中间结果，包括格式化与补精度。

现状：`tests/cdp-ai.mjs` 用假端点对默认请求回 `1+1=3`，断言界面不得当作计算结果；同文件另有对照断言要求引擎算出 `1+1=2`。

```powershell
Select-String -Path MF_UI/MFMath.UI.Vue/tests/cdp-ai.mjs -Pattern "1\+1=3|1\+1=2"
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/bridge.js -Pattern "engineCallAsync|DispatchJob"
```

## 注册表靠 /WHOLEARCHIVE 保留

背景：每个 `*_api.cpp` 用一个没有外部引用的全局对象自注册（`struct Registrar { Registrar() { register_all(); } }; const Registrar g_xxx_registrar;`）。链接静态库时，链接器只抽取解决了未定义符号的目标文件，这些注册器会被整体丢弃。

决定：`mf_mathematics` 链接时加 `target_link_options(mf_mathematics PRIVATE "/WHOLEARCHIVE:$<TARGET_FILE:mf_mathematics_core>")`，并配数字守门：`list_functions` 返回的 `count` 是 424。断言写在 `tests/cdp-settings.mjs` 与 `MFMath.Host.Rust/tools/verify-spike.mjs`。

代价：失效是静默的：DLL 照常加载，`function_exists` 照常能调，只是每个 action 都返回「未找到函数」。没有 `count` 断言，问题只会在用户报障时暴露。自建导出 DLL 并链 `MFMath::engine` 的消费方要自己重复加这一个链接选项。

现状：注册表在 Release 产物上是 424；引擎签名表副本 `MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json` 是 96,794 字节 / 424 条，由 `tools/engine-signatures.mjs --check` 从 `MF_Mathematics/` 源码重建后对账。

```powershell
& MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'   # value.count = 424
Select-String -Path MF_Mathematics/CMakeLists.txt -Pattern "WHOLEARCHIVE"
npm --prefix MF_UI/MFMath.UI.Vue run check:signatures   # 源码 424 条 / 表 424 条
```

## AI 由页面直连

背景：AI 是唯一「请求形状由前端决定、且必须流式」的功能：请求体由页面组装，回复逐段显示，用户可中途停止。把它放进只能同步字符串往返的链接层无法满足流式与中断需求。

决定：AI 整体归前端 TypeScript 侧：`src/lib/ai/` 下 8 个文件 / 2,372 行。页面直接发请求，SSE 分帧与中断都在 TS 里。凭据 `apiKey` 明文存 `%LOCALAPPDATA%\MFMath\settings\ai.json`，读写只借 `sys` 宿主对象，宿主侧没有 `ai` 桥（9 个宿主对象里不含 `ai`）。

代价：DPAPI 密文换成明文文件，同机其它进程可读走密钥。界面把来源标成 `keySource: "file"`，只说明事实，不替用户保管。

现状：`tests/cdp-ai.mjs` 覆盖工具调用、SSE 分帧与「AI 不得成为计算源」。配置文件路径从 `sys.Info()` 的 `settingsDir` 拼出，读不到时退化成字面量路径并如实报错。

```powershell
(Get-ChildItem MF_UI/MFMath.UI.Vue/src/lib/ai -Recurse -File -Include *.ts,*.js | Get-Content | Measure-Object -Line).Lines
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/ai/bridge.js -Pattern "aiConfigPath|keySource"
Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "HOST_OBJECTS"
```

## 绘图组由 React 实现

背景：Vue 外壳内嵌独立 React 绘图工程（`MF_UI/MFMath.UI.React/`），它与外壳共用 `MFMath.UI.Vue/src/lib` 下与框架无关的纯 JS 计算 / 绘图库。绘图页有 7 个：2D、极坐标、3D、复平面、向量场、几何、分形。

决定：7 条 `/plot/*` 路由全部指向 `components/plot-react/ReactPlotView.vue`，由它按页面键动态 import 对应 React 组件。Vue 版 `src/views/plot/` 的 6 个 `.vue` 文件不删除，冻结为回退资产：不参与构建、不在类型检查范围、没有用例覆盖。冻结靠 `tools/check-ui.mjs` 的 `FROZEN_VUE_PLOT_FILES` 双向断言：目录里出现白名单外的文件或白名单文件消失，自检失败；同时确认没有文件 import 它们。

代价：仓库留有一份不可达但需维护的代码，删除更干净但失去回退路径。迁移期只过类型检查不真跑，会漏掉只在运行期可见的失效；相关回归判据在 `tests/cdp-plot-*.mjs` 与 `tests/cdp-plot-workspace.mjs`。

现状：自检输出「冻结的 Vue 绘图组：6/6 个文件在位，被 import 0 处」。React 工程 `src/` 下 37 个源文件 / 6,340 行，独立跑 `npm run check:types`（`tsc --noEmit`）。

```powershell
npm --prefix MF_UI/MFMath.UI.React run check:types
(Get-ChildItem MF_UI/MFMath.UI.React/src -Recurse -File | Get-Content | Measure-Object -Line).Lines
Select-String -Path MF_UI/MFMath.UI.Vue/tools/check-ui.mjs -Pattern "FROZEN_VUE_PLOT_FILES"
```

## 宿主是 Rust 与 Tauri

背景：桌面外壳早期是 C# / WPF + WebView2，第二次实现是 Rust + Tauri v2 + WebView2（`MFMath.Host.Rust/`）。两套并存意味着同一份桥面契约有两处实现。

决定：宿主只有 `MFMath.Host.Rust/`；早期的 C# / WPF 宿主已从仓库移除。接缝形状固定：

- 窗口手工创建（`tauri.conf.json` 里 `create: false`），因为 Tauri 会强制指定 WebView2 数据目录，而 `app_local_data_dir()` 走 known-folder API、不读 `LOCALAPPDATA` 环境变量。宿主用 `data_directory()` 指定 `webview_data_dir()`。
- 宿主对象走 COM：`with_webview()` 取 `ICoreWebView2` 再 `AddHostObjectToScript`，前端的同步调用原样可用。这否掉全异步 `invoke` 路线，`mf.Dispatch` 是采样链与绘图网格的热路径。Tauri 的 `invoke` 命令层已删。
- UI 资产从 exe 同目录的 `wwwroot` 读，映射到 `https://mfmath.local/index.html`；`MF_WWWROOT` 可指向别处，`wwwroot` 缺失时退回 Tauri 内嵌资产。不内置 Vite dev server 集成。

宿主对象表 `HOST_OBJECTS` 共 9 项 / 84 个方法：

| 对象 | 方法数 | 内容 |
| --- | ---: | --- |
| `mf` | 16 | 引擎调用与异步 job 通道 |
| `sys` | 8 | 设置、存储、诊断包导出 |
| `diag` | 1 | 前端异常写入宿主日志 |
| `win` | 9 | 窗口操作与文件对话框 |
| `push` | 3 | 宿主到页面推送 |
| `update` | 6 | 更新检查，只提示不自动安装 |
| `account` | 19 | 用户系统，token 只在宿主 |
| `search` | 12 | 联网搜索，App ID 只在宿主 |
| `con` | 10 | 控制台与可选组件 |

窗口行为与 C# 宿主对齐：无边框、1240×820、最小 980×640、DWM 圆角与投影、数据目录 `%LOCALAPPDATA%\MFMath`、CDP 端口 9222。

代价：早期的 C# 宿主实现细节（桥面契约、DPAPI、搜索解析器）不再维护。`tests/run-all.ps1` 的宿主解析顺序是 `$env:MF_HOST_EXE` 再到 `..\..\..\MFMath.Host.Rust\target\release\mfmath-host-rust.exe`。安装到启动的路径尚未在真机验证，打包步骤见 [`PACKAGING.md`](../MFMath.Host.Rust/docs/PACKAGING.md)。

现状：无头自检 `--selftest-jobs` 与 `--selftest-common` 不需要 WebView2，验收基线见 [`ACCEPTANCE.md`](../MFMath.Host.Rust/docs/ACCEPTANCE.md)。

```powershell
Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "MethodSpec \{ name:" | Measure-Object
Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "HOST_OBJECTS"
& MFMath.Host.Rust\target\release\mfmath-host-rust.exe --selftest-common
```

## 构建期自检

背景：有一类缺陷不报错不崩溃：控件不存在却标「已完成」，模式有引擎映射却选不到，参数填了但引擎没收到，i18n 键漏译文。它们运行期表现成「点了没反应」，人工点查不可靠。

决定：这类问题统一放进构建期自检。`npm run check` 的顺序是 `check:types` → `check:signatures` → `check:args` → `check:ui`，其中 `check:ui` 跑 `tools/build-tutorials.mjs`、`tools/check-ui.mjs`、`tools/check-examples.mjs`。当前实跑输出（exit 0）的关键行：

| 检查项 | 结果 |
| --- | --- |
| 引擎模式可达性 | 映射 415 个 / 页面并集 391 个 / 取不到 0 个 |
| 区间参数契约 | 10 个 handler / 命中 10 个 / 缺 interval 0 个 |
| 冻结的 Vue 绘图组 | 6/6 个文件在位，被 import 0 处 |
| 重名模式登记 | 已登记 24 个，未登记 0 个 |
| i18n 模式名 | 415 个模式，缺译文 0 个 |
| 教程引用 target | 30 个（已实现 30，待实现 0） |
| 数学键盘 | 6 分类 / 126 键 |
| 端到端用例 | cdp-* 48 个，已登记 48 个 |

代价：自检本身是要维护的代码，`tools/check-ui.mjs` 35,468 字节；加界面、模式或 i18n 键都要同步登记。`check-ui.mjs` 不读引擎源码（那是树外路径），检查的是登记表，登记表写错它抓不到；真正读引擎源码对账的是 `tools/engine-signatures.mjs`。运行期才可见的行为（布局、绘制、交互时序）靠端到端用例，构建期自检替代不了。

```powershell
npm --prefix MF_UI/MFMath.UI.Vue run check
(Get-Item MF_UI/MFMath.UI.Vue/tools/check-ui.mjs).Length
```

## 崩溃只写本地

背景：桌面应用通常接崩溃上报服务，把崩溃、设备信息与调用栈汇总到服务端。数学工具的使用内容可以反推用户在研究什么。

决定：崩溃与前端未捕获异常只写本地。日志目录是 `%LOCALAPPDATA%\MFMath\logs`，常规日志写 `app.log`（单文件 2 MB 轮转成 `app.1.log`），崩溃另写 `crash-*.log`（含环境、异常、backtrace 与最近 200 行 `app.log` 尾部），崩溃文件只留最近 20 个。用户可在「设置 → 存储与数据 → 导出诊断包」主动交出（`sys` 对象的 `ExportDiagnostics`）。不上报。

代价：看不到线上崩溃分布，只能等用户报障。排障需引导用户导出日志。隐私与可观测性不可兼得，这里选隐私。

```powershell
Select-String -Path MFMath.Host.Rust/src/logging.rs -Pattern "MAX_BYTES|KEEP_CRASH_FILES|CRASH_TAIL_LINES"
Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "install_panic_hook"
```

## 复用站点端点

背景：账号、组件清单、版本检测需要服务端。早期版本有一套自建后端。

决定：这些能力复用既有站点的 HTTP 端点，默认基址 `https://mf-vis-science.cn`（`MFMath.Host.Rust/src/site.rs` 的 `DEFAULT_BASE_URL`，超时默认 20 s，`normalize_base_url` 负责规范化）。端点路径以 `MFMath.Host.Rust/src/account.rs` 与 `site.rs` 为准：

| 用途 | 路径 |
| --- | --- |
| 登录 / 登出 / 当前用户 | `/api/login`、`/api/logout`、`/api/me` |
| 注册与验证码 | `/api/register`、`/api/send-code`、`/api/verify-code`、`/api/resend-code` |
| 凭据续期与其它 | `/api/token/refresh`、`/api/change-password`、`/api/login-history`、`/api/version` |

代价：客户端受站点发布节奏牵制，线上未部署某路由时对应功能就是半成品，降级行为需由客户端写好并在界面说明。契约漂移由客户端承担。

现状：站点部署状态需从客户端核对，不凭印象写。本环境对该域名的外连未建立，因此本文不给出线上状态结论，只给出核对方法：对一个已部署的 `POST` 端点，期望返回不是 404。

```powershell
Select-String -Path MFMath.Host.Rust/src/account.rs -Pattern "/api/"
Invoke-WebRequest -Method Post -Uri https://mf-vis-science.cn/api/token/refresh -SkipHttpErrorCheck
```

## 不提供许可证

背景：公开仓库通常带 MIT / Apache-2.0 一类许可证，读者默认公开即可自由使用。

决定：仓库根没有 `LICENSE` 或 `COPYING` 文件，依默认版权规则保留所有权利：未经作者许可不得复制、修改或分发。README 的「许可证」一节显式写明这一点。

代价：他人不能合法使用、修改或分发，包括评估，需先取得作者许可。仓库放在公开平台却没有许可证，易被误认为开源，因此 README 显式说明。这是作者保留后续授权选择权，不是漏加文件。

```powershell
Get-ChildItem -File | Where-Object { $_.Name -match 'LICENSE|COPYING' }
Select-String -Path README.md -Pattern "许可证"
```
