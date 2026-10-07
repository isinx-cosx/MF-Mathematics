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

**代码在快速推进，文档在追赶，git 有 59 个提交没推（D2：决定先不推）。**

本轮管理的三件事：

1. **R1 已结案** —— 我提出的"最新端到端与 `BUGS.md` 的『全绿』矛盾"，真因**不是**我猜的
   "产物不对"，而是 **R4 的并发驱动**：那一刻有两个宿主共用一份 CDP 端口，页面被另一个会话开走了。
   **我那条猜想是错的**，B 面用三条独立证据查清了（§3 R1 结案）。留这段是因为
   "结论必须带产物时间戳"这条纪律正是这么来的 —— 连管理者也会猜错；
2. **R4 是当下最要紧的操作纪律** —— 并发驱动已经真的兑现过一次假失败（还顺带污染了对方），
   `AGENTS.md` §4 里那条已从"建议"升级为**前置条件**；
3. **R7（文档债）** —— 所有者拍下"**.NET 宿主已废弃**"之后，暴露出**多份文档仍把它写成现役实现**
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
| B | `tests/run-all.ps1 -NoLaunch` | 48 个 `cdp-*` 全部登记（`check-ui` 会校验"用例数 = 登记数"），无 `no RESULT line` |
| C | `ctest --test-dir MF_Mathematics/build -C Release` | 16/16 套件 |
| C | `probe_call.exe list_functions '{}'` | `count` = **424**（WHOLEARCHIVE 守门） |

---

## 3. 风险台账

### R1【已结案】最新一次端到端与 `BUGS.md` 的"全绿"表述矛盾 —— 真因是**并发驱动**

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

**处置**：~~冻结 / 复跑 / 二选一~~ —— **已在 10:0x 结案，见下。**

#### 结案（2026-10-07 10:0x，由 B 面查清）

**真因是并发驱动，不是旧产物、也不是产品回归** —— 我上面那条"产物不对"的猜想是**错的**。
B 面在 `b8872fa` 里给出了三条独立证据：

1. `Get-CimInstance Win32_Process` 抓到**别的会话**的用例进程在跑
   （`cdp-plot-fractal.mjs`、`cdp-complex-modes.mjs`、`cdp-calc-workspace.mjs`、`cdp-update.mjs`、`cdp-engine-coverage.mjs`），
   采样能看到它们按 `run-all` 的顺序一辆一辆过去；
2. 同一时刻存在**两个 `mfmath-host-rust.exe`**（09:50:12 / 09:50:15 各起一个），
   而 **CDP 端口只有一份** → 两个会话共用同一个页面；
3. 设 `location.hash='#/plot/2d'` 之后读到的是 **`#/plot/vector`**，另一次是 **`#/plot/fractal`**
   —— 这两个路由 B 面从没导航过。于是 `cdp-plot-accuracy` 在完整套件里 10/4：
   它的 ③ 三条断言全挂在"页面已被换成 vector 页"上（vector 页也有 canvas，但没有 `__mfPlot`、
   也没有「缩放到适应」按钮）。同理可解释 `cdp-font-load` 的"字体 0 KB"与 `cdp-plot-fractal`
   的 `no-btn` —— **被测页面已经不是那个套件以为的页面了**。

**同时更正了一个更早的错误归因**：`BUGS.md` §0.3.1 原先把 `cdp-engine-coverage` 的 296/7
归给"长会话累积/内存不回收"，同一份证据表明真因也是并发驱动。

**这条风险的价值**：它把 `AGENTS.md` §4 里那条"跑之前确认没有别的会话在驱动同一页面"
从**建议**变成了**必需品** —— 违反它一次，就会得到一整套看起来像产品回归的假失败，
而且会污染另一个会话的跑批结果（双向破坏）。

**遗留的待办（不是 R1 本身）**：B 面自己写明「本用例尚未跑出数字」——
`cdp-plot-workspace`（B14 那 5 页）在**独占窗口里跑绿之前**仍算"代码就绪、未验证"。
这句话我保留原样，不替它升级状态。

### R2【中·已接受】未推送的提交只存在于本机磁盘

```
git log origin/main..HEAD --oneline | Measure-Object -Line   # 59（2026-10-07 10:10）
```
`master` 领先 `origin/main` **59** 个提交（本轮管理期间从 51 涨到 59 —— 三个面各自又提交了）。
**D2 已决定"先不推"**，所以这是一条**已知并接受**的风险，不是待办。
任何一次磁盘故障 = 这一整轮工作消失；数字继续涨就该重新拍板。

### R3【已处置】本机临时产物污染 `git status`

`.tmp-build/`、`.tmp-shotA.png`、`.tmp-shotB.png`、`MF_UI/MFMath.UI.Vue/.tmp-*.mjs`（5 个）
此前是未跟踪状态。已列入 `.gitignore` 的 `.tmp-*` / `.buildtmp/`（**只忽略，不删文件** ——
可能还有会话在用）。依据：`ACCEPTANCE.md` §0.1 明确要求把 `TEMP/TMP` 指到仓库内的 `.tmp-build/`。

### R4【高·已实测兑现】并发驱动是**当前最会伪造结论**的机制

我最初按"进程残留"登记它（`msedgewebview2` 常驻、CPU 223 s）。**10:0x 它已经真的兑现了**
（见 R1 结案）：同一时刻**两个 `mfmath-host-rust.exe`**、**一份 CDP 端口**、**一个页面**，
结果是两个会话互相污染 —— 一边得到"整套假失败"，另一边的跑批数字同样不可信。

- 09:50 那次跑批的 6 个红套件，起因都在这里；
- `BUGS.md` §0.3.1 的 296/7 也被重新归因到这里；
- 目前状态（10:10 复核）：`Get-Process mfmath-host-rust` **已无进程** —— 宿主被清掉了，
  也就是说**此刻起跑批是安全的**，但这不保证别人不会再起。

**处置**：
1. 跑端到端**之前**先 `Get-Process mfmath-host-rust,msedgewebview2`；
2. 发现有两个宿主 → **先停掉自己那个再跑**，或者干脆等。抢 CDP 端口没有赢家；
3. 跑完把自己起的宿主关掉（别再留 223 s CPU 的孤儿）；
4. 这条现在与 `AGENTS.md` §4 一一对应，**不是建议而是前置条件**。

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

### R8【中】文档与**代码**不符（与宿主废弃无关的另一类）—— 2026-10-07 写层4 时逐条核对所得

R7 是"文档讲了废弃的宿主"，R8 是"**文档或注释讲错了当前代码**"。写
[`docs/link/FEATURES.md`](link/FEATURES.md) 时逐条对照过源码，全部带 `文件:行` 出处。

**A. 旧文档写错的事实（11 条）**

| # | 位置 | 写的是 | 实际是 |
| --- | --- | --- | --- |
| 1 | [OPEN-ITEMS.md](OPEN-ITEMS.md)`:44` | "只有 401 才清登录态" | **403 也会** —— `site.rs:178` 把 401/403 都映射成 `unauthorized`，而 `account.rs:557/604` 对它一律 `clear_token()` |
| 2 | [STATUS-and-ROADMAP.md](STATUS-and-ROADMAP.md)`:29`、[OPEN-ITEMS.md](OPEN-ITEMS.md)`:40-52` | 把 `token_version` 写成软件侧相关行为 | **宿主零实现** —— 全仓库 Rust 源码一处都没有，只有文档提到 |
| 3 | [ACCOUNT.md](ACCOUNT.md)`:96` | 失败分类列七类 | **漏了 `http`** —— 500/404/502 都会产出它（`site.rs:180`） |
| 4 | [ACCOUNT.md](ACCOUNT.md)`:106`、`tests/cdp-account.mjs:225` | "自检 6 项" | 实际 **7** 项；用例只断言 `ok_all`、**不数个数**，所以标签错了却一直是绿的 |
| 5 | [ACCOUNT.md](ACCOUNT.md)`:127-128` | 把"校验 sha256"归入"未做" | 设计上是**永不做**（`update.rs:4-5`）—— "不做"与"未做"必须分开写 |
| 6 | [UPDATE-CHAIN.md](UPDATE-CHAIN.md)`:48` | `ResolveDownloadUrl` 是桥面方法 | 它是**内部函数**，页面调不到 |
| 7 | [UPDATE-CHAIN.md](UPDATE-CHAIN.md)`:28` | 版本比较在 `UpdateBridge.CompareVersions` | 对应物是 `update::compare_versions` |
| 8 | `search.rs:1093-1094`（**代码注释**） | "搜索不用浏览器 UA" | **三个后端全部用浏览器 UA**（否则 DDG 反爬 403）—— 注释与实现**相反** |
| 9 | `console.rs:9/26/1514`、`handlers.rs:104`（**代码注释**） | `Poll` 是"**增量**取回" | **全量快照**；"增量"描述的是调用方式，不是数据形状 |
| 10 | `account.rs:10-11`（**代码注释**） | 续期失败"只标记需重新登录" | 401/403 时**直接清掉登录态** |
| 11 | `dpapi.rs:1/18`（**代码注释**） | AI 的 API Key 是 DPAPI 用户 | AI 密钥已是**明文** |

**B. 代码行为本身的四个待跟进项**（不是文档问题）

| # | 事项 | 影响 | 归属 |
| --- | --- | --- | --- |
| 1 | `con` 的 `cpp.ready` **判据少一件文件**（只查导入库 + `mfmath.hpp`，而运行还要求 `mfmath_autorun.hpp`） | **"下拉里能选 C++，一跑就报缺件"** | A 面（宿主）/ B 面（下拉可见性用 `ready`） |
| 2 | `sys.StoreDelete` **不删 `.bak`**，而 `ai.json.bak` 里是**明文 `apiKey`** | 用户以为"清掉了"，磁盘上还在 | 见 [CREDENTIALS.md](link/CREDENTIALS.md) §2.3 |
| 3 | `sys.OpenPath` 的白名单判据是**小写化字符串前缀**（没补分隔符、没 `canonicalize`） | 同前缀的兄弟目录必然通过；`..` 是否被解析**未证实** | 危害有限（只打开/选中，不执行） |
| 4 | `con` 的 `RUNS`/`JOBS` 两张表**只增不减** | 每个 `Start` 的完整输出（≤512 KiB）永久留内存 | A 面 |

**处置**：A 类的 8 条属**各面自查**（谁的文档谁改，管理者只维护清单）；
B 类的 4 条**需要决定**：改代码，还是写进文档当已知边界 —— **D3 已定"不另起子 Agent"，
所以这 4 条先留在台账里等排期**，不擅自开工。

**C. 4 份旧文档的退役：已加横幅，但**暂不删除**（这是一个被拦下来的动作）

计划里写的是"`FEATURES.md` 写完后退役那 4 份"。**实际执行时发现不能直接删**：

```
grep -c 'ONLINE-SEARCH\.md|ACCOUNT\.md|UPDATE-CHAIN\.md|SETTINGS-BACKUP\.md'
→ 12 个文件 / 41 处引用
```

包括 **A 面的 `LINK-LAYER.md`**、**B 面的源码注释**（`App.vue:262`、`router/index.js:56`），
还有 `MIGRATION-GAPS.md`、`OPEN-ITEMS.md`、`STATUS-and-ROADMAP.md`、`DECISIONS.md`、
`DESIGN-BOUNDARIES.md`。直接删 = **一次性制造 41 处死链**，正好违反
[`AGENTS.md`](../AGENTS.md) §5 与 [`docs/README.md`](README.md) 那条"不给没写好的条目写链接"的规矩。

**改为**：给那 4 份各加一条**退役横幅**（指向 `FEATURES.md` 的对应小节，并写明"引用前先核对"），
**文件保留**；删除动作变成一条**有明确前置条件的待办**：**先把 41 处引用改指到
`docs/link/FEATURES.md`，再删**。跨面的那几处（A 面的 `LINK-LAYER.md`、B 面的两处源码注释）
需要各自面动手。

> 📌 这是这一轮唯一一次**计划被自己的规矩拦下来**。记在这里，是因为"写下计划"与"执行计划"
> 之间常常隔着一个 grep —— 而**先 grep 再删**，比删完再修 41 处要便宜得多。

> **两点说明**：① 这批结论是**读源码 + 交叉核对**得到的，其中 §B-3 与
> "两次 `Install` 同一组件是否会损坏目录"等**已明确标注"未证实"**，没有当成事实写；
> ② 我**没有替一线改**这 11 处 —— 改数字要按 Rust 侧真实契约定稿，那是各面作者的活。

---

### R9【中】层2/3/6 批量产出（24 份）之后的产出债汇总

**先说台账原则**：这 24 份文档里有 **21 份自带「已知的文档债」小节**（每份都注明 `文件:行` 与
"注释说 X，代码做 Y"）。**本文不重复抄它们** —— 那会变成两份互相漂移的清单。
这里只登记**需要做决定**的那几条，以及管理者本轮**已经修掉**的。

**A. 需要决定：这是产品行为，不是文档措辞**（按影响排序）

| # | 事项 | 证据 | 归属 |
| --- | --- | --- | --- |
| 1 | **`erfc_complex = 1 − erf_complex` 在大 \|z\| 时相消失效** | `erfc(5)` 相对偏差 ≈ **1.5e-5**；`erfc(10)` / `erfc(27)` **返回 0 且 `ok=1`**（参考值 2.088e-45 / 5.237e-319）；测试只钉了 `erfc(1)`，**没有回归保护** | 引擎（C 面） |
| 2 | **教程浮层给用户看一句假话** | `TourOverlay.vue:68-71` 的 `missingReason` **恒真**（`targets.js:130-135`）⇒ "前往该界面"按钮与 **14 条 `TARGET_HINTS` 是死代码**，用户看到"这一步的目标界面还没做"（静态可判定） | 前端（B 面） |
| 3 | **给用户看的设置说明写错了安全口径** | `settings/catalog.js:22` 的 AI 说明写"**密钥只存宿主（DPAPI）**"，而实际是明文 `ai.json`（同文件 `:70` 自己又写着"明文…不受保护"，**自相矛盾**） | 前端（B 面） |
| 4 | **两个数字字面量被静默粘连** | `expr_eval("2 3")` → **23**；`math_input.h:549/:960` 的注释只写"数字与数字之间不做乘法"。**静默错值**，而 [BUGS.md](../MF_UI/BUGS.md) 与 [OPEN-ITEMS.md](OPEN-ITEMS.md) **都没登记** | 引擎 / 前端 |
| 5 | **`engine-signatures.json` 的 `required` 与代码不符** | 例：`expr_eval_grid` 表里要求 `xs/ys/x/y`，代码只读 `expr/xs/ys`（不带 x/y 也能成功）。而这张表被 [docs/README.md](README.md) §2 登记为"参数键名权威源"，下游 AI 工具校验（`validateArgs`）会据此**误判必填** | 引擎 + 前端 |
| 6 | **三个 ODE 求解器的步数不经上界收口** | `n = max(1, ceil((t_end−t0)/h))`（`ode_solver.cpp:16-19`）不走 `get_int_bounded`；实测 **1e6 步即超出 `probe_call` 的 4 MiB 缓冲**（`exit=3`） | 引擎 |
| 7 | **pretty 打印仍外泄机器记号** | `simplify_sym` 返回非法的 `(1/2)*/x`；`solve_sym` 的 `delta` 返回 `-4 + a**(-2)`，而同一个量在 `discriminant_sym` 里过了 `pretty_math`（两处**记号不一致**）。与 `symbolic_api.cpp:17` "不再外泄 `a**(-1)`" 的说法相反 | 引擎 |

**B. 文档措辞类** —— 21 份文档各自的债小节已逐条记名，另有**跨到别人领地**的几处需要各自面动手：
`MFMath.Host.Rust/README.md`（自相矛盾：`:3` 说 10 个对象落地 7 个、`:46` 说全部落地、`:19` 说 9 个，而权威是 **9**）、
`MFMath.Host.Rust/docs/ACCEPTANCE.md:99-111`（写 run-all "登记在册 **26 组**"，实测 **53**）、
`docs/STATUS-and-ROADMAP.md`（`token_version`、准确性套件路径、25/0 vs 29/0 三处）。

**C. 管理者本轮已经修掉的（3 处，都在我的领地内）**

1. **根 `README.md` 的准确性用例路径写错**：原文把 `MF_Mathematics/tests/accuracy/` 写得像 v2.0 的路径，
   而实测该目录**在 v2.0 里不存在**（`Test-Path` = `False`，`git ls-files` 无命中），
   它在 **v1 树**里（`../Multifunctional-Mathematics/MF_Mathematics/tests/accuracy/`，28 个 `.py` + `report.json`）。
   已改成显式写清 v1 路径并附实测判据 —— 这条由**三份文档独立指出**，是本轮最实的一处更正；
2. **`docs/ui/README.md` 与 `docs/ui/CHECKS.md` 的计数过期**：写这批文档期间 B 面落了
   `unit-history-store.mjs`，`unit-*` 由 3 变 4、登记表由 52 变 **53**（48 cdp + 4 unit + 1 audit-modes）。
   已改并**写明复核时刻**，另加一句"引用前请重跑命令"；
3. **`docs/ui/ENGINE-BINDING.md` 的 3 处死链**：`../AGENTS.md` 应为 `../../AGENTS.md`
   —— 这是**我的编排提示词写错了相对层级**（对 `docs/*/X.md` 而言根在两级之上），已修。

**D. 一条流程发现（值得写下来）**：**Agent 自报的行数不可信。**
这批 24 份工具回报合计 **8914 行**，我实测是 **6636 行**（差 34%）。
与本仓库"能生成的绝不手抄"同一条道理：**只要数字不是自己跑出来的，就要实测一遍**。
处置：批量产出的任何数字，合并前一律由管理者实测复核。

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

**未提交、且刻意留给 B 面的在途工作**：**（10:05 已由 B 面自行提交为 `b8872fa`，此项清空）**
`MF_UI/BUGS.md`、`tests/cdp-plot-accuracy.mjs`、`tests/run-all.ps1` 与新用例
`tests/cdp-plot-workspace.mjs` 是同一次工作，B 面按 `test(plot)` 一次提交，
并在其中把 R1 的真因（并发驱动）与 `BUGS.md` §0.3.1 的错误归因一并更正。
**管理者的角色到此为止是对的** —— 数字由一线自己定，我不代改。

| 检查 | 结果 |
| --- | --- |
| `git status --short` | **空**（10:10 复核：三个面的在途工作都已各自提交，树是干净的） |
| 提交信息风格 | 新出现的 3 个提交（`b8872fa` `9f0b1f5` `ce1602a`）均符合 `AGENTS.md` §3，且**都写了证据与未验证部分** |
| `cdp-*` 用例数与登记数 | 48 / 48（`README.md` 里两处过时的 46、47 已更正为 48） |
| 未跟踪的**真实资产** | 无（新用例已随 `b8872fa` 入库） |
| 重复工作迹象 | 无（三个面的改动范围互不重叠） |

**文档建设（层 1 + 层 5 已落地）**：六层共 35 份文档的**建设台账不在这里，在
[`docs/README.md`](README.md) §3** —— 本文只记进度与风险，避免出现两份互相漂移的清单。
本轮落地 5 份：[`docs/README.md`](README.md)（文档地图）、[`README.md`](../README.md)（收成入口）、
[`docs/DESIGN.md`](DESIGN.md)、[`docs/DECISIONS.md`](DECISIONS.md)、
[`docs/DESIGN-BOUNDARIES.md`](DESIGN-BOUNDARIES.md)。

两条副产品（都属"文档与实测不一致"这一类）：

1. **README 的 CTest 数字自相矛盾**：原文写"16 个 CTest 套件 + 4 个探针（共 19 个可执行目标）"，
   而实测是 **19 个可执行目标 = 15 个 `test_*.cpp` + 4 个 `probe_*.cpp`，其中 16 个注册进 CTest**
   （`grep add_test MF_Mathematics/CMakeLists.txt` 得 16 条）。两个划分被混在一句话里 —— 已更正。
2. **README 的"无安装包"已过期**：Rust 侧实测**能**出 NSIS 包（11.11 MiB），只是"安装 → 启动"未验证。
   已改成"能出，但没验过"，并保留"三步构建仍是唯一被实测跑通的路径"这句 ——
   见 [PACKAGING.md](../MFMath.Host.Rust/docs/PACKAGING.md) 与 [DESIGN-BOUNDARIES.md](DESIGN-BOUNDARIES.md) §5。

顺带把两处**重复真相**收成指针：README 原来自己维护一份"文档清单"和一份"已知边界"，
现在分别指向 [`docs/README.md`](README.md) 与 [`docs/DESIGN-BOUNDARIES.md`](DESIGN-BOUNDARIES.md)
（保留 LICENSE 那一行作法律声明）。

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
| 10:03:59 | A 面提交 `9f0b1f5`：补一条实测 —— release 构建的无头自检在工作区外 **10/0 与 5/5** |
| 10:05:08 | B 面提交 `b8872fa`：新用例 + 登记（48/48）+ **把 R1 的真因更正为并发驱动**，并推翻自己更早的"长会话累积"归因 |
| 10:10 | 管理者复核：`git status` **空**，未推送 **59**；`README.md` 两处过时用例数（46、47）已改为 **48** |

两点值得记下来：

1. **规约已经在被引用** —— A 面主动把 `AGENTS.md` §4 写进了自己的验收文档。所有权与互斥这两条
   不是纸面文章，是当下就在用的东西。
2. **两个面各自独立地得出了同一条方法论**：A 面在 `ACCEPTANCE.md` §6 写"跑全量前先确认 `dist`
   的构建时间戳并记进结论"；B 面在 `b8872fa` 里写"用例必须自己检测有没有别人在驱动同一个页面"。
   **两条都是"结论要能追溯到产物与时刻"** —— 与 R1 的处置是同一件事，不需要管理者再协调。

> 结论：**管理者的职责不是追平每一次改动，而是保证一条纪律被执行** ——
> "结论必须能追溯到产物与时刻"。它现在已经被三条线（A 的验收文档、B 的用例、本板）各自写进自己的文字里。
>
> ⚠ 顺带一提：**我也猜错过一次**（把 R1 归给"旧产物"）。这正是这条纪律存在的理由 ——
> 它不只约束一线，也约束写这份板子的人。
