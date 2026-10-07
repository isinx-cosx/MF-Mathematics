# 宿主对象与方法表（9 × 84）

> **本文只回答一个问题：宿主到底暴露了哪些对象、哪些方法、什么参数。**
>
> 契约与接缝见 [README.md](README.md)；异步与推送见 [JOBS-PUSH.md](JOBS-PUSH.md)。

**核对时间**：2026-10-07
**权威源**：`MFMath.Host.Rust/src/main.rs:67-216`（`*_SPEC` 方法表 + `HOST_OBJECTS` 注册表）
**交叉验证**：宿主启动日志会逐个打印对象与方法数；[`ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md) §2 的基线表与本文一致

---

## 0. 一句话

**9 个对象 / 84 个方法**，全部注册在同一个通用 `IDispatch` 上：

| 对象 | 方法数 | 一句话 | 前端模块 |
| --- | --- | --- | --- |
| [`mf`](#1-mf--引擎桥16) | **16** | 引擎桥（同步 + 异步 job 通道 + 8 个具名符号封装） | `lib/bridge.js` |
| [`sys`](#2-sys--设置与存储8) | **8** | 设置 / 存储 / 诊断包 | `lib/settings/bridge.js`、`settings/io.js` |
| [`diag`](#3-diag--前端异常入日志1) | **1** | 前端异常写进宿主日志 | `lib/diagnostics/errors.js` |
| [`win`](#4-win--窗口与文件对话框9) | **9** | 窗口操作 + 文件对话框 | `lib/bridge.js`、`lib/settings/io.js` |
| [`push`](#5-push--下行推送3) | **3** | 宿主 → 页面推送（**旁路**） | `lib/push.js` |
| [`update`](#6-update--更新链6) | **6** | 更新检查（只提示，下载交给浏览器） | `lib/update/bridge.js` |
| [`account`](#7-account--用户系统19) | **19** | 登录 / 注册 / 续期 / 历史 | `lib/account/bridge.js` |
| [`search`](#8-search--联网搜索12) | **12** | 联网搜索（慢活，结果走推送） | `lib/search/bridge.js` |
| [`con`](#9-con--控制台与组件10) | **10** | 控制台 + 可选组件安装 | `lib/console/bridge.js` |
| | **84** | | |

> ⚠ **`ai` 不在这张表里，这是刻意的。** AI 已整体搬到 TS 页面直连，宿主不再有 `ai` 对象 ——
> 见 [CREDENTIALS.md](CREDENTIALS.md) 与 [DECISIONS.md](../DECISIONS.md) D-004。
> 因此"宿主对象 10 个"这种说法**已经全面过时**，见到就改。

---

## 1. `mf` —— 引擎桥（16）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Dispatch` | `name`, `argsJson` | JSON 文本 | **主入口**：调引擎的任意 action（424 个） |
| `Ready` | — | 布尔 | 引擎可用？ |
| `Version` | — | JSON 文本 | 引擎版本 |
| `FunctionExists` | `name` | 布尔 | 该 action 是否注册（**守门用**：`count == 424` 的探针走它） |
| `DispatchJob` | `name`, `argsJson` | JSON 文本 | 派发**后台任务**，立刻回 `{ok, jobId}` —— 见 [JOBS-PUSH.md](JOBS-PUSH.md) |
| `PollJob` | `jobId` | JSON 文本 | 查任务状态 |
| `CancelJob` | `jobId` | JSON 文本 | **只停止等待并丢弃结果**（引擎没有取消钩子） |
| `JobStats` | — | JSON 文本 | 任务通道自检/诊断（**C# 侧没有这个**，Rust 新增） |
| `SolveSymbolic` | `expr`, `var` | JSON 文本 | ┐ |
| `DiscriminantSymbolic` | `expr`, `var` | JSON 文本 | │ |
| `FactorSymbolic` | `expr`, `var` | JSON 文本 | │ |
| `CompareExpr` | `a`, `b` | JSON 文本 | │ **8 个具名符号封装** |
| `SimplifySymbolic` | `expr` | JSON 文本 | │ 前端**不走**它们； |
| `ExtremaSymbolic` | `expr`, `var` | JSON 文本 | │ 端到端用例与 C# 公开 API 在用 |
| `FreeSymbols` | `expr` | JSON 文本 | │ |
| `Differentiate` | `expr`, `var` | JSON 文本 | ┘ |

**只用 4 个**：前端实际使用的只有 `Dispatch` / `Ready` / `Version` / `FunctionExists`
（外加异步通道那三个）。其余 8 个是**为兼容 C# 公开 API 与用例**保留的。

---

## 2. `sys` —— 设置与存储（8）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | JSON 文本 | 版本 / 目录 / 能力 |
| `EngineReport` | — | JSON 文本 | 引擎诊断（路径、加载状态） |
| `StoreList` | — | JSON 文本 | 存储里有哪几份 |
| `StoreRead` | `name` | JSON 文本 | 读一份（**`ai.json` 也走它**） |
| `StoreWrite` | `name`, `json` | JSON 文本 | 写一份 |
| `StoreDelete` | `name` | JSON 文本 | 删一份 |
| `OpenPath` | `path` | JSON 文本 | 在资源管理器里打开（**不是任意 shell 执行**） |
| `ExportDiagnostics` | — | JSON 文本 | 导出诊断包（用户主动；**不会自动上传**） |

> `ai` 不再是宿主对象之后，**AI 的配置与密钥仍由 `StoreRead` / `StoreWrite` 读写** ——
> 也就是说"密钥不进宿主"这件事**只对了一半**：宿主不解析它，但**能读到那份文件**。
> 准确的边界见 [CREDENTIALS.md](CREDENTIALS.md)。

---

## 3. `diag` —— 前端异常入日志（1）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Front` | `level`, `message` | 无 | 前端未捕获异常写进宿主日志（对照 C# `LogBridge`） |

> 曾有一条 Tauri 命令 `front_log` 的并行路径，**已删** —— 现在只有这一个入口。

---

## 4. `win` —— 窗口与文件对话框（9）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Minimize` | — | 无 | |
| `ToggleMaximize` | — | 无 | |
| `IsMaximized` | — | 布尔 | |
| `Close` | — | 无 | |
| `StartDrag` | — | 无 | 自绘标题栏用 |
| `SetChromeBackground` | `color` | 无 | |
| `SaveTextFile` | `title`, `defaultName`, `filter`, `content`, `path` | JSON 文本 | `path` 非空则**跳过原生对话框** —— 端到端用例靠这个跑完整链路又不弹窗 |
| `OpenTextFile` | `title`, `filter`, `path` | JSON 文本 | 同上 |
| `SaveBinaryFile` | `title`, `defaultName`, `filter`, `base64`, `path` | JSON 文本 | 导出图片走它 |

> ⚠ **`main.rs:102` 的注释说"10 个方法一个不少"，实际是 9 个 —— 注释过时了。**
> 少掉的是 `Restore`：C# 侧有，但**两侧前端都没有任何调用点**，所以删掉
> （[`ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md) §2 的记录与代码一致：`win` = **9**）。
> `IsMaximized` 是这 9 个里唯一的 `RetKind::Bool`。

---

## 5. `push` —— 下行推送（3）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | JSON 文本 | 宿主侧推送计数（已发 / 失败 / 最后一条主题）—— 页面不用再猜"是宿主没发还是我没收到" |
| `Emit` | `topic`, `payloadJson` | JSON 文本 | 页面**主动**发一条（用于往返自检） |
| `Ready` | — | 布尔 | |

信封、主题清单与四个实现坑见 [JOBS-PUSH.md](JOBS-PUSH.md)。

---

## 6. `update` —— 更新链（6）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | JSON 文本 | |
| `Check` | — | JSON 文本 | 检查新版本 |
| `OpenDownloadPage` | `url` | JSON 文本 | 把下载页交给**默认浏览器** |
| `PreviewDownloadUrl` | `url` | JSON 文本 | 预览将打开的地址（用户可见） |
| `CancelAll` | — | 无 | |
| `SelfCheck` | — | JSON 文本 | |

> **没有**任何自动下载 / 执行安装包的入口 —— 这是 [DECISIONS.md](../DECISIONS.md) 里
> "更新只提示"那条决定的落点，也是安全属性。

---

## 7. `account` —— 用户系统（19）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | JSON 文本 | **脱敏**：只有 `hasToken` 这类字段，**不含 token 本身** |
| `Configure` | `json` | JSON 文本 | 站点地址等配置 |
| `ClearLocal` | — | JSON 文本 | 清本地登录态 |
| `Login` | `username`, `password` | JSON 文本 | |
| `LoginEx` | `json` | JSON 文本 | 前端实际用的是它 |
| `Logout` | — | JSON 文本 | |
| `RefreshProfile` | — | JSON 文本 | |
| `RefreshToken` | — | JSON 文本 | 静默续期 |
| `EnsureFresh` | `thresholdSec` | **布尔** | 剩余有效期低于阈值就续期 |
| `Register` | `json` | JSON 文本 | |
| `SendCode` | `email` | JSON 文本 | |
| `VerifyCode` | `username`, `code` | JSON 文本 | |
| `ResendCode` | `username`, `email` | JSON 文本 | |
| `ChangePassword` | `oldPassword`, `newPassword` | JSON 文本 | |
| `LoginHistory` | — | JSON 文本 | |
| `SiteVersion` | — | JSON 文本 | 站点版本（含 sha256/size 后可用于更新链） |
| `Busy` | — | **布尔** | |
| `CancelAll` | — | 无 | |
| `SelfCheck` | — | JSON 文本 | 含一条**"信息不泄漏"**的断言，见 [CREDENTIALS.md](CREDENTIALS.md) §3 |

---

## 8. `search` —— 联网搜索（12）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | JSON 文本 | 只暴露 `hasWolframKey` 这类布尔，**不含密钥** |
| `Configure` | `json` | JSON 文本 | 端点覆盖等 |
| `SetWolframKey` | `key` | JSON 文本 | 写进宿主（**DPAPI 密文**） |
| `ClearWolframKey` | — | JSON 文本 | |
| `Start` | `json` | JSON 文本 | 发起搜索 —— **慢活，结果不走返回值而走推送** |
| `Cancel` | `requestId` | JSON 文本 | |
| `CancelAll` | — | JSON 文本 | |
| `Busy` | — | **布尔** | |
| `OpenUrl` | `url` | JSON 文本 | 交给默认浏览器 |
| `CacheStats` | — | JSON 文本 | 缓存命中 / 条目数 |
| `ClearCache` | — | JSON 文本 | |
| `SelfCheck` | — | JSON 文本 | |

> `search` 为什么必须走推送：它是**秒级**的活，同步返回会把渲染进程冻住几秒
> （`main.rs:157-159` 原话）。搜索结果主题见 [JOBS-PUSH.md](JOBS-PUSH.md) §3。

---

## 9. `con` —— 控制台与组件（10）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Components` | — | JSON 文本 | 可选组件清单（含 `available` 与体积） |
| `SetDownloadBase` | `url` | JSON 文本 | 下载基址覆盖 |
| `Install` | `name` | **裸 id 字符串**（`"job3"`） | ⚠ 不是 JSON |
| `Uninstall` | `name` | JSON 文本 | |
| `CancelInstall` | `jobId` | JSON 文本 | |
| `InstallStatus` | `jobId` | JSON 文本 | |
| `Start` | `language`, `code`, `stdin` | **裸 id 字符串**（`"run4"`） | ⚠ 不是 JSON |
| `Poll` | `runId` | JSON 文本 | |
| `Stop` | `runId` | JSON 文本 | |
| `StopAll` | — | JSON 文本 | |

### 9.1 ⚠ 命名陷阱：模块叫 `console.rs`，对象名必须是 `con`

前端写的是 `hostObjects.sync.con`，那是**契约**。而 Rust 模块文件只能叫 `console.rs` ——
因为 Windows 把 `con` 当**保留设备名**，`src/con.rs` 这种文件 **git 索引不了**：
`git add` 会报 `open("src/con.rs"): No such file or directory`，**而文件明明在磁盘上**。
留着它就等于这个桥**永远进不了版本库**。

---

## 10. 跨对象的四条约定

1. **参数一律 `VT_BSTR`**：前端宿主对象调用本来就只传字符串（`main.rs:60`）。
   数字要自己转成字符串传，布尔用真布尔返回（`RetKind::Bool`）。
2. **返回 `RetKind` 只有三种**：`Str`（JSON 文本）、`Bool`（真布尔）、`Empty`（无返回）。
   其它类型**刻意不预留**（`handlers.rs` 的原话："其余类型等用到再加，**不预留**"）。
3. **两份表必须同步**：`main.rs` 的 `MethodSpec` 表里有、`handlers.rs` 里没有的方法，
   调用时拿到"没有这个方法"的**错误信封** —— 报错，不是静默。
4. **错误一律 `{"isError":true,"value":"…"}`**，与前端 `parse()` 那一层解耦。
