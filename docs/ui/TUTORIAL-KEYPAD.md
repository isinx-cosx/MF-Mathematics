# 教程系统与数学键盘：18 篇教程 · 30 个引导目标 · 126 键

> **本文只回答一个问题：18 篇教程怎么组织、引导目标怎么保证不"指空"、数学键盘怎么与 v1 对齐。**
>
> 与同层其它文档的分工：
> - [README.md](README.md) —— 前端两个工程、构建链与测试资产总览；本文只讲教程与键盘这两块；
> - [AI.md](AI.md) —— AI 面板与步骤视图（教程 04/05 里 `ai_dialog.*`、`step_viewer.content` 的实现面）；
> - [TOOLS.md](TOOLS.md) —— 搜索页与函数工具箱（教程 12 里 `search_panel.*` 的落点）；
> - [CHECKS.md](CHECKS.md) —— 四道构建闸门各自断言什么；本文只列 `check-ui.mjs` 里跟教程、键盘有关的那几组；
> - [../OPEN-ITEMS.md](../OPEN-ITEMS.md) —— 状态类清单（"教程目标 30/30、`PENDING` 已空"这类结论的现役出处）。

**核对时间**：2026-10-07 10:57（+08:00），本机 Windows，Node v26.3.1 / npm 11.16.0。
本文的"实测"＝本次会话真的跑过那条命令，输出抄在表里；**v1 的对照数字**来自归档的 v1 后端源码
（`..\_archive\v1-python-backend-20261006-073851.zip`，归档缘由见 [../OPEN-ITEMS.md](../OPEN-ITEMS.md) §4，
取用命令见本文 §7）。

---

## 1. 一页结论

| 项 | 实测值 | 出处 |
| --- | --- | --- |
| 教程篇数 | 18 | `build-tutorials.mjs:41-60` 的权威数量表；本次复跑输出 |
| 步骤 / 示例 / FAQ | 66 / 52 / 42 | 本次 `node tools/build-tutorials.mjs` 输出 |
| 引导引用到的 target（去重） | **30** 个 | `check-ui.mjs:542` 打印 `30 个（已实现 30，待实现 0）` |
| `PENDING` 条目 | **0**（空对象） | `src/lib/tutorial/targets.js:33-47` |
| 数学键盘 | 6 分类 / **126** 键，v1 也是 126 | `check-ui.mjs:102-104` 打印；v1 侧见 §6.1 |
| 键面可读性 | 排版 13 键 / 文字 109 键 / 清理后文字 4 键 / **裸 LaTeX 0 键** | `check-ui.mjs:544` 打印 |
| 端到端用例登记 | `cdp-*` 48 个，已登记 48 个 | `check-ui.mjs:545` 打印 |
| 教程+键盘专项用例 | `tests/cdp-tutorials-keypad.mjs`，43 个 `check(...)` 调用点 | 本次静态清点（§9 说明未跑原因） |

---

## 2. 教程数据流：谁产出谁

### 2.1 三个位置，别搞反方向

| 环节 | 路径 | 角色 | 出处 |
| --- | --- | --- | --- |
| **输入**（不在本仓库） | `<v2.0>/../Multifunctional-Mathematics/MF_Tutorial/tutorials/*.yaml` | 唯一内容源，18 篇 | `tests/engine-paths.mjs:36-42`（两个候选 + `MF_TUTORIAL_SRC` 覆盖） |
| 转换器 | `MF_UI/MFMath.UI.Vue/tools/build-tutorials.mjs` | 自带的 YAML 子集解析 + 严格自检 | `build-tutorials.mjs:2-19` |
| **产物** | `MF_UI/MFMath.UI.Vue/src/tutorials/tutorials.json` | 前端 `import` 的数据源（54.6 KB） | `build-tutorials.mjs:32`、`472-481` |
| **留档**（副产物） | `docs/tutorials-src/*.yaml`（18 个，git 已跟踪） | 供人比对，**不参与运行** | `build-tutorials.mjs:36`、`:482-501`；`git ls-files docs/tutorials-src` = 18 行 |

⚠ **方向纠正**：`docs/tutorials-src/*.yaml` 是**产物**，不是输入 —— 脚本把 v1 原件*拷进去留档*
（`build-tutorials.mjs:489` 的 `copyFileSync(SRC, ARCHIVE)`）。改这个目录里的 YAML 对软件**没有任何影响**，
下一次 `npm run tutorials` 会用 v1 原件覆盖它。仓库里唯一引用该目录的代码就是那条拷贝语句（实测 grep 全仓：只有 `build-tutorials.mjs:18`、`:36`）。

### 2.2 实测：转换 + 自检一次

```powershell
cd MF_UI\MFMath.UI.Vue
# 留档目录指到临时目录，避免动 docs/tutorials-src（它只是副本）
$env:MF_TUTORIAL_ARCHIVE = "$env:TEMP\mf-arch"
node tools/build-tutorials.mjs
```

本次输出（节选）：`解析到 18 篇 / 66 步 / 52 示例 / 42 FAQ` → `自检通过 ✔` → `写出 MF_UI\MFMath.UI.Vue\src\tutorials\tutorials.json （54.6 KB）`。

**幂等已核对**：重跑前后 `tutorials.json` 的 SHA256 都是 `C623D363ACE7E9242A041957BB9C3C9F4BDA05A946264BE69CAE5FF2C56B3C2F`，
且 `git status --short MF_UI/MFMath.UI.Vue/src/tutorials/tutorials.json` 无输出 —— 仓库里提交的那份就是这条命令的产物。

### 2.3 转换期做了什么（每一步都能被下面某条自检抓住）

| 处理 | 说明 | 出处 |
| --- | --- | --- |
| 字段改名 | v1 的 `Step.action`（动作类型）与 `Example.action`（计算操作）同名不同义，拆成 `actionType`/`actionValue` 与 `operation` | `build-tutorials.mjs:301-320` |
| 排序 | 按 `order` 升序 | `build-tutorials.mjs:384` |
| 内容指纹 | `version` = `sha1(JSON(steps, examples, faq))` 前 8 位 | `build-tutorials.mjs:326-330` |
| v2 文案覆盖 | `V2_OVERRIDES`：v1 原件不动，每次生成都生效 | `build-tutorials.mjs:83-128`、`134-153` |
| 死字段原样保留 | `prerequisites` 在 v1 就引用不存在的教程，这里**只留原文供比对** | `build-tutorials.mjs:345-346` |
| 自检 1 / 1b / 2 | ① 18 篇的 step/example/faq/order 逐项对上权威数量表；② 覆盖表**每个索引必须命中**（写错下标不许静默失效）；③ 字段完整性（步骤必须有 `target`/`text`，示例不许三者全空，FAQ 不许空） | `build-tutorials.mjs:386-437` |

指纹的作用在 `src/lib/tutorial/store.js:109-121`：`isCompleted()` 要求 `rec.version === t.version`，
内容一变"已学"就失效（`isStale()` 供界面说明"为什么又变成未学了"，`TutorialCatalogView.vue:95` 显示这句）。

### 2.4 v2 覆盖表：改了哪三处、为什么

| 教程 | 位置 | 改成 | 为什么 |
| --- | --- | --- | --- |
| `basic-calculation` | `steps[5]` → target `toolbar.ai_button` | "可以让 AI 助手帮你选对引擎函数……数值始终由引擎产出" | v1 这一步指向 `calc_block.ai_accel_button`（`02-basic-calculation.yaml:51`），v2 **决定不做**该按钮 |
| `ai-steps-accelerate` | `title`/`summary`、`steps[4]` → `ai_dialog.input`、`faq[0]`、`faq[1]` | 改名为"步骤推导与 AI 讲解"，并写明"数字不是 AI 算的" | 同上：v1 的 `05-ai-steps-accelerate.yaml:44` 指向同一个不存在的按钮；且"让模型直接计算"违反产品硬约束 |
| `tips-and-tricks` | `faq[2]` | "引擎通常都在毫秒级完成……" | 原文承诺的是不存在的配额与"本地引擎算不动" |

出处：`build-tutorials.mjs:83-128`。**v1 全域只有 2 个步骤**指向 `calc_block.ai_accel_button`（实测：`02-basic-calculation.yaml:51`、`05-ai-steps-accelerate.yaml:44`），
两条都已被改指 —— 这解释了为什么 v1 的 31 个去重 target 到 v2 变成 30 个（`calc_block.ai_accel_button` 消失，没有新增名字）。

---

## 3. 18 篇教程一览（实测，来自 `src/tutorials/tutorials.json`）

| order | id | 分类 | 难度 | 步 | 示例 | FAQ | 时长 | version |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `quick-start` | 入门指南 | 入门 | 4 | 2 | 2 | 3 分钟 | `41e15a87` |
| 2 | `basic-calculation` | 计算模块 | 入门 | 6 | 5 | 3 | 5 分钟 | `7e7fc80b` |
| 3 | `plot-2d` | 绘图系统 | 入门 | 6 | 4 | 3 | 5 分钟 | `8ef1e614` |
| 4 | `ai-assistant` | AI 功能 | 入门 | 5 | 2 | 3 | 4 分钟 | `baea3950` |
| 5 | `ai-steps-accelerate` | AI 功能 | 进阶 | 5 | 2 | 2 | 4 分钟 | `ae4f992f` |
| 6 | `linear-algebra` | 计算模块 | 进阶 | 3 | 4 | 2 | 5 分钟 | `f5544e6e` |
| 7 | `probability-statistics` | 计算模块 | 进阶 | 3 | 3 | 2 | 5 分钟 | `d864a1e8` |
| 8 | `numerical-analysis` | 计算模块 | 进阶 | 3 | 4 | 2 | 5 分钟 | `f9674ba9` |
| 9 | `plot-3d-complex` | 绘图系统 | 进阶 | 4 | 4 | 2 | 5 分钟 | `b03c2eb8` |
| 10 | `vector-field-geometry` | 绘图系统 | 高级 | 3 | 4 | 2 | 6 分钟 | `b9a194da` |
| 11 | `math-keyboard` | 工具 | 入门 | 3 | 2 | 2 | 3 分钟 | `f5a927a1` |
| 12 | `search-settings` | 设置 | 入门 | 6 | 2 | 2 | 4 分钟 | `b53c4d84` |
| 13 | `themes-appearance` | 设置 | 入门 | 2 | 0 | 2 | 2 分钟 | `023514cf` |
| 14 | `tips-and-tricks` | 入门指南 | 高级 | 1 | 2 | 4 | 5 分钟 | `52e81dd8` |
| 15 | `complex-analysis` | 计算模块 | 进阶 | 3 | 3 | 2 | 8 分钟 | `0383d5b2` |
| 16 | `functional-analysis` | 计算模块 | 高级 | 3 | 3 | 2 | 10 分钟 | `17a7f1b3` |
| 17 | `measure-theory` | 计算模块 | 高级 | 3 | 3 | 2 | 10 分钟 | `4ba5920f` |
| 18 | `algebraic-topology` | 计算模块 | 高级 | 3 | 3 | 3 | 10 分钟 | `033482c7` |

分布（实测）：分类 `general 2 / calculation 8 / plot 3 / ai 2 / tools 1 / settings 2`；
难度 `beginner 7 / intermediate 6 / advanced 5`。分类名与图标的权威表在 `build-tutorials.mjs:286-298`
（`general 入门指南 / calculation 计算模块 / plot 绘图系统 / ai AI 功能 / tools 工具 / settings 设置`）。

步骤里的 `actionType` 分布：`wait 26 / click 15 / select 10 / type 7 / null 8`；
`highlight`：`rect 50 / circle 16`；`placement`：`bottom 31 / right 15 / left 8 / top 12`（实测统计，`check-ui.mjs:140-149` 校验取值合法）。

---

## 4. 前端怎么消费这些数据

| 组件 | 路径 | 职责 | 出处 |
| --- | --- | --- | --- |
| 教程目录 | `src/views/tutorial/TutorialCatalogView.vue` | 分类/难度筛选、进度 `已学 x/y · %`、从任意一篇启动引导、断点续走、重置进度 | `:30-51`、`:60`、`:96-102` |
| 教程正文 | `src/views/tutorial/HelpArticleView.vue` | 概述/操作步骤/示例表/FAQ；底部"标记为已学"可取消 | `:90-130`、`:68-70` |
| 示例库 | `src/components/tutorial/ExampleLibrary.vue` | 把 52 条示例"加载到工作区"（操作名反查页面 + 明说失败原因） | `:35-46`、`:54-74` |
| 欢迎窗 | `src/components/tutorial/WelcomeDialog.vue` | 首次启动 4 张卡；末张卡按**真实示例数**计算 | `:22`、`:63` |
| 引导遮罩 | `src/components/tutorial/TourOverlay.vue` | 挖洞高亮、提示卡、上一步/暂停/跳过 | `:56-89`、`:206-216` |
| 引导状态机 | `src/lib/tutorial/tour.js` | 前进/后退/暂停/断点/结束判定 | 见 §4.2 |
| 进度存储 | `src/lib/tutorial/store.js` | `localStorage` 读写、内容指纹失效 | 见 §4.1 与 §2.3 |
| 目标定位 | `src/lib/tutorial/targets.js` | `[data-tour]` 定位、`PENDING`、`TARGET_HINTS`、富文本清洗 | 见 §5 |
| 全局快捷键 | `src/lib/keyboard/shortcuts.js` | **F1 → `/tutorial`**；Ctrl+Z / Ctrl+Y | `:76-80`、`:82-101` |

入口：路由 `/tutorial`、`/tutorial/:id`、`/examples`（`src/router/index.js:59-60`、`:110-112`），
侧栏"帮助 → 使用教程"（`src/lib/router/nav.js:82`），常驻挂载在 `App.vue:437-438`（键盘）与 `:447-448`（欢迎窗 + 遮罩）。

### 4.1 `localStorage` 键一览

| 键 | 内容 | 出处 |
| --- | --- | --- |
| `mf_tut_progress` | `{schema:2, completed, tourSteps, lastTutorial, welcomeSeen, launchCount}` | `store.js:24-25`、`:73-93` |
| `mf_kb_visible` | 键盘面板显隐（`"1"` 表示开） | `App.vue:61`、`:214` |
| `mf_kb_tab` / `mf_kb_recent` / `mf_kb_fav` | 当前分类页签 / 最近使用（最多 12）/ 收藏 | `MathKeypad.vue:31-33`、`:35-51` |

写入失败**不再静默**：`writeStorage()` 把错误记进 `lastError.message`，由 `storageError` 暴露给界面
（`store.js:44`、`:88-92`、`:137`；目录页 `:79` 与正文页 `:83` 都会显示）。读取时若 `schema` 不匹配，
宁可"从空白开始"并说明（`store.js:59-62`）—— v1 是写失败只 `logger.debug`。

### 4.2 引导状态机：与 v1 的五条差异（逐条对着 v1 源码核过）

| # | v2 行为 | v1 的实际代码 | 出处 |
| --- | --- | --- | --- |
| 1 | 有"上一步" | v1 只有 `_advance()`，全库没有 prev | `walkthrough.py:193-196` |
| 2 | 有暂停/继续 | v1 没有暂停；`stop()` 与"跳过"都把步号归零（丢进度） | `walkthrough.py:100`、`:204-207` |
| 3 | 能"接着上次走"，且内容版本变了不硬接 | v1 的 `start()` 无条件 `_current_step = 0`，不检查已学状态 | `walkthrough.py:91`；`tour.js:52-59`、`store.js:130-136` |
| 4 | **只有真的到过最后一步**才标记已学 | v1 的 `_finish()` 无条件 `mark_completed()`，而"所有步骤都被跳过"也会递归到越界→`_finish()` | `walkthrough.py:104-108`、`:209-216`；`tour.js:109-121` |
| 5 | 缺目标**不跳过**，标成该步缺目标并允许跳过 | v1 `_current_step += 1` 后递归，用户什么都看不到 | `walkthrough.py:118-123`；`targets.js:8-9` |

状态机本身：`start(id,{resume})` / `goto(i)` / `next()` / `prev()` / `pause()` / `resume()` / `end(how)`
（`tour.js:39-141`）；`noteMissing(i)` 由遮罩在定位失败时调用（`tour.js:99-101`、`TourOverlay.vue:72`）。

### 4.3 遮罩的四个机制（含 v1 的等价物与差异）

| 机制 | 做法 | v1 对照 |
| --- | --- | --- |
| 挖洞 | 目标矩形上放一个 `span`，`box-shadow: 0 0 0 9999px <遮罩色>`；圆角 8px、内边距 8px | v1 用 `QPainterPath.subtracted`，`pad = 8` 一致（`overlay.py:156`、`:191-195`） |
| 遮罩色 | 亮 `rgba(0,0,0,0.451)` / 暗 `rgba(0,0,0,0.549)` | v1 `QColor(0,0,0,115)` / `(0,0,0,140)`，115/255=0.451、140/255=0.549 **完全一致**（`overlay.py:21-22`） |
| 四方位 + 边界夹取 | 按 `placement` 摆提示卡，再 `clamp(10, 视口-卡-10)` | v1 `overlay.py:287-302` 同款（`margin=16`、夹取 10） |
| 遮罩不吞点击 | 整层 `pointer-events:none`，只有提示卡可点；用户**真的去点**目标，`document` 捕获阶段监听命中即前进 | v1 显式设 `WA_TransparentForMouseEvents=False`，然后靠 `hasattr(target,"click")` 反射自动点（`overlay.py:91`、`walkthrough.py:168-173`） |

v1 那条反射路径**实际上一个都不会执行**：`_execute_action()` 在第一行就把没有 `action_value` 的步骤挡掉
（`walkthrough.py:139-142`），而 66 个步骤里 15 个 `actionType=click` 的 **actionValue 全是空**（实测：`src/tutorials/tutorials.json` 里这 15 步的 `actionValue` 均为 `""`）。
另有 `prefers-reduced-motion` 时关掉脉冲动画（`TourOverlay.vue:246-248`，v1 没有这个考虑）。

---

## 5. 引导目标的纪律：三道防线

### 5.1 防线 A —— 数据（`src/lib/tutorial/targets.js`）

| 数据 | 作用 | 现状 |
| --- | --- | --- |
| `PENDING` | "界面还没做"的显式清单：`name → 缺什么/依赖什么阶段` | **空对象**（`targets.js:33-47`）。注释写明了它曾经唯一的条目 `calc_block.ai_accel_button` 为什么不做了 |
| `TARGET_HINTS` | 目标"在别的页"或"需要先满足前置条件"时的人话提示（`route` + `note`） | 14 条（`targets.js:60-78`） |
| `REGISTERED` | 界面里确实注册了 `data-tour` 的名字清单（供文档与校验脚本对照） | 32 条（`targets.js:85-120`） |
| `resolveTarget(name)` | 有元素 → `{available:true}`；没有 → `{available:false, reason}`，`reason` 取 `PENDING[name]` 或一句兜底 | `targets.js:125-136` |
| `findTargetEl(name)` | `[data-tour="…"]` + `getBoundingClientRect()`；**宽高都为 0 的元素不算可用**（`v-if` 藏起来的不算） | `targets.js:138-151`（`145-146` 是那条零尺寸判断） |

维护规矩（写在 `targets.js:30-31`、`:45-46`）：**新界面落地时，同一步骤里既补 `data-tour`、也从 `PENDING` 删条目**；
反过来，从 `PENDING` 删条目时必须确保教程不再指向不存在的控件。

### 5.2 防线 B —— 构建期双向校验（`MF_UI/MFMath.UI.Vue/tools/check-ui.mjs`）

| 断言 | 行号 | 失败会说什么 |
| --- | --- | --- |
| 教程 target 必须"源码里真有 `data-tour`"**或**"在 `PENDING` 里写明理由" | `:79-84` | `教程 target「x」既不在源码的 data-tour 里，也没写进 PENDING 说明理由` |
| 两边都占 → 警告（界面已做出来，`PENDING` 该删了） | `:85-88` | 提示 `请从 PENDING 删除` |
| `PENDING` 里**不许留过时条目**（没有任何步骤引用它了） | `:90-94` | `属于过时条目，请删除` |
| `REGISTERED` 声明的名字必须在源码里有对应 `data-tour` | `:95-99` | `REGISTERED 里声明了「x」，但源码里找不到对应的 data-tour` |
| 键盘键数 = v1 的 126 | `:102-104` | `键盘键数 126 ≠ v1 的 126` |
| 分类名与**顺序**必须逐字等于 v1 | `:119-122` | 硬编码串 `基础运算,微积分,线性代数,希腊字母,概率统计,常用模板` |
| 每键都要有键面与插入值；插入值不许残留 `▢`；`\begin{env}` 必须配 `\end{env}` | `:108-118` | 如 `键「x」的 \begin{pmatrix} 没有配对的 \end` |
| 键面不许显示裸 LaTeX（要么排版成数学、要么清理过语法） | `:124-138` | `键面「x」仍在显示裸 LaTeX —— 用户看不懂` |
| 教程字段合法性（`actionType`/`highlight`/`placement`/`version`） | `:140-149` | `actionType 非法`、`缺少内容指纹 version` 等 |

本机实测（2026-10-07 10:5x，`node tools/check-ui.mjs`）：
`源码里注册的 data-tour：38 个` / `教程引用的 target：30 个（已实现 30，待实现 0）` /
`数学键盘：6 分类 / 126 键（v1 也是 126）` / `键面可读性：排版 13 键 / 文字 109 键 / 紧凑替代 0 键 / 清理后文字 4 键（裸 LaTeX 0 键）` / `自检通过 ✔`。

> `38 个`这个数字里含 5 个假阳性，见 §8 D8；它不影响覆盖判定，但会让读者高估"已注册钩子"的数量。

### 5.3 防线 C —— 端到端（`tests/cdp-tutorials-keypad.mjs`）

覆盖点（每行都有断言）：18 篇目录（`:91`）、进度（`:94`）、正文步数/FAQ（`:112`、`:115`）、从正文启动引导（`:124`）、
**高亮到目标而不是静默跳过**（`:128-129`）、步骤计数（`:132`）、上一步/暂停（`:139`、`:147`、`:153`）、
中途结束**不**标记已学（`:172`）、走到最后一步才标记已学（`:193`）、示例库跳转回归（`:213-238`）、
键盘 6 分类名称顺序（`:260-261`）、页脚 `{n}` 已代入（`:268`）、模板键面不是 LaTeX 源码（`:279`）、
基础运算 26 / 希腊字母 34 / 常用模板 11 键（`:290`、`:299`、`:308`）、插入 LaTeX 且保留占位符（`:326-328`）、
插入记入最近使用（`:334`）、符号搜索（`:347`）、无聚焦输入框时明确提示（`:363-366`）、富文本清洗 6 类注入载荷（`:401`）。
它已登记进套件（`tests/run-all.ps1:58`）；**本次没有跑**（本机没有带 `--remote-debugging-port=9222` 的宿主，见 §9）。

### 5.4 v1 的 34/66：独立复核（不是抄注释）

`targets.js:11-13`、`check-ui.mjs:4-6` 与 `cdp-tutorials-keypad.mjs:5-6` 都写着"v1 的 66 步里 34 步的目标控件根本不存在"。
本次**用归档的 v1 源码重新数了一遍**（命令见 §7），判据是 v1 自己那两条查找路径：
`register_elements()` 的 9 个注册名（`main_window.py:872-882`）与 `_find_by_object_name()` 的"取 `target` 最后一段当 `objectName`"（`walkthrough.py:177-191`）。

| 问题 | v1 实测 | 与文档里的说法 |
| --- | --- | --- |
| 66 步里目标既没注册、也没有同名 `setObjectName` 的步骤 | **34** | 一致 |
| 其中去重后的目标名 | **22** | 一致（"22 个名字全库无 setObjectName"） |
| 这些步骤的运行期后果 | 静默跳过；全部跳过 → 递归越界 → `_finish()` → `mark_completed()` | 一致（`walkthrough.py:104-108`、`:118-123`、`:209-216`） |

判据的边界：`setObjectName` 只按**字面量**收集（变量形式的名字数不到），所以 34 是"可查到的口径"；它与文档里的数字逐位吻合。

### 5.5 30 个 target 的分布（引用步数 / 源码位置）

| 组 | target（引用步数） | 源码位置 |
| --- | --- | --- |
| 外壳与顶栏 | `main_window.toolbar`(7)、`main_window.mode_selector`(16)、`main_window.theme_toggle`(2)、`main_window.help_button`(1)、`main_window.keyboard_button`(1) | `App.vue:310`、`:318`、`:329`、`:417`、`:414` |
| 顶栏按钮 | `toolbar.calc_button`(1)、`toolbar.plot_button`(2)、`toolbar.search_button`(1)、`toolbar.settings_button`(1)、`toolbar.ai_button`(2) | `App.vue:313`（一行两态）、`:412`、`:388`、`:410` |
| 计算块与结果对话框 | `calc_block.input`(5)、`calc_block.action_dropdown`(4)、`calc_block.calc_button`(2)、`result_dialog.steps_button`(1) | `views/calc/CalcView.vue:457`、`:461`、`:471`；`components/calc/ResultDialog.vue:137` |
| 绘图 | `plot_workspace.add_function`(3)、`plot_workspace.function_input`(1)、`plot_workspace.sliders`(1)、`plot_canvas`(2)、`geometry_canvas`(1) | `components/plot/ExpressionList.vue:173`、`:152`；`ParamSlider.vue:97`；`views/plot/PlotView.vue:808`；`PlotGeometryView.vue:221` |
| 设置与搜索 | `settings_dialog.appearance_tab`(1)、`settings_dialog.ai_tab`(1)、`search_panel.input`(1)、`search_panel.results`(1) | `views/settings/SettingsView.vue:95`（一行两态）；`views/tools/SearchView.vue:131`、`:172` |
| AI 与步骤 | `ai_dialog.input`(2)、`ai_dialog.send_button`(1)、`ai_dialog.context_label`(1)、`main_window.ai_settings`(1)、`step_viewer.content`(1) | `components/ai/AiPanel.vue:289`、`:301`、`:293`、`:195`；`components/ai/StepViewer.vue:54` |
| 数学键盘 | `math_keyboard.panel`(1)、`math_keyboard.titlebar`(1) | `components/math/MathKeypad.vue:97-98` |

引用步数合计 = 66，与教程数据一致；30 个 target 里 **14 个有前置提示**
（`ai_dialog.input`/`send_button`/`context_label`、`main_window.ai_settings`、`math_keyboard.panel`/`titlebar`、
`plot_workspace.sliders`、`result_dialog.steps_button`、`search_panel.input`/`results`、
`settings_dialog.ai_tab`/`appearance_tab`、`step_viewer.content`、`toolbar.ai_button`），
其余 16 个是**首屏就存在**的钩子（顶栏、计算块输入/按钮/下拉、画布、键盘按钮），不需要提示。

### 5.6 当前状态

`PENDING` 为空对象（`targets.js:33-47`），`check-ui.mjs` 打印"已实现 30，待实现 0"，
[../OPEN-ITEMS.md](../OPEN-ITEMS.md) 的 §0（`:19`）与 §4（`:115`、`:118`）都写着 30/30。
这三处**互相一致**，也是本文的现役结论；§3 那一节的历史数字已过期，见 §8 D7。

---

## 6. 数学键盘（126 键）

### 6.1 分类与键数：与 v1 逐类对齐

v1 的权威定义在归档源码 `MF_UI/math_keyboard.py` 的 `SYMBOLS`（`:14-52`，Python 3.7+ 的 dict 有序，顺序即页签顺序）。
本次把两份**各自数了一遍**（v2 数 `keypadSymbols.js` 的 `CATEGORIES`，v1 数归档源码的 `SYMBOLS`）：

| 顺序 | 分类 | v2 键数 | v1 键数 | v2 定义处 | v1 定义处 |
| --- | --- | --- | --- | --- | --- |
| 1 | 基础运算 | 26 | 26 | `keypadSymbols.js:44-50` | `math_keyboard.py:15-21` |
| 2 | 微积分 | 20 | 20 | `:51-66` | `:22-27` |
| 3 | 线性代数 | 15 | 15 | `:67-81` | `:28-32` |
| 4 | 希腊字母 | 34 | 34 | `:82-94` | `:33-40` |
| 5 | 概率统计 | 20 | 20 | `:95-109` | `:41-46` |
| 6 | 常用模板 | 11 | 11 | `:110-125` | `:47-51` |
| | **合计** | **126** | **126** | `:143`（`KEY_COUNT`） | `:14-52` |

`V1_KEY_COUNT = 126` 写死在 `keypadSymbols.js:146`，由 `check-ui.mjs:102-104` 对账；
分类名与顺序由 `check-ui.mjs:119-122` 逐字对账（v1 自证命令见 §7）。
另有 `DEFAULT_RECENT` 6 个兜底键（`:157`，最近使用为空时显示）。

### 6.2 键面：三类键走三条路（`src/lib/math/keyFace.js` + `KeyFace.vue`）

| 类别 | 判据 | 显示 | 本次实测键数 |
| --- | --- | --- | --- |
| 纯文字 | 键面不含 LaTeX 命令/上下标/占位符（`NEEDS_MATH`，`keyFace.js:23`） | 原样文字（`∫` `sin` `α` `≤` `A⁻¹`） | **109** |
| 数学排版 | 含上述特征且 KaTeX 能排出来（`isRenderable`，`:74-81`） | KaTeX 渲染（`MathLatex.vue`，失败退回文本） | **13** |
| 清理后文字 | 含特征但排不出来 → `toPlain()` 去掉环境名、反斜杠、花括号（`:63-71`） | 清理后的可读文本 | **4**（`^` `_` `{` `}`） |
| 紧凑替代 | `FACE_OVERRIDE`（`:29-33`） | 一眼能懂的紧凑键面 | **0**（见 §8 D3） |

不变量由 `check-ui.mjs:124-138` 守着：**任何键面都不许显示裸 LaTeX**（`showsRawLaTeX`，`keyFace.js:108-115`），
并且必须至少有键面是"按数学排版"的（`:136-137`，防止模板键面整体退回源码）。
`{` `}` 两个键故意不被判成"裸 LaTeX"—— 它们插入的就是花括号（`keyFace.js:104-106` 记了这次自检自己抓出的误报）。

13 个"按数学排版"的键（实测）＝ `I_n`、`0_{m×n}` ＋ 11 个模板键（分数/根式/指数/下标/定积分/求和/极限/三个矩阵环境）。

### 6.3 插入值：四条纪律

1. **插 LaTeX，不插显示用 Unicode**。v1 是 `char.replace("▢","")` 后 `focused.insert(text)`（`math_keyboard.py:105-111`），
   126 键里只有「常用模板」那 11 键是 LaTeX，其余 115 键插的是 `∫` `α` 这类字符，MathLive 里排不出正确字形。
2. **占位符不许被剥掉**。v1 把 `▢` 直接删掉，于是 `\frac{▢}{▢}` → `\frac{}{}`、`\sqrt[▢]{▢}` → `\sqrt[]{}`，插入后光标无处可落。
   v2 改用 MathLive 的 `#0`（插入后光标停的位置）/ `#?`（可 Tab 跳转），与既有 `ExpressionList.vue` 符号面板同一套约定（`keypadSymbols.js:13-18`；该面板的实例见 `ExpressionList.vue:40-53`）。
3. **矩阵模板必须补全**。v1 的 `\begin{pmatrix}` 没有 `\end`（`math_keyboard.py:50`），插进去是残缺 LaTeX；
   v2 给完整的 2×2 环境（`keypadSymbols.js:122-124`），`check-ui.mjs:112-117` 按环境名配对校验。
4. **键面与插入值分开**。模板键的**键面**用真字母（`\frac{a}{b}`）而不是 v1 的 `▢` 空位 —— 这是唯一一处**有意偏离** v1，
   只改键面、插入值一个字没动（`keypadSymbols.js:26-31`、`:110-113`）。

### 6.4 插到哪里：`activeField` 的"最后聚焦"

| 机制 | 说明 | 出处 |
| --- | --- | --- |
| 登记句柄 | `MathField.vue` 挂载时 `createFieldHandle(...)`，`focusin`/`focus`/`pointerdown` 三个入口都登记（实测只挂 `focusin` 不够：MathLive 程序化 `focus()` 不触发它） | `MathField.vue:71-83`；`activeField.js:24-37` |
| DOM 兜底 | 没有登记句柄时，看 `document.activeElement` 是不是 `<math-field>` | `activeField.js:39-57` |
| 插入 | `insertLatex(latex, {selectionMode:"placeholder"})`；没有目标返回 `false` | `activeField.js:68-77` |
| 明确提示 | `onKey()` 插入失败时 flash 一句"先点一下要输入的输入框，再点符号"；面板常驻提示"未选中输入框 —— 点一下计算或绘图里的输入格" | `MathKeypad.vue:77-84`、`:116-118` |

v1 是 `QApplication.focusWidget()` + 只认 `QLineEdit`，找不到就静默忽略（`math_keyboard.py:106-111`）；
v2 保留 v1 那条"键位不可聚焦"的约束（`tabindex="-1"` + `@mousedown.prevent`，`MathKeypad.vue:123`、`:134`、`:146`），但不再当作唯一保障。

### 6.5 面板行为与检索

| 能力 | 说明 | 出处 |
| --- | --- | --- |
| 默认隐藏、顶部按钮切换 | 按钮文字 `⌨ 键盘` ↔ `▼ 收起`；显隐记忆 `mf_kb_visible` | `App.vue:56-62`、`:414-416` |
| 基础运算页不显示 | `keypadAllowed = route.path !== "/calc/basic"`（那一页自带计算器键盘，避免两套叠在一起） | `App.vue:58`、`:437-438` |
| 分类页签 + 名称翻译 | 页签渲染 `t(c.name)`；分类名不翻译键面 | `MathKeypad.vue:101-106`；`check-ui.mjs:473-477` |
| 页签持久化 | `mf_kb_tab`（v1 每次都回到"基础运算"） | `MathKeypad.vue:31`、`:35-51` |
| 符号搜索 | 按键面 / LaTeX / 中文关键词匹配，默认最多 24 条 | `keypadSymbols.js:148-154`；`MathKeypad.vue:56`、`:122-129` |
| 最近使用 / 收藏 / 页脚 | 最多 12 条最近；收藏以 `latex` 为键；页脚写"共 {n} 键 · 模板类键面按数学排版显示 · 插入的是 LaTeX" | `MathKeypad.vue:57-63`、`:83`、`:86-91`、`:155-158` |

---

## 7. 怎么复跑（本文所有数字的来源）

前置：`cd MF_UI\MFMath.UI.Vue`。

| 目的 | 命令 | 本次输出（2026-10-07 10:5x） |
| --- | --- | --- |
| 教程+键盘构建期自检 | `$env:MF_TUTORIAL_ARCHIVE="$env:TEMP\mf-arch"; npm run check:ui`（= `build-tutorials.mjs` → `check-ui.mjs` → `check-examples.mjs`，`package.json:15`） | `自检通过 ✔ 引导目标无静默失效、键盘键位与 v1 对齐、每个键面都看得懂、端到端用例无漏登记`；`示例总数 52：按操作名反查定位 31 条，按分类兜底 15 条` |
| 只重跑教程转换（不动 `docs/tutorials-src`） | `$env:MF_TUTORIAL_ARCHIVE="$env:TEMP\mf-arch"; node tools/build-tutorials.mjs` | `18 篇 / 66 步 / 52 示例 / 42 FAQ`，`tutorials.json 54.6 KB` |
| 只跑目标/键盘校验 | `node tools/check-ui.mjs` | `target 30 个（已实现 30，待实现 0）`；`6 分类 / 126 键` |
| 教程与键盘端到端 | 宿主带 `--remote-debugging-port=9222` 启动后 `node tests/cdp-tutorials-keypad.mjs`；整套 `powershell -File tests/run-all.ps1` | **本次未跑**（无宿主，见 §9） |
| v1 对照源码 | `Expand-Archive ..\_archive\v1-python-backend-20261006-073851.zip -DestinationPath $env:TEMP\v1py -Force` | 277 个 `.py`，含 `MF_UI\math_keyboard.py`、`MF_Tutorial\walkthrough.py`、`MF_Tutorial\overlay.py` |
| 复核 v1 侧数字（126 键、34/66） | 下方脚本（一条命令同时数两项） | `26 / 20 / 15 / 34 / 20 / 11`；`步骤 66 / 缺目标 34 / 去重名字 22` |

```powershell
# 一次数出 v1 的分类键数 + 引导目标缺失数（归档源码在 $env:TEMP\v1py）
Expand-Archive ..\_archive\v1-python-backend-20261006-073851.zip -DestinationPath $env:TEMP\v1py -Force
# ① 分类与键数（输入是归档的 MF_UI/math_keyboard.py）
$py = Get-Content "$env:TEMP\v1py\MF_UI\math_keyboard.py" -Raw
$block = [regex]::Match($py, 'SYMBOLS:[^=]*=\s*\{(?<body>.*?)\n\}', 'Singleline').Groups['body'].Value
foreach ($c in [regex]::Matches($block, '(?m)^\s*"(?<n>[^"]+)":\s*\[(?<b>.*?)^\s*\],?\s*$', 'Singleline')) {
  "{0,-8} {1,3} 键" -f $c.Groups['n'].Value, ([regex]::Matches($c.Groups['b'].Value, '"[^"]*"')).Count
}
# ② 缺目标：target 最后一段既无同名 setObjectName、也不在那 9 个 register_elements 里
$obj = Select-String -Path (Get-ChildItem "$env:TEMP\v1py" -Recurse -Filter *.py).FullName `
       -Pattern 'setObjectName\(\s*["'']([^"'']+)["'']' -AllMatches |
       ForEach-Object { $_.Matches } | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
$reg = @("main_window.toolbar","main_window.mode_selector","main_window.theme_toggle","main_window.help_button",
         "toolbar.calc_button","toolbar.plot_button","toolbar.ai_button","toolbar.search_button","toolbar.settings_button")
$st = Select-String -Path "..\..\..\Multifunctional-Mathematics\MF_Tutorial\tutorials\*.yaml" `
      -Pattern '^\s*-?\s*target:\s*"?([^"\r\n]+)"?\s*$' | ForEach-Object { $_.Matches[0].Groups[1].Value.Trim() }
$bad = $st | Where-Object { $l = ($_ -split '\.')[-1]; -not (($reg -contains $_) -or ($obj -contains $l)) }
"步骤 $($st.Count) / 缺目标 $($bad.Count) / 去重名字 $(($bad | Sort-Object -Unique).Count)"
```

---

## 8. 已知的文档债

| # | 类别 | 位置 | 说的是 | 代码实际做 | 影响 / 怎么证 |
| --- | --- | --- | --- | --- | --- |
| **D1** | 注释 + 旧文档 | `TourOverlay.vue:68-71`（意图）与 `:188-198`（模板）；[../OPEN-ITEMS.md](../OPEN-ITEMS.md) §3 `:74-77` | "区分两种情况：目标在别的页 → 给「前往该界面」按钮；需要先满足前置条件 → 给操作提示" | `resolveTarget()` 在不可用时**reason 恒为非空字符串**（`targets.js:130-135`），所以模板里 `v-if="missingReason"` 恒真 ⇒ `v-else-if="missingHint"`（`:192-198`）**永不渲染**。14 条 `TARGET_HINTS` 与"前往该界面"按钮都是死代码，用户看到的是"**这一步的目标界面还没做**" | 产品缺陷：教程 12/13 的目标在 `/settings`、`/tools/search` 上，用户按"下一步"而没点那个按钮时，界面会说一句**假话**（该界面早做好了）。证法：宿主里从 `/tutorial` 启动 `12-search-settings`，不点顶栏「搜索」直接连点"下一步"，观察 `.tip-missing.soft`/「前往该界面」是否出现（当前实现下不会出现）。未在浏览器里复现，见 §9 |
| **D2** | 旧文档（教程内容） | `docs/tutorials-src/11-math-keyboard.yaml:19-26`、`:31-40`、`:52-54` | 键盘有 6 个分类"基础运算/希腊字母/微积分/**集合逻辑/矩阵向量/常用函数**"，可"拖拽标题栏/拖拽右下角缩放/点 ✕ 关闭"，FAQ 也说"可拖拽到任意位置" | v2（**也是 v1**）的分类是"基础运算/微积分/线性代数/希腊字母/概率统计/常用模板"（`keypadSymbols.js:43-126`；归档 `math_keyboard.py:14-52`），面板是**底部停靠**面板，没有拖拽、没有缩放、没有 ✕（`MathKeypad.vue` 模板 + `App.vue:437-438`） | 教程内容缺陷：用户照着做会找不到那三个页签。`V2_OVERRIDES` 没覆盖这一篇（`build-tutorials.mjs:83-128` 只有 3 篇）。证法：读三段 YAML 原文与 `MathKeypad.vue` 模板；或跑一遍教程 11 |
| **D3** | 注释（两处） | `keyFace.js:26-33`、`:14`、`:22`；`keypadSymbols.js:20` | ①"少数键面（矩阵环境）放不下……换成一眼能懂的紧凑键面"；② 把 v1 遗留的 `\begin{pmatrix}` 缺 `\end` 当作**当下**的渲染失败样例 | ① 3 个 `FACE_OVERRIDE` 键（`\begin{pmatrix}` 等）**匹配不上任何 label** —— 今天的 label 是完整环境串（`keypadSymbols.js:122-124`），分支恒不命中；② v2 的 label 已含 `\end{pmatrix}`，矩阵键走 `reason:"math"`，今天真正触发 `fallback` 的是 `^` `_` `{` `}` 4 个键 | ① 死代码；② 样例过期（机制仍在）。证法：本次实测"紧凑替代 **0** 键"、`math` 13 键、`fallback` 4 键 |
| **D4** | 注释 | `keypadSymbols.js:23-24` | "键面文字与「6 个分类的名称与顺序」都和 v1 **完全一致**" | 同文件 `:26-31` 写明模板类 **11 键**的键面有意偏离 v1（`▢` → 真字母） | 对 11/126 个键，"完全一致"不成立；分类名与顺序确实完全一致（§6.1 已逐类核过） |
| **D5** | 注释 | `store.js:14-15` | "此处保留 import 接口位，不假装已经支持"（指 v1 的 `tutorial_progress.json`） | 模块的导出里**没有任何导入接口**（`store.js` 的 export 清单；最接近的 `resetAllProgress()` 是清空） | 将来接手的人按注释找那个"位"会扑空。证法：读 `store.js:96-196` 的导出 |
| **D6** | 注释 | `TourOverlay.vue:9` | "15 处 `action:click` 里**绝大多数**没写 `action_value`" | 实测 15/15 **全部为空** | 措辞弱于事实，而事实恰好说明 v1 的反射式自动点击一个都不会执行（`walkthrough.py:139-142`）。证法：读 `src/tutorials/tutorials.json` 统计 `actionType=click` 的 15 步的 `actionValue`（全为空） |
| **D7** | 旧文档 | [../OPEN-ITEMS.md](../OPEN-ITEMS.md) §3 `:76-77`、`:86-91` | "31 个教程目标里 29 个已实现 / 2 个待实现（只剩 AI 加速按钮、分步显示）"、"`step_viewer.content` / `calc_block.ai_accel_button` 仍在 PENDING" | 现役实测是 **30 个 target / 30 已实现 / 0 待实现**，`PENDING` 空对象；同文件 §0 `:19` 与 §4 `:115`、`:118` 已经改成 30/30 | §3 是"本轮已修"的历史小节，但它自己写着"修完就删"。**现役结论以 §0/§4 + `check-ui` 为准** |
| **D8** | 守卫缺口 | `check-ui.mjs:541` 打印的"源码里注册的 data-tour：**38** 个" | 读者会以为有 38 个真实钩子 | 38 = 33 个真实钩子 + **5 个假阳性**：`calc`/`plot`（`App.vue:313`、`:318` 三元表达式的比较值）、`appearance`/`ai`（`SettingsView.vue:95` 同上）、`${name}`（`targets.js:134` 的**错误文案字符串**里含 ` data-tour="${name}"`） | 覆盖判定会**放行**一个不存在的目标：若教程把 target 写成 `calc`/`plot`/`appearance`/`ai`，`check-ui.mjs:79-84` 认为"源码里有"，运行期却定位不到。证法：§7 的扫描（32 个属性位点 → 33 个真实名字） |
| **D9** | 守卫缺口 | `targets.js:85-120` 的 `REGISTERED` 只被**单向**校验（`check-ui.mjs:95-99`：REGISTERED ⊆ 源码） | 读者会把它当"已注册钩子的全集" | 源码里的 `plot.export_button`（`PlotView.vue:827`）不在 `REGISTERED` 里，不会被任何断言提醒；`REGISTERED \ 教程引用` 还有 `toolbar.history_button`、`tutorial.catalog` 两条 | 清单与源码可以静默漂移（对当前 30 个目标无影响）。证法：集合差（§7 扫描 + `targets.js:85-120`） |

---

## 9. 未证实项（本文没写死的东西）

| 结论 | 为什么没证实 | 怎么才能证实 |
| --- | --- | --- |
| `cdp-tutorials-keypad.mjs` 的真实 pass/fail | 本机**没有**带 `--remote-debugging-port=9222` 的宿主（`Get-Process msedgewebview2` = 0；`http://127.0.0.1:9222/json/version` 被拒绝）→ 属"环境没准备好"，不是产品缺陷 | 起宿主（带调试端口）后 `node tests/cdp-tutorials-keypad.mjs`，看最后一行 `RESULT|cdp-tutorials-keypad|<pass>|<fail>` |
| 该用例的用例数到底是几项 | 静态清点是 **43 个 `check(...)` 调用点**，其中 1 个在 6 元循环里 ⇒ 全通过时应为 `48/0`；而 [../MIGRATION-GAPS.md](../MIGRATION-GAPS.md) `:334` 写"37 项"、[../FRONTEND-FIXES.md](../FRONTEND-FIXES.md) `:39` 写"46 / 0"，两处都不等于静态值 | 同上：跑一次读 `RESULT|` 行，然后把旧文档的数字改掉 |
| D1 那条死分支在真实界面上的表现 | 静态可判定（上表已给推理链），但未在浏览器里复现 | 见 D1 的证法 |
| 键面 KaTeX 在 30px 键格里的观感（分数/根式是否完整） | 需要真实宿主渲染；本文只证"排得出来、不是裸源码" | 打开键盘「常用模板」页签截图；或跑 `cdp-tutorials-keypad.mjs:273-280` 那段 |
| `store.js:10-11` 说的宿主数据目录 `%LOCALAPPDATA%\MFMath\WebView2`；教程 11 FAQ 的"`\pi` → π" | 前者属宿主侧事实（本仓库里没有它的权威出处），后者是 MathLive 的输入行为 —— 两者本次都没在宿主里查/敲过 | 装好宿主后看该目录；在 `<math-field>` 里输入 `\pi` 看是否即时排版；或在 [../../MFMath.Host.Rust/docs/ACCEPTANCE.md](../../MFMath.Host.Rust/docs/ACCEPTANCE.md) 的验收里补一条 |

三条纪律在本文范围内的落地方式：**① 不编造结果** —— 上面 5 条明确标注"未证实"并给了证法；
**② AI 不承担计算** —— 砍掉"AI 加速"按钮、教程文案改成"数值一律由引擎产出"（§2.4），AI 的数值必须来自 `engine_call`；
**③ 每个修复都留下"为什么"和"怎么证明"** —— `PENDING` 每条都要写理由、`V2_OVERRIDES` 每个索引必须命中（`build-tutorials.mjs:404-415`）、缺目标不许静默跳过（`check-ui.mjs:79-84` + `cdp-tutorials-keypad.mjs:128-129`）。
