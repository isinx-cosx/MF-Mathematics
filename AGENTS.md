# AGENTS.md —— 多个 Agent 并行改同一棵树时的规矩

> **本文只回答一个问题：怎么在这棵树上并行干活而不互相踩。**
>
> 与其它文档的分工：
> - [`docs/PROJECT-BOARD.md`](docs/PROJECT-BOARD.md) —— 谁在做什么、到哪一步了、风险台账；
> - [`docs/OPEN-ITEMS.md`](docs/OPEN-ITEMS.md) —— 还有什么功能没实现（待办）；
> - [`MF_UI/BUGS.md`](MF_UI/BUGS.md) —— 前端确有证据的缺陷；
> - [`MFMath.Host.Rust/docs/ACCEPTANCE.md`](MFMath.Host.Rust/docs/ACCEPTANCE.md) —— Rust 宿主的可复现验收步骤；
> - [`README.md`](README.md) —— 给使用者的说明。
>
> 本文件由**项目管理者**维护。改它请单独一次提交，并在提交信息里写明理由。

---

## 1. 先读那三条纪律

[`README.md`](README.md) 的「三条纪律」不是口号，是有代码与测试对应的：

1. **不编造结果** —— 算不出来就说算不出来；
2. **AI 不承担计算** —— `tests/cdp-ai.mjs` 里有专门守这条的用例；
3. **每个修复都要留下"为什么"和"怎么证明"** —— 没有可复跑的判据，不算修完。

对本文件而言，纪律 ③ 的具体含义是 **§5 证据规约**。

---

## 2. 工作面与文件所有权

按 git 证据划出的三条工作面（划分依据见 [`docs/PROJECT-BOARD.md`](docs/PROJECT-BOARD.md) §2）：

| 面 | 管辖路径 | 验收命令（全在本机可跑） |
| --- | --- | --- |
| **A · Rust 宿主** | `MFMath.Host.Rust/**`（含它自己的 `docs/`、`tools/`） | `cargo build`（warning 应为 0）→ `node tools/sync-wwwroot.mjs` → `--selftest-*` → `tests/run-all.ps1 -NoLaunch`；判据见 `ACCEPTANCE.md` |
| **B · 前端** | `MF_UI/MFMath.UI.Vue/**`、`MF_UI/MFMath.UI.React/**`、`MF_UI/BUGS.md` | Vue：`npm run check`（types + 引擎签名 + UI 自检）→ `npm run build`；React：`npm run check:types`；端到端：`tests/run-all.ps1 -NoLaunch` |
| **C · 引擎 / 全局文档** | `MF_Mathematics/**`、`docs/**`、`README.md`、`AGENTS.md` | 引擎：`cmake --build … --config Release` → `ctest … --output-on-failure` → `probe_call.exe list_functions` 的 `count` 应为 **424** |

> **`MFMath.Host/`（C#/.NET 宿主）已移除** —— 2026-10-07 由项目所有者决定废弃，随后从仓库删除。
> 现役宿主只有 **`MFMath.Host.Rust/`**（A 面）。控制台的 Python/C++ 门面已迁到
> `MFMath.Host.Rust/console/`。
> - `docs/` 里 `ACCOUNT.md`、`ONLINE-SEARCH.md`、`AI-ASSISTANT.md`、`UPDATE-CHAIN.md`、
>   `SETTINGS-BACKUP.md`、`MIGRATION-GAPS.md`、`STATUS-and-ROADMAP.md` 仍把它写成**现役实现**，
>   引用前先核对 Rust 侧；

**跨面的改动必须写清**：例如改了 `MF_Mathematics/` 的键名契约，A/B 两面的用例都可能失效 ——
在提交信息里点名"影响了哪一面"，必要时由管理者协调（B1/B2 就是这一类）。

**唯一写者原则**：同一时刻，**一个文件只有一个 Agent 在写**。要改别人管辖的文件：

1. 先在自己的提交/消息里说明"我要动 `X`，理由是 `Y`"；
2. 小改（加一行断言、改一句注释）可以直接做，但**必须在提交信息里标出跨面**；
3. 结构性改动先找管理者，不要在对方正在跑端到端时动他的源码。

---

## 3. 提交规约

沿用本仓库既有风格（`git log` 里 93 个提交都是这个形状）：

```
<type>(<scope>): <一句中文，说清"做了什么、为什么">

可选正文：现象 / 证据（文件:行 或可复跑命令）/ 影响面 / 验证方式
```

- **type**：`feat` `fix` `docs` `chore` `test` `refactor` `perf`
- **scope**：
  - `engine`（`MF_Mathematics`）、`host-rust`（`MFMath.Host.Rust`）
  - `ui`（Vue 壳/通用）、`plot`（React 绘图组）
  - `tests`、`docs`，多条线时用 `ui,tests,docs` 这种并列写法（仓库里已有先例 `8c4ac48`）
- **一次提交一件事**。文档与代码如果是一件事的两半，可以同一次提交（`d71b457` 就是这样）。
- 提交信息里**不要写**"应该没问题""大概修好了"这类话 —— 见 §5。

---

## 4. 并发互斥（这些资源全仓库只有一份）

并行会话踩过的坑已经写进 [`MF_UI/BUGS.md`](MF_UI/BUGS.md) §0.2、§0.3，这里是操作口径：

| 资源 | 规矩 |
| --- | --- |
| `dist/` 与宿主 `wwwroot/` | **同一时刻只有一个人构建并同步**。`npm run build` 之后必须重新 `sync-wwwroot.mjs`，否则你验的是旧产物 —— 这会被误读成功能回归 |
| 宿主进程 | 起宿主前先看有没有别人已经在跑（`Get-Process msedgewebview2`）。优先 `run-all.ps1 -NoLaunch` **附着**到已有宿主，不要另起一个 |
| `run-all.ps1` 的用例 | 用例会互相踩（套件自己会打印 `INTERFERENCE` 提示）。跑之前确认没有别的会话在驱动同一页面 |
| `%TEMP%` / `.tmp-build/` | 构建前 `$env:TEMP="$repo\.tmp-build"; $env:TMP=$env:TEMP`。它已进 `.gitignore`，别提交 |
| `CARGO_HOME` | `$env:CARGO_HOME="$repo\.cargo-home"`，不要写用户级 |
| 长用例 `cdp-engine-coverage` | 约 45 分钟，且**中途 Ctrl-C 会留下没跑完的后台任务，让页面之后永久阻塞**（`BUGS.md` §0.2 第 5 条）。单独占一个时间窗；要中断就先停宿主 |
| git 索引 | 只 `git add` 自己改的文件，**不要 `git add -A`** —— 别人的半成品不该被你收进提交 |

---

## 5. 证据规约

这个仓库已经因为违反下面几条付出过代价，所以写死：

1. **结论必须带时间戳。** 在有人并行改同一棵树的情况下，"某处失败 ⇒ 归因给环境/宿主"这种结论
   **过期得非常快**：`BUGS.md` §0.2 曾把 88+37+27 条失败归给"宿主缺桥"，随后被并行提交
   （`9c1ad1a`、`eafd482`）悄悄推翻。写成"**<时间> 在 <产物> 上实测**"。
2. **跨工程取证必须覆盖两个工程。** Vue 与 React 共用 `@shared/*`，只 grep `MFMath.UI.Vue/src`
   会得出"全仓库没人调"的错误结论（`BUGS.md` §0.1 第 1 条）。
3. **失败要分清"产品缺陷 / 用例自身判据错 / 环境没准备好"**，并写明是哪一种。
4. **修完就删。** `OPEN-ITEMS.md`、`BUGS.md`、`PENDING`、`KNOWN_FAIL`、`ACCEPTANCE.md` 里的数字
   都按这个纪律维护 —— 留着不删就会变成没人信的摆设（验收清单里 34/66 步那类数字就是这么烂掉的）。
5. **验收类文档里的数字变了就更新**，别让它变成装饰。

---

## 6. 不要提交的东西

`.gitignore` 已覆盖 `.tmp-*`、`.buildtmp/`、`build/`、`dist/`、`bin/`、`obj/`、`.cargo-home/`、
`node_modules/`、`*.log`。**特别注意**：

- `MF_UI/MFMath.UI.Vue/.tmp-*.mjs` 这类排查脚本里有**本机绝对路径与本机端点**；
- 编译产物一律不入 git（`README.md` 已说明理由：可重建，且会让历史迅速膨胀）。

---

## 7. 管理者的收口清单

每次收口（或每轮结束）跑一遍：

```powershell
git status --short                 # 有没有该进 .gitignore 的临时产物混在里面
git log --oneline -10              # 提交信息是否符合 §3
git log origin/main..HEAD --oneline | Measure-Object -Line   # 未推送的提交数
npm run check --prefix MF_UI/MFMath.UI.Vue
npm run check:types --prefix MF_UI/MFMath.UI.React
```

再核对一遍 **文档与实测是否一致**（这一步最容易被跳过，也最容易出问题 ——
`docs/PROJECT-BOARD.md` §3 的风险 R1 就是这么抓出来的）。
