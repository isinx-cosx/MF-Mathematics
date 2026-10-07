# 前端：两个工程、构建链与测试资产

> **本文只回答一个问题：前端由哪两个工程组成、怎么构建、测试资产有哪些。**
>
> 与同层其它文档的分工：
> - [ARCHITECTURE.md](ARCHITECTURE.md) —— Vue 壳内部的分层（`views` / `components` / `lib`）、路由与导航表、i18n、样式；
> - [PLOT.md](PLOT.md) —— 6 个 React 绘图页与共享 plot lib 的内部结构，以及被冻结的 Vue 绘图组；
> - [ENGINE-BINDING.md](ENGINE-BINDING.md) —— `ENGINE_MAP` / `viewConfigs` / `asyncPolicy` 怎么把界面接到引擎；
> - [CHECKS.md](CHECKS.md) —— 各道构建闸门断言什么、以及"守卫必须验证过会失败"的规矩；
> - [TOOLS.md](TOOLS.md) —— 控制台 / 函数工具箱 / 历史 / 搜索页；本文只负责它们的**构建归属与用例归属**。
>
> 前端与宿主之间那条缝（含"为什么要同步桥"）见 [`../link/README.md`](../link/README.md)；
> 宿主侧"照着跑就能复现"的验收步骤见 [`../../MFMath.Host.Rust/docs/ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)；
> 谁在做什么、改哪一面的规矩见 [`../../AGENTS.md`](../../AGENTS.md) §2。

**核对时间**：2026-10-07 10:52（+08:00）首核，**10:54 因发现并行改动而逐条重核**，本机 Windows（见 §8.1）。
本文的"实测"= 本次会话真的跑过那条命令，输出抄在表格里；没跑过的（尤其 `npm run build`）明确标注。
**未跑 `npm run build`**：它会重建 `dist/`，而 `dist/` 与宿主 `wwwroot` 是同一时刻只有一个人能动的独占资源（[`../../AGENTS.md`](../../AGENTS.md) §4）。所以 §4 里除"现存产物清单"外，其余全部是**读配置**得出，不是构建日志。

---

## 1. 两个工程一览

| | **Vue 壳** | **React 绘图组** |
| --- | --- | --- |
| 路径 | `MF_UI/MFMath.UI.Vue/` | `MF_UI/MFMath.UI.React/` |
| `name` | `mfmath-ui-vue` | `mfmath-ui-react-plot` |
| 出处 | `MF_UI/MFMath.UI.Vue/package.json:2` | `MF_UI/MFMath.UI.React/package.json:2` |
| 版本 / `private` | `0.1.0` / `true` | `0.1.0` / `true` |
| 出处 | `package.json:3-4` | `package.json:3-4` |
| 进构建图？ | **是** —— 唯一的产物来源，宿主只读它的 `dist` | **否** —— 它的 `dist` 没有任何消费方（见 §4.3） |
| 独立入口 | `index.html:10` → `/src/main.js` | `index.html:10` → `/src/main.tsx`（自己的 dev 壳，非产品外壳） |
| 框架依赖 | `vue ^3.5.13`、`vue-router ^4.5.0`、`react ^19.3.0`、`react-dom ^19.3.0` | `react ^19.2.0`、`react-dom ^19.2.0` |
| 出处 | `package.json:32-35` | `package.json:16-17` |

**同一个 Vue 工程里同时装了 react 与 react-dom**，这不是误装：`dist` 里的 React 绘图分块是由 **Vue 那次构建**打出来的（`MF_UI/MFMath.UI.Vue/vite.config.js:28` 的 `react()` 插件）。

Vue 工程的依赖版本有一个硬约束记在配置注释里：`@vitejs/plugin-react` 必须是 `^4.x`，因为 vite 是 `^6.0.7`，而插件的 v6 要求 vite ^8（`vite.config.js:13-14`，`package.json:40`、`package.json:43`）。

### 1.1 规模（实测，2026-10-07 10:52）

| 位置 | 数量 | 怎么数的 |
| --- | --- | --- |
| `MFMath.UI.Vue/src/views/**/*.vue` | 16 | `Get-ChildItem ... -Recurse -Filter *.vue` |
| `MFMath.UI.Vue/src/components/**/*.vue` | 33 | 同上 |
| `MFMath.UI.Vue/src/lib/**/*.js` | 43 | `Get-ChildItem ... -Filter *.js` |
| `MFMath.UI.Vue/src/lib/**/*.ts` | 7 | `Get-ChildItem ... -Filter *.ts`（全部在 `src/lib/ai/`） |
| `MFMath.UI.React/src/**/*.tsx` | 16 | `Get-ChildItem ... -Recurse -Filter *.tsx` |
| `MFMath.UI.React/src/**/*.ts` | 6 | 同上 |
| `MFMath.UI.React/src/**/*.css` | 15 | 同上 |
| `MFMath.UI.React/src/plot/` | 13 个文件（其中 6 个是 `*Page.tsx`） | `Get-ChildItem src/plot -File` |

`src/lib` 下 16 个子目录加两个根文件：`bridge.js`、`push.js`（实测 `Get-ChildItem -Directory` / `-File`）。

---

## 2. Vue 壳与内嵌 React 绘图组的关系

**一句话**：整组绘图页归 React，其余页面仍留 Vue；React 页**挂在 Vue 路由上**，由一个 Vue 组件负责挂载/卸载。

### 2.1 路由 → 组件

| 路由 | 页面键 | React 组件 |
| --- | --- | --- |
| `/plot/2d` | `2d` | `PlotPage` |
| `/plot/polar` | `polar` | `PlotPage`（同一个组件，靠 `gridMode` 区分） |
| `/plot/vector` | `vector` | `PlotVectorPage` |
| `/plot/fractal` | `fractal` | `PlotFractalPage` |
| `/plot/3d` | `3d` | `Plot3DPage` |
| `/plot/complex` | `complex` | `PlotComplexPage` |
| `/plot/geometry` | `geometry` | `PlotGeometryPage` |

- 路由 → 组件的绑定：`src/router/index.js:37,40,42,43,44,45,46`（7 条全部指向 `../components/plot-react/ReactPlotView.vue`）；路由表由 `NAV_GROUPS` 生成并写入 `meta.reactPage`：`src/router/index.js:92-106`。
- 路由 → 页面键的映射表 `REACT_PAGES`：`src/router/index.js:68-76`（7 条）。
- 页面键 → 组件加载器 `LOADERS`：`src/components/plot-react/ReactPlotView.vue:28-36`（7 个键 → 6 个组件，`2d`/`polar` 共用 `PlotPage`）。
- 组件源码路径是**跨工程的相对路径**：`ReactPlotView.vue:29-35` 写的是 `../../../../MFMath.UI.React/src/plot/PlotPage`。

### 2.2 挂载方式（Vue 里跑 React）

| 步骤 | 实现 | 出处 |
| --- | --- | --- |
| 动态 `import()` 分块 | 每个页面键一次 `await loader()` | `ReactPlotView.vue:58-66` |
| 用 `createRoot` 挂到 div | `root = createRoot(host.value)` → `root.render(createElement(mod.default, props))` | `ReactPlotView.vue:76-77` |
| 换页**重挂** | `route.fullPath` 变化 → 先 `root.unmount()` 再挂新的 | `ReactPlotView.vue:81-83`、`52-56` |
| 卸载收尾 | `onBeforeUnmount` 里 `disposed = true` + `seq++` + `unmount()` | `ReactPlotView.vue:84-91` |
| 竞态护栏 | 挂载序号 `my !== seq` 就放弃这次挂载 | `ReactPlotView.vue:51,68` |
| 宿主容器必须给高度 | `.react-plot-host { height: 100% }`，否则画布列塌成 0 | `ReactPlotView.vue:98-106` |

**为什么必须重挂、不能只改 prop**：React 页里的模式/状态是 `useState` 初值，只改 prop 不生效；不卸载则 `ResizeObserver` 与采样循环会在离开后继续跑（`ReactPlotView.vue:18-20`）。

`routePath` 是**工作区与导出图片的必需 prop**：`/plot/2d` 与 `/plot/polar` 也必须传，因为工作区按 `route.path` 分页存（`ReactPlotView.vue:69-75`；对应 [BUGS.md](../../MF_UI/BUGS.md) B14/B15）。

### 2.3 与 React 工程自己那个壳的关系（容易看错的一处）

`MFMath.UI.React/src/App.tsx` 里有一份 `MIGRATED_PLOTS = new Set(["/plot/2d", "/plot/polar"])`（`App.tsx:30`），即"只迁了 2 页"。**这份集合不是产品外壳的真相**：

| 谁 | 覆盖的绘图页 | 证据 |
| --- | --- | --- |
| **产品外壳**（Vue 路由 + `ReactPlotView`） | **7 条** | `src/router/index.js:37-46` + `REACT_PAGES` `:68-76` + `LOADERS` `ReactPlotView.vue:28-36` |
| React 工程自己的 dev 壳（`MFMath.UI.React/index.html`） | 2 条 | `App.tsx:30` |

`ReactPlotView.vue:6-7` 的注释把后者当成了前者（已记入 §8 文档债 D5）。

### 2.4 被冻结的 Vue 绘图组

Vue 侧旧绘图页仍在磁盘上、但**已不在构建图与路由里**：`src/views/plot/` 共 6 个 `.vue`（`PlotView.vue`、`Plot3DView.vue`、`PlotComplexView.vue`、`PlotFractalView.vue`、`PlotGeometryView.vue`、`PlotVectorView.vue`）。这是**有意冻结的回退资产**，不是遗漏（[BUGS.md](../../MF_UI/BUGS.md) B9）。

实测守卫输出（`node tools/check-ui.mjs`，2026-10-07 10:52）：

```
冻结的 Vue 绘图组    ：6/6 个文件在位，被 import 0 处
```

`check-ui.mjs:387` 会对"有人 import 已冻结的 `src/views/plot/*`"直接报错。

---

## 3. `@shared/*` 怎么跨两个工程共享

**结论：只有 React 侧的源码写 `@shared/*`，它被解析到 Vue 工程的 `src/lib`。** 于是"两个工程"在运行期共用**同一份模块实例**，不是两份拷贝。

| 谁在解析 | 配置 | 出处 |
| --- | --- | --- |
| Vite（**Vue 那次构建**，编译 React 源码时） | `alias: { "@shared": <Vue>/src/lib }` | `MF_UI/MFMath.UI.Vue/vite.config.js:40-44` |
| Vite（React 工程独立 `dev`/`build` 时） | `alias: { "@shared": ../MFMath.UI.Vue/src/lib }` | `MF_UI/MFMath.UI.React/vite.config.ts:13,19` |
| `tsc`（React 的 `check:types`） | `paths: { "@shared/*": ["../MFMath.UI.Vue/src/lib/*"] }` | `MF_UI/MFMath.UI.React/tsconfig.json:24-25` |
| dev 期文件系统白名单（Vue） | `server.fs.allow: [".."]`（React 源码在工程外一层） | `MF_UI/MFMath.UI.Vue/vite.config.js:18,52` |
| dev 期文件系统白名单（React） | `server.fs.allow: [".."]` | `MF_UI/MFMath.UI.React/vite.config.ts:14,22` |

### 3.1 为什么必须指到同一份文件

配置注释给了理由，且与代码一致：React 侧写的是 `@shared/plot/*`、`@shared/bridge.js`，必须指到**本工程的 `src/lib`**，"必须是同一份文件（同一个模块实例），否则 plotMath 的注入钩子、引擎桥会各有一份，行为会漂移"（`vite.config.js:15-17`）。

### 3.2 共享面有多大（实测）

| 事实 | 数字 | 怎么数的 |
| --- | --- | --- |
| React `src/**` 里 `@shared/` 的 import 命中 | **48** | `grep`（`@{ts,tsx,js}`，路径 `MF_UI/MFMath.UI.React/src`） |
| Vue `src/**` 里 `@shared` 的字面出现 | **4**，且**全是注释**，没有一处 import | `grep`（`@{js,ts,vue}`，路径 `MF_UI/MFMath.UI.Vue/src`） |

所以 Vue 自己的源码**不**用 `@shared`（它直接用相对路径引 `src/lib`）；`@shared` 的存在意义就是让**跨工程的 React 源码**够到这份共享逻辑。

> ⚠ 这也是取证陷阱的来源：只 `grep MFMath.UI.Vue/src` 会得出"没人用"的错误结论 —— [BUGS.md](../../MF_UI/BUGS.md) §0.1 第 1 条就是踩了这个（跨工程共享逻辑的项目，取证必须覆盖两个工程）。

### 3.3 哪些东西被共享（入口举例）

| 共享模块 | 谁在用 | 出处 |
| --- | --- | --- |
| `@shared/bridge.js`（WebView2 引擎桥） | React 各绘图页、`main.tsx` | `PlotPage.tsx:9`、`main.tsx:5` |
| `@shared/plot/plotMath.js` | `PlotPage.tsx:7`，并在 `main.tsx:4` 注入钩子 | — |
| `@shared/plot/view.js`（视口映射） | `PlotPage.tsx:10`、`GeometryCanvas.tsx:6` | — |
| `@shared/plot/sampling.js` | `usePlotSampling.ts:4`、`Plot3DPage.tsx:7` | — |
| `@shared/plot/exportImage.js` | 6 个绘图页 | `PlotPage.tsx:11`、`Plot3DPage.tsx:9` 等 |
| `@shared/engine/asyncPolicy.js` | `PlotFractalPage.tsx:3`、`PlotComplexPage.tsx:3` | — |
| `@shared/router/nav.js`（**导航数据只有一份**） | `App.tsx:7` | 文件自述"两个工程都会 import 它"：`src/lib/router/nav.js:4` |
| `@shared/workspace/store.js` | `MFMath.UI.React/src/lib/plotWorkspace.ts:22` | — |

导航表曾经是**手抄两份并已漂移过**，现在收口到 `src/lib/router/nav.js`（`App.tsx:22-24`、`src/router/registry.js:12`）。

---

## 4. 构建链与产物

### 4.1 Vue（唯一的产物来源）

```powershell
npm run build --prefix MF_UI/MFMath.UI.Vue
```

| 步骤 | 命令/实现 | 出处 |
| --- | --- | --- |
| 打包 | `vite build` | `MF_UI/MFMath.UI.Vue/package.json:9` |
| 清字体冗余 | `node scripts/prune-fonts.mjs` | 同上（`&&` 串联） |
| 只要打包、别清字体 | `npm run build:raw` = `vite build` | `package.json:10` |
| 输出目录 | `dist/`，`emptyOutDir: true` | `vite.config.js:54-58` |
| 编译目标 | `chrome110` | `vite.config.js:57` |
| 路径基数 | `base: "./"` —— 保证经虚拟主机/file 加载时资源可用 | `vite.config.js:45-46` |
| dev 端口 | `127.0.0.1:5173`，`strictPort: true` | `vite.config.js:47-53` |

**`prune-fonts.mjs` 做什么**：KaTeX/MathLive 各带 `woff2`/`woff`/`ttf` 三种格式，WebView2 只命中 `woff2`，于是删掉后两种。该脚本自称把 `wwwroot` 从 **2.44 MB 降到 1.66 MB**（`scripts/prune-fonts.mjs:2,5-10`）—— ⚠ 这个数字**本次未复跑 `npm run build` 验证**，属脚本自述。删除规则是"按字体族+字重归组、只有该组确有 `woff2` 才删"（`prune-fonts.mjs:16-19`）；`KaTeX_Size3` 的 `.woff`+`.ttf`（11.7 KB）**是刻意保留**的，别当漏删（`prune-fonts.mjs:21-25`）。回归方式是 `tests/cdp-font-load.mjs`（`prune-fonts.mjs:27-28`）。

### 4.2 `dist` → 宿主 `wwwroot` 的三条路径

```
MF_UI/MFMath.UI.Vue/src/**  ──vite build──▶  MF_UI/MFMath.UI.Vue/dist/  ──┬─▶ ① 嵌进 exe（tauri frontendDist）
                                                                          ├─▶ ② cargo build 时 → target/<profile>/wwwroot
                                                                          └─▶ ③ tools/sync-wwwroot.mjs → 指定 wwwroot
                                                                                              │
                                          宿主读 wwwroot ──▶ https://mfmath.local/index.html ◀─┘
```

| # | 机制 | 出处 |
| --- | --- | --- |
| ① | `build.frontendDist = "../MF_UI/MFMath.UI.Vue/dist"`（嵌入，**兜底**：没有 `wwwroot` 时仍能起来） | `MFMath.Host.Rust/tauri.conf.json:7`；兜底语义见 `MFMath.Host.Rust/src/main.rs:298-299` |
| ② | `build.rs` 把 `dist` 镜像到 `<exe 同目录>/wwwroot`，失败只警告 | `MFMath.Host.Rust/build.rs:113-118`（`copy_tree` 定义在 `:154`） |
| ③ | `node tools/sync-wwwroot.mjs`，默认 `target/debug/wwwroot` | `MFMath.Host.Rust/tools/sync-wwwroot.mjs:38` |

`sync-wwwroot.mjs` 的参数（`sync-wwwroot.mjs:26-39`）：`--profile release` → `target/release/wwwroot`；`--dest <wwwroot 目录>`；`--exe <exe 路径>` → 该 exe 同目录的 `wwwroot`。

**两条必须知道的护栏**（都是踩过的坑，写在脚本里）：

1. 它会**先清空目标目录**再拷（`sync-wwwroot.mjs:68`）。所以 `--dest` 的语义是"`wwwroot` 目录本身"，与 `sync-engine.mjs --dest`（"exe 所在目录"）**不是一回事**；把同一个目录传给两个脚本，第二个会把刚拷进去的引擎 DLL 乃至宿主 exe 一起删光（`sync-wwwroot.mjs:50-55`）。
2. 目标里若能看到 `mfmath-host-rust.exe` / `MFMath.exe` 就直接拒绝执行（`sync-wwwroot.mjs:56-66`）。

宿主侧落点：`UI_HOST = "mfmath.local"` 与 `UI_URL = "https://mfmath.local/index.html"`（`MFMath.Host.Rust/src/main.rs:309-310`）；`wwwroot_dir()` 先看环境变量、否则用 exe 同目录的 `wwwroot`（`main.rs:300-306`）。前端**改了只要重拷 `dist`、不必重编 Rust**（`sync-wwwroot.mjs:8-9`）。

`sync-wwwroot.mjs` 找不到 `dist/index.html` 时**直接 exit 1**并打印该跑哪条命令，不让宿主静默退回内嵌资产（`sync-wwwroot.mjs:42-48`）。

### 4.3 现存产物（实测，未重跑构建）

| 产物 | 内容 | 怎么数的 |
| --- | --- | --- |
| `MF_UI/MFMath.UI.Vue/dist/` | 73 个文件（`index.html` 0.4 KB + `assets/` 72 个） | `Get-ChildItem -Recurse -File` / `dist/assets` |
| `MF_UI/MFMath.UI.React/dist/` | 62 个文件 | `Get-ChildItem -Recurse -File` |

**React 的 `dist` 没有消费方。** 全仓 `grep MFMath.UI.React` 只命中 Vue 源码里那 7 行跨工程 `import`（`ReactPlotView.vue:29-35`）和几处注释（`vite.config.js:18,51`、`src/lib/router/nav.js:5`）；没有任何配置把 `MFMath.UI.React/dist` 当成来源。宿主只读 Vue 的 `dist`（`tauri.conf.json:7`、`build.rs:113`、`sync-wwwroot.mjs:24`）。**所以 React 工程的 `npm run build`（`MFMath.UI.React/package.json:9`）只服务于它自己的 dev 壳，产品链路上不需要它。**

---

## 5. 测试资产

**全部集中在 `MF_UI/MFMath.UI.Vue/tests/`**（React 工程只有一个自己的探针，见 §5.4）。目录共 **63 个文件** = 62 个 `.mjs` + `run-all.ps1`（实测 `Get-ChildItem tests/*`）。

### 5.1 按命名前缀数（实测，2026-10-07 10:52）

| 类别 | 个数 | 判据 |
| --- | --- | --- |
| `cdp-*.mjs`（需要真宿主窗口） | **48** | `(Get-ChildItem tests/cdp-*.mjs).Count` |
| `unit-*.mjs`（纯 Node，假桥，不需要宿主） | **4** | `(Get-ChildItem tests/unit-*.mjs).Count` |
| `fake-*.mjs`（本地假端点，被 cdp-* 起） | **3** | `(Get-ChildItem tests/fake-*.mjs).Count` |
| 其它探针脚本 | **8** | 63 − 48 − 4 − 3 |
| 合计 `.mjs`（`tests/` 顶层） | **63** | `(Get-ChildItem tests/*.mjs).Count` |

> ⚠ **这两个数字变动过**：本文首次核对时是 3 个 `unit-*` / 合计 62；写这批文档期间 B 面落了
> `unit-history-store.mjs`，所以现在是 **4 / 63**（复核时间 2026-10-07 11:1x）。
> **引用前请重跑上面表里的命令** —— 这也是 [`../DECISIONS.md`](../DECISIONS.md) D-010 那条
> "跑批前先确认没有别人在动"的同一个道理：**数字有主人，也有时刻**。

4 个 `unit-*`：`unit-result-model`、`unit-sse`、`unit-markdown`、`unit-history-store`（前三个在 `run-all.ps1:36,39,41`；第四个由 B 面新增）。

3 个 `fake-*`：`fake-ai-server.mjs`、`fake-search-server.mjs`、`fake-account-server.mjs`（分别供 `cdp-ai` / `cdp-search` / `cdp-account` + `cdp-update` 用，`run-all.ps1:89,94,99,104`）。

8 个其它探针（**不在套件里，要手跑**）：

| 脚本 | 干什么（按它自己的用法） |
| --- | --- |
| `audit-modes.mjs` | 逐模式审计 —— **它在套件里**（`run-all.ps1:108`），只是名字不带 `cdp-`/`unit-` 前缀 |
| `reset-appearance.mjs` | 跑套件前把 localStorage 里的外观复位（`run-all.ps1:177-181` 自动调用） |
| `engine-paths.mjs` | 4 处硬编码绝对路径的统一解析出口（[BUGS.md](../../MF_UI/BUGS.md) B8） |
| `dumpmap.mjs`、`unmapped-report.mjs`、`dupmodes.mjs` | 引擎映射表 / 未映射项 / 重名模式的排查工具 |
| `showfn.mjs` | 从引擎源码里看某个函数 |
| `probe-implicit.mjs` | 隐函数相关的单点探针 |

> `audit-modes` 这个名字容易被上面那句"8 个其它探针"误导，所以单列一行：**它被登记进套件**，实测登记表 **53** 项 = 48 `cdp-*` + 4 `unit-*` + 1 `audit-modes`（复核 2026-10-07 11:1x）。

### 5.2 登记表：`tests/run-all.ps1`

| 事实 | 值 | 出处 |
| --- | --- | --- |
| 输出协议 | 每个脚本打印一行 `RESULT|<name>|<pass>|<fail>`（ASCII） | `run-all.ps1:13`，解析正则 `:190` |
| 登记项数（实测解析 `$tests` 数组） | **52** = 48 cdp + 3 unit + `audit-modes` | `run-all.ps1:35-114` |
| 漏登记检查 | `check-ui.mjs` 断言"磁盘上每个 `tests/cdp-*.mjs` 都登记过"，`NOT_IN_SUITE` 白名单当前为空 | `tools/check-ui.mjs:480-509,491` |
| 实测输出 | `端到端用例          ：cdp-* 48 个，已登记 48 个` | 本次跑 `node tools/check-ui.mjs`，`EXIT=0` |
| 必须保留 UTF-8 **BOM** | 否则 PowerShell 5.1 按 ANSI 解码，中文注释吞掉下一行、`$tests` 数组直接语法错 | `run-all.ps1:7-10` |
| 顺序有约束 | `cdp-engine-coverage` **必须放最后**（它会走遍每个视图点一次计算，污染后续断言） | `run-all.ps1:109-113` |
| 长用例 | `cdp-engine-coverage` 约 7 秒/模式 × 415 ≈ **45 分钟** | [BUGS.md](../../MF_UI/BUGS.md) §0.2（第 95 行） |

### 5.3 夹具与工具

| 目录 | 文件 | 数 |
| --- | --- | --- |
| `tests/fixtures/` | `mode-samples.mjs`（15,415 B）、`view-samples.mjs`、`no-usage.sse`、`reasoning-deepseek.sse`、`text-basic.sse`、`tool-calls.sse` | 6 |
| `tools/` | `build-tutorials.mjs`、`check-arg-contract.mjs`、`check-examples.mjs`、`check-ui.mjs`、`dedupe-engine-map.py`、`engine-signatures.mjs` | 6 |
| `scripts/` | `prune-fonts.mjs` | 1 |

`check-ui.mjs` 实测打印的关键行（同一时刻）：

```
端到端用例          ：cdp-* 48 个，已登记 48 个
样本 fixture        ：287 个键 / 重复键 0 个
数学键盘            ：6 分类 / 126 键（v1 也是 126）
教程引用的 target    ：30 个（已实现 30，待实现 0）
引擎模式可达性      ：映射 415 个 / 页面并集 391 个 / 取不到 0 个
自检通过 ✔
```

`dedupe-engine-map.py` 是这批工具里**唯一的 Python**（其余 5 个是 `.mjs`）。

### 5.4 React 工程自己的探针

`MFMath.UI.React/verify-plot.mjs`（工程根，**不在任何套件里**）：连 `http://127.0.0.1:9222/json/list`，挑 `mfmath.local|index.html` 那个页签，用 CDP 在真宿主里验绘图页结构与 Vue 版一致（`verify-plot.mjs:1-25`）。用法 `node verify-plot.mjs [截图输出目录]`（`verify-plot.mjs:2`）。

---

## 6. 跑端到端的前提：一个**真实宿主**

`cdp-*` 与 `audit-modes` 全部通过 CDP 驱动宿主 WebView2 里的真页面，**没有宿主就跑不了**；`unit-*` 与 `check-*` 不需要宿主（`run-all.ps1:12`）。宿主侧完整步骤见 [`../../MFMath.Host.Rust/docs/ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)；接缝本身见 [`../link/README.md`](../link/README.md)。

| 前提 | 具体要求 | 出处 |
| --- | --- | --- |
| 宿主进程 | 一个**已构建的**宿主 exe；现役是 `mfmath-host-rust.exe` | `ACCEPTANCE.md:37,45-49`；[`../../AGENTS.md`](../../AGENTS.md) §2 |
| CDP 端口 | `9222`。由 `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9222` 打开 | `run-all.ps1:121` |
| 页面 URL | 必须是 `https://mfmath.local/index.html`（取页正则靠它） | `main.rs:310`；`ACCEPTANCE.md:52` |
| 搜索假端点 | `MF_SEARCH_ENDPOINTS` 必须在**宿主启动前**设好，指向 `tests/fake-search-server.mjs`；没设时 `cdp-search` 拒绝跑 | `run-all.ps1:122-126` |
| 工作区外运行 | exe + DLL + `wwwroot` 拷到工作区外（如 `%TEMP%\mfhost-run`），否则日志/设置静默失败 | `ACCEPTANCE.md:31-38`；`MFMath.Host.Rust/docs/LINK-LAYER.md:121` |
| 外观复位 | `reset-appearance.mjs` 会先跑，否则上一轮的深色主题漏进来、按像素数的绘图用例假失败 | `run-all.ps1:167-181` |
| 独占 `dist`/`wwwroot` | 同一时刻只有一个人构建并同步；`npm run build` 之后必须重新 `sync-wwwroot.mjs`，否则验的是旧产物 | [`../../AGENTS.md`](../../AGENTS.md) §4 |
| 独占 9222 | 残留的 WebView2 会占住端口，新宿主绑不上而 CDP 静默附着到**旧**宿主（表现为"假失败，看着像产品缺陷"） | `run-all.ps1:150-156` |

两种跑法：

```powershell
# A) 本脚本起宿主（会先清掉 msedgewebview2 并等端口空出来）
powershell -ExecutionPolicy Bypass -File MF_UI/MFMath.UI.Vue/tests/run-all.ps1

# B) 附着到你自己已经起好的宿主（推荐：把"起宿主"和"跑用例"解耦）
powershell -ExecutionPolicy Bypass -File MF_UI/MFMath.UI.Vue/tests/run-all.ps1 -NoLaunch
```

`-NoLaunch` 存在的实证理由：某些环境里脚本自己的 `Start-Process` 起不了 GUI 进程（`ERROR_CANCELLED`），而经 shell 起（`cmd /c start`）可以（`run-all.ps1:128-135`；[BUGS.md](../../MF_UI/BUGS.md) §0.1「脚手架③」）。`-NoLaunch` 不会杀调用方自己的宿主（`run-all.ps1:213-215`），并且会先验 `127.0.0.1:9222/json/list` 可达（`run-all.ps1:138-146`）。

⚠ **宿主是谁**：`run-all.ps1:24-28` 的默认候选路径指向的是**已废弃的 .NET 宿主**（`MFMath.Host\bin\Release\net10.0-windows\MFMath.exe`，`:26`），上限提示词也写着 `dotnet build -c Release`（`:5,31`）。要跑 Rust 宿主请用环境变量覆盖：

```powershell
$env:MF_HOST_EXE = "<...>\mfmath-host-rust.exe"   # 优先级最高，run-all.ps1:24
```

这不是猜测：[BUGS.md](../../MF_UI/BUGS.md) §0.2（第 66-69 行）记着本机只能跑起 Rust 宿主，`ACCEPTANCE.md:37` 用的是 `mfmath-host-rust.exe`。该项已登记为 §8 的文档债 D2。

### 6.1 总回归的判据口径

**全量的 fail 数不能直接当回归数。** 用例会互相踩，[`../../AGENTS.md`](../../AGENTS.md) §4 与 `ACCEPTANCE.md:119-133` 都写明"单跑为准"。已知的成套 vs 单跑对照（`ACCEPTANCE.md:121-130`）里，只有"单独跑也红"的才算真失败 —— 例如 `cdp-plot-fractal` 成套 9/5、单独 12/2 且稳定复现（`ACCEPTANCE.md:130`）。

⚠ 另一条操作层面的坑：**中途 Ctrl-C 会让宿主里留一支没跑完的后台任务**，之后页面上任何同步 engine 调用都会永久阻塞（[BUGS.md](../../MF_UI/BUGS.md) §0.2 第 5 条，第 116-120 行）。要中断就先停宿主。

---

## 7. 构建期闸门与本次实测结果

### 7.1 闸门是什么

| 命令 | 展开 | 出处 |
| --- | --- | --- |
| `npm run check`（Vue） | `check:types` → `check:signatures` → **`check:args`** → `check:ui` | `MF_UI/MFMath.UI.Vue/package.json:17` |
| `npm run check:types`（Vue） | `tsc --noEmit -p tsconfig.json` | `package.json:13` |
| `npm run check:signatures` | `node tools/engine-signatures.mjs --check` | `package.json:14` |
| `npm run check:ui` | `build-tutorials.mjs` → `check-ui.mjs` → `check-examples.mjs` | `package.json:15` |
| `npm run check:args` | `node tools/check-arg-contract.mjs` | `package.json:18` |
| `npm run signatures:write` | 重写签名表（引擎侧改了才用） | `package.json:16` |
| `npm run check:types`（React） | `tsc --noEmit -p tsconfig.json` | `MFMath.UI.React/package.json:11` |

⚠ **这四个闸门里有一个是本次会话期间才接进 `check` 的** —— `package.json:17` 在会话早期读到的是 `… && npm run check:ui`（文件 44 行），重新读时已含 `npm run check:args`（文件 45 行）。见 §8.1。所以引用这一行时必须带时间戳。

Vue 的 `check:types` 覆盖面**只有** `src/**/*.ts`（= 7 个文件，全在 `src/lib/ai/`），`allowJs: true` + `checkJs: false` 表示只检查"TS 与 JS 的边界 + TS 内部"，**不检查 `.js`/`.vue` 内部**（`tsconfig.json:3-10,34-37`）。React 的 `include: ["src"]` 且**刻意排除 `vite.config.ts`**（缺 `@types/node` 会稳定报 TS2307，`MFMath.UI.React/tsconfig.json:2-9,27`）。

### 7.2 本次实测（2026-10-07 10:52）

| 命令 | 结果 | 判据 |
| --- | --- | --- |
| `npm run check:types --prefix MF_UI/MFMath.UI.Vue` | **exit 0** | 无输出（tsc 静默即通过） |
| `npm run check:signatures --prefix MF_UI/MFMath.UI.Vue` | **exit 0** | `引擎签名对账：源码 register_function 424 条 / 表 424 条` + `✓ 无漂移` |
| `npm run check:args --prefix MF_UI/MFMath.UI.Vue` | **exit 0** | `参数契约对账：415 个模式 / 检查 934 个声明键` + `白名单 74 条` + `✓ 参数契约一致` |
| `node tools/check-ui.mjs`（在 `MF_UI/MFMath.UI.Vue`） | **exit 0** | `端到端用例：cdp-* 48 个，已登记 48 个` + `自检通过 ✔` |
| `npm run check:types --prefix MF_UI/MFMath.UI.React` | **exit 0** | 无输出 |
| `npm run build` | **本次未跑**（会写 `dist/`，独占资源） | — |
| `tests/run-all.ps1` | **本次未跑**（需要真宿主，且会与并行会话互踩） | 见 §6 |

---

## 8. 已知的文档债

**规则**：注释/旧文档说 X、代码做 Y 时以**代码**为准。下面每条都给了 `文件:行`。

| # | 位置 | 注释/旧文档说 | 代码/实测做 | 严重度 |
| --- | --- | --- | --- | --- |
| **D1** | `MF_UI/MFMath.UI.Vue/package.json:6` | description：「计算走 `mf_mathematics.dll`，经 **C# MathBridge**/WebView2」 | C# 宿主 `MFMath.Host/` 已废弃，现役是 `MFMath.Host.Rust/`；页面走 `hostObjects.sync.mf.Dispatch`（[`../link/README.md`](../link/README.md) §2） | 中（误导读者去读废弃实现） |
| **D2** | `MF_UI/MFMath.UI.Vue/tests/run-all.ps1:5`、`:26`、`:30-32` | Prereq「host built (`dotnet build -c Release`)」；宿主人选写死 `MFMath.Host\bin\Release\net10.0-windows\MFMath.exe` | 现役宿主是 `mfmath-host-rust.exe`（`ACCEPTANCE.md:37`、[`../../AGENTS.md`](../../AGENTS.md) §2）；本机只跑得起 Rust 宿主（[BUGS.md](../../MF_UI/BUGS.md) §0.2:66-69）。绕法：`$env:MF_HOST_EXE`（`run-all.ps1:24`）或 `-NoLaunch` | **高**（照默认路径走会失败，且失败原因指向已废弃宿主） |
| **D3** | `MFMath.Host.Rust/tools/sync-wwwroot.mjs:6`、`MFMath.Host.Rust/build.rs:11`、`MFMath.Host.Rust/docs/ACCEPTANCE.md:52`、`MFMath.Host.Rust/docs/LINK-LAYER.md:526` | 「**47** 个 CDP 用例 / 47 个用例的取页正则」 | 实测磁盘 **48** 个 `cdp-*.mjs`，`check-ui.mjs` 打印 `cdp-* 48 个，已登记 48 个`（§5.1、§7.2）。[`../link/README.md`](../link/README.md):168 已更新为 48 | 低（纯计数过时，不影响行为） |
| **D4** | [BUGS.md](../../MF_UI/BUGS.md) §0.1 表（第 35 行） | 「check-ui 打印 `cdp-* **47** 个，已登记 47 个`」 | 现为 48（§7.2）。该表自称"是第一轮的记录，保留原样"（`:47-48`），属**有意留档**，不是错误 —— 但引用它时必须知道数已变 | 低 |
| **D5** | `MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue:6-7` | 「React 版目前是**迁移外壳**（`MFMath.UI.React/src/App.tsx` 的 `MIGRATED_PLOTS` 只有 `/plot/2d` 与 `/plot/polar`，其余页面显示"还没迁移到 React"占位）」 | `App.tsx:30` 的 `MIGRATED_PLOTS` 只覆盖 2 页，但那是 **React 自己的 dev 壳**（`MFMath.UI.React/index.html:10`）；**产品外壳已把 7 条绘图路由全交给 React**（`src/router/index.js:37-46` + `REACT_PAGES:68-76` + `LOADERS:28-36`）。详见 §2.3 | 中（会让人以为只有 2 页迁完了） |
| **D6** | `ReactPlotView.vue:14` | 样式「抽取值 Vue 版（`tools/extract-styles.mjs`）」 | 该文件真实位置是 **`MFMath.UI.React/tools/extract-styles.mjs`**；`MFMath.UI.Vue/tools/` 下没有它（实测 `Get-ChildItem MF_UI/MFMath.UI.Vue/tools/*` 只有 6 个文件，无 `extract-styles.mjs`）。单看这句会去错工程找 | 低 |
| **D7** | `vite.config.js:7` | 「dev：`npm run dev` → `http://127.0.0.1:5173`（**C# 宿主** Debug 模式指向此处，热更新）」 | 端口与 `strictPort` 属实（`:47-53`），但消费方 C# 宿主已废弃（同 D1/D2） | 低 |

### 8.1 本会话期间的并行改动（时间戳纪律的实例）

`AGENTS.md` §5 第 1 条要求结论带时间戳，理由是"在有人并行改同一棵树时，结论过期得非常快"。本文就撞上了一次，记在这里作为可核对的实例：

| 时刻 | 事实 | 证据 |
| --- | --- | --- |
| 2026-10-07 10:52 | `MF_UI/MFMath.UI.Vue/package.json` 共 **44** 行；`check` 展开为 `check:types && check:signatures && check:ui`（**不含** `check:args`）；`check:args` 已定义但无人调用 | 本次会话第一次 `read` 该文件 |
| 2026-10-07 10:54 | 同一文件共 **45** 行；`package.json:17` 变成 `check:types && check:signatures && **check:args** && check:ui`，`check:args` 落在 `:18` | 本次会话第二次 `read` + `Select-String` |

**后果**：本文初稿把"`check:args` 不在 `check` 里"写成了文档债；10:54 复核时该债已不存在，条目已撤掉。这一格同时说明：[`../README.md`](../README.md):134 的「**四道**构建闸门」在 10:54 之后才与 `package.json:17` 逐字对齐（types / signatures / args / ui 各算一道）。

**同一次复核里没变的**（所以本文其余引用仍按原行号成立）：`vite.config.js`、`ReactPlotView.vue`、`MF_UI/MFMath.UI.React/package.json`、`run-all.ps1`、`check-ui.mjs`、`MFMath.Host.Rust/tools/sync-wwwroot.mjs`、`build.rs`、`tauri.conf.json`、`main.rs`（上表 D1–D7 的行号都在 10:54 用 `Select-String` 逐条重核过）。

**未证实项**（不替它们背书）：

1. `prune-fonts.mjs:2` 的「2.44 MB → 1.66 MB」、`:10` 的「xz 734 KB → 257 KB」：**本次未跑 `npm run build`**，无法复核。验证方式：跑一次 `npm run build`，对 `dist` 做 `Get-ChildItem -Recurse | Measure-Object Length -Sum`（会写 `dist/`，需独占）。
2. `MFMath.UI.React/dist` 是否曾被某个未跟踪脚本消费：我只做了**全仓 grep**（`MFMath.UI.React` 关键字）未命中消费方。可能存在的本机脚本（如 `.tmp-*`）不在版本控制内，因此"没有消费方"这个结论的**范围是仓库内可见文件**。
3. 本次**没有跑任何 `cdp-*`**，所以"48 个 CDP 用例现在是否全绿"**未证实**。最近的成套基线是 `ACCEPTANCE.md:125`（2026-10-07 10:20 实测 `run-all.ps1` 全量 2142/20）—— 该数字带时间戳，用前请重新核。
4. `MF_UI/MFMath.UI.Vue/.tmp/`、`.tmp-*.log`（3 个）与 `.tmp-checkverify/tests/run-all.ps1` 仍在工作区磁盘上。按 [`../../AGENTS.md`](../../AGENTS.md) §6 它们属应当被 `.gitignore` 覆盖的临时产物；**我没有核实它们是否已被 git 跟踪**（未跑 `git status`），也未删除（不在本文工作面）。
