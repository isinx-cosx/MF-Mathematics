# 异步任务通道与下行推送

> **本文只回答一个问题：那些"不能同步等"的活怎么跑，宿主怎么主动通知页面。**
>
> 契约与接缝见 [README.md](README.md)；方法清单见 [OBJECTS.md](OBJECTS.md)。

**核对时间**：2026-10-07
**权威源**：`MFMath.Host.Rust/src/jobs.rs`、`push.rs`、`handlers.rs:329-343`；前端 `src/lib/bridge.js:160-235`、`src/lib/push.js`

---

## 0. 一句话

链接层有**两条不对称的通道**，各修一半问题：

| 通道 | 修的是 | 代价 |
| --- | --- | --- |
| **job 通道**（`DispatchJob`/`PollJob`/`CancelJob`） | 同步 `Dispatch` 会把 WebView2 的 UI 线程**占住** | 页面要轮询；**取消是假的**（见 §2） |
| **推送通道**（`push` + `PostWebMessageAsJson`） | 宿主"主动说话"只能靠轮询 —— 延迟固定、空转浪费 | 旁路：会丢，所以**权威数据仍在同步桥上** |

---

## 1. 为什么需要 job 通道

同步的 `mf.Dispatch` 会占住 WebView2 的 UI 线程，而引擎里确实有能跑到**分钟级**的动作
（`jobs.rs` 模块注释列举的四个来源）：

| 动作 | 规模 |
| --- | --- |
| `mandelbrot`（分形） | 分辨率 ≤1000 × 迭代 ≤1024 ≈ **1e9 次迭代** |
| `complex_grid`（复平面） | 分辨率 ≤1000 → **1e6 点** |
| `expr_eval_grid`（3D / 向量场 / 工具箱） | 2000×2000 = **4e6 点** |
| `factor_integer` / `integrate_double` / `taylor_series` 等符号运算 | **没有上界** |

同步跑它们的症状是"**窗口白屏 + 系统判定未响应**"。

---

## 2. 设计：一个常驻工作线程 + 队列，**串行**执行

- `DispatchJob` **入队即返回** `jobId` → 界面立刻拿到，不再阻塞；界面用 `PollJob` 轮询；
- 任务状态：`queued | running | done | error | canceled`；
- 返回值 `result` 是**引擎信封原文** `{"isError":…,"value":…}`，前端按原样解析。

### 2.1 为什么是"串行"而不是并发（这不是偷懒）

`jobs.rs` 给的理由值得逐字记住：

> 引擎里除 `numerical/numerical_integration.cpp` 的一个 `thread_local` 外**没有任何同步原语**，
> `math_call` 无锁（`api.cpp` 就是 dispatch + memcpy）；并发调用会踩 FLINT/SymEngine 的
> **全局缓存**，而这件事**没人验证过**。一次只跑一个重活也够用。

> 📌 这条是"**没验证过就不做**"的正面例子 —— 与 [DESIGN.md](../DESIGN.md) §2 ② 同一条纪律。
> 反过来讲：如果哪天要开并发，**先验证 FLINT/SymEngine 的全局缓存是否线程安全**，别靠猜。

### 2.2 ⚠ `CancelJob` 的语义：**停止等待，不是停止计算**

引擎**没有取消钩子**，工作线程会把这一步算完。所以：

- 宿主侧只能做到"停止等待 + **丢弃结果**"（结果回来了也不再交付）；
- **界面文案必须是"已取消等待"，不能写"已停止"** —— `jobs.rs` 与 `bridge.js:155-157` 各写了一遍。
  前端现在的实际文案是：`已取消等待（引擎会把这一步算完后丢弃结果）`；
- 要做到"真停"，只能靠**进程边界**：把执行器换成 worker 子进程 + 杀进程
  （**引擎同样一行不用改**）。那是下一步，不是现在。

### 2.3 ⚠ 由此产生的一个真实事故（跑批时必须知道）

**中途杀掉套件会在宿主里留下一支没跑完的后台任务。** 那支任务占着引擎，之后页面上
**任何同步 engine 调用都会永久阻塞** → 渲染进程卡死，连 `location.hash` 这种纯 DOM 读取都会超时。
`MF_UI/BUGS.md` §0.2 记录过一次实测：**卡了 30+ 分钟**，重启宿主才恢复。

> **所以：跑长用例（尤其 `cdp-engine-coverage`）时不要中途 Ctrl-C；要中断就先停宿主。**
> 这条与 [DECISIONS.md](../DECISIONS.md) D-010（跑批前独占宿主）是同一族风险。

---

## 3. 前端怎么用（`lib/bridge.js`）

```
engineCall(name, args)              同步 —— 毫秒级的活走它（含绘图热循环）
engineCallAsync(name, args, opts)   异步 —— 可能重的活走它
```

`engineCallAsync` 的三条行为必须知道：

1. **自动退回同步**：`typeof mf.DispatchJob !== "function"` 时直接走同步
   （`bridge.js:165`）—— 兼容"宿主还没有 job 通道"的旧桥；
   `DispatchJob` **抛异常**时也退回同步（"至少能用"）；
2. **轮询间隔 120 ms**（`POLL_MS`），终态是 `done` / `error`；
3. **`opts.signal`（`AbortSignal`）**：触发时调 `CancelJob`，并按 §2.2 的语义交回
   `{isError:true, canceled:true}`。

**谁决定走哪条**：`src/lib/engine/asyncPolicy.js` —— 判据是**规模**，不是"感觉重"。
`complex_grid` / `expr_eval_grid` 的阈值是 `2.5e5`（`asyncPolicy.js:29-30`），
另有 `ALWAYS_ASYNC` 集合（`asyncPolicy.js:39`）装着"没有上界"的符号运算。

> ⚠ 反向约束：**绘图页"每条曲线一次"的采样刻意保持同步**（`asyncPolicy.js:12-16`），
> 一条曲线一个 `await` 会把采样时序拆碎。**如果哪天把那些网格的上界调大，必须同时改回异步。**

---

## 4. 推送通道：为什么绕这么大一圈

**它修的问题**：在它之前，宿主与界面之间只有"页面发起、一问一答"的同步桥与轮询两种办法；
**宿主主动说话**（安装进度、控制台跑完、搜索结束）只能靠轮询 —— 延迟固定、空转浪费。

**机制**：WebView2 的原生 `PostWebMessageAsJson`，页面侧收在 `chrome.webview` 的 `message`
事件上（`src/lib/push.js`）。**前端一行都不用改** —— 这条路挂在 WebView2 上，不挂在框架上，
所以换宿主时原样保留。

### 4.1 信封与三条约束

```json
{ "topic": "console.run", "seq": 42, "ts": 1730000000000, "payload": { … } }
```

| 约束 | 内容 |
| --- | --- |
| ① | **只在 UI 线程碰 WebView2**（由"worker 排队回主线程"保证） |
| ② | **推送失败绝不抛给调用方**：页面在导航、窗口在关闭都会失败，只记计数与最后一条错误 |
| ③ | **信封固定，`seq` 单调递增** —— **页面靠它发现丢消息** |

### 4.2 四个坑（都实测过，第四个花的代价最大）

| # | 坑 | 现象 / 结论 |
| --- | --- | --- |
| ① | **不能在同步宿主对象回调里直接 post** | 调用期间浏览器正阻塞等 `Invoke` 返回，此时调 `PostWebMessageAsJson` 就是**重入等待** → `Emit` 永不返回、页面失去响应，**stderr 与崩溃日志里一条都没有** |
| ② | **`run_on_main_thread` 在主线程上调用等于没推迟** | tauri-runtime-wry 的 `send_user_message` 有"当前就是主线程 → 就地执行"的优化，所以当场就把闭包跑了 —— **还是重入**。**从别的线程调**才会真正排队 |
| ③ | **也不能换个线程直接调 WebView2** | `ICoreWebView2` 既不是 agile、也没注册 proxy/stub：编组直接失败（实测 `REGDB_E_IIDNOTREG 0x80040155`），拿裸指针跨线程调则是 UB —— **实测宿主当场消失**。也试过 `SetTimer(1ms)`：定时器挂上了、`SetTimer` 返回非 0，但回调**一次都没被调用** |
| ④ | **别把 `ICoreWebView2` 存成裸指针** | 那个接口取自 `with_webview` 闭包，**闭包一结束引用就被 Release**，只留一个 `usize` 再用就是**悬垂指针**。症状与 ①/③ **一模一样**（页面卡死或宿主静默消失，stderr / 崩溃日志 / WER 转储里一条都没有）。`CoreHandle` 会 AddRef 一份并持有到进程结束 |

**正确的路径**（`push.rs:41-44`）：

```
worker 线程 ──send（只塞 channel，立刻返回，永不阻塞）──▶ 常驻 worker
                                                        │
                                          run_on_main_thread（从 worker 调才是真排队）
                                                        ▼
                                                主线程执行 post（CoreHandle 持有接口）
```

### 4.3 主题清单（Rust 侧生产者）

| 主题 | 生产者 | 页面订阅者 | 用途 |
| --- | --- | --- | --- |
| `component.install` | `console.rs:363` | 设置 → 组件 | 安装进度 |
| `console.run` | `console.rs:1162` | 控制台页 | 运行输出 / 结束 |
| `search.done` | `search.rs:1458` | `lib/search/bridge.js`（按 `search.` 前缀分发） | 搜索成功 |
| `search.error` | `search.rs:1469` | 同上 | 搜索失败（带错误分类） |
| `account.changed` | `account.rs:221` | `lib/account/bridge.js` | 登录态变化 |
| `settings.test` | **页面自己**经 `push.Emit` 发，宿主回推 | 设置 → 引擎组 | **往返自检**：验证推送这条路是通的 |

> ⚠ 历史主题 `ai.http` / `ai.raw` / `ai.rawEnd` / `ai.rawError` / `ai.test` **已不存在** ——
> AI 改成页面直连后，字节由 `fetch` 的 `response.body` 直接读，不再经推送
> （见 [DECISIONS.md](../DECISIONS.md) D-004）。**见到它们就是过时文档。**

### 4.4 加一个主题的步骤

1. 宿主侧：`crate::push::send("<topic>", &payload_json)`（`payload_json` 必须是**合法 JSON 文本**，
   空串 = 没有负载）；
2. 页面侧：在 `src/lib/push.js` 的分发里加一个分支（**按主题前缀**分发是既有做法，
   `search.` 就是这么做的）；
3. **补一条端到端断言** —— 推送是旁路，丢了不会报错，所以**没有断言就等于没有**。
   `settings.test` 那条往返自检就是为此存在的。

---

## 5. 验收

| 手段 | 覆盖 |
| --- | --- |
| `mfmath-host-rust.exe --selftest-jobs` | job 通道的并发与取消，期望 **5/5**（无头，不起窗口） |
| `cdp-console` / `cdp-search` / `cdp-account` | 分别覆盖 `console.run` / `search.*` / `account.changed` 主题 |
| 设置 → 引擎组 | `settings.test` 往返自检（页面 → `Emit` → 宿主 → 回推） |
| `mf.JobStats()` | 任务通道自检；页面侧可用它确认"没留下孤儿任务" |
