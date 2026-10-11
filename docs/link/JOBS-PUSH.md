# 异步任务通道与下行推送

> 本文说明两条旁路通道：耗时较长的引擎调用如何改走后台任务通道，以及宿主如何在不依赖页面轮询的情况下主动向页面发消息。
> 内容包括任务队列与串行执行、任务状态、取消语义、推送信封、发送路径的约束与主题清单。
> 接缝的构成见 [README.md](README.md)，宿主对象与方法清单见 [OBJECTS.md](OBJECTS.md)，宿主谱系见 [HOSTS.md](HOSTS.md)。
> 权威源是 [`jobs.rs`](../../MFMath.Host.Rust/src/jobs.rs)、[`push.rs`](../../MFMath.Host.Rust/src/push.rs)、[`push.js`](../../MF_UI/MFMath.UI.Vue/src/lib/push.js)。

## 1. 两条通道的分工

| 通道 | 解决的问题 | 代价 |
| --- | --- | --- |
| 任务通道：`DispatchJob` / `PollJob` / `CancelJob` / `JobStats` | 同步 `Dispatch` 在 WebView2 的 UI 线程上执行引擎调用，重活期间窗口停止重绘，系统判定为未响应 | 页面按固定间隔轮询；取消只停止等待，不停止计算 |
| 推送通道：`push` 对象 + `PostWebMessageAsJson` | 宿主主动通知页面（安装进度、控制台输出、搜索结束），在只有同步桥时只能靠轮询，延迟固定且空转 | 推送是旁路，消息可能丢失；权威数据仍由同步桥提供 |

两条通道互相独立：任务通道不产生推送，推送不携带任务状态。

## 2. 异步任务通道

### 2.1 适用对象

`jobs.rs` 的模块注释列出四类动机，均来自引擎参数上界：

| 动作 | 规模上界 |
| --- | --- |
| `mandelbrot` | 分辨率 ≤1000 × 迭代 ≤1024，约 1e9 次迭代 |
| `complex_grid` | resolution ≤1000，约 1e6 点 |
| `expr_eval_grid` | 工具箱参数自由，2000×2000 = 4e6 点 |
| `factor_integer` / `integrate_double` / `taylor_series` 等符号运算 | 无上界 |

定位命令：`Select-String -Path MFMath.Host.Rust/src/jobs.rs -Pattern "mandelbrot|complex_grid|expr_eval_grid"`

### 2.2 队列与串行执行

`start()` 起一条名为 `mf-engine-jobs` 的常驻线程，幂等，由 `main` 在启动时调用一次。队列由 `queue()` 返回的静态 `(Mutex<Queue>, Condvar)` 持有，`Queue` 的字段是 `pending`（`VecDeque<Job>`）、`jobs`（`HashMap<String, Job>`）、`running`（当前任务 id，空闲时为 `None`）。`worker_loop` 在没有待跑任务时等待 `Condvar`。

引擎调用串行执行，同一时刻只有一个任务处于 `running`。`jobs.rs` 记录的理由是：引擎中除 `numerical/numerical_integration.cpp` 的一个 `thread_local` 外没有同步原语，`math_call` 无锁（`api.cpp` 只做 dispatch 与 memcpy），并发调用会触及 FLINT 与 SymEngine 的全局缓存，而这一点尚未验证。

定位命令：`Select-String -Path MFMath.Host.Rust/src/jobs.rs -Pattern "Condvar|num_threads"`

自检同时验证该性质：派发一个重活后再派发第二个，第二个停留在 `queued`，见 2.7。

### 2.3 方法契约

四个方法挂在宿主对象 `mf` 上（`main.rs` 的 `MF_SPEC`，注册于 `HOST_OBJECTS` 的 `("mf", MF_SPEC)` 项）。

| 方法 | 参数 | 返回 |
| --- | --- | --- |
| `DispatchJob(name, argsJson)` | 引擎 action 名、参数 JSON 文本 | `{"ok":true,"jobId":"e-N"}`；加锁失败时 `{"ok":false,"error":…}` |
| `PollJob(jobId)` | 任务 id | `{"ok":true,"jobId","name","state","ms","elapsedMs","result"}`；未知 id 时 `{"ok":false,"error":"未知的任务 id"}` |
| `CancelJob(jobId)` | 任务 id | `{"ok":true,"state":…,"note":…}`；未知 id 时 `{"ok":false,"error":"未知的任务 id"}` |
| `JobStats()` | 无 | `{"pending":N,"running":id或null,"total":N}`；加锁失败时 `{"error":…}` |

`jobId` 由 `SEQ: AtomicU64` 生成，初值为 1，格式为 `e-<序号>`，编号在进程内单调递增且不回收。

`DispatchJob` 入队后立即返回，不等待引擎。`PollJob` 的 `result` 是引擎返回的信封原文，形如 `{"isError":…,"value":…}`，前端按原样解析。任务处于 `queued` 或 `running` 时 `result` 为空串。`ms` 是本次引擎调用的耗时，在完成前为 0。`elapsedMs` 是自 `started_ms` 起的时长；`started_ms` 在派发时写入，任务开始执行时更新为开工时刻，因此排队期间 `elapsedMs` 从派发起算，进入 `running` 后从开工起算。

定位命令：`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'MethodSpec \{ name: "DispatchJob"'`

### 2.4 任务状态

`state` 的取值有五个，定义在 `Job.state` 上：

| 状态 | 含义 |
| --- | --- |
| `queued` | 已入队，未开始 |
| `running` | 正在执行引擎调用 |
| `done` | 引擎返回成功，`result` 为引擎信封原文 |
| `error` | 引擎调用失败，`result` 为 `{"isError":true,"value":<错误文本>}` |
| `canceled` | 被取消，`result` 为空串 |

定位命令：`Select-String -Path MFMath.Host.Rust/src/jobs.rs -Pattern "queued \| running"`

### 2.5 取消语义

`CancelJob` 的行为按任务所处状态分为三种，全部在 `cancel_job` 内实现：

| 取消时的状态 | 宿主动作 | 返回的 `note` |
| --- | --- | --- |
| `queued` | 从 `pending` 中移除，状态置为 `canceled` | `尚未开始，已作废` |
| `running` | 置 `canceled` 标记，计算继续，结果回来时丢弃 | `已停止等待；引擎不支持中途停止，它会把这一步算完后丢弃结果` |
| `done` / `error` | 置 `canceled` 标记，已产生的 `result` 保留 | `已作废` |

引擎没有取消钩子，工作线程无法中断已经在执行的 `Engine::call_json`。因此取消的语义是停止等待并丢弃结果，不是停止计算。页面文案与之一致：`engineCallAsync` 在取消时返回 `{isError:true, value:"已取消等待（引擎会把这一步算完后丢弃结果）", canceled:true}`。

做到真正中断需要把执行器换成子进程并在取消时结束该进程。该路径未实现，引擎侧不需要改动。

定位命令：`Select-String -Path MFMath.Host.Rust/src/jobs.rs -Pattern "已停止等待|尚未开始"`

### 2.6 页面侧调用

[`bridge.js`](../../MF_UI/MFMath.UI.Vue/src/lib/bridge.js) 提供两个入口：`engineCall(name, args)` 走同步通道，`engineCallAsync(name, args, opts)` 走任务通道。后者的行为如下。

| 行为 | 实现 |
| --- | --- |
| 退回同步 | `typeof mf.DispatchJob !== "function"` 时直接调用 `engineCall`；`DispatchJob` 抛异常时同样退回 |
| 轮询间隔 | `POLL_MS = 120`（毫秒） |
| 终态 | `done` / `error` 时解析 `result` 并交付；`canceled` 时交付取消结果 |
| 进度回调 | `opts.onProgress({state, elapsedMs, ms})` |
| 取消 | `opts.signal`（`AbortSignal`）触发时调用 `CancelJob` |
| 无宿主 | 返回 `null`，与同步版一致 |

`engineJobPoll(jobId)` 与 `engineJobCancel(jobId)` 是对 `PollJob` / `CancelJob` 的直接封装，供诊断使用；常规调用由 `engineCallAsync` 内部轮询完成。

定位命令：`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/bridge.js -Pattern 'POLL_MS = |DispatchJob !== '`

走哪条通道由规模决定。[`asyncPolicy.js`](../../MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js) 用 `BY_SIZE` 估算工作量，超过 `LIMIT` 才走异步：

| action | 工作量估算 | 阈值 |
| --- | --- | --- |
| `mandelbrot` | `width × height × max_iter`（`max_iter` 缺省 256） | 1.5e8 |
| `complex_grid` | `nx × ny` | 2.5e5 |
| `expr_eval_grid` | `xs.length × ys.length` | 2.5e5 |
| `matrix_multiply` | `n³` | 2e6 |

阈值由实测换算而来：模块注释记录 `mandelbrot` 600×600×256 = 9.2e7 次迭代耗时 248 ms，约 3.7e8 次迭代/秒，因此 1.5e8 对应约 400 ms。

另有一个 `ALWAYS_ASYNC` 集合，成员是没有规模上界、无法从参数估算的 action，命中即走异步。集合规模为 28 项，核对命令：

```powershell
$a = Get-Content MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Raw
$m = [regex]::Match($a, 'ALWAYS_ASYNC = new Set\(\[(?<body>.*?)\]\)', [System.Text.RegularExpressions.RegexOptions]::Singleline)
[regex]::Matches($m.Groups['body'].Value, '"([a-z_0-9]+)"').Count
```

`shouldRunAsync(name, args, opt)` 是唯一判据入口，`opt.force` 为真时无条件走异步，对应工具箱的「后台运行」选项。

反向约束：绘图页按曲线发起的采样与极值标记保持同步调用。那些调用是毫秒级，且每条曲线引入一次 `await` 会改变采样时序。若将来放宽这些网格参数的上界，需要同时把它们纳入异步判据。

定位命令：`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern "LIMIT = \{" -Context 0,6`

### 2.7 无头自检

`--selftest-jobs` 不依赖 WebView2，因此宿主窗口无法启动的环境下仍可运行。自检覆盖五项：小活完成且结果正确、重活在跑时第二个任务排队、取消排队中的任务、重活完成且结果点数正确、取消运行中的任务并丢弃结果。末行输出 `RESULT|selftest-jobs|PASS|5`，其中最后一个字段是项目数。

```powershell
& MFMath.Host.Rust/target/debug/mfmath-host-rust.exe --selftest-jobs
```

判定等待的两个辅助函数避免了按固定时长睡眠：`wait_final` 以 50 ms 间隔轮询到终态，`wait_running` 以 10 ms 间隔轮询到 `running` 后才执行取消。取消运行中任务的用例依赖后者，因为该测试负载的执行时长与机器速度相关。

## 3. 推送通道

### 3.1 发送路径

推送使用 WebView2 的原生 `PostWebMessageAsJson`，页面侧在 `chrome.webview` 的 `message` 事件上接收。这条路挂在 WebView2 上，不挂在某个前端框架上，因此换宿主时页面侧无需改动。

发送路径为三段：

```
调用方 ──send（只写入 channel，立即返回）──▶ mf-push worker 线程
                                             │
                               run_on_main_thread（从 worker 调用才排队）
                                             ▼
                                     主线程执行 post
```

`send` 只把信封字符串放入 `Sender<String>`，不等待投递，返回值表示是否已排入队列，不表示已送达。常驻 worker `mf-push` 收到消息后调用 `AppHandle::run_on_main_thread`，闭包在事件循环的下一拍于主线程执行 `post`。`post` 通过 `CORE: OnceLock<CoreHandle>` 取得接口并调用 `PostWebMessageAsJson`。

`CoreHandle` 在 `attach` 时 clone 一次 `ICoreWebView2`（即 AddRef），并由 `OnceLock` 持有到进程结束。

定位命令：`Select-String -Path MFMath.Host.Rust/src/push.rs -Pattern "fn send|fn worker|fn post|run_on_main_thread"`

### 3.2 信封

```json
{ "topic": "console.run", "seq": 42, "ts": 1730000000000, "payload": { } }
```

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `topic` | 字符串 | 主题名，页面按主题订阅 |
| `seq` | 整数 | 宿主侧序号，自 1 起单调递增 |
| `ts` | 整数 | 宿主发出时的毫秒时间戳 |
| `payload` | 任意 JSON 或 `null` | 主题自身的数据 |

`send(topic, payload_json)` 的第二个参数是 JSON 文本。空串或全空白转换为 `null`；解析失败的文本同样转换为 `null`，不报错。因此经 `send` 直发的生产者需要自行保证文本合法。

定位命令：`Select-String -Path MFMath.Host.Rust/src/push.rs -Pattern 'json!\(\{ "topic"'`

### 3.3 三条约束

| 约束 | 实现 |
| --- | --- |
| 只在 UI 线程接触 WebView2 | 由 worker 经 `run_on_main_thread` 排队回主线程保证 |
| 推送失败不抛给调用方 | `send` 返回布尔值；失败时累加 `FAILED` 并记录 `LAST_ERROR` |
| 信封固定、`seq` 单调递增 | `SEQ` 自增；页面用序号连续性判断是否丢失消息 |

失败分三类：通道未连接（WebView2 尚未就绪或窗口已关闭）、worker 已退出、事件循环已退出。这三类都不影响调用方的业务流程。

### 3.4 发送路径必须经过 worker 的原因

`push.rs` 记录了四种曾尝试的做法及其结果，最终方案是「worker 线程 → `run_on_main_thread` → 主线程 post」。

| 做法 | 结果 |
| --- | --- |
| 在同步宿主对象回调内直接调用 `PostWebMessageAsJson` | 调用期间浏览器正在等待 `Invoke` 返回，形成重入等待：方法不返回，页面失去响应，stderr 与崩溃日志中没有记录 |
| 在主管道线程上调用 `run_on_main_thread` | `tauri-runtime-wry` 的 `send_user_message` 在当前线程即主线程时就地执行闭包，仍然构成重入 |
| 从其他线程直接调用 `ICoreWebView2` | 该接口不是 agile 对象且未注册 proxy/stub，`CoMarshalInterThreadInterfaceInStream` 编组失败并返回 `REGDB_E_IIDNOTREG 0x80040155`；用裸指针跨线程调用导致宿主进程退出 |
| 把 `ICoreWebView2` 保存为裸指针 | 该引用取自 `with_webview` 闭包，闭包结束时被 Release，之后使用即悬垂指针，症状与重入一致：页面卡住或宿主静默退出 |

同一处还记录了以 `SetTimer` 配合 1 ms 回调的尝试：计时器注册成功且 `SetTimer` 返回非 0，但回调没有被调用。

上述结论来自 `push.rs` 文件头的记录。判定当前代码是否仍走目标路径，用定位命令核对 `worker`、`post` 与 `CoreHandle` 三处实现。

### 3.5 诊断桥

宿主对象 `push` 提供三个方法（`main.rs` 的 `PUSH_SPEC`）：

| 方法 | 参数 | 返回 |
| --- | --- | --- |
| `Ready()` | 无 | 通道是否已挂上（`CORE`、`APP`、`TX` 三者均就绪） |
| `Info()` | 无 | 通道状态 JSON |
| `Emit(topic, payloadJson)` | 主题、payload JSON 文本 | `{"ok":true,"seq":N}` 或 `{"ok":false,"seq":N,"error":…}` |

`Info()` 的字段为 `ready`、`sent`、`failed`、`seq`、`attachedMs`、`lastTopic`、`lastError`、`hostVersion`，其中 `sent` 是实际投递成功的条数，`failed` 是排队失败与投递失败的合计。

`Emit` 是页面经宿主再回到页面的往返调用，用于自测与诊断。它在调用 `send` 之前做校验：主题去掉首尾空白后不得为空、长度不得超过 120 个字符、payload 若非空必须是合法 JSON。

定位命令：`Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern "PUSH_SPEC" -Context 0,4`

### 3.6 页面侧订阅

`push.js` 的导出与职责：

| 导出 | 职责 |
| --- | --- |
| `initPush()` | 挂上 `chrome.webview` 的 `message` 监听，幂等；无宿主时不生效 |
| `onPush(handler)` / `onPush(topic, handler)` | 订阅全部主题或单个主题，返回取消订阅函数 |
| `pushState` | 页面侧计数：`available`、`received`、`lastTopic`、`lastTs`、`lastSeq`、`gaps` |
| `pushInfo()` | 同时返回宿主侧 `Info()` 与页面侧计数，用于判断消息停在哪一段 |
| `isPushHosted()` | 宿主是否提供 `push` 桥 |
| `emit(topic, payload)` | 经宿主往返发送一条消息 |
| `pushLog()` | 最近收到的信封列表，上限 `MAX_LOG = 50` 条 |

分发规则：监听器只处理至少含有字符串 `topic` 的消息，其余消息被忽略。主题匹配是精确比较，由 `dispatch` 按 `h.topic !== env.topic` 跳过不匹配的订阅方；`search` 相关订阅在 `search/bridge.js` 内用 `topic.startsWith("search.")` 前缀过滤。单个订阅方抛出的异常被捕获并写入控制台，不影响其他订阅方与推送本身。

`gaps` 的计数条件是收到序号与上一个序号之差不为 1，用于发现丢失的消息。

`initPush` 会把 `{info, state, log, on, emit}` 挂到 `window.__mfPush`，供端到端用例通过 CDP 读取。

无宿主（浏览器预览）时上述接口全部降级为空实现，界面照常可用。

定位命令：`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/push.js -Pattern "export function|MAX_LOG|__mfPush"`

### 3.7 主题清单

宿主侧当前有 5 处 `push::send` 调用，覆盖 5 个主题。核对命令：

```powershell
Select-String -Path MFMath.Host.Rust/src/*.rs -Pattern 'push::send\("([a-z.]+)"' |
  ForEach-Object { $_.Matches[0].Groups[1].Value } | Sort-Object -Unique
```

| 主题 | 生产者 | 页面订阅方 | 用途 |
| --- | --- | --- | --- |
| `component.install` | `console.rs` | `components/settings/ComponentsGroup.vue` | 组件安装进度 |
| `console.run` | `console.rs` | `views/tools/ConsoleView.vue` | 控制台运行输出与结束 |
| `search.done` | `search.rs` | `lib/search/bridge.js` | 搜索成功 |
| `search.error` | `search.rs` | `lib/search/bridge.js` | 搜索失败，携带错误分类 |
| `account.changed` | `account.rs` | `lib/account/bridge.js` | 登录态变化 |

另有 `settings.test` 由页面经 `emit` 发出、由宿主回推，用于验证往返链路（`components/settings/EngineGroup.vue`），以及 `test.echo` 由端到端用例发出（`tests/cdp-push.mjs`）。这两个主题没有业务订阅方。

订阅方对数据的处理：

| 主题 | payload 关键字段 | 订阅方处理 |
| --- | --- | --- |
| `search.done` | `requestId`、`results`、`abstract`、`fromCache`、`cachedAt`、`elapsedMs` | `requestId` 与当前轮次不一致时丢弃，避免迟到消息覆盖新结果 |
| `search.error` | `kind`、`status`、`message` | 写入 `searchState` 的 `error` 字段 |
| `component.install` | `jobId` 等 | 触发一次权威状态读取，推送只负责及时性 |

推送的定位是旁路通知：`push.js` 不保存权威数据，安装进度、控制台输出与搜索结果的最终状态由同步桥的 `InstallStatus`、`Poll` 等方法提供。推送丢失只会让界面晚一拍更新。

历史主题 `ai.http`、`ai.raw`、`ai.rawEnd`、`ai.rawError`、`ai.test` 在宿主侧已无生产者；AI 输出改为页面直连后不再经过推送。核对命令：

```powershell
Select-String -Path MFMath.Host.Rust/src/*.rs -Pattern 'ai\.http|ai\.raw'
```

### 3.8 新增主题的步骤

1. 宿主侧在产生事件的函数中调用 `crate::push::send("<topic>", &payload)`，`payload` 是用 `serde_json` 序列化出的合法 JSON 文本，无负载时传空串。
2. 页面侧在 `push.js` 的订阅方或对应模块的 `onPush` 中处理该主题，按主题名精确匹配或按前缀过滤。
3. 补一条端到端断言。推送失败不报错，只有断言能发现主题不再到达。

## 4. 验收

| 手段 | 覆盖 | 命令或入口 |
| --- | --- | --- |
| `--selftest-jobs` | 任务通道的派发、串行、轮询、完成、两种取消；无需 WebView2 | `& MFMath.Host.Rust/target/debug/mfmath-host-rust.exe --selftest-jobs`，期望末行 `RESULT\|selftest-jobs\|PASS\|5` |
| `cdp-push.mjs` | 信封四项齐全、`seq` 单调、`component.install`、`console.run`、`settings.test` 往返、无丢消息 | `node MF_UI/MFMath.UI.Vue/tests/cdp-push.mjs` |
| `cdp-console.mjs` / `cdp-search.mjs` / `cdp-account.mjs` | 分别覆盖 `console.run`、`search.*`、`account.changed` | 同目录下的 CDP 用例，需已启动宿主页面 |
| 设置 → 引擎组 | 页面侧 `push.Info()` 与计数、`settings.test` 往返 | 界面按钮，发出后页面计数加一 |
| `mf.JobStats()` | 任务通道残留检查：`pending` 与 `running` 应回到 0 与 `null` | 页面控制台或诊断入口 |

[`ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md) 给出宿主的可复现验收步骤与期望值。
