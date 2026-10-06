# MFMath.Host.Rust —— 宿主由 C# 换到 Rust（迁移中）

> 状态：**spike 阶段**。当前目录只有工程骨架与方案，尚未能替代 `MFMath.Host`（C#）。
> 引擎（C++ `mf_mathematics.dll`）与前端（`MF_UI/MFMath.UI.Vue`）**都不动**。

---

## 一、为什么换，以及不换什么

- **换的是宿主**：窗口 + WebView2 + 那 10 个桥（DPAPI、HTTP、组件下载、控制台子进程…），
  C# 侧共 **30 文件 / 5,663 行**。
- **不换引擎**：`mf_mathematics.dll` 已经是一个只有两个 C ABI 导出的干净边界
  （`math_call` / `function_exists`），任何语言接它都只是 `libloading` + JSON。
- **不换前端**：`MF_UI/MFMath.UI.Vue` 的 30,149 行一行不改（理由见下）。

## 二、硬约束：**必须保住同步的宿主对象接缝**

前端现在的调用形状是 WebView2 的**同步** COM 宿主对象：

```js
window.chrome.webview.hostObjects.sync.mf.Dispatch("expr_eval_vars_batch", "{…}")
```

这条接缝是**同步**的，而且用在热循环里 —— `lib/plot/sampling.js` 的 `adaptiveSample()`
每轮对几百个点做一次批量求值，`engineCall` 是同步返回的。整棵树里共有
**10 个宿主对象、约 45 处 `call("Method", …)` 调用点**（`engineCall` 更是遍布绘图各页）。

因此：

| 方案 | 结论 |
| --- | --- |
| **wry + `ICoreWebView2::AddHostObjectToScript`**（本目录采用） | 前端**零改动**；Rust 侧要自己实现 `IDispatch`，但**只需实现一个通用版**，10 个桥共用 |
| Tauri 2 的 `invoke()` | ❌ 它是 **async**（返回 Promise）→ `engineCall` 变异步 → `adaptiveSample`、PlotView/3D/Vector/Complex/Geometry 的采样链路全部重写。这不是"换宿主"，是"换前端架构" |
| 自定义协议 + `fetch` | ❌ 同样异步；同步 XHR 在主线程做几百次批量求值不可接受 |

**做法**：Rust 侧实现**一个**通用 `IDispatch`，内部是一张 `(对象名, 方法名) → 处理函数`
的注册表；每个宿主对象都用它注册一遍。方法的返回是 JSON 字符串，和现在
`MathBridge.Dispatch` 的契约逐字一致 —— 前端的 `parse()` 那一层不用动。

## 三、桥清单（迁移映射）

| 宿主对象 | C# 源 | 大约行数 | Rust 侧要点 | 状态 |
| --- | --- | --- | --- | --- |
| `mf` | `MathBridge.cs` + `NativeEngine.cs` | 190 | `libloading` 载入 DLL，调两个 C ABI；分级缓冲（4/16/64 MB） | spike 目标 |
| `win` | `WindowBridge.cs` | 200 | 无边框 + DWM 圆角/投影、拖动、最大/最小、文件对话框（`rfd`） | 待做 |
| `sys` | `SettingsBridge.cs` | 365 | 设置 JSON 读写（含 `.bak`）、依赖 DLL 体检、导出诊断包、打开目录 | 待做 |
| `diag` | `LogBridge.cs` | 90 | 前端异常写进同一份 `app.log` | 待做 |
| `push` | `PushBridge.cs` + `PushHub.cs` | 130 | `PostWebMessageAsJson` 单向下行（组件进度、控制台结束、AI 流式） | 待做 |
| `con` | `ConsoleBridge.cs` | **824** | CPython/MinGW 组件的下载（Range 续传 + SHA-256 + zip 解包）、启动/停止子进程、stdin/stdout 管道 | 最重，最后做 |
| `ai` | `AiBridge.cs` + `AiRelay.cs` + `AiClient.cs` | 345 | `reqwest`(**rustls**) + SSE 中继；密钥 DPAPI 密文 | 待做 |
| `search` | `SearchBridge.cs` + `SearchBackend.cs` + `SearchCache.cs` | 411 + 323 | 三个后端 + 四个解析器 + 缓存（键含引擎） | 待做 |
| `account` | `AccountBridge.cs` + `AccountApi.cs` + `AccountConfig.cs` | 484 | 站点契约、令牌 DPAPI、401 自动登出 | 待做 |
| `update` | `UpdateBridge.cs` | 304 | 版本关系判定、sha256、把下载交给浏览器 | 待做 |

> `reqwest` 一律用 **rustls**（不是 native-tls/Schannel）：宿主自己的 HTTP 从此不再依赖
> Schannel —— 这台机器上那个 `SEC_E_NO_CREDENTIALS` 就是 Schannel 路径的问题。

## 四、Spike 验收（做完这三步再谈全量）

| 步骤 | 内容 | 验收方式（用现成用例，不新写测试） | 实测结果（2026-10-06） |
| --- | --- | --- | --- |
| **S1** | wry 窗口 + `SetVirtualHostNameToFolderMapping("mfmath.local", wwwroot)` + 打开 CDP 9222 | 宿主起来后页面能加载；用 CDP 断言 `#app` 有内容、路由可用 | ✅ **全过**：页面在 `https://mfmath.local/index.html#/`，Vue 已挂载，12 个导航元素 |
| **S2** | 通用 `IDispatch` + `mf` 对象（`Dispatch` / `Ready` / `Version` / `FunctionExists`） | `node tools/verify-spike.mjs`（它只依赖 `mf.Dispatch`） | ⚠ **5/5**：`hostObjects.sync` 存在、`mf` 可见，但 **`typeof mf.Dispatch === "string"`** —— 见下 |
| **S3** | `win` 对象（无边框/拖动/文件对话框）+ `sys` 的读写 | `node tests/cdp-workspace.mjs` 的"另存为/从文件打开"段通过 | 未开始 |

### S2 卡在哪，为什么

实测输出：

```
{"hasSync":true,"names":[],"hasMf":true}
{"t":"string","err":"mf.Dispatch is not a function"}
```

`mf` 在同步命名空间里**可见**（说明 `GetIDsOfNames` 通了），但读 `mf.Dispatch` 拿到的是**字符串**：
WebView2 的宿主对象代理要靠 **`ITypeInfo`** 才知道一个成员是"方法"还是"属性"。没有类型信息时
它按属性处理 —— 读 `Dispatch` 就发一次 `DISPATCH_PROPERTYGET`（无参），我们的处理函数返回了
"缺少函数名"的错误 JSON，于是 `mf.Dispatch` 变成了字符串，后面调用自然"不是函数"。

**试过但已回退的路**：把整套 IDispatch 换成 Windows 的 `CreateDispTypeInfo` + `CreateStdDispatch`
（VB6/ATL 的 dispinterface 标准机）。结果**宿主起不来了**——注意窗口是在 `event_loop.run()` 才显示的，
所以 `register()` 一旦失败，表现就是"窗口根本没出现"，而不是报错。已回退。

**下一步（更小的增量）**：保留这个**已被证明能响应** GetIDsOfNames/Invoke 的手写 IDispatch，
只把缺失的那一半补上 —— `GetTypeInfoCount` 返回 1，`GetTypeInfo` 返回一个由
`CreateDispTypeInfo` 从同一张方法表造出的 `ITypeInfo`（dispid 与 `GetIDsOfNames` 保持一致）。
即"只加类型信息，不换调度机制"。

## 五、本机开发的两条特殊处理（只在这台机器上需要）

1. **`CARGO_HOME` 放在仓库内**（`.cargo-home/`）：本会话的沙箱只允许写工作区，
   写 `~/.cargo` 会被拒。构建时设：`$env:CARGO_HOME = "<repo>\.cargo-home"`。
2. **crates 走本地明文代理**（`.cargo/config.toml` + `tools/crates-proxy.mjs`）：
   这台机器的 Schannel 在受限令牌下不可用（`AcquireCredentialsHandle failed:
   SEC_E_NO_CREDENTIALS`），cargo/curl 取不了包，而 Node 可以。于是让 Node 去 HTTPS 取、
   cargo 只走 127.0.0.1 明文：
   ```powershell
   node MFMath.Host.Rust/tools/crates-proxy.mjs      # 127.0.0.1:8432
   $env:CARGO_HOME = "<repo>\.cargo-home"
   cargo build
   ```
   CI / 干净机器上不需要这两条（删掉 `.cargo/config.toml` 即回直连）。

## 六、与 C# 宿主共存

两者可以并存、互不干扰，切换成本为零：

- **前端共用**：Release 的 `wwwroot` 是 `MF_UI/MFMath.UI.Vue/dist` 的拷贝，Rust 宿主读同一份；
- **数据目录共用**：`%LOCALAPPDATA%\MFMath\`（settings / logs / components / WebView2）；
  迁移期两边都写同一份 JSON（格式不变），谁的实现先跑通就用谁；
- **端到端用例共用**：47 个 `cdp-*.mjs` 走的是 CDP，跟宿主用什么语言无关。

## 七、已知风险

| 风险 | 说明 | 对策 |
| --- | --- | --- |
| Rust 侧 `IDispatch` 实现 | 需要 unsafe COM/VARIANT 处理，是本迁移唯一"可能翻车"的点 | S2 先做它；只写一份通用实现 |
| 控制台桥（824 行） | 子进程 + 管道 + 组件下载 = 最多细节 | 放到最后；C# 版继续可用直到搬完 |
| 两份宿主的行为漂移 | 迁移期两边都在 | 同一批 CDP 用例同时对着两边跑，谁红修谁 |
| 本机 Schannel | 影响取包，不影响产物 | 见第五节；或用另一台机器/CI 构建 |
