# MFMath 链接层：现状、断点与迁移方案

> **范围**：`MFMath.Host.Rust/src/**`（宿主侧）↔ `MF_UI/MFMath.UI.Vue/src/lib/**`（前端桥；React 绘图页经
> `@shared` 别名用的是**同一份**，见 `MF_UI/MFMath.UI.Vue/vite.config.js:40-44`）。
>
> **目的**：把链接层的现状、断点、可选路线与验收方式一次写清，作为后续改动的唯一依据。
>
> **证据标注**：**【实测】** = 本次在本机读码 / 跑命令得到；**【引用】** = 引自仓库既有文档（标了出处）。
> 没标的一律当"待核实"，别当结论用。
>
> **维护规矩**：**改完就更新本文**。哪一条不再成立就删掉 —— 留着一份过时的分析，
> 比没有分析更坏（v1 的「34/66 步失效」就是这么来的）。

---

## 0. 一句话结论【实测 · 2026-10-07 更新】

**接缝形状已经落地：同步宿主对象在 Tauri 下跑通了**（路线 A）。前端那 15 处访问器与 47 个 CDP
用例**一行都没改**，`mf.Dispatch` 是同步函数、返回字符串、引擎真的在算。

- 已实现 **7/10** 个宿主对象：`mf`（16 个方法，含 job 通道）、`win`（10）、`sys`（8）、`diag`（1）、
  `push`（3）、**`update`（6）**、**`account`（19）**；
- 页面 URL 恢复成 **`https://mfmath.local/index.html`**（读 exe 同目录的 `wwwroot`，与 C# 宿主同一份）
  —— 47 个用例的取页正则不用动；
- 剩余 3 个：`search`、`con`（控制台/组件，最重）、`ai`。

### 0.1 当前验收基线（2026-10-07，11 组用例，**已提交版本**）

| 套件 | 结果 | 失败项归属 |
| --- | --- | --- |
| `cdp-basic-calc` / `cdp-bridge-verify` / `cdp-window-shell` / `cdp-plot-verify` | 41/0 · 7/0 · 25/0 · 9/0 | — |
| `cdp-account` / `cdp-update` | **52/0 · 37/0** | — |
| `cdp-export-image` | 43/2 | 导出状态行文案（**改动前就有的 2 项**，与链接层无关） |
| `cdp-settings` | 40/3 | `con`×2 · `search`×1 |
| `cdp-workspace` | 20/5 | `con`（控制台页载荷）+ React 绘图页自身的载荷 |
| `cdp-history-search` | 18/3 | `search` |
| `cdp-push` | 14/6 | `con`（控制台运行 / 组件安装两段） |

**19 项失败全部能追到 `con` / `search`** —— 也就是剩下要补的两个桥。
（另有 `verify-spike` 10/0、`--selftest-jobs` 5/5、`--selftest-common` 10/0 三条无头验收。）

### 0.2 本轮实测记录（2026-10-07）

**做成了什么**

| # | 事 | 关键点 |
| --- | --- | --- |
| 1 | **同步宿主对象接回 Tauri** | `with_webview()` → `PlatformWebview::controller()` → `ICoreWebView2::AddHostObjectToScript`。`hostobject.rs` 从 git 捞回（它已经有 `ITypeInfo` + 对 `PROPERTYGET` 返回 `DISP_E_MEMBERNOTFOUND` 这两个关键修复，README §四说的"下一步"其实早写好了） |
| 2 | **UI 走 `wwwroot` + 虚拟主机** | `SetVirtualHostNameToFolderMapping("mfmath.local", <exe>/wwwroot)` + `ICoreWebView2::Navigate`，与 C# 宿主的 `MainWindow.xaml.cs:187-192` 逐字一致。新增 `tools/sync-wwwroot.mjs`（默认拷到 `target/debug/wwwroot`，`MF_WWWROOT` 可指到别处） |
| 3 | **`push` 桥** | `PostWebMessageAsJson` + 信封 `{topic,seq,ts,payload}`。`cdp-push` 从"崩"变成 **14/6**（余下 6 项全在需要 `con` 的两段） |
| 4 | 验收 | `verify-spike` **10/0**、`cdp-bridge-verify` **7/0**、`cdp-basic-calc` **41/0**、`cdp-window-shell` **25/0**、`cdp-plot-verify` **9/0** |
| 5 | **共享件**（`dpapi` / `http` / `pack`） | DPAPI 逐字兼容 C#（**不传 entropy**，否则两个宿主的密文互相解不开）；HTTP 用 reqwest+rustls+**ring**；sha256 与 zip（**自带路径穿越防护，整包拒绝**）；新增 `--selftest-common` |
| 6 | **`update` 桥** | 版本关系判定（1.10.0 > 1.9.9、预发布小于正式版）、信封解析、协议闸门。`cdp-update` **37/0** |
| 7 | **`account` 桥**（19 方法） | 离线优先（`Info()` 不碰网络）、token 只在宿主、失败不合并、临期静默续期。`cdp-account` **52/0** |
| 8 | **部署接进构建** | `build.rs` 自动把引擎 DLL 与 `dist`→`wwwroot` 放到 exe 同目录（只在新时拷、缺了只警告） |
| 9 | **启动失败可观测** | panic 钩子写 `crash-*.log`（含 backtrace + app.log 尾部）；WebView2 起不来给可读原因 + 非阻塞提示框 |
| 10 | **取包代理的 bug** | `Readable.fromWeb(...).pipe(res)` 不转发错误 → 上游抖一次就**杀掉 Node 进程**，cargo 只看到 `Connection was reset`。改用 `pipeline` + 重试 + 进程兜底 |
| 11 | **`--selftest-jobs` 竞态** | 第 5 项盲睡 250 ms 后取消，而本机那次 mandelbrot 恰好 ~253 ms 跑完 → 随机红。改成轮询到"真的在跑"再取消，连跑三次 5/5 |

**踩到的坑（都在代码注释里留了原话，别再踩）**

| 坑 | 现象 | 根因 | 修法 |
| --- | --- | --- | --- |
| **DWM 常量写错** | 无边框窗口**底部/两侧多出一圈"WinForm 味"的老式边框** | `winbridge.rs` 把 `DWMWA_NCRENDERING_POLICY` 传成 `1`（= `DWMNCRP_DISABLED`），注释却写着 ENABLED。DWM 一被关掉非客户区渲染，Windows 就退回**未主题化的经典边框**；tao 又把客户区铺满窗口，于是只在底部与两侧露出来 | 改成 `2`（= `DWMNCRP_ENABLED`，与 C# `MainWindow.xaml.cs:15` 一致） |
| **启动白窗口** | 一启动就是**一整块纯白**窗口（实测 0.2/0.45/0.8 秒三帧），1.3 秒后才出界面 | `about:blank` 的底色是白的，而窗口建出来就显示 | `visible(false)` + `on_page_load(Finished)` 才 `show()`；6 秒兜底；另把 WebView2 的 `DefaultBackgroundColor` 设成主题底色 |
| **push：重入** | `push.Emit` 永不返回、页面失去响应 | 在**同步宿主对象回调里**直接调 `PostWebMessageAsJson` —— 浏览器进程正等我们返回 | 改成"回调返回后再发"（见下） |
| **push：假延后** | 以为推迟了，其实没有 | `tauri::AppHandle::run_on_main_thread` 在主线程上会**就地执行**（tauri-runtime-wry `lib.rs:263`） | 从 **worker 线程**调它，才会走 `proxy.send_event` 真排队 |
| **push：跨公寓** | 编组直接失败 `REGDB_E_IIDNOTREG 0x80040155`；拿裸指针换线程调则宿主当场消失 | `ICoreWebView2` 既非 agile、也没注册 proxy/stub | 放弃跨线程直调；`SetTimer` 也不可靠（挂上了但回调一次都没被调用） |
| **push：悬垂指针（真元凶）** | 与"重入"**一模一样**：页面卡死、或宿主静默消失（stderr / 崩溃日志 / WER 转储里一条都没有） | 只存了 `core.as_raw() as usize`，而那个引用来自 `with_webview` 闭包，闭包结束就 Release 了 | `CoreHandle` AddRef 一份并由 `OnceLock` 持有到进程结束 |
| **C 依赖编不过（D8050）** | reqwest 默认后端 `aws-lc-sys`、以及换成 `ring` 之后，都报 `cl.exe D8050：未能将命令行放入调试记录中` | **不是编译器坏** —— 受限令牌下 `%TEMP%` 不可写（与 README §五.3 的 esbuild 同类） | `TEMP`/`TMP` 指到仓库内再编。选 `ring`（`rustls-no-provider` + `install_default()`）避开动辄编一堆 C 的 aws-lc-sys |
| **工作区内镜像不能写外** | 宿主在 `target/debug` 下跑时，日志/设置/WebView2 数据目录**全静默失败**，用例莫名变红 | 本机沙箱对"镜像位于工作区内"的进程限制写入范围 | 端到端测试把 exe+DLL+wwwroot 拷到工作区外（`%TEMP%\mfhost-run`）再跑 |
| **旧理由被推翻（Schannel）** | README §三 写"本机 Schannel 不可用，所以用 rustls" | 服务器抓包定案：RST 是**本机发的**，真凶是开发机沙箱的出站阻止规则，只对部分进程生效 | rustls 仍然用，但**理由改成**"不依赖系统 TLS 配置、与 Chromium 那条链一致"；并明确**不要**因为"某台机器连不上"去关系统代理 |

**还没做**

- `search`（进行中）、`con`、`ai` 三个桥。
- **用例顺序会互相影响**：`cdp-export-image` 紧跟 `cdp-plot-verify` 在同一宿主会话里跑会掉到 **20/13**
  （单独跑是 **43/2**，与改动前一致）。这与 `docs/STATUS-and-ROADMAP.md` 风险台账里 `cdp-plot-p5`
  那条是同一类问题：**成套跑时最好让每个用例独占一个宿主进程**。
- 一批 edition-2024 的 `unsafe_op_in_unsafe_fn` 警告（`hostobject.rs`，~40 处，纯噪音）、
  `cstr_lossy`/`stamp_min` 死代码。
- `apply_dwm_chrome` 保留但仍未被调用（现用系统标题栏时不需要）；要换回无边框就调它，
  值已修对（`DWMNCRP_ENABLED = 2`）。
- 本机沙箱特性（只影响我这类自动化）：**镜像位于工作区内的进程不能写工作区外**，
  所以宿主在 `target/debug` 下跑时写不了 `%LOCALAPPDATA%`（日志/设置全部静默失败）。
  测试时把 exe + DLL + wwwroot 拷到工作区外（如 `%TEMP%\mfhost-run`）即可。

> ⚠ 下面 §3 的"现状实测"是**本轮改动之前**的快照（2026-10-07 上午），保留它是为了记录当时的判断依据；
> 现在的状态以本节为准。

---

## 1. 链接层是什么

### 1.1 三层与职责

| 层 | 位置 | 对外面 |
| --- | --- | --- |
| 引擎 | `MF_Mathematics/`（C++） | 只有两个 C ABI：`math_call(name, args_json, out, size)` / `function_exists(name)`；424 个 action |
| **宿主** | `MFMath.Host/`（C# WPF+WebView2，现役）、**`MFMath.Host.Rust/`（迁移中）** | 窗口 + WebView + **10 个宿主对象** |
| 前端 | `MF_UI/MFMath.UI.Vue/`（Vue 外壳 + React 绘图页） | 22 个模式视图、7 个绘图页、控制台、设置、教程 |

链接层 = 上表中间那一列与前端 `src/lib/**` 之间的**那条缝**。它是这次"换宿主"唯一不能靠改配置绕过去的东西。

### 1.2 契约（三条，逐字对齐 C#）

1. **成员名 PascalCase、大小写敏感**。写 `mf.dispatch` 不是返回 `undefined`，而是抛 `0x80070057`。
   仓库里已经为这个故障排查过两次（`src/lib/diagnostics/errors.js:62-67` 有原话）。
2. **返回值一律 JSON 字符串**，前端统一 `JSON.parse`。所以宿主侧返回的是"文本"，不是对象。
3. **错误也走信封**：`{"isError":true,"value":"原因"}`。Rust 侧是 `src/handlers.rs:41` 的 `err_envelope`，
   与 C# `MathBridge.Dispatch` 逐字一致 —— 这样前端 `parse()` 那一层不用区分是谁在回话。

### 1.3 十个宿主对象（两侧落点与现状）

前端调用的方法名是从各 `bridge.js` 的实调点里数出来的【实测】；Rust 侧现状读自 `src/handlers.rs:86-94`【实测】。

| 对象 | 前端模块 | 前端实际调用的方法 | C# 源 | **Rust 现状** |
| --- | --- | --- | --- | --- |
| `mf` | `src/lib/bridge.js` | Ready, Version, Dispatch, **DispatchJob, PollJob, CancelJob**, FunctionExists | MathBridge.cs | ✅ 全部实现，另加 `JobStats` |
| `win` | `src/lib/bridge.js`、`settings/io.js` | Minimize, ToggleMaximize, Close, StartDrag, IsMaximized, SetChromeBackground, SaveTextFile, OpenTextFile, SaveBinaryFile | WindowBridge.cs | ✅ 全部实现（含**前端从不调用的** `Restore`，见 §6.1） |
| `sys` | `settings/bridge.js`、`settings/io.js`、`ai/bridge.js`、`update/bridge.js` | Info, EngineReport, StoreList, StoreRead, StoreWrite, StoreDelete, OpenPath, ExportDiagnostics | SettingsBridge.cs | ✅ 全部实现 |
| `diag` | `diagnostics/errors.js` | Front | LogBridge.cs | ✅ 实现（另有独立命令 `front_log`，见 §6.3） |
| `push` | `push.js` | Info, Emit ＋ `chrome.webview` 的 `message` 事件 | PushBridge.cs / PushHub.cs | ❌ **缺**（`handlers::call` 返回"未知宿主对象"） |
| `con` | `console/bridge.js` | Components, Install, Uninstall, CancelInstall, InstallStatus, SetDownloadBase, Start, Poll, Stop, StopAll | ConsoleBridge.cs（824 行） | ❌ **缺** |
| `ai` | `ai/bridge.js`、`ai/relay.ts` | Info, Configure, SetKey, ClearKey, Test, SelfCheck, Begin, Cancel, Busy | AiBridge.cs / AiRelay.cs | ❌ **缺** |
| `search` | `search/bridge.js` | Info, Configure, SetWolframKey, ClearWolframKey, Start, Cancel, CancelAll, OpenUrl, CacheStats, ClearCache, SelfCheck | SearchBridge.cs 等 | ❌ **缺** |
| `account` | `account/bridge.js` | Info, Configure, LoginEx, Logout, RefreshProfile, RefreshToken, EnsureFresh, ClearLocal, Register, SendCode, VerifyCode, ResendCode, ChangePassword, LoginHistory, SiteVersion, SelfCheck, Busy, CancelAll | AccountBridge.cs 等 | ❌ **缺** |
| `update` | `update/bridge.js` | Info, Check, OpenDownloadPage, PreviewDownloadUrl, CancelAll, SelfCheck | UpdateBridge.cs | ❌ **缺** |

> `mf` 的 `*Symbolic` 八个具名封装（SolveSymbolic / DiscriminantSymbolic / FactorSymbolic / CompareExpr /
> SimplifySymbolic / ExtremaSymbolic / FreeSymbols / Differentiate）Rust 侧已实现（`SYMBOLIC_ALIASES`）。
> 前端**不走**它们，是端到端用例与 C# 公开 API 在用。

### 1.4 下行通道（宿主 → 页面）

这是链接层的**另一半**，容易被漏掉：推送是**旁路**，权威数据仍在同步桥上，推送只负责"及时"。

机制【实测】：C# 侧 `PushHub.Send(topic, payloadJson)` → `PostWebMessageAsJson`；
JS 侧 `push.js` 在 `chrome.webview` 上挂 `message` 监听，按 `{topic, seq, ts, payload}` 信封分发。

| 主题 | 生产者（C#） | 页面订阅者 |
| --- | --- | --- |
| `component.install` | ConsoleBridge.cs:386 | `components/settings/ComponentsGroup.vue:74` |
| `console.run` | ConsoleBridge.cs:400 | `views/tools/ConsoleView.vue:354` |
| `search.done` / `search.error` | SearchBridge.cs:349/355 | `lib/search/bridge.js:204`（按 `search.` 前缀） |
| `ai.http` / `ai.raw` / `ai.rawEnd` / `ai.rawError` | AiRelay.cs:180/240/214/246 | `lib/ai/relay.ts:102-104` |
| `ai.test` | AiBridge.cs:281 | `lib/ai/bridge.js:237` |
| `account.changed` | AccountBridge.cs:133 | `lib/account/bridge.js:182` |
| `settings.test` | **页面自己**经 `push.Emit` 发，宿主回推（往返自检） | `components/settings/EngineGroup.vue:38` |

> Tauri 里这套机制**能平移**：Rust 侧用 `app.emit()` / `webview.eval()`，页面侧用 Tauri 的 `listen()`。
> 但**形状会变**（Tauri 的事件名是扁平的），`push.js` 的信封与 seq 连续性检查需要重写而不是照搬。

---

## 2. 为什么它是这次迁移唯一可能翻车的点

### 2.1 同步是硬需求，而且用在热循环里【实测】

| 调用点 | 形状 |
| --- | --- |
| `MFMath.UI.React/src/plot/usePlotSampling.ts:36-42` `batchEval()` | **每条曲线一次**同步 `engineCall("expr_eval_vars_batch", …)`，在自适应采样循环里 |
| `PlotPage.tsx:173 / 208 / 224 / 331` | 交点、局部极值、符号驻点、参数点求值，都是同步 |
| `Plot3DPage.tsx:118`、`PlotVectorPage.tsx:124-125`、`PlotComplexPage.tsx:141/162` | 曲面/向量场/复平面的网格，一次同步大批量 |
| `src/lib/engine/asyncPolicy.js:12-16` | 原话：「绘图页里"每条曲线一次"的采样/极值标记**保持同步**：那些是毫秒级，而且一条曲线一个 await 会把采样时序拆碎，得不偿失」 |

### 2.2 47 个 CDP 用例就是链接层的验收【实测】

`MF_UI/MFMath.UI.Vue/tests/` 下 **47 个** `cdp-*.mjs`。它们的共同前提有两条：

1. 用 CDP 连 `127.0.0.1:9222`，按 URL 正则 `/mfmath\.local|index\.html/` 找页面
   （例：`tests/cdp-bridge-verify.mjs:8`）；
2. 断言直接打在宿主对象上：`window.chrome.webview.hostObjects.sync.mf.FunctionExists('solve_sym')`
   （`tests/cdp-bridge-verify.mjs:43-58`）。

**47 个用例同时也是"接缝形状"的回归网**：形状一改，它们全废。

### 2.3 Tauri 给不了同步

`invoke()` 只返回 Promise。而 JS 在主线程上**没有任何办法**阻塞等一个 Promise。
WebView 里真正能同步取值的通道只有两条：**COM 宿主对象**（`AddHostObjectToScript`）与
**同步 XHR**。所以 §5 的三条路线本质上就是"用哪条同步通道 / 要不要放弃同步"。

---

## 3. 现状实测

### 3.1 Rust 侧：四分之一

`src/handlers.rs:86-94` 的 `match object` 只有 `mf` / `sys` / `diag` / `win` 四个分支，
其余走 `other => err_envelope("未知宿主对象：{other}")`。

`src/commands.rs` 只注册了三条命令：`call` / `host_info` / `front_log`（`src/main.rs:110-114`）。

### 3.2 JS 侧：只有 `win` 迁了

全仓库认识 Tauri 的地方**只有一处**：`src/lib/bridge.js:459-473` 的 `tauriInvoke()` / `tauriHostCall()`，
且**只被 `callWin()`（:481-497）与 `winIsMaximized()`（:510-522）使用**。

其余 **15 处**宿主对象访问器仍是 `window.chrome?.webview?.hostObjects?.sync?.<对象> ?? null`【实测】：

```
lib/bridge.js:92 (mf), :446 (win)        lib/console/bridge.js:14 (con)
lib/settings/bridge.js:14 (sys)          lib/search/bridge.js:21 (search)
lib/settings/io.js:35 (sys), :38 (win)   lib/account/bridge.js:18 (account)
lib/push.js:39 (push)                    lib/update/bridge.js:16 (update), :19 (sys)
lib/diagnostics/errors.js:26 (diag)      lib/ai/bridge.js:34 (ai), :180 (sys), :192 (sys)
                                         lib/ai/relay.ts:76 (ai)
```

关键后果：**`engineCall()` 走的是 `bridgeObj()`（`lib/bridge.js:90-96`）**，它在 Tauri 里是 `null`，
于是 `engineCall()` 直接 `return null`（`lib/bridge.js:127-136`）——引擎一次都调不到。

### 3.3 失效矩阵

| 能力 | C# 宿主 | **Rust/Tauri 宿主（现在）** | 原因 |
| --- | --- | --- | --- |
| 窗口最小化/最大化/关闭/拖拽/背景色 | ✅ | ✅（异步发、不读结果） | `lib/bridge.js:481-530` 有 Tauri 分支 |
| 是否最大化（顶栏图标） | ✅ 同步 | ⚠️ 返回**上次已知值**，异步刷新 | `lib/bridge.js:510-522` |
| **引擎调用（算数、绘图）** | ✅ 同步 | ❌ 返回 `null` | `engineCall` 无 Tauri 分支 |
| 异步重活（mandelbrot 等） | ✅ | ❌ | `mf` 访问器是 `null` |
| 设置读写（`sys`） | ✅ 落盘 | ⚠️ **静默降级到 localStorage** | `settings/bridge.js:34-43` |
| 文件对话框（另存为/打开/导出图片） | ✅ | ❌ 返回「无宿主」 | `callWinJson` 只认 `winBridge()`（`lib/bridge.js:539-549`） |
| 前端异常入 app.log（`diag`） | ✅ | ❌ 只在控制台 | `errors.js:60-68`；Rust 侧其实已有 `front_log` 命令 |
| 推送（控制台/组件/AI/搜索/账号） | ✅ | ❌ | `push.js:37-43` + 无 Tauri 事件桥 |
| 控制台（`con`） | ✅ | ❌ | 对象未实现 |
| AI / 搜索 / 账号 / 更新 | ✅ | ❌ | 对象未实现 |

### 3.4 验收链为什么现在一条都跑不了

两条**独立**的原因，改一条不够：

1. **找不到页面**：47 个用例都按 `/mfmath\.local|index\.html/` 过滤 CDP 的页面列表。
   C# 宿主用虚拟主机映射 `mfmath.local`；Tauri 的资产协议在 Windows 上预期是 `http://tauri.localhost/`，
   **两个正则都不匹配** → 用例在第一步就 `未找到宿主页面` 退出。
   （**【待核实】**：需起宿主后用 `curl 127.0.0.1:9222/json/list` 实测 URL 到底是什么。）
2. **没有同步桥**：即使连上页面，`hostObjects.sync.mf` 仍不存在，断言会全红。

另外本目录自带的两个工具**已经过期**【实测】：

- `tools/verify-spike.mjs:73-99` 断言的正是 `hostObjects.sync.mf.Dispatch` 是**同步函数**、返回值是字符串 —— 那是 wry 时代的验收；
- `tools/probe-hostobject.mjs` 是当时为排查 S2 卡点（`mf.Dispatch` 读出字符串）写的探针，同理过期。

**结论：Rust 宿主现在没有任何一条有效验收。**

### 3.5 编译产物现状【实测】

| 事实 | 证据 |
| --- | --- |
| `target/debug/mfmath-host-rust.exe` 确实是 **Tauri 构建**（不是 wry 遗留） | exe 里含 `com.mfvis.mfmathematics`（来自 `tauri.conf.json` 的 identifier）、`Tauri`、`__TAURI`、`tauri://webview-created`；`target/debug/deps/` 里有 `libtauri_runtime_wry-*` |
| exe 时间戳 = 2026-10-07 01:54:13，晚于 `tauri.conf.json`(01:53:53) / `build.rs`(01:43) / `main.rs`(01:20) | 即最后一次源码改动之后**成功链接过** |
| **前端资源是编译期嵌进 exe 的** | exe 里含资产键 `assets/index-BeZSahQQ`、`index.html`；但**正文串搜不到**（`mf_theme`、`液态玻璃` 均 MISS）——Tauri 对嵌入资产做 brotli 压缩 |

> ⚠ 最后一条对本项目是个**工作流变更**：C# 宿主是"`dist` 拷进 `wwwroot`"（改前端只要 `dotnet build`，
> 见 `docs/STATUS-and-ROADMAP.md` 附录 B 的告诫）；**Tauri 宿主必须重新 `cargo build` 才会带上新前端**。
> 迁移期两边并存时，这一条最容易让人对着旧界面白跑一轮。

---

## 4. 构建与运行闭环

### 4.1 本机两条特殊处理（README §五 已写，仍然成立）

1. `CARGO_HOME` 必须在**仓库内**（`<repo>\.cargo-home`，实测 **487 MB / 15582 文件**）：本机 Schannel
   在受限令牌下不可用，用户级的 `~/.cargo` 也可能不可写。
2. crates 走**本地明文代理**：`node MFMath.Host.Rust/tools/crates-proxy.mjs`（`127.0.0.1:8432`），
   cargo 只走明文 HTTP，由 Node 用 OpenSSL 去 HTTPS 取包。
   **它不在跑的时候 `cargo` 会直接失败**（实测：`download of ta/ur/tauri failed … Connection was reset`）。

### 4.2 沙箱下的实测限制

本次会话的文件沙箱是 `workspace-write`，**工作区 = `MFMath.Host.Rust`**，而 `.cargo-home` 在它的**上一级**：

```text
warning: failed to write cache, path: …\.cargo-home\registry\index\…\ta/ur/tauri-build,
         error: 拒绝访问。 (os error 5)
error: failed to download replaced source registry `crates-io`
Caused by: failed to open …\.cargo-home\registry\cache\…\adler2-2.0.1.crate
Caused by: 拒绝访问。 (os error 5)
```

也就是说：**在这个沙箱里我没法直接 `cargo build`**。三条可行做法（选一条即可）：

| 做法 | 代价 |
| --- | --- |
| 给一次更大权限的一次性放行（写工作区之外） | 需要你批准一次 |
| `CARGO_HOME` 指到工作区内的新目录，从 `..\.cargo-home` 拷一份过去 | 多占约 500 MB，但之后完全自洽 |
| 你在自己的终端里构建（README 的原流程），我只读产物与日志 | 构建不占我的会话，但迭代慢 |

### 4.3 可观测点（验收时要用的）

| 观测量 | 位置 |
| --- | --- |
| 启动自检（引擎在不在、注册了多少 action） | 启动时 `note()` 写的那一行「引擎自检：…」，见 `src/main.rs:70` |
| 异步任务通道的**无头**自检（不需要 WebView2） | `mfmath-host-rust.exe --selftest-jobs`（`src/jobs.rs:294-373`，五项 PASS/FAIL + `RESULT|` 行） |
| 宿主日志 / 崩溃记录 | `%LOCALAPPDATA%\MFMath\logs\app.log`、`crash-*.log`（`src/logging.rs`） |
| CDP | `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222`（`src/main.rs:64-68` 已自动设置） |
| WebView2 用户数据目录 | `MF_WEBVIEW2_DIR`，默认 `%LOCALAPPDATA%\MFMath\webview2` |

---

## 5. 方案：**先定形状，再补对象**

### 5.1 三条路线

| 路线 | 做法 | 前端改动 | 风险 |
| --- | --- | --- | --- |
| **A. 恢复同步宿主对象** | Tauri 的 `WebviewWindow::with_webview()` 在 Windows 上能拿到 `ICoreWebView2Controller` → 自行调 `AddHostObjectToScript`；把删掉的 `src/hostobject.rs` 写回来，并补上当初卡的 `ITypeInfo`（`GetTypeInfoCount`=1 + `GetTypeInfo` 用 `CreateDispTypeInfo` 从同一张方法表造） | **0 行**（15 处访问器、47 个用例原样可用） | 唯一的 unsafe COM/VARIANT 面；README §七 自己点的"可能翻车点" |
| **B. 全异步 invoke** | 15 处访问器统一改成 `invoke("call", …)`；`engineCall` 变 async | **大**：采样链、绘图网格、AI relay 全部异步化；47 个用例的取页与断言一起改 | 采样时序被 await 拆碎（`asyncPolicy.js` 明说不要）；回归网要重建 |
| **C. 混合：`mf` 独占同步通道，其余走 invoke** | 只给 `mf` 恢复宿主对象（一个对象、一张方法表）；`win`/`sys`/`diag`/`push`/`con`/`ai`/`search`/`account`/`update` 用 Tauri 原生命令 + 事件 | **中等**：只有 `win`/`sys`/`diag`/`push` 这几处（低频、本来就是"发出去不管结果"或可异步）要改；**引擎热循环一行不动** | unsafe 面收敛到 1 个对象；但前端会出现两种通道，需要一条明确规则 |

### 5.2 我的倾向：**C**，理由三条

1. **把"唯一可能翻车的点"限制在一个对象上**。`mf` 是唯一真正需要同步的（§2.1 有证据），
   `win`（发完不管）、`sys`（读写文件，可以 await）、`push`（本来就是事件）都不需要同步。
2. **Tauri 的原生机制天然适合剩下 9 个**：命令 + 事件比手写 `IDispatch` 简单得多，而且
   `push` 在 Tauri 里有现成的 `emit/listen`。
3. **保住了 47 个用例里最有价值的那部分**：引擎侧的断言（`cdp-bridge-verify`、`cdp-engine-*`、
   全部绘图用例）不用改；只有窗口/设置/文件对话框那几条要跟着改。

> 但这是**你的决定**，不是我替你定：A 的吸引力在于"前端零改动、47 个用例全保"，
> 代价是那套 COM 代码要重写一遍（且当年就卡过）。

### 5.3 分阶段（每阶段都有可验证的产物）

| 阶段 | 做什么 | 验收（可复现） |
| --- | --- | --- |
| **P0 闭环** | 让 `cargo build` 能跑（§4.2 三选一）；起宿主；用 `curl 127.0.0.1:9222/json/list` **实测页面 URL**；确认 `--selftest-jobs` 五项 PASS | 页面 URL 落地成事实；`--selftest-jobs` 全绿 |
| **P1 定形状** | 按选定路线，**只做 `mf`** 的 `Ready` / `Version` / `FunctionExists` / `Dispatch` 四个方法 | 一段 CDP 探针：`list_functions.count === 424`、`FunctionExists('solve_sym')===true`、`FunctionExists('no_such_fn')===false` |
| **P2 补对象** | 按 §1.3 的表逐个搬：`diag`（最便宜）→ `sys` → `win` 的对话框 → `push` → `con` → `search`/`account`/`update` → `ai`（最重） | 每搬完一个，把它对应的 `cdp-*.mjs` 跑绿；全绿后再动下一个 |
| **P3 验收对齐** | 让用例不绑定实现：取页正则接受两种宿主；把用例里的 `hostObjects.sync.*` 直连改为走前端桥模块 | `tests/run-all.ps1` 对着 Rust 宿主跑完，失败清单为空或每条都有写明原因 |

### 5.4 明确不做

- **不改引擎**：两个 C ABI 不动（README §一 的边界）。
- **不改前端业务逻辑**：只动 `src/lib/*/bridge.js` 这一层与 `push.js`/`errors.js` 的通道部分。
- **不拆 C# 宿主**：迁移期两边并存，同一批用例对两边跑，谁红修谁（README §六）。

---

## 6. 顺手记的小账（都是【实测】）

1. **`win.Restore` 是死成员**：C# `WindowBridge.cs` 与 `handlers.rs` 都实现了，前端**从不调用**
   （grep `Restore` 在 `MF_UI/src` 只命中 i18n 词条）。两边各留一份，要么补调用点，要么删。
2. **窗口"是否最大化"在 Tauri 下是**返回值滞后一帧**的**（`lib/bridge.js:510-522` 返回上次已知值）。
   顶栏图标靠 `App.vue` 的 `syncMaximized` 补，属于**已知的语义降级**，不是 bug —— 但要写进文档，
   否则以后会被当成回归。
3. **`diag.Front` 有两条路**：`handlers.rs` 的 `diag` 分支 与 `commands.rs` 的独立命令 `front_log`。
   独立命令更稳（异常上报要在"桥本身可能坏了"时仍可用，`commands.rs:58-59` 的注释就是这么写的）。
   两条都留着会分裂，建议**只留命令**。
4. **本目录 `README.md` 已经过时**：它还停在"wry + spike + S2 卡在 ITypeInfo"，
   与 `Cargo.toml`/`main.rs` 里的 Tauri 现状矛盾。读代码的人会先被它误导 —— 需要按本文刷新。
5. **`src/handlers.rs:280` 有个 `static _UNUSED: OnceLock<()>` 占位**；`src/engine.rs:126` 的
   `cstr_lossy` 全仓库无调用。都是遗留物。
6. **`--selftest-jobs` 是目前唯一还能跑的验收**（不依赖 WebView2），P0 阶段应当先用它把宿主自身钉住。
7. **`wry = "0.57.0"` 是死依赖**：`Cargo.toml` 直接依赖它，但 `src/` 里一处都没引用（Tauri 自己会经
   `tauri-runtime-wry` 带进来）。可以直接删。

---

## 7. 待补清单（按依赖排序）

> 规模用 **C# 对应文件行数**当底数（【实测】`Get-Content | Measure-Object -Line`），不用"人日"猜。
> **已迁**：`mf` 67 + `win` 237 + `sys` 365 + `diag` 31 ≈ **700 行**；
> **待迁**：**约 4190 行**（下表合计）—— 也就是还有 **6 倍于已完成的量**。

### 7.0 先决条件（不补这三条，后面所有工作都无法验证）

| # | 缺口 | 为什么卡 | 怎么补 |
| --- | --- | --- | --- |
| 0-1 | **构建闭环** | cargo 写 `<repo>\.cargo-home` 被沙箱拒（§4.2 实测 `os error 5`），而 crates 代理不在跑时 cargo 必失败 | §4.2 三选一：放宽一次权限 / 工作区内自建 `CARGO_HOME` / 你在自己终端构建 |
| 0-2 | **接缝形状未定** | A/B/C 决定前端 15 处访问器怎么写、47 个用例要不要改（§5.1） | 你拍板 |
| 0-3 | **一条有效验收** | 47 个用例因 URL 正则找不到页面（§3.4）；自带的两个探针是 wry 时代产物 | 起宿主 → `curl 127.0.0.1:9222/json/list` 实测 URL → 改正则 → 重写 `tools/verify-spike.mjs` 为 Tauri 版 |

### 7.1 Rust 侧：缺的 6 个宿主对象

| 优先 | 对象 | C# 底数 | Rust 要新增的东西 | 依赖 |
| --- | --- | --- | --- | --- |
| ① | `diag` | 31 | **零新增**：`handlers.rs` 的 `diag` 分支与命令 `front_log` 都在，只差前端接线（§6.3 建议只留命令） | — |
| ② | `sys` | 365 | **零新增**：`sys.rs` 已全实现，只差前端接线 | — |
| ③ | `win` 对话框 | 237 | **零新增**：`winbridge.rs` 已含 `SaveTextFile`/`OpenTextFile`/`SaveBinaryFile`，只差前端 `callWinJson` 接 Tauri | — |
| ④ | `push` | 60 + 133 | ~~推送中继~~ **✅ 已完成**：`with_webview()` 拿 `ICoreWebView2` → worker + `run_on_main_thread` → `PostWebMessageAsJson`。`push.js` 与信封**原样未动** | — |
| ⑤ | `con` | 824 + 185 | 子进程 + stdin/stdout 管道 + 组件下载（Range 续传 / SHA-256 / zip 解包） | 新增 `sha2`、`zip` 依赖 |
| ⑥ | `update` | 304 | 版本关系判定 + sha256 + 把下载交给浏览器 | 新增 HTTP（`reqwest` rustls） |
| ⑦ | `search` | 411 + 323 + 147 + 118 | 三后端抓取 + 四解析器 + 缓存（键含引擎） | 同上 |
| ⑧ | `account` | 484 + 228 + 106 | 站点契约 + token DPAPI + 401 自动登出 | HTTP + **DPAPI** |
| ⑨ | `ai` | 345 + 236 + 149 + 134 | `reqwest`(rustls) + SSE 中继（`Begin`/`Cancel` + `ai.raw*` 事件） | HTTP + DPAPI + ④ 的推送通道 |

> ① `diag`、② `sys`、③ `win` 对话框、④ `push` 已在 2026-10-07 落地（见 §0.1）。剩下的从 ⑤ 开始。

### 7.2 Rust 侧：共用件与 `Cargo.toml`

| # | 缺什么 | 说明 |
| --- | --- | --- |
| 2-1 | **DPAPI 模块**（`Dpapi.cs` 110 行） | `account` / `ai` / `search` 三个桥的凭据都靠它。`windows` crate 的 `Win32_Security_Cryptography` **feature 已经开了**，抽一个 `dpapi.rs` 即可 |
| 2-2 | **HTTP 模块**（`Http.cs` 77 行） | 按 README §三 的决定用 `reqwest` + **rustls**（不用 Schannel）—— 顺带修掉 `docs/OPEN-ITEMS.md` §1 记的那条"本机 .NET 侧到生产站点 TLS 建立失败" |
| 2-3 | ~~`webview2-com` 依赖~~ **✅ 已加** | `PlatformWebview::controller()` 返回的是 **`webview2-com-sys` 0.39.1** 的接口，不是 `windows` crate 的。必须加**同版本**的 `webview2-com`（版本不匹配 → 类型对不上，编译不过）。已在 `Cargo.toml` |
| 2-4 | `sha2` / `zip` | `con` 的组件校验与解包、`update` 的 sha256 |
| 2-5 | ~~删 `wry`~~ **✅ 已删** | 死依赖，`src/` 一处未引用 |
| 2-6 | **引擎 DLL 随宿主走** | ✅ 新增 `tools/sync-engine.mjs`：把 6 个 DLL 拷到 exe 同目录（C# 宿主靠 csproj 做的事）。**缺了它界面照开、但一次都算不了** |

> **④ 号位的关键结论【已核实】**：`tauri 2.12.1` 在 Windows 上提供
> `PlatformWebview::controller() -> ICoreWebView2Controller`
>（[docs.rs（Windows 目标）](https://docs.rs/tauri/2.12.1/x86_64-pc-windows-msvc/tauri/webview/struct.PlatformWebview.html)），
> 经它拿到 `ICoreWebView2` 后，**`AddHostObjectToScript`（同步接缝）与 `PostWebMessageAsJson`（推送通道）
> 两个接口都在手里**。这同时说明两件事：路线 A/C 技术上可行；**推送通道不必重写**，`push.js` 与它
> 那套 `{topic,seq,ts,payload}` 信封可以原样保留。

### 7.3 前端侧：接线

| # | 缺口 | 位置 |
| --- | --- | --- |
| 3-1 | **15 处访问器各自为政**，没有统一通道 | `lib/bridge.js:92/446`、`settings/bridge.js:14`、`settings/io.js:35/38`、`push.js:39`、`errors.js:26`、`console/bridge.js:14`、`search/bridge.js:21`、`account/bridge.js:18`、`update/bridge.js:16/19`、`ai/bridge.js:34/180/192`、`ai/relay.ts:76`。建议先建**一个** `lib/host.js` 收口：`hostCall(object, method, args) → {sync|async}`，之后每加一个桥只加一个分支 |
| 3-2 | `engineCall` / `engineCallAsync` 的 Tauri 分支 | 取决于 0-2 的路线 |
| 3-3 | 文件对话框只认 `winBridge()` | `lib/bridge.js:539-549` `callWinJson`（3 个调用点：`plot/exportImage.js:104`、`settings/io.js:185/196`、`workspace/store.js:148/169`） |
| 3-4 | 前端异常上报只走 `diag` 对象 | `lib/diagnostics/errors.js:54-72`；Rust 侧已有 `front_log` 命令，建议直接改走它 |
| 3-5 | 推送订阅只走 `chrome.webview` 的 `message` | `lib/push.js:113-137`（若 7.2-④ 走 `PostWebMessageAsJson`，**这里不用改**） |
| 3-6 | React 侧的宿主兜底 | `MFMath.UI.React/src/lib/hostSafe.ts:23-34`（`diag.Front` 直连，同 3-4） |

### 7.4 验收侧

| # | 缺口 | 怎么补 |
| --- | --- | --- |
| 4-1 | 47 个用例的**取页正则**写死 `mfmath.local` | 抽成一个共用常量，同时接受两种宿主的 URL；`tests/run-all.ps1` 加"对哪个宿主跑"的参数 |
| 4-2 | 用例里 **`hostObjects.sync.*` 直连**（`cdp-bridge-verify.mjs:43-58` 等） | 改为经前端桥模块调用，用例就不再绑定接缝形状 |
| 4-3 | Rust 宿主**自己的**探针过期 | 重写 `tools/verify-spike.mjs`；`tools/probe-hostobject.mjs` 已无用，删 |
| 4-4 | 没有一条"引擎真的算了"的 Tauri 侧断言 | P1 的产物就是它（§5.3） |

### 7.5 清理项（低风险，顺手做）

`Cargo.toml` 删死依赖 `wry`；`handlers.rs:280` 删 `_UNUSED`；`engine.rs:126` 删 `cstr_lossy`；
`diag` 两条路择一（§6.3）；`win.Restore` 补调用点或删（§6.1）；按本文刷新本目录 `README.md`（§6.4）。

---

## 附录 A：C# 桥面（权威方法表）→ Rust 现状

方法名来自 `MFMath.Host/*Bridge.cs` 的公开方法【实测】。

| 对象 | C# 公开方法 | Rust |
| --- | --- | --- |
| `mf` | Dispatch, Ready, Version, FunctionExists, SolveSymbolic, DiscriminantSymbolic, FactorSymbolic, CompareExpr, SimplifySymbolic, ExtremaSymbolic, FreeSymbols, Differentiate | ✅ ＋ DispatchJob, PollJob, CancelJob, JobStats（C# 没有，前端会自动退回同步，见 `lib/bridge.js:164-166`） |
| `win` | Minimize, ToggleMaximize, Restore, IsMaximized, Close, StartDrag, SetChromeBackground, SaveTextFile, OpenTextFile, SaveBinaryFile | ✅ 全 10 个 |
| `sys` | Info, EngineReport, StoreList, StoreRead, StoreWrite, StoreDelete, OpenPath, ExportDiagnostics | ✅ 全 8 个 |
| `diag` | Front | ✅ |
| `push` | Info, Emit, Ready | ❌ |
| `con` | Components, SetDownloadBase, Install, Uninstall, CancelInstall, InstallStatus, Start, Poll, Stop, StopAll | ❌ |
| `ai` | Info, Busy, KeySource, Configure, SetKey, ClearKey, Test, Begin, Cancel, CancelAll, SelfCheck | ❌ |
| `search` | Info, Busy, Configure, SetWolframKey, ClearWolframKey, Start, Cancel, CancelAll, OpenUrl, CacheStats, ClearCache, SelfCheck | ❌ |
| `account` | Info, Configure, ClearLocal, Login, LoginEx, Logout, RefreshProfile, RefreshToken, EnsureFresh, Register, SendCode, VerifyCode, ResendCode, ChangePassword, LoginHistory, SiteVersion, Busy, CancelAll, SelfCheck | ❌ |
| `update` | Info, Check, OpenDownloadPage, PreviewDownloadUrl, CancelAll, SelfCheck | ❌ |

> 注：`ai.Begin` + `ai.Cancel` 是**流式中继**的入口，下游经 `ai.http` / `ai.raw*` 推送回页面
> （`ai/relay.ts:158`、`AiRelay.cs:180/214/240/246`）。它是所有桥里唯一"命令 + 事件 + 网络"三合一的，
> 排在最后（README §三 的判断"最重的是 `con`"，现在的账应该改成 `con` 与 `ai` 并列最重）。

## 附录 B：本机复现命令

```powershell
$H = "<repo>\MFMath.Host.Rust"

# 0) 起包代理（不起的话 cargo 一定失败）
node "$H\tools\crates-proxy.mjs"        # 127.0.0.1:8432

# 1) 构建（本会话沙箱内需要先解决 §4.2 的 CARGO_HOME 问题）
$env:CARGO_HOME = "<repo>\.cargo-home"
cargo build                             # 在 $H 下
#     ⚠ 前端改过就必须重跑这一步（资源是编进 exe 的，§3.5）

# 2) 无头自检：只验后台任务通道，不需要 WebView2
& "$H\target\debug\mfmath-host-rust.exe" --selftest-jobs

# 3) 起宿主后，先确认页面 URL（§3.4 的待核实项）
curl.exe -s http://127.0.0.1:9222/json/list

# 4) C# 宿主的对照跑法（迁移期两边并存）
dotnet build "<repo>\MFMath.Host\MFMath.Host.csproj" -c Release --no-incremental
```
