# 项目管理板（Project Board）

> **本文只回答一个问题：现在谁在做什么、到哪一步了、有什么风险。**
>
> 与其它文档的分工：
> - [`AGENTS.md`](../AGENTS.md) —— 并行干活的**规约**（所有权、提交、互斥、证据）；
> - [`docs/OPEN-ITEMS.md`](OPEN-ITEMS.md) —— 还有什么**功能**没实现（待办）；
> - [`MF_UI/BUGS.md`](../MF_UI/BUGS.md) —— 前端确有**证据**的缺陷；
> - [`docs/STATUS-and-ROADMAP.md`](STATUS-and-ROADMAP.md) —— 全局状态与路线图；
> - **本文** —— 工作面进度、风险台账、待拍板项。
>
> **维护规矩**（与 `OPEN-ITEMS.md`、`BUGS.md` 同一套）：状态**带时间戳**，
> 结论**带证据**（命令 / 文件:行 / 日志），消掉的风险**删掉**，不留装饰。

**快照时间**：2026-10-07 10:00（本机，`master`）
**维护者**：项目管理者

---

## 1. 一句话状态

**代码在快速推进，文档在追赶，git 有 56 个提交没推（决定先不推）。**

本轮管理的两件实事：

1. **R1（最要紧）** —— 最新一次端到端与 `MF_UI/BUGS.md` 的"全绿"表述**互相矛盾**，
   必须先澄清再定稿，否则"全绿"会变成没人信的话（§3 R1 给了带 mtime 的时间线）；
2. **R7** —— 所有者拍下"**.NET 宿主已废弃**"之后，暴露出**多份文档仍把它写成现役实现**
   （含一份描述着**已不存在**的 AI 桥）。已在 `AGENTS.md` 与 `README.md` 落地口径，
   清单与改动顺序见 §3 R7。

---

## 2. 三个工作面（按 git 证据划分）

划分依据是 `git log` 的 scope 前缀与实际改动路径，不是猜测：

| 面 | 管辖路径 | 最近一次提交 | 依据 |
| --- | --- | --- | --- |
| **A · Rust 宿主** | `MFMath.Host.Rust/**` | `30b7586`（2026-10-07，`docs(host-rust)`） | 最近 12 个提交里有 7 个是 `host-rust`；19 个 `src/*.rs`，今日 06:42–09:57 连续改动 |
| **B · 前端** | `MF_UI/MFMath.UI.Vue/**`、`MF_UI/MFMath.UI.React/**`、`MF_UI/BUGS.md` | `b6a77c0`（2026-10-07，`docs(ui)`） | `fix(plot)` / `feat(ui)` / `chore(ui,tests,docs)` 三个提交；今日 08:54–09:56 连续改动 |
| **C · 引擎 / 全局文档** | `MF_Mathematics/**`、`docs/**`、`README.md`、`AGENTS.md` | `37ac02b`（2026-10-07，`fix(engine)`，改动实际落在前端参数层） | 引擎侧今日**无**提交证据；`docs/` 最近一次是 10-06 |

**废弃资产（不属于任何一面）**：`MFMath.Host/`（C#/.NET 宿主）—— 见 §4 D1。
只读作迁移参考，**不接受功能改动**。

> ✅ **D1 已答（2026-10-07，项目所有者原话：".NET 是废弃的东西"）** —— 因此 `MFMath.Host/`
> **不再是 C 面的一部分**，降为"废弃资产"（只读作迁移参考，不接受功能改动）。
>
> 仍待确认的是 **第三个 Agent 具体做哪一块**：当前提交证据只覆盖 A（Rust 宿主）与 B（前端）。
> 若第三条线就是"引擎 + 全局文档"，那它今天还没有提交；若是别的（站点仓库 / 安装包 / 教程资产），
> 告诉我路径，我改"管辖路径"这一列。

**各面的验收口径**写在 [`AGENTS.md`](../AGENTS.md) §2；下面是**本机当前可用的判据**：

| 面 | 命令 | 期望 |
| --- | --- | --- |
| A | `cargo build --message-format short` | `Finished`，warning = 0 |
| A | `mfmath-host-rust.exe --selftest-jobs` / `--selftest-common` | **5/5** / **10/0**（`ACCEPTANCE.md` §1） |
| A | 启动日志的宿主对象表 | **9 个**（`mf`16 `win`9 `sys`8 `diag`1 `push`3 `update`6 `account`19 `search`12 `con`10），**`ai` 刻意不在其中** |
| B | `npm run check`（Vue） | exit 0（types + 引擎签名 + UI 自检） |
| B | `npm run check:types`（React） | exit 0 |
| B | `tests/run-all.ps1 -NoLaunch` | 47 个 `cdp-*` 全部登记，无 `no RESULT line` |
| C | `ctest --test-dir MF_Mathematics/build -C Release` | 16/16 套件 |
| C | `probe_call.exe list_functions '{}'` | `count` = **424**（WHOLEARCHIVE 守门） |

---

## 3. 风险台账

### R1【高】最新一次端到端与 `BUGS.md` 的"全绿"表述矛盾 —— **必须先澄清**

**证据（两侧都是本机实测）**：

| 套件 | `MF_UI/BUGS.md` §0.2 声称（09:48 写入） | 最新日志实测（09:50–09:59） |
| --- | --- | --- |
| cdp-plot-accuracy | ✅ 14/0 | **`no RESULT line, exit=1`** |
| cdp-appearance | ✅ 33 | **32 / 1 fail** |
| cdp-font-load | ✅ 18 | **6 / 12 fail** |
| cdp-plot-p5 | ✅ 12 | **11 / 1 fail** |
| cdp-plot-asymptote | ✅ 7 | **6 / 1 fail** |
| cdp-plot-fractal | ✅ 14 | **9 / 5 fail** |

- 日志：`MFMath.Host.Rust/target/run-all-0950.log`（76 行，**未跑完** —— 停在 `cdp-canvas-theme`，
  后面的 `cdp-console` / `cdp-modes-render` / `cdp-ai` / `cdp-account` / `cdp-update` / `cdp-search` / `cdp-push` / `cdp-settings` **一条都没跑到**）
- 当时没有 node 进程在跑、日志 09:59:19 后不再增长 → 那次跑批是**被中断或提前结束**的。

**时间线（都是文件 mtime，可自行复核）**：

| 时刻 | 事件 |
| --- | --- |
| 03:45:05 | .NET 宿主的 `wwwroot` 最后一次同步（即：**对着 .NET 宿主跑的话，用的是 6 小时前的产物**） |
| 09:44:06 | `MF_UI/MFMath.UI.Vue/dist` 全量重建（`assets/*` 同一时刻） |
| 09:48:49 | `MF_UI/BUGS.md` 写入"全绿"表格（**在下面那次跑批之前**） |
| **09:50:15** | 那次 e2e 起宿主（`msedgewebview2` 进程起始时间） |
| 09:52:01 | `tests/cdp-plot-accuracy.mjs` 被改动 —— **跑批进行中**，所以它跑的是**改动前**的版本 |
| 09:55:20 | 新增 `tests/cdp-plot-workspace.mjs` |
| 09:55:39 | `tests/run-all.ps1` 登记该用例 |
| 09:59:19 | 日志最后一次增长，随后停止（无 node 进程） |

**我的判断（未定案，需 B 面复跑确认）**：失败特征集中在
**"字体传输量 0 KB"、"KaTeX 一个字都没渲染"、"分形页 `no-btn`（按钮不存在）"** ——
这更像**被测页面产物不对**（旧 `dist` / 没重新同步的 `wwwroot` / 跑的不是最新 `wwwroot`），
而不是 6 处互不相关的功能同时回归。`BUGS.md` §0.2 自己也写了同类的坑（沙箱、`TEMP`、esbuild 收尾失败）。
另一条同样成立的解释：**`BUGS.md` 的那份"全绿"是在另一个产物上跑的**（写在本次跑批之前）。

**无论哪种，都不能靠推断结案** —— 需要一次产物时间戳与跑批结果都记录在案的复跑。

**处置**：
1. **冻结**：在澄清之前，不要把 `BUGS.md` 里"二次实测全部转绿"的表格当成已定稿事实引用；
2. **复跑**（B 面，单独占一个时间窗）：
   `npm run build` → `sync-wwwroot.mjs` → 附着宿主 → `run-all.ps1 -NoLaunch`，
   并**同时记录三样东西**：`dist` 的 mtime、被测 `wwwroot` 的绝对路径与 mtime、完整的 `RESULT` 行。
   只记结果不记产物，等于下次还得再吵一遍；
3. 复跑后二选一：要么改 `BUGS.md` 的数字，要么写明"当时是在另一个产物上跑的"。
   无论哪种，都要**带时间戳**（`AGENTS.md` §5）。

### R2【中】51 个提交未推送 —— 只存在于本机磁盘

```
git log origin/main..HEAD --oneline | Measure-Object -Line   # 51
```
`master` 领先 `origin/main` **51** 个提交。任何一次磁盘故障 = 这一整轮工作消失。
**建议**：确认 §4 D2 后推送（或先推一个分支备份）。

### R3【已处置】本机临时产物污染 `git status`

`.tmp-build/`、`.tmp-shotA.png`、`.tmp-shotB.png`、`MF_UI/MFMath.UI.Vue/.tmp-*.mjs`（5 个）
此前是未跟踪状态。已列入 `.gitignore` 的 `.tmp-*` / `.buildtmp/`（**只忽略，不删文件** ——
可能还有会话在用）。依据：`ACCEPTANCE.md` §0.1 明确要求把 `TEMP/TMP` 指到仓库内的 `.tmp-build/`。

### R4【中】宿主进程残留，与"页面唯一驱动者"的互斥假设冲突

`msedgewebview2` 自 **09:50:15** 起常驻（累计 CPU 223 s / 163 s）。在它被关掉之前，
任何"我独占这个页面"的假设都不成立 —— 而 `run-all.ps1` 的用例**对并行驱动极敏感**
（`BUGS.md` §0.3、新用例 `cdp-plot-workspace` 自带 `INTERFERENCE` 提示）。
**处置**：跑端到端之前先确认没有别人的宿主；跑完把自己起的宿主关掉。

### R5【低】`cdp-engine-coverage` 需要一个独占时间窗

约 **45 分钟**（415 模式 × ~7 s），且**中途 Ctrl-C 会让页面之后永久阻塞**
（未取消的后台任务占着引擎；`BUGS.md` §0.2 第 5 条实测卡了 30+ 分钟）。
排期时单独占一个窗口，且在宿主里跑，别在别人的会话里跑。

### R6【提示】每个会话的 `%TEMP%` 是**各自独立**的，`ACCEPTANCE.md` §0.2 的"工作区外运行目录"因此是**每会话一份**

**实测（2026-10-07 10:0x）**：本会话的 `$env:TEMP` =
`C:\Users\FSAFSA~1\AppData\Local\Temp\dsh-S3MvdL`；而 A 面 09:50 那次跑批用的
`%TEMP%\mfhost-run` 并不在这里（本会话里 `…\dsh-S3MvdL\mfhost-run` **不存在**）。

- **好处**：两个会话不会抢同一个 `wwwroot` / 同一个 exe，天然隔离 —— 这解释了为什么
  `AGENTS.md` §4 的"wwwroot 唯一写者"在实际操作里没那么容易撞车；
- **代价**：**"我这边跑绿了"不能推广成"别人那边也绿"** —— 各自 `wwwroot` 的产物时间不同。
  引用结论时必须写清**在哪个会话、哪份产物**上（正是 R1 的成因之一）；
- **给 A 面的建议**：`ACCEPTANCE.md` §0.2 里 `$run = "$env:TEMP\mfhost-run"` 值得补一句
  "这是每会话独立的路径；跨会话对比结论前先核对两边 `wwwroot` 的 mtime"。

### R7【高】文档债：多份文档仍把**已废弃的 .NET 宿主**写成现役实现

D1 之后暴露的最大一块债。**清单（`grep` 可复现，2026-10-07 10:0x）**：

| 文档 | 位置 | 过时的是什么 | 严重度 |
| --- | --- | --- | --- |
| `docs/AI-ASSISTANT.md` | `:19-21` | 把凭据 / 网络 / 桥面写成 `MFMath.Host/AiConfig.cs`、`AiRelay.cs`、`AiBridge.cs` | 🔴 **描述的是一个已经不存在的实现** —— AI 早已改页面直连（`9c1ad1a`），宿主 ai 桥也已拆（`eafd482`） |
| `MF_UI/MFMath.UI.Vue/tests/run-all.ps1` | 解析宿主的默认路径 | 默认指向 `MFMath.Host\bin\Release\...\MFMath.exe`（**实测该 wwwroot 停在 03:45**） | 🔴 .NET 一旦废弃，**默认值就指向废弃产物** —— 每次跑批都可能对着错的东西，正是 R1 的成因 |
| `docs/ACCOUNT.md` | `:79-81` | 账号桥面写成 `AccountApi/AccountConfig/AccountBridge.cs` | 🟡 Rust 侧 `account.rs` 有 19 个方法，契约需重新对照 |
| `docs/ONLINE-SEARCH.md` | `:20-23` | 四个 `Search*.cs` 文件 | 🟡 Rust 侧 `search.rs`（79 KB） |
| `docs/UPDATE-CHAIN.md` | `:48-53` | `UpdateBridge.cs` / `ShellOpen.cs` / csproj 版本号 | 🟡 Rust 侧 `update.rs` / `shellopen.rs` |
| `docs/SETTINGS-BACKUP.md` | `:41` | `WindowBridge.cs` 的 `SaveTextFile/OpenTextFile` | 🟡 Rust 侧 `winbridge.rs` |
| `docs/MIGRATION-GAPS.md` | `:37`、`:331-333`、`:350` | 宿主桥清单 + `dotnet build` 运行步骤 | 🟡 |
| `docs/STATUS-and-ROADMAP.md` | `:58`、`:79`、`:125`、`:365-373` | 宿主构建 / 运行步骤、宿主行数 | 🟡 |
| `MFMath.Host.Rust/README.md` · `docs/LINK-LAYER.md` | `README:19`；`LINK-LAYER:191`、`:640`、`:665` | 写着"C# 宿主**现役**""Rust 宿主**迁移中**" | 🟡 **A 面自己的文档**，口径需要 A 面改（我不代改别人的文件） |

**处置（不要一次全改）** —— 按"会不会直接害人"排序：

1. **`AI-ASSISTANT.md`**：它讲的实现已经不存在，最会误导人；
2. **`run-all.ps1` 的默认宿主**：废弃宿主不该是默认值。**这是 B 面的文件**，我登记不代改；
3. 其余 7 处按"引用前先核对 Rust 侧"逐份改，**谁的文档谁改**，管理者只维护这张清单
   （`AGENTS.md` §2 已点名 7 份，见到"现役"就改）。

> ⚠ **我不替一线改这些数字**：它们的正确写法取决于 Rust 侧的真实契约，
> 而那要 A/B 面各自核对。管理者写错一个字段名，比留着一条"已登记待改"更糟。

---

## 4. 决策记录（2026-10-07，项目所有者）

| # | 问题 | 决定 | 我已做的处置 | 还欠什么 |
| --- | --- | --- | --- | --- |
| **D1** | 三个 Agent 的分工 | **".NET 是废弃的东西"** —— `MFMath.Host/` 不再是工作面 | ① `AGENTS.md` §2/§3 把它移出管辖范围并加报废说明；② 本表把 C 面收窄为"引擎 / 全局文档"；③ `README.md` 加迁移横幅、架构图标出"已废弃"、目录表拆成"现役 / 已废弃"两行；④ 登记文档债 **R7** | 第三个 Agent 做哪一块仍未明（见 §2 注）；`R7` 列的 7 份文档待逐份改 |
| **D2** | 51 个提交是否推送 | **先不推** | 未推送数写进 **R2**，作为**已知并接受**的风险保留 | 每次收口重新报数；数字继续涨就重新拍板 |
| **D3** | 是否另起子 Agent | **先不要，维持现状** | 我只做管理：git 卫生、文档一致性、状态与风险跟踪 | 无 |

> 三条决定的共同点：**都是"收窄"而不是"扩张"** —— 停掉一条已废弃的线、不动远端、不新开战线。
> 那么这一轮管理工作的价值就落在两件可验证的事上：
> ① 让"结论必须带产物时间戳"成为所有人的口径（已有两条线各自写进自己的文档，见 §5.1）；
> ② 把所有者的一句口头决定，变成仓库里**可被搜索到、且能自我延续**的文字（`AGENTS.md` + `README.md` + R7）。

---

## 5. 收口检查结果（2026-10-07 10:00）

**本次收口由管理者做的提交（5 个）**：

| 提交 | 内容 |
| --- | --- |
| `chore(git)` | `.gitignore` 收容 `.tmp-*` / `.buildtmp/`（R3）；只忽略不删文件 |
| `docs` | 新增 [`AGENTS.md`](../AGENTS.md) 与本文 |
| `docs(board)` | R1 补时间线证据 + 新增 R6 |
| `docs(board)` | §5.1 记录 A 面仍在写入 |
| `docs` | **落实 D1**：`README.md` 加宿主迁移横幅、架构图标"已废弃"、目录表拆"现役/已废弃"，`AGENTS.md` §2/§3 移出 .NET 管辖范围，并登记 **R7** |

**未提交、且刻意留给 B 面的在途工作**：`MF_UI/BUGS.md`、
`tests/cdp-plot-accuracy.mjs`、`tests/run-all.ps1`（已改）与
`tests/cdp-plot-workspace.mjs`（新增）。理由：这几份改动是**同一次工作**，
且其中的"全绿"数字要先过 R1 —— 管理者不替在途的一线改数字。

| 检查 | 结果 |
| --- | --- |
| `git status --short` | 3 个已改（`MF_UI/BUGS.md`、`tests/cdp-plot-accuracy.mjs`、`tests/run-all.ps1`）+ 1 个新增未跟踪（`tests/cdp-plot-workspace.mjs`，**已登记进 run-all.ps1，属 B 面在途工作**）+ 临时产物（已按 R3 处置） |
| 提交信息风格 | 近 12 个提交全部符合 `AGENTS.md` §3；无"应该没问题"这类表述 |
| 工作树与 HEAD 的一致性 | `git diff --stat` = 3 文件 / +50 −10 |
| 未跟踪的**真实资产** | `tests/cdp-plot-workspace.mjs`（新用例，**不该被忽略**，应由 B 面随登记一起提交） |
| 重复工作迹象 | 无（三个提交范围互不重叠） |

**给 B 面的一件事**：`tests/cdp-plot-workspace.mjs` + `run-all.ps1` 的登记 + `BUGS.md` 的更正
是同一次工作，建议**一次提交**；但其中的"全绿"数字要先过 R1。
另有一件由 D1 引出的（见 R7 第 2 条）：**`run-all.ps1` 解析宿主的默认路径指向已废弃的 .NET 宿主**
（实测它的 `wwwroot` 停在 03:45），而 `.NET 既然废弃，默认值就该改指 Rust 宿主 —— 这是 B 面的文件，
我登记不代改。

**给 A 面的一件事**：`MFMath.Host.Rust/target/` 下已有 6 个 `*.log`（跑批证据）。
`target/` 不入 git，所以**结论要抄进 `LINK-LAYER.md` / `ACCEPTANCE.md`**，否则证据随 `cargo clean` 一起消失。

### 5.1 本快照写完之后仍在写入（观察，2026-10-07 10:02）

本文件第一次提交（`d4e144f`）之后，工作树立即又变了 —— **这棵树是活的**，快照必然滞后：

| 时刻 | A 面的新动作 |
| --- | --- |
| 10:02:20 | 新增 `MFMath.Host.Rust/docs/PACKAGING.md`（发布形态：`tauri build --bundles nsis`，实测安装包 **11.11 MiB**；安装→启动那条路本机验不了，已如实写明） |
| 10:02:31 | `ACCEPTANCE.md` 加 §7 指向它，并引进 **`AGENTS.md` §4 的并发规矩**（"起宿主前先看有没有别人在跑"） |

两点值得记下来：

1. **规约已经在被引用** —— A 面主动把 `AGENTS.md` §4 写进了自己的验收文档。所有权与互斥这两条
   不是纸面文章，是当下就在用的东西。
2. **A 面独立提出了与 R1 同一个担忧**：`ACCEPTANCE.md` §6 自己写着
   "跑全量前先确认 `dist` 的构建时间戳，并**记进结论**：如果工作区里还有别人正在改的前端代码，
   数字反映的是'那份未提交的代码'，不是被测提交。" —— 这与 R1 的处置第 2 条是同一件事，
   两边口径已经一致，**不需要我再协调**。

> 结论：**管理者的职责不是追平每一次改动**，而是保证"结论必须带产物时间戳"这条被所有人执行。
> 目前它已经被两条线各自写进了自己的文档。
