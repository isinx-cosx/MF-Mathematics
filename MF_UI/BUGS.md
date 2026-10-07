# MF_UI 前端缺陷清单（Bugs）

> **本文只回答一个问题：现在有哪些确有证据的缺陷。**
> 每条都写了「现象 / 证据 / 根因 / 建议修法 / 回归方式」。证据一律给到 `文件:行` 或**可复跑的命令**。
>
> 维护规矩（与 `docs/OPEN-ITEMS.md`、`PENDING`、`KNOWN_FAIL` 同一套纪律）：
> **修完就把状态改成 ✅ 并补上回归断言；不要留一份没人信的清单。**
> 若某条经复查不成立，**连同结论一起删掉**，并在提交信息里写明理由。

- **核对时间**：2026-10-07
- **核对范围**：`MFMath.UI.Vue` + `MFMath.UI.React`（前端）。必要时下探到 C++ 引擎源码核对契约。
- **事实分级**：
  - 【实测·运行】我跑过命令，附可复跑命令
  - 【实测·源码】我读了引擎 C++ 源码，逐行核对键名/参数
  - 【静态】`grep` / 集合运算可证
  - 【存疑】明确写出没证到的部分（见附 A）
- **未做**：**没有跑端到端**（`tests/run-all.ps1` 需先构建 Release 宿主），所以"某功能在真宿主里表现如何"我不下结论。

---

## 0.1 修复记录（2026-10-07 本轮）

**已修且已验证的自检全绿**：`npm run check`（Vue：types + 引擎签名 + UI 自检）与 `npm run check:types`（React）
**双双 exit 0** —— 其中 Vue 的 `npm run check` 是本轮**第一次**能整条跑通（原来会卡在 B8 那个树外归档写入上）。

| # | 状态 | 做了什么 | 怎么验的 |
|---|---|---|---|
| B1 | ✅ 已修 | 10 个模式的区间参数统一成 `interval`；9 个原本没有弹窗的模式补了弹窗字段（默认 0,1 = 引擎缺省） | Node 直接跑构造器：改区间 → `interval:[0,2]`；不改 → `[0,1]`（与修复前逐字一致）。另加 **check-ui 守卫**「区间参数契约」并**验证它会失败** |
| B2 | ✅ 已修 | ① `prob_table` 改为"整串即一张表"，`;` 不再被当参数分隔符；② 全概率/贝叶斯改成**两张分开的表**（先验 + 条件） | 四个模式用**自带默认示例**跑构造器：`P` 不再是空对象。另加 **check-ui 守卫**「概率表契约」并**验证它会失败** |
| B2③ | ✅ 已修（新发现） | `解不等式/组` 的 `string_array` 被截断（`x>1; x<3` 只剩第一条）：`textArg` 的兜底 `spec.args[0]` 把整串交给了"只吃第一段"的逻辑 | `buildEngineArgs("解不等式/组","x>1; x<3")` → `["x>1","x<3"]` |
| B3 | ✅ 已修（代码）| `zoomFit`：补 `viewW/viewH` import + 去掉 Vue 式的 `view.value` | `tsc` 里那 3 条确定性错误消失（64→61）；**回归断言已写进 `cdp-plot-accuracy.mjs`（新第三节）但未执行**——需要 Release 宿主 |
| B4 | ⚠ **部分修复** | 去掉了"静默"：构造器新增 `report.defaulted` 收集器，CalcView 把"哪些必填参数是替用户填的"显示成行内警告 | 探针实测：415 个模式里 **32 个**存在必填参数被兜底（含 `某点导数` 的 `point=0`）。**未改成"拒绝计算"**——那会让这 32 个模式从"算错"变成"报错"，必须先补 fixture 样本并跑端到端，见下 |
| B5 | ✅ 已修（Vue 侧）／❌ React 侧未完 | **并更正了本文原先的错误结论**（见 B5 正文）：接线是**部分**的，不是"死代码"。本轮补上 CalcView（全部模式）与 ToolboxView（全部 424 个 action）的后台通道分流 +「强制后台」勾选 | `npm run check` 绿；`.vue` 用 `@vue/compiler-sfc` 编译通过；`shouldRunAsync` 判据来自既有 asyncPolicy，未改判据 |
| B6 | ✅ 已修 | React `check:types` **60 条 → 0 条**：`Shape` 改成判别联合（干掉 4 处 `as never`）、补 `ParsedExpr`、`Sample[]` 放宽、`@types/node` 以"把 vite.config.ts 移出 include"替代（装不了，见下） | `npm run check:types` exit 0；**无 `any`/`@ts-ignore`/`as never`**（仅 1 处 `as AdaptiveSampleFn`，因为 Vue 侧 JSDoc 比实现窄，见 B6 附注） |
| B7 | ✅ 已修 | `cdp-plot-accuracy` 登记进 `run-all.ps1`（放在绘图组、不放到最后）；另加 **check-ui 守卫**「端到端用例无漏登记」并**验证它会失败** | check-ui 打印 `cdp-* 47 个，已登记 47 个`；造一个未登记用例 → 自检失败（已验证） |
| B8 | ✅ 已修 | 4 处硬编码绝对路径 → 统一走新的 `tests/engine-paths.mjs`（环境变量 → 相对 v2.0 推导 → 可读报错）；教程 YAML 归档失败改为**警告不中断** | `build-tutorials.mjs` 在本沙箱（归档写不进去）**从 exit 1 变成 exit 0**；`showfn.mjs` 能解析到正确那棵树的引擎源码；`npm run check` 由此整条通过 |
| B9 | ✅ 已按决定完成 | 定为**冻结的回退资产**：`router/index.js` 注释改成事实描述（已不跟随修复 / 不在构建图 / 无类型检查 / 无用例覆盖）；新增 **check-ui 守卫**（白名单 + 确认没人 import） | check-ui 打印`6/6 个文件在位，被 import 0 处`；**验证过会失败**（造一个 import → 报错 exit 1） |
| B10 | ✅ 已按决定完成 | **判据收紧**为"模式名必须可选到，否则必须显式登记"；实测 24 个全部登记 | check-ui 打印`已登记 24 个，未登记 0 个`；**验证过会失败**（去掉一条登记 → 报错 exit 1） |
| B13 | ✅ 已修（第二轮） | `PlotPage.tsx` 的 `curves` memo 改成 `emphasis: r.id === activeId` | 与 B14/B15 同一成因，见 §0.3；若要退回"都不加粗"，把这一行改回 `r.emphasis` |
| 脚手架① | ✅ 已修（实跑时暴露） | `tests/run-all.ps1` **没有 UTF-8 BOM**：文档推荐的 `powershell -File`（5.1）按 ANSI 解码，中文注释被解坏并**吞掉下一行**，直接把它自己的 `$tests` 数组弄成语法错误（`Missing expression after ','`）。已补 BOM 并写明"此文件必须保留 BOM" | 两个解释器都 0 解析错误；补 BOM 前 5.1 报 1 个错 |
| 脚手架② | ✅ 已修（实跑时暴露） | 同一文件里解析宿主用了**两层**相对路径（`..\..\`），永远解析不到，靠一条**写死的本机绝对路径**兜住 —— 换台机器就是 "Host not found"。已改三层 + `MF_HOST_EXE` 可覆盖 + 可读报错（**又一处 B8 类缺陷**） | 三层相对路径 `Test-Path` 为真；注释与代码同步 |
| 脚手架③ | ✅ 新增（实跑时暴露） | `run-all.ps1 -NoLaunch`：**附着到已在运行的宿主**。因为本环境里 `Start-Process` 起不了 GUI 进程（`ERROR_CANCELLED`），而经 shell 起（`cmd /c start`）可以 —— 把"起宿主"和"跑用例"解耦 | 本会话 49 条套件就是这样跑起来的；`-NoLaunch` 下不会杀调用方自己的宿主 |
| B11 | ⚠ 部分修复 | `WelcomeDialog.vue` 的 `v-html` 已过 `sanitizeTourHtml`（零成本）；**`NAV_GROUPS` 收口未做** | `.vue` 编译通过 |
| B12 | ⚠ 部分修复 | 已做：注释计数改成"以 check-ui 输出为准"、删掉 3 个零引用导出（`getEngineSpec`/`getVarSpec`/`resultSummary`）、`hasEngineMode` 去重（现在只实现一处）；**未做**：`textArg` 选择逻辑抽函数、`single` 死分支 | `hasEngineMode` 对全部 415 个模式与旧实现逐个比对一致；`npm run check` 绿 |
| B13 | 📝 新登记 | 见文末「附 D」：React 绘图页**从没设置过 `emphasis`**，聚焦曲线不再加粗（Vue 版有） | 由 B6 那轮静态核对发现；一行可修，但属行为变化，未擅自改 |

> 📌 **上表是第一轮的记录，保留原样。** 其中标着"未做 / 部分修复"的项（B4、B5、B11、B12），
> 以及当时还没登记的 B13/B14/B15，**都已在第二轮做完** —— 见 **§0.3**；各条目的最新状态见 §0。

**这一轮暴露的两件事值得写下来**：
1. **本文原先的 B5 结论是错的**，而且错得很有代表性 —— 取证时只 grep 了 `MFMath.UI.Vue/src`，没查 `MFMath.UI.React/src`，于是把"Vue 里没人调"当成了"全仓库没人调"。**跨工程共享逻辑的项目，取证必须覆盖两个工程。** 已在 B5 正文更正。
2. **`npm run build` 的两次不同结果都值得记**：受限沙箱下它**根本跑不起来**（esbuild 子进程被挡：
   `Error: spawn EPERM`）；沙箱解除后能跑了，却又卡在 esbuild **清理临时文件**上：
   `[vite:esbuild-transpile] remove C:\Users\...\Temp\esbuild-…: Access is denied`
   —— 注意此时 `234 modules transformed` 已经成功，是在收尾时被拒。**解法**：把 `TEMP`/`TMP`
   指到工程内的目录再构建（`$env:TEMP='<repo>\.buildtmp'; $env:TMP=$env:TEMP; npm run build`）
   ⇒ **exit 0、产物正常**。这不是代码缺陷，但很容易被误判成"构建坏了"。

---

## 0.2 端到端实跑结果（2026-10-07，**绘图组迁到 React 之后的第一次**）

环境：沙箱已解除（full access）。跑法：`npm run build` → 同步 `dist` 到宿主 wwwroot →
**启动 Rust 宿主** → `run-all.ps1 -NoLaunch`。

> ⚠ **重要前提**：本机只能跑起 **Rust 宿主**（`%TEMP%\mfhost-run\mfmath-host-rust.exe`）。
> 而 `run-all.ps1` 原本针对的是 **.NET 宿主**（`MFMath.Host\bin\Release\...\MFMath.exe`）——
> 本会话里 Start-Process 起不了 GUI 进程（`ERROR_CANCELLED`），用 shell 起起来的那个 .NET 宿主
> 又始终没能初始化 WebView2（无子进程、无日志）。
>
> 🔴 **下面"宿主缺桥"那一行已经作废，别再用（2026-10-07 二次实测推翻）**：
> 当时我看到的是"Rust 宿主只有 `mf/sys/diag/win/push`、没有 `ai/search/account/update`"，
> 于是把 88+37+27 条失败归给宿主。**但那是过期的** —— 并行开发者随后把 **AI 改成页面直连**
> （`9c1ad1a`、`eafd482`），账号 / 更新 / 搜索也各自闭环。用最新提交重新构建后**逐条实测**：
>
> | 套件 | 当时（已作废） | **二次实测** |
> |---|---|---|
> | cdp-ai | 39/88 | **160/0** |
> | cdp-account | 15/37 | **52/0** |
> | cdp-update | 10/27 | **37/0** |
> | cdp-search | 崩溃 exit 0xC0000409 | **55/0** |
> | cdp-console / cdp-push | 无 RESULT 行 | **66/0 / 20/0** |
> | cdp-settings | 40/3 | **43/0** |
> | cdp-history-search | 18/3 | **21/0** |
>
> **教训（与 §0.1 第 1 条同类）**：在**有人并行改同一棵树**的情况下，"某处失败 ⇒ 归因给环境/宿主"
> 这种结论**必须带时间戳**，否则会被后续提交悄悄推翻。另一条更早的教训是"取证只覆盖了一个工程"。

| 结果 | 套件 |
|---|---|
| ✅ 全绿 | reset-appearance 2、unit-result-model 30、unit-sse 13、unit-markdown 18、cdp-bridge-verify 7、cdp-window-shell 25、cdp-appearance 33、cdp-input-notation 28、cdp-font-load 18、**cdp-plot-verify 9、cdp-plot-p3 7、cdp-plot-p4 9、cdp-plot-region 11、cdp-plot-p5 12、cdp-plot-final 10、cdp-plot-asymptote 7、cdp-plot-extrema 15、cdp-plot-extrema-domain 23、cdp-plot-3d 13、cdp-plot-vector 13、cdp-plot-fractal 14、cdp-complex-modes 21、cdp-plot-geometry 20、cdp-plot-truth 9**、cdp-calc-workspace 65、cdp-basic-calc 41、cdp-diff-at-param 10、cdp-fractal-orient 3、cdp-fractal-clickzoom 7、cdp-geometry-line 7、cdp-geometry-aspect 9、cdp-canvas-theme 5、**cdp-modes-render 191**、cdp-tutorials-keypad 48、cdp-settings-io 32、cdp-engine-solve 13、cdp-expr-normalize 26 |
| ✅ 修好后全绿 | **cdp-plot-accuracy 14/0**（原本 13/1，判据错）、**audit-modes 393/0**（原本 391/2，fixture 过期） |
| ~~❌ 宿主缺桥（不算前端缺陷）~~ **← 已作废，见上方红字** | ~~cdp-ai 39/88、cdp-account 15/37、cdp-update 10/27、cdp-search 崩溃、cdp-console / cdp-push 无 RESULT 行、cdp-settings 3 条、cdp-history-search 3 条~~ → 二次实测**全部转绿**（160/0、52/0、37/0、55/0、66/0、20/0、43/0、21/0） |
| ❌ **真前端缺陷（本轮新登记）** | cdp-workspace 21/4 + cdp-shortcuts-prefs 22/1 → **B14**；cdp-export-image 43/2 → **B15** |
| ⚠ 未跑完 | **cdp-engine-coverage**：本机约 7 秒/模式 × 415 ≈ **45 分钟**，我在 10.7 分钟处停掉（已跑完 algebra / algebraic-topology / analytic-geometry）。部分结果：`双曲线方程 结果为空`，随后 `抛物线方程`/`斜截式直线`/`点斜式直线` 三条 **`Runtime.evaluate` 超时（≥30s）** |

**本轮从"实跑"里新挖出来的 5 件事**（都写进对应条目了）：

1. **B14**：React 绘图组**完全没接工作区** —— 7 个绘图页的内容不会被保存/还原。
   直接证据：全 React 工程 `grep` 不到任何 `@shared/workspace/*`；而（已冻结的）Vue 版
   `PlotView.vue:20,35,701` 是接了的。**这是 Vue→React 迁移掉的一块功能**，与 B13（emphasis）同一性质。
2. **B15**：React 绘图页**不再报导出结果** —— "已导出图片：…（尺寸，大小）" / "导出失败：…" 这组文案
   只存在于**已冻结的 Vue 视图**里（`PlotView.vue:657`、`PlotFractalView.vue:35` 等 6 处），
   React 侧一条都没有。用户点导出后**没有任何反馈**（失败时也没有）—— 正是套件里那两条
   "不是静默"断言要抓的东西。
3. **套件自身的判据错**（已修）：`cdp-plot-accuracy` 把视口**写死**成 ±10×±10，
   而真实视口的 y 跨度 = 20·h/w（本机画布 694×726 ⇒ y∈[-10.46,10.46]）。
   |y| 越大偏得越多（y=8 差约 12.8 设备像素，远超 ±2 容差），于是 `x` 那条线在两端被误判成
   "没画出来"。**已改成读 `window.__mfPlot.view()`**（对画布宽高比免疫，也顺带覆盖"设置里配了固定范围"）。
   这也正好是"**这条用例从来没被执行过**"（B7）的代价：判据里的硬编码没人发现。
4. **fixture 的重复键 + 过期样本**（已修）：`tests/fixtures/mode-samples.mjs` 里同一个模式被定义多次
   （JS **后者胜**，前面的是死条目），`全概率公式`/`贝叶斯公式` 生效的那条还是**三段式老形状**；
   B2 改了契约（输入框整串 = 第一张表）之后，它把三样东西全塞进第一张表 → 引擎报
   「缺少条件概率 P(B|B|A1)」。已修样本（**393/0**），并给 `check-ui` 加了一条"重复键"警告
   （现在报 `重复键 28 个`，非阻塞）。
5. **一个操作层面的坑，值得单独记**：**中途杀掉套件会让宿主里留下一支没跑完的后台任务。**
   `bridge.js:154-158` 自己写明"引擎没有取消钩子，CancelJob 只是停止等待，它会把这一步算完"；
   于是那支任务占着引擎，之后页面上**任何同步 engine 调用都会永久阻塞** → 渲染进程卡死，
   连 `location.hash` 这种纯 DOM 读取都会超时（我实测卡了 30+ 分钟，重启宿主才恢复）。
   ⚠ **B5 的改动会放大这个风险**：重的活现在走后台通道，调用方（用例）走了，活还在跑。
   **跑 `cdp-engine-coverage` 时不要中途 Ctrl-C；要中断就先停宿主。**

**结论**：我这轮改的东西**没有引入回归** —— 覆盖它们的套件全绿
（`cdp-calc-workspace` 65/0 覆盖 CalcView 的 B4/B5 改动；`cdp-modes-render` 191/0 与
`audit-modes` 393/0 覆盖 B1/B2 的参数构造；绘图组 12 条套件全绿覆盖 B3/B6 的 React 改动）。
真正的缺陷是**迁移遗留的**（B13/B14/B15），而它们只有在"真跑一次"之后才看得见。

---

## 0.3 第二轮修复（2026-10-07，用户指示"全部修复"）

**范围**：§0.2 里剩下的全部条目 —— B4 的后半、B5 的 React 侧、B11/B12 的余量，
以及实跑新登记的 **B13 / B14 / B15**。全部改完后跑针对性 e2e 验证。

| # | 状态 | 做了什么 | 怎么验的 |
|---|---|---|---|
| **B14** | ✅ **已修** | 新增 `MFMath.UI.React/src/lib/plotWorkspace.ts`（`loadPlotPage` / `savePlotPage` / `usePlotWorkspace` + 一组"工作区文件是用户可手改的"取值守卫），并给 **6 个绘图页全部接上**：2D/极坐标（`kind:"plot"`，载荷形状与 Vue 版 `capturePlot()` **逐字一致**，老工作区文件仍可读）、3D、复平面、向量场、几何、分形。`ReactPlotView.vue` 现在给 2D/极坐标也传 `routePath`（工作区按 `route.path` 分页存，以前这两页只传了 `gridMode`，所以连存的键都没有） | `cdp-workspace` **21/4 → 25/0**、`cdp-shortcuts-prefs` **22/1 → 23/0** ✅ |
| **B15** | ✅ **已修** | `PlotPage` 的 `exportImage()` 原先**丢掉 `exportCanvas()` 的返回值**。现在把结果写进页内状态行（`已导出图片：<路径>（尺寸，大小）` / `已取消导出` / `导出失败：<原因>`），并顺手修掉写死的 `routePath:"#/plot/2d"`（极坐标页导出的文件名也是它）。另外 5 页**本来就报**导出结果，不用改 | `cdp-export-image` **43/2 → 45/0** ✅ |
| **B13** | ✅ **已修**（推翻了先前"只留记录"的决定） | `PlotPage.tsx` 的 `curves` memo：`emphasis: r.emphasis` → `emphasis: r.id === activeId`。字段的**消费方一直都在**（`PlotCanvas.tsx:224` 的 `lineWidth = c.emphasis ? 4 : 2.5`），缺的是生产方 | `tsc` 通过；绘图组 12 条套件全绿（含几何/极值/连续性） |
| **B5** | ✅ **已完成** | ① 复平面页：`fetchGrid`/`fetchConformalGrids` 改 async + `shouldRunAsync`/`engineCallAsync`/进度——它的唯一调用点 `apply()` **本来就是 async**，级联只有一个 `await`（`complex_grid` 分辨率上限 1000 ⇒ 最多 1e6 点，真的会越过 2.5e5 阈值）。② 3D / 向量场 / 网格采样三处**刻意保持同步并写明理由**：规模分别是 96²=9216、41²=1681、180²=32400，都由 UI 自己的滑块上界封住、**恒低于** 2.5e5 阈值（`shouldRunAsync` 恒 false，接异步只是空转），并注明"若把上界提到 500 以上必须改回异步"。③ 抽出共用的 `lib/jobProgress.ts`（`JobProgress` 原先只在分形页有一份本地定义） | `cdp-complex-modes` 21/0 ✅、`cdp-plot-extrema*` / `cdp-plot-3d` / `cdp-plot-vector` 全绿 |
| **B4** | ✅ **已完成**（含前置的样本补齐） | ① **先补样本**：探针查出只有 **10 个页面模式**（不是原先估的 32 个）会走到"必填兜底"，已全部补进 `mode-samples.mjs`（段序 = args 声明顺序，每条都用**真引擎**验过）。② 再把 `CalcView` 的"兜底后照算 + 一句警告"改成**拒绝计算**：`missingRequiredText()` 给出"缺哪些参数 + 怎么补"（有弹窗的指弹窗、没弹窗的指 `;` 分段语法），不再调用引擎。③ 随之删掉已无用的 `warn` 字段 / 模板分支 / `.cb-warn` 样式 / 旧译文，新增 3 条 i18n | 影响面复测 **10 → 0**；`audit-modes` **393/0**（真引擎）；`cdp-calc-workspace` 65/0、`cdp-modes-render` 190/0、`cdp-basic-calc` 41/0、`cdp-engine-solve` 13/0 ✅ |
| **B11** | ✅ **已修** | 新增零依赖模块 `MFMath.UI.Vue/src/lib/router/nav.js`（`NAV_GROUPS` + `findNav`，**逐字**搬移，含解释顺序的中文注释）；`router/registry.js` 改为再导出；`MFMath.UI.React/src/App.tsx` 删掉那份 61 行手抄副本，改从 `@shared/router/nav.js` 引入 | Vue `npm run check` + React `check:types` 均 exit 0；两个工程都跑了真实 `vite build`，产物里含导航路由；`tsc --listFiles` 确认 `nav.js` 真的被解析到 |
| **B12** | ✅ **已修** | ① `calcArgs.js` 里**复制了 3 份**的"输入框第一段喂给哪个参数"抽成 `pickTextArg(args, {skipWholeString})`（两种口径**有意不同**，注释写明不能合并）。② fixture 里的重复键：**36 条死条目**全部删除（保留最后一条），重复数 **29 → 0**。③ `check-ui.mjs` 的重复键检测正则**去掉了行首锚点** —— 原先 `^ {2}"key":` 会漏掉"一行两条目"紧凑行里的后半条，实测就漏过一个 `协方差`（所以真实重复数是 **29** 而不是它报的 28） | 行为一致性强验：12 组**重构前实测过**的期望值（概率四模式 / 不等式组 / 达布和 / 某点导数 / 两点距离 / 定积分 / 交换律）**12/12 一致**；`MODE_SAMPLE` 前后同 277 键、**0 个值不同**；`npm run check` exit 0 |

**这一轮新暴露/修正的两个测试自身问题**（都不是产品缺陷）：

- **`cdp-plot-accuracy` 会在两种情况下假失败**，两种都已修：
  ① **钩子读得太早**：`window.__mfPlot` 是 `useEffect` 里挂的（DOM 提交之后），所以"画布已经在 DOM 里"
  并不保证钩子已就位；原先读不到就**静默退回**假定 ±10×±10，于是几何全错、6 条命中断言集体失败，
  真因却只是一次竞争。现在**先等钩子、等不到就明确报错**，彻底删掉那条静默退路。
  ② **工作区还原会带进上一个用例的视野**：B14 修好之后这是**正确的产品行为**（还原用户上次的视野），
  但本套件原来假定"默认视野"。现在它读 `__mfPlot.view()` 的真实值并用它换算，对视野来源免疫。
- **`cdp-modes-render` 从 191/0 变 190/0**：**不是少跑了一个模式**（候选集由 `slice(0, MODES_PER_VIEW)` 封顶）。
  原因是我给那 10 个模式补了**正确的**样本，候选集合发生替换，其中一个模式现在返回**非数值结果**
  （如 `二项式展开` 返回多项式），于是"引擎的数值必须出现在界面上"那条断言按其分支被跳过。
  0 失败、覆盖的关键断言（界面成败 vs 引擎成败、公式已排版）一条没少。

**仍未完成的一件事**：`cdp-engine-coverage` 需要约 45 分钟（详见 §0.2 与附 C 第 3 条的操作警告）。

### 0.3.1 `cdp-engine-coverage` 的实跑结果（跑到底了）

**`RESULT|cdp-engine-coverage|296|7`** —— 7 条失败**全是同一种**：`[超时]`（`Runtime.evaluate` 30 秒无响应），
不是算错、也不是断言不符：

```
[FAIL] number-theory · 欧拉乘积        模式没切成功（[超时]）—— 结果不可信
[FAIL] number-theory · Dirichlet L 函数 模式没切成功（[超时]）—— 结果不可信
[FAIL] number-theory · 伯努利数         模式没切成功（[超时]）—— 结果不可信
[FAIL] numerical / probability / real-analysis / sequences 视图有模式   [超时]
```

**形态**：卡顿从 `number-theory` 中途开始，**一路持续到用例结束**（后面 4 个视图连"有多少模式"
都读不出来）；用例退出后页面**恢复响应**（我随后读到 `location.hash` 用时 3ms）。所以不是死锁，
是渲染进程被某个东西**占住了几分钟**。

**我试过复现，但没能复现（如实记下）**：
用**套件实际用的样本**（number-theory 视图样本 `"30"`）逐个点
`最佳有理逼近` / `欧拉乘积` / `Dirichlet L 函数` / `伯努利数`，每次点完连续 60 秒、每 5 秒
用纯 DOM 读探活：**四个模式全程可响应（0–3 ms）**，其中三个还成功算出了结果。
（⚠ 前两次探针我把模态结果弹窗忘了关，`.cb-calc` 根本点不动 —— 那两轮"不卡"是假结论，已作废。）

**结论（2026-10-07 10:0x 更正 —— 真因是并发驱动，不是"长会话累积"）**：
这 7 条**不是**前端缺陷，也和"某个模式太重"无关。真因是**另一个会话在同一个宿主上并发跑用例**，
把页面开走了。证据（`10:0x` 实测）：

1. `Get-CimInstance Win32_Process` 抓到 `.../tests/cdp-plot-fractal.mjs`、`cdp-complex-modes.mjs`、
   `cdp-calc-workspace.mjs`、`cdp-update.mjs`、`cdp-engine-coverage.mjs` 等进程在跑 —— 都来自**别的会话**；
   连续采样能看到它们按 `run-all` 的顺序一辆一辆过去。
2. 同一时刻存在**两个 `mfmath-host-rust.exe`**（09:50:12 / 09:50:15 各起一个），而 CDP 端口只有一份
   —— 两个会话共用同一个页面。
3. 我设 `location.hash='#/plot/2d'` 之后读到的是 **`#/plot/vector`**，另一次读到 `#/plot/fractal`
   —— **这两个路由我从没导航过**。（`cdp-plot-accuracy` 因此在完整套件里 10/4：③ 的三条断言全挂，
   是因为 vector 页也有 canvas、但没有 `__mfPlot`、也没有「缩放到适应」按钮。）
4. 这也解释了为什么我**单独**跑那 4 个可疑模式时全程可响应（0–3 ms）——那次恰好在空窗期。

**方法论（已与 `AGENTS.md` §4 对齐）**：并发驱动**只会造成假失败，不会造成假通过**。
所以本文件里"通过"的数字仍然可信；而**任何在并发窗口里得到的失败数字都作废**（本节的 296/7 属此类）。
跑端到端前先确认没有别的会话在驱动同一页面；宿主优先**附着**，不要另起一个。

### 0.3.2 本仓库的"并发互斥"：这一轮真正踩到的坑（含两个副产物）

**这一轮我同时踩了 `AGENTS.md` §4 的两条**：在别人已有宿主的情况下**又起了一个宿主**，
并且在别人的 `run-all` 正在跑时做了多次测量。后果不是"白干"，而是**双方的数字都不可信**。
记录在此，因为它比单个缺陷更贵：

- 同一份 `wwwroot`、同一个 CDP 端口、同一个页面 ⇒ 两个会话互相把页面开走；
- 我这边表现为：`cdp-plot-accuracy` 10/4（③ 三条全挂）、`cdp-engine-coverage` 296/7（全是 `[超时]`）；
- 判别"是谁的锅"的**唯一可靠手段**是当场取证：列出 `node.exe` 的用例进程、数宿主进程、
  以及**核对当前路由是不是自己请求的那一个**（我最后就是靠"`#/plot/vector` 我从来没导航过"定案的）。

**副产物 ①（值得留档的读取坑）**：`window.__mfPlot.view()` 返回的对象，用 CDP 的
`returnByValue` 直接取会得到 **`{}`**；而同一个对象在页面里 `Object.keys` 与 `JSON.stringify`
都是完好的（`x0/x1/y0/y1` 齐全）。**这是读取方式的问题，不是产品状态坏了。**
所以凡是要读这些钩子的对象，一律走 `JSON.stringify(...)` 再在 Node 侧 `JSON.parse`
（`cdp-plot-accuracy` 已改成这样；新写的 `cdp-plot-workspace` 从一开始就这么写）。

**副产物 ②（用例该有的样子）**：新用例一律**内建干扰检测** —— 每次操作后核对
`location.hash` 是否仍是自己请求的路由，不一致就打印 `INTERFERENCE` 并把那条判为失败，
而不是安静地给出错误结论。`cdp-plot-workspace` 与 `cdp-plot-accuracy`（③ 的失败详情里带上
"当前路由 / PlotPage 是否还挂着 / canvas 数"）都已按这个口径改。

### 0.3.3 B 类任务（补 5 个绘图页的工作区断言）：代码完成 + **跑过一次（部分可信）**，全量仍待宿主可用

- **已完成**：新增 `tests/cdp-plot-workspace.mjs`（6 页 × 两个方向：改动→工作区载荷跟着变、
  离开再回来→控件还原；含按页的 `kind` 校验，以及**分开报告**"页面被别人开走"与"页面/宿主整个没了"），
  并在 `tests/run-all.ps1` 绘图组内登记（`check-ui` 报 `cdp-* 48 个，已登记 48 个`；BOM 已保留）。

- **跑过一次，拿到部分可信信号**（`10:2x`，宿主存活的那段）：**2D 与 3D 的"重挂载后还原"通过了**
  —— `sin(2*x)` → `sin(2*x)`、`0.5*x+0.25*y` → 同值，说明 B14 的还原路径对这两页确实生效。
  同一条跑的"改动被写进工作区"却报"工作区里没有这一页" —— **自相矛盾 ⇒ 是我读错了键**：
  `store.js:215` 的 `pages()` 按 **`route.path`（`/plot/2d`，无 `#`）** 存，
  而我的用例拿 `"#/plot/2d"` 去查。**这是我的用例 bug，不是产品没存**（已修：`route`/`path` 分开）。

- **同一轮还修掉了用例的第二个 bug**：宿主在跑复平面那一页时**进程消失**，`location.hash` 读成
  `undefined`，而我的第一版把"读不到"与"路由被改"混成同一句 `INTERFERENCE`（"有并发驱动"）
  —— 归因完全错了。现在两者分开：读不到 ⇒ 报"页面/宿主不可用"、**退出码 2**（不当成产品失败）；
  路由被改成别的 ⇒ 才报 `INTERFERENCE`。

- **未完成的原因（不是"没空跑"，是宿主起不来）**：`10:30` 前后反复尝试启动 Rust 宿主，
  一律在创建窗口时失败：

  ```
  [rust-host] WebView2 窗口创建 失败
  runtime error: failed to create webview: WebView2 error: WindowsError(Error { code: HRESULT(0x800700AA), message: "请求的资源在使用中。" })
  ```

  宿主自己的提示把原因说成"另一个实例占着同一个 WebView2 数据目录"，但**那条提示在这里是误导**：
  - 用 `MF_WEBVIEW2_DIR` 指到一个**全新目录** → 同样报错（日志确认用的就是新目录）；
  - **不带** `--remote-debugging-port=9222` 启动 → 同样起不来（所以也不是端口占用）；
  - 系统里**没有任何** `mfmath-host-rust.exe`，6 个 `msedgewebview2.exe` 全属 `SearchHost.exe`
    （user-data-dir 是 Windows CBS 那个，不是我们的）—— 所以"另一个实例"并不存在。
  - 结论：**这是 A 面（Rust 宿主）的问题**，`0x800700AA` 的**提示文案本身也会误导排查方向**。
    已按 `AGENTS.md` §2 的要求写明是跨面发现，交由 A 面处理。

- **因此 B14 那 5 页的最终状态是**：代码就绪、**2D/3D 两页的还原已实测通过**，
  其余 4 页（复平面 / 向量场 / 几何 / 分形）**仍未验证** —— 等宿主能起来后跑
  `node tests/cdp-plot-workspace.mjs`（它会自己报告 `INTERFERENCE`；退出码 2 = 宿主不可用）。

### 0.4 参数契约系统核对（2026-10-07）：**415 个模式 / 934 个声明键，0 处真缺陷**

**为什么要做**：B1 是"引擎读 `interval`、UI 发 `a`/`b` ⇒ 用户填的区间永远不生效（恒定 [0,1]）"。
而现有的 `npm run check:signatures` **只对账「引擎源码 ↔ engine-signatures.json」，完全不含 UI**
—— 两边各自都"无漂移"，缝里的 B1 谁也没看见。所以要把**第三条边**补上：**UI 的 `ENGINE_MAP` ↔ 引擎实际读的键**。

**怎么做的**（两段，缺一不可）：
1. **静态**：复用 `tools/engine-signatures.mjs` 的刮取器，列出每个模式"UI 声明了、但源码里看不到读"的键。
   ⚠ 刮取器只是**下界** —— 引擎大量参数经 helper / lambda / `args["k"]` 读（例：`get_interval(args,a,b)`）。
2. **动态（定案）**：对每个候选做**差分探针** —— 用 `probe_call.exe` 真调引擎，**删掉**这个键 / 换成别的值，
   看结果变不变。这是 B1 的同一套判据，不依赖刮取器。

**结果**：78 个候选**全部是刮取器盲区**，没有一个是真缺陷。三类判据：
- **删掉即报错**（42 条）：`对象缺少键: z` / `缺少必填参数 point` / `gamma 必须为 circle(center, r)`
  —— 引擎明确要它，铁证；
- **改值结果就变**（30 条）：如 `extreme_value` 的 [0,1] max=1 → [0,2] max=4；
- **单看删除没差别、但已查清原因**（6 条）：`get_interval` 的默认值**就是 [0,1]**，而样本区间恰好也是 [0,1]
  （实测：省略 interval 与传 [0,1] 逐字相同，传 [0,2] 下和 0.285→2.28）；另有两个模式只输出**判定值**
  （`一致连续`/`黎曼可积`），判定对区间不敏感 —— 但源码里 `get_interval` 是**无条件**调用的。

**顺带确认 B1 的修复是对的**：引擎 `real_analysis_api.cpp` 里 `darboux_sum`/`riemann_integrable`/
`fundamental_theorem`/`integral_mean_value`/`uniform_continuity`/`extreme_value`/`intermediate_value`/
`weierstrass_m_test`/`termwise_integration`/`uniform_convergence` 全部走 `get_interval(args, a, b)`，
UI 发 `interval` 正是对的（当初发 `a`/`b` 才是不生效）。

**由此新增的常驻闸门**：`tools/check-arg-contract.mjs`（`npm run check:args`，已进 `npm run check`）。
- 判据：UI 声明的每个键，要么被刮取器看到，要么在 `HELPER_READ` 白名单里且**写明判据**；
- **已验证它会失败**：临时给「达布和」注入一个引擎不读的 `bogus_key` ⇒ 立即报出该模式该键并 `exit 1`，
  还原后 `exit 0`；
- 白名单**拒绝无判据的条目**（文件注释里写明：拿不出判据就别加，白名单只会越长越没人信）；
- 反方向（引擎按必填读、UI 没声明）只**警告**：4 处已核为**多分支互斥**的假阳性
  （`variance` 的 `required=[expr,pmf_data]` 实际是 data / pmf_data / expr+range 三选一）。

**结论**：**参数契约这一侧是干净的**。这也是本轮唯一一处"系统核对"而不是"抽查"——
其余条目（B1 之外的 400 多个模式）此前只做过零散核对，现在有了闸门，**新引入的同类错会被挡住**。

### 0.5 第三轮：把"从没人验证过"的疑点逐条判定（2026-10-07）

**① `history/store.js`：写盘去抖 vs 重新加载 ⇒ 静默丢数据（真缺陷，已修）**
`docs/FRONTEND-FIXES.md` §5 把这条标成"没有独立证据"。判定结果：**它是真的**，而且后果比"竞态"更具体：
- `record()` 之后 250ms 内 `loadHistory(true)`（设置页"重新加载"）：reload 先用**旧文件**覆盖内存，
  随后那个待触发的定时器把**旧内容**写回盘 ⇒ 刚记的条目**内存与磁盘都没了**；
- `clearAll()` 之后 250ms 内 reload：被清掉的条目**复活**并被写回盘 ⇒"清空历史"失效。
另外全库**没有** `beforeunload`/`pagehide` 收尾 ⇒ 关窗前 250ms 内的改动也会丢。
修法：落盘抽成 `flush()`，**强制重读前先 flush**；并在 `pagehide` 补一次（桥是同步宿主调用，来得及）。
- **可复跑的判据**：新增 `tests/unit-history-store.mjs`（假桥/内存 KV，不需要宿主窗口）5 条断言；
  **并已证明它会失败** —— 撤掉那行 `flush()` 后 ① 报「内存=["旧记录"]」、盘上也只剩旧记录（真丢），
  ② 报「内存 1 条、盘上 1 条」（真复活），4 失败；还原后 5/0。

**② `CodeEditor.vue`：编辑器还在惰性加载时切语言，那次切换被丢掉（真缺陷，已修）**
`watch(language)` 里有 `if (!handle) return;`，而 `createEditor` 用的是**调用那一刻**的 `props.language`
—— 加载窗口内切的语言不会生效，编辑器停在旧语法上直到再切一次。
修法：排队切换抽成 `queueSetLanguage()`，boot() 结束时比对"创建时的语言"与当前 props，不一致就补一次。
（该文件其余竞态**已经被加固过**：`disposed` 检查、语言串行链 + await 前判序号、创建期间卸载的 destroy。）

**③ `ENGINE_MAP["解不等式组"]` 的坏条目（已修）**：它只有 fn、`args: []`，一旦被选到一个参数都不发。
按既有覆盖机制在 `engineMapExtra.js` 补上 `ineqs: string_array`（与正式入口「解不等式/组」一致）——
B10 已决定"24 个重名条目登记可见"，所以是**补齐**而不是删名（重名登记仍 24/0）。

**④ "假绿"全量排查（两类，都已堵）**
- **SKIP 被当成通过**：`cdp-console-sci` 在 CPython 组件未安装时打印 `RESULT|…|0|0` 并 exit 0，
  而 run-all 只看 RESULT 的计数 ⇒ 一个**什么都没测**的用例在总表里显示 OK。
  现在：输出含 `[SKIP]` 就打 SKIP 行、单独计数，TOTAL 补 `(N skipped)`。
- **无宿主时逐条跑 48 条 `cdp-*` 实测**：**全部** exit≠0 且**无 RESULT 行** ⇒ run-all 一律报 `????`，
  不存在"没跑成却报 0|0"的其它入口（`cdp-plot-workspace` 是 exit=2 且无 RESULT，符合设计）。
- 顺带把**跨视图重名**也变成显式登记（`dupmodes.mjs` 原先只打印不判成败）：实测 2 处
  （`逆Fourier变换`、`正交投影`）都只是冗余、不是错，已登记进 `CROSS_VIEW_DUP_OK`；
  **已验证新判据会失败**（把 `傅里叶变换` 也塞进 algebra ⇒ 报跨视图重名 + exit 1）。

**⑤ 仍然卡住的：B14 的 4 页（复平面 / 向量场 / 几何 / 分形）**
这一轮又试了多次启动 Rust 宿主，仍然在**创建窗口**时失败：
`WebView2 error: HRESULT(0x800700AA) 请求的资源在使用中`。宿主自己提示是"另一个实例占着数据目录"，
但下列假设**都已被实测排除**：
- **数据目录**：`MF_WEBVIEW2_DIR` 指到全新目录 → 同样报错（日志确认用的就是新目录）；
- **CDP 端口**：**不带** `--remote-debugging-port` 启动 → 同样起不来；
- **别的实例**：系统里**没有** `mfmath-host-rust.exe`，6 个 `msedgewebview2.exe` 全属 `SearchHost.exe`
  （数据目录是 Windows CBS 那个）；
- **桌面会话**：`query session` 显示 console / session 1 / **Active**，`explorer.exe` 在运行；
- release 与 debug 两个构建**都一样**起不来（内核自检那一步是过的：`list_functions.count = 424`）。

**后续（同一轮内，A 面提交 `e951fdd` 之后）拿到了更精确的定位 —— 卡点不在权限，在 A 面新加的锁代码：**

1. `e951fdd`（A 面：启动前明确报出占用者）让失败信息从"窗口创建 0x800700AA"变成
   **"WebView2 数据目录占用 失败 / 原始错误：拒绝访问 (os error 5)"**，并报出了持有者 `pid=25208`。
2. 查明 **`pid=25208` 早已不存在** —— `%LOCALAPPDATA%\MFMath\webview2\.mf-instance` 是一条**过期锁记录**
   （我实测能**独占打开**该文件 ⇒ 没有活动句柄）。删掉它之后错误依旧，只是变成"（读不到持有者信息）"。
   ⇒ **它的存活判定把"死掉的 pid"仍当成"被占用"，于是宿主会永远起不来，直到有人手工删文件。**
3. **`os error 5` 不是权限问题**：我按 `diagnose-windows-sandbox-acl` skill 跑了那条诊断/修复命令
   （`-Path %LOCALAPPDATA%\MFMath\webview2 -AllowRoot %LOCALAPPDATA%\MFMath`），
   结论是 **`VERDICT=NOT_THIS_CLASS`**：
   `MY_RIGHTS=[FullControl]`、`WRITE_DAC=True`、`WRITE_OWNER=True`、owner = 当前用户、
   `packageObjects=[]` —— **没有任何权限项需要修复，它也没做任何改动**（skill 对这类结论的要求就是"停止并报告"，
   所以我没有手工改权限）。报告留在 `%LOCALAPPDATA%\MFMath\acl-recovery\acl-report-*.jsonl`。
4. **`os error 5` 的根因已用 A/B 实验证实：开目录句柄漏了 `FILE_FLAG_BACKUP_SEMANTICS`。**
   `os error 5` 发生在"获取数据目录句柄"这一步，且**换成全新空目录（`MF_WEBVIEW2_DIR`）同样失败**
   ⇒ 与目录状态无关。Windows 上开**目录**句柄必须带 `FILE_FLAG_BACKUP_SEMANTICS`，否则一律
   `ERROR_ACCESS_DENIED(5)`。实测对照（同一台机器、同一目录、同一时刻）：

   ```
   CreateFileW(dir, GENERIC_READ, share=3, OPEN_EXISTING, flags=0)                  → 失败 err=5
   CreateFileW(dir, GENERIC_READ, share=3, OPEN_EXISTING, flags=FILE_FLAG_BACKUP_…) → 成功
   ```

   同时排除了"环境/沙箱挡子进程"这一可能：**从我的 shell 派生的子进程（node）**
   在同一个目录里 ① 列目录 ✔ ② 写文件 ✔ ③ 开目录句柄 ✔（Node 内部正是带了那个 flag）。
   ⇒ 结论：**A 面的"数据目录占用"检查用 `CreateFile` 开目录时少了一个 flag**，
   加上它就应当能启动（这是 ~1 个 flag 的修法）。
5. 另外建议把**持有者判定**改成"pid 不存活即视为空闲"：本轮实测到
   `%LOCALAPPDATA%\MFMath\webview2\.mf-instance` 里留着 `pid=25208`，而那个进程**早已不存在**
   —— 它仍被报成"被占用"，宿主于是永远起不来，直到有人手工删掉那个文件。

⇒ 宿主起不来这条**没有阻塞住 B14 的验证** —— 下一段说明了绕过办法（同一轮内完成）。

### 0.5.1 B14 那 4 页**已验掉**：`cdp-plot-workspace` **24/0**（6 页 × 两个方向）

宿主起不来，但**工作区往返不依赖宿主**：无宿主时 `settings/bridge.js` 自动降级到 localStorage，
而 B14 的代码路径（载荷形状、挂载时还原、变更即回写）**完全一样**，差别只在存储后端。
所以改用**普通浏览器**做 CDP 目标：

1. `npm run dev`（Vite，`http://127.0.0.1:5173/index.html`）—— 用例的页面匹配规则认 `index.html`，无需改代码；
2. headless Edge：`msedge.exe --headless=new --remote-debugging-port=9222 --user-data-dir=<临时> ...`；
3. `node tests/cdp-plot-workspace.mjs` ⇒ **`RESULT|cdp-plot-workspace|24|0`**。

**逐页结果**（每页 4 条：找到控件 / 能写入 / 落进工作区的键与 kind / 重挂载后还原）：
2D、3D 曲面、复平面、向量场、自由几何（吸附）、分形（迭代次数）**全部通过**。
载荷示例：`/plot/3d` → `{kind:"plot3d",exprInput:"0.5*x+0.25*y",...}`；
`/plot/fractal` → `{kind:"plot-fractal",maxIter:520,...}`；
`/plot/geometry` → `{kind:"plot-geometry",shapes:[],tool:"select",snap:false}`。

⚠ **这条结论的边界要说清楚**：验的是"**浏览器 + localStorage 降级**"这一路，
**没有**在 WebView2 宿主（`sys` 键值桥）上验过。存储后端不同、B14 的代码路径相同；
等宿主能起来后仍应补跑一次（用例已登记，直接跑即可）。

**首轮跑的 5 条失败全是我的用例写错了控件，不是产品缺陷**（两个教训值得复用）：
- **React 的复选框必须 `click()`**：React 对 checkbox/radio 的 `onChange` **由 `click` 事件触发**
  （ChangeEventPlugin 的兼容行为）。我原来直接改 `el.checked` 再派发 `change`/`input` ⇒
  React 的 onChange 根本不响 ⇒"改了但工作区没变"，看起来像产品没存。
  （顺带排查：`cdp-appearance` 里两处同样写法**是对的** —— 那是 Vue 壳的页面，`v-model` 正是监听 `change`。
  全仓库除我之外没有 React 页上这么写的。）
- **分形页的「迭代次数」是 range 滑块**（`min=30 max=1024 step=10`，`.slider`），不是 select。
  我按 `select` + `"512"` 去写，结果写进了同一页的「配色方案」下拉（选项里没有 512 ⇒ 值变空 ⇒
  应用侧抛异常），于是报 `能写入控件 [异常]`。
  现在用 `.slider` + 合法值 `520`；几何页那条也改成**与极性无关**（读当前值→切反面→断言落盘与还原）。

### 0.5.2 顺带修掉一个真问题：`npm run dev` 开着时跑用例会把 dev server 打崩

**现象**：Vite dev server 退出，日志尾部是
`EBUSY: ... syscall: 'watch', path: ...\tests\.cdp-plot-workspace.mjs.<pid>.<guid>.tmpdir\cdp-plot-workspace.mjs.tmp`。
**机制**：Node 26 加载 ESM 时会在**被测文件旁边**生成 `.<name>.<pid>.<guid>.tmpdir/` 临时目录，
而 Vite 默认监听整个工程（`tests/` 也在其中）⇒ 它去 watch 这些刚建又刚删的文件，命中 EBUSY 就崩。
**影响**：一边 `npm run dev` 一边跑用例（开发时很常见）会让 dev server 静默退出。
**修法**：`vite.config.js` 的 `server.watch.ignored` 加上 `**/tests/**`、`**/dist/**`、
`**/.buildtmp/**`、`**/node_modules/**`、`**/.*.mjs.*.tmpdir/**`。
**验证**：改完之后**开着 dev server 跑完整套 `cdp-plot-workspace`，5173 仍在监听** ✓（修复前必崩）。

## 0. 汇总（按严重度排序）

| # | 级别 | 状态 | 位置 | 一句话 |
|---|---|---|---|---|
| **B1** | **P1** | ✅ 已修 | `lib/engine/engineMapExtra.js` + `real_analysis_api.cpp:35` | **10 个可达模式的「区间」参数永远无效**，恒定 `[0,1]`：键名契约失配，用户填了也不生效 |
| **B2** | **P1** | ✅ 已修 | `lib/engine/engineMapExtra.js` + `calcArgs.js` | 概率四模式：`;` 双语义 + 字段错位 ⇒ **弹窗自带的默认示例直接点计算就是错的**；另含 B2③ `解不等式/组` 被截断 |
| **B3** | **P1** | ✅ 已修（**已端到端验证** 14/0） | `MFMath.UI.React/src/plot/PlotPage.tsx` | 绘图页「缩放到适应」按钮**必抛 `ReferenceError`**，用户看到"点了没反应" |
| **B4** | **P2** | ✅ **已修完**（第二轮） | `lib/engine/calcArgs.js` / `CalcView.vue` / `mode-samples.mjs` | 必填参数静默退化成 `0` / `[0,0]` / `[]` ⇒ **算错而不报错**。现在**拒绝计算**并说清缺什么、怎么补 |
| **B5** | **P2** | ✅ **已完成**（第二轮） | `lib/engine/asyncPolicy.js` / `PlotComplexPage.tsx` | 异步通道**接线不完整** ⇒ 重活同步阻塞主线程 |
| **B6** | **P2** | ✅ 已修 | `MFMath.UI.React` 全工程 | `npm run check:types` **曾必失败（64 条）**，这道闸门等于不存在 |
| **B7** | **P2** | ✅ 已修 | `tests/cdp-plot-accuracy.mjs` | 用例存在但**没登记进 `run-all.ps1`**，永远不会被执行 |
| **B8** | **P3** | ✅ 已修 | `tools/build-tutorials.mjs`、`tests/*.mjs` | 4 处硬编码本机绝对路径 ⇒ 换机器/CI 上 `npm run check` 与部分用例直接挂 |
| **B9** | **P3** | ✅ 已按决定完成 | `MFMath.UI.Vue/src/views/plot/*` | Vue 版绘图组是**不可达且无人检查**的源码，"回退路径"会落到漂移代码上 ⇒ 定为**冻结资产**并加断言 |
| **B10** | **P3** | ✅ 已按决定完成 | `engineMap.js` / `viewConfigs.js` | **24 个模式名界面上点不到**（实测：**功能全部另有入口**）+ **2 个参数表悬空** |
| **B11** | **P3** | ✅ **已修**（第二轮） | `src/lib/router/nav.js`（新）/ `App.tsx` / `WelcomeDialog.vue` | 重复的导航表、未过清洗器的 `v-html`：今天不致命，但是会静默变质的陷阱 |
| **B12** | **P4** | ✅ **已修**（第二轮） | 多处 | 注释计数过时、死导出、同一函数实现两遍、死导入 |
| **B13** | **P3** | ✅ **已修**（第二轮，推翻先前决定） | `MFMath.UI.React/src/plot/PlotPage.tsx` | 绘图页从不设置 `emphasis` ⇒ 聚焦的那条曲线不再加粗 |
| **B14** | **P1** | ✅ **已修**（第二轮） | `MFMath.UI.React/src/lib/plotWorkspace.ts`（新）+ 6 个绘图页 + `ReactPlotView.vue` | React 绘图组完全没接工作区 ⇒ 7 个绘图页不会被保存/还原（实测 21/4 → **25/0**） |
| **B15** | **P2** | ✅ **已修**（第二轮） | `MFMath.UI.React/src/plot/PlotPage.tsx` | 2D/极坐标页不再报导出结果 ⇒ 导出没有成功/失败反馈（实测 43/2 → **45/0**） |

---

## B1【P1】10 个模式的「区间」参数永远无效（键名契约失配）

**现象**：在「实分析」等页面选这些模式，填入区间后点计算 —— **区间被完全忽略**，引擎恒定按 `[0,1]` 计算：

| UI 模式 | 引擎 fn | UI 实际发出的参数 |
|---|---|---|
| 平均值 | `integral_mean_value` | `a`、`b`（键名错） |
| 达布和 | `darboux_sum` | `expr`（没有区间） |
| 黎曼可积判定 | `riemann_integrable` | `expr` |
| 微积分基本定理 | `fundamental_theorem` | `expr` |
| 一致连续 | `uniform_continuity` | `expr` |
| 极值定理 | `extreme_value` | `expr` |
| 介值定理 | `intermediate_value` | `value`、`expr` |
| 一致收敛 | `uniform_convergence` | `seq_expr` |
| Weierstrass M-判别 | `weierstrass_m_test` | `seq_expr` |
| 逐项积分 | `termwise_integration` | `n_terms`、`seq_expr` |

**证据（逻辑两端的源码都读过了）**：

1. **引擎侧只认 `interval` 这一个键**【实测·源码】——`MF_Mathematics/real_analysis/real_analysis_api.cpp:34-44`：
   ```cpp
   // 区间参数 [a, b],缺省 (0, 1)。
   void get_interval(const Value& args, double& a, double& b) {
       if (args.is_object() && args.has("interval") && args["interval"].is_array() &&
           args["interval"].size() == 2) { ... return; }
       a = 0.0;
       b = 1.0;          // ← 键不对就恒定落到这里
   }
   ```
   `integral_mean_value` 只读 `expr` + `get_interval`（同文件 `:186-189`）。
2. **该文件里一共有 12 个 handler 走 `get_interval`**（逐行扫描所得）：`darboux_sum:162`、`riemann_integrable:172`、`fundamental_theorem:177`、`integral_mean_value:188`、`uniform_continuity:212`、`extreme_value:221`、`intermediate_value:232`、`uniform_convergence:246`、`weierstrass_m_test:256`、`termwise_integration:264`，外加两个在 UI 里另有正确映射的 `real_rolle_theorem:80` / `real_lagrange_theorem:88`。
3. **UI 侧从没发过 `interval`**【实测·运行】——把引擎读键的 fn 反查 `ENGINE_MAP`：
   ```
   BAD darboux_sum        模式「达布和」              args=[expr]
   BAD riemann_integrable 模式「黎曼可积判定」         args=[expr]
   BAD fundamental_theorem模式「微积分基本定理」       args=[expr]
   BAD integral_mean_value模式「平均值」              args=[a,b,expr]   ← 发的是 a/b，键名就不是 interval
   BAD uniform_continuity 模式「一致连续」            args=[expr]
   BAD extreme_value      模式「极值定理」            args=[expr]
   BAD intermediate_value 模式「介值定理」            args=[value,expr]
   BAD uniform_convergence模式「一致收敛」            args=[seq_expr]
   BAD weierstrass_m_test 模式「Weierstrass M-判别」  args=[seq_expr]
   BAD termwise_integration 模式「逐项积分」          args=[n_terms,seq_expr]
   ```
   （产出这一表的命令见附 B ③。`平均值` 的 `A_OPT/B_OPT` 定义在 `engineMapExtra.js:170`。）
4. **10 个模式全部可在页面上选到**【实测·运行】——所以这是用户可见的，不是死配置。

**为什么"改输入也没救"**：`平均值` 走弹窗路径，弹窗字段（`engineMapExtra.js:370`）是「区间左端/区间右端」，用户填得再对，`buildEngineArgsFromValues` 只会把它们塞进 `a`/`b`；引擎根本不看这两个键。其余 9 个连区间字段都没有 ⇒ **无法通过任何输入修复**。

**对照（说明这是漏项而非设计）**：同一仓库里其它模块的区间类参数是正确的 —— `Fubini定理` 用 `range`（`engineMapExtra.js:286`）匹配 `measure_theory_api.cpp:521-524`；`相图` 用 `x_range/y_range`（`:292`）匹配 `numerical_api.cpp:185-193`；`勒贝格测度`/`外测度` 用 `E`（`:259-260`）匹配 `measure_theory_api.cpp:270-281`。**只有 real_analysis 这一族与引擎不一致。**

**建议修法**：把 `interval` 作为统一键。
- `平均值`：`args` 改为 `[EXPR, {key:"interval", type:"double_array", opt:true}]`，弹窗字段同步改成一项「区间 `[a,b]`」；
- 其余 9 个：补 `{key:"interval", type:"double_array", opt:true}` 参数 + 对应 `EXTRA_VAR_SPECS` 字段（默认值写引擎当前的 `[0,1]`，保持既有行为不变）；
- **更根本的**：`interval` 这个键在 12 个 handler 里被读，值得在 `tools/engine-signatures.mjs` 的生成逻辑里把 helper 读取的键也提取出来（见 B10 附注），否则同类失配还会再出现。

**回归方式**（已实现）：`check-ui.mjs` 的「**区间参数契约**」守卫 —— 固定列出"由 `get_interval`
读区间的 handler"（10 个），断言每个对应模式的 `args` 里都有 `interval` 键。
⚠ 刻意**不去读引擎源码**：那是树外路径（见 B8），会让这条自检在别的机器上跑不动。
守卫已**验证会失败**（临时去掉 `平均值` 的 `interval` → 自检报错并 exit 1）。

**状态**：✅ 已修（2026-10-07）。10 个模式全部改发 `interval`；9 个原先没有弹窗的模式补了
「区间 a,b」字段（默认 `0,1` = 引擎缺省，所以**不改弹窗直接点计算的结果与修复前逐字一致**）。

---

## B2【P1】概率四模式：弹窗默认示例点了就是错的

**现象**：在「概率论与数理统计」页选 `条件概率` / `独立性` / `全概率公式` / `贝叶斯公式`，**打开参数弹窗、什么都不改、直接点「计算」**，得到的是错的结果。

### ① `;` 有两种互斥语义（4 个模式全中）

- `splitSegments`（`src/lib/engine/calcArgs.js:60-74`，切分在 `:67`）把**深度 0 的 `;`** 当"多参数分隔符"；
- `probTableOf`（同文件 `:136-146`，切分在 `:138`）又把 `;` 当"**概率表项分隔符**"（正则 `/[;,]\s*/`）。

同一个 `;` 撞在一起。**实测·运行**（我用 Node 直接调 `buildEngineArgs`）：
```
条件概率  输入 "A_and_B=0.2; B=0.5"  →  {"P":{"A_and_B":0.2},"A":"B=0.5","B":"A"}
独立性    输入 "A_and_B=0.2; B=0.5"  →  {"P":{"A_and_B":0.2},"A":"B=0.5","B":"A"}
```
而 `"A_and_B=0.2; B=0.5"` **正是产品自带的默认示例**（`engineMapExtra.js:457`，`独立性` 在 `:458`）。结果是：`P` 丢了 `B=0.5`，`A` 变成字符串 `"B=0.5"`，`B` 变成 `"A"`。

**根因**：`convertArg` 的 `case "prob_table"` 只拿到**一段**（`calcArgs.js:172`）。代码里其实已有正确范式 —— `string_array` 分支（`:233-237`）会把**剩余所有段 `join(";")` 整组喂过去**；`prob_table` 没有等价逻辑。

**建议修法**：给 `prob_table` 加上与 `string_array` 对称的"剩余段整组 join"分支；或换掉表项分隔符（例如只认 `,`，把 `;` 留给参数分段）。**无论怎么改，都必须保留"默认示例能算对"这条断言。**

### ② `全概率公式` / `贝叶斯公式` 的 args 与弹窗字段语义错位（2 个模式）

`buildEngineArgsFromValues` 是**按位置对齐**字段与参数的。两边的顺序与含义：

| | args（`engineMapExtra.js:325-326`） | 弹窗字段（`:459-460`） |
|---|---|---|
| 第 0 项 | `events`（`prob_table`） | 「概率表 P（`键=值; 键=值`）」 |
| 第 1 项 | `P`（`prob_table`） | 「完备事件组（逗号分隔）」 |
| 第 2 项 | `condition` / `evidence` | 「条件 B」/「已发生的事件」 |

于是第 1 项把**逗号分隔的事件名列表**（`"A1,A2"`）喂给了声明为 `prob_table` 的 `P` ⇒ `probTableOf` 找不到 `=` ⇒ **`P` 恒为空对象 `{}`**。
对照 `条件概率`（`:322` / `:457`）的 `P/A/B` ↔ 「概率表 P / 事件 A / 事件 B」是**一致的**，说明这是遗漏的重排，不是有意设计。

附带证据：`engine-signatures.json` 里这四个 action 的 `required` 含全部参数、`optional:[]`，而 `engineMapExtra.js:322-326` 把它们**全部声明为 `opt:true`** ⇒ UI 不会因缺参数告警，只在引擎侧报"缺少必填参数"。

**建议修法**：把 `events` 与 `P` 的字段标签/顺序按引擎语义对齐（`events` = 完备事件组的概率表，`P` = `B|Ai` 条件概率表），或直接调换 `args` 顺序；再把 `opt` 与引擎 `required` 对齐。改完必须用默认示例做断言。

**回归方式**（已实现）：`check-ui.mjs` 的「**概率表契约**」守卫 —— 凡是参数里有 `prob_table`
的模式，都用**弹窗自带默认值**跑一遍真实构造器，断言每个 `prob_table` 参数非空。
守卫已**验证会失败**（把「全概率公式」的条件概率表改成没有 `=` 的串 → 自检报错、exit 1）。
另建议补一条端到端断言："4 个模式用自带默认示例点计算，结果为预期值"。

**状态**：✅ 已修（2026-10-07）。四个模式用自带默认示例构造出的参数分别是
`{P:{A_and_B:0.2,B:0.5},A,B}` / `{P:{A_and_B:0.12,A:0.3,B:0.4},A,B}` /
`{events:{A1:0.5,A2:0.5},P:{"B|A1":0.1,"B|A2":0.2},condition:"B"}` / 同结构 + `evidence:"B"` ——
`P` 不再是空对象，引擎侧 `total_probability` 的 `P["B|A1"]` 查得到了。

---

## B3【P1】绘图页「缩放到适应」按钮必抛异常

**现象**：在 `/plot/2d`（以及共用同一页面的 `/plot/polar`）点右侧工具栏的 ⤢ 按钮，**什么都不会发生**：坐标轴范围不变，也没有任何界面提示。

**证据**（三条相互独立，合起来是确定性的）：

1. `MFMath.UI.React/src/plot/PlotPage.tsx:292-293`
   ```ts
   const v = view.value;                                  // ← view 是 useState 的值，不是 Vue 的 ref
   const padX = viewW(v) * 0.02, padY = viewH(v) * 0.02;  // ← viewW / viewH 在本文件里根本没声明
   ```
2. **同文件的 import 里没有这两个名字**（`PlotPage.tsx:10` 只有 `defaultView, fitBounds`）：
   ```ts
   import { defaultView, fitBounds } from "@shared/plot/view.js";
   ```
   而 React 侧的另一个文件写法是对的（`src/plot/usePlotSampling.ts:5` 有 `import { viewW, viewH } from "@shared/plot/view.js";`）—— 说明这是漏加 import。
3. `tsc` 报确定性错误【实测·运行】：
   ```
   src/plot/PlotPage.tsx(292,20): error TS2339: Property 'value' does not exist on type 'View'.
   src/plot/PlotPage.tsx(293,18): error TS2552: Cannot find name 'viewW'. Did you mean 'view'?
   src/plot/PlotPage.tsx(293,42): error TS2552: Cannot find name 'viewH'. Did you mean 'view'?
   ```
   `TS2552 Cannot find name` 的含义就是"该标识符在作用域内不存在"，即**必然的运行时 `ReferenceError`**，不是类型不匹配。

**触发链**：`PlotPage.tsx:524` 的按钮 `onClick={zoomFit}` → `zoomFit()`（`:287`）→ `:292` 读 `view.value` 得 `undefined` → `:293` 引用未声明的 `viewW` 立刻抛 `ReferenceError`。
**即使补上 import**，`:304` 的 `v.x0`（`v === undefined`）仍会抛 `TypeError`。**两处都得改。**

**为什么界面上"看不出来"**：React 的错误边界**不捕获事件处理器抛出的异常**，所以不会渲染失败页，表现就是按钮没反应。异常本身不会丢 —— Vue 的全局上报（`MFMath.UI.Vue/src/main.js:22`）会把它写进宿主 `app.log`，记为"未捕获异常"，排查时可去日志核对。

**旁证（同类残留）**：同文件的 `zoomBy()`（`:270-285`）用的是正确的 React 写法 `setView((v) => …)`。可见 `zoomFit` 从 Vue 版 `PlotView.vue` 搬迁时漏改，`view.value` 与 `viewW/viewH` 都是 Vue 侧 `defineModel` + import 的痕迹。

**建议修法**（2 行）：
```ts
// 第 10 行
import { defaultView, fitBounds, viewW, viewH } from "@shared/plot/view.js";
// 第 292 行
const v = view;
```
改完语义与 Vue 版一致：`padX/padY` 是"当前视图的 2%"，用于 fit 时只取**视野内**的点。`PlotPage.tsx:288-291` 的注释解释了为什么必须这么做——采样范围是视图的 1.5 倍，`e^x` 在 x=15 处 y≈3.3e6 这种离群值会把范围算爆，导致"适应后曲线塌成一条线"。

**回归方式**：点 ⤢ 后断言 ①视图确实变了 ②曲线在视野内仍有横向展开（不能塌成竖线）。
**已写进 `tests/cdp-plot-accuracy.mjs` 的新第三节**（借 `window.__mfPlot` 读真实视图 + 单独断言
没抛异常 —— 只数像素证明不了"视图变了"）。该节同时把"页面加载后先绕到另一条绘图路由再回来"
补上，**强制 ReactPlotView 重挂**，于是这条用例不再依赖"上一个用例有没有动过视图"。

**状态**：✅ 已修（2026-10-07，代码 **+ 已端到端验证**）。`viewW/viewH` 已 import、`view.value`
已改回 `view`；`tsc` 里那 3 条确定性错误随之消失（64 → 61）。
**e2e 实测（Rust 宿主）**：`cdp-plot-accuracy` **14/0** —— 其中新加的三条断言全过：
`排障钩子 window.__mfPlot 可用`、`「缩放到适应」按钮存在且可点`、**`点击「缩放到适应」不抛异常`**、
`「缩放到适应」确实改变了视图`（before `y0=-10.46` → after `x0=-6.30,y1=11.91`）。
即：这个按钮在原实现下**必抛 `ReferenceError`**，现在真的不抛了、也真的改了视图。

---

## B4【P2】必填参数静默退化成 `0` / `[0,0]` / `[]` ⇒ 算错而不报错

**现象**：表单里没给（或没给全）必填的结构化/数值参数时，`calcArgs` 用"合法但无意义"的默认值填上，引擎照常计算并返回**看起来正常结果**。用户以为自己算的是输入的那个东西。

**证据**【实测·运行】（Node 直接调 `buildEngineArgs`）：
```
某点导数  "x^2"     → {"expr":"x^2","point":0}            ← 静默算成 f'(0)
两点距离  "(1,2)"   → {"p1":[1,2],"p2":[0,0]}             ← 第二个点变成原点
正交投影  "1,1"     → {"vector":[1,1],"basis":[]}          ← basis 空
点积      "1,2"     → {"u":[1,2],"v":[]}
简单函数  "1,2"     → {"coefficients":[1,2],"sets":[]}
高斯模糊  "1,2,3"   → {"signal":[1,2,3],"sigma":0}
```

**根因**：`src/lib/engine/calcArgs.js:192-200`
```js
/** 必填参数拿不到值时的兜底（仍交给引擎校验并报错） */
function fallbackOf(type) {
  switch (type) {
    case "double": case "int": return 0;
    case "bool": return false;
    case "point": return [0, 0];
    default: return STRUCTURED.has(type) ? [] : "";
  }
}
```
注释说"仍交给引擎校验并报错"，但这些**都是合法值**——引擎没有理由报错。最严重的是 `某点导数`（fn=`diff_at`，引擎签名 `required=[expr,point]`）：`point=0` 合法，引擎正常返回 `f'(0)`。

`正交投影` 尤其值得注意：它在**两个视图**里都可达（`viewConfigs.js:254` 泛函分析与 `:294` 线性代数），却**没有多参数弹窗**，所以用户从可见 UI 只能填一段，`basis` 必为 `[]`；除非知道未文档化的 `;` 写法（`1,1; [[1,0],[0,1]]`）才可能通。

**建议修法**：区分"可选参数缺省"与"必填参数缺失"。
- 必填缺失时**不要兜底**，直接返回一个明确的错误（复用 `unmappedHint` 那类行内提示通道），或在 UI 上强制弹窗收集；
- `point` 不应默认 `[0,0]`、必填 `double` 不应默认 `0`；
- 可选参数继续走 `:263-267`"**整个键省略**、让引擎用自己的默认"这条既有正确路径。

**回归方式**：为每种结构化类型加一条断言——"缺少必填参数时必须给出可见提示，不得静默代入默认值"。

**状态**：✅ **已修完**（2026-10-07，第二轮）。前半（消除静默）见上；后半（**拒绝计算**）已做完：
先给 10 个会走到兜底的**页面模式**补齐样本（真引擎验过），再把 `CalcView` 改成"缺必填参数就不调引擎、
直接说清缺什么、怎么补"，并删掉已无用的 `warn` 字段 / 模板分支 / `.cb-warn` 样式 / 旧译文。详见 §0.3。

> **下面这份 32 条的清单要打折看**（原文保留，供对照）：它是按 **415 个 ENGINE_MAP 模式**探的，
> 而其中**只有 10 个是页面模式**（会真正被 UI 和套件点到的那些）——
> `二项式展开`、`二项式通项`、`某点导数`、`最大公约数`、`扩展欧几里得`、`分布函数`、
> `数列通项`、`傅里叶级数`、`傅里叶系数`、`复傅里叶系数`。
> 其余 22 个是**没有页面入口**的模式（引擎里有、界面上点不到），所以"拒绝计算"这条路实际只需
> 那 10 条的样本就够，**不必**给 32 条都补。

```
（原先按 415 个模式探出的清单，仅作对照）
两点式直线 p2=[0,0] · 两点距离 p2=[0,0] · 中点 p2=[0,0] · 某点导数 point=0
二项式展开 b="",n=0 · 二项式通项 b="",n=0,k=0 · 傅里叶系数 n=0 · 傅里叶级数 n_terms=0
复Fourier系数 n=0 · 扩展欧几里得 b=0 · 最大公约数 b=0 · 数列通项 n=0 · 分布函数 x=0
等差数列 d=0,n=0 · 等比数列 q=0,n=0 · 对偶空间基 basis=[] · 内积(泛函) domain=[],g=""
线性泛函求值 x=[] · Hahn-Banach 延拓 subspace_dim=0  （共 32 个）
```

---

## B5【P2】异步通道**接线不完整** ⇒ 重活同步阻塞主线程（附：本文原先结论有误，已更正）

> ### ⚠ 更正声明（同一轮内自查发现）
> 本节原先写的是「异步通道**整体未接线、是死代码**」「**没有任何** `.vue` 或 `.js` 调用
> `engineCallAsync` / `shouldRunAsync`」。**那是错的。**
> 取证时只 grep 了 `MFMath.UI.Vue/src`，**漏查了 `MFMath.UI.React/src`** —— 而
> `PlotFractalPage.tsx:2-3,143-153` **早就接了**：`shouldRunAsync("mandelbrot", …)` 判据 +
> `engineCallAsync` 后台通道 + `AbortController` 取消 + 进度回调，写得比本节原先建议的还完整。
> 教训记在 §0.1：**跨工程共享逻辑的项目，取证必须覆盖两个工程。**

**现象（更正后）**：`asyncPolicy.js` 那份判据只被**部分**调用点使用。已接线的只有分形页的
`mandelbrot`；而 `complex_grid`（复平面）、`expr_eval_grid`（3D 曲面 / 向量场）、以及
**计算页的全部模式**与**函数工具箱的全部 424 个 action** 仍是同步调用 —— 后者最要紧：
它们能跑到 `ALWAYS_ASYNC` 那 28 个"没有上界"的符号运算（积分、因式分解、级数展开…），
同步调用会占住渲染进程主线程，界面白屏并被系统判定"未响应"。

**证据**：
1. **已接线（反例，本文原先漏掉的）**【静态】：`MFMath.UI.React/src/plot/PlotFractalPage.tsx:2-3`
   ```ts
   import { engineCall, engineCallAsync, isHosted } from "@shared/bridge.js";
   import { describeWork, shouldRunAsync } from "@shared/engine/asyncPolicy.js";
   ```
   `:143` `if (shouldRunAsync("mandelbrot", args))` → `:145` `await engineCallAsync(...)`，
   否则 `:153` `engineCall(...)`；`:138-140` 还用 `AbortController` 让新一次渲染取消上一次。
2. **未接线**【静态】：
   - `MFMath.UI.Vue/src/views/calc/CalcView.vue` —— 全部模式（本轮修复前）
   - `MFMath.UI.Vue/src/views/tools/ToolboxView.vue:127` —— 全部 action（本轮修复前），且
     `asyncPolicy.js:67` 提到的"工具箱的『后台运行』勾选"**当时并不存在**
   - `MFMath.UI.React/src/plot/PlotComplexPage.tsx:141,162`（`complex_grid`，n≤1000 ⇒ 最多 1e6 点）
   - `MFMath.UI.React/src/plot/Plot3DPage.tsx:118`、`PlotVectorPage.tsx:124-125`（`expr_eval_grid`）
   - `MFMath.UI.React/src/plot/usePlotSampling.ts:204`（隐式方程/二元区域的网格采样）
   - ⚠ 原先列在这里的 `PlotFractalView.vue` / `PlotComplexView.vue` / `Plot3DView.vue` /
     `PlotVectorView.vue` 都属 **B9 那份不可达的 Vue 绘图组**，拿它们当证据是错的（虽然结论
     恰好也成立）—— 正确的对象是上面这些 React 页面。
3. **"计算中…"确实不显示**【静态】——`CalcView.vue` 里 `patchBlock({computing:true})` 之后
   在**同一个 tick 内**就同步执行 `engineCall`，Vue 没有机会重绘，`{{ b.computing ? "计算中…" }}`
   渲染不出来。（这一条仍然成立；本轮修复后变成"重的活会显示、轻的活照旧不显示"。）

**本轮修法（Vue 侧）**：
- `CalcView.vue`：新增 `callEngine(fn, args, block, mode)` —— `shouldRunAsync` 判为轻的仍走
  **同步**（保持既有行为与既有用例时序），重的走 `engineCallAsync` 并把进度写进状态栏；
  `calc` / `onVarConfirm` 改成 `async`。
- `ToolboxView.vue`：同样的分流 + 新增「强制后台」勾选（这正是 `asyncPolicy.js:67` 里
  `opt.force` 的用途）+ 运行中状态；`window.__mfToolbox.call` 随之改成可 await（已确认没有
  任何测试用它）。

**仍未接（建议单独一轮）**：React 的 `PlotComplexPage` / `Plot3DPage` / `PlotVectorPage`
与 `usePlotSampling:204`。之所以不顺手改：
- `PlotComplexPage.fetchGrid` / `fetchConformalGrids` 是**同步函数且会 throw**，被绘制路径
  直接调用；改成 async 会级联到整条绘制链（573 行的画布组件），属结构性重构而非接线；
- `asyncPolicy.js:12-15` 明确要求"**绘图页每条曲线一次的采样保持同步**"（毫秒级，且 await
  会把采样时序拆碎）—— 这几处要逐个判断属于哪一类，不能一刀切；
- **本沙箱跑不了端到端**，而这类改动最容易在"重绘时序"上出问题，改完必须用
  `cdp-plot-complex` / `cdp-plot-3d` / `cdp-plot-vector` 那几条实测。

**回归方式**：
- 轻活仍同步：断言 `shouldRunAsync` 判为 false 的模式走的仍是同步通道（行为无变化）；
- 重活走后台：跑 `mandelbrot` 大数据量或 `factor_integer(2^61-1)`，断言调用期间 UI 仍可交互
  （或断言走的是 `DispatchJob` 通道），并断言 `computing` 状态至少渲染过一帧。

**状态**：✅ **已完成**（2026-10-07，第二轮）：Vue 侧照旧；React 侧复平面页的 `complex_grid`
已改走后台通道（`apply()` 本来就是 async，级联只有一个 `await`），3D / 向量场 / 网格采样三处
**刻意保持同步并写明算术理由**（96²=9216、41²=1681、180²=32400，都低于 2.5e5 阈值 ⇒ 接异步是空转），
并抽出了共用的 `lib/jobProgress.ts`。详见 §0.3。

---

## B6【P2】React 工程的类型检查是一道用不了的闸门

**现象**：在 `MFMath.UI.React` 下执行 `npm run check:types`（= `tsc --noEmit -p tsconfig.json`）**必然失败**，退出码 2【实测·运行】。这个工程声明了类型检查，却拦不住任何回归——真正的缺陷混在 64 条噪音里看不出来（B3 本可以被它当场拦住）。

**证据**：64 条诊断的分布【实测·运行】：

| 文件 | 条数 |
|---|---|
| `src/plot/GeometryCanvas.tsx` | 22 |
| `src/plot/PlotGeometryPage.tsx` | 18 |
| `src/plot/PlotCanvas.tsx` | 8 |
| `src/plot/PlotPage.tsx` | 7（含 B3 的 3 条） |
| `src/plot/usePlotSampling.ts` | 7 |
| `src/plot/PlotFractalPage.tsx` | 1 |
| `vite.config.ts` | 1 |

| 错误码 | 条数 | 含义 |
|---|---|---|
| `TS2339` | 33 | 属性不存在（绝大多数由下面的 `as never` 造成） |
| `TS2488` | 11 | `never` 不可迭代 |
| `TS2322` | 8 | 赋值类型不匹配 |
| `TS2345` | 8 | 实参类型不匹配 |
| `TS2552` | 2 | **找不到名字**（= B3，是真 bug） |
| `TS2307` | 1 | 找不到模块 `node:url` |
| `TS7006` | 1 | 隐式 any |

**三个根因**（分开处理，别一起糊掉）：

**① 「逃生舱」写成 `as never`，反而制造了约 60 条错误**
4 处：`src/plot/GeometryCanvas.tsx:118`、`:143`、`src/plot/PlotGeometryPage.tsx:48`、`:97`（形如 `const d = s.data as never`）。`never` 是 bottom type，于是后面每次 `d[0]`、`d.length`、解构全部报错。
**建议**：按 `ShapeType` 定义 `data` 的判别联合（`{type:"point"; data:[number,number]} | {type:"circle"; data:[[number,number],number]} | …`），让 `switch (s.type)` 自己收窄——这段代码本来就在做这件事，类型只是没表达出来。

**② 缺 `@types/node`**
`vite.config.ts:3` `import { fileURLToPath, URL } from "node:url";`，而 `package.json` 的 `devDependencies` 里没有 `@types/node` ⇒ `TS2307`。
**建议**：装 `@types/node`；或把 `vite.config.ts` 从 `include` 移出。倾向前者——构建脚本也值得被检查。

**③ 真实的类型不一致**（别用 `any` 盖掉）
- `PlotPage.tsx:66,120,316`：`defaultView()` 可能返回 `{x0:null,…}`（未配置固定范围时的形状），与 `View`（要求 `number`）不兼容。
- `PlotPage.tsx:102`：`emphasis` 不在 `Expr` 上。
- `usePlotSampling.ts:123,129,136,142,152`：采样回调返回 `Sample[]` 而签名要求 `[number,number][]`（`Sample` 允许 `null`，这正是"断点/无定义"的表达）⇒ 建议把签名改成 `Sample[]`。
- `PlotFractalPage.tsx:142`：`(p)` 隐式 any。

**关键前提**：**Vue 侧的类型检查是干净的**（`npm run check:types` → exit 0）【实测·运行】。原因是 Vue 的 `tsconfig.json` 只 `include: ["src/**/*.ts"]`（即只有 `lib/ai/*.ts` 那 7 个文件），而 React 的 `include` 是整个 `src`。所以这不是"React 代码更差"，是**检查面不同**。
修之前先明确：React 侧要不要把 `src` 全量纳入检查？**要**，就按上面三条修干净；**不要**，就把 `include` 收窄并在注释/README 里说明白——别留一个必红的命令。

**回归方式**：`npm run check:types` 退出码 0；并把它纳入提交前检查。

**状态**：✅ 已修（2026-10-07）。**60 条 → 0 条**。做法与残余：
- `Shape` 改成**判别联合**（`ShapeDataMap`：每个 `ShapeType` → 它真实的元组布局），
  于是 `switch (s.type)` 能真正收窄 `s.data`，4 处 `as never` 全部消失（原来的类型只是
  没把这段代码本来就在做的判断表达出来）；`PlotCanvas.tsx` 新增 `ParsedExpr`（把
  `plotMath.js` 在不等式/区域分支里**真的会挂上**的 `op`/`axis`/`boundary` 声明出来）；
  `Sample[]` 的 `null` 是"断点/无定义"的表达，所以放宽回调签名而不是抹掉 null。
- **没有引入任何 `any` / `@ts-ignore` / `@ts-expect-error` / `as never`。**
- **残余（已披露）**：`usePlotSampling.ts` 里有 **1 处** `as AdaptiveSampleFn`，原因是
  `sampling.js` 的 JSDoc 声明 `(ts)=>[number,number][]`，而它的实现**刻意**处理/发出 `null`
  断点（`sampling.js:53-67`）—— 不修 Vue 侧那个 JSDoc 就无法无断言地放宽。属**上游 JSDoc 过窄**，
  建议下次动 `sampling.js` 时一并把声明改准。
- `@types/node` 装不上（`npm install` 在本环境 EPERM），所以按文档给的备选方案把
  `vite.config.ts` 移出 `include`，并在 `tsconfig.json` 里写明"想一起检查就先装 `@types/node`
  再把它加回来"——**没有**用 `@ts-ignore` 去糊那条 `TS2307`。
- ⚠ `npm run build` 在本沙箱跑不了（esbuild spawn EPERM，与代码无关）；替代验证是直接
  esbuild 打包 `src/main.tsx` 成功（exit 0）。**发布前请在沙箱外跑一次真正的 build。**

---

## B7【P2】一个端到端用例存在但从未被执行

**现象**：`tests/cdp-plot-accuracy.mjs` 在磁盘上，但**不在** `tests/run-all.ps1` 的 `$tests` 数组里（数组见 `run-all.ps1:14-85`），整套回归永远不会跑它。

**证据**【实测·运行】——文件与登记做机器对账：
```
cdp test files: 47
未登记进 run-all.ps1 的用例：cdp-plot-accuracy
反向（登记了但没有对应文件）：（空）
```
唯一漏网的就是它，正好是绘图准确性那条。

**为什么值得单列**：项目自己的 `docs/FRONTEND-FIXES.md` §2 记过**同一个坑**（"`cdp-engine-coverage.mjs` 一直没登记进 `run-all.ps1`（49 个 `.mjs` 里 41 个已登记）→ 已登记"）。说明"加了用例忘了登记"**会复发**，值得做成构建期自检而不是靠人记。

**建议修法**：
1. 把 `"cdp-plot-accuracy"` 加进数组。**注意位置**：不要放在 `cdp-engine-coverage` 之后——后者必须留最末，它走遍所有视图与模式，会污染后面用例的"干净初态"（`run-all.ps1:80-84` 有实测记录：混在同一会话里三条用例从 46/0、9/0、66/0 变成 43/3、?/3、63/3）；
2. 更根本的：在 `tools/check-ui.mjs` 里加一条断言——`tests/cdp-*.mjs` 每个文件都必须在 `run-all.ps1` 里登记（允许显式白名单并写明理由）。

**回归方式**：`node tests/cdp-plot-accuracy.mjs` 能打出 `RESULT|…` 行；`run-all.ps1` 汇总里出现它。
**更根本的一条已实现**：`check-ui.mjs` 的「**端到端用例无漏登记**」守卫 —— `tests/cdp-*.mjs`
每个文件都必须登记进 `run-all.ps1`（允许 `NOT_IN_SUITE` 白名单但要写理由），反向也查
"登记了却没有文件"。守卫已**验证会失败**（造一个未登记用例 → 自检报错、exit 1）。

**状态**：✅ 已修（2026-10-07）**并已实跑**。已登记（放在绘图组里，**不放到最后** ——
`cdp-engine-coverage` 必须留在最末，`run-all.ps1:80-84` 有实测记录）。自检现在打印
`cdp-* 47 个，已登记 47 个`。
**实跑结果**：这条用例**一跑就抓到东西**（B7 的价值当场兑现）：
- 它的视口判据写死了 ±10×±10，而真实 y 跨度是 20·h/w ⇒ `x` 那条线两端被误判（**判据错，已修**，见 §0.2 第 3 条）；
- 顺带把 B3 的「缩放到适应」验成了真的（**14/0**）。
这正是"没用例覆盖 = 没人知道它对不对"的实例。

---

## B8【P3】4 处硬编码的本机绝对路径

**现象**：`MF_UI` 多处工具/用例写死了 `C:\Users\fsafsafsa\…`，其中还有指向**另一棵树**的。本机上这些路径都在，所以**现在没坏**；但换机器、换用户名、或在 CI/受限环境里，`npm run check` 与部分用例会直接失败。

**证据**【实测·运行，逐条列出】：

| 文件:行 | 硬编码内容 | 影响 |
|---|---|---|
| `tools/build-tutorials.mjs:28-29` | `C:\Users\fsafsafsa\Desktop\MVS知识库\Multifunctional系列\Multifunctional-Mathematics\MF_Tutorial\tutorials`（**v1 那棵树**） | `npm run check` 的第一步就是它 ⇒ 路径不在就全挂。有 `MF_TUTORIAL_SRC` 可覆盖 |
| `tests/audit-modes.mjs:19` | `C:/Users/fsafsafsa/Desktop/cppcshap/MF_Mathematics/build/bin/Release/probe_call.exe` | 指向 `cppcshap` 那棵树，**与当前目录布局已不是同一棵树** |
| `tests/probe-implicit.mjs:7` | 同上 | 同上 |
| `tests/showfn.mjs:5` | `C:/Users/fsafsafsa/Desktop/cppcshap/MF_Mathematics` | 同上 |

**另外一处越出工程写盘**（同根因，性质不同）：
`tools/build-tutorials.mjs:31` + `:476` 把教程 YAML 归档到 `<v2.0>/docs/tutorials-src`——**在 `MF_UI` 之外**。

**我的实测记录（说明"退出 1"到底是谁的锅）**：本会话跑 `node tools/build-tutorials.mjs`，它**成功解析并写出** `src/tutorials/tutorials.json`（18 篇、55928 字节、JSON 合法），随后在"拷贝 YAML 归档"那一步以 `EPERM: operation not permitted, copyfile` 退出 1。该失败是**我的沙箱只允许写 `MF_UI` 之内**造成的，**不是代码缺陷本身**。但它精确暴露两个真实问题：
1. 这个脚本**依赖树外可写**才能跑完 ⇒ 任何受限/CI 环境都跑不通；
2. 路径是**写死的本机值**，不是相对工程的推导。

**建议修法**：
- 教程源：改成相对推导（默认 `../../MF_Mathematics/../MF_Tutorial/tutorials` 之类，允许 `MF_TUTORIAL_SRC` 覆盖）；路径不存在时**明确报错并说明怎么设**，而不是抛 `EPERM`；
- 归档目标：改为可配置或写进 `MF_UI` 内，并对"不可写"给出可读降级（归档是留档，不该阻断主产物生成）；
- `tests/*.mjs` 三处：从环境变量或仓库相对路径解析 `MF_Mathematics`，找不到就 `SKIP` 并打印原因（项目已有 `SKIP` 不算失败的先例：`cdp-console-sci` 在组件未安装时 SKIP，见 `run-all.ps1:41-43`）。

**回归方式**：把工程拷到另一个路径（或设一个不存在的 `MF_TUTORIAL_SRC`）跑 `npm run check`，应得到**可读的失败说明**，而不是 `EPERM`。

**状态**：✅ 已修（2026-10-07）。新增 `tests/engine-paths.mjs` 作为**树外路径的唯一解析处**
（环境变量 → 相对 v2.0 推导 → 可读报错），`build-tutorials.mjs` / `audit-modes.mjs` /
`probe-implicit.mjs` / `showfn.mjs` 全部改用它；YAML 归档改为可配置且**失败只警告不中断**。
验证：`build-tutorials.mjs` 在本沙箱（归档写不进去）**从 exit 1 变成 exit 0**，
`npm run check` 由此**第一次整条跑通**；`showfn.mjs` 能解析到正确那棵树的引擎源码。
另注：原来那两条硬编码指向的是 `Desktop/cppcshap/MF_Mathematics` —— **另一棵树**，
早就不是这份代码所跑的引擎了；正确的那份在 `<v2.0>/MF_Mathematics`。

---

## B9【P3】Vue 版绘图组是"不可达的源码"，回退路径已漂移

**现象**：`src/views/plot/` 下 6 个文件（`PlotView`/`Plot3DView`/`PlotComplexView`/`PlotFractalView`/`PlotGeometryView`/`PlotVectorView`，约 127KB）以及 `src/components/plot/` 下大部分组件（约 103KB）**没有任何地方引用**，既不在构建产物里，也不在类型检查范围内。而路由注释把它们说成"回退路径"。

**证据**【静态】：
1. `src/router/index.js:29-38` 把 7 条 `/plot/*` 路由**全部**指向 `../components/plot-react/ReactPlotView.vue`；
2. 全 `src` 搜 `views/plot/` 的引用：**只有这些文件互相引用**，无任何外部引用（唯一命中是 `router/index.js:28` 的一句注释）；
3. `MFMath.UI.Vue/tsconfig.json` 的 `include` 是 `["src/**/*.ts"]` ⇒ `.vue` 与 `.js` **不参与类型检查**；
4. 反向证据：实现已搬到 React 且**两侧已经分叉**——`src/lib/plot/cartesian.js:139` 的 `drawPolarGrid` 在 Vue 侧无人调用（`PlotCanvas.vue` 用的是自己文件内 `:233` 的同名本地函数），但在 React 侧是活的（`MFMath.UI.React/src/plot/PlotCanvas.tsx:8` 有 import）。同一个"死代码"结论在两个框架下**不通用**。

**为什么这不只是"脏"**：`router/index.js:28` 写着"要回退就把对应这行改回 `../views/plot/XXX.vue`"。但那些文件没有吃到 React 侧的任何修复（例如 B3 同类问题、极坐标参数识别等），也没有任何用例覆盖它们（`cdp-plot-*` 系列全部打 React 页面）。**照着注释回退，会落到一份已经漂移、且无人验证的代码上。**

**建议修法（二选一，别悬着）**：
- **删**：确认 React 版是唯一实现后，删掉 `views/plot/*` 与仅被它们引用的 `components/plot/*`，并把 `router/index.js:26-28` 的注释改成事实描述；
- **留**：明确标注为"冻结的回退资产"，在 `router/index.js` 注释里写清 ①它已不跟随修复 ②回退前必须先跑通哪些断言，**并纳入某个检查**（例如构建期断言"未被引用的 `views/plot/*` 与白名单一致"），否则它会继续无声漂移。

**状态**：✅ **已按决定完成**（2026-10-07）：**保留为冻结的回退资产**，并让它"看得见"。
1. `router/index.js` 里那段注释改成**事实描述**：这 6 个文件已不跟随修复、不在构建图里、
   不在类型检查范围、没有任何用例覆盖 —— 所以"把路由改回去"**不等于回退到一个能用的版本**；
   真要回退，得先把它们接回来、补跑 `cdp-plot-*` 全套，再删掉下面这条断言。
2. `check-ui.mjs` 新增守卫（`FROZEN_VUE_PLOT_FILES`）：
   - 目录里的 `.vue` 必须与白名单**逐一对应**（增删文件都要改白名单）；
   - 并且断言**没有人 import 它们**（只看真正的 `import` 语句，router 里那句"改回
     ../views/plot/XXX.vue"是注释，不会误报）—— 一旦出现引用就报错，因为那意味着
     有人在回退或误接。
   守卫已**验证会失败**（临时造一个 `src/.tmp-importer.js` → 报错、exit 1）。
   自检现在打印：`冻结的 Vue 绘图组：6/6 个文件在位，被 import 0 处`。

---

## B10【P3】24 个模式界面上点不到 + 2 个参数表悬空

**现象**：`ENGINE_MAP` 里有条目、引擎也有实现，但**任何页面的模式下拉里都没有**，用户完全点不到。

**证据**【实测·运行】——集合运算（命令见附 B ⑥）：
```
ENGINE_MAP 项数        : 415
页面 modes 并集(去重)  : 391
不在任何页面的模式数    : 24
页面有、但 ENGINE_MAP 没有的模式 : 0
```
这 24 个是：
```
化简 | 解不等式组 | 局部极值 | 全局最值 | 幂级数展开 | 级数求和 | 级数敛散性 |
逆傅里叶变换 | 旋转体体积(圆盘法) | 旋转体体积(柱壳法) | 中点 | 两点式直线 |
等差数列 | 等比数列 | 回路积分 | 柯西积分公式 | 洛朗级数 | Zeta 级数 | Lp 范数 |
Banach 空间判定 | Hahn-Banach 延拓 | 内积(泛函) | Hilbert 空间判定 | 谱分类
```
另有 **2 个 `ENGINE_VAR_SPECS` 键悬空**（既无 `ENGINE_MAP` 条目、也不在任何视图）：
```
["数值微分", "矩阵乘法"]
```
（这正是 `docs/FRONTEND-FIXES.md` §1 第 7 条记的"矩阵乘法够不着"。现况：它**仍不是**一个可选的"模式"，但**已可通过「函数工具箱」调用**——`ToolboxView.vue:8,66,119` 以 424 条签名表为数据源。所以它不是完全无入口。）

**为什么 `check:ui` 没报**：`tools/check-ui.mjs` 的可达性断言认的是"**该模式能在某页面选到 _或_ 该 fn 已被页面某模式覆盖**"。这 24 个的 fn 都在别处被覆盖了，所以它判为可达、`NOT_EXPOSED` 登记表为空（自检输出"取不到 0 个"）。于是"**模式名**点不到"这件事不在任何检查范围内。

**建议修法**：逐个决定——补进某个页面的 `modes`（大多数看起来该在对应学科页里）、或从 `ENGINE_MAP` 删掉、或登记进 `NOT_EXPOSED` 并写明理由。无论选哪种，都建议把 `check-ui.mjs` 的判据从"fn 是否被覆盖"**收紧或补充**为"模式名是否可选到，否则必须显式登记"，否则这条永远静默。

**状态**：✅ **已按决定完成**（2026-10-07）：**判据收紧 + 24 个显式登记**。
`check-ui.mjs` 现在区分两档：① 名字选不到**且** fn 也没被任何页面覆盖 → 硬失败（当前 0 个）；
② 名字选不到、但 fn 已被页面别的模式覆盖 → **必须登记进 `DUPLICATE_NAME_GROUPS`**，
否则报错。24 个已逐个登记（同一个理由组），并注明其中 `解不等式组` **不只是重名**：
它的 `args` 是空的，而页面同 fn 的 `解不等式/组` 声明了 `ineqs`，即那个旧名字即便挂出来
也构造不出参数，**建议直接删**。
守卫已**验证会失败**（把「化简」从登记表里去掉 → 报错、exit 1）。
自检现在打印：`重名模式登记：已登记 24 个，未登记 0 个`。

> ### 🔎 一条重要的更正：这 24 个**不是"24 个用不到的能力"**
> 收紧判据时逐个算了它们的 `fn`，结论是 **24/24 都在页面上另有名字可达**（见下表）。
> 所以原先把本项描述成"24 个模式界面上完全点不到"，虽然字面不假（**名字**确实点不到），
> 但容易读成"24 项能力缺失" —— **那是错的**：它们是**同一引擎函数的重复命名**，
> 用户其实用得到，缺的只是"这个旧名字"。真正的缺陷是**命名冗余**，不是功能缺口。

实测对应表（`A → B` 读作"A 这个名字选不到，功能可由页面上的 B 选到"）：

```
化简            → 表达式化简            中点          → 中点坐标
两点式直线       → 斜率 / 直线方程       局部极值       → 极值
全局最值         → 最值                 幂级数展开     → 级数展开 / 幂级数
回路积分         → 围道积分              柯西积分公式    → Cauchy积分
洛朗级数         → Laurent级数           旋转体体积(圆盘法) → 旋转体体积(圆盘)
旋转体体积(柱壳法) → 旋转体体积(壳)        等差数列       → 等差数列第n项
等比数列         → 等比数列第n项          级数求和       → 数列求和 / 无穷级数求和
级数敛散性       → 级数收敛判定           内积(泛函)     → 内积空间
谱分类           → 特征值问题            逆傅里叶变换    → 逆Fourier变换
Lp 范数          → Lp范数               Zeta 级数      → Riemann ζ
Banach 空间判定   → Banach空间            Hilbert 空间判定 → Hilbert空间
Hahn-Banach 延拓 → Hahn-Banach定理       解不等式组      → 解不等式/组  ← 且本条目 args 为空
```

---

## B11【P3】两处重复/未清洗的数据源

**① `NAV_GROUPS` 被手抄了一份**
`MFMath.UI.React/src/App.tsx:28-80` 复制了 Vue 的 `src/router/registry.js` 导航表（分组、名称、路由、顺序），注释自己也标了"后续应收口：把 `NAV_GROUPS` 抽到零依赖模块（如 `lib/router/nav.js`），两边共用"（`App.tsx:22-24`）。

- **今天不是线上风险**：`App.tsx` 只被 React 工程的 `main.tsx` 使用，即**只在 React 独立 dev server 下生效**；出货路径是 Vue → `ReactPlotView.vue:28-36` 的 `LOADERS` 直接加载各页面模块，不经过 `App.tsx`。
- **但它是漂移陷阱**：`App.tsx` 里 `MIGRATED_PLOTS` 只含 `/plot/2d` 与 `/plot/polar`（`:88`），与 `ReactPlotView.vue` 的 7 条 `LOADERS` 已经不一致——谁按 `App.tsx` 判断"迁移进度"就会得出错的结论。
- **建议**：抽成零依赖的 `src/lib/router/nav.js` 两处共用；或删掉 `App.tsx` 里那份改为 import 同一数据。

**② `WelcomeDialog.vue:79` 用 `v-html` 渲染且不过清洗器**
```html
<p class="w-desc" v-html="card.description" />
```
- **今天安全**：`card.description` 是组件内的**硬编码字面量常量**（`:23`、`:33`、`:43`、`:54`），不是外部内容。
- **但已有前车之鉴**：教程富文本因"快照 + `replaceWith` 提升节点后不再递归"造成过一条真实绕过（`<p><img src=x onerror=…></p>` 清完仍留 `onerror`），修复在 `src/lib/tutorial/targets.js:177-198`，且已挂 `window.__mfSanitize` 供端到端断言。本项目自己把这类东西定性为"安全边界"。
- **建议**：要么给 `description` 也过一遍 `sanitizeTourHtml`（零成本），要么在注释里写明"仅限硬编码常量，**不得**改为从数据文件读取"，并加一条构建期断言挡住后一种改法。

**状态**：✅ **已修**（2026-10-07，第二轮）。
- ✅ ② `WelcomeDialog.vue` 的 `v-html` 过了 `sanitizeTourHtml`（第一轮）。
- ✅ ① `NAV_GROUPS` 收口**已做**：搬进零依赖的 `src/lib/router/nav.js`，`registry.js` 再导出，
  React 侧改从 `@shared/router/nav.js` 引入（删掉那份 61 行手抄副本）。详见 §0.3。

---

## B12【P4】注释计数过时 / 死导出 / 重复实现

**① 同一仓库三种计数口径**（`grep` 可证）

| 位置 | 写的 | 实际 |
|---|---|---|
| `lib/engine/engineMap.js:3-4` | "324 项 / 19 项" | 那是 RAW；**对外导出是 415 / 130**（`{...RAW, ...EXTRA}`，`:21-22`） |
| `views/calc/CalcView.vue:5-6` | "引擎映射（324 项）/（19 项 VAR_SPECS）" | 同上 |
| `views/tools/ToolboxView.vue:3,6-7` | "424 个 action"、"engineMap.js，371 个 action" | **这两个是准确的** |

**② 死导出 / 死导入**（跨文件引用数为 0）：
`bridge.js:236,246` 的 `engineJobPoll` / `engineJobCancel`（注释里写明是"诊断用"，属有意保留的
诊断口，**不算缺陷**）、`engineMap.js` 的 `getEngineSpec`/`getVarSpec`、`resultFormat.js` 的 `resultSummary`；
`calcArgs.js` 的 `STRUCTURED` 与 `splitSegments`（导出但仅本文件内用）；
**`toEngineExpr` 被 `CalcView.vue` import 但在该文件内零使用**。
> ⚠ 此处原先还列了 `asyncPolicy` 的三个函数与 `engineCallAsync` —— **那是错的**（见 B5 更正声明）：
> `shouldRunAsync` / `describeWork` / `engineCallAsync` 都在 `PlotFractalPage.tsx` 里被真实调用。
> `estimateWork` 只被前两者内部调用。

**③ 重复实现**
- **`hasEngineMode` 实现了两遍**：`engineMap.js:25-27` 与 `calcArgs.js:356-358`，逻辑逐字相同。
- **`textArg` 选择逻辑在 `calcArgs.js` 复制了 3 份**：`:224-227`、`:305-306`、`:331-332`。
- **64 个模式在 `engineMap.js`(RAW) 与 `engineMapExtra.js`(EXTRA) 各定义一次**，靠 `{...RAW, ...EXTRA}` 静默覆盖。这是刻意设计（`engineMapExtra.js:2-13` 有说明），但**没有任何机制能发现"改了 RAW 却忘了 EXTRA 覆盖"**。名字近似而 fn 相同的重复达 39 组，例如 `化简`/`表达式化简`、`中点`/`中点坐标`、`旋转体体积(圆盘法)`/`旋转体体积(圆盘)`、`回路积分`/`围道积分`（后者 args 还不同）——**每组的第一个正是 B10 那 24 项不可达配置之一**。
- `viewConfigs.js` 的 `single` 字段 14/14 全为 `false`，于是 `CalcView.vue:212,215` 与模板 `:408-412` 的 `v-if="!single"` 都是死分支。

**建议**：注释计数改成从 `Object.keys(ENGINE_MAP).length` 动态取（或在 `check-ui` 里断言注释数字与实际一致）；删死导出/死导入；`hasEngineMode` 只留一处并 import；把 `textArg` 选择抽成一个函数。

**状态**：✅ **已修**（2026-10-07，第二轮）。
- ✅ `textArg` 的三份复制抽成 `pickTextArg(args, {skipWholeString})`（两种口径有意不同，注释写明不能合并）。
- ✅ fixture 的重复键：**36 条死条目**删除，重复数 **29 → 0**（真实值是 29，不是 `check-ui` 原先报的 28
  —— 它的正则带行首锚点，漏掉了"一行两条目"紧凑行里的那个 `协方差`；正则已去掉锚点）。
- 其余各项见下：
- ✅ 注释计数：`engineMap.js` 与 `CalcView.vue` 里的 324/19 改成"以 `npm run check:ui` 打印的为准"，
  并写明当前是 **415 / 139**（不再写死一个会过期的数字）。
- ✅ 删掉 3 个**零引用**导出：`getEngineSpec`、`getVarSpec`（`engineMap.js`）、
  `resultSummary`（`resultFormat.js`）—— 删前逐个 grep 过（含 `tests/`、`tools/`），引用数均为 0。
- ✅ `hasEngineMode` 去重：现在只在 `engineMap.js` 实现一处，`calcArgs.js` 原样再导出
  （既有调用点不用改）。已逐模式比对：**对全部 415 个模式，新旧实现结果完全一致**。
- ✅ 删掉 `CalcView.vue` 里 `toEngineExpr` 的死导入。
- ❌ **未做**：把 `textArg` 那 3 份重复的选择逻辑抽成一个函数（它在参数构造的**关键路径**上，
  本轮已经改过这段代码两次，不宜再叠一次重构）；`viewConfigs` 的 `single` 死分支（14/14 全 false）
  也保留——它是防御性的，删掉反而会在将来真出现 `single:true` 的视图时静默失效。

---

## B14【P1】React 绘图组完全没接工作区（Vue→React 迁移掉的功能）

**现象**：工作区（保存 / 载入 / 另存为）**对 7 个绘图页全部失效** —— 绘图页写的表达式、
视图范围、参数一个都存不下来；`run-all.ps1` 里 `cdp-workspace` 的失败清单只有
`/tools/console` 与 14 条 `/calc/*` 路由，**一条 `/plot/*` 都没有**。

**证据**：
1. 全 `MFMath.UI.React/src` grep `workspace` / `setPage` / `getPage` / `@shared/workspace`：
   **零命中**（命中的全是 `data-tour` 属性与"原版 `workspace.py`"这类注释）。
2. 对照**已冻结的 Vue 版**：`src/views/plot/PlotView.vue:20` `import { getPage, setPage } …`、
   `:35` 从工作区还原、`:701` `setPage(route.path, capturePlot())`。
3. 包装层也没接：`components/plot-react/ReactPlotView.vue` 里同样零命中。
4. 实测（本机 Rust 宿主 + 本轮 dist）：`cdp-workspace` 21/4、`cdp-shortcuts-prefs` 22/1；
   后者的失败值就是 `(window.__mfWorkspace.pages()["/plot/2d"] || {}).view === null`
   —— 它假定"新打开的绘图页会把 view 存进工作区"，而这个前提在 React 版**不成立**
   （顺带说明：**B6 的 `initialView` 包装层是无辜的**，那条失败不是它引起的）。

**根因**：绘图组整组迁到 React 时，只搬了渲染层与算法（`@shared/plot/*`），
没搬"与外壳的契约"——工作区就是其中之一（同一类还有 B13 的 `emphasis`、B15 的导出反馈）。

**建议修法**：给 React 各绘图页补上工作区契约（形状照 `PlotView.vue` 的 `capturePlot()`）：
- 挂载时 `getPage(route.path)` 还原（表达式 / 视图 / 参数）；
- 变更时 `setPage(route.path, { kind:"plot", expressions:[…], view:{…}, params:{…} })`；
- 各页形状不同（2D/极坐标、3D、复平面、向量场、几何、分形），**逐页定义并逐个断言**，
  别只修 2D 就以为完了。
- 建议把这条写进 `check-ui.mjs`：`src/plot/*.tsx` 里出现 `setPage` 的页数必须与绘图路由数一致
  —— 否则下次再迁一页又会漏（B13/B14/B15 是同一个成因的三次重演）。

**回归方式**：`cdp-workspace`（4 条）与 `cdp-shortcuts-prefs`（1 条）转绿。

**状态**：✅ **已修**（2026-10-07，第二轮）。新增 `src/lib/plotWorkspace.ts`，6 个绘图页全部接上
（2D/极坐标的载荷形状与 Vue 版逐字一致；3D/复平面/向量场/几何/分形是**补齐** —— 它们在 Vue 版里
也从来没接过）。`ReactPlotView.vue` 给 2D/极坐标补传了 `routePath`。
实测：`cdp-workspace` **21/4 → 25/0**、`cdp-shortcuts-prefs` **22/1 → 23/0**。详见 §0.3。

---

## B15【P2】React 绘图页不再报导出结果（导出变成"静默"）

**现象**：点「导出图片」后，界面上**没有任何反馈** —— 不知道导到了哪里、成功与否；
路径写不进去时也不说原因。Vue 版会显示"已导出图片：<路径>（尺寸，大小）"/"导出失败：<原因>"。

**证据**：
1. 那组文案**只存在于已冻结的 Vue 视图**里：
   `PlotView.vue:657-658`、`PlotFractalView.vue:35-36`、`PlotComplexView.vue:42-43`、
   `PlotVectorView.vue:25-26`、`Plot3DView.vue:26-27`、`PlotGeometryView.vue:21-22`
   —— React 侧一条都没有。
2. 实测 DOM（`/plot/2d`，本机宿主）：页面上有 `.side-status`，但它显示的是**采样**状态
   （`引擎采样 1 条曲线 · 300 点 · 范围 …`）；`.status` 不存在；外壳的 `#statusText`
   仍停在"引擎已连接（WebView2 桥）"（`ReactPlotView.vue` 根本没给 PlotPage 传
   `onStatusText`，所以那条出口也是断的）。
3. 实测套件：`cdp-export-image` **43/2**，两条失败的判据正是
   `界面上说明了导出到哪里（不是静默）` 与 `路径写不进去时给出失败原因（不静默）`。

**建议修法**：与 B14 同源 —— 导出后把 `exportCanvas()` 的返回值变成一条可见消息
（写进页面的 `.side-status`；同时给 `ReactPlotView` 接上 `onStatusText`，让 2D/极坐标页
也能用外壳状态栏）。六页都要，别只修一页。

**回归方式**：`cdp-export-image` 的 `43/2` → `45/0`。

**状态**：✅ **已修**（2026-10-07，第二轮）。`PlotPage.exportImage()` 不再丢掉返回值，把
`已导出图片：<路径>（尺寸，大小）` / `已取消导出` / `导出失败：<原因>` 写进页内状态行，
并修掉写死的 `routePath:"#/plot/2d"`。另外 5 页本来就报（只有 2D/极坐标这一页是漏的）。
实测：`cdp-export-image` **43/2 → 45/0**。详见 §0.3。

> 关于"顺带给 `ReactPlotView` 接上 `onStatusText`"：**没做**，原因说清楚 ——
> 外壳的状态栏由 Vue 的 `App.vue` 用 `statusText` 这个 ref 持有，React 子树拿不到它；
> 硬接要么写 DOM（`#statusText`，会被 Vue 下次渲染覆盖，属 hack）、要么为此引一个 store/事件通道，
> 收益只是"同一句话多显示一处"，不值得。页内状态行（测试读的也是它）已经把用户可见的问题解决了。

---

## 附 A. 我**没有**证到的（别当成结论）

诚实起见列出来，避免下一个人把"未验证"当"已排除"。**以下是第二轮结束时的状态。**

1. **端到端已经真跑过了（第二轮）** —— 第一轮这条写的是"一条 CDP 用例都没跑"，现已作废：
   完整跑过一次（49/50 条，见 §0.2），针对本轮改动又跑了一遍（见 §0.3）。具体到各条：
   - **B3**：已**浏览器实测**（`cdp-plot-accuracy` 14/0 —— ⤢ 按钮不抛异常、视图确实改变）；
   - **B1/B2/B2③**：已过**真引擎**逐模式验证（`audit-modes` 393/0）；
   - **B5 的 Vue 侧**：已由 `cdp-calc-workspace` 65/0、`cdp-modes-render` 190/0 覆盖；
   - **`npm run build`**：沙箱解除后可跑，只需把 `TEMP`/`TMP` 指到工程内（§0.1 第 2 条）。
2. **⚠ 最重要的一条：B14 里那 5 个页面的工作区接线，没有任何测试覆盖。**
   `cdp-workspace` / `cdp-shortcuts-prefs` 只碰 `/plot/2d`（和 `/plot/polar` 的挂载路径），
   所以 3D / 复平面 / 向量场 / 几何 / 分形的"存进去—读回来"**只过了类型检查和我的代码审阅**，
   **没有**被端到端验证过。它们的载荷形状是我按各页状态新设计的（Vue 版里这 5 页从来没接过，
   没有参照物）。**改动这几页或动工作区格式前，先给它们各写一条 e2e 断言**（形如
   `pages()["/plot/3d"].exprInput === "…"`，并验证重挂载后确实还原）。
3. **`cdp-engine-coverage` 没跑完**（要 45 分钟，见附 C）。它已跑到的部分里有两类现象**尚未定性**：
   `双曲线方程 结果为空`，以及 `抛物线方程`/`斜截式直线`/`点斜式直线` 三条 ≥30 秒无响应。
   **没有确认**它们是前端问题、引擎问题还是宿主问题 —— 别当结论用。
   > **补充（第二轮后）**：这一条已经跑到底了，结论见 **§0.3.1** —— **296/7**，
   > 7 条全是 `[超时]`，且**我没能复现**（四个可疑模式单独跑都不卡）。
   > `双曲线方程 结果为空` 属于第一次实跑（旧构建）的观察，本轮没有再出现。
4. **`engineMap.js` / `engineMapExtra.js`（约 105KB）不是逐行通读**：本次核对了 ①三种表的形状与规模
   ②`interval` 键族（B1）③概率四模式（B2）④`fallbackOf` 调用面（B4）⑤可达性集合（B10）
   ⑥重复键（靠 `check-ui`）。**其余条目的参数是否与引擎签名一一对应，没有系统核对。**
5. **`engine-signatures.json` 不能当"引擎契约的权威"用**：该表**系统性遗漏通过 helper / lambda
   读取的参数**（例：`product_measure` 表里 `params={A,B}`，而 `measure_theory_api.cpp:505-514`
   用 lambda 直接读 `mu`/`nu`；`integral_mean_value` 表里 `params={expr}`，而实际读 `interval`）。
   它的 `required` 也是**多分支并集**而非真必填（例：`variance` 表 `required=[expr,pmf_data]`，
   实际 `probability_api.cpp:237-249` 是 `data`/`pmf_data`/`expr+range` 三分支互斥）。
   ⇒ **不要拿这张表判"UI 少传了必填参数"**。我据它得到的"41 个必填参数从未声明 / 156 处 `opt:true`
   与必填冲突"两份清单**大部分是假阳性**（已逐条回源码核实），故**不作为缺陷上报**。
6. **`docs/FRONTEND-FIXES.md` §5 里另外两条仍未验证**：`CodeEditor.vue` 的 async 竞态、
   `history/store.js` 去抖与 `reload()` 撞车（第三条 `cartesian.drawPolarGrid` 死代码已复核，见 B9）。
7. **`matrix_multiply` 是否需要正式"模式"条目**：见 B10，属产品决策，我没当成缺陷。
8. **`cdp-modes-render` 的 191 → 190 已解释**（见 §0.3）：候选集被 `slice(0, MODES_PER_VIEW)` 封顶，
   我补的样本替换了候选集合，其中一个模式改为返回非数值结果，于是"引擎的数值出现在界面上"那条
   按其分支被跳过。**不是**少跑了一个模式，也**不是**失败。

## 附 B. 怎么复查这份清单

```powershell
$UI = "<...>\Multifunctional-Mathematics-v2.0\MF_UI"

# ① Vue 侧检查：类型 + 引擎签名 + 教程/键盘/i18n/可达性（当前全绿，exit 0）
#    内含本轮新增的 3 条守卫：区间参数契约 / 概率表契约 / 端到端用例无漏登记
npm run check --prefix "$UI\MFMath.UI.Vue"
#   ⚠ check:ui 第一步 build-tutorials.mjs 会读树外的 v1 教程源，并往 <v2.0>\docs 归档。
#     修好 B8 之后，归档失败**只警告、不再中断** —— 所以受限环境下这里也应当是 exit 0。

# ② React 侧类型检查（当前全绿，exit 0；修复前是 64 条红）
npm run check:types --prefix "$UI\MFMath.UI.React"

# ③ B1：把引擎「读 interval 的 fn」反查成 UI 模式（BAD = 该模式发不出 interval）
#    先在引擎源码里扫出读 interval 的 handler（行号 → 函数名）：
#      Select-String -Path "<v2.0>\MF_Mathematics\real_analysis\real_analysis_api.cpp" -Pattern 'get_interval\(args'
#    再在 MFMath.UI.Vue 目录下，用 ENGINE_MAP 反查这些 fn 对应的 UI 模式：
cd "$UI\MFMath.UI.Vue"
node --input-type=module -e "
const em = await import('./src/lib/engine/engineMap.js');
const fns = ['darboux_sum','riemann_integrable','fundamental_theorem','integral_mean_value','uniform_continuity','extreme_value','intermediate_value','uniform_convergence','weierstrass_m_test','termwise_integration'];
for (const fn of fns) for (const [m,v] of Object.entries(em.ENGINE_MAP).filter(([,v])=>v.fn===fn))
  console.log((v.args.some(a=>a.key==='interval')?'OK  ':'BAD ')+fn.padEnd(22)+' 模式「'+m+'」 args=['+v.args.map(a=>a.key).join(',')+']');
"

# ④ B2 / B4：直接跑参数构造器（在 MFMath.UI.Vue 目录下）
cd "$UI\MFMath.UI.Vue"
node --input-type=module -e "
const m = await import('./src/lib/engine/calcArgs.js');
for (const [mode,expr] of [['条件概率','A_and_B=0.2; B=0.5'],['平均值','x^2; 0; 2'],['某点导数','x^2'],['两点距离','(1,2)']])
  console.log(mode, JSON.stringify(expr), '->', JSON.stringify(m.buildEngineArgs(mode, expr)));
"

# ⑤ B5：证明异步通道零调用（输出应只有 asyncPolicy.js / bridge.js 的定义与注释，
#         任何 .vue 命中都说明它其实接了线）
Get-ChildItem "$UI\MFMath.UI.Vue\src" -Recurse -Include *.js,*.ts,*.vue |
  Select-String -Pattern 'engineCallAsync|shouldRunAsync|estimateWork|describeWork|engineJobPoll|engineJobCancel' |
  ForEach-Object { $_.Path.Substring($UI.Length+1) + ':' + $_.LineNumber + '  ' + $_.Line.Trim() }

# ⑥ B10：可达性集合运算（同样在 MFMath.UI.Vue 目录下执行）
node --input-type=module -e "
const em = await import('./src/lib/engine/engineMap.js');
const vc = await import('./src/lib/engine/viewConfigs.js');
const page = new Set(); for (const v of Object.values(vc.VIEW_CONFIGS)) for (const m of (v.modes||[])) page.add(m);
const map = Object.keys(em.ENGINE_MAP);
console.log('MAP', map.length, '页面并集', page.size, '点不到', map.filter(k=>!page.has(k)).length);
console.log(map.filter(k=>!page.has(k)).join(' | '));
console.log('悬空 VAR_SPECS:', JSON.stringify(Object.keys(em.ENGINE_VAR_SPECS).filter(k=>!map.includes(k))));
"

# ⑦ B7：用例与登记的差集（应只剩空集）
$all = Get-ChildItem "$UI\MFMath.UI.Vue\tests\cdp-*.mjs" | % BaseName
$reg = (Get-Content "$UI\MFMath.UI.Vue\tests\run-all.ps1" -Raw |
        Select-String '"([a-z0-9\-]+)"' -AllMatches).Matches | % { $_.Groups[1].Value }
$all | ? { $reg -notcontains $_ }

# ⑧ B3：两行静态证据
Select-String -Path "$UI\MFMath.UI.React\src\plot\PlotPage.tsx" -Pattern 'view\.value|viewW|viewH'
Select-String -Path "$UI\MFMath.UI.React\src\plot\PlotPage.tsx" -Pattern 'from "@shared/plot/view\.js"'

# ⑨ B8：还有哪些本机绝对路径
Select-String -Path "$UI\MFMath.UI.Vue\tools\*.mjs","$UI\MFMath.UI.Vue\tests\*.mjs" -Pattern 'C:\\Users\\|C:/Users/'

# ⑩ 全套端到端（需先 build Vue 与 Release 宿主；耗时，cdp-engine-coverage 必须留最后）
powershell -ExecutionPolicy Bypass -File "$UI\MFMath.UI.Vue\tests\run-all.ps1"
```

## 附 C. 当前状态与后续（第二轮结束后）

**BUGS.md 里的 15 项已全部处理完**（B1–B15），另有 3 项脚手架缺陷（BOM / 宿主路径 / `-NoLaunch`）。
逐项状态见 §0、§0.1、§0.2、§0.3；两轮的改动与验证证据都在那四节里。

**唯一没跑完的是 `cdp-engine-coverage`**：它要逐个点过 393 个页面模式，本机约 **45 分钟**。
跑它之前请先读 §0.2 第 5 条那条操作警告：

> **不要中途 Ctrl-C。** 引擎没有取消钩子（`bridge.js:154-158` 自己写明 `CancelJob` 只是停止等待），
> 中途杀掉会留下一支没跑完的后台任务占住引擎，之后页面上**任何同步 engine 调用都会永久阻塞**
> —— 渲染进程卡死，连 `location.hash` 这种纯 DOM 读取都超时（实测卡死 30+ 分钟）。
> **要中断就先停宿主**（杀 `mfmath-host-rust` 再起），恢复只要几秒。

**下一轮值得做的（按价值排）**：

1. **给 B13/B14/B15 加一条构建期检查**（三者同一成因：绘图组迁 React 时只搬了渲染层与算法，
   没搬"与外层的契约"）。建议在 `check-ui.mjs` 里断言：`src/plot/*.tsx` 中出现
   工作区（`usePlotWorkspace`）、导出反馈、`emphasis` 的页数，必须与绘图路由数一致。
   否则下次再迁一页还会漏 —— 这一轮就是同一个坑踩了三次。
2. **`cdp-engine-coverage` 已跑到底：296/7，7 条全是 `[超时]`**（详见 §0.3.1）。
   我已用套件的原样本逐模式试过复现，**四个可疑模式单独跑都不卡**（60 秒探活全程 0–3 ms），
   所以**不能归因到单模式**，也不是本轮改动引入的（第一次实跑在同一位置附近同样卡住）。
   下一步该做的是一个**专门的分段实验**（拆视图跑 / 冷启动对比 / 中途记录 DOM 与内存增长），
   在那之前别把这 7 条当成"前端算错了"。
3. **B9/B10 的可选清理**（两者都已按拍板"做好并登记"，不是欠账）：
   B9 的冻结断言现在会拦住"悄悄接回来"；B10 的 24 条重名模式已显式登记、不再静默，
   要清理建议从 `解不等式组`（`args` 为空、坏掉的重复条目）开始。
4. **`dupmodes.mjs` 报的 2 处跨视图重名**（`逆Fourier变换` 在 calculus/harmonic-analysis、
   `正交投影` 在 functional-analysis/linear-algebra）：**不是** fixture 问题（它读的是页面模式表），
   属 B10 同一类"同名两组"。目前无害，值得知道。
5. **环境类**：`npm run build` 若报 `esbuild-…: Access is denied`，把 `TEMP`/`TMP` 指到工程内再构建
   （见 §0.1 第 2 条）；`tests/run-all.ps1` **必须保留 UTF-8 BOM**（见 §0.1 脚手架①）。

---

## 附 D. B13：绘图页"聚焦的那条曲线"不再加粗（第二轮已修）

**现象**：在 2D 绘图页选中某一行表达式时，Vue 版把**那条曲线画粗**以表示"当前编辑的是它"；
React 版没有这个效果。

**证据**【静态，由 B6 那轮核对类型时发现，我已逐条复核】：
- Vue（原实现）：`MFMath.UI.Vue/src/views/plot/PlotView.vue:95`
  `emphasis: row.id === activeId.value`；
- React（现实现）：`MFMath.UI.React/src/plot/PlotPage.tsx:121` 传的是 `emphasis: r.emphasis`，
  而**全 React 工程没有任何地方给 `r.emphasis` 赋过值** ⇒ 恒为 `undefined`；
- **画布侧仍在消费它**，所以这不是"字段没人用"，而是"产的人没了"：
  `PlotCanvas.tsx:224` `ctx.lineWidth = c.emphasis ? 4 : 2.5`（另见 `:307`、`:437`）。

**为什么当时没顺手修**：修它是一处**行为变化**（线宽会随选中行改变），而 B6 那轮的任务边界
明确是"不改运行时行为"，所以那一轮只把 `emphasis?: boolean` 声明到 `Expr` 上、让既有透传
通过类型检查，并把它登记下来（`ExpressionList.tsx:15-19` 也留了同样的说明）。

**建议修法**（一行）：`PlotPage.tsx:121` 的 `curves` memo 改成
`emphasis: r.id === activeId` —— `activeId` 在该组件里已有（`PlotPage.tsx:84`）。

**回归方式**：选中第 2 行后断言第 2 条曲线的连续像素厚度大于其它行（或直接断言
传给 `PlotCanvas` 的 `curves[1].emphasis === true`）。

**状态**：✅ **已修**（2026-10-07，第二轮 —— **推翻了先前"只留记录"的决定**，用户指示"全部修复"）。
按上面的"一行修法"改成 `emphasis: r.id === activeId`。若你更想保留"任何曲线都不加粗"的现状，
把这一行改回 `r.emphasis` 即可。
若将来要恢复，按上面的"一行修法"改，并配一条断言即可。
> 注：本项与 **B14/B15 是同一个成因**（绘图组迁 React 时只搬了渲染层，没搬与外层的契约）。
> 下一轮修 B14/B15 时，建议把这三条一起处理 —— 它们都是"React 侧没有产生方"。
