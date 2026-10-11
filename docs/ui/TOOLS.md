# 工具区

> 本文回答工具区四个入口各做什么：控制台、函数工具箱、历史记录、搜索页面，以及它们各自有意不做的部分。
>
> 与同层文档的分工：[README.md](README.md) 讲两个工程与各自用例的对应关系；[ARCHITECTURE.md](ARCHITECTURE.md) 讲分层、路由与导航；[ENGINE-BINDING.md](ENGINE-BINDING.md) 讲 `ENGINE_MAP`、`calcArgs`、`asyncPolicy` 与可达性守门；宿主侧实现细节见 [../link/FEATURES.md](../link/FEATURES.md)；哪些「没有」是有意不做见 [../DESIGN-BOUNDARIES.md](../DESIGN-BOUNDARIES.md)。

## 1. 形态

「工具区四个页面」对搜索、控制台、函数工具箱成立，对历史不成立——历史是顶栏按钮打开的模态对话框，不在侧栏导航、没有自己的路由。

| 名称 | 形态 | 入口 | 载体文件 |
| --- | --- | --- | --- |
| 搜索 | 路由页面 | 侧栏「工具 → 搜索」`/tools/search`；顶栏「搜索」 | `src/views/tools/SearchView.vue` |
| 控制台 | 路由页面 | 侧栏「工具 → 控制台」`/tools/console` | `src/views/tools/ConsoleView.vue` |
| 函数工具箱 | 路由页面 | 侧栏「工具 → 函数工具箱」`/tools/toolbox` | `src/views/tools/ToolboxView.vue` |
| 历史 | 模态对话框 | 顶栏「历史」→ `showHistory` | `src/components/history/HistoryDialog.vue` |

三页都只在有宿主时才有完整能力；浏览器预览下各自给出明确说明。

## 2. 控制台（`/tools/console`）

给用户写小程序试算。计算全部由 C++ 引擎完成，Python 侧只有 `mfmath` 封装、C++ 侧只有导入库，界面自己不算任何数学。

### 2.1 界面布局

| 区域 | 控件 |
| --- | --- |
| 左·工具条 | 语言下拉、示例下拉、运行/终止、清空输出、重置 |
| 左·编辑区 | CodeMirror 6 编辑框，`Ctrl+Enter` 运行 |
| 左·提示 | 每次运行都是新进程 |
| 左·标准输入 | 单行输入框 |
| 右·状态栏 | 退出码徽标、总耗时、C++ 编译耗时、输出已截断、状态文案 |
| 右·输出 | 输出 / 错误两个 `<pre>` |
| 右·组件 | Python / C++ 两行状态 + 安装、进度条、取消 |

示例按语言分开：Python 3 个、C++ 3 个，切语言回到该语言第 0 个示例。重置清输出并退回示例；清空输出只清输出。

### 2.2 编辑器

CodeMirror 6 内核与语言包按需加载，语法包按语言分开（`@codemirror/lang-python` / `@codemirror/lang-cpp`），切语言串行化。语法高亮颜色取项目 CSS 变量，主题切换即时生效。补全候选来自引擎 `list_functions`，`boost: 99` 让引擎函数名压过 Python 内置名。内核或语言包 import 失败退回 `<textarea>`。

函数表只在进页面时取一次 `engineCall("list_functions", {})`；取不回来不影响编辑器可用。

### 2.3 语言与可选组件

| 项 | 行为 |
| --- | --- |
| 默认语言 | Python；C++ 只在 `comps.cpp.ready` 为真时出现 |
| 组件状态行 | 区分已在本地、有 `.part` 断点、需联网下载三种 |
| 安装 | `installComponent` 拿 `jobId`，每 400 ms 轮询，连续 150 次后停止 |
| 取消 | `cancelInstall(jobId)`，已下载部分保留 |

`cpp.ready` 只检查 `lib\libmf_mathematics.a` 与 `include\mfmath.hpp` 两件，实际运行还要求 `include\mfmath_autorun.hpp`。

### 2.4 运行与输出

```
运行 → consoleStart(lang, code, stdin) → runId
     → setInterval(tick)   ← 有 push 500ms / 无 push 200ms
tick → consolePoll(runId) → 改写输出与状态
```

| 项 | 事实 |
| --- | --- |
| 开始 | `con.Start` 返回裸 id 字符串 |
| 轮询间隔 | 有 push 桥 500 ms，无 push 桥 200 ms |
| 推送 | 只改状态文案并立即 `tick()` 一次，不带输出 |
| `Poll` | 每次返回完整累积缓冲，非增量 |

| 界面显示 | 来源字段 |
| --- | --- |
| 输出 | `stdout` |
| 错误 | `stderr` |
| N ms | `elapsedMs` |
| 输出已截断 | `truncated` |
| 状态文案 | `stage` / `running` / `exitCode` / `timedOut` |
| 编译 N ms | `compileMs` |
| 退出码徽标 | `exitCode` |

终止是真杀进程树（`taskkill /PID <pid> /T /F`），与搜索/账号的「停止等待」不同。

失败分类：退出码 `-1` 组件未安装、`-2` 宿主侧错误、`-3` 缺 exe。语言下拉没有 C++ 不是缺陷，是组件未安装或 `ready` 为假。

### 2.5 工作区

控制台只声明 `{kind:"console", lang, code, stdin}`，不存运行结果。进页面优先从工作区还原，没有才回退示例。

## 3. 函数工具箱（`/tools/toolbox`）

把引擎全部 424 个 action 列出来并可直接调用。

### 3.1 数据源与数字

唯一数据源是 `src/lib/ai/engine-signatures.json`，由引擎源码重建。

| 数字 | 值 |
| --- | --- |
| 签名表条目 | 424 |
| 界面模式表覆盖的 `fn` | 371 |
| 不在模式表里的函数（`outsideCount`） | 53 |

验证命令：

```powershell
cd MF_UI\MFMath.UI.Vue; node --input-type=module -e "const m=await import('./src/lib/engine/engineMap.js');const fs=await import('node:fs');const s=JSON.parse(fs.readFileSync('src/lib/ai/engine-signatures.json','utf8'));const f=new Set(Object.values(m.ENGINE_MAP).map(x=>x.fn));const k=Object.keys(s);console.log('signatures',k.length,'modeTableFns',f.size,'outside',k.filter(x=>!f.has(x)).length)"
```

页面按 `file` 字段顶层目录反推模块名，去重后分 18 组。

### 3.2 表单生成

表单按签名表生成，不手写：

| 步骤 | 规则 |
| --- | --- |
| 取参数 | `Object.keys(s.params)`，`required = !optional.has(key)` |
| 标必填/可选 | 字段旁标必填/可选 + 类型名 |
| 输入框类型 | 数值族用 `type="number"`，其余 `text` |
| 组装参数 | 空白的参数一律不发 |
| 数值转换 | `NUMERIC` 集合 `Number(raw)` |
| 结构转换 | `STRUCT` 正则 `JSON.parse(raw)`，失败原样交引擎 |

过滤框同时按函数名 / 模块名 / 参数名命中；「只看不在模式表里的」勾选把列表缩到 53 条。

### 3.3 调用与强制后台

| 分流规则 | 内容 |
| --- | --- |
| 无上界的重活 | 固定 28 个动作走后台 |
| 规模可判的四族 | `mandelbrot` / `complex_grid` / `expr_eval_grid` / `matrix_multiply` 按参数算工作量 |
| 逃生口 | 「强制后台」勾选无条件异步 |

后台通道 `engineCallAsync` 派发 `DispatchJob` 后每 120 ms `PollJob`。宿主无 `DispatchJob` 方法时自动退回同步。取消语义是「已取消等待」，不是「已停止」。

## 4. 历史（顶栏对话框）

`lib/history/store.js` 是唯一记录入口，历史面板与页面里的「最近」都读它。

### 4.1 记录字段与取舍

| 字段 | 说明 |
| --- | --- |
| `id` | 时间戳 36 进制 + 随机 5 位 |
| `ts` | 毫秒时间戳 |
| `route` | 触发页面的路由 |
| `mode` | 界面模式名 |
| `expr` | 表达式 |
| `summary` | 结果摘要，截断到 300 字符 |
| `ok` | `e.ok !== false` |

成功与失败都记，失败的 `ok:false` 面板整行标红。绘图页操作不入历史，这是已登记的推迟项，不是漏做。去重规则：同一 `route + mode + expr` 只更新时间并置顶。上限 200 条，超出从尾部丢。`expr` 与 `mode` 都为空时不记。

### 4.2 存储

落盘走宿主 `sys` 键值存储到 `%LOCALAPPDATA%\MFMath\settings\history.json`。250 ms 内多次记录只落一次盘。宿主侧先校验 JSON、备份旧文件、原子替换。无宿主降级到 `localStorage`。读坏数据只接受结构完整条目，坏条目过滤，文件损坏保留原文件。

### 4.3 面板行为

| 交互 | 行为 |
| --- | --- |
| 搜索 | 空格分词，全部命中才算，范围是 `expr + summary + mode` |
| 点一条回填 | `setPending` → `router.push` → 关闭面板 |
| 逐条删除 | `removeEntry(id)` |
| 清空全部 | 二次确认 |
| 基础运算页单独清 | `clearRoute("/calc/basic")` |

回填走 `pendingInput` 通路，不直接抓控件。

## 5. 搜索页（`/tools/search`）

搜索是页面而不是弹窗，因为结果要来回看、要复制、要送进计算页。

### 5.1 入口与不可用时的表现

| 项 | 事实 |
| --- | --- |
| 顶栏「搜索」 | `router.push("/tools/search")` |
| 深链 | `/tools/search?q=…` 挂载时自动开搜 |
| 无宿主 | 显示说明块，不显示假搜索框 |

### 5.2 只取前 N 条、不翻页

| 问题 | 答案 |
| --- | --- |
| N 从哪来 | 宿主配置，默认 8，钳在 1–20 |
| 前端能改 N | 不能，搜索页只传 `{query, engine, noCache}` |
| 在哪改 | 设置 → 搜索 → 结果条数 |
| 翻页 | 没有，UI 无翻页控件，宿主侧无 `page` / `offset` |

不做翻页记为边界，而非未完成项。

### 5.3 不抓正文

结果项只渲染引擎给的 `snippet`，绝不二次请求结果页。摘要块来自宿主解析的 Instant Answer。

### 5.4 结果使用纪律

| 纪律 | 落地 |
| --- | --- |
| 结果只以文本渲染 | 打开链接走宿主 `OpenUrl`，只放行 http/https |
| 明说查询发往哪个站点 | 头部显示端点与缓存 TTL |
| 表达式只建议、由引擎算 | 「算这个」走 `setPending` → `/calc/basic` |

`extractExpr` 是启发式，纪律是只建议、不自动算、送原文。

### 5.5 引擎、缓存与失败分类

三个引擎：`duckduckgo`（默认）/ `wolfram`（需 App ID）/ `custom`（SearXNG 端点）。换引擎写回宿主配置。缓存命中显示「来自缓存 · 时间」。失败分类六类：`config` / `network` / `http` / `parse` / `timeout` / `aborted`。「停止」只置标记，已在飞的请求不被强杀。

## 6. 验证命令

```powershell
# 签名表对账
cd MF_UI\MFMath.UI.Vue; node tools/engine-signatures.mjs --check

# 前端四道闸门
npm run check
```

端到端用例：`cdp-console.mjs`、`cdp-history-search.mjs`、`cdp-search.mjs`、`cdp-console-sci.mjs` 均需宿主带 CDP，由 `tests/run-all.ps1` 统一登记。搜索用例要求宿主带 `MF_SEARCH_ENDPOINTS` 指向假端点，否则用例拒绝运行。
