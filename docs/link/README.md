# 链接层

> 本文说明前端与宿主之间的调用接缝：接缝由 `AddHostObjectToScript` 构成，调用形状受三条契约约束，`mf.Dispatch` 必须同步返回。
> 方法清单见 [OBJECTS.md](OBJECTS.md)，异步与下行通道见 [JOBS-PUSH.md](JOBS-PUSH.md)，凭据边界见 [CREDENTIALS.md](CREDENTIALS.md)，宿主谱系见 [HOSTS.md](HOSTS.md)。
> 权威源是 [`hostobject.rs`](../../MFMath.Host.Rust/src/hostobject.rs)、[`main.rs`](../../MFMath.Host.Rust/src/main.rs)、[`handlers.rs`](../../MFMath.Host.Rust/src/handlers.rs) 与 [`bridge.js`](../../MF_UI/MFMath.UI.Vue/src/lib/bridge.js)。

## 1. 链接层的位置

| 层 | 位置 | 对外接口 |
| --- | --- | --- |
| 引擎 | `MF_Mathematics/`（C++17） | 两个 C ABI：`math_call` 与 `function_exists`，注册 424 个 action |
| 宿主 | `MFMath.Host.Rust/`（Rust + Tauri v2 + WebView2） | 9 个宿主对象、84 个方法 |
| 前端 | `MF_UI/MFMath.UI.Vue/`、`MF_UI/MFMath.UI.React/` | `window.chrome.webview.hostObjects.sync.<对象>.<方法>(…)` |

```powershell
# 引擎注册的 action 数（需要已构建的 Release 产物）
& MF_Mathematics/build/bin/Release/probe_call.exe list_functions   # value.count = 424
```

链接层是宿主与前端 `src/lib/**` 之间的接缝。更换宿主时编程语言与框架可以变，接缝的形状不变：对象名、方法名、参数个数与返回形状逐条对齐，前端的调用点与端到端用例因此不用跟着改。

## 2. 接缝：`AddHostObjectToScript`

页面侧的调用形状：

```js
window.chrome.webview.hostObjects.sync.mf.Dispatch("expr_eval", "{\"expr\":\"x^2\",\"x\":3}")
//                        ↑        ↑   ↑          ↑
//                     WebView2   sync 对象名    PascalCase 方法名
```

`sync` 是 WebView2 的同步命名空间，调用在渲染进程主线程上阻塞到方法返回。宿主侧的落点是 `ICoreWebView2::AddHostObjectToScript`，实现在 `register`（`Select-String -Path MFMath.Host.Rust/src/hostobject.rs -Pattern "pub fn register"`），由 `main.rs` 在 `win.with_webview(...)` 的闭包内对 `HOST_OBJECTS` 的每一项调用一次（`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "hostobject::register"`）。

`register` 完成三件事：从 `MethodSpec` 表经 `build_type_info` 造一份 `ITypeInfo`；把 `HostObject`（手写 vtable，IUnknown 三个槽位加 IDispatch 四个槽位）装进 `VARIANT(VT_DISPATCH)`；调用 `AddHostObjectToScript` 注册对象名。对象与类型信息都用 `Box::leak` 保持到进程结束。

| 环节 | 符号 | 位置 |
| --- | --- | --- |
| 注册 | `register` | `hostobject.rs` |
| 对象表 | `HOST_OBJECTS` | `main.rs` |
| 名字到 dispid | `ids_of_names` | `hostobject.rs` |
| 类型信息 | `build_type_info`、`type_info_count` | `hostobject.rs` |
| 编组 | vtable `invoke`、`variant_to_arg`、`write_result` | `hostobject.rs` |
| 分发 | `call` | `handlers.rs` |

### 2.1 类型信息决定成员是不是函数

`GetTypeInfoCount` 返回 1，`GetTypeInfo` 交出由 `CreateDispTypeInfo` 造出的 `ITypeInfo`。WebView2 的同步代理用类型信息区分成员是方法还是属性；缺少类型信息时它按属性取值发出 `DISPATCH_PROPERTYGET`，读 `mf.Dispatch` 得到字符串而不是函数。

`invoke` 因此校验调用种类：只带 `DISPATCH_PROPERTYGET`、`DISPATCH_PROPERTYPUT` 或 `DISPATCH_PROPERTYPUTREF` 而不带 `DISPATCH_METHOD` 的调用返回 `DISP_E_MEMBERNOTFOUND`（`Select-String -Path MFMath.Host.Rust/src/hostobject.rs -Pattern "DISP_E_MEMBERNOTFOUND"`）。方法名与 dispid 的对应关系是下标加一，`ids_of_names` 与 `build_type_info` 共用这一规则。

### 2.2 不是 Tauri 的 `invoke`

Tauri 的 `invoke` 命令层已从宿主移除，前端 `bridge.js` 里的 `tauriInvoke` 探测保留，它在没有 Tauri 内部对象时返回 null。`invoke` 只返回 Promise，无法承担需要同步返回的 `mf.Dispatch`。`AddHostObjectToScript` 与下行通道用的 `PostWebMessageAsJson` 同在 `ICoreWebView2` 接口上。

## 3. 宿主对象与方法表

```powershell
# 每个对象的方法数，以及对象数与方法总数（对象数 = 9，方法数 = 84）
$src = Get-Content MFMath.Host.Rust/src/main.rs -Raw
$parts = [regex]::Split($src, 'const (\w+_SPEC)')
for ($i = 1; $i -lt $parts.Count; $i += 2) {
  "{0} = {1}" -f $parts[$i], ([regex]::Matches($parts[$i + 1], 'MethodSpec \{')).Count
}
(Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern '^\s+\("(\w+)", \w+_SPEC\),').Count
(Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'MethodSpec \{').Count
```

| 对象 | 用途 | 方法数 | 前端入口 |
| --- | --- | --- | --- |
| `mf` | 引擎调用与后台任务 | 16 | `lib/bridge.js` |
| `sys` | 设置存储、引擎报告、诊断导出 | 8 | `lib/settings/bridge.js`、`lib/settings/io.js` |
| `diag` | 前端异常写入宿主日志 | 1 | `lib/diagnostics/errors.js` |
| `win` | 窗口操作与文件对话框 | 9 | `lib/bridge.js`、`lib/settings/io.js` |
| `push` | 下行通道的诊断与自测 | 3 | `lib/push.js` |
| `update` | 更新提示 | 6 | `lib/update/bridge.js` |
| `account` | 用户系统 | 19 | `lib/account/bridge.js` |
| `search` | 联网搜索 | 12 | `lib/search/bridge.js` |
| `con` | 控制台与可选组件 | 10 | `lib/console/bridge.js` |

前端访问的对象名集合与 `HOST_OBJECTS` 一致：

```powershell
Get-ChildItem -Path MF_UI/MFMath.UI.Vue/src -Recurse -Include *.js,*.ts | Select-String -Pattern 'hostObjects\?\.sync\?\.(\w+)' -AllMatches | ForEach-Object { $_.Matches } | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
# account, con, diag, mf, push, search, sys, update, win
```

React 工程经 `@shared/*` 指到 Vue 的 `src/lib`，桥因此只有一份实现。React 侧另用 [`hostSafe.ts`](../../MF_UI/MFMath.UI.React/src/lib/hostSafe.ts) 的 `safe()` 兜住首帧期间宿主对象尚未挂上时抛出的异常。

## 4. 三条契约

### ① 成员名与 `MethodSpec` 表中的名字一致

`MethodSpec.name` 是名字的唯一来源：`ids_of_names` 由它给出 dispid，`build_type_info` 由它写入 `ITypeInfo`。前端按 PascalCase 逐字书写。访问宿主对象上不存在的成员时 WebView2 抛 `0x80070057`，不返回 `undefined`，因此探测成员不能靠 `typeof`；`hostSafe.ts` 的 `safe()` 与 `reportToHost` 用 try/catch 兜底，`engineCall` 把异常转成错误信封。

宿主侧现状是 `ids_of_names` 用 `eq_ignore_ascii_case` 比较名字（`Select-String -Path MFMath.Host.Rust/src/hostobject.rs -Pattern "eq_ignore_ascii_case"`），派发阶段不因大小写拒绝。小写写法是否被 WebView2 代理接受未实测。验证方法：设环境变量 `MF_TRACE_DISPATCH=1` 启动宿主，读 exe 同目录的 `dispatch-trace.log`，其中记录每次 `GetIDsOfNames` 与 `Invoke` 的原始参数。

### ② 返回类型只有三种

| `Ret` / `RetKind` | VARIANT 类型 | 前端收到的值 | 方法数 |
| --- | --- | --- | --- |
| `Ret::Str` | `VT_BSTR` | 字符串 | 69 |
| `Ret::Bool` | `VT_BOOL` | 布尔 | 7 |
| `Ret::Empty` | `VT_EMPTY` | 无返回 | 8 |

```powershell
"Str   = " + (Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'ret: RetKind::Str').Count
"Bool  = " + (Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'ret: RetKind::Bool').Count
"Empty = " + (Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'ret: RetKind::Empty').Count
```

`write_result` 负责把 `Ret` 写进返回 `VARIANT`。`Ret::Str` 的约定内容是 JSON 文本，`engineCall` 对字符串做 `JSON.parse`（`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/bridge.js -Pattern "export function engineCall"`）。例外是 `con.Install` 与 `con.Start`：返回裸 id 字符串（`job{}`、`run{}`，`Select-String -Path MFMath.Host.Rust/src/console.rs -Pattern 'format!\("(job|run)\{\}"'`），前端按 `String(c.Install(name))` 使用。

参数方向的声明一律 `VT_BSTR`；`variant_to_arg` 另外接受 `VT_I4`、`VT_R8`、`VT_BOOL`、`VT_EMPTY`，`account.EnsureFresh` 的 `thresholdSec` 走数字这一条。

### ③ 错误走信封

失败一律返回 `{"isError":true,"value":"原因"}`，由 `err_envelope` 生成（`Select-String -Path MFMath.Host.Rust/src/handlers.rs -Pattern "fn err_envelope"`）。前端只判 `isError`，不区分失败来自哪一个对象或哪一层。

| 情况 | `value` 的形状 | 生成位置 |
| --- | --- | --- |
| 引擎调用失败 | 引擎给出的原因 | `handlers.rs` 的 `mf` 分支 |
| 参数缺失 | `Dispatch 缺少函数名` 一类 | 各对象的 `match` 分支 |
| 对象名未知 | `未知宿主对象：<名>` | `call` 的兜底分支 |
| 方法名未知 | `<对象> 没有这个方法：<名>` | 每个对象 `match` 的兜底分支 |

方法表与实现必须同时具备：`MethodSpec` 表里有、`handlers.rs` 里没有的方法在调用时得到方法名未知的信封，失败是显式的。

## 5. 同步调用的必要性

`engineCall` 是同步函数，调用即阻塞渲染进程主线程直到方法返回。绘图页的采样按"每条曲线一次调用"组织，改成 Promise 会把采样时序拆开。

| 调用点 | 形状 |
| --- | --- |
| `usePlotSampling.ts` 的 `batchEval` | 每条曲线一次 `expr_eval_vars_batch` |
| `PlotView.vue` 的 `sampleAll` | 每条曲线一次 `expr_eval_vars_batch` |
| `Plot3DView.vue` | 曲面一次 `expr_eval_grid` |
| `PlotVectorView.vue` | 向量场每个分量一次 `expr_eval_grid` |
| `PlotComplexView.vue` | 复平面 `complex_grid` |

分界线写在 `shouldRunAsync`（`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern "export function shouldRunAsync"`），判据是工作量而不是主观轻重：

| action | 工作量公式 | 阈值 |
| --- | --- | --- |
| `mandelbrot` | `width × height × max_iter` | 1.5e8 |
| `complex_grid` | `nx × ny` | 2.5e5 |
| `expr_eval_grid` | `xs.length × ys.length` | 2.5e5 |
| `matrix_multiply` | `n × n × n` | 2e6 |

```powershell
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern "1.5e8|2.5e5|2e6"
```

超过阈值，或落在 `ALWAYS_ASYNC` 集合里（`integrate`、`factor_integer`、`solve_sym` 等规模无法从参数估计的动作），才走 `engineCallAsync`。异步通道的派发与轮询语义见 [JOBS-PUSH.md](JOBS-PUSH.md)。

同步的必要性来自主线程的约束：`hostObjects.sync` 的调用要在主线程空闲时才返回控制权，而 Promise 的兑现同样排在主线程的事件循环上，主线程阻塞等 Promise 不会推进它。

## 6. 新增一个宿主对象

1. `main.rs`：写 `const XXX_SPEC: &[MethodSpec] = &[…]`，逐个列出参数名，返回类型取 `RetKind` 的三种之一。
2. `main.rs`：在 `HOST_OBJECTS` 里加 `("xxx", XXX_SPEC)`。
3. `handlers.rs`：在 `call` 里加 `"xxx" => xxx(method, args)`，再写该对象的 `match method`。
4. `hostobject.rs` 不改：COM 层与对象名无关。
5. 前端：加该对象的访问器，方法名与 `MethodSpec` 表逐字一致。

对象名与模块文件名可以不同。`con` 的对象名对应模块文件 `console.rs`：Windows 把 `con` 当保留设备名，`src/con.rs` 无法加入 git 索引。前端调用的名字以 `HOST_OBJECTS` 里的注册名为准。

## 7. 核对

```powershell
# 宿主对象数、方法数、返回类型分布
$src = Get-Content MFMath.Host.Rust/src/main.rs -Raw
$parts = [regex]::Split($src, 'const (\w+_SPEC)')
for ($i = 1; $i -lt $parts.Count; $i += 2) {
  "{0} = {1}" -f $parts[$i], ([regex]::Matches($parts[$i + 1], 'MethodSpec \{')).Count
}
(Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern '^\s+\("(\w+)", \w+_SPEC\),').Count
(Select-String -Path MFMath.Host.Rust/src/handlers.rs -Pattern '^\s+"(\w+)" => \w+\(method, args\),').Count

# 引擎注册的 action 数
& MF_Mathematics/build/bin/Release/probe_call.exe list_functions
```

取信顺序：代码（`HOST_OBJECTS`、各 `*_SPEC`、`call` 的 `match`）→ 启动日志（每个对象注册时打印 `宿主对象 <名> 已注册（<n> 个方法）`）→ 本文 → [`LINK-LAYER.md`](../../MFMath.Host.Rust/docs/LINK-LAYER.md)（迁移记录，写作时刻实测，不保证当前仍成立）。

现场观测的两条途径：设 `MF_TRACE_DISPATCH=1` 得到 exe 同目录的 `dispatch-trace.log`；宿主启动时写入 `--remote-debugging-port=9222`，端到端用例经 CDP 驱动界面，运行入口是 [`run-all.ps1`](../../MF_UI/MFMath.UI.Vue/tests/run-all.ps1)。
