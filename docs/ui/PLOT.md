# 绘图模块

> 本文回答绘图模块的组织方式：React 侧六个绘图页与四个画布组件、两侧共用的共享绘图库、绘图页写进工作区的数据结构、排障钩子 `window.__mfPlot`，以及保留下来但已冻结的 Vue 实现及其约束。
>
> 与同层文档的分工：[README.md](README.md) 概述两个前端工程与构建链；[ARCHITECTURE.md](ARCHITECTURE.md) 讲 Vue 壳的分层与路由；[ENGINE-BINDING.md](ENGINE-BINDING.md) 讲 `ENGINE_MAP` 与 `engineCall` 的参数接法；[SETTINGS-WORKSPACE.md](SETTINGS-WORKSPACE.md) 讲工作区的存储机制，本文只讲绘图页往工作区里放什么；[CHECKS.md](CHECKS.md) 讲构建闸门。

## 1. 组成结构

| 层 | 位置 | 内容 |
| --- | --- | --- |
| Vue 壳 | `MF_UI/MFMath.UI.Vue/` | 路由、导航、侧栏、教程、AI、计算页。`/plot/*` 的 7 条路由全部指向同一个包装组件 |
| 包装组件 | `src/components/plot-react/ReactPlotView.vue` | 用 `createRoot` 把 React 页挂进一个 Vue 组件，按 `meta.reactPage` 动态 import |
| React 绘图页 | `MF_UI/MFMath.UI.React/src/plot/` | 13 个文件、5,225 行：6 个页面组件、4 个画布组件、2D 页的 3 个零件 |
| 共享逻辑层 | `MF_UI/MFMath.UI.Vue/src/lib/plot/` | 7 个文件、970 行：采样、坐标映射、表达式解析、配色、导出。零框架依赖，两侧引用同一批模块 |
| 冻结的 Vue 实现 | `MF_UI/MFMath.UI.Vue/src/views/plot/`、`src/components/plot/` | 迁移前的绘图页，不在构建图、不在类型检查范围、无用例覆盖 |

页面在 React，算法在共享层。React 侧源码写的是 `@shared/plot/*` 与 `@shared/bridge.js`，由别名指回 Vue 工程的 `src/lib`，因此不存在两套算法。

## 2. 页面与路由

路由共 7 条，页面组件共 6 个：`/plot/2d` 与 `/plot/polar` 共用 `PlotPage.tsx`，靠 `gridMode` 区分。路由表与页面键映射在 `src/router/index.js` 的 `REACT_PAGES`，包装组件内的加载器 `LOADERS` 与之对应。

| 导航项 | 路由 | 页面组件 | 画布组件 | 工作区 `kind` |
| --- | --- | --- | --- | --- |
| 2D 函数绘图 | `/plot/2d` | `PlotPage.tsx` | `PlotCanvas.tsx` | `plot` |
| 极坐标 | `/plot/polar` | `PlotPage.tsx`（`gridMode="polar"`） | `PlotCanvas.tsx` | `plot` |
| 3D 曲面 | `/plot/3d` | `Plot3DPage.tsx` | `SurfaceCanvas.tsx` | `plot3d` |
| 复平面 | `/plot/complex` | `PlotComplexPage.tsx` | 页内 canvas | `plot-complex` |
| 向量场 | `/plot/vector` | `PlotVectorPage.tsx` | `VectorFieldCanvas.tsx` | `plot-vector` |
| 自由几何 | `/plot/geometry` | `PlotGeometryPage.tsx` | `GeometryCanvas.tsx` | `plot-geometry` |
| 分形 | `/plot/fractal` | `PlotFractalPage.tsx` | 页内 canvas | `plot-fractal` |

定位命令：

```powershell
Select-String -Path MF_UI/MFMath.UI.Vue/src/router/index.js -Pattern "REACT_PAGES|ReactPlotView"
Select-String -Path MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue -Pattern "LOADERS|createRoot|routePath"
```

包装组件在每次切换前先 `root.unmount()` 再挂载：React 页内的模式与状态是 `useState` 初值，只改 prop 不生效；不卸载则 `ResizeObserver` 与采样循环会在离开后继续运行。`2d`/`polar` 额外传 `gridMode` 与 `routePath`，其余页只传 `routePath`。宿主节点需要显式高度，否则各页根节点的 `height:100%` 塌成 0。

`MFMath.UI.React/src/App.tsx` 是独立开发壳，`MIGRATED_PLOTS` 只含 `/plot/2d` 与 `/plot/polar`，不随产品发布；发布壳是 Vue 的 `dist`。

## 3. 共享绘图库

`@shared` 别名在三处配置，须同时成立：

| 位置 | 内容 | 出处 |
| --- | --- | --- |
| React 的 Vite | `alias: { "@shared": <Vue>/src/lib }` | `MF_UI/MFMath.UI.React/vite.config.ts` |
| React 的 tsc | `paths: { "@shared/*": ["../MFMath.UI.Vue/src/lib/*"] }` | `MF_UI/MFMath.UI.React/tsconfig.json` |
| Vue 的 Vite | `alias: { "@shared": ./src/lib }` | `MF_UI/MFMath.UI.Vue/vite.config.js` |

`src/lib/plot/` 的文件与职责：

| 文件 | 行数 | 职责 |
| --- | --- | --- |
| `view.js` | 149 | 视图矩形数学、网格步长、缩放/平移、默认视图 |
| `sampling.js` | 92 | `adaptiveSample` 与 `linspace` |
| `plotMath.js` | 246 | `parseExpr`、`validate`、`toEngineExpr` |
| `cartesian.js` | 216 | `drawCartesianGrid` / `drawPolarGrid` |
| `colors.js` | 54 | 色板 `PLOT_COLORS`、`colorAt`、`gridFor` |
| `exportImage.js` | 115 | 画布转 PNG（离屏 2 倍像素、走宿主写盘） |
| `prepare.js` | 98 | `prepare_expr` 包装：输入规范化与 LaTeX 预览 |

引擎桥（`engineCall` / `engineCallAsync` / `isHosted`）与 `asyncPolicy.js` 在 `src/lib/` 下，同样只有一份实现。两侧共用避免了同一算法的两套漂移。

## 4. 采样

`usePlotSampling.ts` 的采样常量与行为：

| 项 | 取值 | 出处 |
| --- | --- | --- |
| 采样范围 | 视口外扩 25%/边（`PAD = 0.25`） | `usePlotSampling.ts` 的 `PAD` |
| 一元曲线参数 | `initial: 300, maxRounds: 3, tolPx: 0.8, maxPoints: 6000` | 该文件 `opts` |
| 二元网格 | `GRID_N = 180`，一次 `expr_eval_grid`，共 32,400 点 | 该文件 `GRID_N` |
| 去抖 | 60 ms，带序号丢弃过期回调 | 该文件 `setTimeout` |

按解析类型分流：

| `parseExpr().type` | 采样方式 | 引擎 action |
| --- | --- | --- |
| `explicit` | x 上采点 | `expr_eval_vars_batch` |
| `polar` | θ∈[0,2π] | `expr_eval_vars_batch` |
| `parametric` | t 沿视图 x 跨度，两个分量各一次 | `expr_eval_vars_batch` |
| `vertical` | y 上采点 | `expr_eval_vars_batch` |
| `inequality` | 只采边界曲线，填充由画布完成 | `expr_eval_vars_batch` |
| `implicit` / `region` | 180×180 网格，不计入曲线数 | `expr_eval_grid` |
| `point` | 两个分量各求一次值 | `expr_eval_vars` |

两条语义约束：非有限值保留 `null`，不得先 `Number(x)`（`Number(null) === 0` 会把域外点变成合法的 `y=0`）；二元网格刻意保持同步——32,400 远低于 `asyncPolicy.js` 给 `expr_eval_grid` 的 2.5e5 阈值，`shouldRunAsync` 恒为 false。

异步只用于真会越阈值的地方：分形 `mandelbrot` 与复平面 `complex_grid`，二者共用 `lib/jobProgress.ts` 的 `JobProgress` 载荷类型。

## 5. 工作区数据结构

契约在 `MFMath.UI.React/src/lib/plotWorkspace.ts`（101 行）：

| API | 行为 |
| --- | --- |
| `loadPlotPage(route, kind)` | `getPage(route)`；非对象或 `payload.kind !== kind` 返回 `null`，形状不符当作没有 |
| `savePlotPage(route, payload)` | `setPage(route, payload)`；`route` 为空直接返回 |
| `usePlotWorkspace(route, deps, capture)` | 变更即回写；首帧用 `useRef(true)` 吞掉第一次 effect，避免打开即标脏 |

存储本体是 Vue 的 `src/lib/workspace/store.js` 的 `setPage` / `getPage`。

六个页面的载荷形状：

| 页面 | `kind` | 载荷字段 | 还原守卫 |
| --- | --- | --- | --- |
| 2D / 极坐标 | `plot` | `expressions[{text,color,visible}]`、`view{x0,x1,y0,y1}`、`gridMode`、`showGrid`、`params` | `isViewLike` + 逐项取字段 |
| 3D | `plot3d` | `exprInput`、`view{yaw,pitch,zoom}`、`showSurface`、`showWireframe`、`gridN`、`domain`、`params` | `strOr`/`boolOr`/`numOr`/`numsOr` + `zoom>0` |
| 复平面 | `plot-complex` | `funcExpr`、`mode`（下标）、`xMin`、`xMax`、`yMin`、`yMax`、`resolution` | `numOr` + `mode` 夹到合法范围 |
| 向量场 | `plot-vector` | `dxInput`、`dyInput`、`view`、`density`、`normalize`、`colorByMagnitude`、`showGrid`、`arrowScale`、`params` | `isViewLike` + `numOr`/`boolOr`/`strOr`/`numsOr` |
| 自由几何 | `plot-geometry` | `shapes[]`、`tool`、`snap` | 逐条验 `id` 有限数、`type` 字符串、`data` 数组 |
| 分形 | `plot-fractal` | `view{xmin,xmax,ymin,ymax}`、`maxIter`、`scheme`、`smooth`、`maxSide` | `numOr` + `xmin<xmax && ymin<ymax` |

2D 的载荷形状与冻结的 Vue 实现逐字一致，保证既有工作区文件可读。类型守卫（`isViewLike` / `numOr` / `boolOr` / `strOr` / `numsOr`）只校验类型与有限性，不校验取值范围；`density`、`gridN` 等值的上界由 UI 滑块约束，消费点不再夹取。复平面与分形在消费点做了夹取兜底。

## 6. 调试接口

`PlotPage.tsx` 在 `window` 上挂 `__mfPlot`，含三个读取函数：

| 成员 | 返回 |
| --- | --- |
| `view()` | 当前视图 `{x0,x1,y0,y1}` |
| `size()` | 画布尺寸 `{w,h}` |
| `status()` | 采样状态行文本 |

该钩子在 `useEffect` 中且不写依赖数组，每次渲染重跑，闭包不取过期值。其存在理由是 CDP 够不到 React 的 state，而视图是缩放/平移/「缩放到适应」唯一可观测的结果。

覆盖范围：只有 2D/极坐标页有此钩子；3D、复平面、向量场、几何、分形没有同类钩子。`size()` 与 `status()` 当前无消费方。读取须走 `JSON.stringify(window.__mfPlot.view())` 再解析，直接 `returnByValue` 会得到空对象。

## 7. 保留的 Vue 实现及其约束

`src/views/plot/`（6 文件、2,862 行、116,861 字节）：

| 文件 | 行数 |
| --- | --- |
| `PlotView.vue` | 1,029 |
| `PlotComplexView.vue` | 566 |
| `PlotFractalView.vue` | 416 |
| `PlotGeometryView.vue` | 311 |
| `PlotVectorView.vue` | 276 |
| `Plot3DView.vue` | 264 |

`src/components/plot/`（6 文件、2,673 行、101,488 字节）只被上面 6 个文件 import。

保留为冻结的回退资产。其约束是：不随修复更新、不在构建图、不在类型检查范围、无用例覆盖，因此把路由改回不等于回退到可用版本。

`tools/check-ui.mjs` 通过白名单 `FROZEN_VUE_PLOT_FILES` 禁止它被悄悄接回，三条判据：

| 判据 | 失败信息 |
| --- | --- |
| 目录里的 `.vue` 与白名单逐一对应 | 新增文件须挂路由或加进白名单 |
| 白名单里的文件都存在 | 缺失文件须从白名单删除 |
| 无 import 引用 | 引用即要求回退或撤销 |

引用检查只看真正的 `import`/`from` 语句，注释与文件间互相引用不算。

## 8. 验证命令

```powershell
# 冻结白名单 6/6 在位、被 import 0 处
cd MF_UI\MFMath.UI.Vue; node tools\check-ui.mjs

# 三组文件的行数（本文表格来源）
Get-ChildItem MF_UI\MFMath.UI.React\src\plot -File | % { "{0} {1}" -f $_.Name,(Get-Content $_.FullName).Count }
Get-ChildItem MF_UI\MFMath.UI.Vue\src\views\plot -File | % { "{0} {1}" -f $_.Name,(Get-Content $_.FullName).Count }
Get-ChildItem MF_UI\MFMath.UI.Vue\src\components\plot -File | % { "{0} {1}" -f $_.Name,(Get-Content $_.FullName).Count }
Get-ChildItem MF_UI\MFMath.UI.Vue\src\lib\plot -File | % { "{0} {1}" -f $_.Name,(Get-Content $_.FullName).Count }

# React 侧类型检查
cd ..\MFMath.UI.React; npm run check:types
```

绘图组端到端用例共 16 个 `cdp-plot-*.mjs`，另有 `cdp-export-image`、`cdp-workspace`、`cdp-plot-workspace`、`cdp-shortcuts-prefs` 覆盖导出与工作区，均需宿主运行，由 `tests/run-all.ps1` 统一登记。
