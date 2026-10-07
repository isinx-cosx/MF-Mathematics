# 绘图组：React 六个绘图页 + 共享绘图库 + 被冻结的 Vue 版本

> **本文只回答一个问题：绘图组是怎么组织的：React 六个绘图页、共享绘图库、以及被冻结的 Vue 版本。**
>
> 与同层其它文档的分工：[README.md](README.md) 是两个前端工程与构建链的总览；
> [ARCHITECTURE.md](ARCHITECTURE.md) 讲 Vue 壳的分层、路由与导航表；
> [ENGINE-BINDING.md](ENGINE-BINDING.md) 讲界面怎么把参数接到引擎（`ENGINE_MAP` / `calcArgs`）；
> [SETTINGS-WORKSPACE.md](SETTINGS-WORKSPACE.md) 讲设置与工作区**存储**（本文只讲绘图页往工作区里放什么）；
> [CHECKS.md](CHECKS.md) 讲四道构建闸门；引擎侧的采样与视口契约见 [../engine/PLOT.md](../engine/PLOT.md)。

**核对时间**：2026-10-07 10:5x
**权威源**：`MF_UI/MFMath.UI.React/src/plot/`（13 文件 5,225 行）、`MF_UI/MFMath.UI.React/src/lib/plotWorkspace.ts`、`MF_UI/MFMath.UI.Vue/src/router/index.js`、`MF_UI/MFMath.UI.Vue/src/components/plot-react/ReactPlotView.vue`、`MF_UI/MFMath.UI.Vue/tools/check-ui.mjs:348-409`
**行数/字节数的复跑命令**见 §10；本文所有数字都是在本机跑出来的，不是抄来的。

---

## 1. 一句话结构

| 层 | 在哪 | 是什么 |
| --- | --- | --- |
| 外壳（Vue） | `MF_UI/MFMath.UI.Vue/` | 路由、导航、侧栏、教程、AI、计算页。`/plot/*` 的 7 条路由全部指向同一个包装组件 |
| 包装 | `src/components/plot-react/ReactPlotView.vue` | 用 `createRoot` 把 React 页挂进一个 Vue 组件，按 `meta.reactPage` 动态 import（每页一个分块） |
| 绘图页（React） | `MF_UI/MFMath.UI.React/src/plot/` | 6 个页面组件 + 4 个画布组件（`PlotCanvas` / `SurfaceCanvas` / `VectorFieldCanvas` / `GeometryCanvas`）+ 3 个 2D 页的零件（`ExpressionList` / `ParamSlider` / `usePlotSampling`），共 13 文件 |
| 逻辑层（共享） | `MF_UI/MFMath.UI.Vue/src/lib/plot/`、`bridge.js`、`engine/asyncPolicy.js`、`workspace/store.js` | 采样、坐标映射、表达式解析、配色、导出、引擎桥。**零框架依赖**，两侧写的是同一批模块（§3） |
| 冻结的回退资产 | `MF_UI/MFMath.UI.Vue/src/views/plot/`（6 文件 2,862 行） | 迁移前的 Vue 绘图页。不在构建图、不在类型检查范围、无用例覆盖（§8） |

要点：**页面在 React，逻辑不在 React。** React 侧源码里写的是 `@shared/plot/*`，由别名指回 Vue 工程的 `src/lib`（§3），所以不存在两套算法。

---

## 2. 六页 ↔ 七路由 ↔ 组件

路由共有 **7** 条，页面只有 **6** 个：`/plot/2d` 与 `/plot/polar` 共用 `PlotPage.tsx`，靠 `gridMode` 与 `routePath` 区分（`src/router/index.js:68-76` 的 `REACT_PAGES` 是 7 项；`ReactPlotView.vue:28-36` 的 `LOADERS` 也是 7 项，其中两项指向同一个文件）。

| 导航项 | 路由 | `meta.reactPage` | 页面组件 | 画布组件 | 工作区 `kind` |
| --- | --- | --- | --- | --- | --- |
| 2D 函数绘图 | `/plot/2d` | `2d` | `PlotPage.tsx` | `PlotCanvas.tsx` | `plot` |
| 极坐标 | `/plot/polar` | `polar` | `PlotPage.tsx`（`gridMode="polar"`） | `PlotCanvas.tsx` | `plot` |
| 3D 曲面 | `/plot/3d` | `3d` | `Plot3DPage.tsx` | `SurfaceCanvas.tsx` | `plot3d` |
| 复平面 | `/plot/complex` | `complex` | `PlotComplexPage.tsx` | 页面内自己的 canvas（无独立组件文件） | `plot-complex` |
| 向量场 | `/plot/vector` | `vector` | `PlotVectorPage.tsx` | `VectorFieldCanvas.tsx` | `plot-vector` |
| 自由几何 | `/plot/geometry` | `geometry` | `PlotGeometryPage.tsx` | `GeometryCanvas.tsx` | `plot-geometry` |
| 分形 | `/plot/fractal` | `fractal` | `PlotFractalPage.tsx` | 页面内自己的 canvas（无独立组件文件） | `plot-fractal` |

出处：导航项 `src/lib/router/nav.js:49-55`；路由表 `src/router/index.js:37-46`（7 条都指向 `ReactPlotView.vue`）；`REACT_PAGES` 映射 `:68-76`；`meta.reactPage` 的写入 `:103`；各页 `kind` 见 §6 的表。

**只重挂、不改 prop**：`ReactPlotView.vue:49-78` 每次挂载前先 `root.unmount()`（`:52-56`），因为 React 页里的模式/状态是 `useState` 初值，只改 prop 不会生效；不卸载的话 `ResizeObserver` 与采样循环会在离开后继续跑。`2d`/`polar` 会**额外**传 `routePath`（`:73-75`），其余 5 页本来就在传。

包装组件还负责一件事：给宿主节点确定高度（`:98-106`），否则 React 各页根节点的 `height:100%` 会塌成 0 宽。

> `MFMath.UI.React/src/App.tsx` 是**独立开发壳**（`MIGRATED_PLOTS` 只有 `/plot/2d`、`/plot/polar`，见 `App.tsx:30`），不随产品发布 —— 发布壳是 Vue 的 `dist`（`MFMath.Host.Rust/tools/sync-wwwroot.mjs:24`）。它有一处不一致，记在 §11。

---

## 3. 共享绘图库（`@shared` → Vue 的 `src/lib`）

别名有三处，必须同时成立，缺一个就会在某一环报"找不到模块"：

| 位置 | 内容 | 出处 |
| --- | --- | --- |
| React 的 Vite | `alias: { "@shared": <Vue>/src/lib }` | `MFMath.UI.React/vite.config.ts:13`、`:19` |
| React 的 tsc | `paths: { "@shared/*": ["../MFMath.UI.Vue/src/lib/*"] }` | `MFMath.UI.React/tsconfig.json:25` |
| Vue 的 Vite | `alias: { "@shared": ./src/lib }`（供 ReactPlotView 的 import 走同一条路径） | `MFMath.UI.Vue/vite.config.js:41-42` |

`MF_UI/MFMath.UI.Vue/src/lib/plot/` 共 7 个文件 970 行：

| 文件 | 行 | 职责 | React 侧的消费者 |
| --- | --- | --- | --- |
| `view.js` | 149 | 视图矩形数学、`nice numbers` 网格步长、缩放/平移、默认视图 | `PlotPage.tsx:10`、`PlotCanvas.tsx:4-6`、`usePlotSampling.ts:5` |
| `sampling.js` | 92 | `adaptiveSample`（屏幕空间偏差阈值加密）+ 导出 `linspace` | `usePlotSampling.ts:4`、`Plot3DPage.tsx:7`、`PlotVectorPage.tsx:6` |
| `plotMath.js` | 246 | `parseExpr`（类型识别/参数提取）、`validate`、`toEngineExpr` | `PlotPage.tsx:7`、`PlotCanvas.tsx:9`、`usePlotSampling.ts:3`、3D/向量场页 |
| `cartesian.js` | 216 | 可复用网格绘制（`drawCartesianGrid` / `drawPolarGrid`） | `PlotCanvas.tsx:8`（极坐标网格）、`GeometryCanvas.tsx:5` |
| `colors.js` | 54 | Desmos 风格色板 `PLOT_COLORS` / `colorAt` / `gridFor` | `PlotPage.tsx:8`、`PlotCanvas.tsx:7` |
| `exportImage.js` | 115 | 画布 → PNG（离屏 2 倍像素重画、不透明背景、走宿主写盘） | 6 个绘图页全部 import（§7 的导出反馈） |
| `prepare.js` | 98 | `prepare_expr` 的包装：输入规范化 + LaTeX 预览 | 不在 `src/plot/` 里用；`components/MathField.tsx:4`、`lib/plotText.ts:1` |

`bridge.js`（引擎桥 `engineCall` / `engineCallAsync` / `isHosted` / `plotMode` / `onAppearanceChange`）与 `engine/asyncPolicy.js`（`shouldRunAsync` / `describeWork`）也在同一份 `src/lib` 下，同样只有一份实现。

**为什么必须只有一份**：`MFMath.UI.React/vite.config.ts:5-11` 把理由写在配置里 —— 采样/映射/解析/配色全是纯 JS，两侧共用可避免"同一算法两套漂移"。B9 给了一个反向实证：`PlotCanvas.vue:233` 用的是**文件内同名本地函数**而 `cartesian.js:139` 的 `drawPolarGrid` 在 Vue 侧无人调用，但在 React 侧是活的（`PlotCanvas.tsx:8`）—— 所以"某文件是死代码"这个结论**在两个框架下不通用**。

---

## 4. 采样：`usePlotSampling.ts`

| 项 | 值 | 出处 |
| --- | --- | --- |
| 采样范围 | 视口外扩 25%/边（共 1.5 倍），`PAD = 0.25` | `usePlotSampling.ts:43`、`:100-102` |
| 一元曲线参数 | `initial:300, maxRounds:3, tolPx:0.8, maxPoints:6000` | `:121` |
| 二元网格 | `GRID_N = 180`，一次 `expr_eval_grid`，共 32,400 点 | `:46`、`:204-215` |
| 去抖 | 60 ms，带序号 `seq` 丢弃过期回调 | `:233-238` |
| 状态行文本 | `引擎采样 N 条曲线[，M 条失败] · K 点 · 范围 [x0, x1] × [y0, y1]` | `:222-229` |

按解析类型分流（`:115-196`）：

| `parseExpr().type` | 采什么 | 引擎 action |
| --- | --- | --- |
| `explicit` | x 上采点 | `expr_eval_vars_batch` |
| `polar` | θ∈[0,2π]，`r·cosθ / r·sinθ` | `expr_eval_vars_batch` |
| `parametric` | t 沿视图 x 跨度 | `expr_eval_vars_batch` ×2 |
| `vertical` | y 上采点 | `expr_eval_vars_batch` |
| `inequality` | **只采边界曲线**（填充由画布做），计入"采样 N 条曲线" | `expr_eval_vars_batch` |
| `implicit` / `region` | 180×180 网格，**不计入曲线数** | `expr_eval_grid` |
| `point` | 两个分量各求一次值，进"点"列表 | `expr_eval_vars` |
| 其它 | 记为错误：`React 绘图版暂未支持该类型（<type>）` | — |

两条容易写错的语义，代码里有明确依据：

- **非有限值必须留 `null`，不能先 `Number(x)`**。`Number(null) === 0`，于是引擎对域外点返回的 `null` 会变成合法的 `y=0`：`ln(x)` 在 x<0 会画出一条假地平线、`1/x` 会横跨渐近线连成一条线。现行写法是对**原值**做 `Number.isFinite`（`:64-72`）。
- **二元网格刻意保持同步**：32,400 远低于 `asyncPolicy` 给 `expr_eval_grid` 的 2.5e5 阈值，`shouldRunAsync` 恒 false；且 `asyncPolicy.js:12-15` 要求"绘图页每条曲线/每行一次的采样保持同步"。注释同时写明：若把 `GRID_N` 提到 500 以上要重新评估（`:198-203`，另见 [BUGS.md](../../MF_UI/BUGS.md) §B5）。

**异步只用在真会越过阈值的地方**：分形 `mandelbrot`（`PlotFractalPage.tsx:167-175`）与复平面 `complex_grid`（`PlotComplexPage.tsx:165-168`，分辨率上限 1000 ⇒ 最多 1e6 点）。两者共用一个载荷类型 `JobProgress`，定义在 `lib/jobProgress.ts:12`（`{ state: string; elapsedMs?: number; ms?: number }`）—— 当初两页各写一份本地定义，抽出来是为了不让字段名漂移。

---

## 5. 2D 页的骨架：`PlotPage.tsx`

`PlotPage.tsx` 是唯一一个"页面自己管采样 + 表达式列表 + 参数滑块"的实现，其余 5 页各自直连引擎。

| 关注点 | 做法 | 出处 |
| --- | --- | --- |
| 初始视图 | `defaultView(w,h)`；四项必须是有限数，否则退回 `x∈[-10,10]` + 等比 y | `:63-71` |
| 画布真实尺寸一到就重设视野 | **只在第一次**（`sizedRef`），且**从工作区还原过就不覆盖** | `:178-183` |
| 视野不变式 | `view` 是 `useState` 值，**不是** Vue 的 `ref`；`zoomFit` 用 `const v = view` | `:385`（BUGS §B3） |
| 聚焦曲线加粗 | `curves` memo 里 `emphasis: r.id === activeId` | `:151-154`（BUGS 附 D / B13） |
| 行内校验 | 对 `rows` 变化跑，先 `validate()` 再 `parseExpr()`；无变化返回原数组 | `:232-251` |
| 极值/交点 | **默认不自动画到画布上**，点必须由用户自己添加（点击曲线） | `:122-125`、`:438-460` |
| 「缩放到适应」 | 只喂当前视野内的点（视野内不足 2 个才退回全部有限点） | `:377-405` |

画布 `PlotCanvas.tsx` 的绘制顺序是固定的：网格 → 区域 → 不等式 → 极值标记 → 交点 → 曲线 → 隐式等值线 → 用户点 → 追踪标记（`:611-630`）。注释写明"标记必须在曲线之前"（不透明菱形画在曲线之后会盖掉一截，看起来像曲线断了）。另有 `PX_LIMIT = 1e6` 的屏幕坐标钳制（`:87-90`）：世界坐标换算后一旦到 1e38 量级，Canvas 2D 的 float32 路径会被整条丢弃 —— 曲线 0 像素且不报任何异常。

---

## 6. 工作区载荷（`lib/plotWorkspace.ts`）

Vue→React 迁移当初**漏掉的就是这一层**（§9 的 B14）。现行契约在 `MFMath.UI.React/src/lib/plotWorkspace.ts`（101 行）：

| API | 行为 | 出处 |
| --- | --- | --- |
| `loadPlotPage(route, kind)` | `getPage(route)`；非对象/是数组→`null`；`payload.kind !== kind` → `null`。**形状不符就当没有，绝不半还原** | `:32-38` |
| `savePlotPage(route, payload)` | `setPage(route, payload)`；`route` 为空直接返回 | `:41-44` |
| `usePlotWorkspace(route, deps, capture)` | 变更即回写；**首帧刻意不回写**（`useRef(true)` 吞掉第一次 effect），否则"刚打开一页"就被标脏 | `:59-72` |

`deps` 必须覆盖所有会被存下来的状态，长度在本组件内恒定（`:49-51`）。存储本体是 Vue 的 `src/lib/workspace/store.js`：`setPage`（`:34-38`）、`getPage`（`:40-42`）。

六个页面的载荷形状：

| 页面 | `kind` | 载荷字段（键名逐字） | 还原处的守卫 |
| --- | --- | --- | --- |
| 2D / 极坐标 | `plot` | `expressions[{text,color,visible}]`、`view{x0,x1,y0,y1}`、`gridMode`、`showGrid`、`params{…}` | `isViewLike(saved.view)`、数组逐项取字段 | 
| 3D | `plot3d` | `exprInput`、`view{yaw,pitch,zoom}`、`showSurface`、`showWireframe`、`gridN`、`domain`、`params{…}` | `strOr`/`boolOr`/`numOr`/`numsOr` + `zoom>0` |
| 复平面 | `plot-complex` | `funcExpr`、`mode`（下标）、`xMin`、`xMax`、`yMin`、`yMax`、`resolution` | `numOr` + `mode` 夹到 `[0, MODES.length)` |
| 向量场 | `plot-vector` | `dxInput`、`dyInput`、`view{x0,y0,x1,y1}`、`density`、`normalize`、`colorByMagnitude`、`showGrid`、`arrowScale`、`params{…}` | `isViewLike` + `numOr`/`boolOr`/`strOr`/`numsOr` |
| 自由几何 | `plot-geometry` | `shapes[]`、`tool`、`snap` | 逐条验 `id` 有限数、`type` 字符串、`data` 数组，不合格整条丢掉 |
| 分形 | `plot-fractal` | `view{xmin,xmax,ymin,ymax}`、`maxIter`、`scheme`、`smooth`、`maxSide` | `numOr` + `xmin<xmax && ymin<ymax` 检查 |

出处：2D `PlotPage.tsx:92`、`:159-166`；3D `Plot3DPage.tsx:68`、`:75-86`、`:89-98`；复平面 `PlotComplexPage.tsx:117-127`、`:132-141`；向量场 `PlotVectorPage.tsx:66-88`、`:91-102`；几何 `PlotGeometryPage.tsx:70-91`、`:94-99`；分形 `PlotFractalPage.tsx:95-111`、`:115-122`。

**为什么 2D 的形状必须逐字照旧**：老工作区文件（Vue 版 `capturePlot()` 写的）要照样能读，测试里 `pages()["/plot/2d"].view` 这类断言也要继续成立。另外 5 页的形状是**新设计**的 —— 它们在 Vue 版时代**也从来没接过工作区**（`plotWorkspace.ts:9-14`，[BUGS.md](../../MF_UI/BUGS.md) §B14 状态段）。

**那组"用户可手改"的取值守卫**（`plotWorkspace.ts:74-101`）：工作区文件是磁盘上的 JSON，用户能直接编辑，所以每个字段都要过一遍类型检查再采信，坏值就退回默认值，不让一个坏字段把整页带崩。

| 守卫 | 判据 | 出处 |
| --- | --- | --- |
| `isViewLike(v)` | `x0/x1/y0/y1` 全是 `Number.isFinite` | `:75-79` |
| `numOr(v, fallback)` | `Number.isFinite(v)` | `:83-85` |
| `boolOr(v, fallback)` | `typeof v === "boolean"` | `:86-88` |
| `strOr(v, fallback)` | `typeof v === "string"` | `:89-91` |
| `numsOr(v)` | 对象且非数组，坏值**逐项**丢掉 | `:93-101` |

⚠ **这组守卫只校验类型与有限性，不校验取值范围。** 例：`density`（向量场每轴箭头数，`PlotVectorPage.tsx:82`）与 `gridN`（3D 网格密度，`Plot3DPage.tsx:85`）在**消费点也没有夹取** —— `PlotVectorPage.tsx:139` 的 `const n = density`、`Plot3DPage.tsx:139` 的 `const n = gridN` 直接用，其上界只由 UI 滑块守（`min={7} max={41}`，`PlotVectorPage.tsx:215`；`min={16} max={96}`，`Plot3DPage.tsx:198`）。所以手改工作区文件可以绕过"n² ≤ 1681 / 9216"这条被 B5 用来论证"可以保持同步"的前提，把一个本该同步的 `expr_eval_grid` 推到大点数。分类：**未实测的潜在风险**（我只做了静态判读，没有构造 `density: 100000` 的工作区去跑），验证方法见 §10 最后一条。对照组说明这不是普遍现象：复平面在消费点夹了 `Math.max(2, Math.min(1000, …))`（`PlotComplexPage.tsx:174`），分形的 `maxSide` 被 `Math.min(1, maxSide / max(cssW,cssH))` 封住（`PlotFractalPage.tsx:149`）。

两个取值域细节：分形的 `scheme` 不做成员校验，但消费点有兜底 `SCHEMES[scheme] || SCHEMES.classic`（`PlotFractalPage.tsx:198`）；几何的 `tool` 也不做成员校验，由 `TOOLS.find(…) || TOOLS[0]` 兜底（`PlotGeometryPage.tsx:101`）。几何还原还必须把 `nextIdRef` 推到下一个空 id（`:88-91`），否则新画的图形会与还原出来的撞 id。

---

## 7. 排障钩子 `window.__mfPlot`

**是什么**：`PlotPage.tsx` 挂在 `window` 上的一个对象，三个读取函数（`:208-212`）：

| 成员 | 返回 |
| --- | --- |
| `view()` | 当前视图 `{x0,x1,y0,y1}` |
| `size()` | 画布尺寸 `{w,h}` |
| `status()` | 采样状态行文本（`status.text`） |

做法与 `__mfWorkspace`（`src/lib/workspace/store.js:211-226`）、`__mfPrefs`、`__mfSanitize`、`__mfPush` 同一套：CDP 够不到 React 的 state，而这些状态恰恰是端到端最需要能读的东西（`PlotPage.tsx:195-203`，`store.js:205-210`）。

**什么时候挂上**：在 `useEffect` 里，**且刻意不写依赖数组**（`:205-214`）—— 每次渲染都重跑，闭包里的 `view/size/status` 才不会过期。后果是：**画布已经在 DOM 里，并不保证钩子已就位**（effect 发生在 DOM 提交之后）。这条不是理论：`tests/cdp-plot-accuracy.mjs:102-105` 记着一次真实事故 —— 读不到钩子时旧版**静默退回**假定的 `±10×±10` 视野，于是几何全错、6 条命中断言集体失败，真因只是一次竞争。现在改法很硬：先等钩子（最多 10 秒，`:106-113`），等不到就直接 `exit 1` 并打印两种可能（React 页没挂起来 / 渲染进程卡住，`:114-120`）。

**为什么必须暴露"视图"**：视图是缩放/平移/"缩放到适应"这类交互**唯一**可观测的结果。只靠数像素证明不了"视图真的变了"（曲线留在原地也可以有像素），于是 B3 那种"按钮点了抛异常、视图纹丝不动"的缺陷没有任何用例抓得住（`:198-201`）。`tests/cdp-plot-accuracy.mjs:226-266` 就是按这个判据写的：`排障钩子 window.__mfPlot 可用` + `点击「缩放到适应」不抛异常` + `「缩放到适应」确实改变了视图`。

**读法有坑**：必须走 `JSON.stringify(window.__mfPlot.view())` 再解析，不能让 CDP 直接序列化那个对象 —— 实测 `returnByValue` 对视图对象会返回 `{}`（同一对象在页面内 `Object.keys` / `JSON.stringify` 都完整），断言会看到"空视图"。`tests/cdp-plot-accuracy.mjs:130-141` 写明了这是**读取方式的坑，不是产品状态坏了**。

**覆盖范围**：只有 2D/极坐标这一页有（全仓库 grep `__mfPlot` 只命中 `PlotPage.tsx` 与 `cdp-plot-accuracy.mjs`）。3D / 复平面 / 向量场 / 几何 / 分形**没有**同类钩子；它们的状态只能靠 DOM 与工作区载荷间接观察。`size()` 与 `status()` 目前**没有任何消费方**（仓库内 grep `__mfPlot.size` / `__mfPlot.status` 零命中），属于"先摆着的出口"。

---

## 8. 冻结的 Vue 绘图组

### 8.1 是哪 6 个文件

`MF_UI/MFMath.UI.Vue/src/views/plot/`（6 文件 2,862 行 / 116,861 字节）：

| 文件 | 字节 | 行 |
| --- | --- | --- |
| `PlotView.vue` | 42,220 | 1,029 |
| `PlotComplexView.vue` | 24,768 | 566 |
| `PlotFractalView.vue` | 16,182 | 416 |
| `PlotGeometryView.vue` | 12,217 | 311 |
| `PlotVectorView.vue` | 11,002 | 276 |
| `Plot3DView.vue` | 10,472 | 264 |

另有 `src/components/plot/`（6 文件 2,673 行 / 101,488 字节：`PlotCanvas.vue` 894、`GeometryCanvas.vue` 679、`VectorFieldCanvas.vue` 315、`SurfaceCanvas.vue` 295、`ExpressionList.vue` 284、`ParamSlider.vue` 206 行），**只被上面这 6 个文件 import**（复跑命令见 §10）。

### 8.2 为什么保留

[BUGS.md](../../MF_UI/BUGS.md) §B9 的两个选项是"删"或"留"。产品决定是**留，作为冻结的回退资产**，代价写清楚在 `src/router/index.js:29-36`：

- 它们**已不再跟随修复** —— React 侧这些轮次改过的东西（缩放适应、极坐标参数识别、精度、异步通道…）那边一概没有；
- 它们**不在构建图里**（没人 import），也**不在类型检查范围**（`tsconfig.json:37` 的 `include` 只有 `src/**/*.ts`，`.vue`/`.js` 不参与）；
- 它们**没有任何用例覆盖**（16 个 `cdp-plot-*.mjs` 打的全是 React 页面，见 §10 的登记数）；
- 所以"把路由那行改回去"**不等于回退到一个能用的版本**，而是回退到一份无人验证的旧码。真要走回退，得先把它们接回来、补跑 `cdp-plot-*` 全套、再删掉冻结断言。

### 8.3 `check-ui.mjs` 怎么禁止它被悄悄接回

`tools/check-ui.mjs:348-409` 的第 6e 项，白名单 `FROZEN_VUE_PLOT_FILES`（`:356-359`）是这 6 个文件名。三条判据：

| 判据 | 失败信息 | 出处 |
| --- | --- | --- |
| 目录里的 `.vue` 必须与白名单**逐一对应**（多一个） | `<f> 不在"冻结的回退资产"白名单里 —— 新增的文件要么挂上路由，要么加进 FROZEN_VUE_PLOT_FILES 并说明` | `:365-368` |
| 白名单里的文件必须**都存在**（少一个） | `冻结白名单里的 src/views/plot/<f> 已不存在 —— 请从 FROZEN_VUE_PLOT_FILES 里删掉` | `:370-372` |
| **没有人 import 它们** | `<f> import 了已冻结的 src/views/plot/* —— 要么真的回退（补跑 cdp-plot-* 全套后再改这条断言与 router 注释），要么撤掉这个 import` | `:374-388` |

引用检查只看真正的 `import`/`from` 语句（正则 `from\s+["'][^"']*views\/plot\/[^"']*["']`，`:382`），所以 `router/index.js:34` 那句"把下面这行改回去"是注释、不会误报；6 个文件**互相**引用也不算（`:379`）。

B9 记载这条守卫**被验证过会失败**（临时造一个 `src/.tmp-importer.js` → 报错、exit 1）。本会话复跑了真实自检，输出是：

```
冻结的 Vue 绘图组    ：6/6 个文件在位，被 import 0 处
```

（2026-10-07 10:5x 本机实测，命令见 §10 第 1 条。）

**守卫的边界**（别把它当成"Vue 绘图组整体被守住了"）：白名单只覆盖 `src/views/plot/*.vue`。`src/components/plot/` 下的 6 个 `.vue` 既不进白名单、也不在引用检查的报错范围内 —— 它们当前只被那 6 个冻结文件引用，但这个事实**没有任何自动检查在守**（§11 第 3 条）。

---

## 9. B13 / B14 / B15：迁移掉的三块，真跑一次才发现

三条的**共同成因**逐字写在同一处：迁移时只搬了渲染层与算法（`@shared/plot/*`），**没搬"与外壳的契约"**（[BUGS.md](../../MF_UI/BUGS.md) §B14 根因段）。而它们是**实跑端到端时新登记的**，不是读代码读出来的（§0.3 开头："以及实跑新登记的 B13 / B14 / B15"）。

| # | 掉了什么 | 现象（用户可见） | 根因 | 怎么证明修好了 |
| --- | --- | --- | --- | --- |
| **B13** | `emphasis` 的**生产方** | 选中某行表达式时，那条曲线不再加粗 | Vue 版 `PlotView.vue:95` 传 `emphasis: row.id === activeId.value`；React 版传的是 `r.emphasis`，而全工程**没有任何地方给 `r.emphasis` 赋过值** ⇒ 恒 `undefined`。注意这不是"字段没人用"，而是"用的人还在、产的人没了"：`PlotCanvas.tsx:224` 仍在读 `c.emphasis ? 4 : 2.5`（另见 `:307`、`:437`） | 现改为 `emphasis: r.id === activeId`（`PlotPage.tsx:152`）；`tsc` 通过，绘图组 12 条套件全绿 |
| **B14** | 与工作区的**契约** | 7 条绘图路由全部存不进工作区：表达式、视野、参数一个都留不下 | 全 `MFMath.UI.React/src` grep `workspace` / `setPage` / `getPage` / `@shared/workspace` **零命中**；包装层 `ReactPlotView.vue` 同样零命中。对照已冻结的 Vue 版：`PlotView.vue:20` 有 import、`:35` 还原、`:701` 回写、`:661` 的 `capturePlot()` | 新增 `lib/plotWorkspace.ts` 并 6 页全接上；`ReactPlotView.vue` 给 2D/极坐标补传 `routePath`。实测 `cdp-workspace` **21/4 → 25/0**、`cdp-shortcuts-prefs` **22/1 → 23/0** |
| **B15** | 结果的**反馈** | 点「导出图片」后界面没有任何反馈：导到哪、成没成都不知道，失败也不说原因 | `PlotPage` 的 `exportImage()` 丢掉 `exportCanvas()` 的返回值；那组文案当时只存在于已冻结的 Vue 视图里，React 侧一条都没有。绕到 2D/极坐标的 `routePath` 还写死成 `"#/plot/2d"`，于是极坐标页导出的默认文件名也是 `plot-2d` | 现在把 `已导出图片：<路径>（尺寸，大小）`/`已取消导出`/`导出失败：<原因>` 写进页内状态行，并改用外层传进来的真路由（`PlotPage.tsx:415-424`）。实测 `cdp-export-image` **43/2 → 45/0** |

三条教训，按可操作的顺序：

1. **"契约"和"结果反馈"也是要搬的东西。** 渲染层搬完、算法共用之后，页面看起来是好的，所以静态检查一无所获 —— B14 的零命中是"全工程 grep 不到"，但没有任何闸门会因为"少了一个 import"而变红。
2. **只修一页不算修完。** B14 要求"各页形状不同，逐页定义并逐个断言，别只修 2D 就以为完了"；B15 要求"六页都要，别只修一页"—— 事后核对的结果是：B15 里另外 5 页**本来就报**导出结果，只有 2D/极坐标漏了；B14 里另外 5 页则是**从头到尾没有过**。
3. **建议的守卫没有全部落地。** B14 建议把"`src/plot/*.tsx` 里出现 `setPage` 的页数必须与绘图路由数一致"写进 `check-ui.mjs`；截至本文核对时间，`check-ui.mjs` 里 grep `plotWorkspace` 与 `src/plot` 都**零命中**（另外两条命中只是注释里出现"绘图"二字，与工作区无关：`check-ui.mjs:350`、`:484`；唯一真正相关的守卫是 B9 的冻结断言 `:348-409`）。也就是说：下一次再迁一页，仍然只有"真跑一遍端到端"能抓住同类漏项。

B15 还有一条**明确说了不做**并给了理由：没给 `ReactPlotView` 接 `onStatusText`。原因是外壳状态栏由 Vue 的 `App.vue` 用 `statusText` ref 持有，React 子树拿不到；硬接要么写 DOM（`#statusText`，会被 Vue 下次渲染覆盖）、要么为此引一个 store/事件通道，收益只是"同一句话多显示一处"，而测试读的本来就是页内状态行。

---

## 10. 怎么验

在仓库根目录下复跑（`pwsh`）：

```powershell
# 1. 冻结的 Vue 绘图组：白名单 6/6 在位、被 import 0 处（会打印那一行）
cd MF_UI\MFMath.UI.Vue; node tools\check-ui.mjs

# 2. 冻结文件与占位组件的确切字节数/行数（本文表格的来源）
Get-ChildItem MF_UI\MFMath.UI.Vue\src\views\plot  -File | % { "{0} {1} {2}" -f $_.Name,$_.Length,(Get-Content $_.FullName).Count }
Get-ChildItem MF_UI\MFMath.UI.Vue\src\components\plot -File | % { "{0} {1} {2}" -f $_.Name,$_.Length,(Get-Content $_.FullName).Count }

# 3. "components/plot 只被冻结文件 import"的复核（输出应只列 views/plot 下的 4 个文件）
Get-ChildItem -Recurse -File MF_UI\MFMath.UI.Vue\src -Include *.vue,*.js,*.ts |
  % { if ((Get-Content $_.FullName -Raw) -match 'components/plot/') { $_.FullName } }

# 4. React 侧类型检查（应为 exit 0；本会话实测通过）
cd ..\MFMath.UI.React; npm run check:types

# 5. 绘图组端到端：16 个 cdp-plot-* 全部登记在 run-all.ps1，另有 cdp-export-image /
#    cdp-workspace / cdp-shortcuts-prefs 覆盖导出与工作区。需要宿主，本会话**没有跑**。
cd ..\MFMath.UI.Vue; .\tests\run-all.ps1 -NoLaunch
(Get-ChildItem tests\cdp-plot-*.mjs).Count                                              # 应为 16
(Select-String tests\run-all.ps1 -Pattern '"cdp-plot-[a-z0-9-]+"' -AllMatches |
  % { $_.Matches.Value } | Sort-Object -Unique).Count                                  # 也应为 16

# 6. §6 那条"未实测的潜在风险"的验法：把工作区里 /plot/vector 的 density 手改成 100000，
#    然后打开 /plot/vector，看是否出现长时间无响应（渲染进程被同步 expr_eval_grid 占住）。
#    判据：能算出 n² 的上限并被拒绝/夹取 → 风险不成立；页面卡死 → 风险成立，记进 BUGS.md。
```

以下三件事本会话**没有**验证，不要当成结论：① 上面第 5 条的端到端结果（需要 Rust 宿主与已构建的 `dist`，我没有跑）；② §6 里 `density` / `gridN` 越界工作区的实际后果（只做了静态判读）；③ 独立 React 外壳（`App.tsx`）里 `routePath` 默认值带来的影响（§11 第 5 条）。

---

## 11. 已知的文档债

按"注释/旧文档说 X，代码做 Y"的格式记；每条都给了复跑方式。

1. **`MF_UI/BUGS.md` §B9 的字节数偏大。** 该节写 `src/views/plot/` "约 127KB"、`src/components/plot/` "约 103KB"；
   实测是 **116,861 字节（114.1 KiB）** 与 **101,488 字节（99.1 KiB）**（命令见 §10 第 2 条）。
   偏大约 10%，两处都不是"约"能盖住的量级。

2. **`MF_UI/BUGS.md` §B9 的行号已漂移。** 该节写 `src/router/index.js:29-38` 把 7 条 `/plot/*` 指向
   `ReactPlotView.vue`、并在 `:28` 找到"要回退就把这行改回去"的注释；实测 7 条路由在
   `src/router/index.js:37-46`，"冻结的回退资产"那段注释在 `:29-36`，而且它已经被改写成
   **事实描述**（原文的"改回去"口径已经不存在了）。B9 的叙述保留的是修复**前**的状态。
   ⚠ 由此推出一条引用规矩：**引 `MF_UI/BUGS.md` 请按章节名（`## B9`、`## 附 D`），不要按行号。**
   本会话核对期间该文件的行数在两次读取之间从 1,115 变成 1,151（当前 1,151，与 `HEAD` 一致），
   期间有并行会话在同一棵树上工作（[AGENTS.md](../../AGENTS.md) §4 记的就是这类并发）。
   另一条独立的漂移证据：B14/B15 引的 `PlotView.vue:20 / :35 / :661 / :701` 今天仍然逐条对得上，
   而 B9 引的 `router/index.js` 行号对不上 —— 所以"引用会过期"是逐个引用都要复核的事，不能一概而论。

3. **冻结守卫只盖住 `views/plot/`，没盖住 `components/plot/`。** `check-ui.mjs:356-359` 的白名单是 6 个
   `views/plot/*.vue`；`src/components/plot/` 下 6 个文件（2,673 行）同样不可达，但删文件、或从冻结区之外
   误接进来，都不会让任何检查变红。§8.3 的"被 import 0 处"这句话**只对 views/plot 成立**。
   复核命令见 §10 第 3 条。

4. **`linspace` 有两份实现。** `MF_UI/MFMath.UI.React/src/plot/usePlotSampling.ts:48-53` 自己写了一份；
   `@shared/plot/sampling.js:11-15` 已导出逐字相同的实现（`:92` 的 `export { linspace }`），
   而同目录的 `Plot3DPage.tsx:7`、`PlotVectorPage.tsx:6` 用的就是共享那份。两份当前一致，但没有任何检查
   保证它们继续一致。它属于 `MF_UI/BUGS.md` 的 `## B12【P4】注释计数过时 / 死导出 / 重复实现` 那一类，
   但 B12 全文**没有提到 `linspace`**（在该文件里 grep `linspace` 零命中），所以这一处是**新登记的**。

5. **独立 React 外壳的 `routePath` 默认值带 `#`，与工作区键的约定不符。**
   `MFMath.UI.React/src/App.tsx:243-244` 渲染 `PlotPage` 时没传 `routePath`，于是用默认值
   `"#/plot/2d"`（`PlotPage.tsx:77`）；而 `src/lib/workspace/store.js:68` 在载入工作区时**只接受以 `/`
   开头的键**，`#/plot/2d` 会被静默丢掉。分类：**产品缺陷的候选，但只影响独立开发壳** ——
   随产品发布的壳是 Vue 的（`MFMath.Host.Rust/tools/sync-wwwroot.mjs:24` 同步的是
   `MFMath.UI.Vue/dist`），所以现有 16 条 `cdp-plot-*`（打的是 Vue 壳里经 `ReactPlotView` 挂载的页面，
   `route.path` 形如 `/plot/2d`）**打不到**这个问题。未实测。

6. **`__mfPlot` 有两个没有消费方的出口。** `PlotPage.tsx:210-211` 暴露了 `size()` 与 `status()`，
   仓库内 grep `__mfPlot.size` / `__mfPlot.status` **零命中**（测试只用 `view()`）。不算缺陷，
   但按"修完就删"的纪律，它们是待定去留的出口 —— 要么补上用例，要么删掉。
