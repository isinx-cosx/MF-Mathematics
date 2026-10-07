# 构建期闸门与守卫

> **本文只回答一个问题：构建期有哪些闸门、各自拦什么、加一条守卫的规矩是什么。**
>
> 与同层其它文档的分工：
> - [README.md](README.md) —— 两个工程、`@shared` 共享面与构建链；其 §7.1 是**闸门清单的摘要**，本文是它的展开。
> - [ENGINE-BINDING.md](ENGINE-BINDING.md) —— `ENGINE_MAP` / `calcArgs` / `viewConfigs` 的契约本身；本文只讲"谁在构建期检查它们"。
> - [TUTORIAL-KEYPAD.md](TUTORIAL-KEYPAD.md) —— 教程系统与 126 键键盘的内容；本文只讲它们各自的守卫判据。
> - [PLOT.md](PLOT.md) —— React 绘图组与"Vue 绘图组被冻结"的来龙去脉。
> - [`../../MF_UI/BUGS.md`](../../MF_UI/BUGS.md) —— 缺陷台账；本文反复引用 B1 / B2 / B7 / B9 / B10 作为"守卫拦下的真实缺陷"。

**本文的实测时刻**：2026-10-07 10:52–10:56，`HEAD = e77fdb8`（`git rev-parse --short HEAD`）。
命令一律在 `MF_UI/MFMath.UI.Vue` 下跑（除非写明 `--prefix`）。
⚠ 这个时刻很重要：`package.json` 的 `check` 在这一天 10:54 前后**被并行会话改过**（[README.md](README.md) §8.1 有完整记录），引用行号必须带时间戳。

---

## 1. 四道闸门

`npm run check` 是把四段串起来的**唯一入口**（`MF_UI/MFMath.UI.Vue/package.json:17`）：

| # | 段 | 命令展开（`package.json` 行号） | 拦什么 | 2026-10-07 实测 |
| --- | --- | --- | --- | --- |
| 1 | `check:types` | `tsc --noEmit -p tsconfig.json`（`:13`） | TypeScript 类型错误 | exit 0（tsc 静默即通过） |
| 2 | `check:signatures` | `node tools/engine-signatures.mjs --check`（`:14`） | 引擎源码 ↔ `engine-signatures.json` 的漂移 | exit 0，`424 / 424` 条 |
| 3 | `check:args` | `node tools/check-arg-contract.mjs`（`:18`） | **UI 声明的参数键 ↔ 引擎实际读的键**（B1 类"填了不生效"） | exit 0，`415 个模式 / 934 个声明键` |
| 4 | `check:ui` | `build-tutorials.mjs && check-ui.mjs && check-examples.mjs`（`:15`） | 见 §3 的 17 条守卫 | exit 0，三个子步骤各自 `自检通过 ✔` |
| — | React 侧 | `npm run check:types --prefix MF_UI/MFMath.UI.React`（`MFMath.UI.React/package.json:11`） | React 绘图组的类型错误（**没有** `check` 聚合脚本） | exit 0 |

**复跑**：

```powershell
npm run check --prefix MF_UI/MFMath.UI.Vue      # 1→2→3→4，本次 exit 0
npm run check:types --prefix MF_UI/MFMath.UI.React   # 本次 exit 0
```

⚠ **口径提醒**：早先的说明（以及本次任务书）把 Vue 的 `check` 说成"types + 签名 + UI 自检"**三段**，
那是 `check:args` 接进 `check` **之前**的展开式。以代码为准，现在是**四段**；
这一改动是并行会话在 2026-10-07 10:54 前后做的（[README.md](README.md) §8.1 存了两次读到的原文）。

`npm run check` **不是**纯只读：第 4 段第一步 `build-tutorials.mjs` 会重写
`src/tutorials/tutorials.json`，并往 `docs/tutorials-src/*.yaml` 留档（`tools/build-tutorials.mjs:472-493`）。
本次实测**幂等**：跑前跑后 `Get-FileHash -Algorithm SHA256` 相同，且 `git status --short` 只多出别的会话建的
`?? docs/engine/`、`?? docs/ui/`。留档写不进去时只警告、不中断（`:491-499`，BUGS.md B8 的修复）。

> 时间戳纪律的实例：`node tools/check-ui.mjs` 在 **10:58:19 又跑了一次**（当时另有会话正在改
> `src/lib/history/store.js` 与 `src/components/console/CodeEditor.vue`），仍为 `exit 0`。
> 本文 §3 的"本次实测输出"以 **10:52–10:56** 那次为准；那两个文件被并行改动后，`check-ui` 的相关守卫
> （#11 i18n 扫描、#10 import 扫描都会遍历 `src/`）覆盖的输入已经变了 —— 引用数字时必须带上时刻。

**不在闸门里的**（别误当成闸门）：

| 命令 | 为什么不算 | 出处 |
| --- | --- | --- |
| `npm run build` | 产出 `dist/`，是构建不是判据；且与并行会话争 `dist/` | [`../../AGENTS.md`](../../AGENTS.md) §4 |
| `tests/run-all.ps1 -NoLaunch` | 端到端，需要真宿主与独占 CDP 端口（48 条 `cdp-*`） | [`../../AGENTS.md`](../../AGENTS.md) §2、[DECISIONS.md](../DECISIONS.md) D-010 |

---

## 2. 第 2 段与第 3 段：两道"对着引擎"的闸门

这两段都**读引擎源码**（`MF_UI/MFMath.UI.Vue/tools/engine-signatures.mjs:32` 把引擎解析成
`<v2.0>/MF_Mathematics`），与第 4 段的设计取舍正好相反（见 §5）。

### 2.1 `check:signatures` —— 引擎源码 ↔ 签名表

- 判据是**单向**的，只有三种进 `hard`（失败）：函数集合不一致、源码明确读了的参数表里没有、源码按必填读而表里写成可选（`engine-signatures.mjs:145-182`）。
- 反向（表里有、源码没刮到）**只提示**：源码大量参数经 `args["k"]` 或域内 helper 读，刮取器看不到，严格判定会产出上百条假差异（`:88-93`、`:146-156`）。
- 本次实测：`源码 register_function 424 条 / 表 424 条`，提示（不判定失败）**124 处**。
- 重建入口是 `npm run signatures:write`（`package.json:16`），重建后必须人工核对被覆盖的部分（`engine-signatures.mjs:208-209`）。

### 2.2 `check:args` —— UI 的键 ↔ 引擎真读的键（最年轻的一道，`e77fdb8` 才进 `check`）

- 为什么单列：`check:signatures` 只对账"引擎 ↔ 表"，**没有把 UI 算进去**，B1 就是从这个缝里过去的 ——
  引擎读 `interval`、UI 发 `a`/`b`，两边各自"无漂移"，而用户填的区间恒定按 `[0,1]` 算（`tools/check-arg-contract.mjs:5-9`）。
- 判据：UI 为某模式声明的每个键 K，要么刮取器看到 `get_xxx(args,"K")`，要么在 `HELPER_READ` 白名单里**且带判据字符串**（`:11-15`、`:41-44`）。
- 反向（引擎必填、UI 没声明）只警告：已核为**多分支互斥**的假阳性（`:17-19`、`KNOWN_MULTI_BRANCH` `:102-107`）。
- 白名单怎么来的：对全部"刮取器看不到"的键逐个做**差分探针**（删掉 / 改值，用 `probe_call.exe` 真调引擎看结果变不变），
  结论是该 78 个声明全是刮取器盲区（`:21-29`）。脚本自报白名单 **74 条**（`:136-137`）——
  两个数**口径不同**（78 = 声明数含重复；74 = 去重后的 `(fn,key)` 对数），本次实测确认：

```powershell
# 在 MF_UI/MFMath.UI.Vue 下（复跑口径差异；输出：未刮到的声明数(计重复)= 78  去重后的(fn,key)对数= 74）
node -e "import('./tools/engine-signatures.mjs').then(async (sig)=>{const {ENGINE_MAP}=await import('./src/lib/engine/engineMap.js');const eng=sig.scrape();const pairs=new Set();let decls=0;for (const [m,s] of Object.entries(ENGINE_MAP)){const e=eng[s.fn];if(!e)continue;const read=new Set([...(e.required||[]),...(e.optional||[])]);for (const a of s.args||[]){if(read.has(a.key))continue;decls++;pairs.add(s.fn+'|'+a.key);}}console.log('未刮到的声明数(计重复)=',decls,' 去重后的(fn,key)对数=',pairs.size);})"
```

---

## 3. `check-ui.mjs` 的 17 条守卫逐条

文件大小 33,522 字节（32.7 KB，DECISIONS.md D-007 的"代价 ①"引用的是这个数）。
下面所有行号都指 `MF_UI/MFMath.UI.Vue/tools/check-ui.mjs`。任一 `problems` 非空即 `exit 1`（`:552-556`），
`warnings` 只打印不失败（`:548-551`）。

| # | 守卫 | 判据（行号） | 拦下的真实缺陷 | 本次实测输出 |
| --- | --- | --- | --- | --- |
| 1 | 教程 target 覆盖 | 扫描源码 `:43-68`（只看 `.vue`/`.js`，跳过路径含 `tutorials/` 的目录 `:50`）；缺 `data-tour` 又不在 `PENDING` `:83`；两边都有→警告 `:87`；`PENDING` 过时 `:92`；`REGISTERED` 声明了但源码没有 `:97` | v1 的 66 个引导步骤里 **34 个目标控件根本不存在**，而 walkthrough 找不到控件时静默跳过并标记"已完成"（`:1-7`） | `data-tour 38 个` / `教程引用 target 30 个（已实现 30，待实现 0）` |
| 2 | 键盘键数、键区与分类 | 键数 `KEY_COUNT !== V1_KEY_COUNT` `:102-104`；分类缺名或键区 `:106`；缺键面 `:109`；缺插入值 `:110`；`▢` 残留 `:111`；`\begin{}` 无配对 `\end{}` `:112-117`；分类名与顺序 `:119-122` | v1 的 `\begin{pmatrix}` 缺后半截（`:113-116`） | `126 键（v1 也是 126）`、`6 分类` |
| 3 | 键面可读性 | `showsRawLatex(face)` `:132-134`；`faceStats.math === 0` `:136-138` | 模板类键把 LaTeX 源码直接画在键上，用户看到一串反斜杠与花括号（`:124-127`） | `排版 13 键 / 文字 109 键 / 紧凑替代 0 键 / 清理后文字 4 键（裸 LaTeX 0 键）` |
| 4 | 教程数据字段合法性 | `version` `:143`；`actionType ∈ {null,click,type,select,wait}` `:141,145`；`highlight ∈ {rect,circle}` `:146`；`placement ∈ {top,bottom,left,right}` `:147` | 字段取值漂移会让渲染层静默退化 | 无输出（全绿） |
| 5 | 引擎映射重复键 | `checkDuplicateKeys()` `:155-196`，对 `engineMap.js` 与 `engineMapExtra.js` 各跑一次 `:197-198` | `engineMapExtra.js` 的 `Laurent级数` VAR_SPECS 重复，后者丢了 `展开中心 z0` 且**生效**，把"展开项数"当展开中心喂给引擎（`:152-154`） | 无输出（全绿） |
| 6 | 引擎模式可达性 | 正向：映射里有、任何页面都选不到、且 `fn` 未被页面覆盖 `:236-241`；反向：`NOT_EXPOSED` 过时条目 `:243-251` | 首次跑出 **64 个**"引擎有映射、页面一个都没挂"的模式（`:202-204`）；藏得住的原因是用例 `setBlock` 找不到模式时只 `return 'no-mode'`，被静默吞掉（`:206-208`） | `映射 415 个 / 页面并集 391 个 / 取不到 0 个（已登记 0 个）` |
| 7 | 区间参数契约 | 固定列出走 `get_interval` 的 10 个 handler `:270-274`，其模式必须声明 `args` 里有 `interval` 键 `:279-283` | BUGS.md **B1**：`real_analysis_api.cpp:34-44` 的 `get_interval` 只读 `args["interval"]`，而 10 个模式要么声明 `a`/`b`、要么一个区间参数都没有 → 用户填的区间**从来没进过引擎**，界面却毫无提示（`:258-263`） | `10 个 handler / 命中模式 10 个 / 缺 interval 0 个` |
| 8 | 概率表契约 | 用**真实构造器 + 自带默认值**跑 `buildEngineArgsFromValues` `:299-313`，凡 `type === "prob_table"` 的参数必须非空 | BUGS.md **B2②**：`P` 恒为空对象 —— 弹窗字段与 `args` 语义错位，`probTableOf` 找不到 `=` 返回 `{}`；**用户点开弹窗什么都不改、直接点计算就会失败**（`:290-297`） | `4 个模式 / 空表 0 个` |
| 9 | 重名模式登记 | `DUPLICATE_NAME_GROUPS` `:330-346`；未登记且"名字选不到但 `fn` 被页面覆盖" `:395-399`；登记了却已能选到→过时 `:400-406` | BUGS.md **B10**：判据原本是"名字可选到**或** fn 被覆盖"，于是 24 个名字在界面上根本选不到却一路静默通过（自检还打印"取不到 0 个"）（`:321-329`） | `已登记 24 个，未登记 0 个` |
| 10 | 冻结的 Vue 绘图组 | 白名单 `FROZEN_VUE_PLOT_FILES` `:356-359`；目录里多出的 `.vue` `:365-369`；白名单里的文件消失 `:370-372`；有人 `import` 它们 `:373-388` | BUGS.md **B9**：绘图组整组迁到 React 后，6 个 Vue 文件既不参与构建、不在类型检查范围、也无用例覆盖；决定"保留为冻结的回退资产"，但冻结必须**看得见**（`:348-355`） | `6/6 个文件在位，被 import 0 处` |
| 11 | i18n 文案（`t()` 字面量） | 只认键里含中文的 `t("…")` 调用 `:433`，缺 `en-US.js`/`en-modes.js` 译文即失败 `:438-441` | 译文表以**中文原文为键**，改中文原文等于改 key → 英文界面**静默回退成中文**（`:411-419`） | `已用 t() 包裹 50 条，缺译文 0 条` |
| 12 | i18n 模式名 | 按 `ENGINE_MAP/EXTRA_MAP` 全部模式名对账 `:447-451` | `t(m)` 传的是**变量**，第 11 条看不见它（`:444-446`） | `415 个模式，缺译文 0 个` |
| 13 | i18n 弹窗字段 | `ENGINE_VAR_SPECS` 里所有字段名对账 `en-vars.js` `:455-462` | 同上，`t(f[0])` 是变量 | `186 条唯一标签，缺译文 0 条` |
| 14 | i18n 结果标签 | `FIELD_LABELS` 对账 `en-results.js` `:467-470` | 同上，渲染出口 `labelOf()` 传的也是变量 | `78 个字段，缺译文 0 个` |
| 15 | i18n 键盘分类 | 6 个分类名 `:475-476` | 分类名渲染在 `kp-tab` 上；键面**不翻译**（要保 v1 字样，`keyFace.js` 还要按数学排版它，`:473-474`） | `6 个分类，缺译文 0 个` |
| 16 | 端到端用例登记 | 正向：`tests/cdp-*.mjs` 必须出现在 `run-all.ps1` 的登记里，否则失败 `:503-506`；反向：登记了但文件不存在 `:507-510`；`NOT_IN_SUITE` 白名单当前为空 `:492` | 已复发过一次：`cdp-engine-coverage` 曾长期没登记；`cdp-plot-accuracy` **躺在磁盘上却从未被执行**，而它恰恰是唯一按几何判据验证绘图的用例（BUGS.md **B7**，`:480-488`） | `cdp-* 48 个，已登记 48 个` |
| 17 | 样本 fixture 重复键（**只警告**） | 正则 `(?:^\|[,\s])"([^"]+)":` `:528` —— 刻意不用行首锚点，否则紧凑行里的第二个键会被整个漏掉 `:524-527` | 重复键后者胜、前者是**长得像真的死条目**，这一轮就被它误导过（BUGS.md **B15**，`:514-520`） | `287 个键 / 重复键 0 个` |

### 3.1 这些守卫**覆盖不到**的边界（写下来，免得被当成全覆盖）

| 边界 | 代码 | 实测 |
| --- | --- | --- |
| 用例登记只认 `cdp-*.mjs` | `:500` 的正则 `^cdp-.*\.mjs$` | `tests/` 下另有 `unit-*.mjs` **4** 个、`reset-appearance.mjs` **1** 个，不在守卫范围（`Get-ChildItem MF_UI/MFMath.UI.Vue/tests/unit-*.mjs`）；`unit-*` 的**增减不会让这道闸门变红** |
| 登记是在 `run-all.ps1` **全文**里做正则匹配，不解析 `$tests` 数组 | `:498` 的 `"([a-z0-9-]+)"` | 本次实测：加一行注释 `# …提到 "cdp-zzz-ghost"…` ⇒ `✗ tests/run-all.ps1 登记了 cdp-zzz-ghost，但 tests/cdp-zzz-ghost.mjs 不存在`、`exit 1`。也就是说**注释里的引号名字也算登记**（反向检查因此能兜住笔误） |
| `data-tour` 扫描跳过 `src/tutorials/` 下的文件 | `:50` | — |
| 模式可达性只比对 `ENGINE_MAP`/`EXTRA_MAP` 与 `VIEW_CONFIGS`，不比对引擎 | `:231-234` | `VIEW_CONFIGS` 实测 **14** 个页面（见 §6 的债 C1） |
| 不检查 `tests/fixtures/mode-samples.mjs` 的**语义**，只查重复键 | `:521-537` | fixture 过期曾在 `audit-modes` 上表现为 391/2（BUGS.md §0.2 第 4 条） |

---

## 4. 元规矩：每条守卫都必须验证过"它会失败"

**只写一条永远为真的断言，等于没写。** 这是 [DECISIONS.md](../DECISIONS.md) D-007 附加的元规矩（`:122-123`）。
加守卫的标准动作是三步：**临时制造违反 → 确认自检报错并 `exit 1` → 还原**。

### 4.1 本文本次实测的 9 个反例（2026-10-07，`HEAD e77fdb8`）

做法：把 `MF_UI/MFMath.UI.Vue` 的 `tools/`、`src/`、`tests/` 复制到
`MF_UI/MFMath.UI.Vue/.tmp-checkverify/`（`.tmp-*` 已被 `.gitignore` 覆盖，见 [`../../AGENTS.md`](../../AGENTS.md) §6），
在副本里制造违反，跑完整个副本删掉 —— 真实树一次都没动（收尾 `git status --short` 干净）。

| 守卫 | 制造的违反 | 实测结果 |
| --- | --- | --- |
| 教程 target（#1） | 把 `tutorials.json` 第一篇第一个步骤的 `target` 改成 `docverify.nonexistent` | `✗ 教程 target 「docverify.nonexistent」（1 处）既不在源码的 data-tour 里，也没写进 PENDING 说明理由`，`EXIT=1` |
| 键盘键数（#2） | `keypadSymbols.js` 的 `ALL_KEYS = flatten()` 改成 `flatten().slice(1)` | `✗ 键盘键数 125 ≠ v1 的 126`，`EXIT=1` |
| 映射重复键（#5） | 在 `engineMapExtra.js` 的 `EXTRA_MAP` 里把 `"达布和"` 那一行原样再插一遍 | `✗ engineMapExtra.js 的 EXTRA_MAP 里「达布和」重复 2 次（后者胜，前面的是死条目）` |
| 模式可达性（#6） | 往 `EXTRA_MAP` 注入 `"文档债验证模式": { fn: "docverify_unique_fn", … }` | `✗ 模式「文档债验证模式」（docverify_unique_fn）没有任何页面能选到，也没登记进 NOT_EXPOSED` |
| 区间参数契约（#7） | 把 `"达布和"` 的 `args: [EXPR, INTERVAL]` 改成 `[EXPR]` | `✗ 模式「达布和(darboux_sum)」的 handler 用 get_interval 读区间，但 args 里没有 interval 键 …`，`EXIT=1` |
| 概率表契约（#8） | 把 `条件概率` 弹窗默认值里的 `A_and_B=0.2; B=0.5` 删空 | `概率表契约：4 个模式 / 空表 1 个` + `✗ 模式「条件概率.P」用弹窗默认值构造出来是**空概率表** …`，`EXIT=1` |
| 冻结资产（#10） | 往 `src/views/plot/` 加 `PlotDocVerify.vue` | `✗ src/views/plot/PlotDocVerify.vue 不在"冻结的回退资产"白名单里 …`，`EXIT=1` |
| i18n 文案（#11） | 在 `viewConfigs.js` 末尾加 `t("文档债验证未翻译键")` | `✗ i18n：t("文档债验证未翻译键") 在 lib/i18n/en-US.js 里没有译文（lib\engine\viewConfigs.js）`，`EXIT=1` |
| 用例登记（#16） | 建一个空的 `tests/cdp-zzz-docverify.mjs` | `✗ tests/cdp-zzz-docverify.mjs 没有登记进 tests/run-all.ps1 —— 它永远不会被执行 …`，`EXIT=1` |

副本基线（未制造违反时）`node tools/check-ui.mjs` = `EXIT=0`，还原后再跑仍为 0 —— 说明失败确实由注入引起，不是环境。

⚠ 表中 #5、#6 两行**没有单独捕获到退出码**：那两条与 #7 是一批跑的，命令写成 `node … *>&1 | Select-String …`，
管道把 `$LASTEXITCODE` 吞了（#7 单独重跑后捕到 `EXIT=1`）。`problems` 非空必然 `exit 1`（`:552-556`），
但严格说这两行的"`exit 1`"是**由代码推断**，不是本次实测到的。要复现就按上面的注入方式单独跑一次并读 `$LASTEXITCODE`。

### 4.2 仓库里已登记"验证过会失败"的实例

| 守卫 | 记录位置 | 记法 |
| --- | --- | --- |
| 区间参数契约（B1） | [`../../MF_UI/BUGS.md`](../../MF_UI/BUGS.md) §0.1 表 B1 行 | "另加 check-ui 守卫「区间参数契约」并**验证它会失败**" |
| 概率表契约（B2②） | 同上 B2 行 | "另加 check-ui 守卫「概率表契约」并**验证它会失败**" |
| 用例登记（B7） | 同上 B7 行 | "造一个未登记用例 → 自检失败（已验证）" |
| 冻结资产（B9） | 同上 B9 行 | "**验证过会失败**（造一个 import → 报错 exit 1）" |
| 重名登记（B10） | 同上 B10 行 | "**验证过会失败**（去掉一条登记 → 报错 exit 1）" |
| 参数契约（`check:args`） | 同上 `:286-287` | "临时给「达布和」注入一个引擎不读的 `bogus_key` ⇒ 立即报出该模式该键并 `exit 1`，还原后 `exit 0`" |

⚠ **本文未复验**的守卫：#3 键面可读性、#4 教程字段合法性、#9 重名登记、#12–#15 四条 i18n 对账、#17 fixture 重复键。
它们的判据与行号来自本次通读源码；要复验就按 §4.1 的副本法逐个制造违反。

---

## 5. 设计取舍：`check-ui.mjs` **刻意不读引擎源码**

`check-ui.mjs` 的 14 条 import（`:18-31`）全部指向 Vue 包内部，**没有任何一条**碰到引擎树：

```powershell
# 在 MF_UI/MFMath.UI.Vue 下：
Select-String -Path tools/check-ui.mjs -Pattern "MF_Mathematics|MF_ENGINE_ROOT|engine-paths|scrape\("
# （无输出）
```

### 5.1 为什么这么定

引擎源码是**树外路径**（`<v2.0>/MF_Mathematics`，与前端仓库不是同一棵）。若自检去读它，
换台机器 / 进 CI / 只检出前端时整条 `npm run check` 就跑不动（`MFMath.UI.Vue/tests/engine-paths.mjs:1-17` 记的就是被这件事咬过的经过：路径曾被硬编码，且其中两条指向**完全另一棵树**）。

### 5.2 代价（DECISIONS.md D-007 已登记，这里给可核对的证据）

1. **它检查的是登记表，不是真源码** —— 例如"区间参数契约"不读 `real_analysis_api.cpp`，而是把 10 个 handler 名写死在
   `INTERVAL_FNS`（`:270-274`）里。**引擎新增同类 handler 时必须把名字加进来**，否则守卫对着旧清单继续报绿（`:264-269` 自己写明了这一点）。
2. **同一个取舍没有覆盖整条 `check`**：第 2 段 `engine-signatures.mjs:32`、第 3 段 `check-arg-contract.mjs` 都读引擎树。
   也就是说"让自检在别的机器上跑得动"只对 `check-ui.mjs` 这一段成立。
3. **那两段还绕过了 B8 立的规矩**：引擎路径没有走 `tests/engine-paths.mjs` 的 `requirePath`，也不认环境变量覆盖。
   本次实测（把脚本放到一棵解析不到引擎的目录下跑）：

   ```
   Error: ENOENT: no such file or directory, scandir '…\.tmp-pathverify\MF_Mathematics'
       at walk (…/engine-signatures.mjs:62:24)
   ```

   即：抛裸 `ENOENT` 堆栈、`exit 1`，而不是像 `engine-paths.mjs:52-58` 那样打印"请把 `$env:MF_ENGINE_ROOT` 指对"。
   这条差异已记进 §7 的文档债 C3。

---

## 6. 加一条守卫的规矩

按这个顺序做，做完 `npm run check` 必须整条 `exit 0`（`:552-556` 的出口只有一个）。

| 步 | 做什么 | 为什么 / 出处 |
| --- | --- | --- |
| 1 | **先有真实缺陷，再写守卫。** 在 `MF_UI/BUGS.md` 或 `docs/DECISIONS.md` 里登记"这条守卫拦哪一类缺陷" | 没有真实缺陷的守卫会变成装饰；D-007 的背景就是 v1 的 34/66 |
| 2 | 判断进 `problems`（硬失败）还是 `warnings`（只提示） | 只有**确定的错**才进 `problems`：`engine-signatures.mjs:146-150` 写着"吵闹的守卫比没有守卫更糟 —— 它会变成没人信的摆设"；#17 因此只警告 |
| 3 | 登记表类守卫必须**双向校验** | `PENDING` `:90-94`、`NOT_EXPOSED` `:243-251`、`DUPLICATE_NAME_GROUPS` `:400-406`、`NOT_IN_SUITE`/登记反向 `:507-510`：登记了却已经不需要 → 报"过时条目"，逼人删 |
| 4 | 白名单每一条都要**带判据字符串** | `check-arg-contract.mjs:41-44` 明写"拿不出判据就别加 —— 白名单只会越长越没人信" |
| 5 | **制造一次违反，确认它失败**，再还原 | §4 的元规矩；在 `.tmp-*` 副本里做，别动真实树 |
| 6 | 如果守卫的输入是"登记表"而不是真源码，把这句话与**不读源码的原因**写进脚本注释 | §5；`check-ui.mjs:264-269` 就是范例 |
| 7 | 同步更新 README / `docs/` 的清单与计数（修完就删过时条目） | [README.md](../README.md) §4 第 5 条；漏更新就是下一个债 |
| 8 | 复跑 `npm run check` 与 `npm run check:types --prefix MF_UI/MFMath.UI.React` | `AGENTS.md` §7 的收口清单 |

**代价要有心理准备**：守卫本身是 32.7 KB 需要维护的代码，且**加一个界面就要同步加登记**
（DECISIONS.md D-007 代价 ①）。这是"把运行时不可察觉的问题挪到构建期"的必然账单。

---

## 7. 已知的文档债

规则同 [`../README.md`](../README.md)：注释/旧文档说 X、代码做 Y 时**以代码为准**。
编号接 [README.md](README.md) §8 的 D1–D7，本文新增的从 **C** 起编（避免与那份撞号）。

| # | 位置 | 注释/旧文档说 | 代码/实测做 | 严重度 |
| --- | --- | --- | --- | --- |
| **C1** | `tools/check-ui.mjs:203` | "viewConfigs 的 **13** 个页面模式表**一个都没挂**" | 实测 `VIEW_CONFIGS` 有 **14** 个键：`algebra / algebraic-topology / analytic-geometry / calculus / complex-analysis / functional-analysis / linear-algebra / measure-theory / number-theory / numerical / probability / real-analysis / sequences / harmonic-analysis`（`node -e "import('./src/lib/engine/viewConfigs.js').then(m=>console.log(Object.keys(m.VIEW_CONFIGS).length))"`）。前半句（"一个都没挂"）是**当时**的事实，数字已过时 | 低（数字过时，判据不受影响） |
| **C2** | `tools/check-ui.mjs:9` | "断言（任一失败即 exit 1；共 **12** 组，此处只列要点）"，随后只列了 6 条 | 编号 12 组属实，但**判定点有 17 处**，摘要漏掉了键面可读性、概率表契约、重名登记、冻结资产、5 条 i18n 对账、fixture 重复键 | 低（摘要不完整，读者会低估覆盖面） |
| **C3** | `tools/engine-signatures.mjs:32`（同源波及 `tools/check-arg-contract.mjs:33` 的 `scrape`） | `tests/engine-paths.mjs:44-59` 立的规矩是"树外路径**唯一解析处**：环境变量 → 相对推导 → 可读报错" | 这里直接 `path.resolve(PROJECT, "..", "..", "MF_Mathematics")`，既不认 `MF_ENGINE_ROOT` 也不调 `requirePath`；缺树时抛裸 `ENOENT` 堆栈（§5.2 第 3 条的实测输出） | 中（换机器时错误信息不可操作，退回 B8 那个坑） |
| **C4** | [`../../MF_UI/BUGS.md`](../../MF_UI/BUGS.md) §0.2 第 4 条 | "现在报 `重复键 **28** 个`，非阻塞" | 同一件事在 `tools/check-ui.mjs:526` 写的是"真实重复数是 **29** 而不是 28"；**本次实测为 0**（fixture 已清理）。三处数字互不相同，且都不是现值。§0.2 自称是当时记录，但两份文档对同一次测量给出 28/29 两个数，属于**同一事实的两种说法** | 低（`warnings` 非阻塞），但引用时必须带时刻 |
| **C5** | [`../../README.md`](../../README.md):165-172 | "**构建期自检**（`npm run check` 里的 `tools/check-ui.mjs`）会拦下**这几类**"，只列 4 类 | 实际 17 条守卫（§3）。[DECISIONS.md](../DECISIONS.md):127-128 列了 9 类，README 的清单停在更早的版本 | 低 |
| **C6** | `MF_UI/MFMath.UI.Vue/src/views/HomeView.vue:59` | 用户可见文案："计算经 mf_mathematics.dll（C++），链接经 **C# MathBridge** / WebView2" | 与 [README.md](README.md) §8 的 **D1** 同源（`package.json:6` 的 description），但这一处是**界面上给用户看的字**，不只是注释。C# 宿主已废弃（[`../DECISIONS.md`](../DECISIONS.md) D-006、[`../../AGENTS.md`](../../AGENTS.md) §2）；实测全仓库 `MathBridge` 只剩 `MFMath.Host/`（废弃宿主）、注释、以及 `tests/cdp-bridge-verify.mjs:1` 的旧描述 | 中（面向用户） |
| **C7** | `tools/check-ui.mjs:231`、`:276`、`:300`、`:391` | 各自 `{ ...ENGINE_MAP, ...EXTRA_MAP }` | `engineMap.js:27` 的 `ENGINE_MAP` **已经**是 `{ ...RAW_MAP, ...EXTRA_MAP }`，所以这四处展开是冗余的（实测两种写法都得 415 个模式）。**不是缺陷**，只是别据此以为 `ENGINE_MAP` 不含 EXTRA | 低（读代码时的误导） |

**未证实项**（不替它们背书）：

1. `check-arg-contract.mjs:22,28` 的"**78** 个"与脚本自报的"白名单 **74** 条"：本次用去重/不去重两种计数复现了 78 与 74，
   因此判断为**口径差异**而非漏登记；但**没有**逐条比对当时的探针清单，不排除"有 4 条被判为不必登记而没写进注释"。
   验证方式：`git log -p MF_UI/MFMath.UI.Vue/tools/check-arg-contract.mjs`（该文件只有一次提交 `e77fdb8`，注释与代码同时诞生）。
2. 本文**没有跑** `npm run build` 与 `tests/run-all.ps1`（前者写 `dist/` 且与并行会话争资源，后者需真宿主与独占 CDP，
   [DECISIONS.md](../DECISIONS.md) D-010）。所以"闸门全绿"只覆盖 §1 表里的那五条命令。
3. 第 4 段三步各自的 `exit 1` **逐个实测过**（§4.1），但**没有**以"一次注入让多个守卫同时失败"的方式验证
   `problems` 的聚合行为（`:552-556` 的循环）。
