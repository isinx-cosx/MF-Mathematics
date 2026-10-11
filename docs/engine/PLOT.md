# 绘图接口（PLOT）

> 本文说明引擎的绘图接口：绘图相关 action、视口与采样范围、分辨率与迭代上限、同步调用约束。
> 前端六个绘图页与共享绘图库的行为见 [`../ui/PLOT.md`](../ui/PLOT.md)；args 信封与键名契约见 [`CONTRACT.md`](CONTRACT.md)；`digits` 与 `null` 的数值语义见 [`NUMERIC.md`](NUMERIC.md)；action 全表与模块归属见 [`MODULES.md`](MODULES.md)。

## 1. 绘图相关函数

绘图使用的引擎 action 注册在三个文件里。`plot_api.cpp` 与 `fractal_api.cpp` 是绘图专属，`expr_api.cpp` 是绘图热循环借用的通用求值函数。

计数命令：

```powershell
(Select-String -Path MF_Mathematics/plot_api.cpp -Pattern 'register_function\("' | Measure-Object).Count     # 4
(Select-String -Path MF_Mathematics/fractal_api.cpp -Pattern 'register_function\("' | Measure-Object).Count   # 1
```

### 1.1 绘图专属 action

| action | 注册位置 | 必需键 | 可选键（缺省值） | 返回 |
| --- | --- | --- | --- | --- |
| `complex_eval` | `plot_api.cpp` | `expr` | — | `{re, im, isReal}` |
| `complex_eval_many` | `plot_api.cpp` | `exprs`（字符串数组） | — | 对象数组，每项 `{expr, re, im, ok}` 或 `{expr, ok:false, error}` |
| `complex_grid` | `plot_api.cpp` | `expr, x0, x1, y0, y1, nx` | `ny`=`nx`、`digits`=`7`、`var`=`"z"` | `{re, im, nx, ny, ok, nan, x0, x1, y0, y1, maxMag, minMag, unsupported}` |
| `intersections` | `plot_api.cpp` | `expr1, expr2` | `var`=`"x"`、`xmin`=`-50`、`xmax`=`50`、`vars` | `{points, count, method, exact, symbolic, realness, …}` |
| `mandelbrot` | `fractal_api.cpp` | 无 | `xmin`=`-2`、`xmax`=`1`、`ymin`=`-1.5`、`ymax`=`1.5`、`width`=`800`、`height`=`600`、`max_iter`=`100` | 行优先的迭代次数整型数组，长度 `width×height` |

`complex_grid` 返回 `re`/`im` 而非 `mag`/`arg`：共形映射需要 `w` 平面坐标本身，`mag`/`arg` 可由前端一步算出。返回体里 `ok` 是有限值点数，`nan` 是域外点数，`unsupported` 非空表示表达式里有算不出来的成分。

### 1.2 绘图热循环借用的求值函数

| action | 注册位置 | 键 | 用途 |
| --- | --- | --- | --- |
| `expr_eval_vars_batch` | `expr_api.cpp` | `expr, xs`；`var`=`"x"`、`vars` | 一元曲线、极坐标、参数方程、垂直关系、不等式边界的批量取点 |
| `expr_eval_vars` | `expr_api.cpp` | `expr`；`var`=`"x"`、`vars`、同名键或 `values` | 点 `(a,b)` 两个分量各求一次值 |
| `expr_eval_grid` | `expr_api.cpp` | `expr, xs, ys`；`vars` | 隐式方程与二元区域的等值线、3D 曲面、向量场 |

## 2. 视口与采样范围

视口是前端状态，形状是 `{x0, x1, y0, y1}`。引擎不接收「视口」，过桥的只有采样点数组或矩形标量：

| 前端概念 | 过桥形状 | 接收方 |
| --- | --- | --- |
| 一元曲线自变量扫描 | `xs` 数组 | `expr_eval_vars_batch` |
| 二元网格坐标 | `xs`、`ys` 两个数组 | `expr_eval_grid` |
| 复平面矩形 | `x0, x1, y0, y1` 四个标量 | `complex_grid` |
| 分形窗口 | `xmin, xmax, ymin, ymax` | `mandelbrot` |
| 交点搜索区间 | `xmin, xmax` | `intersections` |

### 2.1 一元曲线的采样范围

扫描区间取视口的 1.5 倍，左右各外扩 25%。外扩系数是 `usePlotSampling.ts` 里的 `PAD = 0.25`（定位 `Select-String -Path MF_UI/MFMath.UI.React/src/plot/usePlotSampling.ts -Pattern 'PAD'`）。总跨度是 `sx0 = x0 − 0.25·w`、`sx1 = x1 + 0.25·w`，其中 `w = x1 − x0`。

各表达式类型取哪一段（`usePlotSampling.ts` 的 `sampleAll`）：

| 类型 | 扫描区间 |
| --- | --- |
| `explicit` | `sx0..sx1` |
| `vertical` | `sy0..sy1` |
| `inequality` | 按轴取 `sx*` 或 `sy*` |
| `polar` | 恒为 `0..2π`，与视口无关 |
| `parametric` | `sx0..sx1` |
| `implicit` / `region` | 不外扩，`linspace(x0, x1, 180)` |

`intersections` 是唯一拿到视口语义的调用点：前端把 `xmin: view.x0, xmax: view.x1` 传下去，缺省值 `±50` 只在不传时生效。

### 2.2 一元曲线的采样参数

自适应采样是纯前端算法（`sampling.js`），每轮加密只发一次批量调用。

| 参数 | 值 | 含义 |
| --- | --- | --- |
| `initial` | 300 | 首轮均匀采样点数 |
| `maxRounds` | 3 | 最多加密轮数 |
| `tolPx` | 0.8 | 中点偏离线性插值的屏幕像素阈值 |
| `maxPoints` | 6000 | 点数上限 |

由此每条曲线最多发 `1 + 3 = 4` 次 `expr_eval_vars_batch`；参数方程每轮发 2 次（`x`、`y` 各一次）。

### 2.3 二元网格

隐式方程与二元区域不参与自适应采样，用 `expr_eval_grid` 一次取回整块网格，每轴 180 点（`GRID_N = 180`），共 180×180 = 32400 点。网格坐标数组由前端 `linspace` 生成，铺满视口，不外扩。

### 2.4 域外点的表示

引擎对定义域外的点返回 JSON `null`，前端用 `Number.isFinite` 对原值判断。`Number(null)` 等于 0，先转数值会把域外点画成 `y = 0`。核对命令：

```powershell
MF_Mathematics\build\bin\Release\probe_call.exe expr_eval_vars_batch '{"expr":"ln(x)","var":"x","xs":[-1,0,1],"vars":{}}'
# {"isError":false,"value":[null,null,0]}
```

自适应采样把 `null` 本身插进结果数组，绘制层据此断线，`1/x` 不会横跨渐近线连成竖线。

## 3. 分辨率与迭代上限

### 3.1 网格点数上限

| action | 上限 | 越界行为 |
| --- | --- | --- |
| `complex_grid` | `nx × ny ≤ 400000` | 报错，文案含「超过上限 400000，请降低分辨率（建议 ≤ 600×600）」 |
| `expr_eval_grid` | `xs.length × ys.length ≤ 400000` | 报错「网格点数过多 … 上限 400000」 |

两处上限相同，但坐标约定不同：`expr_eval_grid` 的坐标就是调用方给的数组，`complex_grid` 的坐标由 `x0 + (x1 − x0)·i/(nx−1)` 现算，因此含两端点；`nx==1` 或 `ny==1` 时该维只取起点。

复平面分辨率取 `nx = ny = n`，前端输入框允许到 1000（`min=50 max=1000`），但引擎上限算出可用上界是 632（632² = 399424；633² = 400689 超过 400000）。633–1000 这一段前端放行、引擎拒绝。核对命令：

```powershell
MF_Mathematics\build\bin\Release\probe_call.exe complex_grid '{"expr":"z","x0":-1,"x1":1,"y0":-1,"y1":1,"nx":700,"ny":700}'
```

### 3.2 分形上限

`mandelbrot` 的参数界：

| 参数 | 缺省 | 允许范围 | 越界行为 |
| --- | --- | --- | --- |
| `width` | 800 | `≤ 4000` | 报错「宽度 超出可计算范围 […, 4000]」 |
| `height` | 600 | `≤ 4000` | 报错「高度 超出可计算范围 […, 4000]」 |
| `max_iter` | 100 | `≤ 100000` | 报错「最大迭代次数 超出可计算范围 […, 100000]」 |
| `width × height` | — | `≤ 4000000` | 报错「网格过大 … 上限 4000000」 |

分形按半开区间采样：`c_im = ymin + (ymax−ymin)·py/h`、`c_re = xmin + (xmax−xmin)·px/w`（除以 `h`、`w`，不是 `h−1`、`w−1`），上边界差一格取不到；`complex_grid` 用 `j/(ny−1)` 是闭区间。逃逸判据是 `|z|² ≤ 4`，`iter` 到 `max_iter` 即停，因此集合内部格点的迭代次数恒等于 `max_iter`。前端默认视图是 `x∈[−2,2]` 而引擎缺省 `xmax = 1`；前端每次显式传窗口，缺省值只在裸调用时生效。

## 4. 同步调用约束

同步通道 `engineCall` 是渲染进程主线程上的一次阻塞调用，异步通道 `engineCallAsync` 走宿主 job 通道并轮询。分界线由 `asyncPolicy.js` 的 `shouldRunAsync` 决定，判据是规模估计值而非调用轻重。

| action | 工作量估计式 | 阈值 | 超过阈值时 |
| --- | --- | --- | --- |
| `mandelbrot` | `width × height × max_iter`（`max_iter` 缺省按 256 计） | `1.5e8` | 异步 |
| `complex_grid` | `nx × ny` | `2.5e5` | 异步 |
| `expr_eval_grid` | `xs.length × ys.length` | `2.5e5` | 异步 |
| `matrix_multiply` | `n³` | `2e6` | 异步 |
| 无上界一族 | — | — | 一律异步（`ALWAYS_ASYNC`，含 `solve_sym`、`extrema_sym`、`integrate*` 等） |

定位：`Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern '1.5e8|2.5e5|2e6|ALWAYS_ASYNC'`。

绘图热循环的采样刻意保持同步：每条曲线每次批量调用最多 6000 点，二元网格 32400 点，都低于 `2.5e5` 阈值，`shouldRunAsync` 恒为 `false`。分形页与复平面页按 `shouldRunAsync` 分流，超过阈值走异步并显示进度。

## 5. 核对命令汇总

```powershell
# 引擎 action 总数
MF_Mathematics\build\bin\Release\probe_call.exe list_functions '{}'   # value.count = 424

# 网格上限
MF_Mathematics\build\bin\Release\probe_call.exe complex_grid '{"expr":"z","x0":-1,"x1":1,"y0":-1,"y1":1,"nx":700,"ny":700}'
MF_Mathematics\build\bin\Release\probe_call.exe expr_eval_grid '{"expr":"x*y","xs":[0,1,2],"ys":[0,1]}'

# 分形上限
MF_Mathematics\build\bin\Release\probe_call.exe mandelbrot '{"width":5000,"height":10,"max_iter":10}'
MF_Mathematics\build\bin\Release\probe_call.exe mandelbrot '{"width":2100,"height":2000,"max_iter":100}'
MF_Mathematics\build\bin\Release\probe_call.exe mandelbrot '{"width":10,"height":10,"max_iter":100001}'

# 域外点语义
MF_Mathematics\build\bin\Release\probe_call.exe expr_eval_vars_batch '{"expr":"ln(x)","var":"x","xs":[-1,0,1],"vars":{}}'

# 前端采样与阈值常量
Select-String -Path MF_UI/MFMath.UI.React/src/plot/usePlotSampling.ts -Pattern 'PAD','GRID_N'
Select-String -Path MF_UI/MFMath.UI.Vue/src/lib/engine/asyncPolicy.js -Pattern '1.5e8','2.5e5'
```
