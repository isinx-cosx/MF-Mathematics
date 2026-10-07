# 绘图与分形在引擎侧的契约（`MF_Mathematics/`）

> **本文只回答一个问题：绘图与分形在引擎侧的契约：采样、视口、迭代上限。**
>
> 与同层其它文档的分工：
> - [`CONTRACT.md`](CONTRACT.md) —— args JSON 的通用形状与键名规矩（本文只写绘图/分形这几个 action 的具体键、默认值与上限）；
> - [`MODULES.md`](MODULES.md) —— 424 个 action 的全表与模块归属（本文只筛出绘图相关的那几条，不重复全表）；
> - [`NUMERIC.md`](NUMERIC.md) —— 容差与精度策略（本文只写网格的 `digits` 有效数字，以及它把"有限值"写成 `null` 的那个副作用）；
> - [`TESTS.md`](TESTS.md) —— 19 个可执行目标 / 16 条 CTest 的全貌（本文只指出哪条用例钉住了绘图契约、哪块没钉住）；
> - [`../ui/PLOT.md`](../ui/PLOT.md) —— 前端 6 个绘图页与共享 plot lib 的行为（本文只写它们**调引擎的那一半**）。

**证据基线**：2026-10-07 10:42–10:55 本机实测，仓库 `e65d23c`（`git status --short` 除本次新增的 `docs/engine/` 外干净）。被测产物：`MF_Mathematics/build/bin/Release/mf_mathematics.dll`（LastWriteTime 2026-10-06 05:43:00）、`probe_call.exe`（05:43:03）、`test_complex_grid.exe`（05:43:05）。`build/` 不入 git（[`AGENTS.md`](../../AGENTS.md) §6）⇒ **换产物就要重跑，别把本文数字当现状**；下文每个数字都附可复跑命令。

---

## 1. 结论先行：五条契约

| 维度 | 契约 | 依据 |
| --- | --- | --- |
| **视口** | 引擎**没有**"视口"这个概念。视口 `{x0,x1,y0,y1}` 是前端状态；过桥时只剩"采样区间的两个端点"（`xs`/`ys` 数组）或"矩形两个角"（`x0/x1/y0/y1`、`xmin/xmax/ymin/ymax`） | `plot_api.cpp:241-250`、`plot_api.cpp:341-342`、`fractal_api.cpp:24-27`、`usePlotSampling.ts:100-106` |
| **采样范围** | 一元曲线的扫描区间 = 视口跨度的 **1.5 倍**（左右各外扩 25%），参数名就是 `PAD = 0.25` | `usePlotSampling.ts:43,100-102`；Vue 同值 `PlotView.vue:170-173` |
| **二元网格** | 网格**不外扩**，正好铺满视口；`xs.length × ys.length > 400000` 直接报错，不降分辨率 | `usePlotSampling.ts:206-207`、`expr_api.cpp:145-148`、`plot_api.cpp:252-256` |
| **分形上限** | `width/height ≤ 4000`、`max_iter ≤ 100000`、`width×height ≤ 4000000`；越界**报错**并说明上限 | `fractal_api.cpp:28-37` |
| **同步/异步** | 判据是**规模**不是"重不重"：`mandelbrot > 1.5e8`、`complex_grid / expr_eval_grid > 2.5e5` 才走后台通道；绘图页"每条曲线一次"的采样**刻意保持同步** | `asyncPolicy.js:19-32,12-15` |

一句话：**引擎侧的根本约束是"一次调用能回传多少个数"**（网格 400000 点、分形 4000000 格），而不是屏幕上的那点像素。

---

## 2. 引擎侧的绘图 action 清单（可复跑）

```powershell
# ① 引擎自己认哪些函数（唯一真相在注册表里）
MF_Mathematics/build/bin/Release/probe_call.exe list_functions | ConvertFrom-Json | Select-Object -ExpandProperty value |
  Select-Object count, @{n='n';e={$_.functions.Count}}      # count=424

# ② 按「注册文件」筛出绘图相关的那几条
$S = "MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json"
$j = Get-Content $S -Raw | ConvertFrom-Json; $props = $j.PSObject.Properties
foreach ($f in 'plot_api.cpp','fractal_api.cpp') {
  "=== $f ==="
  $props | Where-Object { $_.Value.file -eq $f } | ForEach-Object { $_.Name }
}

# ③ 表与源码对账（进 npm run check）
node MF_UI/MFMath.UI.Vue/tools/engine-signatures.mjs --check    # ✓ 无漂移，exit 0
```

结果（`plot_api.cpp` 4 条 + `fractal_api.cpp` 1 条）：

| action | 注册位置 | 必需键 | 可选键（默认值） | 谁在调（现役 = React 绘图组） |
| --- | --- | --- | --- | --- |
| `complex_eval` | `plot_api.cpp:180` | `expr` | — | 函数工具箱模式（`engineMapExtra.js:191,351`）；复平面页**不**调它 |
| `complex_eval_many` | `plot_api.cpp:200` | `exprs` | — | **全仓库无调用点**（见 §10 债 3） |
| `complex_grid` | `plot_api.cpp:241` | `expr, x0, x1, y0, y1, nx` | `var`=`"z"`、`ny`=`nx`、`digits`=`7` | `PlotComplexPage.tsx:165-171`（规模 >2.5e5 走异步） |
| `intersections` | `plot_api.cpp:336` | `expr1, expr2` | `var`=`"x"`、`xmin`=`-50`、`xmax`=`50`、`vars` | `PlotPage.tsx:263-269`（**带 `xmin/xmax`＝当前视口 x 范围**） |
| `mandelbrot` | `fractal_api.cpp:23` | 无 | `xmin`=`-2`、`xmax`=`1`、`ymin`=`-1.5`、`ymax`=`1.5`、`width`=`800`、`height`=`600`、`max_iter`=`100` | `PlotFractalPage.tsx:153-176` |

⚠ 绘图热循环实际调用的 action 有一半**不在这两个文件里**（它们按数学门类归在 `expr_api.cpp`）：

| action | 注册位置 | 绘图侧用途 | 规模上界 |
| --- | --- | --- | --- |
| `expr_eval_vars_batch` | `expr_api.cpp:218` | 一元曲线/极坐标/参数方程/垂直关系/不等式的**批量取点** | 每批 ≤ 6000（`sampling.js:34`），每曲线 ≤ 4 批（`sampling.js:41`） |
| `expr_eval_vars` | `expr_api.cpp:172` | 拖动点吸附、`(a,b)` 点坐标 | 1 点/次 |
| `expr_eval_grid` | `expr_api.cpp:136` | 隐式方程/二元区域的等值线、3D 曲面、向量场 | 180²=32400 / 96²=9216 / 41²=1681×2 |
| `local_extrema` / `extrema_sym` | `calculus/calculus_api.cpp` / `symbolic_api.cpp` | 绘图页侧栏的极值标注（`PlotPage.tsx:298,314`） | 无上界 ⇒ `extrema_sym` 属 `ALWAYS_ASYNC`（`asyncPolicy.js:45`） |

---

## 3. 视口 `{x0,x1,y0,y1}`：视口止步于前端

**引擎侧没有任何一个 action 收"视口"**。过桥的只有四种东西：

| 前端概念 | 过桥后的形状 | 谁收 | 端点含不含 |
| --- | --- | --- | --- |
| 视口 x/y 跨度 | `xs`/`ys` 两个**坐标数组**（一元曲线是自变量扫描点） | `expr_eval_vars_batch`、`expr_eval_grid` | 由前端 `linspace` 决定 |
| 复平面矩形 | `x0,x1,y0,y1` 四个标量 | `complex_grid` | **含两端**：`i/(nx-1)`（`plot_api.cpp:290,292`） |
| 分形窗口 | `xmin,xmax,ymin,ymax` | `mandelbrot` | **半开**：`py/h`、`px/w`（§6） |
| 交点搜索区间 | `xmin,xmax` | `intersections` | 含两端（`numeric_roots` 从 `x0` 扫到 `x1`，`plot_api.cpp:96-101`） |

**1.5 倍采样范围**的换算（两处实现逐字同值）：

```js
const PAD = 0.25;                                   // usePlotSampling.ts:43（Vue 写死在 PlotView.vue:171）
const padX = viewW(view) * PAD, padY = viewH(view) * PAD;
const sx0 = view.x0 - padX, sx1 = view.x1 + padX;   // 总跨度 = 1.5 × 视口跨度
const sy0 = view.y0 - padY, sy1 = view.y1 + padY;
```

各表达式类型取哪一段（React 现役实现，`usePlotSampling.ts`）：

| 类型 | 扫描区间 | 行号 |
| --- | --- | --- |
| `explicit` | `sx0..sx1` | `:161-166` |
| `vertical` | `sy0..sy1` | `:155-160` |
| `inequality` | 按轴取 `sx*` 或 `sy*` | `:170-176` |
| `polar`（`r=f(θ)`） | **恒为 `0..2π`**，与视口无关 | `:141-147` |
| `parametric` | React 用 `sx0..sx1`；Vue 用 `0..2π` | `:148-154` vs `PlotView.vue:234-240` |
| `implicit` / `region` | **不外扩**：`linspace(view.x0, view.x1, 180)` | `:206-207`；Vue 同 `PlotView.vue:294-295` |

**为什么是 1.5 倍**（收益）：小幅平移时曲线不断裂——视口一动，边缘那 25% 已经在手，不必等一次重采样。
**代价与已修**：这 25% 里的离群值会被"缩放到适应"当成数据。`PlotPage.tsx:379-381` 写明了实测后果——`e^x` 在 `x=15` 处 `y≈3.3e6`，等比修正把量级搬到另一轴，`x0` 变成 `-2.7e6`、整条曲线塌成一条线。现在的两道闸：
① 只喂**当前视口内**的采样点（`PlotPage.tsx:386-404`，视图内少于 2 点才退回全部有限点）；
② `fitBounds` 的等比修正有 `MAX_STRETCH = 8` 上限（`view.js:118-131`）。

> 注意：`intersections` 是唯一拿到"视口"语义的调用点——`PlotPage.tsx:268` 把 `xmin: view.x0, xmax: view.x1` 直接传下去，而引擎缺省是 `±50`（`plot_api.cpp:341-342`）。**不传就等于按 ±50 搜**，与当前视图无关。

---

## 4. 一元曲线的采样契约

自适应采样是一个纯前端算法（`MF_UI/MFMath.UI.Vue/src/lib/plot/sampling.js`，两个工程共用同一份），它决定**什么时候、发多少次、每次多少个点**去问引擎：

| 参数 | 值 | 含义 | 依据 |
| --- | --- | --- | --- |
| `initial` | 300 | 首轮均匀采样点数 | `sampling.js:31` |
| `maxRounds` | 3 | 最多加密轮数 | `sampling.js:32` |
| `tolPx` | 0.8 | 中点偏离线性插值的**屏幕像素**阈值 | `sampling.js:33` |
| `maxPoints` | 6000 | 点数上限 | `sampling.js:34` |
| 调用点 | `usePlotSampling.ts:121`、`PlotView.vue:256` | 两处逐字同值 | — |

由此推出三条可核对的契约：

1. **引擎调用次数**：每轮加密**只发一次批量调用**（`sampling.js:41-48`）⇒ 每条曲线最多 `1 + 3 = 4` 次 `expr_eval_vars_batch`。参数方程每轮发 2 次（x、y 各一次，`usePlotSampling.ts:150-153`）。这正是 [`asyncPolicy.js:12-15`](../../MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js) 要求"绘图页保持同步"的理由：一条一个 `await` 会把时序拆碎。
2. **长度契约**：`batchEval` 要求返回值是数组且 `length === ts.length`，否则**整轮当没有数据**（返回 `null`），不补齐、不截断、不猜（`usePlotSampling.ts:56-62`）。
3. **域外点 = `null`**：引擎对定义域外的点返回 JSON `null`（`expr_api.cpp:229` 的 `safe_eval_point` 逐点容错）。实测：

```powershell
MF_Mathematics/build/bin/Release/probe_call.exe expr_eval_vars_batch '{"expr":"ln(x)","var":"x","xs":[-1,0,1],"vars":{}}'
# {"isError":false,"value":[null,null,0]}
```

前端**必须**用 `Number.isFinite(原值)` 判，不能先 `Number(x)`——`Number(null) === 0`，会把域外点画成 `y=0`（`usePlotSampling.ts:64-72`、`PlotView.vue:155-164`）。同理，中点为 `null` 时必须**把 null 本身插进结果数组**（`sampling.js:58-67`），否则 `1/x` 会在渐近线处连出一条竖线。

**实测批耗时**（`probe_call.exe`，2026-10-07；口径 = 全进程，含约 10 ms 启动；同一算例跑 3 次取最快）：

| 批量点数 | 表达式 | 最快耗时 |
| --- | --- | --- |
| 300（首轮） | `a*sin(x)+x^2/10` | 13 ms |
| 3000 | 同上 | 18 ms |
| 6000（`maxPoints` 上限） | 同上 | 24 ms |
| 20000 | 同上 | 53 ms |
| 100000 | 同上 | 224 ms |

⇒ 扣掉启动基线后，单条曲线的采样是**毫秒级**，"保持同步"成立。

---

## 5. 二元网格与复网格

两者共用同一个点数上限 `400000`，但坐标约定不同：

| | `expr_eval_grid`（实值网格） | `complex_grid`（复值网格） |
| --- | --- | --- |
| 键 | `expr, xs, ys, vars?`（`expr_api.cpp:136-140`） | `expr, x0,x1,y0,y1,nx, ny?, var?, digits?`（`plot_api.cpp:241-250`） |
| 上限 | `xs.size()×ys.size() > 400000` 报错（`:145-148`） | `nx×ny > 400000` 报错，文案建议 ≤600×600（`:252-256`） |
| 坐标 | 数组即坐标，`xs[i]`/`ys[j]` | 由 `x0+(x1-x0)*i/(nx-1)` 现算 ⇒ **含两端**（`:290,292`）；`nx==1`/`ny==1` 时该维只取起点 |
| 行优先 | 外 `y` 内 `x`（`expr_api.cpp:153-159`） | 外 `j(y)` 内 `i(x)`（`plot_api.cpp:289-291`） |
| 域外点 | `null`（逐点容错，`expr_api.cpp:157`） | `null` **且 `nan++`**（`plot_api.cpp:300-307`） |
| 返回 | 一个扁平数值数组 | `{re,im,nx,ny,ok,nan,x0,x1,y0,y1,maxMag,minMag,unsupported}`（`:318-333`） |
| 有效数字 | 无（原值 `double`） | `digits` 默认 7 位有效数字（`:250,273-287`） |
| 前端调用点 | `usePlotSampling.ts:208`、`Plot3DPage.tsx:148`、`PlotVectorPage.tsx:147-148` | `PlotComplexPage.tsx:175-177` |
| 前端规模 | 180²=32400（`usePlotSampling.ts:46`）、96²=9216（`Plot3DPage.tsx:198`）、41²=1681 ×2（`PlotVectorPage.tsx:215`） | `resolution²`（`:174`） |

`complex_grid` 把 `re`/`im` 分开返回**而不是** `mag`/`arg`，理由写在该 action 的头注释里：共形映射需要 `w` 平面的坐标本身，`mag/arg` 由前端一步就能算，反推则拿不回 `w`（`plot_api.cpp:16-17`）。返回的 `nan` 是域外点计数、`ok = total - nan`，`unsupported` 用来暴露"表达式里有算不出来的东西"，让前端不至于对着空白图猜（`:300-307,323-324,331-332`）。

### 5.1 复平面分辨率：前端允许到 1000，引擎在 633 起必然报错

| 环节 | 值 | 依据 |
| --- | --- | --- |
| 前端输入框 | `min=50 max=1000 step=10` | `PlotComplexPage.tsx:588`（Vue 同值 `PlotComplexView.vue:530`） |
| 前端夹取 | `Math.min(1000, resolution)`，且 `nx = ny = n` | `PlotComplexPage.tsx:174-177` |
| 前端提示 | `resolution > 600` 才警告"可能需要十几秒" | `PlotComplexPage.tsx:151,593` |
| 引擎上限 | `nx*ny ≤ 400000` | `plot_api.cpp:253-256` |
| **算术结论** | `nx = ny = n` 时可用上界是 **632**（632² = 399424 ≤ 400000；633² = 400689 > 400000） | 由上一行直接推出 |

实测（本文口径，`probe_call`）：

```powershell
probe_call.exe complex_grid '{"expr":"z","x0":-5,"x1":5,"y0":-5,"y1":5,"nx":1000,"ny":1000}'
# {"isError":true,"value":"网格点数 1000×1000 超过上限 400000，请降低分辨率（建议 ≤ 600×600）"}
probe_call.exe complex_grid '{"expr":"z","x0":-1,"x1":1,"y0":-1,"y1":1,"nx":700,"ny":700}'
# {"isError":true,"value":"网格点数 700×700 超过上限 400000，请降低分辨率（建议 ≤ 600×600）"}
probe_call.exe complex_grid '{"expr":"z","x0":-1,"x1":1,"y0":-1,"y1":1,"nx":400,"ny":400}'
# isError=false, ok=400*400=160000, nan=0
```

⇒ 分辨率 **633–1000 这一段前端放行、引擎必拒**（失败分类：产品缺陷——两端口径不一致；不是用例判据错，也不是环境问题）。1000×1000 的具体可达性没有端到端实测，但引擎侧的拒绝由上面第一条命令钉死。

---

## 6. 分形：分辨率与迭代上限

`mandelbrot` 是引擎里唯一的分形 action（`fractal_api.cpp:23`），纯 C++、不依赖 SymEngine：

| 参数 | 默认 | 允许范围（含端点） | 越界时的行为 |
| --- | --- | --- | --- |
| `xmin`/`xmax`/`ymin`/`ymax` | `-2` / `1` / `-1.5` / `1.5` | 无界（`get_double_opt`） | — |
| `width` | 800 | `≤ 4000` | 报错：`宽度 超出可计算范围 […, 4000]：收到 5000。…` |
| `height` | 600 | `≤ 4000` | 同上（`高度`） |
| `max_iter` | 100 | `≤ 100000` | 报错：`最大迭代次数 超出可计算范围 […, 100000]：收到 100001。…` |
| `width×height` | — | `≤ 4000000` | 报错：`网格过大：2100×2000 = 4200000 个点，上限 4000000。分形结果要逐点回传，请降低分辨率。` |

依据：`fractal_api.cpp:24-37`。三条错误串都是 2026-10-07 用 `probe_call.exe mandelbrot '<json>'` 实跑出来的原文。

**返回与着色分工**：返回 `width*height` 个**迭代次数**（`to_int_array`，`fractal_api.cpp:53,56`），行优先、第 0 行对应 `ymin`；配色/平滑/翻转全在前端（`PlotFractalPage.tsx:190-220`）。这符合三条纪律②：**引擎只出数，颜色不是数学**。

**两个必须知道的坐标约定细节**（都直接由源码的式子推出，不是注释转述）：

1. 分形按 **半开区间** 采样：`c_im = ymin + (ymax-ymin)*py/h`、`c_re = xmin + (xmax-xmin)*px/w`（`fractal_api.cpp:41,43`，注意是 `/h`、`/w` 而不是 `/ (h-1)`）。所以 `py` 取到 `h-1` 时 `c_im = ymax - (ymax-ymin)/h` —— **上边界永远取不到**，差一格。而 `complex_grid` 用 `j/(ny-1)`（`plot_api.cpp:290`）是**闭区间**。同一块复平面上，两个 action 的取样点相差不到一格，但约定相反。
2. 逃逸判据是 `|z|² ≤ 4`，`iter` 到达 `max_iter` 即停（`fractal_api.cpp:46`）。所以"迭代次数"在集合内部恒等于 `max_iter`，前端用 `it >= mi` 判内部（`PlotFractalPage.tsx:207`）——阈值必须与传下去的 `max_iter` 一致，否则内部与外部会串色。

**前端规模换算**（`PlotFractalPage.tsx:148-156`）：`scale = min(1, maxSide / max(cssW, cssH))`，`w,h = round(css·scale)` 且下钳 32。滑块上界 `maxSide ≤ 1200`（`:311`）、`maxIter ≤ 1024`（`:306`）、默认 `560` / `256`（`:107,111`）⇒ 最坏一档 `1200×1200×1024`，`cells = 1.44e6 < 4e6`（引擎允许）、工作量估计 `1.475e9 > 1.5e8`（必然走异步，`:165`）。

**默认窗口的口径差**：引擎缺省 `xmax = 1`（`fractal_api.cpp:25`），而前端默认视图是 `x∈[-2,2]`（`PlotFractalPage.tsx:27`）。因为前端**每次都显式传** `xmin/xmax`（`:154`），缺省值只在裸调用 `probe_call mandelbrot '{}'` 时生效——写文档/写用例时别把两者当成同一个默认。

---

## 7. 同步 / 异步的分界线，以及 `2.5e5` 的来历

同步通道 `engineCall(name, args)` 是 `mf.Dispatch` 的一次阻塞调用，**占住渲染进程主线程**（[`bridge.js:127-136`](../../MF_UI/MFMath.UI.Vue/src/lib/bridge.js)）；异步通道 `engineCallAsync` 走宿主 job 通道并轮询（`bridge.js:160-233`）。分界线写在 [`asyncPolicy.js`](../../MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js)：

| action | 工作量估计式 | 阈值 | 超过阈值 ⇒ | 依据 |
| --- | --- | --- | --- | --- |
| `mandelbrot` | `width×height×max_iter`（`max_iter` 缺省 256） | `1.5e8`（注释标"≈400 ms"） | 异步 | `asyncPolicy.js:20,28` |
| `complex_grid` | `nx×ny` | `2.5e5`（注释标"500×500"） | 异步 | `asyncPolicy.js:21,29` |
| `expr_eval_grid` | `xs.length×ys.length` | `2.5e5` | 异步 | `asyncPolicy.js:22,30` |
| `matrix_multiply` | `n³` | `2e6` | 异步 | `asyncPolicy.js:23,31` |
| 无上界一族 | — | 一律异步 | 异步 | `ALWAYS_ASYNC`，含 `extrema_sym`、`solve_sym`、`integrate*`（`:39-49`） |

### 7.1 阈值的来历链

- **可追溯的一环**：`asyncPolicy.js:8-10` 记录了一次实测——`mandelbrot 600×600×256 = 9.2e7 → 248 ms`，据此换算 `约 3.7e8 次迭代/秒`，于是 `1.5e8 ≈ 400 ms` 被定为"还能忍"的上限。（9.216e7 ÷ 0.248 ≈ 3.716e8，算式自洽。）
- **`2.5e5` 这一环**：代码里只有注释 `// 500×500`（`:29`），**没有任何实测记录**。除本文之外，全仓库命中 `2.5e5` 的只有 14 处，全是引用/解释，**没有一处给出"2.5e5 点耗时多少"**：

```powershell
Get-ChildItem -Recurse -File -Include *.js,*.ts,*.tsx,*.vue,*.mjs,*.md,*.json |
  Where-Object { $_.FullName -notmatch '\\(node_modules|build|\.cargo-home|dist|\.git|\.tmp-build)\\' -and $_.Name -ne 'PLOT.md' } |
  Select-String -Pattern '2.5e5' -SimpleMatch | Measure-Object     # Count = 14
# 明细：asyncPolicy.js:29,30；usePlotSampling.ts:201,203；Plot3DPage.tsx:144,146；
#       PlotVectorPage.tsx:145,146；PlotComplexPage.tsx:161；BUGS.md:140,571；
#       ../DESIGN.md:122；../link/README.md:115；../link/JOBS-PUSH.md:94
```

（`-and $_.Name -ne 'PLOT.md'` 是为了把本文自己排除掉；含本文时为 23 处。）
- **本文的独立实测**（`probe_call`，2026-10-07；含 ~10 ms 启动）：`expr_eval_grid` 在 `450×450 = 202500` 点（≈2.5e5 档）耗时 **225 ms**；`500×500 = 250000` 点**无法用 `probe_call` 验证**——它的接收缓冲是 4 MiB（`probe_call.cpp:33`），250000 个 `double` 的 JSON 超过该容量，返回 `调用失败：缓冲区不足或参数非法`。⇒ `2.5e5` 与"≈400 ms 上限"的链条**方向一致**（量级对得上），但它不是一个被测出来的数，而是取了个整（500×500）。

### 7.2 必须保持同步的清单（绘图热循环）

| 调用点 | 规模（算术） | 为什么不接异步 |
| --- | --- | --- |
| `usePlotSampling.ts:56-62` `batchEval`（每曲线最多 4 批、每批 ≤6000） | ≤6000/批 | `asyncPolicy.js:12-15` 明文要求；一条一个 `await` 拆碎采样时序 |
| `usePlotSampling.ts:200-208` 二元网格 | 180² = 32400 < 2.5e5 ⇒ `shouldRunAsync` 恒 false | `usePlotSampling.ts:200-203` |
| `Plot3DPage.tsx:139-148` 曲面网格 | ≤96² = 9216 | `Plot3DPage.tsx:142-147` |
| `PlotVectorPage.tsx:145-148` 向量场双网格 | ≤41² = 1681 ×2 | `PlotVectorPage.tsx:145-146` |

对应地，**必须异步**的两处：分形页 `PlotFractalPage.tsx:165-176`、复平面页 `PlotComplexPage.tsx:160-171`（都按 `shouldRunAsync` 分流并显示进度）。

### 7.3 分形耗时的实测（与 `asyncPolicy.js:9-10` 的 248 ms 不一致）

| 算例 | 工作量估计 `w×h×max_iter` | 实测（`probe_call`，含启动与 stdout 序列化） |
| --- | --- | --- |
| `600×600×64` | 2.304e7 | 414 / 485 / 336 ms |
| `600×600×256` | 9.216e7 | 413 / 480 / 421 ms |
| `1200×1200×1024` | 1.47456e9 | 1974 ms |

两点判读（**不是**缺陷结论）：

1. 本机这一档是 413–480 ms，而不是 `asyncPolicy.js:9` 记的 248 ms。口径不同：`probe_call` 是**另一个进程**，含启动与把 360000 个整数写进管道的开销，而 248 ms 那一条应当是引擎内部计时。⇒ 248 ms **属未证实**（本文未能用同一口径复现），见 §9。
2. `max_iter` 从 64 提到 256（估计式涨 4 倍），600×600 的墙钟时间**没有变化**（同量级、抖动还更大）。原因在算法本身：`fractal_api.cpp:46` 一旦 `|z|²>4` 就停，绝大多数格点几步就逃逸，真实迭代数远小于 `w×h×max_iter`。⇒ **`w×h×max_iter` 只是"规模估计式"，不是真实迭代次数**；用它排序轻重是可靠的，用它推算毫秒数不可靠。

---

## 8. 复算命令汇总

```powershell
# 0) 基线
git rev-parse --short HEAD                                   # e65d23c（本文口径）
Get-ChildItem MF_Mathematics/build/bin/Release/*.dll,MF_Mathematics/build/bin/Release/probe_call.exe |
  Select-Object Name,LastWriteTime                           # mf_mathematics.dll 2026-10-06 05:43:00

# 1) 动作全集与绘图动作（§2）
MF_Mathematics/build/bin/Release/probe_call.exe list_functions | ConvertFrom-Json | % { $_.value.count }   # 424
node MF_UI/MFMath.UI.Vue/tools/engine-signatures.mjs --check                                                # 无漂移, exit 0

# 2) 网格上限与复平面分辨率（§5）
MF_Mathematics/build/bin/Release/probe_call.exe complex_grid '{"expr":"z","x0":-1,"x1":1,"y0":-1,"y1":1,"nx":700,"ny":700}'
MF_Mathematics/build/bin/Release/probe_call.exe complex_grid '{"expr":"z","x0":-5,"x1":5,"y0":-5,"y1":5,"nx":1000,"ny":1000}'
MF_Mathematics/build/bin/Release/probe_call.exe expr_eval_grid '{"expr":"x*y","xs":[0,1,2],"ys":[0,1]}'      # 不带 x/y 也能成功

# 3) 分形上限（§6）
MF_Mathematics/build/bin/Release/probe_call.exe mandelbrot '{"width":5000,"height":10,"max_iter":10}'
MF_Mathematics/build/bin/Release/probe_call.exe mandelbrot '{"width":2100,"height":2000,"max_iter":100}'
MF_Mathematics/build/bin/Release/probe_call.exe mandelbrot '{"width":10,"height":10,"max_iter":100001}'

# 4) 域外点语义（§4）
MF_Mathematics/build/bin/Release/probe_call.exe expr_eval_vars_batch '{"expr":"ln(x)","var":"x","xs":[-1,0,1],"vars":{}}'

# 5) 契约用例（§2 / §10）
MF_Mathematics/build/bin/Release/test_complex_grid.exe            # 153 项检查，0 项失败
MF_Mathematics/build/bin/Release/test_complex_grid.exe --strict   # 同上（已知缺陷计数为 0）
Select-String -Path MF_Mathematics/tests/*.cpp -Pattern 'mandelbrot','fractal' -SimpleMatch   # 0 处命中
```

---

## 9. 未证实 / 待验证

| # | 条目 | 为什么没证实 | 怎么验 |
| --- | --- | --- | --- |
| 1 | `asyncPolicy.js:9` 的 `mandelbrot 600×600×256 → 248 ms` | 本文只有 `probe_call` 全进程口径（413–480 ms），没有引擎内部计时口径；宿主里还有一次 JSON 往返 | 在宿主机上跑一次分形页，读状态行 `引擎 mandelbrot 600×600 · N ms`（`PlotFractalPage.tsx:236`），或给引擎加内部计时 |
| 2 | `2.5e5` 是否真是"还能忍"的临界 | 250000 点的调用**无法用 `probe_call` 发**（4 MiB 缓冲，`probe_call.cpp:33`）；202500 点测得 225 ms 只是邻档 | 用宿主通道或更大的缓冲跑 `complex_grid 500×500` / `expr_eval_grid 500×500`，记录同步耗时与是否触发"未响应" |
| 3 | 分辨率 633–1000 在**界面上**的表现（是报错文案、还是空白） | 只验证了引擎会拒绝（§5.1），没跑端到端。前端把引擎错误串**原样**抛进状态行（`PlotComplexPage.tsx:179` throw → `:517-520` `setStatusText(e.message)`，无截断） | 起宿主打开复平面页，分辨率填 700 点"重绘"，看状态行是否出现引擎那句"超过上限 400000" |
| 4 | `parametric` 的自变量区间 React(`sx0..sx1`) 与 Vue(`0..2π`) 哪个对 | 两处代码可读、结论明确，但**没跑端到端**；`docs/README.md:129` 把 Vue 绘图组记为"冻结的回退资产" | 打开 2D 页输入一条参数方程（如 `(cos(t), sin(t))`），把视图平移到远离原点，看曲线是否跟着变 |
| 5 | 分形半开区间的肉眼后果（上/右边界差一格） | 由 `fractal_api.cpp:41,43` 的式子直接推出，未做像素级比对 | 用 `RESET` 视图导出 PNG，比对最上一行像素对应的 `c_im` 与 `ymax` |
| 6 | `complex_grid` 在 `digits ≥ 10` 且值极小时的残余缺陷窗口 | 只验证了 `digits=10` + `1e-300` 一个点（见 §10 债 1），没扫边界 | 按 `floor(log10\|v\|) < digits-309` 取几个点，跑 `probe_call complex_grid` 看 `re` 是否为 `null` 而 `nan=0` |

---

## 10. 已知的文档债

> 规矩见 [`AGENTS.md`](../../AGENTS.md) §5：注释可能是错的，**以代码为准**。下面每一条都给了"注释/文档说 X、代码做 Y"和证据命令。

1. **`digits ≥ 10` 把精确 0 写成 `null`——这条"已知缺陷"已经不复现，但注释与用例分类没跟着改。**
   - 注释说 X：`plot_api.cpp:274-282` 写"0 必须原样返回……边界实测：digits≤9 正常，10~17 坏"；`tests/test_complex_grid.cpp:658-665` 与 `:741-744` 仍把它列为"⑦ 已知引擎缺陷（记录，不计入失败）"，并说"digits ≥ 10 时**任何恰好为 0 的分量**都会被当成域外点"。
   - 代码做 Y：`plot_api.cpp:283` 有一句早退 `if (v == 0.0) return 0.0;`，恰好为 0 的分量根本不会走到溢出那条路。
   - 证据：`probe_call complex_grid '{"expr":"z","x0":0,"x1":0,"y0":0,"y1":0,"nx":1,"ny":1,"digits":10}'` → `"re":[0],"im":[0],"nan":0`；`test_complex_grid.exe --strict` → `153 项检查，0 项失败`，且**没有**打印 `另有 N 项已知引擎缺陷`（该行只在 `g_known_bugs > 0` 时打印）。
   - 残余窗口（真实存在、不在用例里）：`mag = 10^(digits-1-floor(log10|v|))` 溢出当且仅当 `floor(log10|v|) < digits-309`。`digits=10` 时是 `|v| < 1e-299`，实测这一档：`probe_call complex_grid '{"expr":"1e-300","x0":0,"x1":0,"y0":0,"y1":0,"nx":1,"ny":1,"digits":10}'` → `"re":[null]`、`"nan":0`、`"ok":1`，即"`null` 与 `nan` 不可区分"的老问题在极小非零值上仍在；同点换 `digits=9` → `"re":[1e-300]` 正常。
2. **`test_complex_grid.cpp` 的 ⑦ 节现在只起"记录历史"的作用**：`CHECK_KNOWN` 全部通过 ⇒ `g_known_bugs == 0` ⇒ `:742` 那句总结性文案永远不会打印。留着不删就等于摆设（[`AGENTS.md`](../../AGENTS.md) §5 第 4 条）。
3. **`complex_eval_many` 没有调用点**：`plot_api.cpp:199` 的注释写它存在的理由是"一次转多个根，**减少桥调用次数**"，但源码侧只有两处命中——注册处 `plot_api.cpp:200` 与签名表 `engine-signatures.json:855`——**没有调用点**，"减少桥调用"这个收益没有兑现。构建产物里还有几份副本（`MFMath.Host.Rust/target/*/wwwroot/assets/index-*.js:302`，签名表被打进前端包），但那不是调用：

```powershell
Get-ChildItem -Recurse -File -Include *.js,*.ts,*.tsx,*.vue,*.cpp,*.h,*.rs,*.json |
  Where-Object { $_.FullName -notmatch '\\(node_modules|build|target|dist|bin|obj|\.cargo-home|\.git|\.tmp-build)\\' -and $_.Name -ne 'PLOT.md' } |
  Select-String -Pattern 'complex_eval_many' -SimpleMatch        # 仅 plot_api.cpp:200 与 engine-signatures.json:855
```
4. **`engine-signatures.json` 的 `required` 不能当"必填"读**——本文实测了两条反例（该表在 [`docs/README.md`](../README.md):52 被登记为"参数键名的权威源"）：
   - `expr_eval_grid` 表里 `required = [expr, xs, ys, x, y]`，但代码只读 `expr/xs/ys` 三键（`expr_api.cpp:136-140`）：`probe_call expr_eval_grid '{"expr":"x*y","xs":[0,1,2],"ys":[0,1]}'` → `{"isError":false,"value":[0,0,0,0,1,2]}`。
   - `expr_eval_vars` 表里 `required = [expr, values]`，但 `expr_api.cpp:183-203` 还接受"与 `var` 同名的键"：`probe_call expr_eval_vars '{"expr":"t^2+a","var":"t","t":3,"vars":{"a":1}}'` → `10`。
   - 生成器自己也承认判据是单向的：`node tools/engine-signatures.mjs --check` 打印 `✓ 无漂移`（exit 0）的同时，在 `提示（不判定失败）124 处` 里明确列出 `expr_eval_grid: 表里的「y」/「x」/「vars」未能在源码里刮到`、`expr_eval_vars: 表里的「values」/「vars」未能在源码里刮到`（判据范围见 `engine-signatures.mjs:21-23`，刮取规则见 `:68-116`）。同一结论见 [`../../MF_UI/BUGS.md`](../../MF_UI/BUGS.md):970-976（B 面附注 5）。
5. **`PlotFractalPage.tsx:200-203` 引用的行号是错的**：注释说"引擎行主序：第 0 行 = ymin（数学下方，见 `MF_Mathematics/fractal_api.cpp:30-31`）"，但产生 `c_im` 的是 `fractal_api.cpp:41`；`:30` 是 `max_iter` 的读取行、`:31` 是空行。行号漂了约 10 行（结论本身没错）。
6. **`sampling.js` 的 JSDoc 与实现不符**：`:18` 把回调签成 `(ts:number[]) => Array<[number,number]>`，而 `:58-67` 的实现**把 `null` 当"这里断开"并把它插进结果数组**。React 侧已在 `usePlotSampling.ts:8-26` 用自己的类型重声明并注明，`sampling.js:18` 的原注释没改。
7. **`intersections` 的测试覆盖面偏窄**：引擎侧只有 `test_symbolic_contract.cpp` 的 `test_intersections_realness()`（`:72-91`，9 条 `CHECK`）真正断言行为，外加 `:181` 一条"名字在 `list_functions` 里"的登记检查；而 `mandelbrot`/分形**没有任何引擎用例**——`Select-String -Path MF_Mathematics/tests/*.cpp -Pattern 'mandelbrot','fractal' -SimpleMatch` 命中 0 处。§6 那张上限表目前只有本文的手工复算命令钉着，没有回归网（用例登记口径见 [`TESTS.md`](TESTS.md)）。
