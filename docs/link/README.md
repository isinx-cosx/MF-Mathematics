# 链接层：那条缝是什么

> **本文只回答一个问题：前端与宿主之间的接缝由什么构成、契约是什么。**
>
> 与同层其它文档的分工：[OBJECTS.md](OBJECTS.md) 给**方法清单**（9 对象 × 84 方法）；
> [JOBS-PUSH.md](JOBS-PUSH.md) 讲**异步与下行**两条通道；[CREDENTIALS.md](CREDENTIALS.md) 讲**凭据边界**；
> [FEATURES.md](FEATURES.md) 讲**各功能怎么落在这条缝上**；[HOSTS.md](HOSTS.md) 讲**宿主谱系**。
> 迁移过程与历史决策见 [`LINK-LAYER.md`](../../MFMath.Host.Rust/docs/LINK-LAYER.md)（那是**工作日志**，不是手册）。

**核对时间**：2026-10-07 · **权威源**：`MFMath.Host.Rust/src/main.rs`、`handlers.rs`、`hostobject.rs`

---

## 1. 链接层是三层里的哪一层

| 层 | 位置 | 对外面 |
| --- | --- | --- |
| 引擎 | `MF_Mathematics/`（C++） | 只有两个 C ABI：`math_call(name, args_json, out, size)` / `function_exists(name)`；**424** 个 action |
| **宿主** | `MFMath.Host.Rust/`（Rust/Tauri + WebView2，**现役**） | 窗口 + WebView + **9 个宿主对象 / 84 个方法** |
| 前端 | `MF_UI/MFMath.UI.Vue/`（Vue 外壳 + React 绘图页） | 界面、路由、教程、AI、控制台 |

**链接层 = 中间那一列与前端 `src/lib/**` 之间的那条缝。** 它是"换宿主"时唯一不能靠改配置绕过去的东西：
编程语言换了、框架换了，但**这条缝的形状必须一模一样**，否则 48 个端到端用例与整个前端一起废。

---

## 2. 接缝的技术形态：`AddHostObjectToScript`，**不是** `invoke`

这是本节最重要的一句话，也是**最容易被搞错**的一点：

```
页面调用   window.chrome.webview.hostObjects.sync.mf.Dispatch("solve", "{}")
                    ↑                 ↑        ↑
                  WebView2          sync    宿主对象名（PascalCase 方法名）
```

- 宿主侧落点是 `ICoreWebView2::AddHostObjectToScript`（`hostobject.rs` 的 `register()`）：
  把宿主对象做成一个实现了 `IDispatch` 的 COM 对象注册给 WebView2；
- **不是** Tauri 的 `invoke()`（那是 Tauri 命令层，与 WebView2 无关）。

**为什么必须是 COM。** `invoke()` 只返回 Promise，而 JS 在主线程上**没有任何办法**阻塞等一个 Promise。
WebView 里真正能**同步**取值的通道只有两条：**COM 宿主对象**与**同步 XHR**。
这个项目选了前者 —— 于是"换 Tauri"这件事**没有**动到这条缝。

### 2.1 一个通用 dispacher 服务 9 个桥

`hostobject.rs` 只写一次 COM 那一层；对象名与方法表在 `main.rs` 的 `HOST_OBJECTS` 里声明；
`(对象, 方法) → 处理函数` 的映射在 `handlers.rs:86-96` 的 `match` 里。

> **加一个桥 = `main.rs` 加一行 + `handlers.rs` 加一个分支**（`main.rs:204-205` 的原话）。
> COM 层一行都不用动 —— 这是这套设计的全部价值。

---

## 3. 三条契约（逐字对齐，违反一条就出故障）

### ① 成员名 **PascalCase、大小写敏感**

写 `mf.dispatch` **不是**返回 `undefined`，而是**抛 `0x80070057`**（`E_INVALIDARG` / `DISP_E_*` 一族的
HRESULT 会冒到 JS 侧变成异常）。

> 这个故障在本仓库**排查过两次**，原话留在 `src/lib/diagnostics/errors.js:62-67`。
> 所以前端访问宿主对象时一律**先判存在再判可调用** —— 只判 `hostObjects.sync` 存在会误判成
> "有对象"，因为它可能只是个"看着像对象"的东西（`bridge.js:456`）。

### ② 返回值**一律是字符串**，前端统一 `JSON.parse`

宿主侧回的**是文本，不是对象**。所以：

- `Ret::Str` → JSON 文本或**裸字符串**（有几个例外，见 §4）；
- `Ret::Bool` → 真布尔（只有少数方法）；
- `Ret::Empty` → 无返回。

### ③ 错误**也走信封**

```json
{ "isError": true, "value": "原因" }
```

Rust 侧是 `handlers.rs:41` 的 `err_envelope()`，与（已废弃的）C# `MathBridge.Dispatch` **逐字一致** ——
**目的就是让前端 `parse()` 那一层不用区分是谁在回话**。

---

## 4. 返回形状的例外（写代码前必须知道）

规则是"一律 JSON 字符串"，但下面这几处**刻意**不是：

| 方法 | 返回 |
| --- | --- |
| `con.Install(name)` | **裸 id 字符串**，例如 `"job3"` —— 前端写的是 `String(c.Install(name))` |
| `con.Start(language, code, stdin)` | **裸 id 字符串**，例如 `"run4"` |
| `mf.Ready()` / `mf.FunctionExists(name)` | 真布尔 |
| `win.*` 的窗口操作、`update.CancelAll()`、`account.CancelAll()` | 无返回（`Ret::Empty`） |

`main.rs:189-190` 为此专门留了警告：`Install` / `Start` 的返回**不是 JSON**，用例也按裸字符串用。

---

## 5. 为什么"同步"是硬需求（不是历史包袱）

同步桥用在**热循环**里，这一点决定了接缝不能改成 Promise：

| 调用点 | 形状 |
| --- | --- |
| `MFMath.UI.React/src/plot/usePlotSampling.ts:36-42` `batchEval()` | **每条曲线一次**同步 `engineCall("expr_eval_vars_batch", …)`，在自适应采样循环里 |
| `PlotPage.tsx:173 / 208 / 224 / 331` | 交点、局部极值、符号驻点、参数点求值，全同步 |
| `Plot3DPage.tsx:118`、`PlotVectorPage.tsx:124-125`、`PlotComplexPage.tsx:141/162` | 曲面 / 向量场 / 复平面网格，一次同步大批量 |
| `src/lib/engine/asyncPolicy.js:12-16` | 原话：「绘图页里"每条曲线一次"的采样/极值标记**保持同步**：那些是毫秒级，而且一条曲线一个 `await` 会把采样时序拆碎，得不偿失」 |

**所以这个项目的分工是**：

- **毫秒级的活** → 同步桥（`mf.Dispatch`），包括热循环；
- **可能跑分钟级的活** → 异步 job 通道（`DispatchJob` / `PollJob` / `CancelJob` / `JobStats`），见 [JOBS-PUSH.md](JOBS-PUSH.md)；
- **判据是"规模"而不是"重不重"**，阈值写在 `src/lib/engine/asyncPolicy.js`（`complex_grid` / `expr_eval_grid` 是 `2.5e5`）。

---

## 6. 两条通道（别只记住一半）

链接层是**双向**的，很多人只记住同步桥那一半：

| 方向 | 机制 | 语义 |
| --- | --- | --- |
| 页面 → 宿主（**同步、一问一答**） | `hostObjects.sync.<对象>.<方法>(…)` | 权威数据在这里 |
| 页面 → 宿主（**异步、轮询**） | `DispatchJob` 拿 `jobId` → 每 **120 ms** `PollJob` | 只给"重活"用 |
| 宿主 → 页面（**推送、旁路**） | `PostWebMessageAsJson`，信封 `{topic, seq, ts, payload}` | **只负责"及时"**，权威数据仍在同步桥上 |

> **推送是旁路。** 这句话是设计约束，不是描述：丢一条推送不影响正确性，只影响及时性 ——
> 所以推送失败**绝不抛给调用方**（`push.rs:48`）。细节见 [JOBS-PUSH.md](JOBS-PUSH.md)。

---

## 7. 怎么加一个宿主对象（操作步骤）

1. `main.rs`：写一个 `const XXX_SPEC: &[MethodSpec] = &[ … ]`，**参数一律 VT_BSTR**，
   返回类型取 `RetKind::{Str, Bool, Empty}`；
2. `main.rs`：在 `HOST_OBJECTS` 里加一行 `("xxx", XXX_SPEC)`；
3. `handlers.rs:86-96`：在 `match` 里加一个分支 `"xxx" => xxx(method, args)`；
4. `handlers.rs`：写该分支的 `match method { … }`；
5. **`hostobject.rs` 一行都不用改。**

> ⚠ 两份表必须**同步**：`MethodSpec` 表里有、`handlers.rs` 里没有的方法，
> 调用时会拿到"没有这个方法"的错误信封（`main.rs:61-62` 写明）。
> 这是刻意的失败方式 —— **报错，不是静默**。

### 7.1 命名上的一个真陷阱（`con`）

**模块文件叫 `console.rs`，但注册的对象名必须是 `con`。** 原因不是命名偏好：
Windows 把 `con` 当**保留设备名**，`src/con.rs` 这种文件**git 索引不了** ——
`git add` 直接报 `open("src/con.rs"): No such file or directory`，**而文件明明在磁盘上**。
留着它就等于这个桥永远进不了版本库（`main.rs:180-184`）。

---

## 8. 权威源与已知的过时数字

**碰到冲突时按这个顺序取信**：

1. **代码**：`main.rs` 的 `HOST_OBJECTS` / `*_SPEC`（方法表）、`handlers.rs` 的 `match`（实现面）；
2. **启动日志**：宿主启动时会逐个打印对象与方法数（`ACCEPTANCE.md` §2 的基线就是这么来的）；
3. **本文档**；
4. [`LINK-LAYER.md`](../../MFMath.Host.Rust/docs/LINK-LAYER.md)：**历史与迁移日志**，
   里面的数据在写作时刻是实测的，但**不保证当前仍成立**。

> ⚠ 已知 `LINK-LAYER.md` 有两处**计数过时**（内容仍然有效，只是数字没跟上）：
> §1.3 的标题写"**十个**宿主对象"（现在是 **9** 个，`ai` 已刻意移除）；
> §2.2 写"**47** 个 CDP 用例"（现在是 **48** 个）。
> 这两处属于 A 面文件的收尾，[PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 R7 已按同类问题登记。
