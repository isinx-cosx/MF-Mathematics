# 前端：两个工程、共享机制、构建链与测试资产

> 本文回答：前端由哪两个工程组成、二者如何共享代码、构建产物如何进入宿主、测试资产如何组织。
>
> 与同层文档的分工：
> - [ARCHITECTURE.md](ARCHITECTURE.md) —— Vue 壳内部的分层、路由与导航表、i18n、样式；
> - [ENGINE-BINDING.md](ENGINE-BINDING.md) —— 界面与引擎的接线；
> - [CHECKS.md](CHECKS.md) —— 构建期检查与守卫；
> - [PLOT.md](PLOT.md) —— React 绘图组与共享 plot 库的内部结构。
>
> 前端与宿主的接缝见 [`../link/README.md`](../link/README.md)；宿主侧验收步骤见 [`../../MFMath.Host.Rust/docs/ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)。

## 1. 两个工程

| | Vue 壳 | React 绘图组 |
| --- | --- | --- |
| 路径 | `MF_UI/MFMath.UI.Vue/` | `MF_UI/MFMath.UI.React/` |
| `name` | `mfmath-ui-vue` | `mfmath-ui-react-plot` |
| 版本 / `private` | `0.1.0` / `true` | `0.1.0` / `true` |
| 独立入口 | `index.html` → `src/main.js` | `index.html` → `src/main.tsx`（自用的 dev 壳） |
| 框架依赖 | `vue ^3.5.13`、`vue-router ^4.5.0`、`react ^19.3.0`、`react-dom ^19.3.0` | `react ^19.2.0`、`react-dom ^19.2.0` |

Vue 工程的 `package.json` 同时声明 react 与 react-dom。这是有意配置：`dist` 里的 React 绘图分块由 Vue 那次构建经 `react()` 插件转译产出，定位命令：

```powershell
Select-String -Path MF_UI/MFMath.UI.Vue/vite.config.js -Pattern "react\(\)"
Select-String -Path MF_UI/MFMath.UI.Vue/package.json -Pattern '"react"'
```

两个工程的脚本入口：

| 脚本 | Vue | React |
| --- | --- | --- |
| 构建 | `build` = `vite build && node scripts/prune-fonts.mjs` | `build` = `vite build` |
| 类型检查 | `check:types` = `tsc --noEmit -p tsconfig.json` | `check:types` = `tsc --noEmit -p tsconfig.json` |
| 聚合检查 | `check` = `check:types → check:signatures → check:args → check:ui` | 无聚合脚本 |

### 1.1 源码规模

下述数量由本目录命令逐一计数得到：

| 位置 | 数量 | 计数命令（仓库根） |
| --- | --- | --- |
| `MFMath.UI.Vue/src/views/**/*.vue` | 16 | `(Get-ChildItem MF_UI/MFMath.UI.Vue/src/views -Recurse -Filter *.vue).Count` |
| `MFMath.UI.Vue/src/components/**/*.vue` | 33 | 同上，路径换 `components` |
| `MFMath.UI.Vue/src/lib/**/*.js` | 43 | 同上，路径换 `lib`，过滤器换 `*.js` |
| `MFMath.UI.Vue/src/lib/**/*.ts` | 7 | 同上，过滤器换 `*.ts`（全部在 `src/lib/ai/`） |
| `MFMath.UI.React/src/**/*.tsx` | 16 | `(Get-ChildItem MF_UI/MFMath.UI.React/src -Recurse -Filter *.tsx).Count` |
| `MFMath.UI.React/src/**/*.ts` | 6 | 同上，过滤器换 `*.ts` |
| `MFMath.UI.React/src/**/*.css` | 15 | 同上，过滤器换 `*.css` |
| `MFMath.UI.React/src/plot/` 文件数 | 13（其中 6 个 `*Page.tsx`） | `(Get-ChildItem MF_UI/MFMath.UI.React/src/plot -File).Count` |

## 2. Vue 壳与内嵌 React 绘图组的关系

绘图路由整体归 React，其余页面留在 Vue。React 页挂在 Vue 路由上，由 `src/components/plot-react/ReactPlotView.vue` 负责挂载与卸载。

### 2.1 路由到组件

| 路由 | 页面键 | React 组件 |
| --- | --- | --- |
| `/plot/2d` | `2d` | `PlotPage` |
| `/plot/polar` | `polar` | `PlotPage`（同一组件，靠 `gridMode` 区分） |
| `/plot/vector` | `vector` | `PlotVectorPage` |
| `/plot/fractal` | `fractal` | `PlotFractalPage` |
| `/plot/3d` | `3d` | `Plot3DPage` |
| `/plot/complex` | `complex` | `PlotComplexPage` |
| `/plot/geometry` | `geometry` | `PlotGeometryPage` |

三张表完成「路由 → 页面键 → 组件加载器」的映射：

| 表 | 位置 | 定位命令 |
| --- | --- | --- |
| `REACT_PAGES`（路由 → 页面键，7 条） | `src/router/index.js` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "REACT_PAGES"` |
| `LOADERS`（页面键 → 加载器，7 键对应 6 个组件） | `ReactPlotView.vue` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue -Pattern "LOADERS"` |
| 7 条 `/plot/*` 路由全部指向 `ReactPlotView.vue` | `src/router/index.js` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "ReactPlotView.vue"` |

`LOADERS` 里的组件源码路径是跨工程的相对路径，形如 `../../../../MFMath.UI.React/src/plot/PlotPage`。

### 2.2 挂载方式

| 环节 | 实现 | 定位命令 |
| --- | --- | --- |
| 动态分块 | 每个页面键一次 `await loader()` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue -Pattern "await loader"` |
| 挂载 | `createRoot(host)` 后 `render(createElement(...))` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue -Pattern "createRoot"` |
| 换页重挂 | `route.fullPath` 变化时先 `unmount()` 再挂新组件 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue -Pattern "route.fullPath"` |
| 竞态护栏 | 挂载序号 `seq`，旧挂载序号不再生效 | `Select-String -Path MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue -Pattern "seq"` |
| 容器高度 | `.react-plot-host { height: 100% }` | `Select-String -Path MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue -Pattern "react-plot-host"` |

### 2.3 两个外壳的差异

React 工程自己的 dev 壳（`MFMath.UI.React/src/App.tsx`）维护一份 `MIGRATED_PLOTS = new Set(["/plot/2d", "/plot/polar"])`，只把两条路由当已迁移。这份集合描述的是 dev 壳自身的导航，不是产品路由表的范围。产品外壳的绘图路由共 7 条（见 §2.1）。

## 3. `@shared/*` 跨工程共享

两个工程在运行期共用同一份 `src/lib` 模块实例，而不是两份拷贝。解析路径的配置如下：

| 解析方 | 配置 | 定位命令 |
| --- | --- | --- |
| Vue 构建（转译 React 源码时） | `alias: { "@shared": <Vue>/src/lib }` | `Select-String -Path MF_UI/MFMath.UI.Vue/vite.config.js -Pattern '"@shared"'` |
| React 独立 dev/build | `alias: { "@shared": ../MFMath.UI.Vue/src/lib }` | `Select-String -Path MF_UI/MFMath.UI.React/vite.config.ts -Pattern '"@shared"'` |
| React 的 `check:types` | `paths: { "@shared/*": ["../MFMath.UI.Vue/src/lib/*"] }` | `Select-String -Path MF_UI/MFMath.UI.React/tsconfig.json -Pattern '"@shared/\*"'` |
| Vue dev 文件系统白名单 | `server.fs.allow: [".."]` | `Select-String -Path MF_UI/MFMath.UI.Vue/vite.config.js -Pattern "fs:"` |
| React dev 文件系统白名单 | `server.fs.allow: [uiRoot]` | `Select-String -Path MF_UI/MFMath.UI.React/vite.config.ts -Pattern "fs:"` |

指向同一份文件的约束记录在 `vite.config.js` 的注释中：React 侧写 `@shared/plot/*`、`@shared/bridge.js`，必须解析到本工程的 `src/lib`，否则绘图注入钩子与引擎桥会各有一份，行为漂移。

`@shared` 是给 React 侧跨工程引用用的别名；Vue 自身源码直接用相对路径引 `src/lib`，不写 `@shared`。

共享模块示例：

| 模块 | 消费方 | 定位命令 |
| --- | --- | --- |
| `@shared/bridge.js`（WebView2 引擎桥） | React 各绘图页与 `main.tsx` | `Select-String -Path MF_UI/MFMath.UI.React/src -Pattern "@shared/bridge.js"` |
| `@shared/plot/plotMath.js` | `PlotPage.tsx` | `Select-String -Path MF_UI/MFMath.UI.React/src/plot/PlotPage.tsx -Pattern "@shared/plot/plotMath"` |
| `@shared/engine/asyncPolicy.js` | `PlotFractalPage.tsx`、`PlotComplexPage.tsx` | `Select-String -Path MF_UI/MFMath.UI.React/src -Pattern "@shared/engine/asyncPolicy"` |
| `@shared/router/nav.js`（导航数据一份） | `App.tsx` | `Select-String -Path MF_UI/MFMath.UI.React/src/App.tsx -Pattern "@shared/router/nav"` |

## 4. 构建链与产物

### 4.1 Vue 构建

```powershell
npm run build --prefix MF_UI/MFMath.UI.Vue
```

| 步骤 | 内容 | 定位命令 |
| --- | --- | --- |
| 打包 | `vite build` | `Select-String -Path MF_UI/MFMath.UI.Vue/package.json -Pattern '"build"'` |
| 清字体冗余 | `node scripts/prune-fonts.mjs` | 同上（`&&` 串联） |
| 输出目录 | `dist/`，`emptyOutDir: true` | `Select-String -Path MF_UI/MFMath.UI.Vue/vite.config.js -Pattern "outDir"` |
| 编译目标 | `chrome110` | `Select-String -Path MF_UI/MFMath.UI.Vue/vite.config.js -Pattern "chrome110"` |
| 路径基数 | `base: "./"` | `Select-String -Path MF_UI/MFMath.UI.Vue/vite.config.js -Pattern "base:"` |
| dev 端口 | `127.0.0.1:5173`，`strictPort: true` | `Select-String -Path MF_UI/MFMath.UI.Vue/vite.config.js -Pattern "strictPort"` |

`prune-fonts.mjs` 删除 KaTeX 与 MathLive 字体中的 `.woff`/`.ttf`/`.otf`/`.eot`，只保留 Chromium 命中的 `.woff2`。删除按「字体族 + 字重」归组，且只有该组存在 `woff2` 时才删。回归用例是 `tests/cdp-font-load.mjs`。

### 4.2 `dist` 进入宿主的路径

| 机制 | 配置 | 定位命令 |
| --- | --- | --- |
| 内嵌 | `build.frontendDist = "../MF_UI/MFMath.UI.Vue/dist"` | `Select-String -Path MFMath.Host.Rust/tauri.conf.json -Pattern "frontendDist"` |
| 拷贝 | `node tools/sync-wwwroot.mjs`，默认写 `target/debug/wwwroot` | `Select-String -Path MFMath.Host.Rust/tools/sync-wwwroot.mjs -Pattern "target"` |

`sync-wwwroot.mjs` 的参数：`--profile release` 写 `target/release/wwwroot`；`--dest <目录>` 写指定目录；`--exe <路径>` 写该 exe 同目录的 `wwwroot`。

脚本先清空目标目录再拷贝，因此 `--dest` 的语义是「wwwroot 目录本身」。目标目录里若存在 `mfmath-host-rust.exe` 或 `MFMath.exe`，脚本拒绝执行，避免把 exe 目录清空。

宿主读取 `https://mfmath.local/index.html`。前端改动后只需重拷 `dist`，不必重编 Rust 宿主。

### 4.3 React 工程的 `dist`

React 工程的 `npm run build` 只服务于它自己的 dev 壳。产品链路只读取 Vue 的 `dist`（内嵌与 `sync-wwwroot.mjs` 都以 `MFMath.UI.Vue/dist` 为源）。

## 5. 测试资产

测试集中在 `MF_UI/MFMath.UI.Vue/tests/`。React 工程另有一个独立探针 `MFMath.UI.React/verify-plot.mjs`。

### 5.1 按命名前缀

| 类别 | 数量 | 计数命令（仓库根） |
| --- | --- | --- |
| `cdp-*.mjs`（CDP 驱动真宿主） | 48 | `(Get-ChildItem MF_UI/MFMath.UI.Vue/tests/cdp-*.mjs).Count` |
| `unit-*.mjs`（纯 Node，假桥） | 4 | `(Get-ChildItem MF_UI/MFMath.UI.Vue/tests/unit-*.mjs).Count` |
| `fake-*.mjs`（本地假端点） | 3 | `(Get-ChildItem MF_UI/MFMath.UI.Vue/tests/fake-*.mjs).Count` |
| 顶层全部 `.mjs` | 63 | `(Get-ChildItem MF_UI/MFMath.UI.Vue/tests/*.mjs).Count` |

4 个 `unit-*`：`unit-result-model`、`unit-sse`、`unit-markdown`、`unit-history-store`。3 个 `fake-*`：`fake-ai-server`、`fake-search-server`、`fake-account-server`。

### 5.2 登记表

`tests/run-all.ps1` 是端到端套件的登记表。每个脚本打印一行 `RESULT|<name>|<pass>|<fail>`，由脚本解析。`tools/check-ui.mjs` 断言磁盘上每个 `tests/cdp-*.mjs` 都已登记（`NOT_IN_SUITE` 白名单当前为空）。

### 5.3 夹具与工具

| 目录 | 内容 |
| --- | --- |
| `tests/fixtures/` | 模式样本、视图样本、SSE 样本 |
| `tools/` | `build-tutorials.mjs`、`check-arg-contract.mjs`、`check-examples.mjs`、`check-ui.mjs`、`dedupe-engine-map.py`、`engine-signatures.mjs` |
| `scripts/` | `prune-fonts.mjs` |

## 6. 复跑命令

| 目标 | 命令 |
| --- | --- |
| 引擎模式可达性、i18n、键盘、用例登记的守卫输出 | `node MF_UI/MFMath.UI.Vue/tools/check-ui.mjs`（在 `MF_UI/MFMath.UI.Vue` 下执行） |
| 引擎签名对账 | `npm run check:signatures --prefix MF_UI/MFMath.UI.Vue` |
| 参数契约对账 | `npm run check:args --prefix MF_UI/MFMath.UI.Vue` |
| 全部构建期闸门 | `npm run check --prefix MF_UI/MFMath.UI.Vue` |
| 端到端套件 | `powershell -ExecutionPolicy Bypass -File MF_UI/MFMath.UI.Vue/tests/run-all.ps1 -NoLaunch` |

端到端套件需要真宿主与 CDP 端口 `9222`。宿主侧步骤见 [`../../MFMath.Host.Rust/docs/ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)。
