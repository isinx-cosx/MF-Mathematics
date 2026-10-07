# MF-Mathematics v2.0 功能全表

> **本文只回答一个问题：软件的功能全表。**
>
> 与同层其它文档的分工：
> - [`../ui/ARCHITECTURE.md`](../ui/ARCHITECTURE.md) —— 前端分层、路由表与导航表的完整结构；本文只用它的路由结论；
> - [`../ui/ENGINE-BINDING.md`](../ui/ENGINE-BINDING.md) —— 界面怎么把参数接到引擎（`ENGINE_MAP` / `calcArgs` / 可达性守门）；本文只报数字，不重复规则；
> - [`../ui/PLOT.md`](../ui/PLOT.md)、[`../ui/TOOLS.md`](../ui/TOOLS.md)、[`../ui/AI.md`](../ui/AI.md)、[`../ui/TUTORIAL-KEYPAD.md`](../ui/TUTORIAL-KEYPAD.md)、[`../ui/SETTINGS-WORKSPACE.md`](../ui/SETTINGS-WORKSPACE.md) —— 各分区的实现细节与已知缺陷；本文给"有什么、边界在哪、数字怎么来的"；
> - [`../DESIGN-BOUNDARIES.md`](../DESIGN-BOUNDARIES.md) —— 哪些"没有"是**有意不做**、哪些是**推迟**；本文每条边界都指回它的小节。

**核对时间**：2026-10-07 · 本机 Windows · Node v26.3.1（`node -v` 实测）
**权威源**：`MF_UI/MFMath.UI.Vue/src/lib/router/nav.js`、`src/router/index.js`、`src/lib/engine/viewConfigs.js`、`src/lib/settings/catalog.js`、`src/lib/ai/engine-signatures.json`、`src/tutorials/tutorials.json`、`src/components/`、`MF_UI/MFMath.UI.React/src/plot/`

本文的每一个数字都出自 **§7 的可复跑命令**。没有跑过的写"未证实"（§8），**不写估计值**。

## 0. 一张表看全

| 分区 | 入口 | 规模（实测） | 权威源 |
| --- | --- | --- | --- |
| **学科计算** | 侧栏「计算模式」**15** 项 | 基础运算 1 页 + 学科视图 **14** 个，共 **393** 条模式（去重 **391** 个名字） | `nav.js:22-38`；`viewConfigs.js:13-530` |
| **绘图** | 侧栏「绘图模式」**7** 项 | 7 条路由落在 **6** 个页面组件上（2D 与极坐标共用一页） | `nav.js:48-56`；`router/index.js:68-76` |
| **工具** | 侧栏「工具」**3** 项 + 顶栏 1 个对话框 | 搜索 / 控制台 / 函数工具箱；函数工具箱列 **424** 个引擎 action（其中 **53** 个不在任何页面模式表里） | `nav.js:61-74`；`ToolboxView.vue:3` |
| **AI** | 顶栏「AI」按钮（右侧抽屉）+ 两处「查看步骤」 | 助手 2 个工具（`engine_find` / `engine_call`）、轮次上限 4、单轮调用上限 8 | `ai/tools.ts:183-214`；`ai/bridge.js:685-694` |
| **学习** | 侧栏「帮助」**2** 项 + 全局数学键盘 + F1 | **18** 篇教程 / **66** 步 / **52** 示例 / **42** FAQ；引导目标 **30**（已实现 30）；键盘 **6** 分类 **126** 键 | `tutorials.json`；`check-ui.mjs` 输出 |
| **系统** | 侧栏底部「设置」+ 顶栏（计算 / 绘图 / 搜索 / AI / 主题 / 键盘 / 历史 / 设置 / 账号） | 设置 **9** 组 / **57** 项；工作区按路由分页；绘图可导出 PNG | `settings/catalog.js:17-112`；`lib/workspace/store.js`；顶栏各项位置见 [`TUTORIAL-KEYPAD.md`](../ui/TUTORIAL-KEYPAD.md) §5.5 |
| **首页** | `/` | 桥状态 + 3 项引擎冒烟 + 一步 `expr_eval` 试算 | `HomeView.vue:24-40` |

> 导航项总数 **27**（`calc 15 / plot 7 / tools 3 / help 2`，§7 ①）。全局路由数 = 27 + `/tutorial/:id` + `/settings` + `/account` + `/`（`router/index.js:96-137`）。

## 1. 学科计算（14 个视图 + 基础运算）

### 1.1 为什么是"15 个入口、14 份视图配置"

| 事实 | 出处 |
| --- | --- |
| 侧栏「计算模式」有 **15** 项：基础运算、代数计算、微积分、解析几何、数列、线性代数、概率论与数理统计、数值分析、数论、实分析、泛函分析、复分析、代数拓扑、测度论、调和分析 | `nav.js:22-38` |
| 其中 **14** 项走同一个 `CalcView`，按路由末段读 `VIEW_CONFIGS` 的配置 | `router/index.js:79-95`（`CALC_ROUTES` 14 项）；`CalcView.vue:40-42` |
| **基础运算** 不走 `CalcView`，是独立计算器页 | `router/index.js:25`（`REAL_VIEWS["/calc/basic"]`） |

**基础运算页**（`BasicCalcView.vue`）：30 键计算器（`BasicCalcView.vue:22-29`，5 列 × 6 行），按键拼课本写法（`×` `÷` `−` `√` `π`）→ `prepare_expr` 规范化 → 引擎 `expr_eval` 求值（`BasicCalcView.vue:8-9,145`）。页面上会显示"引擎理解为 …"（规范化后的式子）。它的"最近计算"读的是全局历史（`BasicCalcView.vue:57`，只取本页前 8 条），不是自己一份内存列表。

### 1.2 14 个视图的模式全表（数准的版本）

| 视图（路由末段） | 标题 | 模式数 | 模式（逐字，与 `viewConfigs.js` 一致） | 出处 |
| --- | --- | --- | --- | --- |
| `algebra` | 代数计算 | **59** | 解方程/组、解不等式/组、解一元二次、解方程、判别式、韦达定理、解分式方程、解无理方程、解线性不等式、解二次不等式、表达式化简、化简分式、化简根式、因式分解、展开、排列数、组合数、二项式展开、二项式通项、绝对值、数轴距离、比与比例、百分数、百分变化率、科学记数法、有效数字、三角函数求值、三角恒等式、三角周期性、函数定义域、函数值域估计、线性函数、二次函数、二次函数极值、幂函数、指数函数、对数函数、提取公因式、完全平方公式、平方差公式、十字相乘法、分组分解法、通分、分式运算、分母有理化、同类根式判定、根式运算、组合恒等式、对应法则、斜率截距、反比例函数、不等式性质、最值初步、加法原理、乘法原理、交换律验证、结合律验证、分配律验证、AM-GM不等式 | `:14`，模式 `:17-85` |
| `calculus` | 微积分 | **57** | 求导、某点导数、高阶导数、偏导、隐函数求导、不定积分、定积分、广义积分、重积分、不定重积分、三重积分、不定三重积分、极限、单侧极限、无穷极限、连续性判定、泰勒展开、级数展开、幂级数、单调性、凹凸性、拐点、渐近线、极值、最值、平均值、弧长、旋转体体积(圆盘)、旋转体体积(壳)、曲线间面积、曲率、曲率半径、Rolle定理、Lagrange中值定理、Cauchy中值定理、洛必达法则、一阶ODE、高阶ODE、ODE系统、ODE数值解、一阶PDE、二阶PDE、Fourier级数、Fourier系数、复Fourier系数、Fourier变换、逆Fourier变换、参数方程求导、数值积分、微分、幂级数收敛半径、莱布尼茨判别法、极限比较判别法、积分判别法、直接比较判别法、p-级数判别法、综合判别与分类 | `:136`，模式 `:139-200` |
| `probability` | 概率论与数理统计 | **39** | 条件概率、独立性、全概率公式、贝叶斯公式、伯努利分布、二项分布、泊松分布、均匀分布、指数分布、正态分布、期望、方差、协方差、相关系数、大数定律、中心极限定理、样本均值、样本方差、矩估计、MLE、置信区间、z检验、t检验、卡方检验、p值、单因素ANOVA、双因素ANOVA、Mann-Whitney U、Kruskal-Wallis、Wilcoxon符号秩、移动平均、指数平滑、线性趋势、线性回归、预测、残差、分布函数、概率质量函数、概率密度函数 | `:406`，模式 `:409-449` |
| `linear-algebra` | 线性代数 | **32** | 高斯消元、矩阵秩、求解方程组、零空间、特征值、特征向量、特征多项式、可对角化、对角化、点积、范数、夹角、向量正交性、施密特正交化、正交投影、二次型、正定性判定、向量空间判定、线性组合、线性无关判定、基、维数、张成子空间、线性变换、矩阵表示、核、像、秩-零化度、逆矩阵、标准化、负定判定、不定判定 | `:276`，模式 `:280-312` |
| `functional-analysis` | 泛函分析 | **29** | Lp范数、Banach空间、Hilbert空间、线性算子、算子范数、谱半径、Hahn-Banach定理、一致有界原理、开映射定理、闭图像定理、内积空间、正交性、正交投影、弱收敛、弱*收敛、紧算子、特征值问题、Fredholm二择一、Riesz表示定理、共轭算子、自伴算子判定、有界性判定、线性泛函求值、核的维数、对偶空间基、自反性判定、谱逼近、谱定理、空间完备性 | `:238`，模式 `:241-273` |
| `complex-analysis` | 复分析 | **26** | 复数运算、复共轭、复模长、复辐角、复函数值、全纯判定、Cauchy积分、留数、Laurent级数、围道积分、共形映射、Riemann ζ、Dirichlet η、零点与极点、复指数、复对数、复平方根、莫比乌斯变换、奇点分类、留数定理、Zeta 解析延拓、Zeta 函数方程、Zeta 非平凡零点、柯西定理、辐角原理、Rouche 定理 | `:203`，模式 `:206-235` |
| `numerical` | 数值分析 | **25** | 条件数、截断误差、舍入误差、稳定性判断、拉格朗日插值、牛顿插值、三次样条、最小二乘拟合、梯形法则、辛普森法则、高斯求积、数值求导、最优步长、LU分解、雅可比迭代、高斯-赛德尔、共轭梯度、幂法、QR算法、欧拉方法、RK4、隐式欧拉、刚性检测、梯度下降、相图 | `:374`，模式 `:377-403` |
| `measure-theory` | 测度论 | **24** | σ-代数判定、生成σ-代数、Borel σ-代数、外测度、Caratheodory可测、勒贝格测度、测度性质、可测函数判定、简单函数、阶梯函数逼近、简单函数积分、非负函数积分、一般勒贝格积分、零测集无关性、单调收敛定理、Fatou引理、控制收敛定理、乘积测度、Fubini定理、概率空间、随机变量(测度论)、期望(测度论)、条件期望、独立性判定 | `:315`，模式 `:318-343` |
| `number-theory` | 数论 | **21** | 最大公约数、扩展欧几里得、模逆元、模幂、欧拉函数、约数个数、约数和、莫比乌斯函数、中国剩余定理、原根、离散对数、埃氏筛、分段筛、素数判定、素因数分解、连分数、连分数逼近、最佳有理逼近、欧拉乘积、Dirichlet L 函数、伯努利数 | `:346`，模式 `:349-371` |
| `harmonic-analysis` | 调和分析 | **20** | 傅里叶变换、逆Fourier变换、傅里叶级数、傅里叶系数、复傅里叶系数、卷积、卷积定理、小波变换、短时傅里叶变换、低通滤波器、高斯模糊、正交性验证、高斯函数傅里叶变换、δ 分布、缓增分布、普兰舍利定理、泊松求和、不确定性原理、Theta 函数、函数方程演示 | `:503`，模式 `:506-528` |
| `algebraic-topology` | 代数拓扑 | **18** | 基本群、单连通判定、路径同伦、单纯复形、边界算子、同调群、贝蒂数、贝蒂数（复形）、欧拉示性数、上同调群、杯积、庞加莱对偶、映射度、Brouwer不动点定理、毛球定理、过滤复形、持续同调图、条形码 | `:88`，模式 `:91-113` |
| `real-analysis` | 实分析 | **18** | 数列极限(ε-N)、数列收敛判定、柯西收敛准则、ε-δ 极限定义、导数定义、一致连续、介值定理、极值定理、上确界、下确界、黎曼可积判定、达布和、微积分基本定理、一致收敛、逐点收敛、Weierstrass M-判别、逐项微分、逐项积分 | `:452`，模式 `:455-475` |
| `analytic-geometry` | 解析几何 | **13** | 两点距离、中点坐标、斜率、直线方程、圆标准方程、圆一般方程、椭圆方程、双曲线方程、抛物线方程、斜截式直线、点斜式直线、截距式直线、直线一般式 | `:116`，模式 `:119-133` |
| `sequences` | 数列 | **12** | 等差数列第n项、等比数列第n项、数列求和、数列求积、无穷级数求和、无穷乘积、级数收敛判定、级数绝对收敛、数列通项、等差数列求和、等比数列求和、递推数列 | `:477`，模式 `:480-493` |
| | **合计** | **393** 条 / **391** 个不同名字 | `逆Fourier变换`、`正交投影` 各出现在两个视图（§7 ②） | `viewConfigs.js:13-530` |

所有视图的 `single` 都是 `false`（`viewConfigs.js` 每段的 `"single": false`）——**每个视图都允许放多个计算块**。

### 1.3 一道题在页面上能做的事（14 个视图共用）

| 能力 | 做什么 | 边界 / 出处 |
| --- | --- | --- |
| 计算块 | 表达式输入（MathLive 排版输入框）+ 模式下拉 + 计算 + 删除，可加多块 | `CalcView.vue:2-3`；模式下拉内容来自 §1.2 |
| 参数弹窗 | 需要额外参数（如梯形法则的 a/b/n）时先弹窗，用户自定义 | `CalcView.vue:5`（`VAR_SPECS` **139** 项，§7 ③）；弹窗组件 `components/calc/MultiVarDialog.vue` |
| 结果对话框 | 结果用 KaTeX 排版（分数/根式/绝对值不再靠 ASCII 近似），可复制原始 JSON | `components/calc/ResultDialog.vue:2-10` |
| 查看步骤 | 把这道题交给 AI 逐步调引擎讲解（不是模型自己写步骤） | `CalcView.vue:22,412-429`；语义见 §4 |
| 后台通道 | 重活（积分、级数、符号求解…）自动走后台，否则同步调用会占满主线程 | `CalcView.vue:6`；判据在 `engine/asyncPolicy.js`，见 [`ENGINE-BINDING.md`](../ui/ENGINE-BINDING.md) |
| 未映射模式的提示 | 模式没有引擎映射时明确说"引擎未提供该模式的接口"，**不静默** | `CalcView.vue:7` |
| 工作区 | 自动存"表达式 + 模式"（**不存结果**），载入时模式不在本页就落回第一个 | `CalcView.vue:56-84`，见 [`SETTINGS-WORKSPACE.md`](../ui/SETTINGS-WORKSPACE.md) §5.4 |
| 历史 | 成功与失败都记（失败 `ok:false`），去重按 `route + mode + expr` | [`TOOLS.md`](../ui/TOOLS.md) §3.1 |
| 撤销 / 重做 | `Ctrl+Z` / `Ctrl+Y`（与上面那份历史**不是同一份**记录） | `CalcView.vue:27`（`registerUndoable`）；快捷键表见 [`TUTORIAL-KEYPAD.md`](../ui/TUTORIAL-KEYPAD.md) §4 |

**边界**：计算页的**结果不进历史**（历史只记 `expr`/`mode`/`summary` 摘要，`summary` 截断 300 字符 —— [`TOOLS.md`](../ui/TOOLS.md) §3.1）；页面上能选到的模式受 §1.2 那张表约束（引擎有、页面没挂的模式只能在**函数工具箱**里调，§1.4）。

### 1.4 模式可达性：415 / 391 / 24（三个必须一起读的数字）

| 数字 | 含义 | 复跑 |
| --- | --- | --- |
| **415** | `ENGINE_MAP` + `EXTRA_MAP` 里的模式总数 | 自检打印"映射 415 个"（§7 ④） |
| **391** | 14 个视图模式表的**并集**（去重后） | 自检打印"页面并集 391 个"（§7 ④） |
| **0** | 判定为"取不到"的模式数 —— 因为下面那 24 个名字的**功能**能由同 `fn` 的页面模式代替 | 自检打印"取不到 0 个"（§7 ④） |
| **24** | 名字在任何页面都**选不到**的模式（功能可达），逐个登记在 `check-ui.mjs:330-344` 的 `DUPLICATE_NAME_GROUPS` | 自检打印"已登记 24 个，未登记 0 个"（§7 ④） |

那 24 个名字（§7 ③ 的差集，与登记表逐条一致）：化简、中点、两点式直线、全局最值、局部极值、幂级数展开、回路积分、柯西积分公式、洛朗级数、旋转体体积(圆盘法)、旋转体体积(柱壳法)、等差数列、等比数列、级数求和、级数敛散性、内积(泛函)、谱分类、逆傅里叶变换、Lp 范数、Zeta 级数、Banach 空间判定、Hilbert 空间判定、Hahn-Banach 延拓、解不等式组。

> 判据的边界（`check-ui.mjs:329` 原文）：只对"`fn` 已被页面覆盖"的名字要求登记；`fn` 完全没人覆盖的仍判硬失败。**"功能可达"不等于"这个名字在界面上存在"** —— 用户按旧名去下拉里找，是找不到的。

## 2. 绘图（6 类）

### 2.1 7 个入口 = 6 类页面

| 导航项 | 路由 | React 页面 | 画布 | 工作区 `kind` |
| --- | --- | --- | --- | --- |
| 2D 函数绘图 | `/plot/2d` | `PlotPage.tsx` | `PlotCanvas` | `plot` |
| 极坐标 | `/plot/polar` | `PlotPage.tsx`（`gridMode="polar"`） | `PlotCanvas` | `plot` |
| 3D 曲面 | `/plot/3d` | `Plot3DPage.tsx` | `SurfaceCanvas` | `plot3d` |
| 复平面 | `/plot/complex` | `PlotComplexPage.tsx` | 页内自有 canvas | `plot-complex` |
| 向量场 | `/plot/vector` | `PlotVectorPage.tsx` | `VectorFieldCanvas` | `plot-vector` |
| 自由几何 | `/plot/geometry` | `PlotGeometryPage.tsx` | `GeometryCanvas` | `plot-geometry` |
| 分形 | `/plot/fractal` | `PlotFractalPage.tsx` | 页内自有 canvas | `plot-fractal` |

出处：导航 `nav.js:48-56`；7 条路由全指向同一个包装组件 `ReactPlotView.vue`（`router/index.js:37-46`）；路由→页面键 `REACT_PAGES`（`router/index.js:68-76`）；`kind` 见 [`SETTINGS-WORKSPACE.md`](../ui/SETTINGS-WORKSPACE.md) §5.3。

### 2.2 每一类做什么

| 类 | 做什么 | 边界 |
| --- | --- | --- |
| 2D 函数 | 多表达式曲线（显式/极坐标/参数/竖直/不等式/隐式/区域/点）分区采样；参数滑块 | 未支持的类型记为错误"React 绘图版暂未支持该类型（\<type\>）"（[`PLOT.md`](../ui/PLOT.md) §4） |
| 极坐标 | 与 2D 同一页，进入即用极坐标网格（导航项带 `grid:"polar"`，`nav.js:50`） | 与 2D 共用工作区键与 `kind`，靠页面键区分（§5.3） |
| 3D 曲面 | 曲面 / 线框、旋转缩放、网格密度、定义域 | — |
| 复平面 | 复函数按模式着色，分辨率可调 | 模式存的是**下标**，越界归 0（`SETTINGS-WORKSPACE.md` §5.3） |
| 向量场 | `dx/dy` 两分量场、密度、归一化、按模着色、箭头缩放 | — |
| 自由几何 | 图形对象（`shapes[{id,type,data}]`）+ 工具 + 吸附 | 还原时 `id` 必须有限、`data` 必须是数组（`SETTINGS-WORKSPACE.md` §5.3） |
| 分形 | 迭代次数、配色方案、平滑着色、最大边长 | 视野必须 `xmin<xmax && ymin<ymax`，否则该字段丢弃 |

采样用的是**同一份**逻辑层：`MFMath.UI.Vue/src/lib/plot/`（React 侧经 `@shared` 别名引用，不存在两套算法 —— [`PLOT.md`](../ui/PLOT.md) §3）。

### 2.3 绘图区共有的能力与边界

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 导出图片 | 6 个绘图页都有导出按钮（多数是 `⤓`，复平面是"导出图片"按钮）：离屏按 `max(2, devicePixelRatio)` 重画、铺不透明底色、文件名 `页面名-时间戳.png`，结果写进页面状态行 | `lib/plot/exportImage.js:53-115`；`PlotPage.tsx:627`、`PlotComplexPage.tsx:596-597` |
| 导出的是"放大位图" | 像素数是 2×，**细节不是**（`drawImage` 放大已渲染位图，不是按 2 倍分辨率重绘） | `exportImage.js:11-13` |
| 导出失败/取消都有回显 | 三种结果都写状态行：已导出（含路径与尺寸）/ 已取消 / 导出失败（带原因） | `PlotPage.tsx:419-422` |
| 工作区 | 存表达式、视野、参数、模式等**输入**；不存采样、交点、极值、分形像素 | `SETTINGS-WORKSPACE.md` §5.1、§5.3 |
| 绘图操作**不入历史** | 有意推迟，不是漏做：与"历史"的语义边界未定（"哪些绘图操作算一步"没定义） | [`DESIGN-BOUNDARIES.md`](../DESIGN-BOUNDARIES.md) §2 第 6 条；[`TOOLS.md`](../ui/TOOLS.md) §3.4 |
| ⚠ 冻结的 Vue 绘图页 | `src/views/plot/` 6 个文件是**冻结的回退资产**：不在构建图、不在类型检查、无用例覆盖 —— **改路由指回去不等于回退到可用版本** | `router/index.js:29-36`；`check-ui.mjs:348-372`；[`MF_UI/BUGS.md`](../../MF_UI/BUGS.md) B9 |

## 3. 工具（搜索 / 控制台 / 函数工具箱 / 历史）

### 3.1 形态：3 个路由页 + 1 个对话框

| 名称 | 形态 | 入口 | 载体 |
| --- | --- | --- | --- |
| 搜索 | 路由页 `/tools/search` | 侧栏「工具 → 搜索」；顶栏「搜索」 | `views/tools/SearchView.vue` |
| 控制台 | 路由页 `/tools/console` | 侧栏「工具 → 控制台」 | `views/tools/ConsoleView.vue` |
| 函数工具箱 | 路由页 `/tools/toolbox` | 侧栏「工具 → 函数工具箱」 | `views/tools/ToolboxView.vue` |
| 历史 | **模态对话框**（不占侧栏、无路由） | 顶栏「历史」按钮 | `components/history/HistoryDialog.vue` |

出处：[`TOOLS.md`](../ui/TOOLS.md) §0（含端到端断言位置）。

### 3.2 函数工具箱：424 个 action 的可达入口

| 数字 | 值 | 命令 / 出处 |
| --- | --- | --- |
| 引擎 action 总数（= 签名表条目 = 本页函数数） | **424** | §7 ⑤（`源码 register_function 424 条 / 表 424 条`） |
| 界面模式表覆盖到的 `fn` | **371** | §7 ⑥ |
| 不在任何页面模式表里的 action（本页"只看不在模式表里的"筛出的条数） | **53** | §7 ⑥ |
| 按 `file` 顶层目录分出的模块组 | **18** | §7 ⑦；`ToolboxView.vue:39-44` |
| 无参数的 action | **9** | §7 ⑧ |
| 参数类型名 | **15** 种 | §7 ⑧ |
| 一个 action 的参数项合计 | 963 项 | §7 ⑧ |

18 个模块与各自的 action 数（§7 ⑦）：`algebra 79`、`probability 40`、`calculus 35`、`linear_algebra 32`、`complex_analysis 30`、`real_analysis 28`、`extras 25`、`numerical 25`、`number_theory 24`、`measure_theory 24`、`harmonic_analysis 22`、`functional_analysis 21`、`algebraic_topology 17`、`expr_api 9`、`symbolic_api 7`、`plot_api 4`、`introspect_api 1`、`fractal_api 1`（合计 424）。

**用户能做什么**：按函数名/模块名/参数名过滤 → 表单按签名表生成（必填/可选与类型都标出）→ 直接调用 → 显示引擎信封原文（**本页不解读结果**）。
**边界**：空白参数一律不发（让引擎用默认值）；结构型参数要填 JSON，填错由引擎报准确原因；无宿主时只列出函数、不能调用（按钮禁用）；本页**没有任何自动化覆盖**（[`TOOLS.md`](../ui/TOOLS.md) §6 第 1 条，属"未证实"）。

### 3.3 控制台：在应用里写 Python / C++ 小算程

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 语言 | `python`（默认）与 `cpp`；**`cpp` 只在组件就绪时出现在下拉里** | `ConsoleView.vue:58-62` |
| 计算仍然只来自引擎 | Python 侧 `mfmath`（ctypes）、C++ 侧导入库；界面自己不算任何数学 | `ConsoleView.vue:8-11` |
| 编辑器 | CodeMirror 6，按语言懒加载；失败回退 `<textarea>`；补全候选来自引擎 `list_functions`（C++ 模式 = 8 个内置 `mfm::` 名 + 424 个引擎函数名） | [`TOOLS.md`](../ui/TOOLS.md) §1.2 |
| 运行 | 每次运行都是**新进程**（变量不跨次保留）；输出/错误各上限 256 KiB；`终止` 真杀进程树 | [`TOOLS.md`](../ui/TOOLS.md) §1.4 |
| 组件 | CPython / MinGW 可选下载安装，带断点续传与 SHA-256 校验 | [`link/FEATURES.md`](../link/FEATURES.md) §5 |
| 示例 | Python 3 个、C++ 3 个 | `ConsoleView.vue:95-213` |

**边界（两条现在就会碰到）**：① 站点上两个组件 zip **尚未上传**（[`../OPEN-ITEMS.md`](../OPEN-ITEMS.md):119），所以"点安装 → 下载 → 装好"这条路径**没有成功记录**；② `cpp.ready` 只查两件文件而运行要三件 —— 会出现"下拉里有 C++、一跑就报组件不完整"（[`link/FEATURES.md`](../link/FEATURES.md) §5.5）。

### 3.4 搜索：联网取结果，但只取一页

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 引擎 | `duckduckgo`（默认，免密钥）/ `wolfram`（需 App ID）/ `custom`（SearXNG 形状端点） | [`link/FEATURES.md`](../link/FEATURES.md) §1.1 |
| 结果条数 | 宿主配置，默认 **8**，钳在 1–20；搜索页**不能**改（设置 → 搜索里改） | [`TOOLS.md`](../ui/TOOLS.md) §4.2 |
| 缓存 | 键含引擎，TTL 可配（0 = 不过期），上限 **200** 条；`noCache:true` 只跳过读 | [`link/FEATURES.md`](../link/FEATURES.md) §1.3 |
| 失败分类 | 6 类：`config` / `network` / `http` / `parse` / `timeout` / `aborted`，每类给出"下一步做什么" | [`link/FEATURES.md`](../link/FEATURES.md) §1.2 |
| 查询发往哪里 | 面板头部明说端点与隐私说明 | `SearchView.vue:114-117` |
| 「算这个」 | 只是**建议**：命中候选表达式才出现，点了把原文送进 `/calc/basic`，由引擎算 | [`TOOLS.md`](../ui/TOOLS.md) §4.4 |

**有意不做**：不翻页、不抓网页正文（只用引擎给的 snippet）、不做请求去重/限流/退避（[`link/FEATURES.md`](../link/FEATURES.md) §1.5；[`DESIGN-BOUNDARIES.md`](../DESIGN-BOUNDARIES.md) §1 第 6 条）。

### 3.5 历史：全局的一本账

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 记什么 | `route` / `mode` / `expr` / 结果摘要（截断 300 字符）/ `ok`；成功与失败都记 | [`TOOLS.md`](../ui/TOOLS.md) §3.1 |
| 存哪 | 宿主 `sys` 键值存储 → `%LOCALAPPDATA%\MFMath\settings\history.json`；无宿主降级 `localStorage` | `lib/history/store.js:7-9,68` |
| 上限 | **200** 条，超了从尾部丢；同 `route+mode+expr` 去重并置顶 | `store.js:21,79-102` |
| 面板 | 搜索（空格分词全命中）、点一条回填并跳转、逐条删除、清空全部（二次确认）、`Esc` 关闭 | [`TOOLS.md`](../ui/TOOLS.md) §3.3 |
| 不记 | **绘图页操作**（§2.3）、控制台运行输出 | [`TOOLS.md`](../ui/TOOLS.md) §3.1 |

## 4. AI（助手与步骤推导）

### 4.1 两个给人看的界面

| 界面 | 做什么 | 出处 |
| --- | --- | --- |
| AI 助手（顶栏「AI」按钮打开的右侧抽屉） | 多轮对话、流式输出、思维链、工具块（引擎徽标 + 函数名 + 参数 + 结果 + 耗时）、隐私开关、"将发送的内容"预览 | `components/ai/AiPanel.vue:214-234,293,301`；[`AI.md`](../ui/AI.md) §3 |
| 步骤推导（`StepViewer`） | 编号步骤 = **这一轮里 AI 调引擎的记录**（函数 / 参数 / 完整结果 / 状态），失败步骤标红并保留 | `components/ai/StepViewer.vue:3,47-94`；[`AI.md`](../ui/AI.md) §9 |
| 渲染安全 | 模型输出走 token 树 + 模板插值，**没有一处 `v-html`**；链接点了是复制而不是导航 | `components/ai/AiInline.vue:2-5,24-26` |

**"步骤"的语义必须说准**：它不是"模型写的推导过程"，而是 `engine_call` 的调用记录 —— 引擎信封里**没有 `steps` 字段**，所以"直接从引擎拿步骤"做不到；让模型自己编步骤就是伪造推导，直接违反纪律②（[`AI.md`](../ui/AI.md) §9）。

### 4.2 硬约束：AI 不承担计算

| 机制 | 值 | 出处 |
| --- | --- | --- |
| 暴露给模型的工具 | **只有 2 个**：`engine_find`（找函数）、`engine_call`（调函数） | `ai/tools.ts:183-214` |
| 工具能碰的桥 | **只走 `engineCall`**（`mf.Dispatch`），绝不碰 `win`/`sys`/`con` | `ai/tools.ts:11-12,310` |
| 工具目录的权威源 | 引擎签名表 **424** 条（不是从 `ENGINE_MAP` 反推） | `ai/tools.ts:45-117` |
| 轮次上限 | **4** 轮（到顶如实说明，不继续烧） | `ai/bridge.js:685,818-828` |
| 单轮工具调用上限 | **8** 个（超限不执行，但每个都回一条结果） | `ai/bridge.js:686-694,838-883` |
| 回给模型的单条结果 | 截断到 **3000** 字符（界面仍显示完整值） | `ai/tools.ts:220-225` |
| 系统提示 | 写死"所有计算由 C++ 引擎完成，你只做解释" | `ai/bridge.js:529-536` |
| 红线用例 | 假端点故意回 `1+1=3`；断言结果区仍是引擎的 `2` | `tests/cdp-ai.mjs:717,725,727-728` |

### 4.3 运行方式与边界

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 谁发请求 | **页面自己** `fetch`（不是宿主）；宿主只注册 9 个对象，**没有 `ai`** | [`AI.md`](../ui/AI.md) §2 |
| 端点闸门 | 只接受 http/https 绝对地址、路径必须单个 `/` 开头、结果必须与 `baseUrl` 同源；**绝不"不认识就退回内置站点"** | `ai/relay.ts:67-107`；[`AI.md`](../ui/AI.md) §6 |
| 取消的语义 | "停止等待"，**不是撤回请求**（该计费的照旧） | `ai/relay.ts:222-232` |
| 密钥 | 存 `settings\ai.json` 的 `apiKey`，**明文**；界面文案必须如实说"没有加密" | `ai/bridge.js:8-11,278-294`；[`AI.md`](../ui/AI.md) §5 |
| 凭据不进备份 | 导出与诊断都整份排除 `ai`/`account`/`search`，包里写明 `excluded`/`stripped` | `lib/settings/io.js:31,114,122-131` |
| 附带代价 | `StoreDelete` 只删 `.json`，`ai.json.bak` 里可能残留明文密钥 | [`link/CREDENTIALS.md`](../link/CREDENTIALS.md) §2.3 |

**未证实**：只实测过 DeepSeek 与 GitHub 两类端点，"所有服务商都能直连"不成立（[`link/CREDENTIALS.md`](../link/CREDENTIALS.md) §2.1 第 5 条）。

## 5. 学习（18 篇教程 + 126 键键盘 + 示例库）

| 项 | 实测值 | 复跑 |
| --- | --- | --- |
| 教程篇数 | **18** | §7 ⑨ |
| 步骤 / 示例 / FAQ | **66 / 52 / 42** | §7 ⑨ |
| 引导引用到的 target（去重） | **30** 个，已实现 **30**、待实现 **0** | §7 ④（`check-ui.mjs` 输出） |
| 数学键盘 | **6** 分类 / **126** 键（与 v1 逐类一致） | §7 ④ |
| 键面可读性 | 排版 13 键 / 文字 109 键 / 清理后文字 4 键 / **裸 LaTeX 0 键** | §7 ④ |
| 示例库条目 | **52** 条（就是教程数据里的示例，`/examples` 可"加载到工作区"） | §7 ⑨；`router/index.js:60` |
| 教程 + 键盘专项用例 | `tests/cdp-tutorials-keypad.mjs`（已登记进 `run-all.ps1:58`） | [`TUTORIAL-KEYPAD.md`](../ui/TUTORIAL-KEYPAD.md) §5.3 |

**教程系统**：目录页可分类/难度筛选、看进度、从任意一篇启动引导、断点续走、重置进度；正文页有概述/步骤/示例表/FAQ 与"标记为已学"（内容指纹变了"已学"自动失效，并说明原因）。引导遮罩是"用户真的去点目标"，目标缺失时**不静默跳过**（[`TUTORIAL-KEYPAD.md`](../ui/TUTORIAL-KEYPAD.md) §4）。

**数学键盘**：底部停靠面板，6 分类（基础运算 26 / 微积分 20 / 线性代数 15 / 希腊字母 34 / 概率统计 20 / 常用模板 11）；插入的是 **LaTeX**、占位符用 MathLive 的 `#0`/`#?`；插到"最后聚焦的输入框"，没有目标时明确提示而不是静默忽略（[`TUTORIAL-KEYPAD.md`](../ui/TUTORIAL-KEYPAD.md) §6）。基础运算页不显示它（那一页自带计算器键盘）。

**边界**：教程内容源不在本仓库（在 `<v2.0>/../Multifunctional-Mathematics/MF_Tutorial/tutorials/*.yaml`，`docs/tutorials-src/` 只是留档副本，改它无效 —— [`TUTORIAL-KEYPAD.md`](../ui/TUTORIAL-KEYPAD.md) §2.1）。

## 6. 系统（9 组设置 / 工作区 / 导出图片 / 账号 / 更新 / 主题）

### 6.1 设置面板：9 组 57 项，全部 `ready`

| 组 id | 组名 | 项数 | 落在哪 |
| --- | --- | --- | --- |
| `appearance` | 外观 | **6** | `localStorage`：`mf_theme`/`mf_shape`/`mf_density`/`mf_font`/`mf_theme_follow` + 界面语言 |
| `calc` | 计算与绘图 | **2** | `settings\prefs.json`（数值精度 + 四项绘图默认范围） |
| `engine` | 引擎 | **6** | 不写设置文件：读 `Info`/`EngineReport` + 真调引擎自检 |
| `components` | 组件 | **5** | 不写设置文件：状态来自 `con` 桥 |
| `ai` | AI | **11** | `settings\ai.json`（明文 `apiKey`）+ `settings\ai-chat.json` |
| `search` | 搜索 | **8** | `settings\search.json` |
| `account` | 账号 | **5** | `settings\account.json`（token 密文） |
| `update` | 更新 | **7** | `settings\update.json` |
| `storage` | 存储与数据 | **7** | 本组自己不写文件；列出/打开/清理别的文件，并承载工作区与导入导出 |
| | **合计** | **57** | §7 ⑩；`nonReady=0` |

面板本身是**容器**：左侧分组导航带 `x/y` 完成度、顶部搜索**跳到具体某一项**（切组 + 滚动 + 高亮 1.8 秒）、支持深链 `/settings?group=<id>`（[`SETTINGS-WORKSPACE.md`](../ui/SETTINGS-WORKSPACE.md) §2）。

### 6.2 工作区：存"你正在做什么"，不存"算出来的结果"

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 存什么 | 各页**输入**：计算块（表达式 + 模式）、绘图表达式/视野/参数、控制台语言 + 代码 + 标准输入 | `lib/workspace/store.js:5-6,51`；[`SETTINGS-WORKSPACE.md`](../ui/SETTINGS-WORKSPACE.md) §5.1 |
| 不存什么 | 结果、曲线采样、交点、极值、向量场数据、分形像素、运行输出、撤销栈 | 同上 |
| 键 | `route.path`（**不带 `#`**） | `store.js:25,34-42` |
| 落盘 | `settings\workspace.json`（宿主原子写）；"另存为"走 `workspace.mfws.json` 文件对话框 | `store.js:21-22,108-119,146-166` |
| ⚠ 载入不是自动的 | 刷新/重启后内存里是空的，必须显式点设置 → 存储与数据里的「载入」 | `store.js:121-137`；[`SETTINGS-WORKSPACE.md`](../ui/SETTINGS-WORKSPACE.md) §5.5 |
| 坏输入不静默 | 版本比自己新、缺 `pages`、不是 JSON、磁盘文件损坏 —— 逐种给可读原因，且**不覆盖原文件** | `store.js:62-72,123-127,176-179` |

### 6.3 导出图片（PNG）

6 个绘图页都有入口，走宿主写盘（`win.SaveBinaryFile`），文件名 `页面名-时间戳.png`，按 `max(2, devicePixelRatio)` 放大并铺不透明底；三种结果（成功/取消/失败）都写回页面状态行（`lib/plot/exportImage.js:53-115`；`PlotPage.tsx:419-422`）。**它不是"重新按 2 倍分辨率渲染"**（§2.3）。

### 6.4 账号（`/account`）

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 入口 | 顶栏用户名/登录按钮；**不占侧栏一项**（`router/index.js:129-137` 显式注册路由） | `router/index.js:57,129-137` |
| 不登录能不能用 | 能：`Info`/`Configure`/`ClearLocal` 等不需网络，**未登录、断网、站点挂了，本地全部计算功能照常可用** | [`link/FEATURES.md`](../link/FEATURES.md) §2.5 |
| 什么时候清登录态 | **401 或 403**；404/429/5xx/网络/超时**都不清** | [`link/FEATURES.md`](../link/FEATURES.md) §2.3 |
| 脱敏 | `Info()` 不含 token 本体；`Configure` 只能改 4 个字段 | [`link/FEATURES.md`](../link/FEATURES.md) §2.2 |
| ⚠ 两个语义要分开 | `Logout` **不清** `username`/`email`/`balance`；要真抹掉得 `ClearLocal` | [`link/FEATURES.md`](../link/FEATURES.md) §2.3 |

### 6.5 更新

| 项 | 事实 | 出处 |
| --- | --- | --- |
| 比什么 | 比**关系**（`newer`/`same`/`older`），不是"不同"——否则 v2 用户会被提示"升级"到站点上的 1.2.0（那是降级） | [`link/FEATURES.md`](../link/FEATURES.md) §3.3 |
| 做什么 | 查站点版本、显示 `sha256`/大小/版本差异、把下载页交给**系统浏览器** | 同上 §3.1 |
| **不做**（永不做） | 自动下载安装包、自动运行安装包 —— 宿主侧唯一"执行外部程序"的原语 `shellopen::open` 被 http/https 闸门锁死 | 同上 §3.1、§3.5 |
| ⚠ `sha256` 只显示 | **不校验**；站点没给就返回 `null` 并附原因（不给空串假装已校验） | 同上 §3.2 |
| 未做（≠永不做） | 更新回滚、增量更新、静默安装、通道（beta）与历史版本列表 | 同上 §3.6 |

### 6.6 主题与外观

6 项：主题模式（亮/暗/跟随系统）、配色方案、圆角与阴影、疏密、界面字体、恢复默认外观（`settings/catalog.js:35-40`）。**改了就生效、没有保存按钮**（`catalog.js:18`）。主题切换按钮在顶栏（`App.vue:329`，源码位置表见 [`TUTORIAL-KEYPAD.md`](../ui/TUTORIAL-KEYPAD.md) §5.5）；外观偏好**不进工作区文件**，但会随「导入/导出设置」整机迁移（`io.js:56-65`）。

### 6.7 首页（`/`）

显示 WebView2 桥状态 + 3 项引擎冒烟（`expr_eval` / `expr_eval_batch` / `simpson_rule`）+ 一步试算（`HomeView.vue:24-40`）。**边界**：页脚与注释仍写"C# MathBridge"（§9 第 3、4 条）。

## 7. 怎么复跑（本文全部数字的唯一来源）

在 `MF_UI/MFMath.UI.Vue`（除非另有说明）执行。本文实测环境：Windows，Node v26.3.1。

```powershell
# ① 导航项数 → NAV_TOTAL=27（calc 15 / plot 7 / tools 3 / help 2）
node -e "import('./src/lib/router/nav.js').then(m=>{let n=0;for(const g of m.NAV_GROUPS){console.log(g.id,g.items.length);n+=g.items.length}console.log('NAV_TOTAL='+n)})"
# ② 每个视图的模式数与总条数 → VIEWS=14 MODES_TOTAL=393 MODES_DISTINCT=391
node --input-type=module -e "const m=await import('./src/lib/engine/viewConfigs.js');const V=m.VIEW_CONFIGS;const ks=Object.keys(V);let t=0;for(const k of ks)t+=V[k].modes.length;const all=ks.flatMap(k=>V[k].modes);console.log('VIEWS='+ks.length+' MODES_TOTAL='+t+' MODES_DISTINCT='+new Set(all).size);console.log(ks.map(k=>k+'='+V[k].modes.length).join(' '))"
# ③ 视图模式表与 ENGINE_MAP 的差集 → ENGINE_MAP_MODES=415 ENGINE_MAP_FNS=371 VIEW_MODES_DISTINCT=391 VAR_SPECS=139 MAP_ONLY=24 UI_ONLY=0
node --input-type=module -e "const m=await import('./src/lib/engine/engineMap.js');const v=await import('./src/lib/engine/viewConfigs.js');const ui=new Set(Object.values(v.VIEW_CONFIGS).flatMap(c=>c.modes));const map=new Set(Object.keys(m.ENGINE_MAP));console.log('ENGINE_MAP_MODES='+map.size+' ENGINE_MAP_FNS='+new Set(Object.values(m.ENGINE_MAP).map(x=>x.fn)).size+' VIEW_MODES_DISTINCT='+ui.size+' VAR_SPECS='+Object.keys(m.ENGINE_VAR_SPECS).length+' MAP_ONLY='+[...map].filter(x=>!ui.has(x)).length+' UI_ONLY='+[...ui].filter(x=>!map.has(x)).length)"
# ④ 前端自检（可达性 / 键盘 / 教程目标 / 用例登记）；关键行：
$env:MF_TUTORIAL_ARCHIVE="$env:TEMP\mf-arch"; node tools/check-ui.mjs
#   引擎模式可达性：映射 415 个 / 页面并集 391 个 / 取不到 0 个（已登记 0 个待补或无处安放）
#   重名模式登记：已登记 24 个，未登记 0 个
#   教程引用的 target：30 个（已实现 30，待实现 0）/ 数学键盘：6 分类 / 126 键（v1 也是 126）
#   键面可读性：排版 13 键 / 文字 109 键 / 紧凑替代 0 键 / 清理后文字 4 键（裸 LaTeX 0 键）
# ⑤ 引擎 action 总数 → 源码 register_function 424 条 / 表 424 条（✓ 无漂移）
node tools/engine-signatures.mjs --check
# ⑥ 模式表覆盖了多少 action → signatures 424 modeTableFns 371 outside 53
node --input-type=module -e "const m=await import('./src/lib/engine/engineMap.js');const fs=await import('node:fs');const s=JSON.parse(fs.readFileSync('src/lib/ai/engine-signatures.json','utf8'));const f=new Set(Object.values(m.ENGINE_MAP).map(x=>x.fn));const k=Object.keys(s);console.log('signatures',k.length,'modeTableFns',f.size,'outside',k.filter(x=>!f.has(x)).length)"
# ⑦ 每个模块的 action 数 → MODULES=18 TOTAL=424（algebra 79 … fractal_api.cpp 1）
node -e "const s=require('./src/lib/ai/engine-signatures.json');const by={};for(const k of Object.keys(s)){const d=String(s[k].file||'').split('/')[0];by[d]=(by[d]||0)+1}const e=Object.entries(by).sort((a,b)=>b[1]-a[1]);let t=0;for(const [k,v] of e){t+=v;console.log(k,v)}console.log('MODULES='+e.length+' TOTAL='+t)"
# ⑧ 参数形态 → NO_PARAM=9 TYPES=15 PARAM_COUNT=963
node -e "const s=require('./src/lib/ai/engine-signatures.json');const t=new Set();let n=0,noArg=0;for(const f of Object.keys(s)){const ps=Object.keys(s[f].params||{});if(!ps.length)noArg++;for(const p of ps){t.add(s[f].params[p]);n++}}console.log('NO_PARAM='+noArg,'TYPES='+t.size,'PARAM_COUNT='+n)"
# ⑨ 教程 / 步骤 / 示例 / FAQ → TUTORIALS=18 STEPS=66 EXAMPLES=52 FAQ=42
node -e "const t=require('./src/tutorials/tutorials.json');const l=t.tutorials;let s=0,e=0,f=0;for(const x of l){s+=x.steps.length;e+=x.examples.length;f+=x.faq.length}console.log('TUTORIALS='+l.length,'STEPS='+s,'EXAMPLES='+e,'FAQ='+f)"
# ⑩ 设置分组与项数 → groups=9 items=57 / appearance=6 calc=2 engine=6 components=5 ai=11 search=8 account=5 update=7 storage=7 / nonReady=0
node -e "import('./src/lib/settings/catalog.js').then(m=>{const {GROUPS,ITEMS}=m;console.log('groups='+GROUPS.length+' items='+ITEMS.length);console.log(GROUPS.map(g=>g.id+'='+ITEMS.filter(i=>i.group===g.id).length).join(' '));console.log('nonReady='+ITEMS.filter(i=>i.status!=='ready').length)})"
```

②③ 都是**直接 import 生产模块**得到的（`viewConfigs.js` / `engineMap.js` 本身是 ESM），没有另写脚本；③ 得到的 24 个名字与 `check-ui.mjs:330-344` 的登记表逐条比对过（§1.4）。

端到端用例（需要带 `--remote-debugging-port=9222` 的宿主，详见 [`../../MFMath.Host.Rust/docs/ACCEPTANCE.md`](../../MFMath.Host.Rust/docs/ACCEPTANCE.md)）：`tests/run-all.ps1 -NoLaunch`。**本文没有跑端到端**，所有结论只到"源码 + 构建期自检"这一层。

## 8. 未证实（不要当成"有"，也不要当成"没有"）

| # | 事项 | 为什么没证实 | 怎么才能证实 |
| --- | --- | --- | --- |
| 1 | 上面每个功能的**运行时行为** | 本文没起宿主，只跑了构建期自检与数据清点 | 附着已有宿主后 `tests/run-all.ps1 -NoLaunch`，看各 `RESULT\|` 行 |
| 2 | **函数工具箱**（§3.2）的可用性 | 全仓库 `data-toolbox` / `__mfToolbox` 只出现在 `ToolboxView.vue` 自己，没有任何 `tests/*.mjs` 引用（[`TOOLS.md`](../ui/TOOLS.md) §6 第 1 条） | 带 CDP 进 `/tools/toolbox`，断言 `window.__mfToolbox.size() === 424`、`missing().length === 53`、`await __mfToolbox.call("expr_eval",{expr:"x^2",x:3})` 的 `value === 9`（`call` 是 async，要 `awaitPromise:true`） |
| 3 | 控制台"点安装 → 联网下载 → 装好"整条路径 | 站点上两个组件 zip 尚未上传（[`../OPEN-ITEMS.md`](../OPEN-ITEMS.md):119） | 上传后跑 `node tests/cdp-console.mjs` 的 Python / MinGW 两段安装分支 |
| 4 | "C++ 在下拉里可见但一跑就报组件不完整"的真实发生率 | 判据不一致是代码事实（[`link/FEATURES.md`](../link/FEATURES.md) §5.5），但没有在本机复现 | 删掉组件目录里的 `include\mfmath_autorun.hpp`，看下拉是否仍有 `cpp`、点了是否报"组件不完整" |
| 5 | 界面语言这一行**搜不到**（`searchItems("语言") === []`） | 索引层已证，未在界面上敲字 | `/settings` 顶部搜索敲"语言"，看结果是否为空 |
| 6 | 设置面板点「保存」写进工作区的 `route` 是否为 `/settings`（而不是用户当时在编辑的页） | 只有源码证据（[`SETTINGS-WORKSPACE.md`](../ui/SETTINGS-WORKSPACE.md) §7） | 在 `/calc/algebra` 改一个块 → `/settings?group=storage` 点「保存」→ 读 `workspace.json` 的 `route` |
| 7 | `cdp-plot-workspace` 与 `cdp-tutorials-keypad` 现在是否绿 | 未跑（无宿主） | 独占时间窗内各跑一次，读 `RESULT\|` 行 |
| 8 | 键盘键面 KaTeX 在真实宿主里的观感 | 只需要真实渲染 | 打开键盘「常用模板」页签截图 |

## 9. 已知的文档债

逐条对照源码时发现的"注释/数据与代码不符"。**本文只登记，不改任何文件。**

| # | 位置 | 它说 | 代码做 | 影响 / 怎么证 |
| --- | --- | --- | --- | --- |
| 1 | `src/router/index.js:4` | "registry.js 里的 **25** 个导航项全部有真实组件" | `NAV_GROUPS` 现在是 **27** 项（calc 15 / plot 7 / tools 3 / help 2） | 加"极坐标"与"调和分析"两轮各加一项，注释没跟着改。证：§7 ① |
| 2 | `src/lib/router/nav.js:67-70`、`src/router/index.js:52-53`、`views/tools/ToolboxView.vue:7` | 界面模式表覆盖 371，"**剩下 38 个**"没有任何入口 | 实际 **53** 个（424 − 371）。`371 + 38 = 409 ≠ 424`，自相矛盾 | 已在 [`TOOLS.md`](../ui/TOOLS.md) §7 第 1 条登记；证：§7 ⑥，页面运行时算出的 `outsideCount` 也显示 53（`ToolboxView.vue:104`） |
| 3 | `views/HomeView.vue:4` | "验证 **C#→C++** 链路" | 现役宿主是 Rust（`MFMath.Host/` 已废弃） | 属 [`../../AGENTS.md`](../../AGENTS.md) §2 的 R7 族；读者会去找已废弃的 C# 桥 |
| 4 | `views/HomeView.vue:59` | 用户可见页脚写"计算经 mf_mathematics.dll（C++），链接经 **C# MathBridge / WebView2**" | 现役是 Rust 宿主 + WebView2 | **这是用户能看到的文案**；本文只登记，改法须走 B 面 |
| 5 | `src/lib/settings/catalog.js:5` | "9 组 / **60 项**，全部 `status === "ready"`" | 9 组 / **57** 项 | 读数偏大 3；证：§7 ⑩ |
| 6 | `src/lib/settings/catalog.js:62-65` | AI 组"与 v1 的 12 项相比收敛成 **10 项**" | 实际 **11** 项 | 同上；证：§7 ⑩（`ai=11`） |
| 7 | `src/lib/settings/catalog.js:22` | AI 的 `note`："密钥只存宿主（**DPAPI**）" | `settings\ai.json` 的 `apiKey` 是**明文**（`lib/ai/bridge.js:8-11,278-294`；[`AI.md`](../ui/AI.md) §5） | **安全口径错误**，而且这句 `note` 是界面上显示给用户的说明 |
| 8 | `src/lib/settings/catalog.js:23` | 搜索"抓取与解析在宿主（**C#**）" | 现役是 Rust `search.rs` 经 `sys::store_write` | R7 族；同一句还出现在 `src/router/index.js:49` |
| 9 | `src/lib/engine/viewConfigs.js:498-500` | "引擎的 harmonic_analysis 模块有 **15** 个模式……于是这 15 个在界面上完全够不到" | 该视图实际挂了 **20** 个模式名，且全部映射到 `harmonic_analysis` 模块；而签名表里该模块有 **22** 个 action | "15"这个数两头都对不上（20 ≠ 15 ≠ 22）；"模式"与"action"口径不同，**未能判定哪个才是作者本意**。证：§7 ③⑦（`harmonic_analysis=22`）＋ `viewConfigs.js:506-528` |
| 10 | `src/lib/settings/catalog.js:8` | "构建期脚本可以断言 catalog 里的项都在界面上有对应行" | **没有这个脚本**；反例 `appearance.language` 在界面上有、在 catalog 里没有 | 承诺的闸门不存在，缺口已经发生（[`SETTINGS-WORKSPACE.md`](../ui/SETTINGS-WORKSPACE.md) §9 第 7 条） |
| 11 | `lib/console/bridge.js:4`、`lib/push.js:4` | 指向 `MFMath.Host/ConsoleBridge.cs`、`PushHub.cs` | 现役是 `MFMath.Host.Rust/src/{console,push}.rs` | 同族（[`TOOLS.md`](../ui/TOOLS.md) §7 第 3、4 条已登记） |

> 第 3、4、8、11 条属于同一族：**注释或用户可见文案仍指向已废弃的 C# 宿主**。按 [`../../AGENTS.md`](../../AGENTS.md) §2，见到就应改，但那几处不在本文的管辖范围。

## 10. 编辑本文件时

- §0 与 §1.2 的数字**必须重跑 §7 的命令**再改，不要手抄 —— 手抄一遍就是下一个 [BUGS.md](../../MF_UI/BUGS.md) §0.2。
- §1.2 的模式名以 `viewConfigs.js` 为准；**不要**按引擎模块列表去"补全"页面（页面能选到什么才是用户能看到的功能）。
- §3.2 的三个数字（424 / 371 / 53）与 §1.4 的三个数字（415 / 391 / 24）是**两套不同口径**，改一处要连口径一起交代，别互相覆盖。
- 标了"有意不做"的边界（搜索不翻页/不抓正文、绘图操作不入历史、更新不自动下载）不要从这里删 —— 它们是 [`../DESIGN-BOUNDARIES.md`](../DESIGN-BOUNDARIES.md) 的引用，改要先去改那边。
