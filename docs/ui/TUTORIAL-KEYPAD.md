# 教程系统与数学键盘

> 本文回答教程系统与数学键盘：教程的数据流、引导目标的约束、键位与分类，以及构建期校验。
>
> 与同层文档的分工：[README.md](README.md) 讲两个前端工程、构建链与测试资产总览；[AI.md](AI.md) 讲 AI 面板与步骤视图（教程 04/05 的目标落点）；[TOOLS.md](TOOLS.md) 讲搜索页与函数工具箱（教程 12 的目标落点）；[CHECKS.md](CHECKS.md) 讲四道构建闸门。

## 1. 规模与状态

| 项 | 值 |
| --- | --- |
| 教程篇数 | 18 |
| 步骤 / 示例 / FAQ | 66 / 52 / 42 |
| 引导引用的 target（去重） | 30 |
| `PENDING` 条目 | 0（空对象） |
| 数学键盘 | 6 分类 / 126 键（基准键数） |
| 键面可读性 | 排版 13 / 文字 109 / 清理后文字 4 / 裸 LaTeX 0 |

## 2. 数据流

| 环节 | 路径 | 角色 |
| --- | --- | --- |
| 输入 | `<v2.0>/../Multifunctional-Mathematics/MF_Tutorial/tutorials/*.yaml` | 唯一内容源，18 篇 |
| 转换器 | `MF_UI/MFMath.UI.Vue/tools/build-tutorials.mjs` | YAML 子集解析 + 严格自检 |
| 产物 | `MF_UI/MFMath.UI.Vue/src/tutorials/tutorials.json` | 前端 import 的数据源 |
| 留档 | `docs/tutorials-src/*.yaml`（18 个） | 供比对，不参与运行 |

`docs/tutorials-src/*.yaml` 是副产物，不是输入：脚本把上游原件拷进去留档。改该目录的 YAML 对软件无影响，下一次 `npm run tutorials` 会用上游原件覆盖它。

验证命令：

```powershell
cd MF_UI\MFMath.UI.Vue
$env:MF_TUTORIAL_ARCHIVE = "$env:TEMP\mf-arch"
node tools/build-tutorials.mjs
```

输出：`解析到 18 篇 / 66 步 / 52 示例 / 42 FAQ`。

转换期处理：字段改名（`action` 拆成 `actionType`/`actionValue` 与 `operation`）、按 `order` 升序、内容指纹 `version = sha1(JSON(steps, examples, faq))` 前 8 位、`V2_OVERRIDES` 覆盖 v2 文案、死字段 `prerequisites` 原样保留。指纹用于进度失效判定：`isCompleted()` 要求 `rec.version === t.version`，内容一变「已学」失效。

## 3. 18 篇教程

| order | id | 分类 | 难度 | 步 | 示例 | FAQ | 时长 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `quick-start` | 入门指南 | 入门 | 4 | 2 | 2 | 3 分钟 |
| 2 | `basic-calculation` | 计算模块 | 入门 | 6 | 5 | 3 | 5 分钟 |
| 3 | `plot-2d` | 绘图系统 | 入门 | 6 | 4 | 3 | 5 分钟 |
| 4 | `ai-assistant` | AI 功能 | 入门 | 5 | 2 | 3 | 4 分钟 |
| 5 | `ai-steps-accelerate` | AI 功能 | 进阶 | 5 | 2 | 2 | 4 分钟 |
| 6 | `linear-algebra` | 计算模块 | 进阶 | 3 | 4 | 2 | 5 分钟 |
| 7 | `probability-statistics` | 计算模块 | 进阶 | 3 | 3 | 2 | 5 分钟 |
| 8 | `numerical-analysis` | 计算模块 | 进阶 | 3 | 4 | 2 | 5 分钟 |
| 9 | `plot-3d-complex` | 绘图系统 | 进阶 | 4 | 4 | 2 | 5 分钟 |
| 10 | `vector-field-geometry` | 绘图系统 | 高级 | 3 | 4 | 2 | 6 分钟 |
| 11 | `math-keyboard` | 工具 | 入门 | 3 | 2 | 2 | 3 分钟 |
| 12 | `search-settings` | 设置 | 入门 | 6 | 2 | 2 | 4 分钟 |
| 13 | `themes-appearance` | 设置 | 入门 | 2 | 0 | 2 | 2 分钟 |
| 14 | `tips-and-tricks` | 入门指南 | 高级 | 1 | 2 | 4 | 5 分钟 |
| 15 | `complex-analysis` | 计算模块 | 进阶 | 3 | 3 | 2 | 8 分钟 |
| 16 | `functional-analysis` | 计算模块 | 高级 | 3 | 3 | 2 | 10 分钟 |
| 17 | `measure-theory` | 计算模块 | 高级 | 3 | 3 | 2 | 10 分钟 |
| 18 | `algebraic-topology` | 计算模块 | 高级 | 3 | 3 | 3 | 10 分钟 |

分类分布：`general 2 / calculation 8 / plot 3 / ai 2 / tools 1 / settings 2`；难度分布：`beginner 7 / intermediate 6 / advanced 5`。

## 4. 前端消费

| 组件 | 职责 |
| --- | --- |
| `TutorialCatalogView.vue` | 分类/难度筛选、进度、启动引导、断点续走、重置 |
| `HelpArticleView.vue` | 概述/操作步骤/示例表/FAQ、标记已学 |
| `ExampleLibrary.vue` | 把示例加载到工作区 |
| `WelcomeDialog.vue` | 首次启动 4 张卡 |
| `TourOverlay.vue` | 挖洞高亮、提示卡、上一步/暂停/跳过 |
| `tour.js` | 前进/后退/暂停/断点/结束判定 |
| `store.js` | `localStorage` 读写、内容指纹失效 |
| `targets.js` | `[data-tour]` 定位、`PENDING`、`TARGET_HINTS`、富文本清洗 |
| `shortcuts.js` | F1 → `/tutorial` |

### 4.1 localStorage 键

| 键 | 内容 |
| --- | --- |
| `mf_tut_progress` | `{schema:2, completed, tourSteps, lastTutorial, welcomeSeen, launchCount}` |
| `mf_kb_visible` | 键盘面板显隐 |
| `mf_kb_tab` / `mf_kb_recent` / `mf_kb_fav` | 页签 / 最近（最多 12）/ 收藏 |

写入失败不再静默：`writeStorage()` 把错误记进 `lastError.message`。读取时 `schema` 不匹配则从空白开始。

### 4.2 引导状态机

`start(id,{resume})` / `goto(i)` / `next()` / `prev()` / `pause()` / `resume()` / `end(how)`。有「上一步」、有暂停/继续、能接着上次走（内容版本变了不硬接）、只有真的到过最后一步才标记已学、缺目标不跳过而标成缺目标并允许跳过。

### 4.3 遮罩机制

| 机制 | 做法 |
| --- | --- |
| 挖洞 | 目标矩形上放 `span`，`box-shadow: 0 0 0 9999px <遮罩色>`，圆角 8px、内边距 8px |
| 遮罩色 | 亮 `rgba(0,0,0,0.451)` / 暗 `rgba(0,0,0,0.549)` |
| 四方位 + 边界夹取 | 按 `placement` 摆提示卡，再夹取 |
| 遮罩不吞点击 | 整层 `pointer-events:none`，只有提示卡可点 |

## 5. 引导目标约束

### 5.1 数据（`targets.js`）

| 数据 | 作用 | 现状 |
| --- | --- | --- |
| `PENDING` | 界面还没做的显式清单 | 空对象 |
| `TARGET_HINTS` | 目标在别的页或需前置条件时的人话提示 | 14 条 |
| `REGISTERED` | 界面确实注册了 `data-tour` 的名字清单 | 32 条 |
| `resolveTarget(name)` | 有元素返回 `{available:true}`，否则返回 `{available:false, reason}` | — |
| `findTargetEl(name)` | `[data-tour="…"]` + `getBoundingClientRect()`，宽高都为 0 不算可用 | — |

维护规矩：新界面落地时同一步骤既补 `data-tour`、也从 `PENDING` 删条目；从 `PENDING` 删条目时确保教程不再指向不存在的控件。

### 5.2 构建期双向校验（`check-ui.mjs`）

| 断言 | 失败信息 |
| --- | --- |
| 教程 target 必须有 `data-tour` 或写进 `PENDING` | 既不在源码里也没写进 PENDING |
| 两边都占 | 提示从 PENDING 删除 |
| `PENDING` 里不许留过时条目 | 属于过时条目，请删除 |
| `REGISTERED` 声明的名字必须在源码有 `data-tour` | 源码里找不到对应 data-tour |
| 键盘键数 = 126 | 键数不一致 |
| 分类名与顺序逐字等于基准串 | 硬编码串比对 |
| 每键有键面与插入值，无残留 `▢`，`\begin` 配 `\end` | 对应提示 |
| 键面不许显示裸 LaTeX | 仍在显示裸 LaTeX |
| 教程字段合法性 | actionType 非法、缺指纹等 |

验证命令：

```powershell
cd MF_UI\MFMath.UI.Vue; node tools\check-ui.mjs
```

输出含：`教程引用的 target：30 个（已实现 30，待实现 0）`、`数学键盘：6 分类 / 126 键（基准 126）`、`键面可读性：排版 13 键 / 文字 109 键 / 紧凑替代 0 键 / 清理后文字 4 键（裸 LaTeX 0 键）`、`自检通过`。

### 5.3 端到端（`cdp-tutorials-keypad.mjs`）

覆盖 18 篇目录、进度、正文步数/FAQ、从正文启动引导、高亮到目标而不静默跳过、上一步/暂停、中途结束不标已学、走到最后一步才标已学、示例库跳转、键盘 6 分类顺序、模板键面不是 LaTeX 源码、基础运算 26 / 希腊字母 34 / 常用模板 11 键、插入保留占位符、符号搜索、无聚焦输入框提示、富文本清洗。该用例共 43 个 `check(` 调用点，已登记进 `tests/run-all.ps1`。

## 6. 数学键盘

### 6.1 分类与键数

| 顺序 | 分类 | 键数 | 定义处 |
| --- | --- | --- | --- |
| 1 | 基础运算 | 26 | `keypadSymbols.js` |
| 2 | 微积分 | 20 | `keypadSymbols.js` |
| 3 | 线性代数 | 15 | `keypadSymbols.js` |
| 4 | 希腊字母 | 34 | `keypadSymbols.js` |
| 5 | 概率统计 | 20 | `keypadSymbols.js` |
| 6 | 常用模板 | 11 | `keypadSymbols.js` |
| | 合计 | 126 | `KEY_COUNT` |

键数常量写死在 `keypadSymbols.js`（基准 126），由 `check-ui.mjs` 对账；分类名与顺序同样逐字对账。另有 `DEFAULT_RECENT` 6 个兜底键。

### 6.2 键面分类

| 类别 | 判据 | 显示 | 键数 |
| --- | --- | --- | --- |
| 纯文字 | 键面不含 LaTeX 命令/上下标/占位符 | 原样文字 | 109 |
| 数学排版 | 含特征且 KaTeX 能排 | KaTeX 渲染，失败退回文本 | 13 |
| 清理后文字 | 含特征但排不出 | 去环境名、反斜杠、花括号 | 4 |
| 紧凑替代 | `FACE_OVERRIDE` | 紧凑键面 | 0 |

不变量由 `check-ui.mjs` 守着：任何键面不许显示裸 LaTeX，且必须有键面是按数学排版。

### 6.3 插入纪律

插入 LaTeX，不插显示用 Unicode；占位符不许被剥掉（改用 MathLive 的 `#0` / `#?`）；矩阵模板必须补全；键面与插入值分开（模板键键面用真字母，仅此一处有意偏离基准键面约定）。

### 6.4 插入目标

`activeField` 记录最后聚焦的 `MathField`，登记句柄走 `focusin`/`focus`/`pointerdown` 三个入口。无登记句柄时看 `document.activeElement` 是否为 `<math-field>`。插入失败时明确提示先点输入框。

### 6.5 面板行为

默认隐藏、顶部按钮切换，显隐记忆 `mf_kb_visible`；基础运算页不显示（那一页自带键盘）；分类页签 + 名称翻译；页签持久化 `mf_kb_tab`；符号搜索按键盘面 / LaTeX / 中文关键词，默认最多 24 条；最近最多 12 条；收藏以 `latex` 为键。

## 7. 验证命令

```powershell
cd MF_UI\MFMath.UI.Vue
# 教程+键盘构建期自检
$env:MF_TUTORIAL_ARCHIVE="$env:TEMP\mf-arch"; npm run check:ui
# 只跑目标/键盘校验
node tools/check-ui.mjs
```

教程与键盘端到端需宿主带 `--remote-debugging-port=9222` 后运行 `node tests/cdp-tutorials-keypad.mjs`。
