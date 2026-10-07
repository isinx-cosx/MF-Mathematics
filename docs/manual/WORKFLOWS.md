# 典型用法：算一道题、画一张图、用 AI 分步、写控制台程序、保存与导出

> **本文只回答一个问题：典型用法：算一道题、画一张图、用 AI 分步、写控制台程序、保存与导出。**
>
> 与同层其它文档的分工：
> - [FEATURES.md](FEATURES.md) —— 功能全表（有哪些学科视图、多少个模式、几类绘图）；本文只讲"怎么按顺序走一遍"；
> - [INSTALL.md](INSTALL.md) —— 安装与构建（怎么让 `MFMath.exe` 跑起来）；本文假定它已经能跑；
> - [TROUBLESHOOTING.md](TROUBLESHOOTING.md) —— 走不下去时怎么排障（卡死、组件装不上、AI 连不通）；
> - [../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) —— 设置与工作区的**机制**（存哪个文件、schema、坏输入怎么拒），本文只讲按钮在哪、按什么顺序点；
> - [../ui/TOOLS.md](../ui/TOOLS.md) —— 控制台 / 函数工具箱 / 历史 / 搜索页的实现细节。

---

## 0. 本文的取证方式与复跑命令

本文写于 **2026-10-07 11:11–11:17（本机时间，命令都是在这个窗口里跑的）**，**没有跑宿主**（所以没有任何"点一下按钮、看它动"的实测）。本文的事实只有三类来源，逐条标注：

| 来源 | 可信度 | 本文怎么标 |
| --- | --- | --- |
| **引擎实测** | 最高：本机 `probe_call.exe` 真跑出来的返回值 | 命令 + 抄下来的输出 |
| **构建期自检输出** | 高：脚本自己算的，可复跑 | 命令 + 输出 |
| 源码行 | 源码即契约，但注释可能是错的（见 §11） | `文件:行` |

复跑本文数字的三条命令（第一条在 `MF_UI/MFMath.UI.Vue` 下，后两条在仓库根）：

```powershell
cd MF_UI/MFMath.UI.Vue; node tools/check-ui.mjs
# 输出节选：源码里注册的 data-tour：38 个 / 教程引用的 target：30 个（已实现 30，待实现 0）
#          引擎模式可达性：映射 415 个 / 页面并集 391 个 / 取不到 0 个
MF_Mathematics\build\bin\Release\probe_call.exe expr_eval '{"expr":"x^2-4","x":3}'
# -> {"isError":false,"value":5}
node -e "const d=require('./MF_UI/MFMath.UI.Vue/src/tutorials/tutorials.json');const t=d.tutorials;console.log('tutorials='+t.length+' steps='+t.reduce((n,x)=>n+x.steps.length,0)+' examples='+t.reduce((n,x)=>n+x.examples.length,0)+' faq='+t.reduce((n,x)=>n+x.faq.length,0))"
# -> tutorials=18 steps=66 examples=52 faq=42
```

---

## 1. 三条共同前提

| 前提 | 说明 | 出处 |
| --- | --- | --- |
| **必须在 `MFMath.exe`（宿主）里用** | 浏览器预览（`npm run dev`）没有引擎桥：计算页状态栏写"浏览器预览（无引擎）"、结果对话框写"（计算功能待接入引擎）"、控制台写"控制台不可用"、工具箱写"只列出函数、不能调用" | `CalcView.vue:52`、`ResultDialog.vue:31`、`ConsoleView.vue:46`、`ToolboxView.vue:203` |
| **入口只有两处** | 左侧 `#nav` 分组列表（`data-tour="main_window.toolbar"`）与顶栏按钮行 | `App.vue:310-324,402-419` |
| **计算只来自引擎** | 三个计算入口都靠引擎：计算页经 `engineCall`、绘图采样经 `expr_eval_vars_batch` / `expr_eval_grid`、控制台经 `mfmath`（Python）或 `mfm::` 门面（C++）调同一个 C ABI | `CalcView.vue:316-325`、`usePlotSampling.ts:59,208`、`ConsoleView.vue:9-11,35-36`；[../README.md](../README.md) 的三条纪律 |

侧栏 → 路由（本文用到的全部入口，逐字取自导航表 `src/lib/router/nav.js`）：

| 侧栏分组 | 项名 | 路由 |
| --- | --- | --- |
| 计算模式（15 项） | 基础运算 / 代数计算 / 微积分 / 解析几何 / 数列 / 线性代数 / 概率论与数理统计 / 数值分析 / 数论 / 实分析 / 泛函分析 / 复分析 / 代数拓扑 / 测度论 / 调和分析 | `/calc/basic` 与 14 条 `/calc/*`（除 `basic` 外都走 `CalcView`） |
| 绘图模式（7 项） | 2D 函数绘图 / 极坐标 / 3D 曲面 / 复平面 / 向量场 / 自由几何 / 分形 | `/plot/2d` … `/plot/fractal` |
| 工具（3 项） | 搜索 / 控制台 / 函数工具箱 | `/tools/search`、`/tools/console`、`/tools/toolbox` |
| 帮助（2 项） | 使用教程 / 示例任务库 | `/tutorial`、`/examples` |
| （不在侧栏） | 设置（侧栏底部「⚙ 设置」）/ 账号 / 教程正文 | `/settings`、`/account`、`/tutorial/:id` |

出处：`nav.js:13-86`（共 27 个导航项，逐组计数由 `node --input-type=module -e "import {NAV_GROUPS} from './src/lib/router/nav.js';…"` 复跑）、`router/index.js:23-86`（`REAL_VIEWS` 15 条键、`CALC_ROUTES` 14 条、`REACT_PAGES` 7 条；后两个数字由正则数 `"\/calc\/"` 与 `"\/plot\/"` 的键得到，注意 `REAL_VIEWS` 里的 `/calc/basic` 也会被前一个正则数进去）。

---

## 2. 流程一：在学科视图算一道题

### 2.1 最短路（代数化简）

| # | 你做什么 | 界面上的真实控件 | 出处 |
| --- | --- | --- | --- |
| 1 | 点侧栏「计算模式」→「代数计算」 | 侧栏项 `代数计算`（不是下拉框，是列表项） | `nav.js:23`、`App.vue:313-322` |
| 2 | 在输入框写 `x^2 + 2*x + 1` | `data-tour="calc_block.input"`，占位符「输入表达式，如 x^2+3*x-1」 | `CalcView.vue:454-460` |
| 3 | 在右边下拉里选「化简」 | `data-tour="calc_block.action_dropdown"`，选项就是 `VIEW_CONFIGS.algebra.modes` 的 59 项 | `CalcView.vue:461-470`、`viewConfigs.js:17-85` |
| 4 | 点「计算结果」 | 按钮文字 `计算结果`（计算中变「计算中…」） | `CalcView.vue:471-474` |
| 5 | 看结果对话框 | KaTeX 排版的结果；四个按钮：`查看步骤`、`复制结果`、`复制 JSON`、`关闭` | `ResultDialog.vue:130-140` |

引擎真值（命令行复跑，抄回来的输出）：

```powershell
probe_call.exe simplify_polynomial '{"expr":"x^2 + 2*x + 1"}'   # -> {"isError":false,"value":"(x + 1)**2"}
probe_call.exe factor '{"expr":"x^2 - 1"}'                      # -> {"isError":false,"value":"(x + 1)*(x - 1)"}
```

**这一页一次能放多个计算块**：`＋ 添加计算` 追加、每块自己的 ✕ 删除、`↶ 撤销` / `↷ 重做`（`CalcView.vue:475-492`），快捷键 `Ctrl+Z` / `Ctrl+Y`，历史上限 50 步（`:102`）。个别视图 `single: true`，此时「添加计算」与删除按钮不出现（`:213-215,476`）。

**结果之后**：`复制结果` 给人类可读文本、`复制 JSON` 给引擎原始信封（`ResultDialog.vue:137-139,77-100`）；每次计算（成功与失败都记）进历史（`CalcView.vue:386-392`），顶栏「历史」里点一条会**回到原页面并填入那条表达式**（`HistoryDialog.vue:87`，底部提示文字在 `:100`）。

### 2.2 带参数的模式：会先弹参数框

判据是**数据**，不是长相：模式名出现在 `ENGINE_VAR_SPECS` 里就走弹窗（`calcArgs.js:450-452`）。

```powershell
node --input-type=module -e "import {VIEW_CONFIGS} from './src/lib/engine/viewConfigs.js';import {ENGINE_VAR_SPECS} from './src/lib/engine/engineMap.js';const all=new Set();for(const k of Object.keys(VIEW_CONFIGS))for(const m of VIEW_CONFIGS[k].modes||[])all.add(m);console.log('页面模式并集='+all.size+' 走弹窗='+[...all].filter(m=>ENGINE_VAR_SPECS[m]).length)"
# -> 页面模式并集=391 走弹窗=137
```

抽几个页面的比例（同一命令交叉过滤；`VIEW_CONFIGS` 定义在 `viewConfigs.js:13`）：微积分 57 个模式里 38 个走弹窗、数值分析 25 里 14、复分析 26 里 11、代数计算 59 里只有 2 个（`交换律验证`、`结合律验证`）。

**具体走一遍（代数页的「交换律验证」）**：

| # | 你做什么 | 真实控件 / 文案 | 出处 |
| --- | --- | --- | --- |
| 1 | 模式下拉选「交换律验证」，点「计算结果」 | 输入框**可以空着**：走弹窗的模式一律不要求输入框非空 | `CalcView.vue:255`、`:276-286` |
| 2 | 弹出标题为「输入参数 — 交换律验证」的框 | 三个格子：`a（输入框）` / `b` / `运算符（+ 或 *）`，默认 `2` / `3` / `+` | `MultiVarDialog.vue:55-67`、`ENGINE_VAR_SPECS` |
| 3 | 第 1 格的初值来自输入框 | 输入框里有表达式时它预填第 1 格，否则用默认值 | `MultiVarDialog.vue:23-26` |
| 4 | 点「计算」（或按 Enter） | 底部两个按钮 `取消` / `计算`；Esc 取消、点遮罩**不关**（故意） | `MultiVarDialog.vue:33-46,50-52,68-71` |
| 5 | 看到同一个结果对话框 | 走 `onVarConfirm` → 构造参数 → 调引擎 → `finish()` | `CalcView.vue:328-347` |

引擎真值：

```powershell
probe_call.exe commutative_law '{"a":2,"b":3,"op":"+"}'  # -> {"isError":false,"value":{"holds":true,"left":5,"right":5}}
probe_call.exe commutative_law '{"a":2,"b":3,"op":"*"}'  # -> {"isError":false,"value":{"holds":true,"left":6,"right":6}}
```

⚠ 一个真会发生的坑：这一模式三个参数**都是可选**，所以把第 1 格清空不会报缺参数 —— 它会静默变成 `0`：

```powershell
node --input-type=module -e "import {ENGINE_MAP,ENGINE_VAR_SPECS} from './src/lib/engine/engineMap.js';import {buildEngineArgsFromValues} from './src/lib/engine/calcArgs.js';const m='交换律验证';const r={defaulted:[]};console.log(JSON.stringify(buildEngineArgsFromValues(ENGINE_MAP[m],ENGINE_VAR_SPECS[m],['','3','+'],r)),'defaulted='+JSON.stringify(r.defaulted))"
# -> {"a":0,"b":3,"op":"+"} defaulted=[]
```

### 2.3 缺必填参数：会拒绝计算，并说清缺什么

这里是**两层**拒绝，都指向同一件事——不许给出"看起来正常的错结果"：

| 层 | 什么时候触发 | 用户看到什么 | 出处 |
| --- | --- | --- | --- |
| 界面层 | `buildEngineArgs` 把**必填**参数兜底成 `0 / [0,0] / [] / ""`，同时记进 `report.defaulted`；`CalcView` 一旦发现非空就**不调引擎** | `缺少必填参数：point。请在输入框里用 ; 分段补上（顺序 = 参数顺序），例如 x^2; 1` | `calcArgs.js:192-221`、`CalcView.vue:288-299,360-369` |
| 引擎层 | 真的没把 key 传过去 | `{"isError":true,"value":"缺少必填参数 point（应为数字）。本次调用传入的参数键：expr"}` | 引擎实测（下） |

```powershell
probe_call.exe diff_at '{"expr":"x^2"}'          # -> {"isError":true,"value":"缺少必填参数 point（应为数字）。本次调用传入的参数键：expr"}
probe_call.exe diff_at '{"expr":"x^2","point":3}' # -> {"isError":false,"value":6}
probe_call.exe diff_at '{"expr":"x^2","point":0}' # -> {"isError":false,"value":0}   ← 兜底值的后果：f'(0)
```

**这条流程怎么走**：侧栏「计算模式」→「微积分」→ 模式选「某点导数」→ 输入框写 `x^2` → 点「计算结果」，被拒并告诉你缺 `point`；改成 `x^2; 3` 再点，得到 `6`（`某点导数` 的引擎函数是 `diff_at`：`engineMap.js` 的 `RAW_MAP`；它在微积分页的模式表里，见 `viewConfigs.js:144`）。

走弹窗的模式，提示语不同——是"请在参数弹窗里把这些格子填上（留空会算错）"（`CalcView.vue:363-368`）。例：数值分析页「梯形法则」第 1 格留空：

```powershell
# 弹窗字段与留空后的实参（命令同 §2.2 的第二条，换成 梯形法则）
# fields=[["被积函数（输入框）",""],["下限","0"],["上限","1"],["子区间数","100"]]
# values=["","0","1","100"] -> args={"f":"","a":0,"b":1,"n":100} defaulted=[{"key":"f","type":"string","value":""}]
probe_call.exe trapezoidal_rule '{"f":"x^2","a":0,"b":1,"n":100}'  # -> {"isError":false,"value":0.33335000000000004}
```

---

## 3. 流程二：画一张 2D 图、缩放到适应、导出图片

**先知道这一页是谁在渲染**：`/plot/*` 七条路由全部由 React 绘图组承载，Vue 只提供外壳与宿主桥（`ReactPlotView.vue:28-40`）；`src/views/plot/*` 那 6 个 Vue 文件是**冻结的回退资产**，不在构建图里、也没有用例覆盖（`router/index.js:29-36`；[../ui/PLOT.md](../ui/PLOT.md)）。画布上的数**不是前端算的**：采样走引擎的 `expr_eval_vars_batch` / `expr_eval_grid`（`usePlotSampling.ts:59,208`）。

| # | 你做什么 | 界面上的真实控件（文字逐字） | 出处 |
| --- | --- | --- | --- |
| 1 | 侧栏「绘图模式」→「2D 函数绘图」 | 路由 `/plot/2d`；首次进入默认一行表达式 `y=x^2` | `nav.js:49`、`PlotPage.tsx:103` |
| 2 | 在第 1 行输入框写 `sin(x)` | `data-tour="plot_workspace.function_input"`，占位符「输入表达式，如 y=x^2 或 cosx」 | `ExpressionList.tsx:158-167` |
| 3 | 需要多条曲线时点「＋ 添加表达式」 | `data-tour="plot_workspace.add_function"`；行数 >1 才出现行内 ✕ 删除 | `ExpressionList.tsx:170-174,181-183` |
| 4 | 每行还有两个圆点按钮 | 左：显示/隐藏（`title="隐藏"` / `"显示"`）；右：`title="颜色"` 打开色板 | `ExpressionList.tsx:121-154` |
| 5 | 画布上滚轮缩放、按住拖动平移 | `data-tour="plot_canvas"`；`onWheel` 是缩放，`onMouseDown/Move` 是平移（拖动已有点优先） | `PlotCanvas.tsx:665-701` |
| 6 | 点右上角浮动的 `⤢`（`title="缩放到适应"`） | 只喂**当前视野内看得见**的采样点算包围盒；视野内不足 2 个点才退回全部有限点 | `PlotPage.tsx:377-405`、`:622-627` |
| 7 | 点 `⤓`（`title="导出图片（PNG，2 倍像素）"`） | 弹系统保存对话框；出口写进页内状态行 | `PlotPage.tsx:415-424,627` |

浮动按钮组一共 7 个（`title` 逐字，`PlotPage.tsx:622-638`）：`放大`（＋）、`缩小`（－）、`缩放到适应`（⤢）、`重置视图`（⟲）、`导出图片（PNG，2 倍像素）`（⤓）、`切换为极坐标网格`/`切换为直角网格`（◉）、`隐藏网格`/`显示网格`（▦）。向量场 / 分形 / 3D / 几何页也有同名的 `⤓`（`PlotVectorPage.tsx:268`、`PlotFractalPage.tsx:416`、`Plot3DPage.tsx:241`、`PlotGeometryPage.tsx:276`）；复平面页是写「导出图片」的文字按钮，带 `disabled={busy}`（`PlotComplexPage.tsx:596-597`）。

**导出的三件事**（`exportImage.js`）：按 devicePixelRatio 至少 2 倍重画到离屏画布（`:53-62`）、先铺一层不透明底色（`:65-81`）、再交宿主 `SaveBinaryFile`（`:104-110`）。注释里说清了：它是把**已渲染的位图**放大，不是按 2 倍分辨率重渲染（`:10-13`，属注释声明）。

**状态行会如实说结果**（`:419-423`）：`已导出图片：<路径>（宽×高，KB）` / `已取消导出` / `导出失败：<原因>`；成功时它会暂时盖住采样状态，避免"刚导完就被采样刷新冲掉"（`PlotPage.tsx:185-193`）。

两个源码级细节（**未在真机对话框上验证**，见 §10）：

- 2D 页传的默认文件名是字面 `"plot"`（`PlotPage.tsx:418`），于是 `exportImage.js:103` 那条"页面名 + 时间戳"的分支只对**不传** `defaultName` 的调用者生效（自由几何页就不传，`PlotGeometryPage.tsx:204`）；
- 宿主侧的保存对话框没有设置 `lpstrDefExt`（`winbridge.rs:307-318`），所以**不会**自动补 `.png` —— 想得到 `plot-2d-20261007-1111.png` 这种名字，得自己敲。

**参数的滑块**：表达式里有自由参数（如 `a*sin(b*x)`）时，左栏出现「参数」区与滑块（`data-tour="plot_workspace.sliders"`，`ParamSlider.tsx:75`）。⚠ 判据是解析器给出的**自由符号**，不是"按名字排除自变量"（`r` 在极坐标里是因变量）。出处：`PlotPage.tsx:128-145`。

**极值/交点不会自动画到画布上**：分析照算、只进左栏（`showExtrema` / `showIntersections` 初始为 `false`，`PlotPage.tsx:122-125`）；点曲线可以加点，点会吸附在所属曲线上（`:426-460`）。

---

## 4. 流程三：用 AI 助手加步骤推导

### 4.1 先配好（设置 → AI）

| # | 你做什么 | 真实控件 | 出处 |
| --- | --- | --- | --- |
| 1 | 侧栏底部点「⚙ 设置」→ 左列点「AI」 | 该行带 `data-tour="settings_dialog.ai_tab"` | `App.vue:388-390`、`SettingsView.vue:94-96` |
| 2 | 打开「启用 AI」开关 | 默认**关**（`DEFAULT_CFG.enabled = false`） | `AiGroup.vue:106-112`、`ai/bridge.js:57-58` |
| 3 | 填「API Base」与「默认模型」 | 行内 3 个预设按钮 `DeepSeek` / `OpenAI` / `Ollama（本地）`（点了同时填入端点与模型）；也可以用任意 OpenAI 兼容端点 | `AiGroup.vue:60-68,121-146` |
| 4 | 在「API Key」里粘贴 → 点「保存密钥」 | 另有「清除」按钮 | `AiGroup.vue:194-197` |
| 5 | 点「测试连接」区的「测试」 | 出口文字：`连接正常（HTTP <码>，<毫秒> ms）` 或 `连接失败：<原因>` | `AiGroup.vue:279-291`、`AiPanel.vue:163-170` |

⚠ 密钥是**明文**存在 `%LOCALAPPDATA%\MFMath\settings\ai.json` 的 `apiKey` 字段里（界面自己就这么写：`AiGroup.vue:185-187`；安全口径见 [../link/CREDENTIALS.md](../link/CREDENTIALS.md)）。

**想让 AI 真的算，必须保住两个开关**：

| 开关 | 默认 | 关掉的后果 | 出处 |
| --- | --- | --- | --- |
| 「允许 AI 调用引擎计算」 | 开 | 模型不能调工具，数值只能靠它自己 —— 正是本产品禁止的 | `AiGroup.vue:232-235`、`ai/bridge.js:725` |
| 「引擎算出的结果」（在「会发送什么」里） | 开 | `engine_call` 会被**直接拒绝**："用户关闭了「发送引擎结果」，而工具调用的结果必须回传给模型" | `AiGroup.vue:260-263`、`ai/tools.ts:300-308` |

### 4.2 两条入口

| 路径 | 你做什么 | 会发生什么 | 出处 |
| --- | --- | --- | --- |
| (a) 从计算页 | 算完一题后，在结果对话框点「查看步骤」 | 请求被预填并**自动发出**，AI 抽屉自动打开；这一轮若带着引擎步骤，收尾后自动弹出分步显示 | `CalcView.vue:412-429`、`App.vue:258`、`AiPanel.vue:75-88` |
| (b) 直接问 | 顶栏点「AI」→ 在输入框写问题 → 点「发送」或 Enter | 流式输出；`Shift+Enter` 换行 | `App.vue:410-411`、`AiPanel.vue:289-302` |

抽屉是**非模态**的（只占右侧一条，主界面照旧能点，`AiPanel.vue:324-335`）；「停止」可中断本轮，「清空」清这段对话（`:303-304`）。

### 4.3 怎么看出"每一步都是引擎算的"

| 证据 | 长什么样 | 出处 |
| --- | --- | --- |
| 工具调用块 | 每条回答下逐个列出：徽标「引擎」+ 引擎函数名 + 耗时 + 参数 JSON + 摘要；失败的块左边框变红 | `AiPanel.vue:214-234` |
| 「查看步骤（N）」 | 点开 `StepViewer`：每步给 序号 / 引擎函数 / 耗时 /「引擎已算出」或「失败」/ 参数 / **完整结果**；失败的一步标红保留、不隐藏 | `AiPanel.vue:229-233`、`StepViewer.vue:65-80,107` |
| 发送前的那一行 | 「将发送约 N token」+ 分项标签：问题文本 / 当前表达式 / 引擎结果 / 控制台代码 / 会话历史（关掉的会划掉） | `AiPanel.vue:293-300` |
| 硬约束本身 | 系统提示第一条就是"所有计算由 C++ 引擎完成"；工具只有 `engine_find` 与 `engine_call`；函数名不在引擎签名表里一律拒绝 | `ai/bridge.js:529-536`、`ai/tools.ts:185,200,238,269-280` |

### 4.4 两个要知道的实情

1. **计算页那一项「引擎结果」恒为空。** 工作区只存 `expr`/`mode`、不存结果（`CalcView.vue:80-84`），而 `currentContext` 读的是 `blocks[].result`（`ai/bridge.js:547-549`）—— 所以"发送引擎结果"这个开关在计算页实际不起作用。同一结论与验法见 [../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §5.4 与 §8 第 7 条。
2. **没配好时，别只看状态栏。** `CalcView.onSteps` 只看 `requestAiTurn()` 的返回值，而它在 AI 未启用时也返回 `ok: true`（`ai/bridge.js:978-983`），于是状态栏会先说"已请 AI 分步讲解"，紧接着抽屉顶部才显示真正的原因：「AI 未启用」/「还没有 API Key」/「读不到设置文件（浏览器预览里没有 sys 桥）」，并给一个「去设置 → AI」按钮（`AiPanel.vue:186-197`）。**以抽屉里的为准**（`CalcView.vue:424-428`）。

---

## 5. 流程四：函数工具箱里直接调一个引擎函数

入口：侧栏「工具」→「函数工具箱」（`/tools/toolbox`，`nav.js:73`）。

| # | 你做什么 | 真实控件 | 出处 |
| --- | --- | --- | --- |
| 1 | 看头部说明 | 「引擎共有 424 个可调用函数，本页全部列出」+「其中 53 个不在界面模式表里（标了「不在模式表」）」—— 424 与 53 都是运行时算的，不是写死的 | `ToolboxView.vue:196-201,104` |
| 2 | 在搜索框输 `expr` | 占位符「按函数名 / 模块 / 参数名过滤，例如 matrix、taylor、expr」，`data-toolbox="search"` | `ToolboxView.vue:207-208` |
| 3 | 勾「只看不在模式表里的（53）」 | `data-toolbox="missing"` | `ToolboxView.vue:209-212` |
| 4 | 点左栏 `expr_eval` 一行 | 每个条目带函数名、模块名，不在模式表的加「不在模式表」徽标 | `ToolboxView.vue:217-224` |
| 5 | 右侧按参数表填 | 每个参数给出 键名 + `必填`/`可选` + 类型 + 占位符；数字型用 number 输入框；矩阵/数组要填 **JSON 真值**（如 `[[1,2],[3,4]]`） | `ToolboxView.vue:236-246,65-76,132-141` |
| 6 | 点「调用引擎」 | 旁边还有「清空」和勾选框「强制后台」 | `ToolboxView.vue:248-260` |
| 7 | 读结果区 | `data-toolbox="result"`，内容是引擎信封的原样 JSON；本页不做任何解读 | `ToolboxView.vue:262-269` |

引擎真值（两条都能在这一页照着点出来）：

```powershell
probe_call.exe expr_eval '{"expr":"x^2-4","x":3}'                        # -> {"isError":false,"value":5}
probe_call.exe matrix_multiply '{"A":[[1,2],[3,4]],"B":[[5,6],[7,8]]}'   # -> {"isError":false,"value":[[19,22],[43,50]]}
```

其他细节：慢函数可以勾「强制后台」走后台任务通道，运行中会显示「后台运行中… <秒>s · <在算什么>」（`ToolboxView.vue:142-155,253-258`）；引擎报错时小标题写「引擎返回错误（这是引擎自己的判定，本页不做解读）」（`:265`）；没连上引擎写「没有连上本地引擎（本页只在 MFMath.exe 里可用）」（`:162`）。

**这一页为什么存在**：界面模式表覆盖 371 个函数名、签名表有 424 条，差集 53 个此前在界面上没有任何模式入口（`ToolboxView.vue:6-13` 也是这么自述的，但那条注释里的数字是旧的，见 §11 第 6 条）。复跑（在 `MF_UI/MFMath.UI.Vue` 下）：

`node --input-type=module -e "import S from './src/lib/ai/engine-signatures.json' with {type:'json'};import {ENGINE_MAP} from './src/lib/engine/engineMap.js';import {EXTRA_MAP} from './src/lib/engine/engineMapExtra.js';const s=new Set();for(const x of Object.values(ENGINE_MAP))if(x&&x.fn)s.add(x.fn);for(const x of Object.values(EXTRA_MAP))if(x&&x.fn)s.add(x.fn);console.log('签名='+Object.keys(S).length+' 模式表='+s.size+' 表外='+Object.keys(S).filter(f=>!s.has(f)).length)"` → `签名=424 模式表=371 表外=53`

---

## 6. 流程五：控制台里跑一段 Python 或 C++

### 6.1 先装组件（不装就跑会被拦住）

| # | 你做什么 | 真实控件 | 出处 |
| --- | --- | --- | --- |
| 1 | 侧栏「工具」→「控制台」（`/tools/console`） | 左列编辑区、右列输出区 + 「组件」区 | `nav.js:65`、`ConsoleView.vue:390-471` |
| 2 | 在「组件」区点 Python 一行的「安装」 | 同一行显示版本与体积；装好后按钮变「已装」 | `ConsoleView.vue:449-455` |
| 3 | 需要 C++ 时点 C++（MinGW A 档）一行的「安装」 | 该行 `installed` 但 `ready` 为假时写「已安装但不完整，请重新安装」 | `ConsoleView.vue:456-462,68-74` |
| 4 | 安装中看进度 | 进度条 + 百分比 + 说明 + 「取消」；取消后已下载的部分保留（**注释声明**） | `ConsoleView.vue:465-469,463-464` |

**C++ 是装好才出现的**：语言下拉只有两项——`Python` 恒在，`C++` 仅在 `comps.cpp.ready` 为真时推入（`ConsoleView.vue:55-62`）。没装就点运行，状态栏会写「需要先安装 Python 组件」/「需要先安装 C++ 组件」（`:277-278`）。

### 6.2 跑

| # | 你做什么 | 真实控件 | 出处 |
| --- | --- | --- | --- |
| 1 | 选语言、选示例 | 左起两个下拉：语言、示例。Python 3 个：`调引擎：求导 / 求值`、`循环 + 用引擎批量求值`、`函数 + 条件 + 错误处理`；C++ 3 个：`调引擎：求值 / 求导 / 极限`、`循环 + 用引擎逐点求值`、`错误处理：引擎报错必须看得见` | `ConsoleView.vue:394-399,95-208` |
| 2 | 写代码 | CodeMirror 6 编辑器；`Ctrl+Enter` 运行、`Ctrl+Space` 按引擎函数名补全（候选来自引擎 `list_functions`，C++ 另有 8 个 `mfm::` 门面名） | `ConsoleView.vue:409-410,362-367,35-36` |
| 3 | 要喂输入就填「标准输入（可选）」 | 占位符「每行一个输入，运行时会喂给程序」 | `ConsoleView.vue:418-421` |
| 4 | 点「运行 ▷」 | 运行中该按钮变成「终止 ■」；旁边是「清空输出」「重置」 | `ConsoleView.vue:401-404` |
| 5 | 读右列 | 徽标「未运行」/「退出码 N」、耗时、C++ 多一个「编译 N ms」、必要时「输出已截断」；输出区空时写「（还没有输出）」；有 stderr 时多出一块「错误」 | `ConsoleView.vue:426-445` |

**三条必须知道的边界**：

1. **每次「运行」都是新进程**，变量不跨次保留（界面上就写着这句，`ConsoleView.vue:414-417`）。
2. **计算仍由引擎完成**：Python 侧只有 `mfmath`（ctypes 封装）、C++ 侧只有导入库，界面不算数学（`ConsoleView.vue:9-11`）。示例里 `mfmath.call('expr_eval', expr='x^2', x=3)` 对应的引擎调用就是本文跑过的 `expr_eval` → `5`（§0 命令 ②）。
3. **控制台的工作区载荷是「语言 + 代码 + 标准输入」，不存输出**（`ConsoleView.vue:377-379`；[../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §5.1）。

---

## 7. 流程六：保存工作区、换机器时导入导出设置

### 7.1 工作区（算/画/写的东西）

「工作区」= 各页正在编辑的内容，按 `route.path` 分页，**只存输入、不存结果**（`workspace/store.js:5-6,24-25`）。落盘位置：`%LOCALAPPDATA%\MFMath\settings\workspace.json`（`store.js:11,21`）。

入口只有一处：**设置 → 「存储与数据」→ 「工作区」行**（`StorageGroup.vue:230-255`）。

| 按钮 | 做什么 | 出处 |
| --- | --- | --- |
| 保存 | `storeWrite("workspace", snapshot(route))`，宿主原子写（先写 `.tmp`、旧文件转 `.bak`） | `store.js:108-119`、[../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §3.1 |
| 载入 | 读回并**跳回保存时记下的路由**：「已载入 N 个页面，正在跳回 <路由>；页面内容会在切换到该页时还原」 | `StorageGroup.vue:73-78` |
| 另存为文件… | 默认名 `workspace.mfws.json`，过滤器 `*.mfws.json` | `store.js:22,146-166` |
| 从文件打开… | 读 → `JSON.parse` → 校验；不是 JSON 就报「<路径> 不是合法 JSON：<原因>」 | `store.js:168-184` |
| 清空 | 只清内存，二次确认「确定清空？」 | `store.js:44-47`、`StorageGroup.vue:246-253` |

**「载入」不是自动发生的**：刷新或重启后内存里是空的，必须显式点一次「载入」。全仓库 `saveToApp` / `loadFromApp` / `saveToFile` / `loadFromFile` 的调用点只有 `StorageGroup.vue:67,74,80,85`（`grep` 结论），`hasAppWorkspace()` 目前是零引用导出（`store.js:139`）。

各页什么时候回写内存里的工作区：`/calc/*` 是 `watch(blocks, {deep:true})` 且挂载完成后才启用（`CalcView.vue:155-168`）；`/plot/*`（6 个 React 页）是 `usePlotWorkspace` 的 effect，首帧不回写（`plotWorkspace.ts:51-72`、`PlotPage.tsx:159-166`）；`/tools/console` 是 `watch([lang, code, stdin], {deep:true})`（`ConsoleView.vue:377-379`）。

⚠ 已知的疑点（与 [../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §7 同一处）：**从设置面板点「保存」时，记下的 `route` 是 `/settings` 自己**（`StorageGroup.vue:62,67` 用的是设置页的 `useRoute()`），所以「载入」会把你送回设置页而不是你当时在编辑的那一页。**只有源码证据**，验法见那份文档 §8。

### 7.2 换机器：导入 / 导出设置

同一页的「导入 / 导出设置」行（`StorageGroup.vue:256-279`）：

| # | 你做什么 | 真实控件 / 文案 | 出处 |
| --- | --- | --- | --- |
| 1 | 点「导出…」 | `data-io="export"`；成功写「已导出 N 个设置文件与 M 项外观偏好（不含密钥）：<路径>」 | `StorageGroup.vue:263,30-39` |
| 2 | 换机后点「导入…」 | `data-io="import"`，先出确认行「导入会覆盖同名的设置文件，确定？」+「确定导入」 | `StorageGroup.vue:264,266-269` |
| 3 | 重启应用 | 返回值里 `needsRestart: true` 是写死的，界面也写「重启后全部生效」 | `io.js:169-175`、`StorageGroup.vue:276` |

包里有什么 / 没什么（`io.js`）：

| 项 | 内容 | 出处 |
| --- | --- | --- |
| 有 | 每个设置文件（默认含 `history`、`ai-chat`、`prefs`、`update`；**保存过工作区之后也含 `workspace`**）+ `localStorage` 里所有 `mf_` 前缀的键 | `io.js:82-102,56-65` |
| 没有 | 三份凭据文件整份排除：`ai` / `account` / `search`；其余文件再按字段名剥掉 `token`/`apiKey`/`secret` 等，剥了哪些记进 `stripped` | `io.js:31,34,122-131` |
| 导入的硬性质 | 不清你现在的密钥、不写那三类文件；**元数据不合格的包在写第一个文件之前就拒绝** | `io.js:152-160,141-147` |
| 坏文件 | 读不出/解析失败的记进 `skippedCorrupt` 并跳过；`StoreList` 返回错误对象时**中止导出**而不是报"0 个文件成功" | `io.js:92-100,79-81` |

**诊断包不是备份**：它是数据目录下的 `diagnostics-<stamp>.txt`（设置页「导出诊断包」行），跳过三份凭据文件，但 **`ai-chat.json` 会整份进去**（那里是你的会话原文）——发给别人前先看一眼（`MFMath.Host.Rust/src/sys.rs:278-304`；[../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §4.5）。

---

## 8. 流程七：跟着教程或示例库起步

入口：侧栏「帮助」→「使用教程」（`/tutorial`）或顶栏「帮助」（`App.vue:417-418`）。

| 你做什么 | 真实控件 | 出处 |
| --- | --- | --- |
| 在目录里挑一篇 | 每张卡片三个按钮：`开始引导` / `继续`（只有存过进度才出现）/ `阅读`；顶部还有「重置进度」 | `TutorialCatalogView.vue:71-106` |
| 走交互引导 | 遮罩上的按钮：`结束引导` / `上一步` / `暂停`（暂停后变 `继续`）/ `跳过此步`（仅当该步目标缺失）/ `下一步`（末步是「完成」）；`Esc` 暂停、`←/→` 前后 | `TourOverlay.vue:207-216` |
| 目标找不到时 | **不静默跳过**：显示「这一步的目标界面还没做」；若目标在别的页，则给「前往该界面」按钮 | `TourOverlay.vue:186-201`、`targets.js:9` |
| 从示例库起步 | 「示例任务库」里每条示例有 `加载到工作区 →` 与 `复制`；加载会跳到目标页并把表达式+操作送过去 | `ExampleLibrary.vue:54-74,115-116` |

18 篇教程（标题逐字取自构建产物 `src/tutorials/tutorials.json`，命令见 §0 命令 ③；括号里是 `步/示例/FAQ`）：

`quick-start` 快速入门 — 认识 MF-Mathematics（4/2/2）· `basic-calculation` 基础计算 — 代数化简与求导（6/5/3）·
`plot-2d` 2D 绘图 — 画出你的第一个函数（6/4/3）· `ai-assistant` AI 数学助手 — 你的私人数学导师（5/2/3）·
`ai-steps-accelerate` 步骤推导与 AI 讲解（5/2/2）· `linear-algebra` 线性代数 — 矩阵与向量运算（3/4/2）·
`probability-statistics` 概率统计 — 分布、检验与回归（3/3/2）· `numerical-analysis` 数值分析 — 插值、积分与微分方程（3/4/2）·
`plot-3d-complex` 3D 绘图与复数域着色（4/4/2）· `vector-field-geometry` 向量场与几何做图（3/4/2）·
`math-keyboard` 数学键盘 — 符号输入利器（3/2/2）· `search-settings` 联网搜索与软件设置（6/2/2）·
`themes-appearance` 主题切换与界面定制（2/0/2）· `tips-and-tricks` 进阶技巧与效率提升（1/2/4）·
`complex-analysis` 复分析 — 复数域上的微积分（3/3/2）· `functional-analysis` 泛函分析 — 无穷维空间的数学（3/3/2）·
`measure-theory` 测度论 — 长度、面积与积分的推广（3/3/2）· `algebraic-topology` 代数拓扑 — 用代数研究空间的形状（3/3/3）。

合计 **18 篇 / 66 步 / 52 示例 / 42 FAQ**（§0 命令 ③）。列表顺序即 `order`。

三条机制要知道：

1. **教程引用 30 个 target，已实现 30、待实现 0**（`check-ui.mjs` 输出），源码里注册 38 个 `data-tour`；「尚未实现」的显式清单 `PENDING` 现在是空的（`targets.js:33-47`）。
2. **`docs/tutorials-src/*.yaml` 是 v1 原件留档，不是运行时数据源**。v2 的差异在构建期由 `MFMath.UI.Vue/tools/build-tutorials.mjs` 的 `V2_OVERRIDES`（`:83-128`）覆盖 —— 所以 YAML 里**还能看到** v2 决定不做的「AI 加速」步骤（§11 第 5 条），运行时以 `src/tutorials/tutorials.json` 为准。
3. **教程内容一变，"已学"标记就失效**：每篇带一个内容指纹 `version`，目录里会提示「教程内容已更新，先前的"已学"标记已失效」（`TutorialCatalogView.vue:95`、`build-tutorials.mjs:326-330`）。

---

## 9. 三条纪律在这七条流程里长什么样

| 纪律 | 在流程里能被看见的形态 | 出处 |
| --- | --- | --- |
| ① 不编造结果 | 未映射的模式明说「模式「X」暂无引擎映射（引擎未提供该接口）」；缺必填参数**拒绝计算**并列出缺哪个键；工具箱的错误区写"这是引擎自己的判定，本页不做解读" | `CalcView.vue:230-234,288-299`、`ToolboxView.vue:265` |
| ② AI 不承担计算 | 工具只有 `engine_find` 与 `engine_call`；系统提示写明计算由引擎完成；「查看步骤」展示的是**工具调用记录**而不是模型措辞；关掉「引擎算出的结果」时 `engine_call` 被拒 | `ai/tools.ts:185,200,238`、`ai/bridge.js:529-536`、`StepViewer.vue:5-14,60-63` |
| ③ 每个修复留"为什么"和"怎么证明" | 本文每个数字都给了可复跑命令（§0），引擎返回值都是从 `probe_call.exe` 抄下来的 | 本文 §0、§2、§5 |

---

## 10. 未证实（附怎么验）

| # | 未证实的事 | 为什么没证 | 怎么验 |
| --- | --- | --- | --- |
| 1 | 本文全部"点一下会怎样"的行为 | 本文**没跑宿主**，只跑了 `check-ui.mjs` 与 `probe_call.exe` | 按 [../../AGENTS.md](../../AGENTS.md) §4 附着已有宿主后 `tests/run-all.ps1 -NoLaunch`；与本文相关的至少 `cdp-*.mjs` 里的计算、绘图、控制台、AI、工作区几条（登记表见 `tools/check-ui.mjs` 的"端到端用例：48 个"一行） |
| 2 | 导出图片的默认文件名与"不自动补 `.png`" | 只有源码证据（`PlotPage.tsx:418`、`exportImage.js:103`、`winbridge.rs:307-318`），没在真机对话框上看过 | 起宿主 → `/plot/2d` → 点 `⤓` → 看对话框里的默认名；再故意只填 `a` 看落盘文件名 |
| 3 | 组件包的下载体积/耗时 | 界面上的 MB 来自组件清单的 `expectBytes`/`payloadBytes`（`ConsoleView.vue:80-85`），本文没有实测下载 | 起宿主 → `/tools/console` → 点 Python 的「安装」，记时间与最终体积 |
| 4 | AI 全链路（发送、流式、工具调用、分步显示） | 没有可用 API Key，本文没配 | 按 §4.1 配好 Key → 顶栏「AI」问一句需要计算的话 → 看是否出现「引擎」工具块与「查看步骤（N）」 |
| 5 | 控制台真能跑起来 | 本机组件状态未查（`hosted` / `comps` 只在宿主里才有值） | 起宿主 → `/tools/console` → 装组件 → 跑第一个 Python 示例 |
| 6 | `tests/cdp-plot-workspace.mjs` 现在是否绿；「从设置页保存工作区会记下 `/settings`」是否为真 | 前者未跑（[../PROJECT-BOARD.md](../PROJECT-BOARD.md#L139) 明确"独占窗口里跑绿之前仍算未验证"）；后者只有源码证据（§7.1 末段） | 前者：独占时间窗内 `node tests/cdp-plot-workspace.mjs`；后者：起宿主 → `/calc/algebra` 改一个块 → `/settings?group=storage` 点「保存」→ 读 `workspace.json` 的 `route` 字段 → 点「载入」看跳到哪 |

---

## 11. 已知的文档债

以下是本文核对源码时发现的**注释/旧教程文本与代码不符**。按纪律只登记、不改任何文件（这些文件都不属本份文档的管辖范围）。

| # | 文件:行 | 它说 | 代码做 | 影响 |
| --- | --- | --- | --- | --- |
| 1 | `docs/tutorials-src/03-plot-2d.yaml:50-58` | 画布支持「滚轮缩放 / 拖拽平移 / **右键重置视图**」 | React 2D 画布只挂了 `onWheel` / `onMouseDown` / `onMouseMove` / `onMouseUp` / `onMouseLeave`，**没有** `onContextMenu`（`PlotCanvas.tsx:666-712`）；整个 React 工程只有分形页 `:396`（`preventDefault`）与几何页 `:799` 用右键，都不是"重置视图" | 用户右键不会有任何反应；要重置请点 ⟲（`PlotPage.tsx:626`） |
| 2 | `docs/tutorials-src/03-plot-2d.yaml:26-28` | 「点击「添加函数」按钮」 | 按钮文字是「＋ 添加表达式」（`ExpressionList.tsx:181`；冻结的 Vue 版 `ExpressionList.vue:173` 同） | 照着教程找不到按钮 |
| 3 | `docs/tutorials-src/02-basic-calculation.yaml:43-49` | 「点击「计算」按钮！结果会弹出显示：结果、推导步骤、数学含义」 | 按钮文字是「计算结果」（`CalcView.vue:473`）；对话框里只有结果 + `查看步骤`/`复制结果`/`复制 JSON`/`关闭`，没有"数学含义"这一栏（`ResultDialog.vue:130-140`） | 按钮名对不上；承诺的栏目不存在 |
| 4 | `docs/tutorials-src/02-basic-calculation.yaml:19-24`、`03-plot-2d.yaml:19-24` | 「在下拉菜单中选择「代数」」「选择「2D 绘图」」 | 它们是左侧导航的**列表项**（点击跳路由，不是下拉选择），且名字是「代数计算」与「2D 函数绘图」（`nav.js:23,49`；`App.vue:313-322`） | 两处都不精确；`action: select` 与实际交互不符 |
| 5 | `docs/tutorials-src/05-ai-steps-accelerate.yaml:44-51`（以及 `02-basic-calculation.yaml:51-57`） | 仍写着点「AI 加速」按钮、"每天免费 3 次" | v2 **决定不做**该按钮；构建期由 `MFMath.UI.Vue/tools/build-tutorials.mjs:83-117` 的 `V2_OVERRIDES` 把该步改指 `toolbar.ai_button` / `ai_dialog.input`，并改写了对应 FAQ。运行时数据是 `src/tutorials/tutorials.json` | 直接读 YAML 会以为有这个按钮和配额。**别把 `docs/tutorials-src/` 当运行时文案源** |
| 6 | `MF_UI/MFMath.UI.Vue/src/router/index.js:52-53`、`src/lib/router/nav.js:66-69`、`ToolboxView.vue:6-9` | 「界面模式表只覆盖 371 个，余下 **38** 个原本没有任何入口」 | 按同一算法实测：签名 424 − 模式表 371 = **53**（§5 的复跑命令）；`ToolboxView.vue:104` 运行时算出来显示的也是 53 | 注释里的 38 是旧数；读注释会低估"没有入口的函数"数量 |
| 7 | `MF_UI/MFMath.UI.Vue/src/router/index.js:4-5` | 「registry.js 里的 **25** 个导航项全部有真实组件（**14** 个在 REAL_VIEWS、**13** 个 CALC_ROUTES 走 CalcView）」 | 实测：导航项 **27** 个（15+7+3+2，命令见 §1）、`REAL_VIEWS` **15** 条键、`CALC_ROUTES` **14** 条 | 同一文件里的旧计数；不影响行为（每条路由都真有组件），但会误导读代码的人 |
| 8 | `src/components/settings/StorageGroup.vue:9-11` | 「历史记录与工作区管理依赖 P1…这三项在界面上以'待实现'列出」 | 组件里没有 `pending-tag`，三项都已落地（`StorageGroup.vue:211-279`） | 注释与代码相反（同一处已由 [../ui/SETTINGS-WORKSPACE.md](../ui/SETTINGS-WORKSPACE.md) §9 第 6 条登记；此处不另计一份） |
| 9 | `src/views/tutorial/HelpArticleView.vue:84-88` | 「这篇里有 N 步的目标界面尚未实现（引导时会在该步明确提示并允许跳过）」 | `pendingSteps` 过滤的是 `PENDING`，而 `PENDING` 现在是空对象（`targets.js:33-47`）→ 这段警告**永远不渲染**；实测教程引用的 30 个 target 已实现 30（`check-ui.mjs` 输出） | 不是缺陷，但读代码会以为存在未实现步骤 |

> 第 1～5 条是 `docs/tutorials-src/` 与 v2 代码的偏差（源 YAML 是 v1 留档，构建期覆盖是**故意**的设计，代价就是"读 YAML 会被误导"）；第 6～9 条是源码注释与代码不符（含两处旧计数），本份文档只登记、不改任何文件。
