# 宿主对象参考

> 本文列出宿主对外暴露的对象、方法、参数与返回类型。权威源是 [`main.rs`](../../MFMath.Host.Rust/src/main.rs) 的 `*_SPEC` 常量表与 `HOST_OBJECTS` 注册表、[`handlers.rs`](../../MFMath.Host.Rust/src/handlers.rs) 的 `call()` 分发。
> 接缝机制见 [README.md](README.md)，异步与下行通道见 [JOBS-PUSH.md](JOBS-PUSH.md)，凭据边界见 [CREDENTIALS.md](CREDENTIALS.md)。

## 1. 概览

宿主注册 9 个对象、84 个方法，全部经同一份 COM 实现（`hostobject.rs`）挂到 `ICoreWebView2::AddHostObjectToScript`。前端按 `window.chrome.webview.hostObjects.sync.<对象>.<方法>(…)` 同步调用。

| 对象 | 方法数 | 用途 |
| --- | --- | --- |
| `mf` | 16 | 引擎调用、后台任务、具名符号封装 |
| `sys` | 8 | 设置存储、引擎报告、诊断导出 |
| `diag` | 1 | 前端异常写入宿主日志 |
| `win` | 9 | 窗口操作与文件对话框 |
| `push` | 3 | 下行通道的诊断与自测 |
| `update` | 6 | 更新提示 |
| `account` | 19 | 用户系统 |
| `search` | 12 | 联网搜索 |
| `con` | 10 | 控制台与可选组件 |

方法表（`*_SPEC`）与 `handlers.rs` 的 `match` 分支一一对应；表里有而 `handlers.rs` 没有的方法，调用时得到"没有这个方法"的错误信封。

```powershell
# 每个对象的方法数，与总数 84
$src = Get-Content MFMath.Host.Rust/src/main.rs -Raw
$parts = [regex]::Split($src, 'const (\w+_SPEC)')
for ($i = 1; $i -lt $parts.Count; $i += 2) {
  "{0} = {1}" -f $parts[$i], ([regex]::Matches($parts[$i + 1], 'MethodSpec \{')).Count
}
(Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'MethodSpec \{').Count
```

## 2. `mf` —— 引擎桥（16）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Dispatch` | `name`, `argsJson` | Str | 调用引擎任意 action，透传参数 JSON |
| `Ready` | — | Bool | 引擎可用，当前恒为 `true` |
| `Version` | — | Str | 宿主版本标识字符串 |
| `FunctionExists` | `name` | Bool | 引擎是否注册该 action |
| `DispatchJob` | `name`, `argsJson` | Str | 入队后台任务，立即返回 jobId |
| `PollJob` | `jobId` | Str | 查询任务状态 |
| `CancelJob` | `jobId` | Str | 停止等待并丢弃结果 |
| `JobStats` | — | Str | 任务通道诊断 |
| `SolveSymbolic` | `expr`, `var` | Str | 具名封装，映射 `solve_sym` |
| `DiscriminantSymbolic` | `expr`, `var` | Str | 映射 `discriminant_sym` |
| `FactorSymbolic` | `expr`, `var` | Str | 映射 `factor_sym` |
| `CompareExpr` | `a`, `b` | Str | 映射 `compare_expr` |
| `SimplifySymbolic` | `expr` | Str | 映射 `simplify_sym` |
| `ExtremaSymbolic` | `expr`, `var` | Str | 映射 `extrema_sym` |
| `FreeSymbols` | `expr` | Str | 映射 `free_symbols_of` |
| `Differentiate` | `expr`, `var` | Str | 映射 `diff` |

`Dispatch` 是通用透传入口：引擎新增 action 不改宿主。异步通道由 `DispatchJob` / `PollJob` / `CancelJob` / `JobStats` 构成，派发语义见 [JOBS-PUSH.md](JOBS-PUSH.md)。

后 8 个是 C# `MathBridge` 公开 API 的具名封装，均为薄包装：把位置参数拼成 JSON 后走与 `Dispatch` 相同的通路，缺省 `var` 补 `"x"`。封装名到引擎 action 的映射在 `handlers.rs` 的 `SYMBOLIC_ALIASES` 常量里（`Select-String -Path MFMath.Host.Rust/src/handlers.rs -Pattern "SYMBOLIC_ALIASES"`）。

## 3. `sys` —— 设置与存储（8）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | Str | 版本、目录、能力 |
| `EngineReport` | — | Str | 引擎路径与加载状态 |
| `StoreList` | — | Str | 存储中已有几份 |
| `StoreRead` | `name` | Str | 读一份存储 |
| `StoreWrite` | `name`, `json` | Str | 写一份存储 |
| `StoreDelete` | `name` | Str | 删一份存储 |
| `OpenPath` | `path` | Str | 在资源管理器中打开路径 |
| `ExportDiagnostics` | — | Str | 导出诊断包 |

存储读写是 `ai.json` 等配置文件的通道；宿主不解析该文件的内容，边界见 [CREDENTIALS.md](CREDENTIALS.md)。

## 4. `diag` —— 前端异常入日志（1）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Front` | `level`, `message` | Empty | 前端异常写入宿主同一份日志 |

前端异常的唯一入口是 `diag.Front`，落点在 `logging::front`（`Select-String -Path MFMath.Host.Rust/src/handlers.rs -Pattern '"Front"'`）。

## 5. `win` —— 窗口与文件对话框（9）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Minimize` | — | Empty | 最小化 |
| `ToggleMaximize` | — | Empty | 切换最大化 |
| `IsMaximized` | — | Bool | 是否最大化 |
| `Close` | — | Empty | 关闭窗口 |
| `StartDrag` | — | Empty | 自绘标题栏拖拽 |
| `SetChromeBackground` | `color` | Empty | 设置标题栏背景色 |
| `SaveTextFile` | `title`, `defaultName`, `filter`, `content`, `path` | Str | 保存文本到用户选定文件 |
| `OpenTextFile` | `title`, `filter`, `path` | Str | 从用户选定文件读文本 |
| `SaveBinaryFile` | `title`, `defaultName`, `filter`, `base64`, `path` | Str | 保存二进制（图片导出） |

文件对话框三个方法的 `path` 参数是自动化钩子：非空时跳过系统对话框直接读写该路径，为空时弹 Win32 通用对话框（`winbridge.rs` 的 `pick_target`，`Select-String -Path MFMath.Host.Rust/src/winbridge.rs -Pattern "fn pick_target"`）。

## 6. `push` —— 下行推送（3）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | Str | 宿主侧推送计数（已发、失败、最后主题） |
| `Emit` | `topic`, `payloadJson` | Str | 页面主动发一条，用于往返自检 |
| `Ready` | — | Bool | 通道是否就绪 |

信封与主题清单见 [JOBS-PUSH.md](JOBS-PUSH.md)。真实推送由各业务桥发出，此对象只承担诊断与自测。

## 7. `update` —— 更新链（6）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | Str | 更新状态 |
| `Check` | — | Str | 检查新版本 |
| `OpenDownloadPage` | `url` | Str | 把下载页交给默认浏览器 |
| `PreviewDownloadUrl` | `url` | Str | 预览将打开的地址 |
| `CancelAll` | — | Empty | 取消全部在途请求 |
| `SelfCheck` | — | Str | 自检 |

宿主不提供自动下载或执行安装包的入口。

## 8. `account` —— 用户系统（19）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | Str | 脱敏登录态，含 `hasToken` 一类字段 |
| `Configure` | `json` | Str | 站点地址等配置 |
| `ClearLocal` | — | Str | 清本地登录态 |
| `Login` | `username`, `password` | Str | 登录 |
| `LoginEx` | `json` | Str | 登录（JSON 参数） |
| `Logout` | — | Str | 登出 |
| `RefreshProfile` | — | Str | 刷新资料 |
| `RefreshToken` | — | Str | 静默续期 |
| `EnsureFresh` | `thresholdSec` | Bool | 剩余有效期低于阈值则续期，默认 300 秒 |
| `Register` | `json` | Str | 注册 |
| `SendCode` | `email` | Str | 发送验证码 |
| `VerifyCode` | `username`, `code` | Str | 校验验证码 |
| `ResendCode` | `username`, `email` | Str | 重发验证码 |
| `ChangePassword` | `oldPassword`, `newPassword` | Str | 改密 |
| `LoginHistory` | — | Str | 登录历史 |
| `SiteVersion` | — | Str | 站点版本（含 sha256/size） |
| `Busy` | — | Bool | 是否有在途请求 |
| `CancelAll` | — | Empty | 取消全部在途请求 |
| `SelfCheck` | — | Str | 自检，含"信息不泄漏"断言 |

token 只保存在宿主，页面只见脱敏字段。`EnsureFresh` 的 `thresholdSec` 经 `variant_to_arg` 以数字读入，缺省补 300（`Select-String -Path MFMath.Host.Rust/src/handlers.rs -Pattern 'unwrap_or\(300\)'`）。

## 9. `search` —— 联网搜索（12）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Info` | — | Str | 只暴露 `hasWolframKey` 一类布尔 |
| `Configure` | `json` | Str | 端点覆盖等 |
| `SetWolframKey` | `key` | Str | 写入宿主，DPAPI 密文 |
| `ClearWolframKey` | — | Str | 清除密钥 |
| `Start` | `json` | Str | 发起搜索，结果走推送 |
| `Cancel` | `requestId` | Str | 取消单次请求 |
| `CancelAll` | — | Str | 取消全部 |
| `Busy` | — | Bool | 是否有在途请求 |
| `OpenUrl` | `url` | Str | 交给默认浏览器 |
| `CacheStats` | — | Str | 缓存命中与条目数 |
| `ClearCache` | — | Str | 清缓存 |
| `SelfCheck` | — | Str | 自检 |

`Start` 立即返回，结果经下行通道推回；同步等待网络会阻塞渲染进程数秒。App ID 只保存在宿主，页面只见 `hasWolframKey`，边界见 [CREDENTIALS.md](CREDENTIALS.md)。

## 10. `con` —— 控制台与组件（10）

| 方法 | 参数 | 返回 | 说明 |
| --- | --- | --- | --- |
| `Components` | — | Str | 可选组件清单 |
| `SetDownloadBase` | `url` | Str | 下载基址覆盖 |
| `Install` | `name` | Str（裸 id） | 安装组件，返回 `job{n}` |
| `Uninstall` | `name` | Str | 卸载组件 |
| `CancelInstall` | `jobId` | Str | 取消安装 |
| `InstallStatus` | `jobId` | Str | 查询安装状态 |
| `Start` | `language`, `code`, `stdin` | Str（裸 id） | 运行代码，返回 `run{n}` |
| `Poll` | `runId` | Str | 增量取输出 |
| `Stop` | `runId` | Str | 停止运行 |
| `StopAll` | — | Str | 停止全部运行 |

`Install` 与 `Start` 返回裸 id 字符串（`"job{n}"` / `"run{n}"`），不是 JSON 信封（`Select-String -Path MFMath.Host.Rust/src/console.rs -Pattern 'format!\("(job|run)\{\}"'`）。`Start` 的 `language` 缺省为 `"python"`（`Select-String -Path MFMath.Host.Rust/src/handlers.rs -Pattern 'unwrap_or\("python"\)'`）。跑代码走异步：`Start` 立即返回 runId，输出经 `Poll` 增量取。

对象名为 `con`，模块文件为 `console.rs`。原因是 Windows 把 `con` 视为保留设备名，`src/con.rs` 无法加入 git 索引，因此文件名与注册名不同（`main.rs` 的 `mod console` 与 `HOST_OBJECTS` 里的 `"con"`）。

## 11. 返回类型与参数约定

| 返回 | VARIANT 类型 | 前端收到的值 | 方法数 |
| --- | --- | --- | --- |
| `Str` | `VT_BSTR` | 字符串（约定为 JSON 文本） | 69 |
| `Bool` | `VT_BOOL` | 布尔 | 7 |
| `Empty` | `VT_EMPTY` | 无返回 | 8 |

```powershell
"Str   = " + (Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'ret: RetKind::Str').Count
"Bool  = " + (Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'ret: RetKind::Bool').Count
"Empty = " + (Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'ret: RetKind::Empty').Count
```

参数方向声明一律 `VT_BSTR`；`variant_to_arg` 另接受 `VT_I4`、`VT_R8`、`VT_BOOL`、`VT_EMPTY`，`account.EnsureFresh` 的 `thresholdSec` 走数字。`Str` 的约定内容是 JSON 文本，例外是 `con.Install` 与 `con.Start` 的裸 id 字符串。

失败统一返回 `{"isError":true,"value":"原因"}`，由 `handlers.rs` 的 `err_envelope()` 生成（`Select-String -Path MFMath.Host.Rust/src/handlers.rs -Pattern "fn err_envelope"`）。前端只判 `isError`，不区分失败来自哪个对象或哪一层。

## 12. 未注册的 `ai` 对象

宿主不暴露 `ai` 对象。AI 功能由页面直接连接，宿主侧不存在对应桥；AI 的配置与密钥仍经 `sys.StoreRead` / `sys.StoreWrite` 读写存储文件，宿主不解析其内容。边界见 [CREDENTIALS.md](CREDENTIALS.md)。

## 13. 核对

```powershell
# 对象数与方法总数
(Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern '^\s+\("\w+", \w+_SPEC\),').Count   # 9
(Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'MethodSpec \{').Count              # 84

# 引擎注册的 action 数（需要已构建的 Release 产物）
& MF_Mathematics/build/bin/Release/probe_call.exe list_functions   # value.count = 424
```

取信顺序：`HOST_OBJECTS` 与各 `*_SPEC`（`main.rs`）→ `call()` 的分发（`handlers.rs`）→ 启动日志（每个对象注册时打印"宿主对象 `<名>` 已注册（`<n>` 个方法）"）。宿主验收的基线表见 [`ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)。
