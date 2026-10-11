# 功能清单

> 本文回答：软件有哪些功能，逐项落到页面与模式名。
> 学科模式的数量统计依据 `MF_UI/MFMath.UI.Vue/src/lib/engine/viewConfigs.js`，导航依据
> `src/lib/router/nav.js`，设置项依据 `src/lib/settings/catalog.js`。

## 1. 总览

| 分区 | 入口 | 规模 |
| --- | --- | --- |
| 学科计算 | 侧栏「计算模式」15 项 | 基础运算 1 页 + 学科视图 14 个，共 393 条模式 |
| 绘图 | 侧栏「绘图模式」7 项 | 7 条路由落在 6 个页面组件上 |
| 工具 | 侧栏「工具」3 项 | 搜索、控制台、函数工具箱 |
| AI | 顶栏「AI」按钮 | 助手对话 + 分步讲解 |
| 学习 | 侧栏「帮助」2 项 | 18 篇教程、示例库、数学键盘 |
| 系统 | 侧栏底部「设置」 | 9 组 57 项 |

侧栏共 4 个分组、27 个导航项：计算模式 15 项，绘图模式 7 项，工具 3 项，帮助 2 项。

## 2. 学科计算

「计算模式」组共 15 项。其中「基础运算」是独立计算器页，其余 14 项是学科视图。14 个学科视图
共用同一个计算界面，按学科组织模式下拉列表。

### 2.1 基础运算

计算器风格页面，30 个按键，覆盖四则运算、乘方、开方、阶乘、对数等。按键使用课本写法
（`×` `÷` `−` `√` `π`），求值前把式子转成引擎语法，页面上会显示「引擎理解为 …」说明转换结果。

### 2.2 学科视图与模式数

下表按 `viewConfigs.js` 统计。模式总数 393 条，去重后 391 个名字（「逆Fourier变换」「正交投影」
两个名字各出现在两个视图）。

| 视图 | 路由 | 模式数 |
| --- | --- | --- |
| 代数计算 | `/calc/algebra` | 59 |
| 微积分 | `/calc/calculus` | 57 |
| 概率论与数理统计 | `/calc/probability` | 39 |
| 线性代数 | `/calc/linear-algebra` | 32 |
| 泛函分析 | `/calc/functional-analysis` | 29 |
| 复分析 | `/calc/complex-analysis` | 26 |
| 数值分析 | `/calc/numerical` | 25 |
| 测度论 | `/calc/measure-theory` | 24 |
| 数论 | `/calc/number-theory` | 21 |
| 调和分析 | `/calc/harmonic-analysis` | 20 |
| 代数拓扑 | `/calc/algebraic-topology` | 18 |
| 实分析 | `/calc/real-analysis` | 18 |
| 解析几何 | `/calc/analytic-geometry` | 13 |
| 数列 | `/calc/sequences` | 12 |

每个视图都允许放多个计算块。有些模式需要额外参数（如梯形法则的上下限与子区间数），这类模式
会先弹参数框再计算。

### 2.3 计算页能做的事

| 能力 | 说明 |
| --- | --- |
| 计算块 | 表达式输入 + 模式下拉 + 「计算结果」按钮，可加多块 |
| 参数弹窗 | 需要额外参数的模式先弹「输入参数 — 模式名」框 |
| 结果对话框 | 结果用 KaTeX 排版，提供「查看步骤」「复制结果」「复制 JSON」「关闭」 |
| 撤销重做 | 「↶ 撤销」「↷ 重做」，对应 Ctrl+Z 与 Ctrl+Y |
| 工作区 | 自动保存「表达式 + 模式」，不保存结果 |

## 3. 绘图

「绘图模式」组共 7 项，由 React 绘图组渲染。2D 函数与极坐标共用同一页面，靠网格类型区分。

| 导航项 | 路由 | 页面组件 |
| --- | --- | --- |
| 2D 函数绘图 | `/plot/2d` | PlotPage |
| 极坐标 | `/plot/polar` | PlotPage（极坐标网格） |
| 3D 曲面 | `/plot/3d` | Plot3DPage |
| 复平面 | `/plot/complex` | PlotComplexPage |
| 向量场 | `/plot/vector` | PlotVectorPage |
| 自由几何 | `/plot/geometry` | PlotGeometryPage |
| 分形 | `/plot/fractal` | PlotFractalPage |

2D 绘图页支持多表达式曲线、隐函数、参数方程、参数滑块，右侧浮动按钮提供「放大」「缩小」
「缩放到适应」「重置视图」「导出图片（PNG，2 倍像素）」「切换为极坐标网格」「隐藏网格」。
6 个绘图页都有导出 PNG 的入口。绘图操作默认不入历史记录。

## 4. 工具

| 工具 | 路由 | 作用 |
| --- | --- | --- |
| 搜索 | `/tools/search` | 联网搜索，支持 DuckDuckGo、Wolfram、自定义 SearXNG 端点 |
| 控制台 | `/tools/console` | 写 Python 或 C++ 程序调用同一引擎 |
| 函数工具箱 | `/tools/toolbox` | 列出全部 424 个引擎函数并直接调用 |

### 函数工具箱

工具箱以引擎签名表为数据源，列出全部 424 个函数，按模块分组（18 个模块）。支持按函数名、
模块名、参数名过滤。每个函数右侧按参数表生成表单，标出必填与可选，填好后点「调用引擎」，
结果以引擎原始 JSON 显示。其中 53 个函数不在任何学科视图的模式表里，工具箱是它们的主要入口。

### 控制台

语言有 Python 与 C++ 两种。C++ 在组件装好后才出现在下拉里。运行需要先安装可选组件
（CPython 或 MinGW），组件从站点下载，装好后可离线使用。每次「运行 ▷」都是新进程，变量不跨次
保留。Python 侧经 `mfmath` 调引擎，C++ 侧经导入库调同一引擎。

## 5. AI

顶栏「AI」按钮打开右侧抽屉，非模态，主界面仍可操作。

| 项 | 说明 |
| --- | --- |
| 对话 | 多轮对话，流式输出，可「停止」与「清空」 |
| 工具 | 只有 `engine_find`（查函数）与 `engine_call`（调函数）两个 |
| 分步 | 结果对话框的「查看步骤」把题目交给 AI 逐步调引擎，数值由引擎给出 |
| 轮次 | 单轮工具调用上限 8 个，工具循环上限 4 轮 |

AI 不承担计算。系统提示写死「所有计算由 C++ 引擎完成」，函数名不在引擎表里的一律拒绝。AI 请求
由页面直连用户填写的端点，需在「设置 → AI」配置端点与 API Key 后才能使用。

## 6. 学习

| 项 | 数量 |
| --- | --- |
| 交互教程 | 18 篇 |
| 教程步骤 | 66 步 |
| 教程示例 | 52 条 |
| 教程 FAQ | 42 条 |
| 数学键盘 | 6 分类 126 键 |

侧栏「帮助」下有「使用教程」与「示例任务库」两项。教程可分类筛选、看进度、断点续走。示例库的
每条示例可「加载到工作区」或复制。数学键盘停靠在底部，插入 LaTeX，覆盖基础运算、微积分、线性
代数、希腊字母、概率统计与常用模板 6 类。

## 7. 系统设置

设置面板共 9 组 57 项：

| 组 | 项数 | 管什么 |
| --- | --- | --- |
| 外观 | 6 | 主题模式、配色、圆角、疏密、字体、恢复默认 |
| 计算与绘图 | 2 | 数值精度、绘图默认范围 |
| 引擎 | 6 | 版本、目录、依赖状态、函数数、推送通道、自检 |
| 组件 | 5 | CPython、MinGW、组件目录、下载源、清理 |
| AI | 11 | 开关、端点、模型、参数、密钥、上下文、隐私、测试、自检等 |
| 搜索 | 8 | 引擎、Wolfram App ID、自定义端点、超时、缓存等 |
| 账号 | 5 | 站点地址、登录会话、本机凭据、离线承诺、自检 |
| 更新 | 7 | 当前版本、通道、自动检查、间隔、手动检查等 |
| 存储与数据 | 7 | 数据目录、教程进度、设置文件、诊断包、历史、工作区、导入导出 |

主题模式支持亮色、暗色与跟随系统。更新检查只提示并显示校验值，把下载页交给系统浏览器，不自动
下载或执行安装包。

## 8. 数字复核

在仓库根目录执行：

```powershell
# 学科视图数与模式数，应为 VIEWS=14 MODES_TOTAL=393 MODES_DISTINCT=391
node --input-type=module -e "const m=await import('./MF_UI/MFMath.UI.Vue/src/lib/engine/viewConfigs.js');const ks=Object.keys(m.VIEW_CONFIGS);let t=0;for(const k of ks)t+=m.VIEW_CONFIGS[k].modes.length;const a=ks.flatMap(k=>m.VIEW_CONFIGS[k].modes);console.log('VIEWS='+ks.length,'MODES_TOTAL='+t,'MODES_DISTINCT='+new Set(a).size)"

# 导航项数，应为 calc 15 / plot 7 / tools 3 / help 2，共 27
node --input-type=module -e "const m=await import('./MF_UI/MFMath.UI.Vue/src/lib/router/nav.js');let n=0;for(const g of m.NAV_GROUPS){console.log(g.id,g.items.length);n+=g.items.length}console.log('NAV_TOTAL='+n)"

# 设置分组与项数，应为 groups=9 items=57
node --input-type=module -e "const m=await import('./MF_UI/MFMath.UI.Vue/src/lib/settings/catalog.js');console.log('groups='+m.GROUPS.length,'items='+m.ITEMS.length)"

# 教程、步骤、示例、FAQ，应为 18 / 66 / 52 / 42
node -e "const t=require('./MF_UI/MFMath.UI.Vue/src/tutorials/tutorials.json');let s=0,e=0,f=0;for(const x of t.tutorials){s+=x.steps.length;e+=x.examples.length;f+=x.faq.length}console.log(t.tutorials.length,s,e,f)"

# 引擎函数数，应为 424
node -e "const s=require('./MF_UI/MFMath.UI.Vue/src/lib/ai/engine-signatures.json');console.log(Object.keys(s).length)"
```
