# 工具区：控制台 / 函数工具箱 / 历史 / 搜索页

> **本文只回答一个问题：工具区这四个入口各做什么、界面怎么用、哪些事它们有意不做。**
>
> 与同层其它文档的分工：
> - [README.md](README.md) —— 两个工程的构建归属与**用例归属**；本文只讲行为；
> - [ARCHITECTURE.md](ARCHITECTURE.md) —— 分层、路由与导航表、i18n、样式；本文只点到这四个入口的路由；
> - [ENGINE-BINDING.md](ENGINE-BINDING.md) —— `ENGINE_MAP` / `calcArgs` / `asyncPolicy` / 可达性守门；本文只用它们，不重复其规则；
> - [../link/FEATURES.md](../link/FEATURES.md) —— 宿主侧实现细节：组件体积与 SHA-256、搜索的六类失败、`Poll` 与推送；本文只讲界面看到的部分；
> - [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) —— 哪些"没有"是**有意不做**（搜索不翻页、绘图操作不入历史）。

**核对时间**：2026-10-07 · **权威源**：`MF_UI/MFMath.UI.Vue/src/views/tools/`、`src/components/{console,history}/`、`src/lib/{console,search,history,math,engine}/`、`src/lib/push.js`、`src/lib/bridge.js`、`MFMath.Host.Rust/src/{console,search}.rs`

---

## 0. 先纠一处形态：侧栏「工具」是 **3 个页面 + 1 个对话框**

"工具区四个页面"这个说法对三个成立，对「历史」不成立 —— 它是**顶栏按钮打开的模态对话框**，不在侧栏导航里、没有自己的路由。

| 名称 | 形态 | 入口 | 载体文件 |
| --- | --- | --- | --- |
| 搜索 | **路由页面** | 侧栏「工具 → 搜索」`/tools/search`；顶栏「搜索」 | `src/views/tools/SearchView.vue` |
| 控制台 | **路由页面** | 侧栏「工具 → 控制台」`/tools/console` | `src/views/tools/ConsoleView.vue` |
| 函数工具箱 | **路由页面** | 侧栏「工具 → 函数工具箱」`/tools/toolbox` | `src/views/tools/ToolboxView.vue` |
| 历史 | **模态对话框** | 顶栏「历史」按钮 → `showHistory` | `src/components/history/HistoryDialog.vue` |

证据：

- 侧栏「工具」组只有 **3 项**：`nav.js:61-74`（`搜索` / `控制台` / `函数工具箱`）；
- 路由表由 `NAV_GROUPS` 循环生成，所以这 3 项各有一条真实路由：`router/index.js:92-106`；三条视图在 `REAL_VIEWS` 里显式注册：`router/index.js:48,51,54`；
- 历史是 `App.vue` 里的一个布尔量 + 组件：`showHistory`（`App.vue:243`）、打开（`App.vue:246` 的 `openHistory`）、挂载（`App.vue:451` 的 `<HistoryDialog v-if="showHistory" …>`）；
- 端到端用例也按这个形态断言：顶栏「历史」打开的是 `.hist-dialog`（`tests/cdp-history-search.mjs:105-106`），顶栏「搜索」**跳到 `/tools/search`**（`tests/cdp-history-search.mjs:204-208`）。

> 三页都只在**有宿主**（`MFMath.exe`）时才有完整能力；浏览器预览下各自给出明确说明而不是报错（下文逐页写）。

---

## 1. 控制台（`/tools/console`）

给普通用户写小程序试算用。**计算仍全部由 C++ 引擎完成**：Python 侧只有 `mfmath`（ctypes 封装）、C++ 侧只有导入库，界面自己不算任何数学（`ConsoleView.vue:8-11`）。

### 1.1 界面布局

| 区域 | 控件 | 出处 |
| --- | --- | --- |
| 左·工具条 | 语言下拉、示例下拉、`运行 ▷` / `终止 ■`、`清空输出`、`重置` | `ConsoleView.vue:394-404` |
| 左·编辑区 | CodeMirror 6 编辑框（`Ctrl+Enter` 运行） | `ConsoleView.vue:409-410` |
| 左·提示 | "每次运行都是新进程" | `ConsoleView.vue:414-417` |
| 左·标准输入 | 单行输入框，运行时喂给程序 | `ConsoleView.vue:418-421` |
| 右·状态栏 | 退出码徽标、总耗时、C++ 编译耗时、`输出已截断`、状态文案 | `ConsoleView.vue:427-435` |
| 右·输出 | `输出` / `错误` 两个 `<pre>` | `ConsoleView.vue:438-445` |
| 右·组件 | Python / C++ 两行状态 + `安装`，安装中显示进度条与`取消` | `ConsoleView.vue:447-470` |

示例代码按语言分开：Python 3 个、C++ 3 个，切语言时回到该语言的第 0 个示例（`ConsoleView.vue:95-213`，`@change="loadSample(0)"` 在 `:394`）。

`重置` 与 `清空输出` 是两件事：前者清输出**并**把代码退回示例，后者只清输出（`ConsoleView.vue:316-326`）。

### 1.2 编辑器：CodeMirror 6，内核与语言包都按需加载

| 能力 | 怎么做的 | 出处 |
| --- | --- | --- |
| 惰性加载内核 | `CodeEditor.vue` 里**只**用 `await import("../../lib/console/editor.js")`，不静态 import | `CodeEditor.vue:58-68` |
| 按语言分开的语法包 | `LANGS = { python: () => import("@codemirror/lang-python"), cpp: () => import("@codemirror/lang-cpp") }`，另有 `langCache` | `editor.js:37-43` |
| 切语言不并发 | 一条 `langChain` Promise 链串行化；排队期间被取代的请求直接跳过（连语言包都不 import） | `CodeEditor.vue:119-130` |
| 语法高亮 | `HighlightStyle` + `syntaxHighlighting`；**颜色全部取项目 CSS 变量**，所以主题切换即时生效、不用重建编辑器 | `editor.js:97-158` |
| 行号 / 括号配对 / 搜索 | `lineNumbers()`、`bracketMatching()`、`highlightSelectionMatches()`、`searchKeymap`（Ctrl+F 面板） | `editor.js:194-222` |
| 补全 | `EditorState.languageData` 挂一个补全源；候选来自引擎 `list_functions`，`boost: 99` 让引擎函数名压过 Python 内置名 | `editor.js:55-74,185-187` |
| `Tab` / `Mod-Enter` | `Tab` 缩进（多选时整块缩进）；`Mod-Enter` 触发 `run` | `editor.js:161-171,215` |
| 回退 | 内核或语言包 import 失败 → 退成 `<textarea>`，功能少但**写得进去、跑得起来**；回退态只保留 `Ctrl+Enter` 运行 | `CodeEditor.vue:62-68,140-145` |
| 测试钩子 | `EditorView` 句柄挂成编辑区 DOM 属性 `host.__mfEditor`（不是全局变量） | `CodeEditor.vue:89-92` |

`Ctrl+Space` 按引擎函数名补全（`ConsoleView.vue:410` 的 placeholder 文案；空词要显式触发见 `editor.js:63`）。C++ 模式下候选 = 8 个内置 `mfm::` 名字 + 424 个引擎函数名（`ConsoleView.vue:35-38`）。

函数表**只在进页面时取一次**（引擎函数是固定的）：`engineCall("list_functions", {})`（`ConsoleView.vue:361-367`）。取不回来也不影响编辑器可用 —— 补全源在候选为空时返回 `null`，后到的候选经 `setCandidates` 随时生效（`editor.js:57-60,235`）。

用例覆盖（`tests/cdp-console.mjs:145-213`）：首页**不加载**编辑器内核、进控制台才加载、Python 与 C++ 是两个不同 chunk、切回 Python 不再重复下载、配色跟随主题。判定语言包身份用的是**内容指纹**而不是文件名（两个语言包打包出来都叫 `index-<hash>.js`）。

### 1.3 两种语言与可选组件（界面怎么用）

- 语言下拉的默认项是 `Python`；**`C++` 只在 `comps.cpp.ready` 为真时才出现**（`ConsoleView.vue:58-62`）。用 `ready` 而不是 `installed` 是刻意的：工具链解压到一半时让 C++ 出现在下拉里只会让用户点了报错（`ConsoleView.vue:55-57`）。
- 组件状态行把"要下多大 / 从哪来 / 上次是否下到一半"说清楚（`ConsoleView.vue:80-85`）：
  - 包已在本地 → `未安装（组件包已在本地，约 N MB，点安装即可）`；
  - 有 `.part` → `未安装（上次只下到 N MB，点安装会接着下）`；
  - 都没有 → `未安装（点安装会从官网下载约 N MB）`。
- 安装作业：`installComponent("python"|"cpp")` 拿 `jobId`，然后**每 400 ms 轮询** `installStatus(jobId)`（`ConsoleView.vue:240-267`）。连续 150 次（≈60 秒）查不到状态就停下并说明原因，不会无限轮询（`ConsoleView.vue:231-238,248-256`）。
- 取消：`cancelInstall(jobId)`（`ConsoleView.vue:87-91`，按钮在 `:468`）。取消后已下载的部分保留，下次点安装接着下（`ConsoleView.vue:463-464`）。
- 两块组件的**体积、SHA-256、下载路径名与安装名的差异（`mingw` vs `cpp`）**见 [../link/FEATURES.md](../link/FEATURES.md) §5.1 —— 本文不重复。
- 现状：站点上**两个 zip 尚未上传**，清单如实标 `available:false`（[../OPEN-ITEMS.md](../OPEN-ITEMS.md):119）。所以界面现在通常显示"未安装（点安装会从官网下载约 N MB）"，而这条联网路径尚无成功记录，见 §6。

⚠ **一条会影响界面的已知不一致**：`cpp.ready` 只检查 `lib\libmf_mathematics.a` 与 `include\mfmath.hpp` 两件（`console.rs:279`），而实际运行还要 `include\mfmath_autorun.hpp`（[../link/FEATURES.md](../link/FEATURES.md) §5.5）。后果是"下拉里有 C++，一点就报组件不完整"。本文不重复实现细节，只提示这条判据是**界面可见性**的依据。

### 1.4 运行与输出：数据一律来自轮询，推送只是"叫页面去看"

```
运行 ▷ → consoleStart(lang, code, stdin) → runId
       → setInterval(tick)                    ← 有 push 500ms / 无 push 200ms
tick() → consolePoll(runId) → 改写输出与状态  ← 权威数据只在这里
```

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 开始 | `con.Start(language, code, stdin)` 返回**裸 id 字符串** | `console/bridge.js:104-112`；[../link/FEATURES.md](../link/FEATURES.md) §6.1 |
| 轮询间隔 | 有 `push` 桥 **500 ms**，无 `push` 桥 **200 ms** | `ConsoleView.vue:286-288` |
| 推送做什么 | 订阅 `console.run` 只做两件事：改一句状态文案、立刻 `tick()` 一次 | `ConsoleView.vue:352-360` |
| 推送**不带**输出 | `console.run` 的载荷里没有 `stdout` / `stderr`，数据必须 `Poll` 取 | [../link/FEATURES.md](../link/FEATURES.md) §5.6 |
| `Poll` 的形状 | **每次返回完整累积缓冲，不是增量** | [../link/FEATURES.md](../link/FEATURES.md) §5.4、§7 第 9 条 |

界面字段 ← `Poll` 字段的对应关系：

| 界面显示 | 来源字段 | 出处 |
| --- | --- | --- |
| `输出` | `stdout` | `ConsoleView.vue:295` |
| `错误` | `stderr`（非空才显示整块） | `ConsoleView.vue:296,442` |
| `N ms` | `elapsedMs` | `ConsoleView.vue:297,430` |
| `输出已截断` | `truncated`（每流上限 256 KiB，见 FEATURES §5.4） | `ConsoleView.vue:298,433` |
| 状态文案 | `stage` / `running` / `exitCode` / `timedOut` | `ConsoleView.vue:299-313` |
| `编译 N ms` | `compileMs`（C++ 专有，单独显示，免得总耗时被误读成"程序慢"） | `ConsoleView.vue:300-301,432` |
| 退出码徽标 | `exitCode`（`done` 之前是 `null` → 显示"未运行"） | `ConsoleView.vue:302-306,427-429` |

`终止 ■` → `con.Stop(runId)`。语义是**真杀进程树**（`taskkill /PID <pid> /T /F`），与搜索/账号那种"停止等待"不是一回事（`console/bridge.js:125-133`；[../link/FEATURES.md](../link/FEATURES.md) §5.4、§6.3）。

失败分类（写文档与排障时不要混）：

| 现象 | 归类 | 依据 |
| --- | --- | --- |
| 退出码 `-1` | 组件未安装 | FEATURES §5.4 |
| 退出码 `-2` | 宿主侧错误（stderr 前缀 `[宿主错误] `） | FEATURES §5.4 |
| 退出码 `-3` | 缺 exe | FEATURES §5.4 |
| `组件包已在本地` 却装不上 | 环境没准备好（`.sha256` 旁文件与缓存包不一致，见 `tests/cdp-console.mjs:470-512` 的说明） | FEATURES §5.1、§7 |
| 语言下拉里没有 C++ | 不是缺陷：`cpp` 组件未安装或 `ready` 为假 | `ConsoleView.vue:58-62` |

每次「运行」都是**新进程**：变量不跨次保留（`ConsoleView.vue:414-417`）。这一点必须写在界面上——原版 PyQt 是同进程持久命名空间，用户会以为"上次算出的 `a` 这次还能用"。

### 1.5 工作区里存什么

控制台只声明 `{kind:"console", lang, code, stdin}`，**不存运行结果**（`ConsoleView.vue:375-379`）。进页面时优先从工作区还原，没有才回退到示例（`ConsoleView.vue:341-350`）。

---

## 2. 函数工具箱（`/tools/toolbox`）

把引擎**全部 424 个 action** 列出来并可直接调用（`ToolboxView.vue:3`）。它的存在理由是一个倒挂：界面模式表只覆盖一部分 action，其余"引擎算得出来、界面点不出来"。

### 2.1 数据源与三个该记住的数字

唯一数据源是 `src/lib/ai/engine-signatures.json`（`ToolboxView.vue:22`）。它由引擎源码重建并可对账（`tools/engine-signatures.mjs:3-24`）。

| 数字 | 值 | 复跑命令 / 出处 |
| --- | --- | --- |
| 签名表条目（= 本页列出的函数数 = `CATALOG.length`） | **424** | `node tools/engine-signatures.mjs --check` → 打印 `源码 register_function 424 条 / 表 424 条`（实测 2026-10-07，exit 0） |
| 界面模式表覆盖到的不同 `fn` | **371** | 见下方一行命令（`ENGINE_MAP` 导出 415 个**模式名**，去重后 371 个 `fn`） |
| 不在模式表里的函数（= 页面上的 `outsideCount`） | **53** = 424 − 371 | 同上；页面显示在 `ToolboxView.vue:104,198,211` |

```powershell
# 在 MF_UI/MFMath.UI.Vue 下执行（实测输出：signatures 424 modeTableFns 371 outside 53）
node --input-type=module -e "const m=await import('./src/lib/engine/engineMap.js');const fs=await import('node:fs');const s=JSON.parse(fs.readFileSync('src/lib/ai/engine-signatures.json','utf8'));const f=new Set(Object.values(m.ENGINE_MAP).map(x=>x.fn));const k=Object.keys(s);console.log('signatures',k.length,'modeTableFns',f.size,'outside',k.filter(x=>!f.has(x)).length)"
```

> ⚠ 源码注释里写的"剩下 **38** 个"是旧数字（371 + 38 = 409 ≠ 424）。见 §7。

页面按 `file` 字段的顶层目录反推模块名、去重后分成 **18** 组（`ToolboxView.vue:39-44,78`）：`algebra` `algebraic_topology` `calculus` `complex_analysis` `expr` `extras` `fractal` `functional_analysis` `harmonic_analysis` `introspect` `linear_algebra` `measure_theory` `number_theory` `numerical` `plot` `probability` `real_analysis` `symbolic`。

| 参数形态统计 | 值 | 说明 |
| --- | --- | --- |
| 无参数的 action | 9 | 页面显示"该函数没有参数，直接调用即可"（`ToolboxView.vue:234`） |
| `optional` 为空的 action | 237（含上面 9 个） | 即 228 个"参数全部必填" + 9 个无参数 |
| 出现过的参数类型名 | 15 种 | `array` `bool` `bound` `equation` `get_keyword_opt` `get_sig` `int` `int[]` `matrix` `number` `number[]` `parse_omega` `string` `string\|number` |

### 2.2 表单是"按签名表生成的"，不是手写的

| 步骤 | 规则 | 出处 |
| --- | --- | --- |
| 取参数 | `Object.keys(s.params)` → `{key, type, required}`，`required = !optional.has(key)` | `ToolboxView.vue:52-56` |
| 标必填/可选 | 每个字段旁 `必填` / `可选` + 类型名 | `ToolboxView.vue:236-241` |
| 输入框类型 | 数值族用 `type="number"`，其余 `text` | `ToolboxView.vue:242-244` |
| 占位提示 | 数值→`数字`；`matrix`→`[[1,2],[3,4]]（JSON 数组）`；其它结构型→`JSON，如 [1,2,3]`；其余→`字符串（如 x^2+1）` | `ToolboxView.vue:71-76` |
| 组装参数 | **空白的参数一律不发**（让引擎用自己的默认值） | `ToolboxView.vue:131` |
| 数值转换 | `NUMERIC` 集合（`number/int/integer/float/double/real`）→ `Number(raw)`；传字符串会被引擎的类型检查拒掉 | `ToolboxView.vue:66,132-133` |
| 结构转换 | `STRUCT` 正则（`matrix/array/object/list/vector/tuple/sets/data/pmf_data`）→ `JSON.parse(raw)`；解析失败**原样交出去**，让引擎报准确原因 | `ToolboxView.vue:68,134-137` |

`matrix_multiply` 是这条规则的实例：传 `"[[1,2]]"`（字符串）会被引擎判成"缺少矩阵参数"，必须传真值 `[[1,2]]`（`ToolboxView.vue:135-136`）。

过滤框同时按**函数名 / 模块名 / 参数名**三者之一命中（`ToolboxView.vue:92-101`）；`只看不在模式表里的` 勾选把列表缩到 53 条（`ToolboxView.vue:210-212`）。

### 2.3 调用与"强制后台"勾选

本页能调**任意** action，所以默认就按 `asyncPolicy` 自动分流（`ToolboxView.vue:115-124`）：

| 分流规则 | 内容 | 出处 |
| --- | --- | --- |
| 没有上界的重活 | 固定 **28** 个动作一律走后台（积分、级数、符号求解/化简、`factor_integer`、`matrix_inverse` …） | `asyncPolicy.js:39-49` |
| 规模可判的四族 | `mandelbrot` / `complex_grid` / `expr_eval_grid` / `matrix_multiply`，按参数算出工作量，超过阈值才异步 | `asyncPolicy.js:19-32` |
| 逃生口 | 勾「强制后台」→ `shouldRunAsync(..., {force:true})` 无条件返回 `true` | `asyncPolicy.js:69-70`；`ToolboxView.vue:254-257` |

后台通道是 `engineCallAsync`（`bridge.js:160-167`）：派发 `DispatchJob` → 每 **120 ms** `PollJob`（`bridge.js:182,204-224`）。宿主**没有** `DispatchJob` 方法时（旧桥）自动退回同步调用，所以这条路径是安全的（`bridge.js:164-167,178`）。取消的语义是"已取消等待（引擎会把这一步算完后丢弃结果）"，**不能**写成"已停止"（`bridge.js:192-198`）。

进度文案由 `describeWork` 生成（`asyncPolicy.js:80-86`），显示在 `data-toolbox="progress"` 那个元素里（`ToolboxView.vue:144,258`）。

### 2.4 其它界面行为

| 行为 | 事实 | 出处 |
| --- | --- | --- |
| 结果显示 | 引擎信封 `{isError, value}` **原样** `JSON.stringify(value, null, 2)`；页面不解读（错误头写"这是引擎自己的判定，本页不做解读"） | `ToolboxView.vue:161-163,262-269` |
| 无宿主 | 只列出函数、不能调用；按钮 `:disabled="!hosted"`，并在头部给一行橙色说明 | `ToolboxView.vue:28,203,249` |
| 桥断开 | 调用返回 `null` → 显示"没有连上本地引擎（本页只在 MFMath.exe 里可用）" | `ToolboxView.vue:161-162` |
| 排障钩子 | `window.__mfToolbox`：`size()` / `missing()` / `modules()` / `pick(fn)` / `call(fn,args)` / `setForceAsync(v)` | `ToolboxView.vue:174-188` |

⚠ `__mfToolbox.call` 是 **async**（其内部按 `shouldRunAsync` 决定是否走后台通道），CDP 侧取值要用 `awaitPromise: true`（`ToolboxView.vue:171-173`）。

---

## 3. 历史（顶栏对话框）

`lib/history/store.js` 是**唯一记录入口**，历史面板与页面里的"最近"都读它（`history/store.js:2-4,23`）。

### 3.1 记什么、不记什么

| 字段 | 类型 / 限制 | 出处 |
| --- | --- | --- |
| `id` | `"h" + 时间戳36进制 + 随机5位` | `store.js:30-32` |
| `ts` | 毫秒时间戳 | `store.js:85` |
| `route` | 触发它的页面路由 | `store.js:86` |
| `mode` | 界面模式名（如 `解方程/组`、`基础运算`） | `store.js:87` |
| `expr` | 表达式 | `store.js:88` |
| `summary` | 结果摘要，**截断到 300 字符** | `store.js:89` |
| `ok` | `e.ok !== false`（默认 true） | `store.js:90` |

| 记 | 不记 |
| --- | --- |
| **成功与失败都记**；失败的 `ok:false`，面板里整行标红（`HistoryDialog.vue:86,91`） | **绘图页的操作不入历史**（见 §3.4） |
| 基础运算页（`BasicCalcView.vue:141,154,164`，三次调用分别覆盖解析失败 / 引擎报错 / 成功） | **运行输出本身不存**（控制台的 `stdout` 从不进历史） |
| 学科计算页（`CalcView.vue:386-392`，成功与失败都记） | 计算页的撤销栈**不共用**这份历史（`MIGRATION-GAPS.md:238` 说明撤销栈只记表达式与模式） |
| 去重：同一 `route` + `mode` + `expr` → 只更新时间并**置顶**，`ts` 保留首次时间 | 超上限（**200 条**）的从尾部丢（`store.js:21,102`） |

`record()` 的门槛：`expr` 与 `mode` **都**为空时返回 `null`，不记（`store.js:79-81`）。

### 3.2 存哪、怎么保证写不坏

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 落盘 | 走宿主 `sys` 键值存储 → `%LOCALAPPDATA%\MFMath\settings\history.json` | `store.js:7-8,68` |
| 合并写入 | 250 ms 内多次记录只落一次盘 | `store.js:63-71` |
| 写入保障 | 宿主侧：先校验 JSON → 备份旧文件 → 原子替换（不重犯 v1"写一半崩掉下次必 JSONDecodeError"的错） | `store.js:11-13`；[../link/FEATURES.md](../link/FEATURES.md) §4.1 |
| 无宿主 | `lib/settings/bridge.js` 自动降级到 `localStorage`，功能照样点得通，只是不落文件 | `store.js:8-9` |
| 读坏数据 | 只接受结构完整的条目（`expr` 是字符串且 `ts` 是数字），坏的过滤掉；文件损坏时**保留原文件**并报出来 | `store.js:35-37,44-50` |
| 内容解析失败 | 写进 `errorText`，面板显示成一行红色说明 | `store.js:56-58`；`HistoryDialog.vue:78` |

### 3.3 面板行为

| 交互 | 行为 | 出处 |
| --- | --- | --- |
| 搜索 | 空格分词、**全部命中**才算；匹配范围是 `expr + summary + mode` | `store.js:133-141` |
| 计数 | 头部"共 N 条（最多保留 200 条）"；工具条"N / N" | `HistoryDialog.vue:62,75` |
| 点一条回填 | `setPending({expr, mode, operation:mode, label:expr})` → `router.push(e.route || "/calc/algebra")` → 关闭面板 | `HistoryDialog.vue:36-41` |
| 逐条删除 | `removeEntry(id)` | `HistoryDialog.vue:93`；`store.js:107-111` |
| 清空全部 | **二次确认**（按钮先变成"确定清空 / 取消"） | `HistoryDialog.vue:102-109` |
| `Esc` | 关闭面板 | `HistoryDialog.vue:48-52` |
| 基础运算页单独清 | `clearRoute("/calc/basic")`，只清那一页的部分 | `store.js:120-124`；面板里的 `basicCount` 在 `HistoryDialog.vue:55,100` |
| 另一处入口 | 设置 → 存储与数据 里显示当前条数并可清空 | `components/settings/StorageGroup.vue:211-224` |

回填走 `pendingInput` 这条**已验证通路**（示例库同一条），不直接抓控件 `setText`——v1 那种做法在模式匹配不上时会静默丢失语义（`HistoryDialog.vue:12-13`；`lib/workspace/pendingInput.js:1-9`）。

### 3.4 为什么绘图页操作不进来

这是**已登记的推迟项**，不是漏做：

- [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §2 第 6 条：「绘图页操作入历史」——理由"与'历史'的语义边界未定"，回来的条件是"定义清楚'哪些绘图操作算一步'"，出处指向 [../MIGRATION-GAPS.md](../MIGRATION-GAPS.md) §2.5；
- `MIGRATION-GAPS.md:148` 原文："绘图页的操作没记入历史（v1 也只记计算）"。

代码层面的核对：全仓库 `history/store.js` 的调用点只有两处 —— `CalcView.vue:27,386` 与 `BasicCalcView.vue:19,141,154,164`；React 绘图组（`MF_UI/MFMath.UI.React/src`）里**零引用**。

---

## 4. 搜索页（`/tools/search`）

它是**页面而不是弹窗**：搜索结果要来回看、要复制、要送进计算页，而且教程示例「联网搜索」需要一条能落地的路由（`SearchView.vue:4-8`）。

### 4.1 入口与不可用时的表现

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 顶栏「搜索」 | `router.push("/tools/search")`（不再有浮层状态） | `App.vue:244-247` |
| 深链 | `/tools/search?q=…` 挂载时自动开搜；页面已挂载时 `watch(route.query.q)` 也生效 | `SearchView.vue:32-44` |
| 侧栏入口 | 「工具」组第 1 项 | `nav.js:64` |
| 无宿主 | 显示一块说明而不是假搜索框："浏览器预览里没有宿主桥…"（并说明为什么不做前端直连 fetch：CORS + App ID 不该进渲染进程） | `SearchView.vue:120-126` |

### 4.2 只取前 N 条、**不翻页**

| 问题 | 答案 | 出处 |
| --- | --- | --- |
| N 从哪来 | 宿主配置，默认 **8**，钳在 **1–20**（给 0 视为没配 → 8） | `search.rs:120-122,188-193` |
| 前端能改 N 吗 | 搜索页只传 `{query, engine, noCache}`，**不传条数** | `search/bridge.js:170`；`search.rs:1734-1740` |
| 在哪改 | 设置 → 搜索 →「结果条数」，输入框 `min=1 max=20` | `components/settings/SearchGroup.vue:152-165` |
| 页面上显示什么 | `共 N 条 · M ms`（N 就是**实际返回**的条数） | `SearchView.vue:164` |
| 翻页 | **没有**。UI 无翻页控件，宿主侧也没有 `page` / `offset` 参数 | `SearchView.vue:172-190`；[../link/FEATURES.md](../link/FEATURES.md) §1.5 第 1 条 |
| 为什么不做 | 记为边界，不是待办：推翻门槛是"有用户证据表明缺它就不能用" | [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) §1 第 6 条 |

### 4.3 不抓正文（有意不做）

结果项只渲染引擎给的 `snippet`（`SearchView.vue:179`），**绝不二次请求结果页**（[../link/FEATURES.md](../link/FEATURES.md) §1.5 第 2 条）。摘要块 `searchState.abstract` 也来自宿主解析的 Instant Answer，不是我们抓的正文（`SearchView.vue:167-170`）。

### 4.4 结果怎么用（三条纪律在这页的落地）

| 纪律 | 落地方式 | 出处 |
| --- | --- | --- |
| 结果只以文本渲染 | 标题/摘要/网址都是插值；打开链接走宿主 `OpenUrl`，那条闸门**只放行 http/https** | `SearchView.vue:10-11,91`；[../link/FEATURES.md](../link/FEATURES.md) §1.4 |
| 面板明说查询发往哪个站点 | 头部一行"查询会发往：`<endpoint>`"，另有缓存 TTL | `SearchView.vue:114-117` |
| 表达式只是**建议**，且由引擎算 | 「算这个」按钮只在 `extractExpr()` 提出候选时才出现；点了走 `setPending` → `/calc/basic`，由引擎计算 | `SearchView.vue:101-107,184-187`；`search/bridge.js:234-249` |

`extractExpr` 是**启发式**（正则挑片段 + 打分），所以纪律是"只建议、不自动算、送原文"（`search/bridge.js:236-240`）。用例也守着这条：结果里出现可算表达式才会出现按钮，且点了之后跳转加回填（`tests/cdp-search.mjs:251-282`）。

### 4.5 引擎选择、缓存与失败分类（界面部分）

- 三个引擎：`duckduckgo`（默认）/ `wolfram`（需 App ID）/ `custom`（SearXNG 端点）（`search/bridge.js:126-130`）。换引擎会**写回宿主配置**（`searchConfigure({engine})`），写不进去会显示出来而不是静默（`SearchView.vue:64-73`）。缺 App ID / 缺自定义端点时给的是**指向设置页的链接**，不是笼统失败（`SearchView.vue:142-147`）。
- 缓存：命中时显示"来自缓存 · <时间>"；`忽略缓存` 按钮走 `noCache:true`（`SearchView.vue:138-139,158-159`）。缓存键含引擎、TTL 与上限见 [../link/FEATURES.md](../link/FEATURES.md) §1.3。
- 失败分类六类 `config` / `network` / `http` / `parse` / `timeout` / `aborted`，页面把每一类翻译成"下一步做什么"（`SearchView.vue:77-89`；[../link/FEATURES.md](../link/FEATURES.md) §1.2）。
- 「停止」→ `Cancel(id)`：**只置标记，已在飞的请求不会被强杀**（`search/bridge.js:180-185`；FEATURES §1.6）。

---

## 5. 怎么复跑（可复跑命令）

前置：Vue 已 `npm run build` 并同步到宿主 `wwwroot/`，宿主带 `--remote-debugging-port=9222` 启动（见 [../../MFMath.Host.Rust/docs/ACCEPTANCE.md](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)；`tests/run-all.ps1:121` 用环境变量设置这个端口）。

| 目的 | 命令 | 备注 |
| --- | --- | --- |
| 签名表对账（424 的来源） | `cd MF_UI/MFMath.UI.Vue` → `node tools/engine-signatures.mjs --check` | 实测打印 `源码 register_function 424 条 / 表 424 条`，exit 0 |
| 371 / 53 的来源 | 见 §2.1 那一行 `node --input-type=module -e …` | 实测 `signatures 424 modeTableFns 371 outside 53` |
| 前端四道闸门 | `npm run check`（= `check:types` + `check:signatures` + `check:args` + `check:ui`） | `package.json:13-18` |
| 控制台 | `node tests/cdp-console.mjs` | 需宿主带 CDP；用法见 `tests/cdp-console.mjs:8` |
| 历史 + 顶栏搜索入口 | `node tests/cdp-history-search.mjs` | 断言"真落盘"用 `sys.StoreList()`（`tests/cdp-history-search.mjs:195-201`） |
| 搜索 | `node tests/cdp-search.mjs` | ⚠ 宿主**必须**带 `MF_SEARCH_ENDPOINTS` 指向 `tests/fake-search-server.mjs`（默认端口 **8792**，可用 `FAKE_SEARCH_PORT` 改），否则用例自己拒绝跑（`tests/cdp-search.mjs:107-115`；`run-all.ps1:122-126`） |
| 成套 | `tests/run-all.ps1 -NoLaunch` | 登记位置：`cdp-console`（`run-all.ps1:55`）、`cdp-history-search`（`:69`）、`cdp-console-sci`（`:72`）、`cdp-search`（`:97`） |

**已实测的通过数（2026-10-07，绘图组迁到 React 之后的一次，来源 [../../MF_UI/BUGS.md](../../MF_UI/BUGS.md):81-84）**：

| 套件 | 结果 |
| --- | --- |
| `cdp-console` / `cdp-push` | **66 / 0** / **20 / 0** |
| `cdp-search` | **55 / 0** |
| `cdp-history-search` | **21 / 0** |
| `cdp-settings` | **43 / 0** |
| ~~`cdp-ai` / `cdp-account` / `cdp-update` 的旧失败数~~ | 已作废，二次实测 160/0、52/0、37/0 |

> 这些数字是**状态类**信息，过期很快 —— 引用时请连同时间戳一起引，别把它写成本文档的结论。

---

## 6. 未证实（不要当成"没有"，也不要当成"有"）

| 事项 | 现状 | 怎么才能验证 |
| --- | --- | --- |
| **函数工具箱没有任何自动化覆盖** | 全仓库 grep `data-toolbox` 与 `__mfToolbox`：只出现在 `ToolboxView.vue` 自己（`:207-262`、`:174-188`），**没有** `tests/*.mjs` 引用；`BUGS.md:588` 也只是提到钩子的签名变化 | 在带 CDP 的宿主里进 `/tools/toolbox`，断言 `window.__mfToolbox.size() === 424`、`missing().length === 53`、`await window.__mfToolbox.call("expr_eval",{expr:"x^2",x:3})` 的 `value === 9`（`call` 是 async，要 `awaitPromise:true`） |
| **"点安装 → 联网下载组件包 → 装好"这条路径** | 站点上两个 zip **尚未上传**，清单标 `available:false`（[../OPEN-ITEMS.md](../OPEN-ITEMS.md):119）。本机若把包放进 `%LOCALAPPDATA%\MFMath\components\cache\`，界面会显示"组件包已在本地"走本地安装（`ConsoleView.vue:81-83`） | 上传后跑 `node tests/cdp-console.mjs`，看它 `:370-385`（Python）与 `:653-680`（MinGW）两段安装分支；`cdp-console.mjs:516-627` 已备好断点续传的判据 |
| **`cdp-console-sci`（sympy / numpy / scipy）当前的通 / 失败数** | 该套件在组件未安装时 SKIP 且不算失败（`run-all.ps1:70-72`；`BUGS.md:734` 记了这个先例），而 `BUGS.md` §0.2 的实跑表里没有它 | 装好 Python 组件后单独跑 `node tests/cdp-console-sci.mjs` 并记录 `RESULT` 行 |
| **"C++ 在下拉里可见但一跑就报组件不完整"的真实发生率** | 判据不一致是**代码事实**（`console.rs:279` 查两件 vs 运行时要求三件，FEATURES §5.5 已登记），但我没有在本机复现过 | 删掉 `<组件目录>\include\mfmath_autorun.hpp`，进控制台看语言下拉是否仍有 `cpp`、点了运行是否报"组件不完整" |
| **历史在浏览器预览下的 localStorage 降级路径** | 代码存在（`store.js:8-9`），但端到端用例只跑宿主路径（`cdp-history-search.mjs` 全程 driver 宿主窗口） | 无宿主打开页面，算一次 → 看历史面板是否有记录、刷新后是否还在 |

---

## 7. 已知的文档债

写这份文档时逐条对照过源码，下面这些是**注释/旧文档与代码不符**的地方：

| # | 位置 | 文本说 | 代码做 | 证据 |
| --- | --- | --- | --- | --- |
| 1 | `ToolboxView.vue:7`、`nav.js:67-68`、`router/index.js:53` | 界面模式表覆盖 371 个，"**剩下 38 个**"没有任何入口 | 实际是 **53** 个（424 − 371）。`371 + 38 = 409`，与 424 自相矛盾 | §2.1 的复跑命令输出 `outside 53`；页面运行时算出的 `outsideCount` 也显示 53（`ToolboxView.vue:104`） |
| 2 | `App.vue:450` | 注释写"顶栏「历史」/「**搜索**」**弹窗** + AI 抽屉" | 搜索自改为真实页面后已无弹窗：`openSearch()` 是 `router.push("/tools/search")` | `App.vue:244-247`；模板里只剩 `<HistoryDialog>` 与 `<AiPanel>`（`App.vue:451-452`）；`cdp-history-search.mjs:214` 断言"占位浮层已经不存在了" |
| 3 | `lib/console/bridge.js:4` | "宿主对象：`…hostObjects.sync.con`（见 **`MFMath.Host/ConsoleBridge.cs`**）" | 现役宿主是 Rust，`con` 由 `CON_SPEC` 注册 | `MFMath.Host.Rust/src/main.rs:215`；`handlers.rs:96`。旧文件确实存在（`MFMath.Host/ConsoleBridge.cs`），但它属已废弃宿主，见 [../../AGENTS.md](../../AGENTS.md) §2 的 R7 表述 |
| 4 | `lib/push.js:4` | 同上，指向 **`MFMath.Host/PushHub.cs`** | 现役实现是 `MFMath.Host.Rust/src/push.rs`，`push` 桥由 `PUSH_SPEC` 注册 | `main.rs:117,211`；`push.rs:1` 与 `handlers.rs:208` 自己写着"对照 C# `PushHub.cs`"—— 属**有意的交叉引用**，但读者容易误以为是现役文件 |
| 5 | `lib/console/bridge.js:135-136` | `consoleStopAll` 的注释写"退出前清场（**兜底**；正常由宿主关窗时自己清）" | 该函数在 `src/` 下**零调用点**，这条"兜底"实际不存在 | grep `consoleStopAll`：只有 `bridge.js:136` 的定义 |
| 6 | `docs/MIGRATION-GAPS.md:147` | `tests/cdp-history-search.mjs` **20 / 0** | 二次实测 **21 / 0**（较新） | 对照 `MF_UI/BUGS.md:84` |
| 7 | `docs/MIGRATION-GAPS.md:337` | "`cdp-history-search.mjs` # **20 项**（历史 + **搜索占位**）" | 条数过期（同 #6）；且搜索已是真实页面，"占位"不成立 | `cdp-history-search.mjs:204-208` 断言跳转 `/tools/search` 且搜索框可用 |
| 8 | `docs/MIGRATION-GAPS.md:142` | 历史落盘写的是 `SettingsBridge.StoreWrite`（C# 名） | 现役是 Rust `sys` 桥的 `StoreWrite` | [../link/FEATURES.md](../link/FEATURES.md) §4.1；属 R7 债 |
| 9 | `tests/run-all.ps1:26-31,163` | 默认 `$hostExe` 指向 **已废弃**的 `MFMath.Host\bin\Release\net10.0-windows\MFMath.exe`，报错提示是 `dotnet build -c Release` | 实际跑法是用 Rust 宿主 + `-NoLaunch` 附着，或 `MF_HOST_EXE` 指定 | `BUGS.md:63-66`（"本机只能跑起 Rust 宿主…跑法：启动 Rust 宿主 → `run-all.ps1 -NoLaunch`"）；`run-all.ps1:24,138-148` 支持这两种绕过 |

**附带两条代码层的观察**（不是文档债，但会被误读成"有兜底"）：

1. `ConsoleView.vue:17` 从 `console/bridge.js` import 了 `setDownloadBase`，但**本文件从未调用**它 —— 换组件下载源（内网镜像）的入口只在设置页（`components/settings/ComponentsGroup.vue:120`）。
2. `uninstallComponent` 与 `consoleStopAll` 由 `console/bridge.js:82,136` 导出，`src/` 下除设置页的卸载调用外没有其它使用点；阅读时不要以为控制台页有"卸载组件"或"退出清场"的按钮。

---

## 8. 编辑本文件时

- 四个入口的**形态**（3 路由 + 1 对话框）变了要同步 §0；
- §2.1 的三个数字（424 / 371 / 53）**必须重跑命令**再改，不要手抄 —— 手抄一遍就是下一个 `BUGS.md` §0.2；
- §5 的实跑数字属于状态类信息，更新时**带上时间戳与新来源**；
- 标了"有意不做"的条目（搜索不翻页/不抓正文、绘图页操作不入历史）不要从这里删 —— 它们是 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md) 的引用，改要先去改那边。
