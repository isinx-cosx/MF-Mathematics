# 宿主谱系与迁移现状

> **本文只回答一个问题：有哪几个宿主、谁是现役、换过去时什么会跟着走、什么不会。**
>
> 契约见 [README.md](README.md)；凭据的可移植性见 [CREDENTIALS.md](CREDENTIALS.md) §3。
> 迁移过程的历史记录在 [`LINK-LAYER.md`](../../MFMath.Host.Rust/docs/LINK-LAYER.md)（那是工作日志）。

**核对时间**：2026-10-07
**权威源**：`MFMath.Host.Rust/src/main.rs`（URL / 数据目录 / 启动日志）、`AGENTS.md` §2（所有权）

---

## 0. 现状一句话

| 宿主 | 路径 | 状态 |
| --- | --- | --- |
| **Rust / Tauri + WebView2** | `MFMath.Host.Rust/` | ✅ **现役**（唯一的）。9 个宿主对象 / 84 个方法 |
| C# / WPF + WebView2 | `MFMath.Host/` | 🚩 **已废弃**（2026-10-07 项目所有者决定）。**可以读、不要改** |

**"两个宿主并存 / 可来回切换"这个前提已经不成立。** 见到这种说法就是过时文档 ——
`LINK-LAYER.md` §9 的标题与 `MFMath.Host.Rust/README.md`、`LINK-LAYER.md:191/640` 都还留着旧口径，
属 [PROJECT-BOARD.md](../PROJECT-BOARD.md) §3 **R7** 已登记的文档债。

---

## 1. 页面 URL 是契约的一部分：`https://mfmath.local/index.html`

宿主用 WebView2 的虚拟主机映射把 `wwwroot` 挂到 `mfmath.local`，而不是让 Tauri 把前端**嵌进 exe**
（`frontendDist`）。**这不是风格选择**，三条理由（`main.rs:244-256`）：

1. **48 个 CDP 用例**按 URL 正则 `/mfmath\.local|index\.html/` 找页面（例：
   `tests/cdp-bridge-verify.mjs:8`）。URL 变了，整张回归网一起废；
2. **"改了前端只要重拷 `dist`"这条工作流**以它为准（不必重新编译 exe）；
3. 嵌进 exe 的话 URL 会变成 `http://tauri.localhost/` —— 与上面两条都冲突。

**嵌进去的资产仍然保留，只当兜底**：没有 `wwwroot` 时（例如直接 `cargo run` 没同步过 UI）仍能起来。

### 1.1 UI 目录的两个开关

| 环境变量 | 作用 | 默认 |
| --- | --- | --- |
| `MF_WWWROOT` | 指到别处的 `wwwroot` | exe 同目录的 `wwwroot` |
| `MF_WEBVIEW2_DIR` | WebView2 用户数据目录（**与 C# 宿主同名开关**） | `%LOCALAPPDATA%\MFMath\webview2` |
| `MF_HOST_EXE` | （`run-all.ps1` 侧）指定被测宿主 exe | 见 §4 的待办 |

`MF_WEBVIEW2_DIR` 的用途是"**多个宿主实例不能共用同一数据目录**"。遇到这个错误码时有明确提示：

> `0x800700AA`（请求的资源在使用中）—— 多半是**另一个宿主实例正占着同一个 WebView2 数据目录**。
> 关掉另一个实例，或用 `MF_WEBVIEW2_DIR` 指到别的目录再试。（`main.rs:268-273`）

---

## 2. 启动与失败可观测性（GUI 子系统的坑）

宿主是 **GUI 子系统**，双击运行时 **stdout 不连终端** —— 所以启动信息**不能只靠 `println!`**
（重定向时 stderr 仍可见），必须**同时写 stderr 与 `app.log`**（`main.rs:218-223` 的 `note()`）。

WebView2 起不来时走 `fail_with_reason()`：**日志 + 崩溃文件 + 一个不阻塞过久的提示框**。
为什么不能让它落到 Tauri 的 panic：用户只会觉得"**点了没反应**"，而日志里一行都没有
（C# 宿主曾修过同一个问题，commit `7bc5632`）。

**启动日志里会逐个打印对象与方法数** —— 这是本套文档里方法表的**交叉验证源**：

```
[rust-host] Tauri WebView2 就绪；宿主对象 9 个（含 diag）；CDP 端口 9222
```

---

## 3. 换宿主时，什么跟着走、什么不跟着走

| 数据 | 跟着走？ | 说明 |
| --- | --- | --- |
| `search.json`（含 Wolfram App ID） | ✅ | 字段同名、格式相同 |
| `account.json`（token） | ✅ | 同上；都是 DPAPI 密文，且**熵一致**（都不传 optional entropy） |
| `update.json`、窗口 / 工作区 / 历史 | ✅ | 同上 |
| **`ai.json` 的密钥** | ❌ | C# 写 `apiKeyProtected`（DPAPI 密文）↔ Rust/TS 读 `apiKey`（明文），**两种形式互不通用** |

**可移植性是怎么做到的**：Rust 侧给每个字段加了 **PascalCase `alias`**，对齐 C# 的
`PropertyNameCaseInsensitive` 反序列化行为。**唯一不通用的那一项**是 AI 架构变更（D-004）的直接后果：
老用户只会被要求**重填一次密钥**，其余不用动 —— 且 `hasKey=false`，**不假装还有密钥**。

---

## 4. 废弃之后剩下的收尾（三件）

| # | 事项 | 归属 | 说明 |
| --- | --- | --- | --- |
| 1 | **文档债（R7，8 处）** | C 面 / 各面自查 | `docs/` 下多份文档仍把 C# 宿主写成**现役实现**，其中 `AI-ASSISTANT.md` 描述的是一个**已经不存在的** AI 桥 |
| 2 | **`run-all.ps1` 的默认宿主仍指向 C# 宿主** | **B 面** | `tests/run-all.ps1:26` 的默认候选是 `MFMath.Host\bin\Release\net10.0-windows\MFMath.exe`。C# 既已废弃，默认值就该改指 Rust 宿主 —— 否则每次跑批都可能对着**废弃产物**（实测那份 `wwwroot` 停在 03:45）。可用 `MF_HOST_EXE` 覆盖，是当前的实际用法 |
| 3 | `MFMath.Host/` 里已闲置的 `AiBridge/AiRelay/AiClient/AiConfig`（864 行） | 不动 | 随项目一起**冻结**，不必单独删（`LINK-LAYER.md` §9.3） |

### 4.1 一处**两份文档说法不一致**的地方（如实记下，不替你选边）

前端 `lib/bridge.js` 里留着一条 Tauri 探测链：`tauriInvoke()`（`:459`）→ `tauriHostCall()`
（`:469`）→ 被 `callWin()`（`:493`）与 `winIsMaximized()`（`:517`）**当兜底**用。

| 出处 | 说法 |
| --- | --- |
| `LINK-LAYER.md` §9.3 第 2 条 | "它实际**永不成功**；**删它属于 B 面**，要动先跟管理者打招呼" |
| `main.rs:507-514`（Rust 侧代码注释） | 三条 Tauri 命令（`call`/`host_info`/`front_log`）**已随 `commands.rs` 一起删掉**，理由是实测的：从 `mfmath.local` 这个 origin 调 `invoke` 会被 Tauri 拒（`call not allowed. Plugin not found`），**永远不会成功**；而且 `Dispatch` 必须同步返回，`invoke` 只有 Promise，救不了 `mf`。**但**"前端 `tauriInvoke()` 探测**保持原样**：它在 C# 宿主下本来就返回 null，**留着无害**（那是两个宿主共用的那一层）" |

**所以两条说法并不冲突到需要谁认错**：功能上它确实永远不会成功（Rust 侧确认）；
它是**有意的兜底分支**（只在 `winBridge()` 为 null 时才走到 —— 即"没有 `wwwroot`、页面退回
`tauri.localhost`"那个假设场景），Rust 侧明确表示保留。

**判断留给 B 面**：删是清理，留是兜底。**只要动，就要在提交信息里写明理由**
（[AGENTS.md](../../AGENTS.md) §2 的跨面规矩）。

---

## 5. 怎么验宿主（判据不在本文）

宿主侧的验收步骤与基线**有专门文档，不在本文重复**：

- [`MFMath.Host.Rust/docs/ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md) —— 构建配方、
  9 个宿主对象的期望方法数、26 组用例、已知易抖项、真机清单；
- [`MFMath.Host.Rust/docs/PACKAGING.md`](../../MFMath.Host.Rust/docs/PACKAGING.md) —— 出包与
  **尚未真机验证的部分**（"安装 → 启动"这条路）；
- [`PROJECT-BOARD.md`](../PROJECT-BOARD.md) §2 —— 各面的验收命令速查。

**一条最容易踩的**：Rust 宿主必须**跑在工作区之外**（工作区内的进程写不了 `%LOCALAPPDATA%`，
日志与设置会静默失败）。见 `ACCEPTANCE.md` §0.2。
