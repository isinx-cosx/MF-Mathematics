# 前端：分层、路由与导航表、i18n、样式

> **本文只回答一个问题：前端的目录分层、路由与导航表、i18n、样式是怎么组织的。**
>
> 与同层其它文档的分工：
> - [README.md](README.md) —— 前端由哪两个工程组成、构建链、测试资产；本文不重复这些，只讲**壳内部**的结构；
> - [ENGINE-BINDING.md](ENGINE-BINDING.md) —— `ENGINE_MAP` / `viewConfigs` / `calcArgs` 怎么把界面接到 C++ 引擎（本文只讲"模式名在哪渲染"）；
> - [PLOT.md](PLOT.md) —— 6 个 React 绘图页与共享 plot lib 的内部结构，以及被冻结的 Vue 绘图组（本文 §7 一句话带过）；
> - [CHECKS.md](CHECKS.md) —— 四道构建闸门各断言什么；本文只引用其中拦 i18n 漏译的那几条；
> - [TUTORIAL-KEYPAD.md](TUTORIAL-KEYPAD.md) —— 教程系统与 126 键数学键盘的内部结构（本文只讲它们的**入口从哪来**）。

**口径**：本文所有数字都是 **2026-10-07 本机实测**（命令抄在 §8，输出抄进表里）。
凡"读代码得出"而不是"跑出来"的，都在表里写明推导方式；没验证的一律进 §10。

---

## 1. 分层总览

产品外壳是 **Vue 工程**（`MF_UI/MFMath.UI.Vue/`）；`MF_UI/MFMath.UI.React/` 只提供绘图页，其 `dist` 无消费方（[README.md](README.md) §4.3）。

```
index.html:10  ──▶ src/main.js:18-23        createApp(App).use(router) + installErrorReporting + mount("#app")
                        │
                        ├─ src/App.vue      壳：侧栏导航 / 顶栏 / 内容区 <router-view> / 状态栏 / 常驻浮层
                        │      └─ src/router/registry.js:15  再导出 NAV_GROUPS / findNav
                        │             └─ src/lib/router/nav.js:13  NAV_GROUPS（4 组 27 项，Vue 与 React 共用）
                        ├─ src/router/index.js:88-134       路由表（31 条）
                        │      ├─ REAL_VIEWS:23-64          15 个直接组件（其中 7 条绘图 → ReactPlotView.vue）
                        │      └─ CALC_ROUTES:79-86         14 条学科路由 → CalcView.vue（FallbackView:17-20 兜底，当前 0 条命中）
                        ├─ src/views/**      16 个页面组件（路由的落点）
                        ├─ src/components/** 33 个组件（按域分子目录）
                        ├─ src/lib/**        51 个模块（引擎桥 / 绘图 / i18n / 设置 / 教程…，非组件代码全在这）
                        └─ src/styles/theme.css:1-815       唯一全局样式表（设计系统变量）
```

三个"从哪来"的入口，各自只有一个：

| 关注点 | 唯一入口 | 出处 |
| --- | --- | --- |
| 挂载与全局样式 | `main.js`（`import "./styles/theme.css"` 在 :14） | `src/main.js:18-23` |
| 导航数据 | `src/lib/router/nav.js` 的 `NAV_GROUPS` | `src/lib/router/nav.js:13` |
| 路由表 | `src/router/index.js` 的 `routes` | `src/router/index.js:88-134` |

`src/router/registry.js` 只有 15 行，**不再是视图注册表**（见 §9 D1）；真正的"路由 → 组件"映射在 `src/router/index.js`。

---

## 2. 目录规模（实测）

### 2.1 一级

| 目录 | 文件数 | 行数 | 装的是什么 |
| --- | --- | --- | --- |
| `src/`（根，`App.vue` + `main.js`） | 2 | 621 | 壳组件与入口 |
| `src/views/` | 16 | 5,737 | 路由落点的页面组件 |
| `src/components/` | 33 | 7,373 | 按域分的可复用组件（含 1 个 React 桥） |
| `src/lib/` | 51 | 16,748 | 非组件代码：引擎桥、绘图算法、i18n、设置、教程… |
| `src/router/` | 2 | 161 | `index.js`（路由表）+ `registry.js`（转出） |
| `src/styles/` | 1 | 815 | `theme.css`，唯一全局样式表 |
| `src/types/` | 1 | 45 | `webview.d.ts`：宿主对象的 TS 声明 |
| `src/tutorials/` | 1 | 1,604 | `tutorials.json`，**构建产物**（`tools/build-tutorials.mjs:20-21` 生成） |
| **合计** | **107** | **33,104** | 行数含空行，不含 `node_modules/`、`dist/` |

### 2.2 `views` / `components` / `lib` 的二级拆开

| `src/views/` 子目录 | 文件 | 行 | | `src/components/` 子目录 | 文件 | 行 | | `src/lib/` 子目录 | 文件 | 行 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| （根）`HomeView.vue` | 1 | 111 | | `ai/` | 4 | 670 | | （根）`bridge.js`+`push.js` | 2 | 729 |
| `account/` | 1 | 306 | | `calc/` | 3 | 319 | | `account/` | 1 | 216 |
| `calc/` | 2 | 847 | | `console/` | 1 | 186 | | `ai/` | 9 | 8,527 |
| `plot/`（**冻结**，§7） | 6 | 2,862 | | `history/` | 1 | 168 | | `console/` | 2 | 392 |
| `settings/` | 1 | 215 | | `math/` | 4 | 503 | | `diagnostics/` | 1 | 104 |
| `tools/` | 3 | 1,080 | | `plot/` | 6 | 2,673 | | `engine/` | 7 | 1,980 |
| `tutorial/` | 2 | 316 | | `plot-react/` | 1 | 107 | | `history/` | 1 | 164 |
| | | | | `settings/` | 10 | 2,150 | | `i18n/` | 5 | 1,014 |
| | | | | `tutorial/` | 3 | 597 | | `keyboard/` | 1 | 113 |
| | | | | `tools/`（**空目录**，0 文件） | 0 | 0 | | `math/` | 3 | 362 |
| | | | | | | | | `plot/` | 7 | 970 |
| | | | | | | | | `router/` | 1 | 96 |
| | | | | | | | | `search/` | 1 | 273 |
| | | | | | | | | `settings/` | 4 | 666 |
| | | | | | | | | `tutorial/` | 3 | 548 |
| | | | | | | | | `update/` | 1 | 180 |
| | | | | | | | | `workspace/` | 2 | 414 |

两条值得记住的数字：① `lib/ai/` 的 8,527 行里**5,905 行是 `lib/ai/engine-signatures.json`**（引擎签名表，生成物），代码本体只有约 2,600 行；② `src/components/tools/` 是**空目录**（0 文件，实测），工具页的组件在 `src/views/tools/` 下。

**Vue 与 React 的文件不在同一棵 `src/` 下**：`MFMath.UI.React/src/` 另有 37 个文件 / 6,824 行，其中 `plot/` 13 个文件 5,225 行、`styles/` 15 个文件 829 行（实测，同一口径）。

---

## 3. 路由：31 条从哪来

### 3.1 生成规则

| 事实 | 代码 |
| --- | --- |
| 首页单独一条 | `src/router/index.js:88-90`（`/` → `HomeView`，`name: "home"`） |
| **其余 27 条由 `NAV_GROUPS` 循环生成** | `src/router/index.js:92-106` |
| 路由 `name` 由路径推导 | `path.slice(1).replace(/\//g, "-")` → `/calc/harmonic-analysis` 得 `calc-harmonic-analysis`（:98） |
| `meta` 四个字段 | `{ title: 导航项名, desc: 分组名, calc, grid, reactPage }`（:103） |
| 3 条**不在导航里**的显式路由 | `/tutorial/:id`（:109-114）、`/settings`（:119-124）、`/account`（:129-134） |
| 历史模式 | `createWebHashHistory()` —— URL 形如 `#/calc/basic`，`file://` 与 dev server 都可用（:136-140） |
| 文档标题 | `router.afterEach` 写 `document.title`（:142-144） |

所以总数 = **1 + 27 + 3 = 31 条**（由 `:88-134` 的代码推导，未在运行中的宿主里点数）。

`/settings` 与 `/account` 必须**手写**注册：它们不在 `NAV_GROUPS` 里，而上面的路由是"照着导航表循环"生成的 —— 漏一步就是"点进去内容区空白"（`src/router/index.js:116-128` 记着这个坑踩过两次）。

### 3.2 三张映射表

| 表 | 是什么 | 条数 | 出处 |
| --- | --- | --- | --- |
| `REAL_VIEWS` | 路由 → 独立组件的**静态 import 函数** | 15 键（13 个导航项 + `/account` + `/settings`） | `src/router/index.js:23-64` |
| `CALC_ROUTES` | 走同一个 `CalcView.vue` 的学科路由 | 14 | `src/router/index.js:79-86` |
| `REACT_PAGES` | 绘图路由 → `ReactPlotView` 里的 React 页面键 | 7 | `src/router/index.js:68-76` |
| `FallbackView` | 既不在 `REAL_VIEWS` 也不在 `CALC_ROUTES` 时的兜底 | 0 条命中 | `src/router/index.js:17-20` |

`CalcView.vue` 靠**路由末段**去 `VIEW_CONFIGS` 取配置（`VIEW_CONFIGS` 正好 14 个键：`algebra, algebraic-topology, analytic-geometry, calculus, complex-analysis, functional-analysis, linear-algebra, measure-theory, number-theory, numerical, probability, real-analysis, sequences, harmonic-analysis`），渲染时读 `config.title` / `config.desc` / `config.modes`（`src/views/calc/CalcView.vue:439-440`；`src/lib/engine/viewConfigs.js:13-15`）。

### 3.3 覆盖核对（实测 27/27）

```
REAL_VIEWS keys: 15  CALC_ROUTES: 14  union: 29
nav routes: 27       nav routes covered: 27；NOT covered: []
realKeys not in nav: ["/account","/settings"]
```

脚本见 §8 第 3 条。结论：**每个导航项都有归宿**，`FallbackView` 当前不可达（与 `src/router/index.js:16` 的注释一致）；`REAL_VIEWS` 比导航多出的两个键是 `/account` 与 `/settings`，它们各自还有那条手写路由，属于同一份 import 的重复声明（改路径要改两处）。

---

## 4. 导航表（`NAV_GROUPS`：4 组 27 项）

### 4.1 全表

`route` 列即路由；`en` 列取自 `src/lib/i18n/en-US.js`（导航条目在 :15-46）。

**计算模式（15 项）** —— 顺序注释自称以"原版 `MF_UI/i18n.py` 的 `get_calc_modes()`"为准（`src/lib/router/nav.js:17-20`，该文件本工作区不存在，见 §10.1）：

| # | 导航项 | 路由 | 承载组件（出处 `src/router/index.js`） | en |
| --- | --- | --- | --- | --- |
| 1 | 基础运算 | `/calc/basic` | `views/calc/BasicCalcView.vue`（:25） | Basic Arithmetic |
| 2 | 代数计算 | `/calc/algebra` | `CalcView`（:80） | Algebra |
| 3 | 微积分 | `/calc/calculus` | `CalcView`（:80） | Calculus |
| 4 | 解析几何 | `/calc/analytic-geometry` | `CalcView`（:80） | Analytic Geometry |
| 5 | 数列 | `/calc/sequences` | `CalcView`（:82） | Sequences |
| 6 | 线性代数 | `/calc/linear-algebra` | `CalcView`（:80） | Linear Algebra |
| 7 | 概率论与数理统计 | `/calc/probability` | `CalcView`（:81） | Probability & Statistics |
| 8 | 数值分析 | `/calc/numerical` | `CalcView`（:81） | Numerical Analysis |
| 9 | 数论 | `/calc/number-theory` | `CalcView`（:81） | Number Theory |
| 10 | 实分析 | `/calc/real-analysis` | `CalcView`（:81） | Real Analysis |
| 11 | 泛函分析 | `/calc/functional-analysis` | `CalcView`（:82） | Functional Analysis |
| 12 | 复分析 | `/calc/complex-analysis` | `CalcView`（:82） | Complex Analysis |
| 13 | 代数拓扑 | `/calc/algebraic-topology` | `CalcView`（:83） | Algebraic Topology |
| 14 | 测度论 | `/calc/measure-theory` | `CalcView`（:83） | Measure Theory |
| 15 | 调和分析 | `/calc/harmonic-analysis` | `CalcView`（:85） | Harmonic Analysis |

**绘图模式（7 项）** —— 7 条全部指向 `components/plot-react/ReactPlotView.vue`（`src/router/index.js:37-46`）：

| # | 导航项 | 路由 | 页面键 `meta.reactPage` | 额外 meta | en |
| --- | --- | --- | --- | --- | --- |
| 1 | 2D 函数绘图 | `/plot/2d` | `2d` | — | 2D Function Plot |
| 2 | 极坐标 | `/plot/polar` | `polar` | `grid: "polar"` | Polar |
| 3 | 3D 曲面 | `/plot/3d` | `3d` | — | 3D Surface |
| 4 | 复平面 | `/plot/complex` | `complex` | — | Complex Plane |
| 5 | 向量场 | `/plot/vector` | `vector` | — | Vector Field |
| 6 | 自由几何 | `/plot/geometry` | `geometry` | — | Free Geometry |
| 7 | 分形 | `/plot/fractal` | `fractal` | — | Fractal |

**工具（3 项）**：

| # | 导航项 | 路由 | 承载组件 | en |
| --- | --- | --- | --- | --- |
| 1 | 搜索 | `/tools/search` | `views/tools/SearchView.vue`（:51） | Search |
| 2 | 控制台 | `/tools/console` | `views/tools/ConsoleView.vue`（:48） | Console |
| 3 | 函数工具箱 | `/tools/toolbox` | `views/tools/ToolboxView.vue`（:54） | Function Toolbox |

**帮助（2 项）**：

| # | 导航项 | 路由 | 承载组件 | en |
| --- | --- | --- | --- | --- |
| 1 | 使用教程 | `/tutorial` | `views/tutorial/TutorialCatalogView.vue`（:59） | Tutorials |
| 2 | 示例任务库 | `/examples` | **`components/tutorial/ExampleLibrary.vue`**（:60，注意在 `components/` 下） | Examples |

**不在导航里的 3 条路由**（入口在别处）：

| 路由 | 入口 | 承载组件 | 出处 |
| --- | --- | --- | --- |
| `/tutorial/:id` | 教程目录 / 引导进入的详情页 | `views/tutorial/HelpArticleView.vue` | `src/router/index.js:109-114` |
| `/settings` | 侧栏底部「⚙ 设置」按钮 | `views/settings/SettingsView.vue` | `src/router/index.js:119-124`；按钮见 `src/App.vue:388-390` |
| `/account` | 顶栏用户名/登录按钮 | `views/account/AccountView.vue` | `src/router/index.js:129-134`；按钮见 `src/App.vue:408-409` |

`calc` 组 15 项里 14 项走同一个 `CalcView`；唯一的例外是 `基础运算` → `BasicCalcView.vue`（自带计算器键盘，`:25`），并且**那一页不挂数学键盘**（`src/App.vue:58`）。

### 4.2 为什么这张表在 `src/lib/` 下（B11 的产物）

| 事实 | 证据 |
| --- | --- |
| `NAV_GROUPS` 与 `findNav` 只有一份，位于 `src/lib/router/nav.js:13,89` | 文件自述"两个工程都会 import 它"，并禁止在本文件 import Vue 或碰 DOM 全局（`src/lib/router/nav.js:4-9`） |
| Vue 侧**转出**，不复制 | `src/router/registry.js:15`；`src/App.vue:8` 从 `./router/registry.js` 取 |
| React 侧经 alias `@shared` 直接引入 | `MFMath.UI.React/src/App.tsx:7`（`@shared/router/nav.js`）；alias 配置见 [README.md](README.md) §3 |
| 修之前 React 有一份 61 行手抄副本，已漂移 | [BUGS.md](../../MF_UI/BUGS.md) 第 142 行（B11 第二轮"已修"） |

**两个渲染点**（同一份数据、两种外壳）：

| 外壳 | 渲染 | 出处 |
| --- | --- | --- |
| 产品壳（Vue） | `v-for="g in NAV_GROUPS"` → 分组标题 `t(g.title)`、条目 `t(it.name)` | `src/App.vue:311-323` |
| React 自己的 dev 壳 | `NAV_GROUPS.map(...)` → 侧栏列表（**未过 `t()`**） | `MFMath.UI.React/src/App.tsx:92-113` |

React dev 壳只把 `/plot/2d`、`/plot/polar` 当已迁移（`MFMath.UI.React/src/App.tsx:30`），其余路由显示"还没迁移到 React"占位（:245-250）—— 那是**它自己的壳**，不是产品路由表的真相（[README.md](README.md) §2.3）。

**双入口的代价（设计事实，不是缺陷）**：`NAV_GROUPS` 里同一路径既能是"侧栏一项"，也可能只是 `/account`、`/settings` 那种"顶栏/底部按钮的落点"。前者由循环生成路由，后者必须手写 —— 这条不对称就是 `src/router/index.js:116-128` 两次踩坑的根因。判断方法：**路由是否在 `NAV_GROUPS` 里**；不在就得在这里补一行。

---

## 5. i18n

### 5.1 机制：以中文原文为键

| 设计点 | 实现 | 出处 |
| --- | --- | --- |
| 语言表 | 只有 `zh-CN`、`en-US` | `src/lib/i18n/index.js:29-32` |
| 持久化键 | `localStorage["mf.lang"]`，取值不合法则回退 `zh-CN` | `src/lib/i18n/index.js:34-44` |
| `locale` 是 Vue `ref` | `export const locale = ref(readStored())` —— **因此 React 侧用不了它** | `src/lib/i18n/index.js:1,46` |
| 取译文 `t(key, params)` | 中文环境**原样返回键**；英文环境查 `DICT`，查不到**回退中文**（不空白、不显示 key） | `src/lib/i18n/index.js:64-75` |
| 占位符 | `{name}` 形式，用第二参数替换；**中英两个分支都替换**（曾出现中文界面显示字面 `共 {n} 键`） | `src/lib/i18n/index.js:65-74` |
| 合并顺序 | `DICT = { ...EN_MODES, ...EN_VARS, ...EN_RESULTS, ...EN }` —— 外壳文案（`EN`）优先级最高 | `src/lib/i18n/index.js:8` |
| `<html lang>` | 启动与切换时都同步 | `src/lib/i18n/index.js:53,77` |
| 切换 UI | 设置 → 外观 → 界面语言 | `src/components/settings/AppearanceGroup.vue:52-53`；断言见 `tests/cdp-settings.mjs:103-112` |

### 5.2 四张译文表（实测键数）

| 文件 | 导出 | 条目 | 覆盖的东西 | 谁渲染 |
| --- | --- | --- | --- | --- |
| `src/lib/i18n/en-US.js` | `EN` | 101 键 | 外壳：4 个分组标题、27 个导航条目、顶栏、外观浮层、窗口控制、语言项、键盘面板文案、14 条视图描述、缺参提示 | `src/App.vue`、`MathKeypad.vue`、`CalcView.vue` |
| `src/lib/i18n/en-modes.js` | `EN_MODES` | **415** | 引擎 action 的中文显示名 = `ENGINE_MAP`∪`EXTRA_MAP` 的全部键 | `CalcView.vue:469`（下拉框）、`MultiVarDialog.vue:55`、`ResultDialog.vue:121` |
| `src/lib/i18n/en-vars.js` | `EN_VARS` | 187 键（`ENGINE_VAR_SPECS` 的**唯一标签 186 条**） | 参数弹窗的字段标签 | `MultiVarDialog.vue:60`（`t(f[0])`） |
| `src/lib/i18n/en-results.js` | `EN_RESULTS` | 78 | 结果面板字段标签（`resultModel.js` 的 `FIELD_LABELS`） | `src/lib/engine/resultModel.js:138`（`labelOf` 唯一出口） |

键数怎么来的（可复跑，见 §8 第 4 条）：`EN_MODES 415`、`EN_VARS 187`、`EN_RESULTS 78`、`EN 101`；且 `node tools/check-ui.mjs` 打印 `i18n 模式名：415 个模式，缺译文 0 个` / `i18n 弹窗字段：186 条唯一标签，缺译文 0 条` / `i18n 结果标签：78 个字段，缺译文 0 个`。

### 5.3 覆盖到哪、没覆盖到哪

**覆盖到（都用 `t()` 包了）**：

| 面 | 证据 |
| --- | --- |
| 侧栏：4 分组 + 27 条目 | `src/App.vue:314,321` |
| 顶栏（账号/AI/搜索/历史/键盘/帮助/关于）与窗口三键 | `src/App.vue:412-426` |
| 外观浮层（配色/圆角/疏密/字体/跟随系统） | `src/App.vue:329-385` |
| 14 个学科视图的**标题与描述** | `src/views/calc/CalcView.vue:439-440`；`en-US.js:116-145`（14 条 `desc`） |
| 415 个模式名（下拉框、弹窗标题、结果标题） | `CalcView.vue:469`、`MultiVarDialog.vue:55`、`ResultDialog.vue:121` |
| 参数弹窗的 186 条唯一字段标签 | `MultiVarDialog.vue:60` |
| 结果字段标签（78） | `src/lib/engine/resultModel.js:138` |
| 数学键盘面板文案 + 6 个分类名 | `src/components/math/MathKeypad.vue:97-157`；`en-US.js:99-102` |
| 缺必填参数的拒绝提示（含 `{list}`/`{how}`） | `src/views/calc/CalcView.vue:363-367` |

**没覆盖到（页面正文仍是中文）**：首页、全部绘图页（React 侧**零 i18n**）、工具页（控制台/搜索/函数工具箱）、设置的 9 个分组、教程与示例库、历史浮层、账号页、AI 面板。
判据：全仓 `t(` 的实际调用点只有 8 个文件 —— `src/App.vue`、`components/math/MathKeypad.vue`、`components/settings/AppearanceGroup.vue`、`components/calc/MultiVarDialog.vue`、`components/calc/ResultDialog.vue`、`views/calc/CalcView.vue`、`lib/engine/resultModel.js`（另有 `lib/plot/plotMath.js` 里一个**同名局部函数**，不是 i18n）。
`node tools/check-ui.mjs` 的对应数字是 `i18n 文案：已用 t() 包裹 50 条`（脚本对 `.vue`/`.js` 的字面量键去重后计数，`tools/check-ui.mjs:421-442`）。

**React 侧没有 i18n 是结构性的**，不是漏做：React 源码里出现 `i18n` 只有一处注释，说明"`resultModel.js` 顶部 import 了 i18n（i18n 又 import vue）"，所以在 React 侧另写了一份：`MFMath.UI.React/src/lib/plotText.ts:7`（`import { ref } from "vue"` 见 `src/lib/i18n/index.js:1`）。

### 5.4 迁移路径与闸门

**路径（固定两步）**：① 在要翻译的那一处把中文原文包一层 `t()`；② 往对应的 `en-*.js` 补一条同键译文。数据层一行都不用改 —— 因为键就是中文原文，没包 `t()` 的地方照旧显示中文，**界面永远不会出现空白或 key**（`src/lib/i18n/index.js:11-27`）。

**闸门**（`npm run check` = `check:types` → `check:signatures` → `check:ui`，`MF_UI/MFMath.UI.Vue/package.json:17`）：

| 守卫 | 断言 | 出处 |
| --- | --- | --- |
| ① 字面量 `t("…")` | 键里含中文的调用，必须在 `EN` 或 `EN_MODES` 里有译文 | `tools/check-ui.mjs:433-441` |
| ② 模式名（`t(m)` 传变量，①盯不到） | `ENGINE_MAP`∪`EXTRA_MAP` 的**每个**键在 `EN_MODES` 里有译文 | `tools/check-ui.mjs:447-452` |
| ③ 弹窗字段标签 | `ENGINE_VAR_SPECS` 的每条唯一标签在 `EN_VARS` 里有译文 | `tools/check-ui.mjs:456-463` |
| ④ 结果标签 | `FIELD_LABELS` 的每个值在 `EN_RESULTS` 里有译文 | `tools/check-ui.mjs:467-471` |

反向**不算问题**（译文多出来只是"别处还没包 `t()`"的迁移中间态，`tools/check-ui.mjs:417`）。改中文原文 = 改 key，漏译的后果是"静默回退成中文"，所以这三道守卫的存在意义就是把这个静默变成构建失败。

---

## 6. 样式

### 6.1 一个设计系统，4 个 `<html>` 属性

| 维度 | 属性 | 取值数 | 取值 | 写属性 | 读回 |
| --- | --- | --- | --- | --- | --- |
| 配色 | `data-theme` | 10 | `glass-light`（默认）`glass-dark` `minimal-light` `minimal-dark` `nord-light` `nord-dark` `paper-light` `sakura-light` `neon-dark` `terminal-dark` | `src/lib/bridge.js:350` | `src/lib/bridge.js:279,285` |
| 圆角与阴影 | `data-shape` | 3 | `glass` `flat` `round` | `src/lib/bridge.js:356` | `:399` |
| 疏密 | `data-density` | 2 | `cozy` `compact` | `src/lib/bridge.js:360` | `:400` |
| 界面字体 | `data-font` | 3 | `sans` `serif` `mono` | `src/lib/bridge.js:364` | `:401` |
| 跟随系统深浅色 | `data-mode` / `data-follow` | — | `dark`/`light`、`1`/`0` | `src/lib/bridge.js:352,370` | `:285` |

初值写死在 HTML 上：`<html lang="zh-CN" data-theme="glass-light">`（`MF_UI/MFMath.UI.Vue/index.html:2`），启动时由 `initTheme()` 补全（`src/main.js:16`）。
配色预览卡是"每张卡自带 `data-theme`、直接用那套主题的真实变量渲染"，所以预览不会与实际走样（`src/App.vue:342-343` 与 `:521-523` 的注释与代码一致）。

### 6.2 Vue 侧

| 事实 | 数字 / 出处 |
| --- | --- |
| 全局样式表 | **只有一份**：`src/styles/theme.css`（815 行），由 `src/main.js:14` 引入 |
| 第三方样式 | `mathlive/static.css`、`mathlive/fonts.css`、`katex/dist/katex.min.css`（`src/main.js:1-3`） |
| 预处理器 | **无** —— 依赖里没有 sass/less/stylus（`MF_UI/MFMath.UI.Vue/package.json:19-43`） |
| 组件私有样式 | 50 个 `.vue` 中 **49 个**用 `<style scoped>`；唯一例外是 `src/components/math/MathField.vue:129`（非 scoped，因为要样式化 `math-field` 这个自定义元素） |
| 无独立 `.css` 文件 | `src/` 下除 `styles/theme.css` 外**没有**其它 `.css`（实测 `src/styles/` 只有 1 个文件） |

`theme.css` 的分段（行号为该段注释头所在行）：配色 10 套 `:root, [data-theme=…]` :26-285 → 形状 :289-326 → 疏密 :329-350 → 字体 :354-375 → 基础 :379-401 → 左侧导航 :402-479 → 右侧 :480-559 → 视图页通用 :560-572 → 基础运算计算器 :573-615 → 代数视图 :616-661 → 通用视图表单 :662-681 → 计算工作区 :682-721 → 结果对话框 :722-777 → 绘图 :778-799 → 控制台 :800-815。
两处硬约束：`--font-mono` 全局固定（"公式与代码永远等宽，不受界面字体影响"，:367-368），紧凑密度下要单独覆盖写死的 padding（:347-350）。

### 6.3 React 侧

| 事实 | 出处 |
| --- | --- |
| 每个组件自带 CSS，共 15 个文件 / 829 行放在 `src/styles/`，由 **15 处**组件 import 引用 | `MFMath.UI.React/src/App.tsx:10`、`PlotPage.tsx:15`、`PlotCanvas.tsx:10` 等 |
| **设计系统不复制**：独立壳直接 import Vue 工程那份 `theme.css` | `MFMath.UI.React/src/main.tsx:13`（`../../MFMath.UI.Vue/src/styles/theme.css`） |
| 内嵌模式（`ReactPlotView`）**不重复**引入全局样式 | 只有 `src/components/plot-react/ReactPlotView.vue:98-106` 一段 scoped 样式；全局样式由 Vue 外壳的 `src/main.js:14` 提供 |
| 绘图 CSS 是从 Vue 版抽出来的 | `ReactPlotView.vue:14`；抽取脚本在 `MFMath.UI.React/tools/extract-styles.mjs`（[README.md](README.md) §8 D6 记过这句文件名没写清工程） |
| 宿主容器必须给高度 | `.react-plot-host { height: 100% }`，否则 React 页的画布列塌成 0（`ReactPlotView.vue:100-106`） |

---

## 7. 冻结的 Vue 绘图组（一句话）

`src/views/plot/` 的 **6 个 `.vue`（2,862 行）** 是**有意冻结的回退资产**：不在构建图、不在路由、不在类型检查、无用例覆盖，`node tools/check-ui.mjs` 打印 `冻结的 Vue 绘图组：6/6 个文件在位，被 import 0 处`（守卫在 `tools/check-ui.mjs:356-388`，白名单同名在那里；决定与理由见 [BUGS.md](../../MF_UI/BUGS.md) B9）。它们引用的 `src/components/plot/*`（6 文件 2,673 行）只被这 6 个文件 import，因此同样不在产品链路上。内部结构见 [PLOT.md](PLOT.md)。

---

## 8. 复跑本文数字的命令

全部在仓库根目录、`pwsh` 下执行（本文实测时间 2026-10-07；行数口径 = `(Get-Content -LiteralPath <file>).Count`，**含空行**）。

1) 各目录文件数与行数（`views`/`components`/`lib` 的二级目录会被拆开）：

```powershell
$root='MF_UI/MFMath.UI.Vue/src'
Get-ChildItem $root -Recurse -File | ForEach-Object {
  $rel = $_.DirectoryName.Substring((Resolve-Path $root).Path.Length).TrimStart('\')
  [pscustomobject]@{ dir = $rel; lines = (Get-Content -LiteralPath $_.FullName).Count }
} | Group-Object dir | Sort-Object Name | ForEach-Object {
  '{0,-26} files={1,-4} lines={2}' -f ($_.Name -replace '^$','(root)'), $_.Count, ($_.Group | Measure-Object lines -Sum).Sum
}
```

2) i18n 与守卫的全部数字（只读，不写任何文件；本项与下一项都在 `MF_UI/MFMath.UI.Vue` 下执行）：

```powershell
node tools/check-ui.mjs
```

3) 导航项与"每条导航项都有归宿"的核对：

```powershell
node -e "import('./src/lib/router/nav.js').then(n=>console.log(n.NAV_GROUPS.map(g=>g.id+':'+g.items.length).join(' '),'total',n.NAV_GROUPS.flatMap(g=>g.items).length))"
```

4) 四张译文表的键数（在 `MF_UI/MFMath.UI.Vue` 下执行，Node ≥ 20，ESM）：

```powershell
node --input-type=module -e "const m=await import('./src/lib/i18n/en-modes.js');const v=await import('./src/lib/i18n/en-vars.js');const r=await import('./src/lib/i18n/en-results.js');const u=await import('./src/lib/i18n/en-US.js');console.log(Object.keys(m.EN_MODES).length,Object.keys(v.EN_VARS).length,Object.keys(r.EN_RESULTS).length,Object.keys(u.EN).length)"
```

⚠ 不要用 `Measure-Object -Line` 数行数：它**不计空行**，会把 `theme.css` 数成 760 而不是 815，把 `src/` 总数从 33,104 数成 31,183。

---

## 9. 已知的文档债

规则：注释/旧文档说 X、代码做 Y 时**以代码为准**。下面每条都给了 `文件:行`；本文档与 [README.md](README.md) §8 是两张独立的表，编号不共用（那边的 D1/D8 覆盖的是 `package.json`、`run-all.ps1`、`vite.config.js:7` 的同类问题，此处不重复登记）。

| # | 位置 | 注释/旧文档说 | 代码/实测做 | 严重度 |
| --- | --- | --- | --- | --- |
| **A1** | `src/router/registry.js:1-3` | 「视图注册表 — Vue 版（对应旧版 MODES / 视图 HTML 映射）／迁移进度：占位视图逐步替换为真实组件」 | 该文件只剩**转出**：`export { NAV_GROUPS, findNav }`（:15）；:5 的 `import HomeView` 与 :8 的 `const lazy` **无人使用**（视图映射实际在 `src/router/index.js:23-86`）。名字与内容已经不符 | 中（会去错文件找"视图注册表"） |
| **A2** | `src/router/index.js:5` | 「registry.js 里的 **25 个**导航项全部有真实组件（**14** 个在 REAL_VIEWS、**13** 个 CALC_ROUTES 走 CalcView）」 | `NAV_GROUPS` 实测 **27** 项（calc 15 / plot 7 / tools 3 / help 2）；覆盖方式是 **13** 个导航项在 `REAL_VIEWS` + **14** 条 `CALC_ROUTES`（§3.3）。括号里的 14/13 恰好写反，且总数少 2 | 中（照它推算会得出"有 2 项没归宿"的错误结论） |
| **A3** | `src/lib/i18n/en-vars.js:4` | 「这些标签来自 `ENGINE_VAR_SPECS`（每个模式的弹窗字段名），共 **381** 个字段、**184** 条唯一标签」 | 实测 `ENGINE_VAR_SPECS`：**139** 个模式 / **400** 个字段 / **186** 条唯一标签（`check-ui.mjs` 第 9 项打印的也是 186）；`EN_VARS` 本身 187 键（多 1 条无害，反向不算问题） | 中（"184"会被当成权威数字抄进别的文档 —— 本文 §5.2 用的是 186） |
| **A4** | `src/router/index.js:49` | 「联网搜索：抓取与解析在宿主（**C#**）」 | 现役宿主是 `MFMath.Host.Rust/`；搜索的宿主侧实现在 `MFMath.Host.Rust/src/main.rs:163`（`SEARCH_SPEC`）与 `handlers.rs:138`（`fn search`）。C# 宿主已废弃（[AGENTS.md](../../AGENTS.md) §2） | 低（与 [README.md](README.md) §8 D1 同类，此处是另一处） |
| **A5** | `tests/cdp-modes-render.mjs:1,5,192` | 「**13** 个学科模式的界面渲染验证」「把 13 个视图都走一遍」「── 13 个学科模式的界面渲染 ──」 | :191 是 `Object.keys(VIEW_CONFIGS)` = **14**（含 `harmonic-analysis`，`src/lib/engine/viewConfigs.js:503`），样本也齐（`tests/fixtures/view-samples.mjs:27`）。**覆盖是 14，只有文案停在 13** | 低（会低估覆盖；该文件在 `tests/` 下，属 B 面，本文只登记不动它） |
| **A6** | `tools/check-ui.mjs:438` | `en-US.js:6` 自述"`npm run check` 会检查每个 `t("…")` 的字面量键**都在这里**（`en-US.js`）存在" | 守卫实际判据是 `!(k in EN) && !(k in EN_MODES)`，而运行期 `t()` 查的是 `EN_MODES+EN_VARS+EN_RESULTS+EN`（`src/lib/i18n/index.js:8`）。即**守卫比运行期更严**：只登记在 `en-vars.js`/`en-results.js` 的字面量会被误报为缺译。方向安全（不会漏放），但口径不一致 | 低（有朝一日报错时要知道是守卫口径，不是真的漏译） |

补充一条**非债**但值得记住的：`src/App.vue:262` 的注释引用 `docs/ACCOUNT.md`，该文档讲的是已废弃的 .NET 实现（[AGENTS.md](../../AGENTS.md) §2 的 R7 债）；现役口径在 [../link/FEATURES.md](../link/FEATURES.md)。

---

## 10. 未证实项（不替它们背书）

**10.1 导航顺序"与原版逐项一致"这一条本次无法验证。**
`src/lib/router/nav.js:17-20` 说顺序以**原版** `MF_UI/i18n.py` 的 `get_calc_modes()` / `get_plot_modes()` 为准，:19 还提到旧网页壳 `MFMath.UI/js/app.js`。
实测：`Test-Path MF_UI/i18n.py` → `False`；`Test-Path MF_UI/MFMath.UI/js/app.js` → `False`（本工作区 `MF_UI/` 下只有 `MFMath.UI.Vue/`、`MFMath.UI.React/`、`BUGS.md`）。
所以本文 §4.1 只保证**表里 27 项的取值与顺序抄自 `nav.js`**（可复跑），**不保证**它与 v1 一致。
验证方式：拿到 v1 源码树（`tools/build-tutorials.mjs:29-31` 说明这类 v1 资产在**另一棵树**里，需用 `MF_TUTORIAL_SRC` 一类环境变量指过去），比对 `get_calc_modes()` / `get_plot_modes()` 的名称与顺序。

**10.2 未跑 `npm run check` 全量，也未跑构建。**
本次只跑了 `node tools/check-ui.mjs`（read-only，exit 0）。`check:types`（`tsc`）、`check:signatures`、`check:examples` **未跑**；`npm run build` 未跑（会写 `dist/`，与 [AGENTS.md](../../AGENTS.md) §4 的独占规矩冲突）。因此"前端现在能构建通过"本文不背书。

**10.3 "31 条路由"是代码推导，不是运行时点数。**
`1 + 27 + 3`（§3.1）由 `src/router/index.js:88-134` 的循环与三次 `routes.push` 推出；没有在真宿主里读 `router.getRoutes().length`。验证方式：页面里没有暴露 `router` 实例，实际可行的是在 `tests/cdp-window-shell.mjs` 那类套件里加一条 `getRoutes()` 断言（需真宿主，本文未做）。

**10.4 页面正文的中文覆盖率没有机器判据。** 本文只说"这 8 个文件之外没有 `t()` 调用点"（§5.3），这是**调用点**统计，不是"未翻译的中文字符串条数"；全仓不存在"中文硬编码条数"的守卫（`tools/check-ui.mjs` 只做上述 4 条正向对账）。所以"页面正文仍中文"是定性结论，量级未证实。

**10.5 §2.2 的"最大文件"只对 Vue 的 `src/` 成立** —— `MF_UI/MFMath.UI.Vue/src` 之外的文件（如 `tests/`、React 的 `plot/`）本文未参与该排序。
