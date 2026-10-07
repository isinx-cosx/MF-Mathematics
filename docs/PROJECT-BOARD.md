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

**代码在快速推进，文档在追赶，git 有 51 个提交没推。**
最要紧的一件事不是写代码，而是 **§3 的 R1** —— 最新一次端到端与 `MF_UI/BUGS.md` 的
"全绿"表述**互相矛盾**，必须先澄清再定稿，否则"全绿"会变成没人信的话。

---

## 2. 三个工作面（按 git 证据划分）

划分依据是 `git log` 的 scope 前缀与实际改动路径，不是猜测：

| 面 | 管辖路径 | 最近一次提交 | 依据 |
| --- | --- | --- | --- |
| **A · Rust 宿主** | `MFMath.Host.Rust/**` | `30b7586`（2026-10-07，`docs(host-rust)`） | 最近 12 个提交里有 7 个是 `host-rust`；19 个 `src/*.rs`，今日 06:42–09:57 连续改动 |
| **B · 前端** | `MF_UI/MFMath.UI.Vue/**`、`MF_UI/MFMath.UI.React/**`、`MF_UI/BUGS.md` | `b6a77c0`（2026-10-07，`docs(ui)`） | `fix(plot)` / `feat(ui)` / `chore(ui,tests,docs)` 三个提交；今日 08:54–09:56 连续改动 |
| **C · 引擎 / .NET 宿主 / 全局文档** | `MF_Mathematics/**`、`MFMath.Host/**`、`docs/**`、`README.md` | `37ac02b`（2026-10-07，`fix(engine)`，改动实际落在前端参数层） | 引擎侧今日**无**提交证据；`docs/` 最近一次是 10-06 |

> ⚠ **C 面的归属需要你确认**（见 §4 D1）。当前只有两条线在提交上有明显活动；
> 如果第三个 Agent 做的是别的（例如站点仓库、安装包、教程资产），告诉我，我改这张表。

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

**我的判断（未定案，需 B 面复跑确认）**：失败特征集中在
**"字体传输量 0 KB"、"KaTeX 一个字都没渲染"、"分形页 `no-btn`（按钮不存在）"** ——
这更像**被测页面产物不对**（旧 `dist` / `wwwroot` 没重新同步），而不是 6 处互不相关的功能同时回归。
`BUGS.md` §0.2 自己也写了同类的坑（沙箱、`TEMP`、esbuild 收尾失败）。

**处置**：
1. **冻结**：在澄清之前，不要把 `BUGS.md` 里"二次实测全部转绿"的表格当成已定稿事实引用；
2. **复跑**（B 面，单独占一个时间窗）：`npm run build` → `sync-wwwroot.mjs` → 附着宿主 → `run-all.ps1 -NoLaunch`，
   把**完整**的 `RESULT` 行与产物时间戳记下来；
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

---

## 4. 待拍板（需要你回答）

| # | 问题 | 为什么需要你 |
| --- | --- | --- |
| **D1** | 三个 Agent 的**具体分工与身份** —— 我按 git 证据划成 A/B/C（§2），但 **C 面今日没有提交证据** | 定错了这张表，所有权边界就是空的 |
| **D2** | 51 个提交**是否推送** `origin/main` | 推送是外发动作，且远端是公开仓库，我不擅自做 |
| **D3** | 是否要我**另起三个子 Agent** 去承接 `OPEN-ITEMS.md` 里的活（例如 §1 站点部署、§6 六个待拍板项） | 可以，但会与现有三条线**抢同一棵树**，得先定互斥 |

---

## 5. 收口检查结果（2026-10-07 10:00）

| 检查 | 结果 |
| --- | --- |
| `git status --short` | 3 个已改（`MF_UI/BUGS.md`、`tests/cdp-plot-accuracy.mjs`、`tests/run-all.ps1`）+ 1 个新增未跟踪（`tests/cdp-plot-workspace.mjs`，**已登记进 run-all.ps1，属 B 面在途工作**）+ 临时产物（已按 R3 处置） |
| 提交信息风格 | 近 12 个提交全部符合 `AGENTS.md` §3；无"应该没问题"这类表述 |
| 工作树与 HEAD 的一致性 | `git diff --stat` = 3 文件 / +50 −10 |
| 未跟踪的**真实资产** | `tests/cdp-plot-workspace.mjs`（新用例，**不该被忽略**，应由 B 面随登记一起提交） |
| 重复工作迹象 | 无（三个提交范围互不重叠） |

**给 B 面的一件事**：`tests/cdp-plot-workspace.mjs` + `run-all.ps1` 的登记 + `BUGS.md` 的更正
是同一次工作，建议**一次提交**；但其中的"全绿"数字要先过 R1。

**给 A 面的一件事**：`MFMath.Host.Rust/target/` 下已有 6 个 `*.log`（跑批证据）。
`target/` 不入 git，所以**结论要抄进 `LINK-LAYER.md` / `ACCEPTANCE.md`**，否则证据随 `cargo clean` 一起消失。
