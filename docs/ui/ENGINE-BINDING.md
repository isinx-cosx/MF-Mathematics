# 前端怎么把界面接到引擎上

> **本文只回答一个问题：前端怎么把界面接到引擎上，以及为什么前端一行数学都不算。**
>
> 与同层其它文档的分工：
> - [ARCHITECTURE.md](ARCHITECTURE.md) —— 目录分层、路由与导航表、i18n、样式；本文只讲"计算"这一条竖线；
> - [PLOT.md](PLOT.md) —— 绘图页的采样、视口、配色；本文只讲它里面的**同步/异步分流**那一小段；
> - [AI.md](AI.md) —— AI 面板、SSE、步骤视图；本文只讲"AI 也不许自己算"这条硬约束；
> - [CHECKS.md](CHECKS.md) —— 四道构建闸门怎么跑、守卫为什么必须"验证过会失败"；本文只给可达性守门的**行号**；
> - [../engine/CONTRACT.md](../engine/CONTRACT.md) —— 契约的另一半：引擎侧的 args 形状与"未实现"返回形状。

**取证时刻**：2026-10-07 10:50–11:05（+08:00），工作树在 commit `e77fdb8`。
除 §8 里明标"未跑"的两条外，本文的数字都由 §8 的命令在本次复跑得到；
**没有复跑过的**（性能基准、"未实现的返回形状"之类）在文中单独标注为"未证实"。

---

## 1. 结论：前端只做三件事，一件都不是"算"

| 前端负责 | 载体 | 具体做什么 |
| --- | --- | --- |
| **参数构造** | `src/lib/engine/calcArgs.js` | 把"中文模式名 + 用户输入"变成引擎要的 args JSON（键名、类型、必填/可选） |
| **传输** | `src/lib/bridge.js` | `hostObjects.sync.mf.Dispatch(name, JSON.stringify(args))`；重的活走 `DispatchJob`/`PollJob` |
| **展示** | `src/lib/engine/resultModel.js`、`resultFormat.js`、`components/calc/ResultDialog.vue` | 判定"哪一段是数学"、KaTeX 排版、数值格式化、历史摘要 |

`window.chrome.webview.hostObjects.sync.mf` 这个对象在 `bridge.js:90-96` 里取，
它**同步阻塞渲染进程主线程**（`src/types/webview.d.ts:10-11`、`:24`）—— 这是 §6 分流存在的全部理由。

### 1.1 为什么不让前端顺便算一下

| 理由 | 出处 |
| --- | --- |
| 单一计算来源：前端也能算 ⇒ 同一个问题两个来源，不一致时用户无法判断哪个对 | [DESIGN.md](../DESIGN.md) §2 ①（`:26-39`） |
| 语法归一化只允许发生在引擎里一处；`toEngineExpr` 现在**不做任何算符替换**，只做 `String()` | `src/lib/engine/calcArgs.js:33-35` |
| 结果里的数学排版曾经是前端拼 HTML 的 ASCII 近似（`mathHtml()`），已废弃 | `src/lib/engine/resultFormat.js:4-7` |
| LaTeX 也是问引擎要的：`prepare_expr` / `sym_latex` / `to_engine_expr` 三个都是 `engineCall` | `src/lib/plot/prepare.js:21-42`、`:49-58`、`:65-98` |
| AI 也只能调引擎：工具的入参表就是 `ENGINE_MAP` 的 args，且**只走 `engineCall`**，绝不碰 `win`/`sys`/`con` | `src/lib/ai/tools.ts:9-16`、`:11` |
| 硬约束用例：假端点故意回 `1+1=3`，断言结果区仍是引擎的值 | `tests/cdp-ai.mjs:8-9`、`:696-728` |

### 1.2 这条"不算"的**准确边界**（别读成"前端什么都不过手"）

| 前端确实会做的 | 它为什么不算"计算" | 出处 |
| --- | --- | --- |
| 决定**在哪些点**问引擎：`linspace(a,b,n)` 生成采样横坐标 | 这是视口/像素问题（"图要画在哪几个位置"），不是"函数值是多少" | `MFMath.UI.React/src/plot/usePlotSampling.ts:48-53`、`:206-207`；参数曲线用 `linspace(0, Math.PI*2, 300)`（`:141`） |
| 数值格式化为显示文本：`fmtNum` | 它不改数值、不产生新数值，只决定小数点后几位 | `src/lib/engine/resultFormat.js:33-50` |
| 判定"这段文本按数学还是按文字显示" | 判定失败一律退回纯文本，宁可不排版也不猜 | `src/lib/engine/resultModel.js:153-159` |

一切**函数值/解/根/积分/特征值**都只在引擎里产生：绘图页三条求值路径全部是
`expr_eval_vars_batch`（`usePlotSampling.ts:59`）、`expr_eval_grid`（`:208`）、
`expr_eval_vars`（`MFMath.UI.React/src/plot/PlotPage.tsx:432`）；
交点/极值走 `intersections`（`:263`）、`local_extrema`（`:298`）、`extrema_sym`（`:314`）。

---

## 2. 一条计算从界面到引擎的完整链路

以计算页（`/calc/<学科>`）为例：普通模式走这条线，需要多参数的模式在 ③ 处分叉进弹窗，再回到 ⑤。

```
① 用户输入            math-field / <input>            CalcView.vue 的 block.expr
② 点「计算」          CalcView.calc()                 CalcView.vue:263-302
③ 模式查表            ENGINE_MAP[mode]                CalcView.vue:268-273（查不到 → unmappedHint，:230-234）
③' 需弹窗？           needsVarDialog(mode)            calcArgs.js:450-452 → MultiVarDialog.vue
④ 构造 args           buildEngineArgs / …FromValues   calcArgs.js:262-336 / :352-443（内部分步①~⑥，见 §3）
④' 必填缺失？         拒绝计算，不兜底                CalcView.vue:291-299、:360-369
⑤ 分流                shouldRunAsync(fn, args)        CalcView.vue:316-325 → asyncPolicy.js:69-77
⑥ 过桥                engineCall / engineCallAsync    bridge.js:127-136 / :160-233
⑦ 宿主                mf.Dispatch → engine.call_json MFMath.Host.Rust/src/handlers.rs:307-319
⑧ 引擎                C ABI → JSON 信封 {isError,value}
⑨ 展示                toResultNodes / fmtNum / KaTeX  resultModel.js:197-224、ResultDialog.vue:30-36
⑩ 记账                历史摘要 briefValue              CalcView.vue:386-392、resultModel.js:253-281
```

| 步 | 关键事实 | 出处 |
| --- | --- | --- |
| ② | 输入框空且该模式确实需要输入 → 只提示"请输入表达式"，不调引擎 | `CalcView.vue:265`、`modeNeedsInput` `:242-243` |
| ③ | 页面的模式下拉来自 `VIEW_CONFIGS`，按**路由末段**取（`/calc/algebra` → `algebra`） | `CalcView.vue:33-36`、`viewConfigs.js:13`、`:532-534` |
| ③' | 有 `ENGINE_VAR_SPECS[mode]` 的模式先弹窗收参数，再回到 ⑤ | `CalcView.vue:276-286`、`:328-347` |
| ④ | 构造 args 的内部分步（①~⑥）见 §3 | `calcArgs.js:262-336` |
| ⑥ | 无宿主 → `engineCall` 返回 `null`（**不是错误**，浏览器预览就是这个形态） | `bridge.js:128-129`；`CalcView.vue:373-375` 显示"未检测到引擎桥" |
| ⑥ | 桥抛异常 → 包成 `{isError:true, value:"桥调用失败: …"}`，**不往外抛** | `bridge.js:133-135` |
| ⑦ | 方法名**大小写敏感**：`Dispatch`（写成 `dispatch` 会抛 `0x80070057`） | `bridge.js:3-5`；宿主侧登记名见 `MFMath.Host.Rust/src/main.rs:68` |
| ⑦ | 宿主不认识的函数名 → `{isError:true,value:"mf 没有这个方法：X"}` | `handlers.rs:345-350`、`err_envelope` `:41-42` |
| ⑧ | args 是**一段 JSON 字符串**（不是对象）；`engineCall` 负责 `JSON.stringify` | `bridge.js:131`；`main.rs:68` 的 `params: &["name","argsJson"]` |

### 2.1 失败要分类（三种不能混着写）

| 现象 | 分类 | 判据 |
| --- | --- | --- |
| `engineCall` 返回 `null`，界面显示"未检测到引擎桥" | **环境没准备好**（没在宿主里跑） | `bridge.js:128-129`、`CalcView.vue:373-375` |
| `{isError:true, value:"桥调用失败: …"}` | 环境/宿主问题 | `bridge.js:133-135` |
| `{isError:true, value:"mf 没有这个方法：X"}` | 版本不匹配（宿主比前端旧） | `handlers.rs:349` |
| `{isError:true, value:"对象缺少键: z"}` / `"参数 n 类型错误"` | **产品缺陷**：前端声明的 args 与引擎实际读的键/类型不符 | 这类修正记在 `engineMapExtra.js:29-40`（"实测报'对象缺少键: z / z0 / s / initial'"）；键名失配的同类见 `MF_UI/BUGS.md` B1（`:281-344`）；现由 `tools/check-arg-contract.mjs` 在构建期拦 |
| `{isError:true, value:"未实现…"}` | **不是缺陷**，是如实的能力边界 | [DESIGN.md](../DESIGN.md) §2 ②（`:41-56`） |
| 下拉里某项标着「（未接入引擎）」 | 该模式不在 `ENGINE_MAP` 里 | `CalcView.vue:467-469`、`hasEngineMode` `engineMap.js:33-35` |

---

## 3. 参数构造：`calcArgs.js` 的六步

`buildEngineArgs(mode, expr, report)`（`calcArgs.js:262-336`）按固定次序处理输入框文本。
输入框支持用 **深度 0 的 `;`** 分段一次给多个参数（`splitSegments` `:60-74`），
所以"哪一段喂给谁"必须写死，否则输入会被静默喂错参数：

| 步 | 规则 | 行号 |
| --- | --- | --- |
| ① | 第一段喂给 `pickTextArg` 选出的那个参数：**先找"必填的 `string`"**；自动映射路径还要排除 `string_array`/`complex_obj`（它们要整串） | `:242-252`、`:276-291` |
| ② | `string_array` 类参数把**剩余所有段 `join(";")` 整组**吃掉（`x>1; x<3` 不能只剩 `x>1`） | `:294-298` |
| ③ | 其余**必填**参数按**声明顺序**逐段吃；段不够就记账待补 | `:301-305` |
| ④ | 还有剩余段 → 补给**可选**参数（`x^2-4; -2; 2`） | `:308-312` |
| ⑤ | 仍缺的必填 → 依次取 `ENGINE_VAR_SPECS` 字段（跳过"（输入框）"类字段）→ 还不行才 `fallbackOf` **并记账** | `:315-327`、`:200-207`、`:218-221` |
| ⑥ | 其余可选参数 → 弹窗字段；**没有就整个键省略**，让引擎用自己的默认值 | `:330-334` |

弹窗路径 `buildEngineArgsFromValues(spec, fields, values, report)`（`:352-443`）有四处**有意不同**：

| 差异 | 为什么 | 行号 |
| --- | --- | --- |
| 判"输入框是否为空"看 `boxText.trim() === ""`，不看 `segments` | `splitSegments("")` 返回空数组，用段数判断会恒判成"有输入"，字段队列整体错位一格 | `:358-363` |
| 空输入框时**第 0 格自己是有值的**（如乘积测度默认 `lebesgue`），要用它而不能跳过 | 早先整个跳过 ⇒ `mu` 没传给引擎 ⇒ `product_measure` 抛"值不是数字" | `:403-426` |
| 概率表（`prob_table`）把**整串 join 回去**，且此时 `ui` 必须为 0 | `;` 在表内是表项分隔符、在参数间是分段符，两种语义撞车（BUGS.md B2①） | `:279-291`、`:369-372`、`:379-386`、`:402` |
| 段已经填过的参数，弹窗字段要同步跳过（`ui = seg - 1`） | 否则同一参数被段和字段各填一次（交换律验证把运算符填成了 b） | `:400-402` |

类型转换集中在 `convertArg`（`:160-190`）+ `STRUCTURED` 集合（`:53-57`）。
**解析不出来时原样返回文本**，让引擎抛它自己的中文错误 —— 在这里静默塞 `0`/`1` 才是真正难查的失败（`:155-159`）。

### 3.1 兜底不静默：`noteDefaulted` → 拒绝计算

`fallbackOf` 给的 `0` / `[0,0]` / `[]` / `""` **在引擎眼里都是合法值**（`:200-207`），
引擎不会报错，而是拿它们算出一个"看起来很正常的错结果"。所以：

1. 每用一次兜底就 `noteDefaulted(report, a)` 记账（`:218-221`）；
2. `CalcView` 拿到 `report.defaulted` 非空就**拒绝调引擎**，直接说清缺什么、怎么补
   （`missingRequiredText` `CalcView.vue:360-369`，调用点 `:291-299`、`:334-342`）；
3. 走这条拒绝路径的前提是**样本齐全**：10 个页面模式的 fixture 已补并用真引擎验过
   （`CalcView.vue:349-359` 的说明、`MF_UI/BUGS.md` B4 `:487-496`）。

---

## 4. 三张表各管什么

| 表 | 文件:行 | 回答什么 | 规模（2026-10-07 复跑） |
| --- | --- | --- | --- |
| `RAW_MAP` | `engineMap.js:22` | 旧版 `MFMath.UI/js/engine-map.js` 的**自动转换快照**，保原样 | 324 |
| `EXTRA_MAP` | `engineMapExtra.js:28` | **增量与修正**：新增映射 + 参数/键名修正（同名覆盖前者） | 164（与 `RAW_MAP` 同名 73 ⇒ 合并 415） |
| `ENGINE_MAP` | `engineMap.js:27` | `{...RAW_MAP, ...EXTRA_MAP}` —— **中文模式名 → `{fn, module, args}`**，是"前端发哪些键"的唯一来源 | **415** |
| `RAW_VAR_SPECS` | `engineMap.js:24` | 旧版多参数弹窗字段快照 | 19 |
| `EXTRA_VAR_SPECS` | `engineMapExtra.js:380` | 弹窗字段的增量/覆盖 | 130（与 RAW 同名 10 ⇒ 合并 139） |
| `ENGINE_VAR_SPECS` | `engineMap.js:28` | **模式名 → `[[字段标签, 默认值], …]`**；有它才弹窗（`needsVarDialog` `calcArgs.js:450-452`） | **139** |
| `VIEW_CONFIGS` | `viewConfigs.js:13` | **14 个学科页 → `{title, desc, modes, single}`**，即"用户能选到哪些模式" | 14 页 / 393 条 / 去重 391 |
| （对照）`engine-signatures.json` | `src/lib/ai/engine-signatures.json` | 引擎**全部 action** 的签名表，工具箱与 AI 工具表的唯一数据源 | 424；模式表只覆盖其中 **371**，另 53 个只由工具箱暴露 |

| 表 | 谁消费 | 加东西时改哪 | 规矩 |
| --- | --- | --- | --- |
| `ENGINE_MAP` | `calcArgs`、`CalcView`、`tools.ts`、`check-ui.mjs`、`check-arg-contract.mjs` | **只改 `engineMapExtra.js`** | `engineMap.js:16` 明写"不要在这份自动生成的内容里改" |
| `ENGINE_VAR_SPECS` | `CalcView`（弹窗，`:276-286` 把它作为 `fields` 传给 `MultiVarDialog.vue`）、i18n 自检 | 同上 | `args` 里**可选参数的先后顺序**必须与字段顺序一致（`engineMapExtra.js:10-12`） |
| `VIEW_CONFIGS` | `CalcView`（下拉框） | `viewConfigs.js` | 新增模式必须挂进某个页，否则 `check-ui.mjs` 的可达性守卫失败（§5） |

### 4.1 两个必须记住的键名契约（都是"填了不生效"类）

| 契约 | 内容 | 出处 |
| --- | --- | --- |
| `interval` | `real_analysis` 一族 handler 只读 `args["interval"]` 且必须是 **2 元数组**，读不到就恒定 `[0,1]`；10 个模式原先一个区间参数都没声明 | `engineMapExtra.js:23-26`、`:356-377`；`MF_UI/BUGS.md` B1（`:281-344`） |
| `;` 的双语义 | 参数分段符 vs 概率表项分隔符；`prob_table` 必须整串吃 | `calcArgs.js:279-291`；`MF_UI/BUGS.md` B2①（`:351-365`） |

新闸门 `tools/check-arg-contract.mjs` 专门守这一类：**UI 声明的每个参数键都必须有证据说明引擎真的读它**
（① 刮取器看到 `get_xxx(args,"K")`，或 ② 在 `HELPER_READ` 白名单里并写明判据），否则 `exit 1`
（`:114-133`、`:145-152`）。跑法见 §8，输出 `415 个模式 / 检查 934 个声明键`、白名单 74 条、`exit 0`。

---

## 5. 可达性守门：模式要么选得到，要么显式登记

判据在 `tools/check-ui.mjs`，**两档 + 双向**：

| 机制 | 行号 | 做什么 |
| --- | --- | --- |
| `NOT_EXPOSED_GROUPS` 定义 | `check-ui.mjs:213-226` | `["原因", ["模式名", …]]`；**目前是空数组**（`[]`），因为最后三条（柯西定理/辐角原理/Rouche 定理）已改用参数弹窗挂回复分析页 |
| 展开成 `NOT_EXPOSED` Map | `:227-228` | 模式名 → 原因 |
| **正向**校验 | `:236-241` | 名字不在任何页面 `modes` 里、且它映射的 `fn` 也没被页面别的模式覆盖、且没登记 ⇒ **硬失败** |
| **反向**校验（过时条目） | `:242-251` | 登记了却在页面上能选到（或 fn 已被覆盖）⇒ 报"现在已经能在页面上选到了 —— 过时条目，请删除" |
| 打印口径 | `:252-255` | `引擎模式可达性：映射 N 个 / 页面并集 M 个 / 取不到 K 个（已登记 …）` |
| 第二张登记表 `DUPLICATE_NAME_GROUPS` | `:330-346` | "**名字**选不到、但 fn 已被页面覆盖"的重复命名（BUGS.md B10） |
| 6d 正向 | `:395-399` | 这类名字**必须登记**，否则失败 |
| 6d 反向 | `:400-406` | 登记了却能选到 ⇒ 过时条目 |

判定顺序很重要：正向校验先 `pageModes` → 再 `pageFns` → 再 `NOT_EXPOSED`（`:237-239`），
所以"同一个 action 换个名字挂在页面上"**不算缺口**，但**也不许静默** —— 它必须落进
`DUPLICATE_NAME_GROUPS`（`:329` 的注释写明了这次收紧的来由）。

### 5.1 当前状态（2026-10-07 复跑 `node tools/check-ui.mjs`，exit 0）

```
引擎模式可达性      ：映射 415 个 / 页面并集 391 个 / 取不到 0 个（已登记 0 个待补或无处安放）
区间参数契约        ：10 个 handler / 命中模式 10 个 / 缺 interval 0 个
概率表契约          ：4 个模式 / 空表 0 个
重名模式登记        ：已登记 24 个，未登记 0 个
```

| 数字 | 含义 | 备注 |
| --- | --- | --- |
| 映射 415 / 页面并集 391 | 415 个模式里，391 个能在页面下拉里选到 | 差额 24 个正是 `DUPLICATE_NAME_GROUPS` 那 24 个**旧名字**；它们的功能由同 fn 的页面模式提供（BUGS.md B10 `:785-800` 有逐条对应表） |
| 取不到 0 / 已登记 0 | `NOT_EXPOSED_GROUPS` 为空且没有遗留缺口 | 第一次跑这项自检时是 **64 个**（`check-ui.mjs:202-204`） |
| 393 条 vs 391 去重 | 14 个页面共 393 条模式条目，去重后 391；重复的 2 个名字是 `逆Fourier变换`（calculus + harmonic-analysis）、`正交投影`（functional-analysis + linear-algebra） | 复跑命令见 §8 |
| 页面有、模式表没有：0 | 没有"下拉里挂着却查不到 fn"的死项 | 同上 |

**同一份自检里与本文直接相关的另两条守卫**（它们是 B1/B2 的回归判据）：

| 守卫 | 行号 | 断言 |
| --- | --- | --- |
| 区间参数契约 | `:258-288` | 固定列出 10 个由 `get_interval` 读区间的 handler，每个对应模式的 `args` 里必须有 `interval` 键 |
| 概率表契约 | `:290-319` | 参数含 `prob_table` 的 4 个模式，用**弹窗自带默认值**跑真实构造器，每个 `prob_table` 参数必须非空 |

两条都按 `DESIGN.md` §2 ③ 的规矩**验证过会失败**（`MF_UI/BUGS.md` B1 `:340`、B2 `:386`）：
临时制造一个违反、确认 `exit 1`、再还原。只写一条永远为真的断言等于没写。

### 5.2 这条守门的边界（它**不**覆盖什么）

| 不覆盖 | 说明 |
| --- | --- |
| `engine-signatures.json` 里那 53 个不在 `ENGINE_MAP` 的 action | 它们的入口是**函数工具箱**（`views/tools/ToolboxView.vue:46` 以 424 条签名表为数据源），不走模式下拉，因此不在可达性判据里 |
| `ENGINE_VAR_SPECS` 里**悬空**的键 | 当前 2 个：`数值微分`、`矩阵乘法`（无 `ENGINE_MAP` 条目）；`check-ui.mjs` 没有针对它的断言（`MF_UI/BUGS.md` B10 `:760-764` 登记了这件事，现状与登记一致） |
| 页面是否存在 | 本自检只做**静态**表运算，不启动浏览器、不点界面 |

---

## 6. 同步还是后台：`asyncPolicy.js` 的三条判据

`shouldRunAsync(name, args, opt)`（`asyncPolicy.js:69-77`）依次判：

| 判据 | 条件 | 数据 | 行号 |
| --- | --- | --- | --- |
| ① 强制 | `opt.force === true` ⇒ 异步 | 工具箱的「强制后台」勾选 | `:70`；`ToolboxView.vue:142` |
| ② 无上界 | `ALWAYS_ASYNC.has(name)` ⇒ 异步 | **28** 个符号/数值重活（积分/求和/级数、符号求解与化简、数论与矩阵） | `:39-49` |
| ③ 按规模 | 在 `BY_SIZE` 里算工作量，`> LIMIT[name]` ⇒ 异步 | **4** 个 action | `:19-24`、`:26-32` |

| action | 工作量公式 | 阈值 `LIMIT` | 实测两侧边界（本次复跑） |
| --- | --- | --- | --- |
| `mandelbrot` | `width × height × max_iter`（`max_iter` 缺省 256） | `1.5e8` | `600×600×256 = 9.216e7` → **同步**；`1200×1200×1024 = 1.47456e9` → **后台** |
| `complex_grid` | `nx × ny` | **`2.5e5`** | `500×500 = 250000` → **同步**（等于阈值不算超）；`501×501 = 251001` → **后台** |
| `expr_eval_grid` | `xs.length × ys.length`（没有 `xs` 就退回 `nx`/`ny`） | **`2.5e5`** | `500×500` → 同步；`501×501` → 后台 |
| `matrix_multiply` | `n³` | `2e6` | `n=125`（1.953125e6）→ 同步；`n=126`（2.000376e6）→ 后台 |

`num(v, d)` 把"非正数/非有限"一律折成默认值（`:51-54`），所以 `nx=0` 这类脏参数不会被算成 0 工作量。

**阈值是个"约等于"的数**，注释给了它的整数口径：`2.5e5` 标注为 `500×500`（`:29-30`），
`1.5e8` 标注为 `≈400 ms`（`:28`）。因为判据是**严格大于**，正好 500×500 **不会**走后台 —— 这是有意的，
不是差一错误。

### 6.1 反向约束：绘图页"每条曲线一次"的采样**刻意保持同步**

`asyncPolicy.js:11-15` 写死了这条反向约束：异步通道**只给"用户明确发起的一次重活"**用
（分形页重绘、复平面页求网格、工具箱跑一条 action）；绘图页里"每条曲线一次"的采样/极值标记
**保持同步**，理由有两条：毫秒级、且一条曲线一个 `await` 会把采样时序拆碎。

目前的实现与规模（都是本次复跑核对的常量）：

| 位置 | 规模 | 阈值两侧 | 出处 |
| --- | --- | --- | --- |
| 隐式方程/二元区域的网格采样 | `GRID_N = 180` ⇒ `180×180 = 32400` | 远低于 `2.5e5` ⇒ `shouldRunAsync` **恒 false** | `MFMath.UI.React/src/plot/usePlotSampling.ts:46`、`:198-208` |
| 3D 曲面 | 滑块 `max=96` ⇒ `96×96 = 9216` | 同上 | `Plot3DPage.tsx:139-148`、`:198` |
| 向量场 | 滑块 `max=41` ⇒ `41×41 = 1681` | 同上 | `PlotVectorPage.tsx:145-148`、`:215` |
| 共形映射 | `N=400, L=21` ⇒ 每次 `400×21 = 8400` | 同上 | `PlotComplexPage.tsx:192-198` |

反过来，**已经接了后台通道**的四类调用点是：分形页 `mandelbrot`、复平面页 `complex_grid`、
Vue 计算页的全部模式、函数工具箱的全部 action（BUGS.md B5 `:509-572` 记录了接线不完整的那一轮与更正过程）。

| 调用点 | 分流写法 | 出处 |
| --- | --- | --- |
| 分形页 | `shouldRunAsync` → `engineCallAsync`（带 `AbortController`，新一次渲染先 abort 上一次） | `PlotFractalPage.tsx:160-176` |
| 复平面页 | 同上，`apply()` 本来就是 async | `PlotComplexPage.tsx:164-171` |
| 计算页 | 轻的同步、重的后台并把进度写进状态栏 | `CalcView.vue:316-325` |
| 工具箱 | 同一套 + `opt.force` | `ToolboxView.vue:142-155` |

### 6.2 异步通道的语义（读代码得到的，不是猜的）

| 行为 | 事实 | 出处 |
| --- | --- | --- |
| 没宿主 | 返回 `null`，与同步版一致 | `bridge.js:162` |
| 宿主**没有** `DispatchJob` | **自动退回同步调用**（刻意设计：前端不因宿主版本旧就不好用） | `bridge.js:164-167`、`:178` |
| 派发失败 | 同样退回同步（`throw` 分支） | `bridge.js:177-179` |
| 轮询间隔 | `POLL_MS = 120`（毫秒） | `bridge.js:182` |
| 返回值对齐 | 成功 `{isError,value}`；失败 `{isError:true,value:"原因"}` —— 调用点从 sync 换 async 只需加 `await` | `bridge.js:148-152`、`:215-219` |
| 取消的语义 | 引擎**没有取消钩子**，宿主只能"停止等待并丢弃结果"，这一步会算完；所以文案必须是**"已取消等待"**，不能写"已停止" | `bridge.js:156-158`、`:197`、`:223`；`MFMath.Host.Rust/src/jobs.rs:15-17`、`:212` |

> **未证实（性能基准）**：`asyncPolicy.js:8-10` 记录了一条实测 ——
> `mandelbrot 600×600×256 = 9.2e7 次迭代 → 248 ms`，由此推出"约 `3.7e8` 次迭代/秒，`1.5e8 ≈ 400 ms`"。
> 我本次**没有复跑**这条基准（需要 Release 引擎产物 + 宿主）。它只是注释里的记录，不要当成本机现值。
> 怎么验：起宿主后在分形页把分辨率/迭代数固定到 `600×600×256`，读状态栏耗时；或用工具箱对
> `mandelbrot` 单发一次并计时。

---

## 7. 结果展示：四道闸门 + 数值格式

引擎返回的 `value` 里混着两类东西：**数学**（`(x + 2)*(x - 2)`、`x = -sqrt(a)`）与
**元信息**（`solveMethod = "symbolic"`、`kind = "maximum"`）。把 `"symbolic"` 丢给 KaTeX 会排成
`symbolic` 的斜体乘积 —— 看起来像数学，其实是错的。所以判定设了四道闸门，**宁可退回纯文本**：

| 闸门 | 规则 | 行号 |
| --- | --- | --- |
| ① | 字段名在 `PLAIN_KEYS` 里（引擎明确的元信息字段）⇒ 文字 | `resultModel.js:25-35`、`:154` |
| ② | 含中日韩文字或全角标点（`CJK`）⇒ 文字 | `:150`、`:157` |
| ③ | 没有任何"只可能出现在数学里"的字符（`MATH_CHARS`：数字、运算符、括号、`√ π` 等）⇒ 文字 | `:147`、`:158` |
| ④ | `symLatex`（引擎 `sym_latex`）必须真的解析出 LaTeX ⇒ 才算数学 | `:174-185`；`prepare.js:49-58` |

第 ② 道是实测逼出来的：`sym_latex("该分支内结论不唯一：极大值")` 会**原样返回中文**并报 `ok:true`
（`:15-17`）—— "引擎接受了"不等于"这是数学"。
第 ④ 道解释了 `equationLatex` 的存在：引擎解析器不认 `=`，所以 `a = b` 要**两边分开转再拼**，
一边解析不了就整串退回纯文本，不做"一半数学一半文字"的混排（`:166-172`）。

| 展示环节 | 事实 | 出处 |
| --- | --- | --- |
| 节点树 | `toResultNodes` 产出 `num`/`bool`/`math`/`text`/`table`/`list`/`obj` 七种节点 | `resultModel.js:187-224` |
| 空值必须**显示**出来 | 空对象显示"（空对象）"、空数组显示"（空）"；渲染成空节点会让对话框看起来像"算了但没结果" | `:198`、`:204`、`:216` |
| 字段名翻译 | `labelOf` 按 `FIELD_LABELS` 翻中文，**只做显示层翻译，不改任何计算结果**；没收录的键原样显示 | `:49-130`、`:133-139` |
| 数字格式 | `fmtNum`：**整数原样输出**（含 ≥1e12 的阶乘结果）；`Math.abs(v) >= 1e12`、或 `Math.abs(v) < 1e-10 && v !== 0` 走 `.6e`；其余按 `currentDecimals()`（默认 12）定点并去尾零 | `resultFormat.js:33-50`；默认位数见 `:22-24` |
| 对话框三态 | 无引擎/引擎报错/正常结果三态；`generalSolution` 非空时**只在显示层**摘掉空的 `solutions`（原始 JSON 不变） | `ResultDialog.vue:29-34`、`:46-53` |
| 上下文那一栏 | 用 `prepare_expr` 的 LaTeX（保留用户书写顺序），而不是 `sym_latex`（会重排成规范形式） | `ResultDialog.vue:55-66` |
| 历史摘要 | `briefValue` 先取"答案类"字段（`solutions`/`roots`…），元信息能省就省；理由是 `solve_sym` 的返回里判别式排在最前，直接取前四个会把**解集**挤掉 | `resultModel.js:243-251`、`:253-281` |

---

## 8. 怎么自己把这些数字复跑一遍

工作目录一律是 `MF_UI/MFMath.UI.Vue`。

```powershell
# ① 可达性 / 区间契约 / 概率表契约 / 重名登记（本文 §5 的全部数字）—— 本次实测 exit 0
node tools/check-ui.mjs

# ② 参数契约（§4.1）：415 个模式 / 934 个声明键 / 白名单 74 条 —— 本次实测 exit 0
npm run check:args
```

```powershell
# ③ 引擎签名表与源码对账（424 条）—— 本次**未跑**
npm run check:signatures

# ④ 全量前端闸门（types → 签名 → 参数契约 → UI 自检）—— 本次**未跑**
npm run check
```

> ⚠ ③④ **是"未执行"，不是"通过"**。没跑的原因：`npm run check` 的第一步
> `tools/build-tutorials.mjs` 会读**树外**的 v1 教程源并往 `docs/` 归档产物
> （`MF_UI/BUGS.md` 附 B ③ / B8 `:675-711`）—— 写这份文档时不想在这个工作树里产生
> 计划外的写入，所以只跑了不落盘的①②。要在本机确认全绿，请自己跑 ③④。

```powershell
# ⑤ 表规模与"模式表覆盖了多少 action"（§4 的那几个数）
node --input-type=module -e "import fs from 'node:fs'; const m = await import('./src/lib/engine/engineMap.js'); const sig = JSON.parse(fs.readFileSync('src/lib/ai/engine-signatures.json','utf8')); const fns = new Set(Object.values(m.ENGINE_MAP).map(s => s.fn)); console.log('模式表覆盖的 action', fns.size, '/ 签名表', Object.keys(sig).length, '/ 未被模式表引用的 action', Object.keys(sig).filter(k => !fns.has(k)).length);"
# 输出：模式表覆盖的 action 371 / 签名表 424 / 未被模式表引用的 action 53

# ⑥ EXTRA_MAP / EXTRA_VAR_SPECS 的条目数（§4）
node --input-type=module -e "const a=await import('./src/lib/engine/engineMapExtra.js'); console.log('EXTRA_MAP',Object.keys(a.EXTRA_MAP).length,'EXTRA_VAR_SPECS',Object.keys(a.EXTRA_VAR_SPECS).length);"
# 输出：EXTRA_MAP 164 EXTRA_VAR_SPECS 130

# ⑦ 旧版快照口径 RAW_MAP / RAW_VAR_SPECS（§4；这两个未导出，只能从源码的整行字面量里数）
node --input-type=module -e "import fs from 'node:fs'; const q=String.fromCharCode(34); const L=(f,p)=>fs.readFileSync(f,'utf8').split(/\r?\n/).find(x=>x.startsWith(p)); const raw=L('src/lib/engine/engineMap.js','const RAW_MAP = '); const rawv=L('src/lib/engine/engineMap.js','const RAW_VAR_SPECS = '); const k=(s,t)=>[...s.matchAll(new RegExp(q+'([^'+q+']+)'+q+':'+t,'g'))].length; console.log('RAW_MAP',k(raw,'\\{'),'RAW_VAR_SPECS',k(rawv,'\\[\\['));"
# 输出：RAW_MAP 324 RAW_VAR_SPECS 19
```

`check-ui.mjs` 也顺带打印另外几条与本文无关但同属"构建期闸门"的口径（i18n 缺译文、
端到端用例登记、键盘键数），本文不复述 —— 见 [CHECKS.md](CHECKS.md)。

---

## 9. 本文**不**背书的

| 项 | 状态 |
| --- | --- |
| `mandelbrot` 的 `248 ms` / `3.7e8 次迭代/秒` | **未复跑**，只是 `asyncPolicy.js:8-10` 注释里的一次实测记录 |
| `list_functions` 的 `count` 必须是 **424** | 我证实的是 `engine-signatures.json` 有 424 个键（§8 命令）；**没有**跑 `probe_call.exe` 本身（[AGENTS.md](../../AGENTS.md) §2 是那条判据的出处） |
| 48 个 `cdp-*` 用例"全部登记且全部通过" | `check-ui.mjs` 只断言**登记**（打印 `cdp-* 48 个，已登记 48 个`）；本次**未执行**端到端套件（需先 build + Release 宿主） |
| Vue 绘图组确实不可达 | `check-ui.mjs` 打印"冻结的 Vue 绘图组 6/6 个文件在位，被 import 0 处"；我未独立复核运行时行为（背景见 `MF_UI/BUGS.md` B9 `:712-741`） |
| `functionExists()` 保底分支的旧桥行为 | 现役 Rust 宿主实现了 `mf.FunctionExists`（`MFMath.Host.Rust/src/main.rs:71`、`handlers.rs:320-326`），所以 `bridge.js:269-272` 那条退路**没有在本机被触发过** |

---

## 已知的文档债

> 规矩照 [AGENTS.md](../../AGENTS.md) §5 与 [DESIGN.md](../DESIGN.md) §2 ③：**以代码为准**，注释可能是错的。
> 以下都是本次（2026-10-07）读代码时发现的**注释与代码不符**，我只记录，**没有改**。

| 位置 | 注释说 | 代码做 / 实测 | 怎么核 |
| --- | --- | --- | --- |
| `src/views/tools/ToolboxView.vue:7` | "…（lib/engine/engineMap.js，371 个 action）。剩下 **38** 个引擎早就算得出来，但界面上没有任何入口" | 424 − 371 = **53**，不是 38。`371` 这个数本身是对的（§8 命令） | `node --input-type=module -e "…"`（§8 ⑤） |
| `tools/check-arg-contract.mjs:22`、`:28` | "对全部 **78** 个'刮取器看不到'的键逐个做了差分探针"、"结论：**78** 个全是刮取器盲区" | 该文件自己打印的白名单条数是 **74**（本次跑 `npm run check:args` 的输出）。两个数最多只有一个是对的 | `npm run check:args` 第 2 行输出 |
| `src/lib/bridge.js:4`、`:343`；`src/lib/settings/bridge.js:4`；`src/types/webview.d.ts:8-9`；`package.json:6` | 把桥的对面写成 `MFMath.Host/MathBridge.cs`、`MFMath.Host/SettingsBridge.cs`、`MFMath.Host/MainWindow.xaml`、"经 C# MathBridge" | 这三个文件都**存在**，但按 [AGENTS.md](../../AGENTS.md) §2 属于**已废弃**的 `MFMath.Host/`；现役宿主是 `MFMath.Host.Rust/`，对应登记表是 `src/main.rs:67-84`（`MF_SPEC`）与 `:87-96`（`SYS_SPEC`） | `Select-String -Path MFMath.Host.Rust/src/main.rs -Pattern 'MethodSpec'`；`AGENTS.md` §2 的"已废弃"横幅 |

**核对通过、不是债**（避免有人重复怀疑，列出来）：

| 位置 | 说法 | 实测 |
| --- | --- | --- |
| `engineMap.js:7-9` | `RAW_MAP 324 / RAW_VAR_SPECS 19`，对外导出"目前是 **415 / 139**" | 四个数全部正确（415 / 139 由 `check-ui.mjs` 打印核对，324 / 19 由 §8 ⑦ 核对）—— B12 记的"三种口径"在这份文件里**已经修好** |
| `engineMap.js:31-35`、`calcArgs.js:445-447` | `hasEngineMode` 只实现一处，另一处只是再导出 | 全仓 grep 只有 `engineMap.js:33` 一处函数定义 + `calcArgs.js:447` 一处 `export … from` |
| `engineMap.js:37-39`、`resultFormat.js:52` | `getEngineSpec`/`getVarSpec`/`resultSummary` 已删除 | 全仓只剩这两处注释提到它们，没有任何调用点 |
| `MF_UI/BUGS.md` B10 `:748-763` | `ENGINE_MAP 415 / 页面并集 391 / 不在任何页面 24`、悬空 `VAR_SPECS` 2 个（`数值微分`、`矩阵乘法`） | 与本次实测逐条一致 |
| `asyncPolicy.js:39-49` 与 `CalcView.vue:311` | `ALWAYS_ASYNC` 是 **28** 个 | 精确计数 28 个 |
