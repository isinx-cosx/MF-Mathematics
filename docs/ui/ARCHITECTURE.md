# 前端：目录分层、路由与导航、i18n、样式

> 本文回答：Vue 壳内部如何分层、路由与导航表如何组织、国际化覆盖范围与扩展方式、样式如何组织。
>
> 与同层文档的分工：
> - [README.md](README.md) —— 两个工程、共享机制、构建链、测试资产；
> - [ENGINE-BINDING.md](ENGINE-BINDING.md) —— 界面与引擎的接线（本文只涉及模式名在何处渲染）；
> - [PLOT.md](PLOT.md) —— React 绘图组与冻结的 Vue 绘图组；
> - [CHECKS.md](CHECKS.md) —— 构建期检查与守卫。

## 1. 分层总览

产品外壳是 Vue 工程（`MF_UI/MFMath.UI.Vue/`）。`MF_UI/MFMath.UI.React/` 只提供绘图页。

| 层 | 位置 | 职责 |
| --- | --- | --- |
| 入口 | `index.html` → `src/main.js` | 创建应用、挂载路由、初始化主题与错误上报 |
| 壳组件 | `src/App.vue` | 侧栏导航、顶栏、内容区 `<router-view>`、状态栏、常驻浮层 |
| 路由 | `src/router/index.js`、`src/router/registry.js` | 路由表与导航数据转出 |
| 页面 | `src/views/**` | 路由落点的页面组件 |
| 组件 | `src/components/**` | 按域拆分的可复用组件 |
| 逻辑 | `src/lib/**` | 引擎桥、绘图、i18n、设置、教程等非组件代码 |
| 样式 | `src/styles/theme.css` | 唯一全局样式表 |
| 类型 | `src/types/webview.d.ts` | 宿主对象的 TS 声明 |

三个唯一入口：

| 关注点 | 唯一入口 | 定位命令 |
| --- | --- | --- |
| 挂载与全局样式 | `src/main.js` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/main.js -Pattern "theme.css"` |
| 导航数据 | `src/lib/router/nav.js` 的 `NAV_GROUPS` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/router/nav.js -Pattern "NAV_GROUPS"` |
| 路由表 | `src/router/index.js` 的 `routes` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "const routes"` |

## 2. 目录规模

一级目录文件数（由命令逐一计数）：

| 目录 | 文件数 | 内容 |
| --- | --- | --- |
| `src/`（根） | 2 | `App.vue`、`main.js` |
| `src/views/` | 16 | 页面组件 |
| `src/components/` | 33 | 可复用组件（含 1 个 React 桥） |
| `src/lib/` | 51（43 `.js` + 7 `.ts` + 2 根文件） | 非组件代码 |
| `src/router/` | 2 | `index.js`、`registry.js` |
| `src/styles/` | 1 | `theme.css` |
| `src/types/` | 1 | `webview.d.ts` |

`src/views/` 二级拆分：

| 子目录 | 文件数 |
| --- | --- |
| `calc/` | 2 |
| `tools/` | 3 |
| `tutorial/` | 2 |
| `plot/`（冻结，见 §6） | 6 |
| `account/`、`settings/`、根 `HomeView.vue` | 各 1 |

`src/components/` 二级拆分（`tools/` 为空目录）：

| 子目录 | 文件数 |
| --- | --- |
| `settings/` | 10 |
| `plot/`（冻结组件） | 6 |
| `ai/`、`math/` | 各 4 |
| `calc/`、`tutorial/` | 各 3 |
| `console/`、`history/`、`plot-react/` | 各 1 |

`src/lib/` 二级拆分（根文件为 `bridge.js`、`push.js`）：

| 子目录 | 文件数 |
| --- | --- |
| `ai/` | 9（含生成物 `engine-signatures.json`） |
| `engine/`、`plot/` | 各 7 |
| `i18n/` | 5 |
| `settings/` | 4 |
| `math/`、`tutorial/` | 各 3 |
| `console/`、`workspace/` | 各 2 |
| `account/`、`diagnostics/`、`history/`、`keyboard/`、`router/`、`search/`、`update/` | 各 1 |

## 3. 路由

### 3.1 生成规则

| 事实 | 定位命令 |
| --- | --- |
| 首页单独一条 `/` → `HomeView` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern 'path: "/"'` |
| 其余导航项由 `NAV_GROUPS` 循环生成 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "NAV_GROUPS"` |
| 路由名由路径推导 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "slice\(1\)"` |
| 历史模式 `createWebHashHistory()` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "createWebHashHistory"` |

`NAV_GROUPS` 共 4 组 27 项（calc 15、plot 7、tools 3、help 2），由命令核对：

```powershell
node --input-type=module -e 'const n=await import("./src/lib/router/nav.js");console.log(n.NAV_GROUPS.flatMap(g=>g.items).length)'
```

3 条显式路由不在导航中：`/tutorial/:id`、`/settings`、`/account`。后两条由 `routes.push` 手写注册，因为它们不在 `NAV_GROUPS` 里，而循环只覆盖导航项。

### 3.2 三张映射表

| 表 | 职责 | 定位命令 |
| --- | --- | --- |
| `REAL_VIEWS` | 路由 → 独立组件的静态 import（15 键） | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "REAL_VIEWS"` |
| `CALC_ROUTES` | 走同一个 `CalcView.vue` 的学科路由（14 条） | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "CALC_ROUTES"` |
| `REACT_PAGES` | 绘图路由 → React 页面键（7 条） | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "REACT_PAGES"` |

`CalcView.vue` 按路由末段从 `VIEW_CONFIGS` 读取配置。`VIEW_CONFIGS` 共 14 个键（14 个学科页），由命令核对：

```powershell
node --input-type=module -e 'const v=await import("./src/lib/engine/viewConfigs.js");console.log(Object.keys(v.VIEW_CONFIGS).length)'
```

## 4. 导航表

`NAV_GROUPS` 定义在 `src/lib/router/nav.js`，是 Vue 与 React 共用的零依赖模块。该文件禁止 import Vue 或访问 DOM 全局。

分组与项数：

| 分组 | `id` | 项数 | 路由前缀 |
| --- | --- | --- | --- |
| 计算模式 | `calc` | 15 | `/calc/` |
| 绘图模式 | `plot` | 7 | `/plot/` |
| 工具 | `tools` | 3 | `/tools/` |
| 帮助 | `help` | 2 | `/tutorial`、`/examples` |

两个渲染点共用同一份数据：

| 外壳 | 渲染方式 | 定位命令 |
| --- | --- | --- |
| 产品壳（Vue） | `v-for` 遍历 `NAV_GROUPS`，经 `t()` 翻译 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/App.vue -Pattern "NAV_GROUPS"` |
| React dev 壳 | `NAV_GROUPS.map(...)` 渲染侧栏 | `Select-String -Path MF_UI/MFMath.UI.React/src/App.tsx -Pattern "NAV_GROUPS"` |

## 5. i18n

### 5.1 机制

以中文原文为键的最小实现。

| 设计点 | 实现 | 定位命令 |
| --- | --- | --- |
| 语言表 | `zh-CN`、`en-US` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/i18n/index.js -Pattern "LOCALES"` |
| 持久化键 | `localStorage["mf.lang"]` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/i18n/index.js -Pattern "STORE_KEY"` |
| 取译文 `t(key, params)` | 中文环境原样返回键；英文环境查表，查不到回退中文 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/i18n/index.js -Pattern "export function t"` |
| 合并顺序 | `DICT = { ...EN_MODES, ...EN_VARS, ...EN_RESULTS, ...EN }` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/i18n/index.js -Pattern "const DICT"` |

### 5.2 四张译文表

| 文件 | 导出 | 键数 | 覆盖 |
| --- | --- | --- | --- |
| `en-US.js` | `EN` | 101 | 外壳文案（分组标题、导航条目、顶栏、外观浮层、键盘面板文案、视图描述、缺参提示） |
| `en-modes.js` | `EN_MODES` | 415 | 引擎模式显示名 |
| `en-vars.js` | `EN_VARS` | 187 | 参数弹窗字段标签 |
| `en-results.js` | `EN_RESULTS` | 78 | 结果面板字段标签 |

键数由命令核对：

```powershell
node --input-type=module -e 'const m=await import("./src/lib/i18n/en-modes.js");const v=await import("./src/lib/i18n/en-vars.js");const r=await import("./src/lib/i18n/en-results.js");const u=await import("./src/lib/i18n/en-US.js");console.log(Object.keys(m.EN_MODES).length,Object.keys(v.EN_VARS).length,Object.keys(r.EN_RESULTS).length,Object.keys(u.EN).length)'
```

### 5.3 覆盖范围

`t()` 的实际调用点集中在 8 个文件：`App.vue`、`MathKeypad.vue`、`AppearanceGroup.vue`、`MultiVarDialog.vue`、`ResultDialog.vue`、`CalcView.vue`、`resultModel.js`，另有 `plotMath.js` 里的同名局部函数（非 i18n）。`check-ui.mjs` 的对应计数是「已用 t() 包裹 50 条」。

未覆盖范围：首页、全部绘图页（React 侧零 i18n）、工具页、设置分组、教程与示例库、历史浮层、账号页、AI 面板。

### 5.4 扩展方式

扩展翻译是固定两步：

1. 在目标位置把中文原文包一层 `t()`；
2. 向对应的 `en-*.js` 补一条同键译文。

数据层无需改动：键即中文原文，未包 `t()` 的位置仍显示中文，界面不出现空白或 key。构建期守卫把漏译从静默回退变成失败（见 [CHECKS.md](CHECKS.md)）。

## 6. 样式

### 6.1 设计系统

| 维度 | `<html>` 属性 | 取值数 | 写属性 | 读回 |
| --- | --- | --- | --- | --- |
| 配色 | `data-theme` | 10 | `applyAppearance` | `currentTheme` |
| 圆角与阴影 | `data-shape` | 3 | 同上 | `currentAppearance` |
| 疏密 | `data-density` | 2 | 同上 | `currentAppearance` |
| 界面字体 | `data-font` | 3 | 同上 | `currentAppearance` |
| 跟随系统 | `data-mode` / `data-follow` | — | 同上 | `currentMode` |

外观逻辑集中在 `src/lib/bridge.js`（`THEME_LIST`、`SHAPE_LIST`、`DENSITY_LIST`、`FONT_LIST` 与 `applyAppearance`）。

### 6.2 Vue 侧

| 事实 | 定位命令 |
| --- | --- |
| 全局样式表唯一：`src/styles/theme.css` | `Get-ChildItem MF_UI/MFMath.UI.Vue/src/styles -File` |
| 无预处理器 | `Select-String -Path MF_UI/MFMath.UI.Vue/package.json -Pattern "sass|less|stylus"`（无输出） |
| 第三方样式 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/main.js -Pattern "mathlive|katex"` |

### 6.3 React 侧

| 事实 | 定位命令 |
| --- | --- |
| 15 个 CSS 文件在 `src/styles/`，由组件 import | `Get-ChildItem MF_UI/MFMath.UI.React/src/styles -File` |
| 独立壳直接 import Vue 工程的 `theme.css` | `Select-String -Path MF_UI/MFMath.UI.React/src/main.tsx -Pattern "theme.css"` |
| 内嵌模式不重复引入全局样式 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue -Pattern "react-plot-host"` |

## 7. 冻结的 Vue 绘图组

`src/views/plot/` 的 6 个 `.vue` 是有意冻结的回退资产，不在构建图、不在路由、不在类型检查、无用例覆盖。`check-ui.mjs` 的守卫输出「冻结的 Vue 绘图组：6/6 个文件在位，被 import 0 处」。白名单在 `tools/check-ui.mjs` 的 `FROZEN_VUE_PLOT_FILES`。这些文件引用的 `src/components/plot/*`（6 文件）只被这 6 个文件 import，同样不在产品链路。

## 8. 复跑命令

| 目标 | 命令（工作目录 `MF_UI/MFMath.UI.Vue`） |
| --- | --- |
| 守卫输出与 i18n、键盘、用例计数 | `node tools/check-ui.mjs` |
| 导航分组与项数 | `node --input-type=module -e 'const n=await import("./src/lib/router/nav.js");console.log(n.NAV_GROUPS.map(g=>g.id+":"+g.items.length).join(" "))'` |
| 四张译文表键数 | 见 §5.2 命令 |
